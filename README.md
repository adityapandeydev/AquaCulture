# AquaTech

AquaTech is a pond monitoring and early-warning system for aquaculture. It is being rewritten. The goal is a dashboard that shows current water conditions, forecasts dissolved oxygen with honest uncertainty, and alerts operators before oxygen runs low.

## Status

| Part | State |
| --- | --- |
| Data | A 17-pond carp dataset is prepared. [Dataset record](docs/data/carp.md) |
| Forecast models | Tested for research and demonstration use: point forecasts to +6 h, an interval at +1 h and low-oxygen probabilities. [Results](docs/models/results.md) |
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
│   ├── models/     Naive, ridge, tree and neural forecasters
│   ├── training/   Training runs
│   ├── evaluation/ Metrics, calibration and testing
│   └── tests/      Python tests
└── docs/
    ├── data/       Current dataset, sources and policy
    ├── models/     Forecast experiment and acceptance criteria
    └── pilot/      Archive of the first experiment
```

Datasets, experiment runs and credentials are not tracked.

## Tests

```powershell
python -B -m unittest discover -s ml/tests -t .
```
