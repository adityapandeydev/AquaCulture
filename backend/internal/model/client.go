// Package model calls the private Python forecast service.
package model

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Hour struct {
	Start       time.Time `json:"start"`
	Coverage    float64   `json:"coverage"`
	DO          *float64  `json:"do_mgL"`
	PH          *float64  `json:"ph"`
	Temperature *float64  `json:"temperature_c"`
}

type Request struct {
	Species   string    `json:"species"`
	Timezone  string    `json:"timezone"`
	IssueTime time.Time `json:"issue_time"`
	History   []Hour    `json:"history"`
}

type Interval struct {
	Low  float64 `json:"low_mgL"`
	High float64 `json:"high_mgL"`
}

type LowOxygen struct {
	Threshold   float64 `json:"threshold_mgL"`
	Probability float64 `json:"probability"`
}

type Value struct {
	Horizon     int        `json:"horizon_hours"`
	TargetStart time.Time  `json:"target_start"`
	TargetEnd   time.Time  `json:"target_end"`
	Point       *float64   `json:"point_mgL"`
	Interval    *Interval  `json:"interval_90"`
	LowOxygen   *LowOxygen `json:"low_oxygen"`
	Withheld    []string   `json:"withheld"`
}

type Forecast struct {
	ModelID   string    `json:"model_id"`
	Manifest  string    `json:"manifest_sha256"`
	IssueTime time.Time `json:"issue_time"`
	Forecasts []Value   `json:"forecasts"`
	Warnings  []string  `json:"warnings"`
}

// Unavailable is a definite answer that no forecast can be made from this request.
type Unavailable struct {
	Code    string
	Reasons []string
}

func (u *Unavailable) Error() string { return "forecast unavailable: " + u.Code }

type Client struct {
	base, token string
	http        *http.Client
}

func New(base, token string) *Client {
	return &Client{base, token, &http.Client{Timeout: 15 * time.Second}}
}

const maxResponse = 1 << 20

func (c *Client) do(ctx context.Context, method, path string, body io.Reader) (int, []byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.base+path, body)
	if err != nil {
		return 0, nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	res, err := c.http.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer res.Body.Close()
	data, err := io.ReadAll(io.LimitReader(res.Body, maxResponse))
	return res.StatusCode, data, err
}

// Forecast returns a forecast, *Unavailable for a definite refusal, or another error to retry.
func (c *Client) Forecast(ctx context.Context, r Request) (*Forecast, error) {
	payload, err := json.Marshal(r)
	if err != nil {
		return nil, err
	}
	status, data, err := c.do(ctx, http.MethodPost, "/v2/forecasts", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	if status == http.StatusOK {
		var f Forecast
		if err := json.Unmarshal(data, &f); err != nil {
			return nil, errors.New("the model service returned an unreadable forecast")
		}
		return &f, check(&f, r)
	}
	var e struct {
		Error struct {
			Code    string   `json:"code"`
			Reasons []string `json:"reasons"`
		} `json:"error"`
	}
	json.Unmarshal(data, &e)
	if status == http.StatusUnprocessableEntity || status == http.StatusBadRequest {
		return nil, &Unavailable{e.Error.Code, e.Error.Reasons}
	}
	return nil, fmt.Errorf("the model service answered %d %s", status, e.Error.Code)
}

// check refuses a response that does not match the request.
func check(f *Forecast, r Request) error {
	if f.ModelID == "" || f.Manifest == "" || len(f.Forecasts) == 0 || !f.IssueTime.Equal(r.IssueTime) {
		return errors.New("the model service returned an incomplete forecast")
	}
	for _, v := range f.Forecasts {
		end := r.IssueTime.Add(time.Duration(v.Horizon) * time.Hour)
		if v.Horizon < 1 || !v.TargetEnd.Equal(end) || !v.TargetStart.Equal(end.Add(-time.Hour)) {
			return errors.New("the model service returned inconsistent target times")
		}
		if v.LowOxygen != nil && (v.LowOxygen.Probability < 0 || v.LowOxygen.Probability > 1) {
			return errors.New("the model service returned an invalid probability")
		}
	}
	return nil
}

// Info returns the service's model description.
func (c *Client) Info(ctx context.Context) (json.RawMessage, error) {
	status, data, err := c.do(ctx, http.MethodGet, "/v2/model", nil)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK || !json.Valid(data) {
		return nil, fmt.Errorf("the model service answered %d", status)
	}
	return data, nil
}
