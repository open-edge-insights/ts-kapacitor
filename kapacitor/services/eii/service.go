package eii // import "github.com/influxdata/influxdb/services/eii"

import (
    "fmt"
    "io"
    "log"
    "os"
    "sync"
    "sync/atomic"
    "time"

    "github.com/influxdata/influxdb/models"
    "github.com/influxdata/influxdb/services/meta"
    "github.com/influxdata/influxdb/tsdb"
    eiscfgmgr "ConfigMgr/eisconfigmgr"
    eismsgbus "EISMessageBus/eismsgbus"
    "EISMessageBus/pkg/types"
)

// statistics gathered by the eii service.
const (
    statPointsReceived       = "pointsRx"
    statReadFail             = "readFail"
    statBatchesTransmitted   = "batchesTx"
    statPointsTransmitted    = "pointsTx"
    statBatchesTransmitFail  = "batchesTxFail"
    statDroppedPointsInvalid = "droppedPointsInvalid"
)

// pointsWriter is an internal interface to make testing easier.
type pointsWriter interface {
    WritePoints(database,
                retentionPolicy string,
                consistencyLevel models.ConsistencyLevel,
                points []models.Point) error
}

// metaStore is an internal interface to make testing easier.
type metaClient interface {
    CreateDatabase(name string) (*meta.DatabaseInfo, error)
}

// Service represents an EII service
type Service struct {
    Config       *Config
    MetaClient   metaClient
    PointsWriter pointsWriter
    Logger       *log.Logger
    wg          sync.WaitGroup
    batcher     *tsdb.PointBatcher
    mu          sync.RWMutex
    ready       bool          // Has the required databse/storage been created?
    done        chan struct{} // Is the service closing or closed?

    // expvar-based stats.
    stats       *Statistics
    defaultTags models.StatisticTags
}

// NewService returns a new instance of the eii service.
func NewService(c Config) *Service {
    s := Service{
        // Use defaults where necessary.
        Config: c.WithDefaults(),

        Logger:      log.New(os.Stderr, "[eii] ", log.LstdFlags),
        stats:       &Statistics{},
    }

    return &s
}

// Open starts the service.
func (s *Service) Open() error {
    s.mu.Lock()
    defer s.mu.Unlock()

    if !s.closed() {
        return nil // Already open.
    }
    s.done = make(chan struct{})

    s.Logger.Printf("Starting eii service")

    if s.Config.Database == "" {
        return fmt.Errorf("storage name is blank")
    } else if s.PointsWriter == nil {
        return fmt.Errorf("PointsWriter is nil")
    }


    // Start the points batcher.
    s.batcher = tsdb.NewPointBatcher(s.Config.BatchSize,
                                    s.Config.BatchPending,
                                    time.Duration(s.Config.BatchDuration))
    s.batcher.Start()

    // Create waitgroup for signalling goroutines to stop and start goroutines
    // that process data from eii.
    s.wg.Add(2)
    go func() { defer s.wg.Done(); s.serve() }()
    go func() { defer s.wg.Done(); s.writePoints() }()

    return nil
}

// Close stops the service.
func (s *Service) Close() error {
    s.mu.Lock()
    defer s.mu.Unlock()

    if s.closed() {
        return nil // Already closed.
    }
    close(s.done)

    // Close the connection, and wait for the goroutine to exit.
    if s.batcher != nil {
        s.batcher.Stop()
    }
    s.wg.Wait()

    // Release all remaining resources.
    s.batcher = nil
    s.done = nil
    return nil
}

func (s *Service) closed() bool {
    select {
    case <-s.done:
        // Service is closing.
        return true
    default:
    }
    return s.done == nil
}

// createInternalStorage ensures that the required storage has been created.
func (s *Service) createInternalStorage() error {
    s.mu.RLock()
    ready := s.ready
    s.mu.RUnlock()
    if ready {
        return nil
    }

    if _, err := s.MetaClient.CreateDatabase(s.Config.Database); err != nil {
        return err
    }

    // The service is now ready.
    s.mu.Lock()
    s.ready = true
    s.mu.Unlock()
    return nil
}

// SetLogOutput sets the writer to which all logs are written. It must not be
// called after Open is called.
func (s *Service) SetLogOutput(w io.Writer) {
    s.Logger = log.New(w, "[eii] ", log.LstdFlags)
}

// Statistics maintains statistics for the eii service.
type Statistics struct {
    PointsReceived       int64
    ReadFail             int64
    BatchesTransmitted   int64
    PointsTransmitted    int64
    BatchesTransmitFail  int64
    InvalidDroppedPoints int64
}

