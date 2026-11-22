# AquaTech

AquaTech is a pond monitoring and early-warning system for aquaculture. It is being rewritten. The goal is a dashboard that shows current water conditions, forecasts dissolved oxygen with honest uncertainty, and alerts operators before oxygen runs low.

## Status

| Part | State |
| --- | --- |
| Data | A 17-pond carp dataset is prepared. [Dataset record](docs/data/carp.md) |
| Forecast models | In development. No model is approved for use. |
| Model service | Planned, Python |
| Backend | The Python backend in `backend/` no longer runs and will be replaced by a Go service. |
| Frontend | The existing React app in `frontend/` will be rebuilt. |

The first forecasting experiment, on a single tilapia tank, failed its acceptance criteria. Its record is in the [pilot archive](docs/pilot/README.md). No suitable shrimp dataset has been found, so shrimp ponds will have monitoring and threshold alerts without forecasts.

## Layout

```text
AquaCulture/
├── backend/        Application server (legacy, to be replaced)
├── frontend/       Web dashboard
├── ml/
│   ├── data/       Acquisition, audit and dataset preparation
│   └── tests/      Python tests
└── docs/
    ├── data/       Current dataset, sources and policy
    └── pilot/      Archive of the first experiment
```

Datasets, experiment runs and credentials are not tracked.

## Tests

```powershell
python -B -m unittest discover -s ml/tests -t .
```
