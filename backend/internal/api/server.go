// Package api is the public HTTP interface.
package api

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net"
	"net/http"
	"net/url"
	"regexp"
	"runtime/debug"
	"slices"
	"strings"
	"time"

	"aquatech/internal/auth"
	"aquatech/internal/config"
	"aquatech/internal/model"
	"aquatech/internal/store"
)

const (
	maxJSON       = 1 << 20
	maxCSV        = 12 << 20
	sessionCookie = "aquatech_session"
	sessionLength = 14 * 24 * time.Hour
)

type Server struct {
	Config config.Config
	Store  *store.Store
	Model  *model.Client
	Log    *slog.Logger
	Now    func() time.Time
	logins *auth.Limiter
	signup *auth.Limiter
	ingest *auth.Limiter
}

// problem is an error that is safe to show to a client.
type problem struct {
	status        int
	code, message string
}

func (p *problem) Error() string { return p.code }

func bad(code, message string) error { return &problem{http.StatusBadRequest, code, message} }

type handler func(w http.ResponseWriter, r *http.Request) error
type userHandler func(w http.ResponseWriter, r *http.Request, u store.User) error
type pondHandler func(w http.ResponseWriter, r *http.Request, p store.Pond) error

// Handler builds the routes.
func (s *Server) Handler() http.Handler {
	s.logins = auth.NewLimiter(10, 15*time.Minute)
	s.signup = auth.NewLimiter(10, time.Hour)
	s.ingest = auth.NewLimiter(120, time.Minute)
	mux := http.NewServeMux()
	public := func(pattern string, h handler) { mux.Handle(pattern, s.wrap(h)) }
	user := func(pattern string, h userHandler) { mux.Handle(pattern, s.wrap(s.withUser(h))) }
	pond := func(pattern string, h pondHandler) { mux.Handle(pattern, s.wrap(s.withPond(h))) }

	public("GET /api/v1/health", s.health)
	public("GET /api/v1/ready", s.ready)
	public("GET /api/v1/species", s.species)
	public("POST /api/v1/auth/register", s.register)
	public("POST /api/v1/auth/login", s.login)
	public("POST /api/v1/auth/logout", s.logout)
	public("POST /api/v1/ingest", s.ingestReadings)
	user("GET /api/v1/auth/me", s.me)
	user("GET /api/v1/model", s.modelInfo)
	user("GET /api/v1/alerts", s.openAlerts)
	user("POST /api/v1/alerts/{id}/acknowledge", s.acknowledge)
	user("GET /api/v1/ponds", s.listPonds)
	user("POST /api/v1/ponds", s.createPond)
	user("DELETE /api/v1/devices/{id}", s.revokeDevice)
	pond("GET /api/v1/ponds/{id}", s.getPond)
	pond("PATCH /api/v1/ponds/{id}", s.updatePond)
	pond("DELETE /api/v1/ponds/{id}", s.deletePond)
	pond("GET /api/v1/ponds/{id}/overview", s.overview)
	pond("GET /api/v1/ponds/{id}/readings", s.listReadings)
	pond("GET /api/v1/ponds/{id}/hours", s.listHours)
	pond("GET /api/v1/ponds/{id}/forecasts", s.listForecasts)
	pond("POST /api/v1/ponds/{id}/forecasts", s.requestForecast)
	pond("GET /api/v1/ponds/{id}/accuracy", s.accuracy)
	pond("GET /api/v1/ponds/{id}/alerts", s.pondAlerts)
	pond("GET /api/v1/ponds/{id}/devices", s.listDevices)
	pond("POST /api/v1/ponds/{id}/devices", s.createDevice)
	pond("POST /api/v1/ponds/{id}/imports", s.importCSV)
	mux.Handle("/", s.wrap(func(http.ResponseWriter, *http.Request) error {
		return &problem{http.StatusNotFound, "not_found", "There is nothing at this address."}
	}))
	return s.cors(mux)
}

// cors answers only configured origins and rejects cross-site changes.
func (s *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("Cache-Control", "no-store")
		h.Add("Vary", "Origin")
		origin := r.Header.Get("Origin")
		allowed := origin != "" && slices.Contains(s.Config.Origins, origin)
		if allowed {
			h.Set("Access-Control-Allow-Origin", origin)
			h.Set("Access-Control-Allow-Credentials", "true")
		}
		if r.Method == http.MethodOptions {
			if allowed {
				h.Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE")
				h.Set("Access-Control-Allow-Headers", "Content-Type")
				h.Set("Access-Control-Max-Age", "600")
			}
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.Method != http.MethodGet && origin != "" && !allowed && !sameHost(origin, r.Host) {
			s.fail(w, r, &problem{http.StatusForbidden, "origin_not_allowed", "Requests from this site are not allowed."})
			return
		}
		next.ServeHTTP(w, r)
	})
}