// Statistics returns statistics for periodic monitoring.
func (s *Service) Statistics(tags map[string]string) []models.Statistic {
    return []models.Statistic{{
        Name: "eii",
        Tags: s.defaultTags.Merge(tags),
        Values: map[string]interface{}{
            statPointsReceived:         atomic.LoadInt64(&s.stats.PointsReceived),
            statReadFail:               atomic.LoadInt64(&s.stats.ReadFail),
            statBatchesTransmitted:     atomic.LoadInt64(&s.stats.BatchesTransmitted),
            statPointsTransmitted:      atomic.LoadInt64(&s.stats.PointsTransmitted),
            statBatchesTransmitFail:    atomic.LoadInt64(&s.stats.BatchesTransmitFail),
            statDroppedPointsInvalid:   atomic.LoadInt64(&s.stats.InvalidDroppedPoints),
        },
    }}
}


// The thread function which is responsible for listening to publisher messages
// and send the same to the message channel. The other thread 'writePoints()'
// read from this channel and finally writes to the internal storage
func (s *Service) serve() {
    configmgr, err := eiscfgmgr.ConfigManager()
    if err != nil {
            s.Logger.Print("Fatal: Config Manager initialization failed...")
            return
    }
    defer configmgr.Destroy()

    sub_count, _ := configmgr.GetNumSubscribers()
    var subs  []*eismsgbus.Subscriber

    for sub_index := 0; sub_index < sub_count; sub_index++ {
        subctx, err := configmgr.GetSubscriberByIndex(sub_index)
        if err != nil {
            s.Logger.Printf("Error: %v to GetSubscriberByIndex %d",
                err, sub_index)
            return
        }
        defer subctx.Destroy()

        config, err := subctx.GetMsgbusConfig()
        if err != nil {
            s.Logger.Printf("Error: %v to GetMsgbusConfig", err)
            return
        }

        topics, err := subctx.GetTopics()
        if err != nil {
            s.Logger.Printf("Error: %v to GetTopics", err)
            return
        }

        endpoint, err := subctx.GetEndPoints()
        if err != nil {
            s.Logger.Printf("Error: %v to GetEndPoints", err)
            return
        }
        s.Logger.Printf("Info: Subscriber# %v endpoints: %v", sub_index, endpoint)

        client, err := eismsgbus.NewMsgbusClient(config)
        if err != nil {
            s.Logger.Printf("Error: while initializing message bus context: %v", err)
            return
        }
        defer client.Close()

        for _, topic := range topics {
            subscriber, err := client.NewSubscriber(topic)
            if err != nil {
                s.Logger.Printf("Error: %v while subscribing to topic: %v", err, topic)
                return
            }
            defer subscriber.Close()
            subs = append(subs, subscriber)
        }
    }


    for {
        select {
        case <-s.done:
            // We closed the connection, time to go.
            return
        default:
            // Keep processing.
        }

        for _, sub := range subs {
            select {
            case msg := <-sub.MessageChannel:
                s.handleMessage(msg)
            case err := <-sub.ErrorChannel:
                atomic.AddInt64(&s.stats.ReadFail, 1)
                s.Logger.Printf("Error: while receiving message: %v", err)
            }
        }

        time.Sleep(1 * time.Second)
    }
}

// Convert the received publisher data into Points data which can be wriiten
// to the Kapacitor internal storage
func (s *Service) convertMsgToPoints(msg *types.MsgEnvelope) models.Point {
    tags := make(map[string]string)

    timestamp :=  time.Now()

    point, err := models.NewPoint(msg.Name, models.NewTags(tags), msg.Data, timestamp)
    if err != nil {
        // Drop invalid points
        s.Logger.Printf("Warning: Dropping point %v: %v", msg.Name, err)
        atomic.AddInt64(&s.stats.InvalidDroppedPoints, 1)
        return nil
    }

    return point
}


func (s *Service) handleMessage(msg *types.MsgEnvelope) {
    point := s.convertMsgToPoints(msg)
    s.batcher.In() <- point
    atomic.AddInt64(&s.stats.PointsReceived, 1)
}

// The thread responsible for reading Points data from message channel and writing the same 
// to the kapacitor internal storage
func (s *Service) writePoints() {
    for {
        select {
        case <-s.done:
            return
        case batch := <-s.batcher.Out():
            // Will attempt to create the storage if not yet created.
            if err := s.createInternalStorage(); err != nil {
                s.Logger.Printf("Required storage %s not yet created: %s", s.Config.Database, err.Error())
                continue
            }

            if err := s.PointsWriter.WritePoints(s.Config.Database, s.Config.RetentionPolicy, models.ConsistencyLevelAny, batch); err == nil {
                atomic.AddInt64(&s.stats.BatchesTransmitted, 1)
                atomic.AddInt64(&s.stats.PointsTransmitted, int64(len(batch)))
            } else {
                s.Logger.Printf("failed to write point batch to storage %q: %s", s.Config.Database, err)
                atomic.AddInt64(&s.stats.BatchesTransmitFail, 1)
            }
        }
    }
}
