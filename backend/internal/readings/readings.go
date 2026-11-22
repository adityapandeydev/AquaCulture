// Package readings validates sensor values and parses CSV imports.
package readings

import (
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"math"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Reading is one timestamped set of sensor values. Missing channels are nil.
type Reading struct {
	ObservedAt  time.Time `json:"observed_at"`
	DO          *float64  `json:"do_mgL"`
	PH          *float64  `json:"ph"`
	Temperature *float64  `json:"temperature_c"`
}

const (
	MaxImportRows = 100000
	futureLimit   = 5 * time.Minute
)

// Validate checks physical bounds. A DO of exactly zero is kept, because it may be a sensor
// fault or real oxygen loss, and both need attention.
func (r Reading) Validate(now time.Time) error {
	if r.ObservedAt.IsZero() || r.ObservedAt.Year() < 2000 {
		return errors.New("invalid_time")
	}
	if r.ObservedAt.After(now.Add(futureLimit)) {
		return errors.New("future_time")
	}
	if r.DO == nil && r.PH == nil && r.Temperature == nil {
		return errors.New("no_values")
	}
	for _, c := range []struct {
		name      string
		value     *float64
		low, high float64
	}{{"do", r.DO, 0, 40}, {"ph", r.PH, 0, 14}, {"temperature", r.Temperature, -5, 50}} {
		if c.value != nil && (math.IsNaN(*c.value) || *c.value < c.low || *c.value > c.high) {
			return errors.New(c.name + "_out_of_bounds")
		}
	}
	return nil
}

func equal(a, b *float64) bool {
	return (a == nil) == (b == nil) && (a == nil || *a == *b)
}

// Same reports whether two readings hold identical values.
func (r Reading) Same(o Reading) bool {
	return equal(r.DO, o.DO) && equal(r.PH, o.PH) && equal(r.Temperature, o.Temperature)
}

type Rejection struct {
	Line   int    `json:"line"`
	Reason string `json:"reason"`
}

// Batch is the result of checking many readings. Conflicting values for one time are rejected.
type Batch struct {
	Rows       int
	Accepted   []Reading
	Repeated   int
	Rejected   int
	Rejections []Rejection
}

const maxRejections = 20

func (b *Batch) reject(line int, reason string) {
	b.Rejected++
	if len(b.Rejections) < maxRejections {
		b.Rejections = append(b.Rejections, Rejection{line, reason})
	}
}

type numbered struct {
	line int
	r    Reading
}

func (b *Batch) finish(rows []numbered) {
	groups := map[int64][]numbered{}
	for _, n := range rows {
		n.r.ObservedAt = n.r.ObservedAt.UTC().Truncate(time.Microsecond)
		key := n.r.ObservedAt.UnixMicro()
		groups[key] = append(groups[key], n)
	}
	for _, group := range groups {
		same := true
		for _, n := range group[1:] {
			same = same && n.r.Same(group[0].r)
		}
		if same {
			b.Accepted = append(b.Accepted, group[0].r)
			b.Repeated += len(group) - 1
			continue
		}
		// No value can be preferred, so none is stored.
		for _, n := range group {
			b.reject(n.line, "conflicting_values_for_time")
		}
	}
	sort.Slice(b.Accepted, func(i, j int) bool { return b.Accepted[i].ObservedAt.Before(b.Accepted[j].ObservedAt) })
	sort.Slice(b.Rejections, func(i, j int) bool { return b.Rejections[i].Line < b.Rejections[j].Line })
}

// Check validates readings from a device.
func Check(list []Reading, now time.Time) Batch {
	b := Batch{Rows: len(list)}
	var rows []numbered
	for i, r := range list {
		if err := r.Validate(now); err != nil {
			b.reject(i+1, err.Error())
			continue
		}
		rows = append(rows, numbered{i + 1, r})
	}
	b.finish(rows)
	return b
}

// ParseCSV reads a file with the columns timestamp, do_mgl and optionally ph and temperature_c.
// Times without an offset are read in the pond's timezone.
func ParseCSV(body io.Reader, zone *time.Location, now time.Time) (Batch, error) {
	reader := csv.NewReader(body)
	reader.FieldsPerRecord = -1
	reader.TrimLeadingSpace = true
	header, err := reader.Read()
	if err != nil {
		return Batch{}, errors.New("the file has no header row")
	}
	index := map[string]int{}
	for i, name := range header {
		name = strings.ToLower(strings.TrimSpace(strings.TrimPrefix(name, "\ufeff")))
		if _, seen := index[name]; seen {
			return Batch{}, fmt.Errorf("column %q appears twice", name)
		}
		index[name] = i
	}
	for _, name := range []string{"timestamp", "do_mgl"} {
		if _, ok := index[name]; !ok {
			return Batch{}, fmt.Errorf("column %q is required", name)
		}
	}
	b, rows := Batch{}, []numbered(nil)
	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		line, _ := reader.FieldPos(0)
		if err != nil {
			return Batch{}, fmt.Errorf("the file is not valid CSV: %w", err)
		}
		if b.Rows++; b.Rows > MaxImportRows {
			return Batch{}, fmt.Errorf("the file has more than %d rows", MaxImportRows)
		}
		r, reason := parseRecord(record, index, zone)
		if reason == "" {
			if err := r.Validate(now); err != nil {
				reason = err.Error()
			}
		}
		if reason != "" {
			b.reject(line, reason)
			continue
		}
		rows = append(rows, numbered{line, r})
	}
	b.finish(rows)
	return b, nil
}

func parseRecord(record []string, index map[string]int, zone *time.Location) (Reading, string) {
	field := func(name string) string {
		if i, ok := index[name]; ok && i < len(record) {
			return strings.TrimSpace(record[i])
		}
		return ""
	}
	var r Reading
	var err error
	if r.ObservedAt, err = parseTime(field("timestamp"), zone); err != nil {
		return r, "invalid_time"
	}
	for name, target := range map[string]**float64{"do_mgl": &r.DO, "ph": &r.PH, "temperature_c": &r.Temperature} {
		text := field(name)
		if text == "" {
			continue
		}
		value, err := strconv.ParseFloat(text, 64)
		if err != nil || math.IsNaN(value) || math.IsInf(value, 0) {
			return r, "invalid_number_" + name
		}
		*target = &value
	}
	return r, ""
}

func parseTime(text string, zone *time.Location) (time.Time, error) {
	if t, err := time.Parse(time.RFC3339Nano, text); err == nil {
		return t, nil
	}
	for _, layout := range []string{"2006-01-02 15:04:05", "2006-01-02T15:04:05", "2006-01-02 15:04"} {
		if t, err := time.ParseInLocation(layout, text, zone); err == nil {
			return t, nil
		}
	}
	return time.Time{}, errors.New("unknown time format")
}

// HourStart returns the start of the local clock hour that contains t.
// It subtracts minutes instead of rebuilding the date, so repeated hours stay distinct.
func HourStart(t time.Time, zone *time.Location) time.Time {
	l := t.In(zone)
	return t.Add(-time.Duration(l.Minute())*time.Minute - time.Duration(l.Second())*time.Second - time.Duration(l.Nanosecond())).UTC()
}

// Hours lists the distinct local hours touched by readings.
func Hours(list []Reading, zone *time.Location) []time.Time {
	var out []time.Time
	seen := map[int64]bool{}
	for _, r := range list {
		h := HourStart(r.ObservedAt, zone)
		if !seen[h.Unix()] {
			seen[h.Unix()] = true
			out = append(out, h)
		}
	}
	return out
}