func sameHost(origin, host string) bool {
	u, err := url.Parse(origin)
	return err == nil && u.Host == host
}

func (s *Server) wrap(h handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if v := recover(); v != nil {
				s.Log.Error("panic", "value", v, "stack", string(debug.Stack()))
				s.fail(w, r, errors.New("panic"))
			}
		}()
		if err := h(w, r); err != nil {
			s.fail(w, r, err)
		}
	})
}

func (s *Server) fail(w http.ResponseWriter, r *http.Request, err error) {
	var p *problem
	var large *http.MaxBytesError
	switch {
	case errors.As(err, &p):
	case errors.As(err, &large):
		p = &problem{http.StatusRequestEntityTooLarge, "too_large", "The request is too large."}
	case errors.Is(err, store.ErrNotFound):
		p = &problem{http.StatusNotFound, "not_found", "This item was not found."}
	case errors.Is(err, context.Canceled):
		return
	default:
		s.Log.Error("request failed", "method", r.Method, "path", r.URL.Path, "error", err)
		p = &problem{http.StatusInternalServerError, "internal", "Something went wrong."}
	}
	write(w, p.status, map[string]any{"error": map[string]string{"code": p.code, "message": p.message}})
}

func write(w http.ResponseWriter, status int, value any) error {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	return ignore(json.NewEncoder(w).Encode(value))
}

// ignore drops write errors, which mean that the client has gone.
func ignore(error) error { return nil }

// read decodes one strict JSON object.
func read(w http.ResponseWriter, r *http.Request, target any) error {
	if kind, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type")); kind != "application/json" {
		return &problem{http.StatusUnsupportedMediaType, "json_required", "Send JSON."}
	}
	d := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxJSON))
	d.DisallowUnknownFields()
	if err := d.Decode(target); err != nil {
		var large *http.MaxBytesError
		if errors.As(err, &large) {
			return err
		}
		return bad("invalid_json", "The request body is not valid.")
	}
	if _, err := d.Token(); err != io.EOF {
		return bad("invalid_json", "The request body must hold one object.")
	}
	return nil
}

var uuidPattern = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

func pathID(r *http.Request) (string, error) {
	id := r.PathValue("id")
	if !uuidPattern.MatchString(id) {
		return "", store.ErrNotFound
	}
	return id, nil
}

func (s *Server) withUser(h userHandler) handler {
	return func(w http.ResponseWriter, r *http.Request) error {
		c, err := r.Cookie(sessionCookie)
		if err != nil {
			return &problem{http.StatusUnauthorized, "signed_out", "Sign in to continue."}
		}
		u, err := s.Store.SessionUser(r.Context(), auth.HashSecret(c.Value))
		if errors.Is(err, store.ErrNotFound) {
			return &problem{http.StatusUnauthorized, "signed_out", "Sign in to continue."}
		}
		if err != nil {
			return err
		}
		return h(w, r, u)
	}
}

// withPond resolves a pond that belongs to the signed-in user. Others see "not found".
func (s *Server) withPond(h pondHandler) handler {
	return s.withUser(func(w http.ResponseWriter, r *http.Request, u store.User) error {
		id, err := pathID(r)
		if err != nil {
			return err
		}
		p, err := s.Store.OwnedPond(r.Context(), u.ID, id)
		if err != nil {
			return err
		}
		return h(w, r, p)
	})
}

// client identifies the caller for rate limits. Forwarded addresses count only behind a trusted proxy.
func (s *Server) client(r *http.Request) string {
	if s.Config.TrustProxy {
		parts := strings.Split(r.Header.Get("X-Forwarded-For"), ",")
		if last := strings.TrimSpace(parts[len(parts)-1]); last != "" {
			return last
		}
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) error {
	return write(w, http.StatusOK, map[string]string{"status": "ok"})
}

// ready needs the database. A missing model is reported but does not stop monitoring.
func (s *Server) ready(w http.ResponseWriter, r *http.Request) error {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	if err := s.Store.Ping(ctx); err != nil {
		return &problem{http.StatusServiceUnavailable, "database_unavailable", "The database is not available."}
	}
	return write(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) modelInfo(w http.ResponseWriter, r *http.Request, u store.User) error {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	info, err := s.Model.Info(ctx)
	if err != nil {
		s.Log.Warn("model information is unavailable", "error", err)
		return write(w, http.StatusOK, map[string]any{"available": false})
	}
	return write(w, http.StatusOK, map[string]any{"available": true, "model": info})
}
