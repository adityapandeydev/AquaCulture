package api

import (
	"encoding/json"
	"math"
	"os"
	"strings"
	"testing"
	"time"

	"aquatech/internal/model"
)

// TestChain compares forecasts made from raw readings by the whole system with reference values.
// It runs only with a model service and a reference file. See backend/README.md.
func TestChain(t *testing.T) {
	url, path := os.Getenv("CHAIN_MODEL_URL"), os.Getenv("CHAIN_REFERENCE")
	if url == "" || path == "" {
		t.Skip("CHAIN_MODEL_URL and CHAIN_REFERENCE are not set")
	}
	var ref struct {
		CSV   string `json:"csv"`
		Cases []struct {
			Issue         time.Time `json:"issue"`
			Point         []float64 `json:"point"`
			Low, High     float64
			Probabilities []float64 `json:"probabilities"`
		} `json:"cases"`
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &ref); err != nil {
		t.Fatal(err)
	}
	e := setup(t)
	e.worker.Model = model.New(url, "")
	e.now = time.Now()
	e.signUp("a@example.com", nil)
	id := e.pond("demo")
	out := e.send(call{method: "POST", path: "/ponds/" + id + "/imports?commit=true", body: ref.CSV, kind: "text/csv"}, 200)
	t.Logf("import: %v", out)
	for _, c := range ref.Cases {
		body, _ := json.Marshal(map[string]any{"issue_time": c.Issue})
		e.post("/ponds/"+id+"/forecasts", string(body), 202)
	}
	e.runJobs()
	got := map[string]map[string]any{}
	for _, item := range e.get("/ponds/" + id + "/forecasts?limit=200")["list"].([]any) {
		f := item.(map[string]any)
		got[f["issue_time"].(string)] = f
	}
	worst, worstProbability := 0.0, 0.0
	for _, c := range ref.Cases {
		f := got[c.Issue.UTC().Format(time.RFC3339)]
		if f == nil || f["status"] != "ok" {
			t.Fatalf("%v: %v", c.Issue, f)
		}
		for j, item := range f["values"].([]any) {
			v := item.(map[string]any)
			if v["horizon_hours"].(float64) == 12 {
				if v["point_mgL"] != nil || !strings.Contains(strings.Join(strs(v["withheld"]), " "), "point") {
					t.Fatal("the withheld +12 h point forecast was shown")
				}
			} else {
				worst = math.Max(worst, math.Abs(v["point_mgL"].(float64)-c.Point[j]))
			}
			if j == 0 {
				worst = math.Max(worst, math.Max(math.Abs(v["low_mgL"].(float64)-c.Low), math.Abs(v["high_mgL"].(float64)-c.High)))
			}
			worstProbability = math.Max(worstProbability, math.Abs(v["probability"].(float64)-c.Probabilities[j]))
		}
	}
	t.Logf("%d forecasts, largest difference %.5f mg/L and %.5f in probability", len(ref.Cases), worst, worstProbability)
	if worst > 0.001 || worstProbability > 0.001 {
		t.Fatal("the system does not reproduce the reference forecasts")
	}
}

func strs(v any) []string {
	var out []string
	for _, item := range v.([]any) {
		out = append(out, item.(string))
	}
	return out
}
