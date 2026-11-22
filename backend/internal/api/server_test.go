package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	embedded "github.com/fergusstrange/embedded-postgres"
	"github.com/jackc/pgx/v5"

	"aquatech/internal/auth"
	"aquatech/internal/config"
	"aquatech/internal/model"
	"aquatech/internal/store"
	"aquatech/internal/worker"
)

var adminURL string

// TestMain starts a private PostgreSQL. It never reads the application's settings.
func TestMain(m *testing.M) {
	dir, err := os.MkdirTemp("", "aquatech-pg")
	if err != nil {
		panic(err)
	}
	const port = 54329
	pg := embedded.NewDatabase(embedded.DefaultConfig().Port(port).Version(embedded.V17).RuntimePath(dir + "/run").DataPath(dir + "/data").Logger(io.Discard))
	if err := pg.Start(); err != nil {
		panic(err)
	}
	adminURL = fmt.Sprintf("postgresql://postgres:postgres@127.0.0.1:%d/postgres?sslmode=disable", port)
	code := m.Run()
	pg.Stop()
	os.RemoveAll(dir)
	os.Exit(code)
}

type fakeModel struct {
	mu    sync.Mutex
	err   error
	last  model.Request
	calls int
}

func (f *fakeModel) Forecast(_ context.Context, r model.Request) (*model.Forecast, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.last, f.calls = r, f.calls+1
	if f.err != nil {
		return nil, f.err
	}
	out := &model.Forecast{ModelID: "fake", Manifest: "m", IssueTime: r.IssueTime}
	for _, h := range []int{1, 3, 6, 12} {
		end := r.IssueTime.Add(time.Duration(h) * time.Hour)
		v := model.Value{Horizon: h, TargetStart: end.Add(-time.Hour), TargetEnd: end, LowOxygen: &model.LowOxygen{Threshold: 3, Probability: 0.8}, Withheld: []string{}}
		if h < 12 {
			point := 4.0
			v.Point = &point
		} else {
			v.Withheld = []string{"point", "interval"}
		}
		if h == 1 {
			v.Interval = &model.Interval{Low: 3, High: 5}
		}
		out.Forecasts = append(out.Forecasts, v)
	}
	return out, nil
}

type env struct {
	t      *testing.T
	store  *store.Store
	server *httptest.Server
	worker *worker.Worker
	model  *fakeModel
	now    time.Time
	client *http.Client
}

// setup gives each test its own database.
func setup(t *testing.T) *env {
	t.Helper()
	ctx := context.Background()
	name := fmt.Sprintf("t%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, adminURL)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		t.Fatal(err)
	}
	admin.Close(ctx)
	db, err := store.Open(ctx, strings.Replace(adminURL, "/postgres?", "/"+name+"?", 1))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(db.Close)
	if _, err := db.Migrate(ctx); err != nil {
		t.Fatal(err)
	}
	e := &env{t: t, store: db, model: &fakeModel{}, now: time.Date(2026, 1, 24, 12, 35, 0, 0, time.UTC)}
	clock := func() time.Time { return e.now }
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	e.worker = &worker.Worker{Store: db, Model: e.model, Log: log, Now: clock}
	s := &Server{Config: config.Config{Origins: []string{"http://localhost:5173"}, Registration: true}, Store: db,
		Model: model.New("http://127.0.0.1:1", ""), Log: log, Now: clock}
	e.server = httptest.NewServer(s.Handler())
	t.Cleanup(e.server.Close)
	e.client = e.visitor()
	return e
}

func (e *env) visitor() *http.Client {
	jar, _ := cookiejar.New(nil)
	return &http.Client{Jar: jar}
}

type call struct {
	method, path, body, kind string
	headers                  map[string]string
	client                   *http.Client
}

