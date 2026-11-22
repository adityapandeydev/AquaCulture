package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"

	"aquatech/internal/model"
)

type Job struct {
	ID        string    `db:"id" json:"id"`
	PondID    string    `db:"pond_id" json:"pond_id"`
	IssueTime time.Time `db:"issue_time" json:"issue_time"`
	State     string    `db:"state" json:"state"`
	Attempts  int       `db:"attempts" json:"attempts"`
}

const jobColumns = "id::text, pond_id::text, issue_time, state, attempts"

// Enqueue adds a forecast job once per pond and issue time.
func (s *Store) Enqueue(ctx context.Context, pondID string, issue time.Time) (bool, error) {
	tag, err := s.pool.Exec(ctx, "INSERT INTO jobs (pond_id, issue_time) VALUES ($1, $2) ON CONFLICT DO NOTHING", pondID, issue)
	return err == nil && tag.RowsAffected() == 1, err
}

// Claim takes one ready job. A job whose worker stopped becomes ready again when its lease ends.
func (s *Store) Claim(ctx context.Context, lease time.Duration) (Job, error) {
	rows, err := s.pool.Query(ctx, `UPDATE jobs SET state = 'running', attempts = attempts + 1, lease_until = now() + make_interval(secs => $1)
		WHERE id = (SELECT id FROM jobs WHERE (state = 'waiting' AND run_after <= now()) OR (state = 'running' AND lease_until < now())
			ORDER BY run_after FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING `+jobColumns, lease.Seconds())
	return single[Job](rows, err)
}

// Retry returns a claimed job to the queue. Only the worker holding this attempt may do so.
func (s *Store) Retry(ctx context.Context, j Job, after time.Duration, reason string) error {
	_, err := s.pool.Exec(ctx, `UPDATE jobs SET state = 'waiting', run_after = now() + make_interval(secs => $3), last_error = $4
		WHERE id = $1 AND state = 'running' AND attempts = $2`, j.ID, j.Attempts, after.Seconds(), reason)
	return err
}

