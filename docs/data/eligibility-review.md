# First forecasting release: eligibility and scope

Review date: 2026-11-05. Decision: select the main Oman controlled-tank session for a small, chronological DO forecasting pilot. The release is selected for partition planning; training remains blocked on the remaining split, window, evaluation and release checks. No predictive model has been fitted.

The machine-readable [selection](release-selection.json) records the session roles and initial experiment scope. The [source review](source-review.md), [quality review](quality-review.md) and [aggregation policy](aggregation-policy.md) supply the evidence behind those decisions.

## Selected data and channels

| Item | Selection and evidence |
|---|---|
| Source | Oman author repository, pinned commit `d95207b6f129c3de1f426ec90eed5a38f46832b8`; acquired files have recorded SHA-256 hashes and author-declared CC BY 4.0 terms. |
| Primary session | `oman-2cbad87a2dbd2a81d6e1`, controlled 180 L tank; publisher-declared Nile tilapia. Physical-site independence is unverified. |
| Time support | 188 consecutive eligible one-hour bins: first bin `[2026-04-02 07:00, 08:00)` UTC, last bin `[2026-04-10 02:00, 03:00)` UTC. This is 7 days 20 hours of bin support, with the permitted small observation gaps still present. |
| Target | Future DO summary, mg/L: mean of supported minute medians, under `oman-hourly-v1`. |
| Minimum inputs | Historical eligible DO bins. |
| Extended inputs | Historical eligible DO, water temperature (°C) and pH; same eligible hours as DO-only. Extra sensors are a comparison, not a promised improvement. |
| Primary task | Six completed hourly input bins, predicting the next hour's DO summary (1-hour horizon). |
| Secondary task | Same six-hour history, 3-hour horizon, subject to adequate partition counts. |
| Deferred variants | 12/24-hour histories and 6-hour forecasts have feasibility counts, but are outside the first comparison unless later split sufficiency justifies a versioned change. |

Channel units and timestamp interpretation have source evidence. Numeric coverage checks pass, but calibration accuracy remains unverified and rapid-change/plateau diagnostics remain unresolved. These data are suitable for a limited methodological pilot, not evidence of operational reliability. The eligible hourly DO summaries span approximately 6.430–9.778 mg/L; this does not establish coverage of hazardous low-oxygen events or instantaneous extrema.

## Session decisions

Both input configurations have the same eligible hours and example counts.

| Session | Context | Eligible hours / longest run | Role |
|---|---|---:|---|
| `oman-2cbad87a2dbd2a81d6e1` | Main tank recording | 188 / 188 | Primary pilot, selected for partition planning |
| `oman-af7b8feb5e74019b0afc` | Pond | 42 / 42 | Context diagnostics only |
| `oman-c58a4e8c880d2a6a5258` | Pond | 11 / 11 | Context diagnostics only |
| `oman-87c10c86fe6e1b54d7c6` | Pond | 5 / 5 | Context diagnostics only; too short for six-hour history plus target |
| `oman-5be584c894082740491f` | Short pond fragment | 0 / 0 | Excluded: no hourly bin passes the preparation policy |
| `oman-d2a9072243df68854549` | Short tank fragment | 0 / 0 | Excluded: no hourly bin passes the preparation policy |
| `oman-4aa66291b0a6af9fd6a7` | First pond group | 0 / 0 candidate hours | Excluded pending source-ordering evidence, regardless of numeric bin coverage |

The pond recordings provide 58 hours in three short eligible runs, rather than one 58-hour history. Their duration makes separate fitting, tuning, calibration and final evaluation particularly fragile. They are retained for contextual diagnostics and excluded from the primary fitting release. No pond result will be described as independent-farm validation: pond/tank identities and their shared study lineage do not establish independent sites. A later pond experiment requires its own explicit selection and split decision.

All other source groups retain their documented dispositions. Shrimp-buoy channels lack defensible conversion/deployment evidence; aquaponics has unresolved units, faults and shared sequences; Colombia has unresolved measured-versus-filled status and metadata; local variants have lost provenance; compilation/classification/chemistry tables do not supply the required forecasting series. WorldFish remains unacquired. None contributes inputs or labels to this pilot.