func (e *env) send(c call, want int) map[string]any {
	e.t.Helper()
	req, _ := http.NewRequest(c.method, e.server.URL+"/api/v1"+c.path, strings.NewReader(c.body))
	if c.kind == "" {
		c.kind = "application/json"
	}
	req.Header.Set("Content-Type", c.kind)
	for k, v := range c.headers {
		req.Header.Set(k, v)
	}
	if c.client == nil {
		c.client = e.client
	}
	res, err := c.client.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	defer res.Body.Close()
	data, _ := io.ReadAll(res.Body)
	if res.StatusCode != want {
		e.t.Fatalf("%s %s: status %d, want %d: %s", c.method, c.path, res.StatusCode, want, data)
	}
	var out any
	json.Unmarshal(data, &out)
	if m, ok := out.(map[string]any); ok {
		return m
	}
	return map[string]any{"list": out}
}

func (e *env) get(path string) map[string]any { return e.send(call{method: "GET", path: path}, 200) }
func (e *env) post(path, body string, want int) map[string]any {
	e.t.Helper()
	return e.send(call{method: "POST", path: path, body: body}, want)
}

func (e *env) signUp(email string, c *http.Client) {
	e.t.Helper()
	e.send(call{method: "POST", path: "/auth/register", body: fmt.Sprintf(`{"name":"Asha","email":%q,"password":"long enough password"}`, email), client: c}, 201)
}

func (e *env) pond(mode string) string {
	e.t.Helper()
	out := e.post("/ponds", fmt.Sprintf(`{"name":"North","species":"rohu_catla","timezone":"Asia/Kolkata","mode":%q,"sampling_minutes":15,"do_low":4,"do_critical":3}`, mode), 201)
	return out["id"].(string)
}

// csv makes quarter-hour readings that end at a time.
func csv(end time.Time, hours int, do float64) string {
	var b bytes.Buffer
	b.WriteString("timestamp,do_mgl,ph,temperature_c\n")
	for k := hours * 4; k > 0; k-- {
		fmt.Fprintf(&b, "%s,%g,8.1,25\n", end.Add(-time.Duration(k)*15*time.Minute).Format(time.RFC3339), do)
	}
	return b.String()
}

func (e *env) runJobs() {
	e.t.Helper()
	for {
		more, err := e.worker.RunOne(context.Background())
		if err != nil {
			e.t.Fatal(err)
		}
		if !more {
			return
		}
	}
}

func TestAccounts(t *testing.T) {
	e := setup(t)
	e.send(call{method: "GET", path: "/auth/me"}, 401)
	for _, body := range []string{`{"name":"A","email":"bad","password":"long enough password"}`, `{"name":"A","email":"a@b.co","password":"short"}`,
		`{"name":"","email":"a@b.co","password":"long enough password"}`, `{"admin":true}`, `{} {}`, `[`} {
		e.post("/auth/register", body, 400)
	}
	e.signUp("asha@example.com", nil)
	if e.get("/auth/me")["email"] != "asha@example.com" {
		t.Fatal("registration should sign in")
	}
	e.send(call{method: "POST", path: "/auth/register", body: `{"name":"B","email":"ASHA@example.com","password":"long enough password"}`, client: e.visitor()}, 409)
	e.post("/auth/logout", "{}", 200)
	e.send(call{method: "GET", path: "/auth/me"}, 401)
	e.post("/auth/login", `{"email":"asha@example.com","password":"wrong password!"}`, 401)
	e.post("/auth/login", `{"email":"nobody@example.com","password":"wrong password!"}`, 401)
	e.post("/auth/login", `{"email":"Asha@Example.com","password":"long enough password"}`, 200)
	e.get("/auth/me")
	for range 7 {
		e.post("/auth/login", `{"email":"asha@example.com","password":"wrong password!"}`, 401)
	}
	e.post("/auth/login", `{"email":"asha@example.com","password":"long enough password"}`, 429)
}

