package store

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"

	"aquatech/internal/readings"
)

type Reading struct {
	ObservedAt  time.Time `db:"observed_at" json:"observed_at"`
	DO          *float64  `db:"do_mgl" json:"do_mgL"`
	PH          *float64  `db:"ph" json:"ph"`
	Temperature *float64  `db:"temperature_c" json:"temperature_c"`
	Source      string    `db:"source" json:"source"`
}

type Hour struct {
	Start        time.Time `db:"start_at" json:"start"`
	DO           *float64  `db:"do_mgl" json:"do_mgL"`
	DOMin        *float64  `db:"do_min" json:"do_min_mgL"`
	PH           *float64  `db:"ph" json:"ph"`
	Temperature  *float64  `db:"temperature_c" json:"temperature_c"`
	Coverage     float64   `db:"coverage" json:"coverage"`
	ZeroReadings int       `db:"zero_readings" json:"zero_readings"`
}

type Inserted struct {
	Stored    int `json:"stored"`
	Duplicate int `json:"duplicate"`
	Conflict  int `json:"conflict"`
}

const (
	compareSQL = `SELECT count(*), count(*) FILTER (WHERE (r.do_mgl, r.ph, r.temperature_c) IS DISTINCT FROM (n.d, n.p, n.t))
		FROM unnest($2::timestamptz[], $3::float8[], $4::float8[], $5::float8[]) AS n(at, d, p, t)
		JOIN readings r ON r.pond_id = $1 AND r.observed_at = n.at`
	insertSQL = `INSERT INTO readings (pond_id, observed_at, do_mgl, ph, temperature_c, source, device_id)
		SELECT $1, n.at, n.d, n.p, n.t, $6, $7 FROM unnest($2::timestamptz[], $3::float8[], $4::float8[], $5::float8[]) AS n(at, d, p, t)
		ON CONFLICT DO NOTHING`
	// A channel's mean needs the same coverage as DO. Zeros are treated as missing, as in model training.
	hoursSQL = `INSERT INTO hours (pond_id, start_at, do_mgl, do_min, ph, temperature_c, coverage, zero_readings)
		SELECT $1, h.start_at, avg(r.do_mgl) FILTER (WHERE r.do_mgl > 0), min(r.do_mgl) FILTER (WHERE r.do_mgl > 0),
			CASE WHEN count(*) FILTER (WHERE r.ph > 0) >= 0.75 * $3 THEN avg(r.ph) FILTER (WHERE r.ph > 0) END,
			CASE WHEN count(*) FILTER (WHERE r.temperature_c > 0) >= 0.75 * $3 THEN avg(r.temperature_c) FILTER (WHERE r.temperature_c > 0) END,
			least(1, count(*) FILTER (WHERE r.do_mgl > 0) / $3::float8), count(*) FILTER (WHERE r.do_mgl = 0)
		FROM unnest($2::timestamptz[]) AS h(start_at)
		JOIN readings r ON r.pond_id = $1 AND r.observed_at >= h.start_at AND r.observed_at < h.start_at + interval '1 hour'
		GROUP BY h.start_at
		ON CONFLICT (pond_id, start_at) DO UPDATE SET do_mgl = excluded.do_mgl, do_min = excluded.do_min, ph = excluded.ph,
			temperature_c = excluded.temperature_c, coverage = excluded.coverage, zero_readings = excluded.zero_readings, updated_at = now()`
)

// AddReadings stores readings and refreshes the affected hours in one transaction.
// A pond lock keeps concurrent uploads from leaving stale hourly values.
func (s *Store) AddReadings(ctx context.Context, p Pond, list []readings.Reading, source string, device *string) (Inserted, error) {
	var result Inserted
	if len(list) == 0 {
		return result, nil
	}
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT 1 FROM ponds WHERE id = $1 FOR UPDATE", p.ID); err != nil {
			return err
		}
		const size = 5000
		for first := 0; first < len(list); first += size {
			part := list[first:min(first+size, len(list))]
			at := make([]time.Time, len(part))
			d, ph, t := make([]*float64, len(part)), make([]*float64, len(part)), make([]*float64, len(part))
			for i, r := range part {
				at[i], d[i], ph[i], t[i] = r.ObservedAt, r.DO, r.PH, r.Temperature
			}
			var existing, conflict int
			if err := tx.QueryRow(ctx, compareSQL, p.ID, at, d, ph, t).Scan(&existing, &conflict); err != nil {
				return err
			}
			tag, err := tx.Exec(ctx, insertSQL, p.ID, at, d, ph, t, source, device)
			if err != nil {
				return err
			}
			result.Stored += int(tag.RowsAffected())
			result.Conflict += conflict
			result.Duplicate += existing - conflict
		}
		expected := max(1, 60/p.SamplingMinutes)
		_, err := tx.Exec(ctx, hoursSQL, p.ID, readings.Hours(list, p.Zone()), expected)
		return err
	})
	return result, err
}

// Existing counts how a batch compares with stored readings, without storing it.
func (s *Store) Existing(ctx context.Context, pondID string, list []readings.Reading) (duplicate, conflict int, err error) {
	at := make([]time.Time, len(list))
	d, ph, t := make([]*float64, len(list)), make([]*float64, len(list)), make([]*float64, len(list))
	for i, r := range list {
		at[i], d[i], ph[i], t[i] = r.ObservedAt, r.DO, r.PH, r.Temperature
	}
	var existing int
	err = s.pool.QueryRow(ctx, compareSQL, pondID, at, d, ph, t).Scan(&existing, &conflict)
	return existing - conflict, conflict, err
}

func (s *Store) Readings(ctx context.Context, pondID string, from, to time.Time, limit int) ([]Reading, error) {
	rows, err := s.pool.Query(ctx, `SELECT observed_at, do_mgl, ph, temperature_c, source FROM readings
		WHERE pond_id = $1 AND observed_at >= $2 AND observed_at < $3 ORDER BY observed_at DESC LIMIT $4`, pondID, from, to, limit)
	return collect[Reading](rows, err)
}

func (s *Store) LatestReading(ctx context.Context, pondID string) (Reading, error) {
	rows, err := s.pool.Query(ctx, `SELECT observed_at, do_mgl, ph, temperature_c, source FROM readings
		WHERE pond_id = $1 ORDER BY observed_at DESC LIMIT 1`, pondID)
	return single[Reading](rows, err)
}

func (s *Store) Hours(ctx context.Context, pondID string, from, to time.Time) ([]Hour, error) {
	rows, err := s.pool.Query(ctx, `SELECT start_at, do_mgl, do_min, ph, temperature_c, coverage, zero_readings FROM hours
		WHERE pond_id = $1 AND start_at >= $2 AND start_at < $3 ORDER BY start_at`, pondID, from, to)
	return collect[Hour](rows, err)
}

type Extent struct {
	First *time.Time `db:"first" json:"first"`
	Last  *time.Time `db:"last" json:"last"`
	Count int64      `db:"count" json:"count"`
}

func (s *Store) Extent(ctx context.Context, pondID string) (Extent, error) {
	rows, err := s.pool.Query(ctx, "SELECT min(observed_at) AS first, max(observed_at) AS last, count(*) AS count FROM readings WHERE pond_id = $1", pondID)
	return single[Extent](rows, err)
}
