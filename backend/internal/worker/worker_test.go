package worker

import (
	"slices"
	"testing"
	"time"

	"aquatech/internal/store"
)

var now = time.Date(2026, 1, 24, 6, 0, 0, 0, time.UTC)

func f(v float64) *float64 { return &v }

func pond(mode string) store.Pond {
	return store.Pond{Mode: mode, Timezone: "Asia/Kolkata", DOLow: f(4), DOCritical: f(3), PHLow: f(6.5), PHHigh: f(8.5), AlertProbability: 0.5}
}

func reading(age time.Duration, do float64) store.Reading {
	return store.Reading{ObservedAt: now.Add(-age), DO: &do}
}

func forecast(issue time.Time, probabilities ...float64) store.Forecast {
	out := store.Forecast{IssueTime: issue, Status: "ok"}
	for i, p := range probabilities {
		h := []int{1, 3, 6, 12}[i]
		end := issue.Add(time.Duration(h) * time.Hour)
		out.Values = append(out.Values, store.ForecastValue{Horizon: h, TargetStart: end.Add(-time.Hour), TargetEnd: end, Threshold: f(3), Probability: &p})
	}
	return out
}

func kinds(list []store.Condition) map[string]string {
	out := map[string]string{}
	for _, c := range list {
		out[c.Kind] = c.Severity
	}
	return out
}

func TestOxygenLevels(t *testing.T) {
	for do, want := range map[float64]map[string]string{
		5: {}, 3.5: {"low_oxygen": "warning"}, 2.9: {"low_oxygen": "critical"}, 0: {"zero_oxygen": "critical"}} {
		if _, active := Conditions(pond("live"), reading(time.Minute, do), nil, now); len(kinds(active)) != len(want) ||
			(len(want) > 0 && kinds(active)["low_oxygen"]+kinds(active)["zero_oxygen"] != want["low_oxygen"]+want["zero_oxygen"]) {
			t.Fatalf("DO %v gave %v", do, kinds(active))
		}
	}
}

func TestThresholdsAreOptional(t *testing.T) {
	p := pond("live")
	p.DOLow, p.DOCritical, p.PHHigh = nil, nil, nil
	r := reading(time.Minute, 0.5)
	r.PH = f(12)
	if _, active := Conditions(p, r, nil, now); len(active) != 0 {
		t.Fatal(active)
	}
}

func TestStaleDataKeepsObservedAlerts(t *testing.T) {
	assessed, active := Conditions(pond("live"), reading(3*time.Hour, 5), nil, now)
	if kinds(active)["stale_data"] == "" || slices.Contains(assessed, "low_oxygen") {
		t.Fatalf("assessed %v active %v", assessed, active)
	}
	assessed, active = Conditions(pond("demo"), reading(900*time.Hour, 2), nil, now)
	if slices.Contains(assessed, "stale_data") || kinds(active)["low_oxygen"] != "critical" {
		t.Fatalf("a demo pond is never stale: %v %v", assessed, active)
	}
}

func TestForecastAlerts(t *testing.T) {
	check := func(name string, list []store.Forecast, known, alert bool) {
		t.Helper()
		assessed, active := Conditions(pond("live"), reading(time.Minute, 6), list, now)
		_, on := kinds(active)["forecast_low_oxygen"]
		if slices.Contains(assessed, "forecast_low_oxygen") != known || on != alert {
			t.Fatalf("%s: assessed %v active %v", name, assessed, active)
		}
	}
	bad := store.Forecast{IssueTime: now, Status: "unavailable"}
	check("none", nil, true, false)
	check("low", []store.Forecast{forecast(now, .1, .2, .3, .4)}, true, false)
	check("high", []store.Forecast{forecast(now, .1, .2, .6, .4)}, true, true)
	check("past target", []store.Forecast{forecast(now.Add(-2*time.Hour), .9, .1, .1, .1)}, true, false)
	check("outage keeps the last forecast", []store.Forecast{bad, forecast(now.Add(-time.Hour), .1, .1, .7, .1)}, true, true)
	check("expired", []store.Forecast{bad, forecast(now.Add(-13*time.Hour), .9, .9, .9, .9)}, true, false)
}
