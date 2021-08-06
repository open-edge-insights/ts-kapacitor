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

package pipeline

// Writes the data to EII Message Bus as it is received.
//
// Example:
// stream
//        |from()
//                .database('datain')
//                .retentionPolicy('autogen')
//                .measurement('point_data')
//        @go_point_classifier()
//        // Write the data to EII Message Bus  
//        |eisOut()
//               .pubname('eisOutNode')
//               .topic('publish_test')
//

type EiiOutNode struct {
   // Include the generic node implementation.
   node
   // EII publisher name
   Pubname string `json:"pubname"`
   // EII publisher topic
   Topic string `json:"topic"`
}

// Create a new EiiOutNode that accepts any edge type.
func newEiiOutNode(wants EdgeType) *EiiOutNode{
    return &EiiOutNode{
        node: node{
            desc: "eii",
            wants: wants,
            provides: NoEdge,
        },
    }
}

