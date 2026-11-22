CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL,
    name          text NOT NULL,
    password_hash text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email ON users (lower(email));

CREATE TABLE sessions (
    token_hash bytea PRIMARY KEY,
    user_id    uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX sessions_user ON sessions (user_id);

-- A demo pond replays recorded data. Its readings never count as live conditions.
CREATE TABLE ponds (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    name              text NOT NULL,
    timezone          text NOT NULL,
    species           text NOT NULL CHECK (species IN ('rohu_catla', 'vannamei', 'other_fish', 'other_shrimp')),
    mode              text NOT NULL CHECK (mode IN ('live', 'demo')),
    sampling_minutes  integer NOT NULL CHECK (sampling_minutes BETWEEN 1 AND 30),
    do_low            double precision,
    do_critical       double precision,
    ph_low            double precision,
    ph_high           double precision,
    temperature_low   double precision,
    temperature_high  double precision,
    alert_probability double precision NOT NULL DEFAULT 0.5 CHECK (alert_probability BETWEEN 0.05 AND 0.95),
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (do_critical <= do_low),
    CHECK (ph_low < ph_high),
    CHECK (temperature_low < temperature_high)
);
CREATE INDEX ponds_owner ON ponds (owner_id);

CREATE TABLE devices (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pond_id      uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    name         text NOT NULL,
    key_hash     bytea NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz,
    revoked_at   timestamptz
);
CREATE INDEX devices_pond ON devices (pond_id);

-- Readings are never changed. The first value for a pond and time is kept.
CREATE TABLE readings (
    pond_id       uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    observed_at   timestamptz NOT NULL,
    do_mgl        double precision,
    ph            double precision,
    temperature_c double precision,
    source        text NOT NULL CHECK (source IN ('device', 'import')),
    device_id     uuid REFERENCES devices ON DELETE SET NULL,
    received_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pond_id, observed_at)
);

-- Derived from readings. Exact zero DO is excluded from the mean.
CREATE TABLE hours (
    pond_id       uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    start_at      timestamptz NOT NULL,
    do_mgl        double precision,
    do_min        double precision,
    ph            double precision,
    temperature_c double precision,
    coverage      double precision NOT NULL,
    zero_readings integer NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pond_id, start_at)
);

CREATE TABLE jobs (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pond_id    uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    issue_time timestamptz NOT NULL,
    state      text NOT NULL DEFAULT 'waiting' CHECK (state IN ('waiting', 'running', 'done', 'failed')),
    attempts   integer NOT NULL DEFAULT 0,
    run_after  timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pond_id, issue_time)
);
CREATE INDEX jobs_ready ON jobs (run_after) WHERE state IN ('waiting', 'running');

CREATE TABLE forecasts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pond_id         uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    issue_time      timestamptz NOT NULL,
    status          text NOT NULL CHECK (status IN ('ok', 'unavailable')),
    model_id        text,
    manifest_sha256 text,
    reasons         text[] NOT NULL DEFAULT '{}',
    warnings        text[] NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pond_id, issue_time)
);

CREATE TABLE forecast_values (
    forecast_id   uuid NOT NULL REFERENCES forecasts ON DELETE CASCADE,
    horizon_hours integer NOT NULL,
    target_start  timestamptz NOT NULL,
    target_end    timestamptz NOT NULL,
    point_mgl     double precision,
    low_mgl       double precision,
    high_mgl      double precision,
    threshold_mgl double precision,
    probability   double precision,
    withheld      text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (forecast_id, horizon_hours)
);

CREATE TABLE alerts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pond_id         uuid NOT NULL REFERENCES ponds ON DELETE CASCADE,
    kind            text NOT NULL,
    origin          text NOT NULL CHECK (origin IN ('observed', 'forecast', 'system')),
    severity        text NOT NULL CHECK (severity IN ('warning', 'critical')),
    message         text NOT NULL,
    opened_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    resolved_at     timestamptz
);
-- At most one open alert of each kind per pond.
CREATE UNIQUE INDEX alerts_open ON alerts (pond_id, kind) WHERE resolved_at IS NULL;
CREATE INDEX alerts_recent ON alerts (pond_id, opened_at DESC);