func TestOrigins(t *testing.T) {
	e := setup(t)
	body := `{"email":"a@b.co","password":"x"}`
	e.send(call{method: "POST", path: "/auth/login", body: body, headers: map[string]string{"Origin": "https://evil.example"}}, 403)
	e.send(call{method: "POST", path: "/auth/login", body: body, headers: map[string]string{"Origin": "null"}}, 403)
	e.send(call{method: "POST", path: "/auth/login", body: body, headers: map[string]string{"Origin": "http://localhost:5173"}}, 401)
	e.send(call{method: "POST", path: "/auth/login", body: body, kind: "text/plain"}, 415)
}

func TestOtherUsersSeeNothing(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	id := e.pond("live")
	device := e.post("/ponds/"+id+"/devices", `{"name":"probe"}`, 201)["device"].(map[string]any)["id"].(string)
	key := e.post("/ponds/"+id+"/devices", `{"name":"second"}`, 201)["key"].(string)
	e.send(call{method: "POST", path: "/ingest", body: fmt.Sprintf(`{"readings":[{"observed_at":%q,"do_mgL":2}]}`, e.now.Format(time.RFC3339)),
		headers: map[string]string{"Authorization": "Device " + key}}, 200)
	alert := e.get("/alerts")["list"].([]any)[0].(map[string]any)["id"].(string)
	other := e.visitor()
	e.signUp("b@example.com", other)
	for _, c := range []call{{method: "GET", path: "/ponds/" + id}, {method: "PATCH", path: "/ponds/" + id, body: "{}"}, {method: "DELETE", path: "/ponds/" + id},
		{method: "GET", path: "/ponds/" + id + "/overview"}, {method: "GET", path: "/ponds/" + id + "/readings"}, {method: "GET", path: "/ponds/" + id + "/hours"},
		{method: "GET", path: "/ponds/" + id + "/forecasts"}, {method: "POST", path: "/ponds/" + id + "/forecasts", body: "{}"},
		{method: "GET", path: "/ponds/" + id + "/accuracy"}, {method: "GET", path: "/ponds/" + id + "/alerts"}, {method: "GET", path: "/ponds/" + id + "/devices"},
		{method: "POST", path: "/ponds/" + id + "/devices", body: `{"name":"x"}`}, {method: "POST", path: "/ponds/" + id + "/imports", body: "timestamp,do_mgl\n", kind: "text/csv"},
		{method: "DELETE", path: "/devices/" + device}, {method: "POST", path: "/alerts/" + alert + "/acknowledge", body: "{}"}, {method: "GET", path: "/ponds/nonsense"}} {
		c.client = other
		e.send(c, 404)
	}
	if list := e.send(call{method: "GET", path: "/summary", client: other}, 200)["ponds"].([]any); len(list) != 0 {
		t.Fatalf("summary leaked %v", list)
	}
	e.send(call{method: "GET", path: "/ponds/" + id, client: e.visitor()}, 401)
	for _, path := range []string{"/ponds", "/alerts"} {
		if list := e.send(call{method: "GET", path: path, client: other}, 200)["list"].([]any); len(list) != 0 {
			t.Fatalf("%s leaked %v", path, list)
		}
	}
	e.get("/ponds/" + id)
}

