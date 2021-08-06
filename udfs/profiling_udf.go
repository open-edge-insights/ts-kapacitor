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

package main

import (
	"errors"
	"flag"
	"net"
	"os"
	"syscall"
	"time"

	"github.com/golang/glog"
	"github.com/influxdata/kapacitor/udf/agent"
)


// Mirrors all points it receives back to Kapacitor
type mirrorHandler struct {
	agent *agent.Agent
}

func newMirrorHandler(agent *agent.Agent) *mirrorHandler {
	return &mirrorHandler{agent: agent}
}

// Return the InfoResponse. Describing the properties of this UDF agent.
func (*mirrorHandler) Info() (*agent.InfoResponse, error) {
	glog.V(1).Infof("1. Info methos called")
	info := &agent.InfoResponse{
		Wants:    agent.EdgeType_STREAM,
		Provides: agent.EdgeType_STREAM,
		Options:  map[string]*agent.OptionInfo{},
	}
	return info, nil
}

// Initialze the handler based of the provided options.
func (*mirrorHandler) Init(r *agent.InitRequest) (*agent.InitResponse, error) {
	glog.V(1).Infof("2. Init Method Called")
	init := &agent.InitResponse{
		Success: true,
		Error:   "",
	}
	return init, nil
}

// Create a snapshot of the running state of the process.
func (*mirrorHandler) Snapshot() (*agent.SnapshotResponse, error) {
	glog.V(1).Infof("3. Snapshot Method Called")
	return &agent.SnapshotResponse{}, nil
}

// Restore a previous snapshot.
func (*mirrorHandler) Restore(req *agent.RestoreRequest) (*agent.RestoreResponse, error) {
	glog.V(1).Infof("4. Restore Method Called")
	return &agent.RestoreResponse{
		Success: true,
	}, nil
}

// Start working with the next batch
func (*mirrorHandler) BeginBatch(begin *agent.BeginBatch) error {
	glog.V(1).Infof("5. Begin Batch Method Called")
	return errors.New("batching not supported")
}

func (h *mirrorHandler) Point(p *agent.Point) error {
	// Send back the point we just received

	var temp int64
	temp = (time.Now().UnixNano() / 1e6)

	if p.FieldsInt == nil {
		p.FieldsInt = make(map[string]int64)
	}

	p.FieldsInt["ts_kapacitor_udf_entry"] = temp
	p.FieldsInt["ts_kapacitor_udf_exit"] = (time.Now().UnixNano() / 1e6)

	h.agent.Responses <- &agent.Response{
		Message: &agent.Response_Point{
			Point: p,
		},
	}

	glog.V(1).Infof("6. Point Method Called in profiling mode")

	return nil
}

func (*mirrorHandler) EndBatch(end *agent.EndBatch) error {
	glog.V(1).Infof("7. EndBatch Method Called")
	return nil
}

// Stop the handler gracefully.
func (h *mirrorHandler) Stop() {
	close(h.agent.Responses)
}

type accepter struct {
	count int64
}

// Create a new agent/handler for each new connection.
// Count and log each new connection and termination.
func (acc *accepter) Accept(conn net.Conn) {
	glog.Infof("8. Accept Method Called")
	count := acc.count
	acc.count++
	a := agent.New(conn, conn)
	h := newMirrorHandler(a)
	a.Handler = h

	glog.Infof("Starting agent for connection", count)
	a.Start()
	go func() {
		err := a.Wait()
		if err != nil {
			glog.Fatal(err)
		}
		glog.Infof("Agent for connection %d finished", count)
	}()
}

var socketPath = flag.String("socket", "/tmp/profiling_udf", "Where to create the unix socket")

func main() {
	flag.Parse()

	//Removing the socket file below to address the `bind address already in use` issue
	os.Remove(*socketPath)

	// Create unix socket
	addr, err := net.ResolveUnixAddr("unix", *socketPath)
	if err != nil {
		glog.Fatal(err)
	}

	l, err := net.ListenUnix("unix", addr)
	if err != nil {
		glog.Fatal(err)
	}

	err = os.Chmod(*socketPath, 0755)
	if err != nil {
		glog.Fatal(err)
	}

	// Create server that listens on the socket
	s := agent.NewServer(l, &accepter{})

	// Setup signal handler to stop Server on various signals
	s.StopOnSignals(os.Interrupt, syscall.SIGTERM)

	glog.Infoln("Server listening on", addr.String())
	err = s.Serve()
	if err != nil {
		glog.Fatal(err)
	}
	glog.Infoln("Server stopped")
}
