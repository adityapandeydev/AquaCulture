// Package auth handles passwords, random credentials and login limits.
package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/argon2"
)

const (
	argonTime    = 2
	argonMemory  = 19 * 1024
	argonThreads = 1
	argonLength  = 32
)

// hashing limits concurrent password work, which is deliberately expensive.
var hashing = make(chan struct{}, 4)

func derive(password string, salt []byte, time, memory uint32, threads uint8, length uint32) []byte {
	hashing <- struct{}{}
	defer func() { <-hashing }()
	return argon2.IDKey([]byte(password), salt, time, memory, threads, length)
}

// HashPassword returns an encoded Argon2id hash.
func HashPassword(password string) string {
	salt := make([]byte, 16)
	rand.Read(salt)
	key := derive(password, salt, argonTime, argonMemory, argonThreads, argonLength)
	enc := base64.RawStdEncoding.EncodeToString
	return fmt.Sprintf("$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s", argon2.Version, argonMemory, argonTime, argonThreads, enc(salt), enc(key))
}

var errHash = errors.New("stored password hash is not valid")

// CheckPassword compares a password with an encoded hash.
func CheckPassword(encoded, password string) (bool, error) {
	parts := strings.Split(encoded, "$")
	if len(parts) != 6 || parts[1] != "argon2id" {
		return false, errHash
	}
	var version int
	var memory, time uint32
	var threads uint8
	if _, err := fmt.Sscanf(parts[2], "v=%d", &version); err != nil || version != argon2.Version {
		return false, errHash
	}
	if _, err := fmt.Sscanf(parts[3], "m=%d,t=%d,p=%d", &memory, &time, &threads); err != nil || threads == 0 {
		return false, errHash
	}
	salt, err1 := base64.RawStdEncoding.DecodeString(parts[4])
	key, err2 := base64.RawStdEncoding.DecodeString(parts[5])
	if err1 != nil || err2 != nil || len(key) == 0 {
		return false, errHash
	}
	got := derive(password, salt, time, memory, threads, uint32(len(key)))
	return subtle.ConstantTimeCompare(got, key) == 1, nil
}

// decoy makes a login for an unknown email cost the same as a real one.
var decoy = sync.OnceValue(func() string { return HashPassword("unused") })

// CheckNothing spends the time of one password check.
func CheckNothing(password string) { CheckPassword(decoy(), password) }

// NewSecret returns a random credential and the hash to store.
func NewSecret(prefix string) (string, []byte) {
	raw := make([]byte, 32)
	rand.Read(raw)
	secret := prefix + base64.RawURLEncoding.EncodeToString(raw)
	return secret, HashSecret(secret)
}

// HashSecret hashes a high-entropy credential for lookup.
func HashSecret(secret string) []byte {
	sum := sha256.Sum256([]byte(secret))
	return sum[:]
}

// Limiter allows a number of attempts per key in a sliding window.
type Limiter struct {
	mu     sync.Mutex
	limit  int
	window time.Duration
	seen   map[string][]time.Time
}

func NewLimiter(limit int, window time.Duration) *Limiter {
	return &Limiter{limit: limit, window: window, seen: map[string][]time.Time{}}
}

// Allow records an attempt and reports whether it is permitted.
func (l *Limiter) Allow(key string, now time.Time) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if len(l.seen) > 10000 {
		for k, times := range l.seen {
			if now.Sub(times[len(times)-1]) > l.window {
				delete(l.seen, k)
			}
		}
	}
	recent := l.seen[key][:0]
	for _, t := range l.seen[key] {
		if now.Sub(t) < l.window {
			recent = append(recent, t)
		}
	}
	if len(recent) >= l.limit {
		l.seen[key] = recent
		return false
	}
	l.seen[key] = append(recent, now)
	return true
}
