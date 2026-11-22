// Command server runs the API and the background worker.
package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
	_ "time/tzdata"

	"aquatech/internal/api"
	"aquatech/internal/config"
	"aquatech/internal/model"
	"aquatech/internal/store"
	"aquatech/internal/worker"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	if err := run(log); err != nil {
		log.Error("stopped", "error", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	env := flag.String("env", ".env", "settings file")
	migrate := flag.Bool("migrate", false, "apply database migrations and exit")
	flag.Parse()
	cfg, err := config.Load(*env)
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	opening, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()
	db, err := open(opening, cfg.DatabaseURL, log)
	if err != nil {
		return err
	}
	defer db.Close()
	if *migrate {
		applied, err := db.Migrate(ctx)
		log.Info("migrations", "applied", applied)
		return err
	}
	if err := db.CheckSchema(opening); err != nil {
		return err
	}

	client := model.New(cfg.ModelURL, cfg.ModelToken)
	server := &api.Server{Config: cfg, Store: db, Model: client, Log: log, Now: time.Now}
	web := &http.Server{Addr: cfg.Address, Handler: server.Handler(), ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 60 * time.Second, WriteTimeout: 60 * time.Second, IdleTimeout: 2 * time.Minute, MaxHeaderBytes: 16 << 10}
	background := &worker.Worker{Store: db, Model: client, Log: log, Now: time.Now}

	var work sync.WaitGroup
	work.Go(func() { background.Run(ctx) })
	failed := make(chan error, 1)
	go func() {
		log.Info("listening", "address", cfg.Address)
		if err := web.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			failed <- err
		}
	}()
	select {
	case err = <-failed:
		stop()
	case <-ctx.Done():
		closing, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		err = web.Shutdown(closing)
	}
	work.Wait()
	return err
}

// open retries for a short time, so a brief network failure does not stop the start.
func open(ctx context.Context, url string, log *slog.Logger) (*store.Store, error) {
	for {
		db, err := store.Open(ctx, url)
		if err == nil || ctx.Err() != nil {
			return db, err
		}
		log.Warn("the database is not reachable yet", "error", err)
		select {
		case <-ctx.Done():
			return nil, err
		case <-time.After(3 * time.Second):
		}
	}
}
