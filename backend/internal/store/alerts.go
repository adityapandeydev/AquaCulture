package store

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5"
)

// Condition is one alert that is currently true for a pond.
type Condition struct {
	Kind, Origin, Severity, Message string
}

type Alert struct {
	ID             string     `db:"id" json:"id"`
	PondID         string     `db:"pond_id" json:"pond_id"`
	Kind           string     `db:"kind" json:"kind"`
	Origin         string     `db:"origin" json:"origin"`
	Severity       string     `db:"severity" json:"severity"`
	Message        string     `db:"message" json:"message"`
	OpenedAt       time.Time  `db:"opened_at" json:"opened_at"`
	LastSeenAt     time.Time  `db:"last_seen_at" json:"last_seen_at"`
	AcknowledgedAt *time.Time `db:"acknowledged_at" json:"acknowledged_at"`
	ResolvedAt     *time.Time `db:"resolved_at" json:"resolved_at"`
}

const alertColumns = `a.id::text, a.pond_id::text, a.kind, a.origin, a.severity, a.message, a.opened_at, a.last_seen_at, a.acknowledged_at, a.resolved_at`

// SyncAlerts opens or refreshes active conditions and resolves the others among the assessed kinds.
// Kinds that could not be assessed are left as they are. A rise in severity clears acknowledgement.
func (s *Store) SyncAlerts(ctx context.Context, pondID string, assessed []string, active []Condition) error {
	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		kinds := []string{}
		for _, c := range active {
			kinds = append(kinds, c.Kind)
			if _, err := tx.Exec(ctx, `INSERT INTO alerts (pond_id, kind, origin, severity, message) VALUES ($1, $2, $3, $4, $5)
				ON CONFLICT (pond_id, kind) WHERE resolved_at IS NULL DO UPDATE SET message = excluded.message, last_seen_at = now(),
				acknowledged_at = CASE WHEN alerts.severity = 'warning' AND excluded.severity = 'critical' THEN NULL ELSE alerts.acknowledged_at END,
				severity = excluded.severity`, pondID, c.Kind, c.Origin, c.Severity, c.Message); err != nil {
				return err
			}
		}
		_, err := tx.Exec(ctx, `UPDATE alerts SET resolved_at = now() WHERE pond_id = $1 AND resolved_at IS NULL
			AND kind = ANY($2::text[]) AND NOT kind = ANY($3::text[])`, pondID, assessed, kinds)
		return err
	})
}

func (s *Store) Alerts(ctx context.Context, pondID string, openOnly bool, limit int) ([]Alert, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+alertColumns+` FROM alerts a WHERE a.pond_id = $1 AND (NOT $2 OR a.resolved_at IS NULL)
		ORDER BY a.resolved_at IS NULL DESC, a.opened_at DESC LIMIT $3`, pondID, openOnly, limit)
	return collect[Alert](rows, err)
}

// OpenAlerts lists open alerts of every pond an owner has.
func (s *Store) OpenAlerts(ctx context.Context, owner string) ([]Alert, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+alertColumns+` FROM alerts a JOIN ponds p ON p.id = a.pond_id
		WHERE p.owner_id = $1 AND a.resolved_at IS NULL ORDER BY a.severity, a.opened_at DESC LIMIT 200`, owner)
	return collect[Alert](rows, err)
}

func (s *Store) Acknowledge(ctx context.Context, owner, id string) (Alert, error) {
	rows, err := s.pool.Query(ctx, `UPDATE alerts a SET acknowledged_at = coalesce(a.acknowledged_at, now()) FROM ponds p
		WHERE a.id = $1 AND p.id = a.pond_id AND p.owner_id = $2 RETURNING `+alertColumns, id, owner)
	return single[Alert](rows, err)
}