// Finish stores a forecast result and closes its job together. An older attempt changes nothing.
// f is nil when no forecast could be made.
func (s *Store) Finish(ctx context.Context, j Job, f *model.Forecast, reasons []string, failed bool) error {
	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		state := "done"
		if failed {
			state = "failed"
		}
		tag, err := tx.Exec(ctx, "UPDATE jobs SET state = $3, lease_until = NULL WHERE id = $1 AND state = 'running' AND attempts = $2", j.ID, j.Attempts, state)
		if err != nil || tag.RowsAffected() == 0 {
			return err
		}
		status, id, manifest, warnings := "unavailable", (*string)(nil), (*string)(nil), []string{}
		if f != nil {
			status, id, manifest, warnings = "ok", &f.ModelID, &f.Manifest, append(warnings, f.Warnings...)
		}
		if reasons == nil {
			reasons = []string{}
		}
		var forecastID string
		err = tx.QueryRow(ctx, `INSERT INTO forecasts (pond_id, issue_time, status, model_id, manifest_sha256, reasons, warnings)
			VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING RETURNING id::text`,
			j.PondID, j.IssueTime, status, id, manifest, reasons, warnings).Scan(&forecastID)
		if errors.Is(err, pgx.ErrNoRows) || f == nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return nil
			}
			return err
		}
		if err != nil {
			return err
		}
		for _, v := range f.Forecasts {
			var low, high, threshold, probability *float64
			if v.Interval != nil {
				low, high = &v.Interval.Low, &v.Interval.High
			}
			if v.LowOxygen != nil {
				threshold, probability = &v.LowOxygen.Threshold, &v.LowOxygen.Probability
			}
			withheld := append([]string{}, v.Withheld...)
			if _, err := tx.Exec(ctx, `INSERT INTO forecast_values (forecast_id, horizon_hours, target_start, target_end, point_mgl, low_mgl,
				high_mgl, threshold_mgl, probability, withheld) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
				forecastID, v.Horizon, v.TargetStart, v.TargetEnd, v.Point, low, high, threshold, probability, withheld); err != nil {
				return err
			}
		}
		return nil
	})
}

type ForecastValue struct {
	Horizon     int       `db:"horizon_hours" json:"horizon_hours"`
	TargetStart time.Time `db:"target_start" json:"target_start"`
	TargetEnd   time.Time `db:"target_end" json:"target_end"`
	Point       *float64  `db:"point_mgl" json:"point_mgL"`
	Low         *float64  `db:"low_mgl" json:"low_mgL"`
	High        *float64  `db:"high_mgl" json:"high_mgL"`
	Threshold   *float64  `db:"threshold_mgl" json:"threshold_mgL"`
	Probability *float64  `db:"probability" json:"probability"`
	Withheld    []string  `db:"withheld" json:"withheld"`
}

type Forecast struct {
	ID        string          `db:"id" json:"id"`
	IssueTime time.Time       `db:"issue_time" json:"issue_time"`
	Status    string          `db:"status" json:"status"`
	ModelID   *string         `db:"model_id" json:"model_id"`
	Reasons   []string        `db:"reasons" json:"reasons"`
	Warnings  []string        `db:"warnings" json:"warnings"`
	CreatedAt time.Time       `db:"created_at" json:"created_at"`
	Values    []ForecastValue `db:"-" json:"values"`
}

// Forecasts returns stored forecasts, newest issue first.
func (s *Store) Forecasts(ctx context.Context, pondID string, limit int) ([]Forecast, error) {
	rows, err := s.pool.Query(ctx, `SELECT id::text, issue_time, status, model_id, reasons, warnings, created_at FROM forecasts
		WHERE pond_id = $1 ORDER BY issue_time DESC LIMIT $2`, pondID, limit)
	list, err := collect[Forecast](rows, err)
	if err != nil {
		return nil, err
	}
	index := map[string]int{}
	ids := make([]string, len(list))
	for i := range list {
		ids[i], list[i].Values = list[i].ID, []ForecastValue{}
		index[list[i].ID] = i
	}
	type row struct {
		ForecastID string `db:"forecast_id"`
		ForecastValue
	}
	rows, err = s.pool.Query(ctx, `SELECT forecast_id::text, horizon_hours, target_start, target_end, point_mgl, low_mgl, high_mgl, threshold_mgl,
		probability, withheld FROM forecast_values WHERE forecast_id = ANY($1::uuid[]) ORDER BY horizon_hours`, ids)
	values, err := collect[row](rows, err)
	if err != nil {
		return nil, err
	}
	for _, v := range values {
		i := index[v.ForecastID]
		list[i].Values = append(list[i].Values, v.ForecastValue)
	}
	return list, nil
}

type Accuracy struct {
	Horizon          int      `db:"horizon_hours" json:"horizon_hours"`
	Compared         int      `db:"compared" json:"compared"`
	Points           int      `db:"points" json:"points"`
	MAE              *float64 `db:"mae" json:"mae_mgL"`
	PersistenceMAE   *float64 `db:"persistence_mae" json:"persistence_mae_mgL"`
	Intervals        int      `db:"intervals" json:"intervals"`
	IntervalCoverage *float64 `db:"interval_coverage" json:"interval_coverage"`
	Events           int      `db:"events" json:"events"`
	Brier            *float64 `db:"brier" json:"brier"`
}

// Accuracy compares stored forecasts with hours observed later. Hours with low coverage are left out.
func (s *Store) Accuracy(ctx context.Context, pondID string) ([]Accuracy, error) {
	rows, err := s.pool.Query(ctx, `SELECT v.horizon_hours, count(*)::int AS compared, count(v.point_mgl)::int AS points,
		avg(abs(v.point_mgl - o.do_mgl)) AS mae,
		avg(abs(b.do_mgl - o.do_mgl)) FILTER (WHERE v.point_mgl IS NOT NULL) AS persistence_mae,
		count(v.low_mgl)::int AS intervals,
		avg((o.do_mgl BETWEEN v.low_mgl AND v.high_mgl)::int) FILTER (WHERE v.low_mgl IS NOT NULL)::float8 AS interval_coverage,
		(count(*) FILTER (WHERE o.do_mgl < v.threshold_mgl))::int AS events,
		avg(power(v.probability - (o.do_mgl < v.threshold_mgl)::int, 2)) AS brier
		FROM forecasts f JOIN forecast_values v ON v.forecast_id = f.id
		JOIN hours o ON o.pond_id = f.pond_id AND o.start_at = v.target_start AND o.coverage >= 0.75
		JOIN hours b ON b.pond_id = f.pond_id AND b.start_at = f.issue_time - interval '1 hour' AND b.do_mgl IS NOT NULL
		WHERE f.pond_id = $1 AND o.do_mgl IS NOT NULL GROUP BY v.horizon_hours ORDER BY v.horizon_hours`, pondID)
	return collect[Accuracy](rows, err)
}
