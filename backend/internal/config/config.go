// Package config reads settings from the environment and an optional .env file.
package config

import (
	"bufio"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	DatabaseURL   string
	Address       string
	ModelURL      string
	ModelToken    string
	Origins       []string
	SecureCookies bool
	Registration  bool
	TrustProxy    bool
}

// Load reads settings. Real environment variables win over the file.
func Load(file string) (Config, error) {
	values, err := readFile(file)
	if err != nil {
		return Config{}, err
	}
	get := func(key, fallback string) string {
		if v := os.Getenv(key); v != "" {
			return v
		}
		if v := values[key]; v != "" {
			return v
		}
		return fallback
	}
	c := Config{
		Address:    get("ADDRESS", "127.0.0.1:8090"),
		ModelURL:   strings.TrimRight(get("MODEL_URL", "http://127.0.0.1:8100"), "/"),
		ModelToken: get("MODEL_TOKEN", ""),
	}
	for _, o := range strings.Split(get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"), ",") {
		if o = strings.TrimRight(strings.TrimSpace(o), "/"); o != "" {
			c.Origins = append(c.Origins, o)
		}
	}
	for key, target := range map[string]*bool{"SECURE_COOKIES": &c.SecureCookies, "REGISTRATION": &c.Registration, "TRUST_PROXY": &c.TrustProxy} {
		fallback := "false"
		if key == "REGISTRATION" {
			fallback = "true"
		}
		if *target, err = strconv.ParseBool(get(key, fallback)); err != nil {
			return Config{}, fmt.Errorf("%s must be true or false", key)
		}
	}
	c.DatabaseURL, err = NormalizeURL(get("DATABASE_URL", ""))
	return c, err
}

// NormalizeURL accepts plain PostgreSQL URLs and the form used by the old Python backend.
// Errors never include the URL because it holds a password.
func NormalizeURL(raw string) (string, error) {
	if raw == "" {
		return "", errors.New("DATABASE_URL is required")
	}
	raw = strings.Replace(raw, "postgresql+asyncpg://", "postgresql://", 1)
	u, err := url.Parse(raw)
	if err != nil || (u.Scheme != "postgresql" && u.Scheme != "postgres") || u.Host == "" {
		return "", errors.New("DATABASE_URL is not a valid PostgreSQL URL")
	}
	q := u.Query()
	if mode := q.Get("ssl"); mode != "" {
		q.Del("ssl")
		if q.Get("sslmode") == "" {
			q.Set("sslmode", mode)
		}
	}
	u.RawQuery = q.Encode()
	return u.String(), nil
}

func readFile(path string) (map[string]string, error) {
	values := map[string]string{}
	f, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) || path == "" {
		return values, nil
	}
	if err != nil {
		return nil, err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if key, value, ok := strings.Cut(line, "="); ok {
			values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(value), `"'`)
		}
	}
	return values, scanner.Err()
}
