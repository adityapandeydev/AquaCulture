package api

import (
	"errors"
	"net/http"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"aquatech/internal/auth"
	"aquatech/internal/store"
)

type suggestion struct {
	DOLow    *float64 `json:"do_low"`
	PHLow    *float64 `json:"ph_low"`
	PHHigh   *float64 `json:"ph_high"`
	Source   string   `json:"source"`
	Strength string   `json:"strength"`
}

type speciesInfo struct {
	ID        string      `json:"id"`
	Name      string      `json:"name"`
	Forecasts bool        `json:"forecasts"`
	Suggested *suggestion `json:"suggested_thresholds"`
}

func number(v float64) *float64 { return &v }

// speciesList holds suggestions an operator can change. They are never applied silently.
var speciesList = []speciesInfo{
	{"rohu_catla", "Rohu and Catla", true, &suggestion{number(3), number(6.5), number(8.5),
		"Fish Welfare Initiative, ARA Commitment required ranges (morning oxygen)", "published programme range"}},
	{"vannamei", "Whiteleg shrimp", false, &suggestion{number(4), number(7.5), number(8.5),
		"Intensive culture values cited in secondary literature", "secondary source, review before use"}},
	{"other_fish", "Other fish", false, nil},
	{"other_shrimp", "Other shrimp", false, nil},
}

func (s *Server) species(w http.ResponseWriter, r *http.Request) error {
	return write(w, http.StatusOK, speciesList)
}

type pondInput struct {
	Name             string   `json:"name"`
	Species          string   `json:"species"`
	Timezone         string   `json:"timezone"`
	Mode             string   `json:"mode"`
	SamplingMinutes  int      `json:"sampling_minutes"`
	DOLow            *float64 `json:"do_low"`
	DOCritical       *float64 `json:"do_critical"`
	PHLow            *float64 `json:"ph_low"`
	PHHigh           *float64 `json:"ph_high"`
	TemperatureLow   *float64 `json:"temperature_low"`
	TemperatureHigh  *float64 `json:"temperature_high"`
	AlertProbability *float64 `json:"alert_probability"`
}

// apply checks the editable fields and copies them to a pond.
func (in pondInput) apply(p *store.Pond) error {
	p.Name = strings.TrimSpace(in.Name)
	if n := utf8.RuneCountInString(p.Name); n < 1 || n > 80 {
		return bad("invalid_name", "Enter a pond name of at most 80 characters.")
	}
	known := false
	for _, item := range speciesList {
		known = known || item.ID == in.Species
	}
	if !known {
		return bad("invalid_species", "Choose a species from the list.")
	}
	p.Species = in.Species
	within := func(low, high float64, values ...*float64) bool {
		for _, v := range values {
			if v != nil && !(*v >= low && *v <= high) {
				return false
			}
		}
		return true
	}
	if !within(0.1, 20, in.DOLow, in.DOCritical) || !within(0, 14, in.PHLow, in.PHHigh) || !within(-5, 50, in.TemperatureLow, in.TemperatureHigh) {
		return bad("invalid_threshold", "A threshold is outside the possible range.")
	}
	if in.DOCritical != nil && (in.DOLow == nil || *in.DOCritical > *in.DOLow) {
		return bad("invalid_threshold", "The critical oxygen level must not be above the low level.")
	}
	for _, pair := range [][2]*float64{{in.PHLow, in.PHHigh}, {in.TemperatureLow, in.TemperatureHigh}} {
		if pair[0] != nil && pair[1] != nil && *pair[0] >= *pair[1] {
			return bad("invalid_threshold", "A lower limit must be below its upper limit.")
		}
	}
	p.DOLow, p.DOCritical, p.PHLow, p.PHHigh = in.DOLow, in.DOCritical, in.PHLow, in.PHHigh
	p.TemperatureLow, p.TemperatureHigh = in.TemperatureLow, in.TemperatureHigh
	if in.AlertProbability != nil {
		if !within(0.05, 0.95, in.AlertProbability) {
			return bad("invalid_probability", "The alert probability must be between 0.05 and 0.95.")
		}
		p.AlertProbability = *in.AlertProbability
	}
	return nil
}