func TestPondValidation(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	e.pond("live")
	if s := e.get("/summary")["ponds"].([]any)[0].(map[string]any); s["latest_at"] != nil || s["trend_do_mgL"] != nil || s["open_alerts"] != 0.0 {
		t.Fatal("an empty pond must have an empty summary", s)
	}
	base := map[string]any{"name": "P", "species": "rohu_catla", "timezone": "Asia/Kolkata", "mode": "live", "sampling_minutes": 15}
	for field, value := range map[string]any{"name": " ", "species": "whale", "timezone": "Mars/Base", "mode": "test", "sampling_minutes": 0,
		"do_low": 99, "do_critical": 3, "alert_probability": 1.5} {
		in := map[string]any{}
		for k, v := range base {
			in[k] = v
		}
		in[field] = value
		body, _ := json.Marshal(in)
		e.post("/ponds", string(body), 400)
	}
	id := e.pond("live")
	e.send(call{method: "PATCH", path: "/ponds/" + id, body: `{"name":"New","species":"vannamei","do_low":4,"ph_low":8,"ph_high":7}`}, 400)
	e.send(call{method: "PATCH", path: "/ponds/" + id, body: `{"name":"New","species":"vannamei","timezone":"UTC"}`}, 400)
	out := e.send(call{method: "PATCH", path: "/ponds/" + id, body: `{"name":"New","species":"vannamei","do_low":4}`}, 200)
	if out["name"] != "New" || out["do_critical"] != nil {
		t.Fatal(out)
	}
}

func TestDeviceIngestIsIdempotent(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	id := e.pond("live")
	created := e.post("/ponds/"+id+"/devices", `{"name":"probe"}`, 201)
	key, device := created["key"].(string), created["device"].(map[string]any)["id"].(string)
	at := e.now.Add(-5 * time.Minute)
	send := func(body string, want int) map[string]any {
		return e.send(call{method: "POST", path: "/ingest", body: body, headers: map[string]string{"Authorization": "Device " + key}, client: e.visitor()}, want)
	}
	body := fmt.Sprintf(`{"readings":[{"observed_at":%q,"do_mgL":2.5,"ph":8,"temperature_c":25},{"observed_at":%q,"do_mgL":5}]}`,
		at.Format(time.RFC3339), e.now.Add(time.Hour).Format(time.RFC3339))
	out := send(body, 200)
	if out["stored"] != 1.0 || out["rejected"] != 1.0 {
		t.Fatal(out)
	}
	if out = send(body, 200); out["stored"] != 0.0 || out["duplicate"] != 1.0 {
		t.Fatal(out)
	}
	out = send(strings.Replace(body, "2.5", "7.5", 1), 200)
	if out["conflict"] != 1.0 {
		t.Fatal(out)
	}
	if e.get("/ponds/" + id + "/overview")["latest"].(map[string]any)["do_mgL"] != 2.5 {
		t.Fatal("the first value must be kept")
	}
	alerts := e.get("/ponds/" + id + "/alerts")["list"].([]any)
	if len(alerts) != 1 || alerts[0].(map[string]any)["severity"] != "critical" {
		t.Fatal(alerts)
	}
	send(`{"readings":[]}`, 400)
	e.send(call{method: "POST", path: "/ingest", body: body, headers: map[string]string{"Authorization": "Device wrong"}}, 401)
	e.send(call{method: "DELETE", path: "/devices/" + device}, 200)
	send(body, 401)
}

func TestAlertLifecycle(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	id := e.pond("live")
	key := e.post("/ponds/"+id+"/devices", `{"name":"probe"}`, 201)["key"].(string)
	send := func(do float64) {
		e.now = e.now.Add(time.Minute)
		e.send(call{method: "POST", path: "/ingest", body: fmt.Sprintf(`{"readings":[{"observed_at":%q,"do_mgL":%g}]}`, e.now.Format(time.RFC3339), do),
			headers: map[string]string{"Authorization": "Device " + key}}, 200)
	}
	open := func() []any { return e.get("/ponds/" + id + "/alerts?open=true")["list"].([]any) }
	send(3.5)
	first := open()[0].(map[string]any)
	e.post("/alerts/"+first["id"].(string)+"/acknowledge", "{}", 200)
	send(3.4)
	if a := open()[0].(map[string]any); a["id"] != first["id"] || a["acknowledged_at"] == nil {
		t.Fatal("a continuing alert keeps its identity and acknowledgement")
	}
	send(2)
	if a := open()[0].(map[string]any); a["severity"] != "critical" || a["acknowledged_at"] != nil {
		t.Fatal("an escalation must need attention again")
	}
	e.now = e.now.Add(3 * time.Hour)
	if err := e.worker.Schedule(context.Background()); err != nil {
		t.Fatal(err)
	}
	if n := len(open()); n != 2 {
		t.Fatalf("stale data must not clear low oxygen, open alerts: %d", n)
	}
	send(6)
	if n := len(open()); n != 0 {
		t.Fatalf("open alerts after recovery: %d", n)
	}
}

