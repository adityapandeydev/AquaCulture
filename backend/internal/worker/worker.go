// Package worker schedules forecasts, runs them and keeps alerts current.
package worker

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"aquatech/internal/model"
	"aquatech/internal/readings"
	"aquatech/internal/store"
)

const (
	HistoryHours = 24
	// A live forecast is issued after a short wait for late readings, and only within its hour.
	settle      = 3 * time.Minute
	issueWindow = time.Hour
	// Live readings and forecasts older than this are stale.
	staleAfter     = 2 * time.Hour
	maxAttempts    = 6
	longestHorizon = 12
	lease          = 2 * time.Minute
)

type Forecaster interface {
	Forecast(context.Context, model.Request) (*model.Forecast, error)
}

type Worker struct {
	Store *store.Store
	Model Forecaster
	Log   *slog.Logger
	Now   func() time.Time
}

// Run works until the context ends.
func (w *Worker) Run(ctx context.Context) {
	schedule, poll, clean := time.NewTicker(30*time.Second), time.NewTicker(2*time.Second), time.NewTicker(time.Hour)
	defer schedule.Stop()
	defer poll.Stop()
	defer clean.Stop()
	w.log("schedule", w.Schedule(ctx))
	for {
		select {
		case <-ctx.Done():
			return
		case <-schedule.C:
			w.log("schedule", w.Schedule(ctx))
		case <-clean.C:
			w.log("session cleanup", w.Store.DeleteExpiredSessions(ctx))
		case <-poll.C:
			for ctx.Err() == nil {
				more, err := w.RunOne(ctx)
				w.log("forecast job", err)
				if !more || err != nil {
					break
				}
			}
		}
	}
}

func (w *Worker) log(what string, err error) {
	if err != nil && !errors.Is(err, context.Canceled) {
		w.Log.Error(what+" failed", "error", err)
	}
}

// Schedule queues due live forecasts and refreshes live alerts.
func (w *Worker) Schedule(ctx context.Context) error {
	ponds, err := w.Store.LivePonds(ctx)
	if err != nil {
		return err
	}
	var failures []error
	for _, p := range ponds {
		issue := readings.HourStart(w.Now(), p.Zone())
		if latest, err := w.Store.LatestReading(ctx, p.ID); err == nil && w.Now().Sub(issue) >= settle &&
			issue.Sub(latest.ObservedAt) < staleAfter {
			_, err := w.Store.Enqueue(ctx, p.ID, issue)
			failures = append(failures, err)
		} else if err != nil && !errors.Is(err, store.ErrNotFound) {
			failures = append(failures, err)
		}
		failures = append(failures, w.Assess(ctx, p))
	}
	return errors.Join(failures...)
}

// RunOne claims and completes one job. It reports whether a job was found.
func (w *Worker) RunOne(ctx context.Context) (bool, error) {
	j, err := w.Store.Claim(ctx, lease)
	if errors.Is(err, store.ErrNotFound) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	p, err := w.Store.Pond(ctx, j.PondID)
	if err != nil {
		return true, err
	}
	if p.Mode == "live" && w.Now().Sub(j.IssueTime) >= issueWindow {
		if err := w.Store.Finish(ctx, j, nil, []string{"issue_window_passed"}, true); err != nil {
			return true, err
		}
		return true, w.Assess(ctx, p)
	}
	f, err := w.forecast(ctx, p, j.IssueTime)
	var unavailable *model.Unavailable
	switch {
	case err == nil:
		err = w.Store.Finish(ctx, j, f, nil, false)
	case errors.As(err, &unavailable):
		reasons := unavailable.Reasons
		if len(reasons) == 0 {
			reasons = []string{unavailable.Code}
		}
		err = w.Store.Finish(ctx, j, nil, reasons, false)
	case j.Attempts >= maxAttempts:
		w.Log.Error("forecast given up", "pond", p.ID, "error", err)
		err = w.Store.Finish(ctx, j, nil, []string{"model_unavailable"}, true)
	default:
		w.Log.Warn("forecast will be retried", "pond", p.ID, "attempt", j.Attempts, "error", err)
		return true, w.Store.Retry(ctx, j, time.Duration(1<<j.Attempts)*5*time.Second, err.Error())
	}
	if err != nil {
		return true, err
	}
	return true, w.Assess(ctx, p)
}

func (w *Worker) forecast(ctx context.Context, p store.Pond, issue time.Time) (*model.Forecast, error) {
	hours, err := w.Store.Hours(ctx, p.ID, issue.Add(-HistoryHours*time.Hour), issue)
	if err != nil {
		return nil, err
	}
	if len(hours) == 0 {
		return nil, &model.Unavailable{Code: "no_history"}
	}
	request := model.Request{Species: p.Species, Timezone: p.Timezone, IssueTime: issue}
	for _, h := range hours {
		request.History = append(request.History, model.Hour{Start: h.Start, Coverage: h.Coverage, DO: h.DO, PH: h.PH, Temperature: h.Temperature})
	}
	return w.Model.Forecast(ctx, request)
}