func (s *Server) createPond(w http.ResponseWriter, r *http.Request, u store.User) error {
	var in pondInput
	if err := read(w, r, &in); err != nil {
		return err
	}
	p := store.Pond{OwnerID: u.ID, Timezone: in.Timezone, Mode: in.Mode, SamplingMinutes: in.SamplingMinutes, AlertProbability: 0.5}
	if err := in.apply(&p); err != nil {
		return err
	}
	if _, err := time.LoadLocation(in.Timezone); err != nil || in.Timezone == "" || in.Timezone == "Local" {
		return bad("invalid_timezone", "Choose a valid timezone.")
	}
	if in.Mode != "live" && in.Mode != "demo" {
		return bad("invalid_mode", "Choose live or demo.")
	}
	if in.SamplingMinutes < 1 || in.SamplingMinutes > 30 {
		return bad("invalid_sampling", "Readings must be 1 to 30 minutes apart.")
	}
	p, err := s.Store.CreatePond(r.Context(), p)
	if err != nil {
		return err
	}
	return write(w, http.StatusCreated, p)
}

func (s *Server) listPonds(w http.ResponseWriter, r *http.Request, u store.User) error {
	ponds, err := s.Store.OwnedPonds(r.Context(), u.ID)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, ponds)
}

func (s *Server) getPond(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	return write(w, http.StatusOK, p)
}

func (s *Server) updatePond(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	var in pondInput
	if err := read(w, r, &in); err != nil {
		return err
	}
	if in.Timezone != "" && in.Timezone != p.Timezone || in.Mode != "" && in.Mode != p.Mode ||
		in.SamplingMinutes != 0 && in.SamplingMinutes != p.SamplingMinutes {
		return bad("fixed_field", "The timezone, mode and sampling interval cannot change.")
	}
	if err := in.apply(&p); err != nil {
		return err
	}
	p, err := s.Store.UpdatePond(r.Context(), p)
	if err != nil {
		return err
	}
	if err := s.assess(r, p); err != nil {
		return err
	}
	return write(w, http.StatusOK, p)
}

func (s *Server) deletePond(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	if err := s.Store.DeletePond(r.Context(), p.OwnerID, p.ID); err != nil {
		return err
	}
	return write(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (s *Server) summary(w http.ResponseWriter, r *http.Request, u store.User) error {
	list, err := s.Store.Summaries(r.Context(), u.ID)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, map[string]any{"now": s.Now().UTC(), "ponds": list})
}

// overview reads its parts at the same time, because the database may be far away.
func (s *Server) overview(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	var (
		extent    store.Extent
		latest    *store.Reading
		forecasts []store.Forecast
		alerts    []store.Alert
		work      sync.WaitGroup
		failures  [4]error
	)
	ctx := r.Context()
	work.Go(func() { extent, failures[0] = s.Store.Extent(ctx, p.ID) })
	work.Go(func() {
		reading, err := s.Store.LatestReading(ctx, p.ID)
		if err == nil {
			latest = &reading
		} else if !errors.Is(err, store.ErrNotFound) {
			failures[1] = err
		}
	})
	work.Go(func() { forecasts, failures[2] = s.Store.Forecasts(ctx, p.ID, 1) })
	work.Go(func() { alerts, failures[3] = s.Store.Alerts(ctx, p.ID, true, 50) })
	work.Wait()
	if err := errors.Join(failures[:]...); err != nil {
		return err
	}
	var forecast *store.Forecast
	if len(forecasts) == 1 {
		forecast = &forecasts[0]
	}
	return write(w, http.StatusOK, map[string]any{"pond": p, "now": s.Now().UTC(), "extent": extent, "latest": latest,
		"forecast": forecast, "alerts": alerts})
}

func (s *Server) listDevices(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	devices, err := s.Store.Devices(r.Context(), p.ID)
	if err != nil {
		return err
	}
	return write(w, http.StatusOK, devices)
}

// createDevice returns the key once. Only its hash is stored.
func (s *Server) createDevice(w http.ResponseWriter, r *http.Request, p store.Pond) error {
	var in struct{ Name string }
	if err := read(w, r, &in); err != nil {
		return err
	}
	name := strings.TrimSpace(in.Name)
	if n := utf8.RuneCountInString(name); n < 1 || n > 80 {
		return bad("invalid_name", "Enter a device name of at most 80 characters.")
	}
	if p.Mode != "live" {
		return bad("demo_pond", "Devices can only be added to live ponds.")
	}
	key, hash := auth.NewSecret("aqd_")
	d, err := s.Store.CreateDevice(r.Context(), p.ID, name, hash)
	if err != nil {
		return err
	}
	return write(w, http.StatusCreated, map[string]any{"device": d, "key": key})
}

func (s *Server) revokeDevice(w http.ResponseWriter, r *http.Request, u store.User) error {
	id, err := pathID(r)
	if err != nil {
		return err
	}
	if err := s.Store.RevokeDevice(r.Context(), u.ID, id); err != nil {
		return err
	}
	return write(w, http.StatusOK, map[string]string{"status": "revoked"})
}