func TestImportPreviewAndHours(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	id := e.pond("demo")
	end := time.Date(2026, 1, 20, 0, 30, 0, 0, time.UTC)
	body := csv(end, 2, 6)
	send := func(query string) map[string]any {
		return e.send(call{method: "POST", path: "/ponds/" + id + "/imports" + query, body: body, kind: "text/csv"}, 200)
	}
	if out := send(""); out["committed"] != false || out["valid"] != 8.0 {
		t.Fatal(out)
	}
	window := "?from=2026-01-19T00:00:00Z&to=2026-01-21T00:00:00Z"
	if n := len(e.get("/ponds/" + id + "/readings" + window)["list"].([]any)); n != 0 {
		t.Fatal("a preview stored readings")
	}
	if out := send("?commit=true"); out["stored"] != 8.0 {
		t.Fatal(out)
	}
	if out := send("?commit=true"); out["stored"] != 0.0 || out["duplicate"] != 8.0 {
		t.Fatal(out)
	}
	hours := e.get("/ponds/" + id + "/hours" + window)["list"].([]any)
	if len(hours) != 2 {
		t.Fatal(hours)
	}
	h := hours[1].(map[string]any)
	if h["start"] != "2026-01-19T23:30:00Z" || h["coverage"] != 1.0 || h["do_mgL"] != 6.0 || h["ph"] != 8.1 {
		t.Fatal(h)
	}
	body = "timestamp,do_mgl,ph,temperature_c\n2026-01-20T00:30:00Z,0,0,25\n2026-01-20T00:45:00Z,5,8,25\n2026-01-20T01:00:00Z,7,8,25\n2026-01-20T01:15:00Z,6,,25\n"
	send("?commit=true")
	h = e.get("/ponds/" + id + "/hours" + window)["list"].([]any)[2].(map[string]any)
	if h["coverage"] != 0.75 || h["do_mgL"] != 6.0 || h["zero_readings"] != 1.0 || h["ph"] != nil || h["temperature_c"] != 25.0 {
		t.Fatal("zeros and thin channels must be left out of hourly means", h)
	}
	e.send(call{method: "POST", path: "/ponds/" + id + "/imports", body: "x\n", kind: "text/csv"}, 400)
	e.send(call{method: "POST", path: "/ponds/" + id + "/devices", body: `{"name":"x"}`}, 400)
}

