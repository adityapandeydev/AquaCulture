# Running the development baselines

The executable benchmark compares persistence and daily seasonal persistence on the approved DO release. It reports training and validation results only. It does not fit learned model weights, touch calibration/final-test scoring or require a GPU.

## Run from PowerShell

Open a terminal at the repository root. The existing preparation environment has all dependencies for this benchmark:

```powershell
$python = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $python -B -u -m ml.training.baselines --matrix --output ml/runs/baselines-first
```

`--matrix` runs both DO-only and DO/temperature/pH configurations at +1 h and +3 h. Baselines use historical DO in both configurations, so corresponding results should agree; the separate window IDs make later sensor-ablation comparisons traceable. Omit `--matrix` to run only the configuration/horizon in `ml/training/configs/do_pilot.json`. Use a new output directory for every invocation; an existing directory is never overwritten.

The command prints release verification, expected counts, numbered computation steps and validation MAE/RMSE with prediction coverage. `-u` keeps progress unbuffered. There are no epochs because these reference methods have no optimizer.

To validate the complete command and counts without making predictions or calculating statistics:

```powershell
& $python -B -u -m ml.training.baselines --matrix --dry-run --output ml/runs/baselines-check
```

The matrix contains 472 train/validation windows across configurations/horizons. A complete run produces 944 model/window prediction records and 128 metric records across partition, configuration, horizon, model, cohort and diagnostic subset. They include paired alternatives and overlapping histories, not independent trials.

## What each method sees

Persistence uses the last completed historical DO bin at the issue time. Daily seasonal persistence uses the eligible observation at **target time minus 24 hours**, in the same session and partition. At +3 h, that is issue time minus 21 hours, not issue time minus 24 hours. Neither predictor reads a future target value when constructing its forecast.

When a seasonal reference is unavailable, its output has an explicit unavailable status and an empty prediction. The scorer records the missing coverage. Seasonal comparisons use the seasonal-matched cohort for both models; their errors cannot be compared with persistence errors on a different full cohort. Validation seasonal support is only eight examples per configuration/horizon, or six common issues when both horizons need seasonal support.

The 10th-percentile lower-DO diagnostic threshold is computed once from the 100 distinct training DO observations, using linear interpolation. Validation values never fit it. It describes a relative lower tail and is not a biological safety threshold. Empty diagnostic subsets receive null metrics and zero sample counts.

## Saved files

| File | Contents |
|---|---|
| `predictions.csv` | Window context, baseline prediction/status/reason, canonical float64 observed DO, signed/absolute errors and cohort flags |
| `metrics.csv`, `metrics.json` | MAE, RMSE, signed bias, persistence skill, expected/valid/missing/failed/unavailable counts and coverage |
| `run.json` | Configuration, source/release/policy hashes, development counts, training-only diagnostic threshold, output checksums and execution status |
| `config.json`, `prepared-release.json` | Exact configuration and checksum-anchor snapshots |

Scores join by window ID rather than row order and reject duplicate/unknown IDs or mismatched prediction context. Non-finite/negative forecasts and missing rows remain visible in coverage. Conditional errors do not qualify as complete-cohort results. MAE skill is computed only with complete paired predictions; a zero persistence MAE gives a null skill with an explicit reason. Signed error is prediction minus observation, so positive bias means overprediction.

The full cohort and the training-lower-decile diagnostic are reported separately for each registered comparison cohort. No subset is silently substituted for the main result. Baseline results describe this recorded development period, not independent-farm accuracy or model qualification. GPU training and inference-resource gates are not assessed by this benchmark.

## Notebook interface and tests

`ml/notebooks/06_baseline_benchmark.ipynb` calls the same `run_baselines` function and displays validation tables. It is stored without executed outputs. Running the notebook performs the benchmark; run records remain under ignored `ml/runs/`.

Any notebook kernel with the preparation dependencies can run this CPU benchmark. The CUDA model environment is needed when neural training is implemented, not to run these reference forecasts.

```powershell
& $python -B -m unittest discover -s ml/training/tests -q
& $python -B -m unittest discover -s ml/data -p 'test_*.py' -q
```

Synthetic tests cover baseline alignment, future/partition isolation, matched metrics, explicit unavailable results, zero-reference error, empty cohorts, invalid/nullable outputs, training-only threshold fitting and held-out scoring guards. Real-data dry runs verify the published release and all development counts without scoring it. The complete baseline run is left for the developer to launch and inspect.

Implementation lives in `ml/modeling/baselines.py`, `ml/evaluation/metrics.py` and `ml/training/baselines.py`. Shared provenance comes from `ml/training/experiment.py`. The next learned reference is ridge regression, followed by the compact GPU-trained GRU under the existing search/evaluation rules.
