package readings

import (
	"strings"
	"testing"
	"time"
)

var (
	ist, _ = time.LoadLocation("Asia/Kolkata")
	now    = time.Date(2026, 1, 24, 12, 0, 0, 0, time.UTC)
)

func TestHourStartUsesLocalHours(t *testing.T) {
	got := HourStart(time.Date(2026, 1, 24, 6, 14, 59, 5, ist), ist)
	if want := time.Date(2026, 1, 24, 0, 30, 0, 0, time.UTC); !got.Equal(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	// Both hours labelled 01:00 on the autumn change stay separate.
	york, _ := time.LoadLocation("America/New_York")
	first := time.Date(2026, 11, 1, 5, 30, 0, 0, time.UTC)
	if a, b := HourStart(first, york), HourStart(first.Add(time.Hour), york); b.Sub(a) != time.Hour {
		t.Fatalf("repeated hour merged: %v %v", a, b)
	}
}

func TestParseCSV(t *testing.T) {
	text := "\xef\xbb\xbftimestamp,DO_mgL,ph,temperature_c\n" +
		"2026-01-24 06:00:00,5.5,8.4,25\n" + // local time
		"2026-01-24T00:45:00Z,5.1,,\n" +
		"2026-01-24 06:00:00,5.5,8.4,25\n" + // identical repeat
		"2026-01-24 07:00:00,4,8,25\n" +
		"2026-01-24 07:00:00,9,8,25\n" + // conflict
		"2026-01-24 08:00:00,-1,8,25\n" +
		"2026-01-24 08:15:00,NaN,8,25\n" +
		"not a time,5,8,25\n" +
		"2026-01-25 08:00:00,5,8,25\n" + // future
		"2026-01-24 09:00:00,,,\n" +
		"2026-01-24 09:15:00,0,8,25\n"
	b, err := ParseCSV(strings.NewReader(text), ist, now)
	if err != nil {
		t.Fatal(err)
	}
	if b.Rows != 11 || len(b.Accepted) != 3 || b.Repeated != 1 || b.Rejected != 7 {
		t.Fatalf("rows %d accepted %d repeated %d rejected %d %v", b.Rows, len(b.Accepted), b.Repeated, b.Rejected, b.Rejections)
	}
	if want := time.Date(2026, 1, 24, 0, 30, 0, 0, time.UTC); !b.Accepted[0].ObservedAt.Equal(want) {
		t.Fatalf("local time read as %v", b.Accepted[0].ObservedAt)
	}
	if b.Accepted[1].PH != nil || *b.Accepted[2].DO != 0 {
		t.Fatal("missing and zero values must stay distinct")
	}
	reasons := map[string]int{}
	for _, r := range b.Rejections {
		reasons[r.Reason]++
	}
	for reason, n := range map[string]int{"conflicting_values_for_time": 2, "do_out_of_bounds": 1, "invalid_number_do_mgl": 1, "invalid_time": 1, "future_time": 1, "no_values": 1} {
		if reasons[reason] != n {
			t.Fatalf("%s: %d, want %d (%v)", reason, reasons[reason], n, reasons)
		}
	}
	if b.Rejections[0].Line != 5 {
		t.Fatalf("first rejection at line %d", b.Rejections[0].Line)
	}
}

func TestParseCSVHeader(t *testing.T) {
	for _, text := range []string{"", "time,do\n", "timestamp,do_mgl,do_mgl\n"} {
		if _, err := ParseCSV(strings.NewReader(text), ist, now); err == nil {
			t.Fatalf("accepted header %q", text)
		}
	}
}
