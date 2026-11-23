package store

import (
	"context"
	"time"
)

type User struct {
	ID        string    `db:"id" json:"id"`
	Email     string    `db:"email" json:"email"`
	Name      string    `db:"name" json:"name"`
	CreatedAt time.Time `db:"created_at" json:"created_at"`
}

func (s *Store) CreateUser(ctx context.Context, email, name, hash string) (User, error) {
	rows, err := s.pool.Query(ctx, `INSERT INTO users (email, name, password_hash) VALUES ($1, $2, $3)
		RETURNING id::text, email, name, created_at`, email, name, hash)
	return single[User](rows, err)
}

// Credentials returns a user ID and password hash by email.
func (s *Store) Credentials(ctx context.Context, email string) (id, hash string, err error) {
	err = s.pool.QueryRow(ctx, "SELECT id::text, password_hash FROM users WHERE lower(email) = lower($1)", email).Scan(&id, &hash)
	return id, hash, translate(err)
}

func (s *Store) CreateSession(ctx context.Context, userID string, tokenHash []byte, length time.Duration) error {
	_, err := s.pool.Exec(ctx, "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ($1, $2, now() + make_interval(secs => $3))", tokenHash, userID, length.Seconds())
	return err
}

func (s *Store) SessionUser(ctx context.Context, tokenHash []byte) (User, error) {
	rows, err := s.pool.Query(ctx, `SELECT u.id::text, u.email, u.name, u.created_at FROM sessions s JOIN users u ON u.id = s.user_id
		WHERE s.token_hash = $1 AND s.expires_at > now()`, tokenHash)
	return single[User](rows, err)
}

func (s *Store) DeleteSession(ctx context.Context, tokenHash []byte) error {
	_, err := s.pool.Exec(ctx, "DELETE FROM sessions WHERE token_hash = $1", tokenHash)
	return err
}

func (s *Store) DeleteExpiredSessions(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, "DELETE FROM sessions WHERE expires_at <= now()")
	return err
}

type Pond struct {
	ID               string    `db:"id" json:"id"`
	OwnerID          string    `db:"owner_id" json:"-"`
	Name             string    `db:"name" json:"name"`
	Timezone         string    `db:"timezone" json:"timezone"`
	Species          string    `db:"species" json:"species"`
	Mode             string    `db:"mode" json:"mode"`
	SamplingMinutes  int       `db:"sampling_minutes" json:"sampling_minutes"`
	DOLow            *float64  `db:"do_low" json:"do_low"`
	DOCritical       *float64  `db:"do_critical" json:"do_critical"`
	PHLow            *float64  `db:"ph_low" json:"ph_low"`
	PHHigh           *float64  `db:"ph_high" json:"ph_high"`
	TemperatureLow   *float64  `db:"temperature_low" json:"temperature_low"`
	TemperatureHigh  *float64  `db:"temperature_high" json:"temperature_high"`
	AlertProbability float64   `db:"alert_probability" json:"alert_probability"`
	CreatedAt        time.Time `db:"created_at" json:"created_at"`
}

// Zone is valid for every stored pond, because timezones are checked on creation.
func (p Pond) Zone() *time.Location {
	zone, err := time.LoadLocation(p.Timezone)
	if err != nil {
		return time.UTC
	}
	return zone
}

const pondColumns = `id::text, owner_id::text, name, timezone, species, mode, sampling_minutes, do_low, do_critical,
	ph_low, ph_high, temperature_low, temperature_high, alert_probability, created_at`

func (s *Store) CreatePond(ctx context.Context, p Pond) (Pond, error) {
	rows, err := s.pool.Query(ctx, `INSERT INTO ponds (owner_id, name, timezone, species, mode, sampling_minutes, do_low, do_critical,
		ph_low, ph_high, temperature_low, temperature_high, alert_probability)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) RETURNING `+pondColumns,
		p.OwnerID, p.Name, p.Timezone, p.Species, p.Mode, p.SamplingMinutes, p.DOLow, p.DOCritical,
		p.PHLow, p.PHHigh, p.TemperatureLow, p.TemperatureHigh, p.AlertProbability)
	return single[Pond](rows, err)
}

