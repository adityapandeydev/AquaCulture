package api

import (
	"errors"
	"mime"
	"net/http"
	"strconv"
	"strings"
	"time"

	"aquatech/internal/auth"
	"aquatech/internal/readings"
	"aquatech/internal/store"
	"aquatech/internal/worker"
)

const (
	maxBatch = 2000
	maxRange = 120 * 24 * time.Hour
)

func (s *Server) assess(r *http.Request, p store.Pond) error {
	w := worker.Worker{Store: s.Store, Log: s.Log, Now: s.Now}
	return w.Assess(r.Context(), p)
}

// ingestReadings accepts readings from a device key.
func (s *Server) ingestReadings(w http.ResponseWriter, r *http.Request) error {
	key, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Device ")
	denied := &problem{http.StatusUnauthorized, "unknown_device", "A valid device key is required."}
	if !ok || key == "" {
		return denied
	}
	if !s.ingest.Allow(s.client(r), s.Now()) {
		return tooMany()
	}
	d, err := s.Store.DeviceByKey(r.Context(), auth.HashSecret(key))
	if errors.Is(err, store.ErrNotFound) {
		return denied
	}
	if err != nil {
		return err
	}
	var in struct {
		Readings []readings.Reading `json:"readings"`
	}
	if err := read(w, r, &in); err != nil {
		return err
	}
	if len(in.Readings) < 1 || len(in.Readings) > maxBatch {
		return bad("invalid_batch", "Send 1 to 2000 readings.")
	}
	p, err := s.Store.Pond(r.Context(), d.PondID)
	if err != nil {
		return err
	}
	batch := readings.Check(in.Readings, s.Now())
	result, err := s.Store.AddReadings(r.Context(), p, batch.Accepted, "device", &d.ID)
	if err != nil {
		return err
	}
	if err := s.assess(r, p); err != nil {
		return err
	}
	return write(w, http.StatusOK, batchReport(batch, result, true))
}

func batchReport(b readings.Batch, r store.Inserted, stored bool) map[string]any {
	if b.Rejections == nil {
		b.Rejections = []readings.Rejection{}
	}
	out := map[string]any{"rows": b.Rows, "valid": len(b.Accepted), "repeated": b.Repeated, "rejected": b.Rejected,
		"rejections": b.Rejections, "duplicate": r.Duplicate, "conflict": r.Conflict, "committed": stored}
	if stored {
		out["stored"] = r.Stored
	}
	if n := len(b.Accepted); n > 0 {
		out["first"], out["last"] = b.Accepted[0].ObservedAt, b.Accepted[n-1].ObservedAt
	}
	return out
}

// importCSV previews a file, and stores it only with commit=true.
func (s *Server) importCSV(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	if kind, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type")); kind != "text/csv" {
		return &problem{http.StatusUnsupportedMediaType, "csv_required", "Send a CSV file."}
	}
	batch, err := readings.ParseCSV(http.MaxBytesReader(w, r.Body, maxCSV), p.Zone(), s.Now())
	if err != nil {
		var large *http.MaxBytesError
		if errors.As(err, &large) {
			return err
		}
		return bad("invalid_csv", "The file cannot be read: "+err.Error()+".")
	}
	if r.URL.Query().Get("commit") != "true" {
		var compared store.Inserted
		if compared.Duplicate, compared.Conflict, err = s.Store.Existing(r.Context(), p.ID, batch.Accepted); err != nil {
			return err
		}
		return write(w, http.StatusOK, batchReport(batch, compared, false))
	}
	result, err := s.Store.AddReadings(r.Context(), p, batch.Accepted, "import", nil)
	if err != nil {
		return err
	}
	if err := s.assess(r, p); err != nil {
		return err
	}
	return write(w, http.StatusOK, batchReport(batch, result, true))
}

// period reads the from and to parameters.
func (s *Server) period(r *http.Request) (from, to time.Time, err error) {
	q := r.URL.Query()
	to = s.Now().Add(time.Hour)
	for name, target := range map[string]*time.Time{"to": &to, "from": &from} {
		if text := q.Get(name); text != "" {
			if *target, err = time.Parse(time.RFC3339, text); err != nil {
				return from, to, bad("invalid_time", "Times must look like 2026-01-24T06:00:00Z.")
			}
		}
	}
	if from.IsZero() {
		from = to.Add(-48 * time.Hour)
	}
	if !from.Before(to) || to.Sub(from) > maxRange {
		return from, to, bad("invalid_range", "Choose a range of up to 120 days.")
	}
	return from, to, nil
}

func limit(r *http.Request, fallback, highest int) (int, error) {
	text := r.URL.Query().Get("limit")
	if text == "" {
		return fallback, nil
	}
	n, err := strconv.Atoi(text)
	if err != nil || n < 1 || n > highest {
		return 0, bad("invalid_limit", "The limit must be between 1 and "+strconv.Itoa(highest)+".")
	}
	return n, nil
}

func (s *Server) listReadings(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	from, to, err := s.period(r)
	if err != nil {
		return err
	}
	n, err := limit(r, 500, 5000)
	if err != nil {
		return err
	}
	list, err := s.Store.Readings(r.Context(), p.ID, from, to, n)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

func (s *Server) listHours(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	from, to, err := s.period(r)
	if err != nil {
		return err
	}
	list, err := s.Store.Hours(r.Context(), p.ID, from, to)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

func (s *Server) listForecasts(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	n, err := limit(r, 24, 200)
	if err != nil {
		return err
	}
	list, err := s.Store.Forecasts(r.Context(), p.ID, n)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

// requestForecast replays a past moment of a demo pond. Live forecasts are only issued by the schedule.
func (s *Server) requestForecast(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	var in struct {
		IssueTime time.Time `json:"issue_time"`
		Hours     int       `json:"hours"`
	}
	if err := read(w, r, &in); err != nil {
		return err
	}
	if p.Mode != "demo" {
		return bad("live_pond", "Forecasts for live ponds are issued automatically.")
	}
	if in.Hours == 0 {
		in.Hours = 1
	}
	if in.Hours < 1 || in.Hours > 72 {
		return bad("invalid_hours", "Request 1 to 72 forecasts.")
	}
	issue := readings.HourStart(in.IssueTime, p.Zone())
	if in.IssueTime.IsZero() || !issue.Equal(in.IssueTime) {
		return bad("invalid_time", "The issue time must be a whole local hour.")
	}
	queued := 0
	for k := range in.Hours {
		added, err := s.Store.Enqueue(r.Context(), p.ID, issue.Add(time.Duration(k)*time.Hour))
		if err != nil {
			return err
		}
		if added {
			queued++
		}
	}
	return write(w, http.StatusAccepted, map[string]int{"queued": queued, "already_requested": in.Hours - queued})
}

func (s *Server) accuracy(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	list, err := s.Store.Accuracy(r.Context(), p.ID)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

func (s *Server) pondAlerts(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	n, err := limit(r, 50, 200)
	if err != nil {
		return err
	}
	list, err := s.Store.Alerts(r.Context(), p.ID, r.URL.Query().Get("open") == "true", n)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

func (s *Server) openAlerts(w http.ResponseWriter, r *http.Request, u store.User) error {
	list, err := s.Store.OpenAlerts(r.Context(), u.ID)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, list)
}

func (s *Server) acknowledge(w http.ResponseWriter, r *http.Request, u store.User) error {
	id, err := pathID(r)
	if err != nil {
		return err
	}
	a, err := s.Store.Acknowledge(r.Context(), u.ID, id)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, a)
}