## Feasible examples before splitting

The counting rule requires consecutive eligible historical input bins, including the issue hour, followed by eligible DO bins throughout the forecast interval and at the target hour, all within one session. A forecast issued at 10:00 with a 1-hour horizon targets the summary over `[10:00, 11:00)`. The intermediate-DO requirement is conservative: it prevents a forecast span from bridging an unobserved outage. It does not require future temperature or pH, which would incorrectly condition forecasts on optional future input availability.

The table gives counts for the primary tank session. The corresponding DO-only and multivariate counts are equal; they are alternative configurations of the same observations, not separate datasets.

| Historical bins | 1-hour horizon | 3-hour horizon | 6-hour horizon |
|---:|---:|---:|---:|
| 6 | 182 | 180 | 177 |
| 12 | 176 | 174 | 171 |
| 24 | 164 | 162 | 159 |

For context only, the pond runs yield 41/37/31 examples at six-hour history and 1/3/6-hour horizons. At 12 hours the counts are 30/28/25, and at 24 hours they are 18/16/13. The five-hour pond run supplies none.

These are **pre-split, overlapping examples**. Consecutive examples share observations and are statistically dependent. Counts will fall when chronological target boundaries, calibration periods and any required separation are applied. Neither 182 windows nor 188 hours can be presented as 182 independent trials or a large training corpus.

The short recording supports testing a compact forecasting workflow. It does not justify a large neural architecture, an extensive hyperparameter search, cross-species accuracy claims or a precise calibrated-confidence claim. Partition planning must report actual fitting, validation, calibration and final-test counts and narrow the scope further if those periods are insufficient. Nominal 80%/90% intervals remain research candidates, not committed release outputs.

## What this release can establish

The first benchmark can compare new models trained from scratch with persistence on a small chronological slice of one publisher-declared tilapia tank recording. Later reporting must include baseline error, physical-unit errors, example counts, measurement limitations and the tank environment. Model complexity must earn its place through development-set results and measured CPU costs.

This selection does not validate other fish, shrimp, farms, seasons, disease outcomes or automated interventions. It does not establish an independent-site holdout. Additional traceable recordings across deployments, longer periods and independently verified sensor measurements would be needed to support those claims.

## Reproduce the feasibility report

Run from the repository root using Python 3.10+ with pandas, NumPy and openpyxl. The commands acquire only cataloged public files and write separate preparation outputs. Use fresh output paths; the preparation commands refuse existing directories.

```powershell
.\.venv\Scripts\python.exe -m ml.data.acquire
.\.venv\Scripts\python.exe -m ml.data.sessions --output Datasets/processed/oman-sessions-review
.\.venv\Scripts\python.exe -m ml.data.quality --sessions Datasets/processed/oman-sessions-review --output Datasets/processed/oman-quality-review
.\.venv\Scripts\python.exe -m ml.data.aggregation --sessions Datasets/processed/oman-sessions-review --quality Datasets/processed/oman-quality-review --output Datasets/processed/oman-hourly-review
.\.venv\Scripts\python.exe -m ml.data.eligibility --prepared Datasets/processed/oman-hourly-review --output Datasets/processed/oman-eligibility-review
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

Completed feasibility output: `Datasets/processed/oman-eligibility-2026-11-05/`. `example_counts.csv` records all nine history/horizon combinations by session and input configuration. `eligibility.json` records session support, roles, observed target ranges, input hashes and the selection version. No final supervised indices, partitions, scaler or model are created. Raw files, generated datasets and local task notes remain outside version control.

Six focused tests cover hour/horizon indexing, same-session history, missing inputs and targets, gaps in the future DO path, optional future-sensor isolation and duplicate-key validation. The preparation suite has 45 passing tests. Raw inputs are verified through the aggregation's recorded hashes, and the feasibility inputs are checked again before export.
