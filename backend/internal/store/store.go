// Package store is the PostgreSQL data layer.
package store

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"io/fs"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

var (
	ErrNotFound = errors.New("not found")
	ErrConflict = errors.New("already exists")
)

//go:embed migrations/*.sql
var migrations embed.FS

type Store struct{ pool *pgxpool.Pool }

func Open(ctx context.Context, url string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, errors.New("the database URL could not be parsed")
	}
	cfg.MaxConns = 10
	cfg.MaxConnIdleTime = 2 * time.Minute
	// Times are returned in UTC, whatever the server's own timezone is.
	cfg.AfterConnect = func(_ context.Context, conn *pgx.Conn) error {
		conn.TypeMap().RegisterType(&pgtype.Type{Name: "timestamptz", OID: pgtype.TimestamptzOID,
			Codec: &pgtype.TimestamptzCodec{ScanLocation: time.UTC}})
		return nil
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &Store{pool}, nil
}

func (s *Store) Close() { s.pool.Close() }

func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

// Migrate applies new migrations in one transaction. It refuses a database whose tables it
// did not create, so it can never alter an older application's data.
func (s *Store) Migrate(ctx context.Context) ([]string, error) {
	files, err := fs.Glob(migrations, "migrations/*.sql")
	if err != nil {
		return nil, err
	}
	sort.Strings(files)
	var applied []string
	err = pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, "SELECT pg_advisory_xact_lock(74120001)"); err != nil {
			return err
		}
		var known bool
		var tables int
		err := tx.QueryRow(ctx, `SELECT count(*) FILTER (WHERE tablename = 'aquatech_migrations') > 0, count(*)
			FROM pg_tables WHERE schemaname = current_schema()`).Scan(&known, &tables)
		if err != nil {
			return err
		}
		if !known && tables > 0 {
			return fmt.Errorf("the database already has %d tables from another application", tables)
		}
		if _, err := tx.Exec(ctx, `CREATE TABLE IF NOT EXISTS aquatech_migrations (
			name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`); err != nil {
			return err
		}
		for _, file := range files {
			var done bool
			if err := tx.QueryRow(ctx, "SELECT EXISTS (SELECT 1 FROM aquatech_migrations WHERE name = $1)", file).Scan(&done); err != nil {
				return err
			}
			if done {
				continue
			}
			text, err := migrations.ReadFile(file)
			if err != nil {
				return err
			}
			// Several statements need the simple protocol.
			if _, err := tx.Conn().PgConn().Exec(ctx, string(text)).ReadAll(); err != nil {
				return fmt.Errorf("%s: %w", file, err)
			}
			if _, err := tx.Exec(ctx, "INSERT INTO aquatech_migrations (name) VALUES ($1)", file); err != nil {
				return err
			}
			applied = append(applied, file)
		}
		return nil
	})
	return applied, err
}

func translate(err error) error {
	var pg *pgconn.PgError
	switch {
	case errors.Is(err, pgx.ErrNoRows):
		return ErrNotFound
	case errors.As(err, &pg) && pg.Code == "23505":
		return ErrConflict
	}
	return err
}

// one reports ErrNotFound when a statement changed nothing.
func one(tag pgconn.CommandTag, err error) error {
	if err == nil && tag.RowsAffected() == 0 {
		return ErrNotFound
	}
	return translate(err)
}

func collect[T any](rows pgx.Rows, err error) ([]T, error) {
	if err != nil {
		return nil, err
	}
	list, err := pgx.CollectRows(rows, pgx.RowToStructByName[T])
	if list == nil {
		list = []T{}
	}
	return list, err
}

func single[T any](rows pgx.Rows, err error) (T, error) {
	var zero T
	if err != nil {
		return zero, translate(err)
	}
	v, err := pgx.CollectExactlyOneRow(rows, pgx.RowToStructByName[T])
	return v, translate(err)
}

// CheckSchema reports whether every migration has been applied.
func (s *Store) CheckSchema(ctx context.Context) error {
	files, err := fs.Glob(migrations, "migrations/*.sql")
	if err != nil {
		return err
	}
	var exists bool
	if err := s.pool.QueryRow(ctx, "SELECT to_regclass('aquatech_migrations') IS NOT NULL").Scan(&exists); err != nil {
		return err
	}
	var count int
	if exists {
		if err := s.pool.QueryRow(ctx, "SELECT count(*) FROM aquatech_migrations WHERE name = ANY($1::text[])", files).Scan(&count); err != nil {
			return err
		}
	}
	if count != len(files) {
		return errors.New("the database is not migrated, run the server with -migrate first")
	}
	return nil
}
