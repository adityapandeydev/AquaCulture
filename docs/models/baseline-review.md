# First development baseline results

Reviewed 2026-11-09 from the developer-run `ml/runs/baselines-first/` benchmark. Run-record SHA-256: `1dcd65908238a93367a04e06c9c4c41f447dbaab8aff0ac9cbf27aa1bcb05c60`.

The saved output checksums, release anchor, source fingerprints and locked-partition metadata agree. Whole-target cohort MAE/RMSE values were independently recomputed from `predictions.csv`, including explicit unavailable seasonal predictions. Only training and validation were scored. The run contains 944 prediction records and 128 metric records across the registered alternatives; no learned weights were fitted.

## Validation results

DO-only and DO/temperature/pH baselines agree because both reference methods use DO alone. The table applies to either configuration.

| Horizon | Cohort | Targets | Persistence MAE / RMSE, mg/L | Daily seasonal MAE / RMSE, mg/L |
|---|---|---:|---:|---:|
| +1 h | Full horizon-specific | 26 | 0.246824 / 0.318449 | Incomplete coverage: 8/26 predictions |
| +3 h | Full horizon-specific | 24 | 0.349044 / 0.444921 | Incomplete coverage: 8/24 predictions |
| +1 h | Seasonal matched | 8 | 0.225498 / 0.311180 | 0.675417 / 0.757167 |
| +3 h | Seasonal matched | 8 | 0.509852 / 0.600527 | 0.675417 / 0.757167 |

Persistence has complete prediction coverage. Seasonal persistence is worse on the matched subsets and cannot replace it as the main comparator. The identical seasonal error at the two horizons is expected here: the matched target hours and 24-hour reference observations coincide, while their issue times differ.

The training-only lower-decile threshold is 6.8687591667 mg/L. There are zero validation targets at or below it for these cohorts, so lower-tail validation errors are null. This gives no lower-DO or biological-event performance evidence.

## Consequence for the learned references

The next comparison is regularized regression on the six-bin history, separately by horizon and input configuration. Scaling and coefficients use training only; validation chooses from four predeclared regularization strengths. The final test and calibration periods remain locked.

The provisional 5% improvement requirement corresponds to validation MAE at most approximately 0.234483 mg/L for +1 h and 0.331592 mg/L for +3 h on their full cohorts. Absolute error, bias, RMSE-regression and completeness gates also apply. These numbers are comparison targets, not achieved learned-model results or field qualification. No test result is used to choose an architecture or change the split.