// UpdatePond changes the name, species and thresholds. Mode, timezone and sampling stay fixed,
// because stored hours depend on them.
func (s *Store) UpdatePond(ctx context.Context, p Pond) (Pond, error) {
	rows, err := s.pool.Query(ctx, `UPDATE ponds SET name = $3, species = $4, do_low = $5, do_critical = $6, ph_low = $7, ph_high = $8,
		temperature_low = $9, temperature_high = $10, alert_probability = $11 WHERE id = $1 AND owner_id = $2 RETURNING `+pondColumns,
		p.ID, p.OwnerID, p.Name, p.Species, p.DOLow, p.DOCritical, p.PHLow, p.PHHigh, p.TemperatureLow, p.TemperatureHigh, p.AlertProbability)
	return single[Pond](rows, err)
}

// SessionPond returns a pond if it belongs to the session's user, in one round trip.
func (s *Store) SessionPond(ctx context.Context, tokenHash []byte, id string) (Pond, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+pondColumns+` FROM ponds WHERE id = $2 AND owner_id =
		(SELECT user_id FROM sessions WHERE token_hash = $1 AND expires_at > now())`, tokenHash, id)
	return single[Pond](rows, err)
}

// Pond returns any pond, for background work.
func (s *Store) Pond(ctx context.Context, id string) (Pond, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+pondColumns+" FROM ponds WHERE id = $1", id)
	return single[Pond](rows, err)
}

func (s *Store) OwnedPonds(ctx context.Context, owner string) ([]Pond, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+pondColumns+" FROM ponds WHERE owner_id = $1 ORDER BY lower(name), id", owner)
	return collect[Pond](rows, err)
}

func (s *Store) LivePonds(ctx context.Context) ([]Pond, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+pondColumns+" FROM ponds WHERE mode = 'live' ORDER BY id")
	return collect[Pond](rows, err)
}

func (s *Store) DeletePond(ctx context.Context, owner, id string) error {
	return one(s.pool.Exec(ctx, "DELETE FROM ponds WHERE id = $1 AND owner_id = $2", id, owner))
}

type Device struct {
	ID         string     `db:"id" json:"id"`
	PondID     string     `db:"pond_id" json:"pond_id"`
	Name       string     `db:"name" json:"name"`
	CreatedAt  time.Time  `db:"created_at" json:"created_at"`
	LastSeenAt *time.Time `db:"last_seen_at" json:"last_seen_at"`
	RevokedAt  *time.Time `db:"revoked_at" json:"revoked_at"`
}

const deviceColumns = "id::text, pond_id::text, name, created_at, last_seen_at, revoked_at"

func (s *Store) CreateDevice(ctx context.Context, pondID, name string, keyHash []byte) (Device, error) {
	rows, err := s.pool.Query(ctx, "INSERT INTO devices (pond_id, name, key_hash) VALUES ($1, $2, $3) RETURNING "+deviceColumns, pondID, name, keyHash)
	return single[Device](rows, err)
}

func (s *Store) Devices(ctx context.Context, pondID string) ([]Device, error) {
	rows, err := s.pool.Query(ctx, "SELECT "+deviceColumns+" FROM devices WHERE pond_id = $1 ORDER BY created_at", pondID)
	return collect[Device](rows, err)
}

func (s *Store) RevokeDevice(ctx context.Context, owner, id string) error {
	return one(s.pool.Exec(ctx, `UPDATE devices d SET revoked_at = coalesce(d.revoked_at, now()) FROM ponds p
		WHERE d.id = $1 AND p.id = d.pond_id AND p.owner_id = $2`, id, owner))
}

// DeviceByKey finds an active device.
func (s *Store) DeviceByKey(ctx context.Context, keyHash []byte) (Device, error) {
	rows, err := s.pool.Query(ctx, "UPDATE devices SET last_seen_at = now() WHERE key_hash = $1 AND revoked_at IS NULL RETURNING "+deviceColumns, keyHash)
	return single[Device](rows, err)
}
