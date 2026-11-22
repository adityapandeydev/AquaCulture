package api

import (
	"errors"
	"net/http"
	"net/mail"
	"strings"
	"time"
	"unicode/utf8"

	"aquatech/internal/auth"
	"aquatech/internal/store"
)

func (s *Server) register(w http.ResponseWriter, r *http.Request) error {
	if !s.Config.Registration {
		return &problem{http.StatusForbidden, "registration_closed", "New accounts cannot be created."}
	}
	var in struct{ Name, Email, Password string }
	if err := read(w, r, &in); err != nil {
		return err
	}
	if !s.signup.Allow(s.client(r), s.Now()) {
		return tooMany()
	}
	in.Name, in.Email = strings.TrimSpace(in.Name), strings.TrimSpace(in.Email)
	address, err := mail.ParseAddress(in.Email)
	if err != nil || address.Address != in.Email || len(in.Email) > 254 {
		return bad("invalid_email", "Enter a valid email address.")
	}
	if n := utf8.RuneCountInString(in.Name); n < 1 || n > 80 {
		return bad("invalid_name", "Enter a name of at most 80 characters.")
	}
	if err := checkPassword(in.Password); err != nil {
		return err
	}
	u, err := s.Store.CreateUser(r.Context(), in.Email, in.Name, auth.HashPassword(in.Password))
	if errors.Is(err, store.ErrConflict) {
		return &problem{http.StatusConflict, "email_in_use", "An account with this email already exists."}
	}
	if err != nil {
		return err
	}
	if err := s.startSession(w, r, u.ID); err != nil {
		return err
	}
	return write(w, http.StatusCreated, u)
}

func checkPassword(password string) error {
	if n := utf8.RuneCountInString(password); n < 10 || len(password) > 200 {
		return bad("invalid_password", "Use a password of 10 to 200 characters.")
	}
	return nil
}

func tooMany() error {
	return &problem{http.StatusTooManyRequests, "too_many_requests", "Too many attempts. Try again later."}
}

func (s *Server) login(w http.ResponseWriter, r *http.Request) error {
	var in struct{ Email, Password string }
	if err := read(w, r, &in); err != nil {
		return err
	}
	email, now := strings.TrimSpace(in.Email), s.Now()
	if !s.logins.Allow("ip "+s.client(r), now) || !s.logins.Allow("email "+strings.ToLower(email), now) {
		return tooMany()
	}
	wrong := &problem{http.StatusUnauthorized, "wrong_credentials", "The email or password is wrong."}
	if len(in.Password) > 200 {
		return wrong
	}
	id, hash, err := s.Store.Credentials(r.Context(), email)
	if errors.Is(err, store.ErrNotFound) {
		auth.CheckNothing(in.Password)
		return wrong
	}
	if err != nil {
		return err
	}
	if ok, err := auth.CheckPassword(hash, in.Password); err != nil || !ok {
		if err != nil {
			return err
		}
		return wrong
	}
	if err := s.startSession(w, r, id); err != nil {
		return err
	}
	return write(w, http.StatusOK, map[string]string{"status": "signed_in"})
}

func (s *Server) startSession(w http.ResponseWriter, r *http.Request, userID string) error {
	token, hash := auth.NewSecret("")
	if err := s.Store.CreateSession(r.Context(), userID, hash, sessionLength); err != nil {
		return err
	}
	http.SetCookie(w, s.cookie(token, int(sessionLength/time.Second)))
	return nil
}

func (s *Server) cookie(value string, age int) *http.Cookie {
	return &http.Cookie{Name: sessionCookie, Value: value, Path: "/api", MaxAge: age, HttpOnly: true,
		Secure: s.Config.SecureCookies, SameSite: http.SameSiteLaxMode}
}

func (s *Server) logout(w http.ResponseWriter, r *http.Request) error {
	if c, err := r.Cookie(sessionCookie); err == nil {
		if err := s.Store.DeleteSession(r.Context(), auth.HashSecret(c.Value)); err != nil {
			return err
		}
	}
	http.SetCookie(w, s.cookie("", -1))
	return write(w, http.StatusOK, map[string]string{"status": "signed_out"})
}

func (s *Server) me(w http.ResponseWriter, r *http.Request, u store.User) error {
	return write(w, http.StatusOK, u)
}
