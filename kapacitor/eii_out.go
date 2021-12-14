/*
Copyright (c) 2021 Intel Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

package kapacitor

import (
    "github.com/influxdata/kapacitor/edge"
    "github.com/influxdata/kapacitor/pipeline"
    "github.com/golang/glog"
    eiicfgmgr "github.com/open-edge-insights/eii-configmgr-go/eiiconfigmgr"
    eiimsgbus "github.com/open-edge-insights/eii-messagebus-go/eiimsgbus"
)

type EiiOutNode struct {
    // Include the generic node implementation
    node
    // Keep a reference to the pipeline node
    h *pipeline.EiiOutNode
    publisher *eiimsgbus.Publisher
    client *eiimsgbus.MsgbusClient
    batchBuffer *edge.BatchBuffer
}

func newEiiOutNode(et *ExecutingTask, n *pipeline.EiiOutNode, d NodeDiagnostic) (*EiiOutNode, error) {
    h := &EiiOutNode{
        // pass in necessary fields to the 'node' struct
        node: node{Node: n, et: et, diag: d},
        // Keep a reference to the pipeline.HouseDBOutNode
        h: n,
        batchBuffer: new(edge.BatchBuffer),
    }
    // Set the function to be called when running the node
    // more on this in a bit.
    h.node.runF = h.runOut
    h.initPublisher()
    return h, nil
}

func (h *EiiOutNode) runOut(snapshot []byte) error {
    consumer := edge.NewConsumerWithReceiver(
        h.ins[0],
        h,
    )
    return consumer.Consume()
}

func (h *EiiOutNode) BeginBatch(begin edge.BeginBatchMessage) (error) {
    return h.batchBuffer.BeginBatch(begin)
}

func (h *EiiOutNode) BatchPoint(bp edge.BatchPointMessage) (error) {
    return h.batchBuffer.BatchPoint(bp)
}

func (h *EiiOutNode) EndBatch(end edge.EndBatchMessage) (error) {
    msg := h.batchBuffer.BufferedBatchMessage(end)
    return h.write(msg)
}

func (h *EiiOutNode) Point(p edge.PointMessage) (error) {
    batch := edge.NewBufferedBatchMessage(
        edge.NewBeginBatchMessage(
            p.Name(),
            p.Tags(),
            p.Dimensions().ByName,
            p.Time(),
            1,
        ),
        []edge.BatchPointMessage{
            edge.NewBatchPointMessage(
                p.Fields(),
                p.Tags(),
                p.Time(),
            ),
        },
        edge.NewEndBatchMessage(),
    )
    return h.write(batch)
}

func (h *EiiOutNode) Barrier(b edge.BarrierMessage) (error) {
    return nil
}

func (h *EiiOutNode) DeleteGroup(d edge.DeleteGroupMessage) (error) {
    return nil
}

func (h *EiiOutNode) Done() {
    if h.publisher != nil  {
        h.publisher.Close()
    }
    if h.client != nil {
        h.client.Close()
    }
}

// Write a batch of data to HouseDB
func (h *EiiOutNode) write(batch edge.BufferedBatchMessage) error {
    // Implement writing to HouseDB here...
    point := batch.Points()[0]
    var ivalue interface{}
    var cvalue interface{}
    fields := make(map[string]interface{})
    for key, value  := range  point.Fields(){
        ivalue = value
        switch ivalue.(type) {
        case int64:
            val := int(ivalue.(int64))
            cvalue = val
        default:
            cvalue = ivalue
        }
        fields[key] = cvalue
    }

    if h.publisher != nil {
        h.publisher.Publish(fields)
    }
    return nil
}

func (h *EiiOutNode) initPublisher() error {
    configmgr, err := eiicfgmgr.ConfigManager()
    if err != nil {
        glog.Errorln("Error: Config Manager initialization failed...")
        return err
    }
    defer configmgr.Destroy()

    pubctx, err := configmgr.GetPublisherByName(h.h.Pubname)
    if err != nil {
        glog.Errorf("Error: %v to GetPublisherByIndex\n", err)
        return err
    }
    defer pubctx.Destroy()

    endpoint, err := pubctx.GetEndPoints()
    if err != nil {
        glog.Errorf("Error: %v to GetEndPoints\n", err)
        return err
    }

    glog.V(1).Infof("Publisher's endpoint: %v\n", endpoint)

    topics, err := pubctx.GetTopics()
    if err != nil {
        glog.Errorf("Error: %v to GetTopics\n", err)
        return err
    }

    glog.V(1).Infof("Publisher Topics are %v\n", topics)

    config, err := pubctx.GetMsgbusConfig()
    if err != nil {
        glog.Errorf("Error occured with error:%v\n", err)
        return err
    }

    h.client, err = eiimsgbus.NewMsgbusClient(config)
    if err != nil {
        glog.Errorf("Error initializing message bus context: %v\n", err)
        return err
    }

    h.publisher, err = h.client.NewPublisher(h.h.Topic)
    if err != nil {
        glog.Errorf("Error creating publisher: %v\n", err)
        return err
    }

    return nil
}
