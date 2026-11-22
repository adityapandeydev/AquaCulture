package store

import (
	"context"
	"time"
)

// Summary is one pond with what an operator looks at first.
type Summary struct {
	Pond
	LatestAt       *time.Time `db:"latest_at" json:"latest_at"`
	LatestDO       *float64   `db:"latest_do" json:"latest_do_mgL"`
	LatestPH       *float64   `db:"latest_ph" json:"latest_ph"`
	LatestTemp     *float64   `db:"latest_temp" json:"latest_temperature_c"`
	OpenAlerts     int        `db:"open_alerts" json:"open_alerts"`
	CriticalAlerts int        `db:"critical_alerts" json:"critical_alerts"`
	ForecastIssue  *time.Time `db:"forecast_issue" json:"forecast_issue"`
	ForecastStatus *string    `db:"forecast_status" json:"forecast_status"`
	Probability    *float64   `db:"probability" json:"highest_probability"`
	TrendEnd       *time.Time `db:"trend_end" json:"trend_end"`
	Trend          []*float64 `db:"trend" json:"trend_do_mgL"`
}

// Summaries lists an owner's ponds. The trend is the last 24 stored hours, with gaps as null.
func (s *Store) Summaries(ctx context.Context, owner string) ([]Summary, error) {
	rows, err := s.pool.Query(ctx, `SELECT `+pondColumns+`, r.latest_at, r.latest_do, r.latest_ph, r.latest_temp,
		a.open_alerts, a.critical_alerts, f.forecast_issue, f.forecast_status, f.probability, t.trend_end, t.trend
		FROM ponds
		LEFT JOIN LATERAL (SELECT observed_at AS latest_at, do_mgl AS latest_do, ph AS latest_ph, temperature_c AS latest_temp
			FROM readings WHERE pond_id = ponds.id ORDER BY observed_at DESC LIMIT 1) r ON true
		CROSS JOIN LATERAL (SELECT count(*)::int AS open_alerts, (count(*) FILTER (WHERE severity = 'critical'))::int AS critical_alerts
			FROM alerts WHERE pond_id = ponds.id AND resolved_at IS NULL) a
		LEFT JOIN LATERAL (SELECT x.issue_time AS forecast_issue, x.status AS forecast_status,
			(SELECT max(v.probability) FROM forecast_values v WHERE v.forecast_id = x.id) AS probability
			FROM forecasts x WHERE x.pond_id = ponds.id ORDER BY x.issue_time DESC LIMIT 1) f ON true
		LEFT JOIN LATERAL (SELECT e.trend_end, (SELECT array_agg(h.do_mgl ORDER BY g.s)
			FROM generate_series(e.trend_end - interval '23 hours', e.trend_end, interval '1 hour') AS g(s)
			LEFT JOIN hours h ON h.pond_id = ponds.id AND h.start_at = g.s) AS trend
			FROM (SELECT max(start_at) AS trend_end FROM hours WHERE pond_id = ponds.id) e WHERE e.trend_end IS NOT NULL) t ON true
		WHERE owner_id = $1 ORDER BY lower(name), id`, owner)
	return collect[Summary](rows, err)
}
