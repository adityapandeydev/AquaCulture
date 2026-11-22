# Backend

A Go server with the public API and a background worker. It stores readings in PostgreSQL, calls the private [forecast service](../docs/models/service.md) and keeps alerts current.

| Folder | Purpose |
| --- | --- |
| `cmd/server` | Program entry |
| `internal/api` | HTTP routes, validation, sign-in |
| `internal/auth` | Passwords, random credentials, rate limits |
| `internal/config` | Settings |
| `internal/model` | Forecast service client |
| `internal/readings` | Sensor values, CSV, local hours |
| `internal/store` | Database access and migrations |
| `internal/worker` | Forecast schedule, jobs, alert rules |

## Run

Settings come from the environment or `backend/.env`. Only `DATABASE_URL` is required.

| Setting | Default |
| --- | --- |
| `DATABASE_URL` | |
| `ADDRESS` | `127.0.0.1:8090` |
| `MODEL_URL`, `MODEL_TOKEN` | `http://127.0.0.1:8100`, none |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `SECURE_COOKIES` | `false`, set to `true` behind HTTPS |
| `REGISTRATION` | `true` |
| `TRUST_PROXY` | `false`, set to `true` only behind a proxy that sets `X-Forwarded-For` |

```powershell
cd backend
go run ./cmd/server -migrate
go run ./cmd/server
```

Migration refuses a database that holds another application's tables.

## Behaviour

- **Ponds** are live or demo. Live ponds take device readings and receive a forecast each hour. Demo ponds replay imported data, and forecasts are requested for past hours. The two are never mixed.
- **Readings** are never changed. The first value for a pond and time is kept, and later different values are counted as conflicts. Conflicting values inside one upload are all rejected.
- **Hours** follow the pond's local clock. An hour's mean leaves out exact zeros, as model training did. A zero oxygen reading raises its own alert, because it may be a sensor fault or a real loss of oxygen.
- **Forecasts** are issued once per pond and hour, 3 minutes after the hour closes. A forecast that cannot be made within its hour is recorded as unavailable and is never made later.
- **Outages** of the model do not affect monitoring. Failed calls are retried, and the last real forecast counts until its targets pass.
- **Alerts** have one open entry per kind and pond. Stale data cannot close an oxygen alert. A rise in severity needs a new acknowledgement. No alert does not mean that a pond is safe.
- **Thresholds** are chosen by the operator. Suggestions carry their source. The carp values come from the Fish Welfare Initiative programme. The shrimp values come from secondary literature and need review before use.
- **Accuracy** compares stored forecasts with hours observed later, against simple persistence.

## Devices

A device key is shown once and stored as a hash.

```text
POST /api/v1/ingest
Authorization: Device aqd_...
Content-Type: application/json

{"readings": [{"observed_at": "2026-01-24T00:30:00Z", "do_mgL": 5.4, "ph": 8.1, "temperature_c": 25.3}]}
```

CSV imports need the columns `timestamp` and `do_mgl`, and may have `ph` and `temperature_c`. Times without an offset are read in the pond's timezone. An import is a preview unless `commit=true`.

## Tests

```powershell
go vet ./...
go test ./...
```

The tests start their own PostgreSQL and never read `.env`. The first run downloads it.

`TestChain` checks the whole system. It imports raw sensor data, computes forecasts through the database and the real model service, and compares them with the research code. It is skipped unless both variables are set.

```powershell
& $python -B -m ml.evaluation.chain
$env:CHAIN_MODEL_URL = 'http://127.0.0.1:8100'
$env:CHAIN_REFERENCE = "$PWD/ml/runs/chain-reference.json"
```

On 22 November 2026, 150 forecasts matched within 0.0005 mg/L, which is the rounding of the output.
