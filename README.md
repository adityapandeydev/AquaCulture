# AquaTech

AquaTech is a pond monitoring and early-warning system for aquaculture. It is for research and demonstration. The app shows current water conditions, forecasts the sensor's dissolved oxygen a few hours ahead, and warns when limits are crossed or low oxygen is likely. It misses some drops, so it supports pond checks and cannot replace them.

## Status

| Part | State |
| --- | --- |
| Data | A 17-pond carp dataset is prepared. [Dataset record](docs/data/carp.md) |
| Forecast models | Tested for research and demonstration use: point forecasts to +6 h, an interval at +1 h and low-oxygen probabilities. [Results](docs/models/results.md) |
| Model service | Working on localhost. [Contract and performance](docs/models/service.md) |
| Backend | Working on localhost, Go. [Guide](backend/README.md) |
| Frontend | Working on localhost, React. [Guide](frontend/README.md) |

An earlier experiment on a single tilapia tank failed its limits. [Pilot record](docs/pilot/README.md). No suitable shrimp data has been found, so shrimp ponds have monitoring and limit alerts without forecasts.

## Documents

| Question | Page |
| --- | --- |
| What data is used, and what was rejected? | [Sources](docs/data/sources.md), [carp dataset](docs/data/carp.md) |
| How were the models chosen and tested? | [Plan](docs/models/forecast.md), [results](docs/models/results.md) |
| How does the forecast service work? | [Service](docs/models/service.md) |
| How do the backend and app work? | [Backend](backend/README.md), [frontend](frontend/README.md) |
| What was the first experiment? | [Pilot](docs/pilot/README.md) |

JSON files beside these pages hold fixed policies, limits and checksums. Results depend on their exact content, so they are changed only as a new version.

## Layout

```text
AquaCulture/
├── backend/        Application server and background worker
├── frontend/       Web app
├── ml/
│   ├── data/       Acquisition, audit and dataset preparation
│   ├── models/     Naive, ridge, tree and neural forecasters
│   ├── training/   Training runs
│   ├── evaluation/ Metrics, calibration and testing
│   ├── service/    Forecast HTTP service
│   └── tests/      Python tests
└── docs/
    ├── data/       Current dataset, sources and policy
    ├── models/     Forecast experiment and acceptance criteria
    └── pilot/      Archive of the first experiment
```

Datasets, experiment runs, model bundles and credentials are not tracked.

## Run on one machine

Three terminals, from the repository root. The [backend guide](backend/README.md) covers the first setup.

```powershell
python -B -m ml.service.app                 # 1. forecast service, in its own environment
cd backend; go run ./cmd/server             # 2. backend
cd frontend; bun install; bun run dev       # 3. app on http://127.0.0.1:5190
```

## Tests

Training and service packages are installed in separate environments. Each skips the tests it has no packages for.

```powershell
python -B -m unittest discover -s ml/tests -t .
```
