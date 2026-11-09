# Ridge regression on the frozen DO windows

The ridge reference learns new coefficients from the six-bin history, using only training observations. It provides a compact learned comparator before the GPU sequence model. It is independent of the application's existing TensorFlow models and weights.

## Run in PowerShell

From the repository root:

```powershell
$python = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $python -B -u -m ml.training.ridge --matrix --output ml/runs/ridge-first
```

This uses the existing preparation dependencies; no additional package installation or GPU is required for ridge. `--matrix` runs DO-only and DO/temperature/pH at +1 h and +3 h. Omit it to use only the setting in `do_pilot.json`. Every run needs a new output directory.

The command displays each case, each of the four fits, validation error/coverage, checkpoint saves and the selected alpha. `-u` makes output appear immediately. There is no epoch loop because ridge uses a closed-form solve. The later neural trainer uses CUDA and will have epoch progress.

For a preflight without fitting:

```powershell
& $python -B -u -m ml.training.ridge --matrix --dry-run --output ml/runs/ridge-check
```

The dry run checks release integrity, configuration, case counts, dtype and array/index alignment. It fits no scaler, coefficients or diagnostic threshold and computes no prediction scores. Delivery verification used this real-data preflight and synthetic end-to-end fits; the actual dataset fit is left for the developer to launch.

## Model definition

Each example's six chronological bins are flattened in row-major order. DO-only has six lag features; the extended configuration has eighteen, ordered DO/temperature/pH within each hour, oldest hour first. The model uses float64 canonical values, while the default development arrays remain float32 for the later neural path.

Feature means and population standard deviations (`ddof=0`) are fitted on the training windows only. Constant training columns are centered exactly and assigned unit scale, preventing floating-point roundoff from turning a constant into an artificial standardized signal. Validation data never updates these values. The unpenalized intercept is the training target mean.

For standardized training matrix `Z`, centered training targets `y`, and alpha `a`, the coefficients solve `(Z.T @ Z + a*I) w = Z.T @ y`. The objective is the sum of squared training errors plus `a` times the squared standardized coefficients. Predictions are directly in mg/L. No pretrained weights, target imputation or post-hoc output clipping is used.

## Fixed search and selection

[ridge_settings.json](../../ml/training/configs/ridge_settings.json) preregisters alpha **0.1, 1, 10 and 100**, exactly four settings per configuration/horizon, within the frozen search budget. All settings are evaluated on the same complete validation cohort. Choose the lowest validation MAE among complete finite candidates; remaining exact ties within this equal-cost implementation use registered setting order. Cross-family selection retains the broader evaluation protocol's simplicity/resource rules. No additional settings are tried in response to test errors.

The algorithm is deterministic and uses no random seed or stochastic replicas. The common experiment config's seed is recorded for provenance but is explicitly marked unused. Calibration and final-test data are not available through this runner. Training errors are diagnostics, not selection criteria.

If every candidate has incomplete or invalid validation predictions, the case reports no selected model. It never fills failed forecasts, borrows labels or substitutes an unregistered setting. A numerical fit or wall-budget failure is recorded as a failed trial. Fit-and-predict timing is checked against the 600-second per-fit budget after each closed-form computation; these small solves are not a hard realtime timeout service.

## Saved artifacts

Each `<configuration>/horizon_<h>/` directory contains:

- `trial_01/` through `trial_04/`: data-only `model.json` checkpoints and train/validation prediction rows for each successful setting.
- `trials.json`: statuses, elapsed fit/prediction time and complete-cohort training/validation metrics for every setting, including failures.
- `selected_model.json`: the selected parameters and fitted means/scales, with no executable pickle content.
- `case.json`: feature order, input shape, train/validation window IDs, selected alpha, metrics and validation error-gate reasons.

The model JSON is loaded by `ml.modeling.ridge.RidgeForecaster.load`. Keep `case.json` and the root run metadata with the parameters so feature order, horizon, source and experiment bindings remain explicit. JSON shape, scale, coefficient and finite-value checks apply on load; existing model files cannot be overwritten by `save`.

Root files include `predictions.csv`, `metrics.csv`/`metrics.json` for the selected ridge and both baselines on identical cohorts, plus `progress.log`, configuration/settings/descriptor snapshots and `run.json`. The run record includes code/data/policy hashes, host/thread environment, selected artifacts and output checksums. During a fit it has a running status and per-case progress; an interrupted/failed run is not a completed experiment.

The lower-DO diagnostic threshold uses only the 100 distinct training bins. Seasonal comparisons remain limited to the explicitly supported subset, and empty lower-tail validation subsets remain unsupported rather than perfect results.

## Interpreting the result

The [first baseline review](baseline-review.md) establishes persistence as the main comparator. Ridge reports whether its selected validation result meets the provisional physical-unit error, coverage, 5% MAE-skill and no-RMSE-regression gates. A passing validation error check **does not qualify the model**: CPU inference resource tests and locked final evaluation remain outstanding. A failing check remains visible with its reasons; another model is not selected using final-test outcomes.

The matrix has 16 planned fits. If each case selects a model, the root comparison contains 1,416 model/window predictions and 192 metric records, including paired alternatives and diagnostic subsets. They are not independent environmental trials.

`ml/notebooks/07_ridge_reference.ipynb` calls the same runner and summarizes chosen alphas. Tests cover analytic solutions, scaling/validation isolation, constant columns, float64 preservation, JSON roundtrips, malformed artifacts, bounded settings, complete-cohort selection and a synthetic full training/reporting run. The next model-development slice is the compact CUDA GRU after reviewing this CPU reference.
