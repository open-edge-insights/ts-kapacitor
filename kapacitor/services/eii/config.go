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

package eii

import (
	"time"
	"github.com/influxdata/influxdb/toml"
)

const (
	// DefaultDatabase is the default DB to write to
	DefaultDatabase = "eii"

	// DefaultRetentionPolicy is the default retention policy of the writes
	DefaultRetentionPolicy = "autogen"

	// DefaultBatchSize is the default write batch size.
	DefaultBatchSize = 5000

	// DefaultBatchPending is the default number of pending write batches.
	DefaultBatchPending = 10

	// DefaultBatchDuration is the default batch timeout duration.
	DefaultBatchDuration = toml.Duration(10 * time.Second)

)

// Config represents a configuration for the collectd service.
type Config struct {
	Enabled         bool          `toml:"enabled"`
	Database        string        `toml:"database"`
	RetentionPolicy string        `toml:"retention-policy"`
	BatchSize       int           `toml:"batch-size"`
	BatchPending    int           `toml:"batch-pending"`
	BatchDuration   toml.Duration `toml:"batch-timeout"`
}

// NewConfig returns a new instance of Config with defaults.
func NewConfig() Config {
	return Config{
		Database:        DefaultDatabase,
		RetentionPolicy: DefaultRetentionPolicy,
		BatchSize:       DefaultBatchSize,
		BatchPending:    DefaultBatchPending,
		BatchDuration:   DefaultBatchDuration,
	}
}

// WithDefaults takes the given config and returns a new config with any required
// default values set.
func (c *Config) WithDefaults() *Config {
	d := *c
	if d.Database == "" {
		d.Database = DefaultDatabase
	}
	if d.RetentionPolicy == "" {
		d.RetentionPolicy = DefaultRetentionPolicy
	}
	if d.BatchSize == 0 {
		d.BatchSize = DefaultBatchSize
	}
	if d.BatchPending == 0 {
		d.BatchPending = DefaultBatchPending
	}
	if d.BatchDuration == 0 {
		d.BatchDuration = DefaultBatchDuration
	}

	return &d
}