func TestDemoForecasts(t *testing.T) {
	e := setup(t)
	e.signUp("a@example.com", nil)
	id := e.pond("demo")
	issue := time.Date(2026, 1, 20, 0, 30, 0, 0, time.UTC)
	e.send(call{method: "POST", path: "/ponds/" + id + "/imports?commit=true", body: csv(issue.Add(13*time.Hour), 40, 5), kind: "text/csv"}, 200)
	e.post("/ponds/"+id+"/forecasts", `{"issue_time":"2026-01-20T00:00:00Z"}`, 400)
	request := fmt.Sprintf(`{"issue_time":%q}`, issue.Format(time.RFC3339))
	if out := e.post("/ponds/"+id+"/forecasts", request, 202); out["queued"] != 1.0 {
		t.Fatal(out)
	}
	if out := e.post("/ponds/"+id+"/forecasts", request, 202); out["already_requested"] != 1.0 {
		t.Fatal(out)
	}
	e.runJobs()
	if h := e.model.last.History; len(h) != 24 || !h[23].Start.Equal(issue.Add(-time.Hour)) || e.model.last.Timezone != "Asia/Kolkata" {
		t.Fatalf("history must end at the issue time: %d hours", len(h))
	}
	list := e.get("/ponds/" + id + "/forecasts")["list"].([]any)
	values := list[0].(map[string]any)["values"].([]any)
	last := values[3].(map[string]any)
	if len(values) != 4 || last["point_mgL"] != nil || last["probability"] != 0.8 || len(last["withheld"].([]any)) != 2 {
		t.Fatal(values)
	}
	s := e.get("/summary")["ponds"].([]any)[0].(map[string]any)
	if trend := s["trend_do_mgL"].([]any); len(trend) != 24 || trend[23] != 5.0 || s["highest_probability"] != 0.8 || s["open_alerts"] != 1.0 || s["name"] != "North" {
		t.Fatal(s)
	}
	accuracy := e.get("/ponds/" + id + "/accuracy")["list"].([]any)
	first := accuracy[0].(map[string]any)
	if len(accuracy) != 4 || first["mae_mgL"] != 1.0 || first["persistence_mae_mgL"] != 0.0 || first["interval_coverage"] != 1.0 ||
		accuracy[3].(map[string]any)["points"] != 0.0 {
		t.Fatal(accuracy)
	}
	if a := e.get("/ponds/" + id + "/alerts")["list"].([]any); len(a) != 1 || a[0].(map[string]any)["origin"] != "forecast" {
		t.Fatal(a)
	}
}

func TestLiveSchedule(t *testing.T) {
	e := setup(t)
	ctx := context.Background()
	e.signUp("a@example.com", nil)
	id := e.pond("live")
	e.post("/ponds/"+id+"/forecasts", `{"issue_time":"2026-01-24T12:30:00Z"}`, 400)
	issue := time.Date(2026, 1, 24, 12, 30, 0, 0, time.UTC) // 18:00 in India
	e.send(call{method: "POST", path: "/ponds/" + id + "/imports?commit=true", body: csv(issue, 24, 5), kind: "text/csv"}, 200)
	schedule := func() {
		t.Helper()
		if err := e.worker.Schedule(ctx); err != nil {
			t.Fatal(err)
		}
	}
	e.now = issue.Add(time.Minute)
	schedule()
	e.runJobs()
	if e.model.calls != 0 {
		t.Fatal("forecast issued before readings could settle")
	}
	e.now = issue.Add(4 * time.Minute)
	schedule()
	schedule()
	e.runJobs()
	if e.model.calls != 1 {
		t.Fatalf("calls %d", e.model.calls)
	}
	// A job that is too late must not produce a live forecast.
	e.store.Enqueue(ctx, id, issue.Add(-3*time.Hour))
	e.runJobs()
	list := e.get("/ponds/" + id + "/forecasts")["list"].([]any)
	if late := list[1].(map[string]any); e.model.calls != 1 || late["status"] != "unavailable" || late["reasons"].([]any)[0] != "issue_window_passed" {
		t.Fatal(list)
	}
	// Old data stops the schedule.
	e.now = issue.Add(5*time.Hour + 10*time.Minute)
	schedule()
	e.runJobs()
	if e.model.calls != 1 {
		t.Fatal("forecast issued from stale readings")
	}
}