var observedKinds = []string{"low_oxygen", "zero_oxygen", "ph", "temperature"}

// Assess updates a pond's alerts from its latest reading and forecast.
func (w *Worker) Assess(ctx context.Context, p store.Pond) error {
	latest, err := w.Store.LatestReading(ctx, p.ID)
	if errors.Is(err, store.ErrNotFound) {
		return nil
	}
	if err != nil {
		return err
	}
	forecasts, err := w.Store.Forecasts(ctx, p.ID, 1+longestHorizon)
	if err != nil {
		return err
	}
	assessed, active := Conditions(p, latest, forecasts, w.Now())
	return w.Store.SyncAlerts(ctx, p.ID, assessed, active)
}

// Conditions decides which alerts are active. Stale readings cannot clear an observed alert, and
// a missing forecast cannot clear a forecast alert until that forecast's own time has passed.
func Conditions(p store.Pond, latest store.Reading, forecasts []store.Forecast, now time.Time) (assessed []string, active []store.Condition) {
	add := func(kind, origin, severity, format string, values ...any) {
		active = append(active, store.Condition{Kind: kind, Origin: origin, Severity: severity, Message: fmt.Sprintf(format, values...)})
	}
	live := p.Mode == "live"
	stale := live && now.Sub(latest.ObservedAt) >= staleAfter
	if live {
		assessed = append(assessed, "stale_data")
	}
	if stale {
		add("stale_data", "system", "warning", "No reading since %s.", latest.ObservedAt.In(p.Zone()).Format("2 Jan 15:04"))
	} else {
		assessed = append(assessed, observedKinds...)
		if v := latest.DO; v != nil {
			switch {
			case *v == 0:
				add("zero_oxygen", "observed", "critical", "The sensor reports zero oxygen. Check the pond and the sensor.")
			case p.DOCritical != nil && *v < *p.DOCritical:
				add("low_oxygen", "observed", "critical", "Oxygen is %.2f mg/L, below %.2f mg/L.", *v, *p.DOCritical)
			case p.DOLow != nil && *v < *p.DOLow:
				add("low_oxygen", "observed", "warning", "Oxygen is %.2f mg/L, below %.2f mg/L.", *v, *p.DOLow)
			}
		}
		outside(latest.PH, p.PHLow, p.PHHigh, func(v float64, word string, limit float64) {
			add("ph", "observed", "warning", "pH is %.2f, %s %.2f.", v, word, limit)
		})
		outside(latest.Temperature, p.TemperatureLow, p.TemperatureHigh, func(v float64, word string, limit float64) {
			add("temperature", "observed", "warning", "Water temperature is %.1f °C, %s %.1f °C.", v, word, limit)
		})
	}
	if c, known := forecastCondition(p, forecasts, now); known {
		assessed = append(assessed, "forecast_low_oxygen")
		if c != nil {
			active = append(active, *c)
		}
	}
	return assessed, active
}

func outside(value, low, high *float64, report func(v float64, word string, limit float64)) {
	if value == nil {
		return
	}
	if low != nil && *value < *low {
		report(*value, "below", *low)
	} else if high != nil && *value > *high {
		report(*value, "above", *high)
	}
}

func forecastCondition(p store.Pond, forecasts []store.Forecast, now time.Time) (*store.Condition, bool) {
	// An outage says nothing about the pond, so the last real forecast counts until its targets pass.
	var f *store.Forecast
	for i := range forecasts {
		if forecasts[i].Status == "ok" {
			f = &forecasts[i]
			break
		}
	}
	if f == nil {
		return nil, p.Mode == "live"
	}
	var worst *store.ForecastValue
	for i, v := range f.Values {
		if v.Probability == nil || (p.Mode == "live" && !v.TargetEnd.After(now)) {
			continue
		}
		if worst == nil || *v.Probability > *worst.Probability {
			worst = &f.Values[i]
		}
	}
	if worst == nil || *worst.Probability < p.AlertProbability {
		return nil, true
	}
	zone := p.Zone()
	return &store.Condition{Kind: "forecast_low_oxygen", Origin: "forecast", Severity: "warning", Message: fmt.Sprintf(
		"%.0f%% chance that the sensor's hourly oxygen is below %.1f mg/L between %s and %s.", *worst.Probability*100, *worst.Threshold,
		worst.TargetStart.In(zone).Format("15:04"), worst.TargetEnd.In(zone).Format("15:04 on 2 Jan"))}, true
}