func TestModelFailures(t *testing.T) {
	e := setup(t)
	ctx := context.Background()
	e.signUp("a@example.com", nil)
	id := e.pond("demo")
	issue := time.Date(2026, 1, 20, 0, 30, 0, 0, time.UTC)
	e.store.Enqueue(ctx, id, issue)
	e.runJobs()
	if e.model.calls != 0 {
		t.Fatal("a pond without history must not reach the model")
	}
	e.send(call{method: "POST", path: "/ponds/" + id + "/imports?commit=true", body: csv(issue.Add(2*time.Hour), 30, 5), kind: "text/csv"}, 200)
	e.model.err = &model.Unavailable{Code: "history_unavailable", Reasons: []string{"recent_do_gap"}}
	e.store.Enqueue(ctx, id, issue.Add(time.Hour))
	e.runJobs()
	f := e.get("/ponds/" + id + "/forecasts")["list"].([]any)[0].(map[string]any)
	if f["status"] != "unavailable" || f["reasons"].([]any)[0] != "recent_do_gap" || len(f["values"].([]any)) != 0 {
		t.Fatal(f)
	}
	e.model.err = errors.New("connection refused")
	e.store.Enqueue(ctx, id, issue.Add(2*time.Hour))
	if _, err := e.worker.RunOne(ctx); err != nil {
		t.Fatal(err)
	}
	if n := len(e.get("/ponds/" + id + "/forecasts")["list"].([]any)); n != 2 {
		t.Fatal("a temporary failure must not be recorded as a result")
	}
	if _, err := e.store.Claim(ctx, time.Minute); !errors.Is(err, store.ErrNotFound) {
		t.Fatal("a retried job must wait")
	}
	if e.get("/health")["status"] != "ok" || e.get("/model")["available"] != false {
		t.Fatal("monitoring must continue without the model")
	}
}

func TestExpiredLeaseCannotOverwrite(t *testing.T) {
	e := setup(t)
	ctx := context.Background()
	e.signUp("a@example.com", nil)
	id := e.pond("demo")
	e.store.Enqueue(ctx, id, e.now.Truncate(time.Hour))
	old, err := e.store.Claim(ctx, -time.Second)
	if err != nil {
		t.Fatal(err)
	}
	current, err := e.store.Claim(ctx, time.Minute)
	if err != nil || current.ID != old.ID {
		t.Fatal("an expired job must be claimable", err)
	}
	if err := e.store.Finish(ctx, old, nil, []string{"old"}, false); err != nil {
		t.Fatal(err)
	}
	if n := len(e.get("/ponds/" + id + "/forecasts")["list"].([]any)); n != 0 {
		t.Fatal("an expired worker wrote a result")
	}
	if err := e.store.Finish(ctx, current, nil, []string{"new"}, false); err != nil {
		t.Fatal(err)
	}
}

func TestMigrationRefusesForeignTables(t *testing.T) {
	ctx := context.Background()
	name := fmt.Sprintf("f%d", time.Now().UnixNano())
	admin, _ := pgx.Connect(ctx, adminURL)
	admin.Exec(ctx, "CREATE DATABASE "+name)
	admin.Close(ctx)
	url := strings.Replace(adminURL, "/postgres?", "/"+name+"?", 1)
	conn, _ := pgx.Connect(ctx, url)
	conn.Exec(ctx, "CREATE TABLE users (id int)")
	conn.Close(ctx)
	db, err := store.Open(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if _, err := db.Migrate(ctx); err == nil || !strings.Contains(err.Error(), "another application") {
		t.Fatal(err)
	}
	if db.CheckSchema(ctx) == nil {
		t.Fatal("an unmigrated database must not pass")
	}
}

func TestPasswordsAndConfig(t *testing.T) {
	hash := auth.HashPassword("correct horse")
	if ok, err := auth.CheckPassword(hash, "correct horse"); !ok || err != nil {
		t.Fatal(ok, err)
	}
	if ok, _ := auth.CheckPassword(hash, "wrong horse"); ok {
		t.Fatal("accepted a wrong password")
	}
	if _, err := auth.CheckPassword("plain", "x"); err == nil {
		t.Fatal("accepted an invalid hash")
	}
	got, err := config.NormalizeURL("postgresql+asyncpg://u:p@h/db?ssl=require")
	if err != nil || got != "postgresql://u:p@h/db?sslmode=require" {
		t.Fatal(got, err)
	}
	if _, err := config.NormalizeURL("mysql://u:secret@h/db"); err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatal(err)
	}
}
