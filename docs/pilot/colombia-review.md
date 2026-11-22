# Colombia workbook: cadence and label review

Review date: 2026-11-05. Decision: exploratory-only; excluded from the current forecasting and biological-outcome benchmarks. The workbook and existing cleaned outputs are unchanged.

## File and evidence

The local `O1D3` workbook has SHA-256 `5c7fba481c91d4f227450044d8f620af157406061b360c0f2c669c0b041a9bfe`. Its origin remains unverified because the original acquisition link is unavailable. Two publisher records are plausible related sources, not proven identities for this file:

- [3g2b4sh65m, version 1](https://data.mendeley.com/datasets/3g2b4sh65m/1) describes hourly January–June 2024 observations, interpolation, and rule-derived risk/health fields.
- [8s73jfvgr5, version 3](https://data.mendeley.com/datasets/8s73jfvgr5/3), by the same contributors with a related title/schema, describes six-hour readings and interpolation.

These descriptions were checked against the publisher pages. No publisher file checksum was matched, so neither stated cadence nor license is automatically assigned to the local workbook. Their relationship is a lineage warning, not evidence of two independent datasets.

## Findings in the local file

| Check | Result | Consequence |
|---|---|---|
| Timestamps | 4,383 unique, parseable timestamps from January 1 to July 1, 2024 at 14:00; every successive difference is one hour. | Establishes the row grid, not the original sensor cadence. It also extends beyond the January–June description. |
| Repeated water vectors | 4,023 successive rows repeat temperature, DO, pH and turbidity together; only 360 distinct vectors exist. | About 91.8% of successive rows are unchanged. The file cannot be assumed to contain 4,383 independent measured targets. |
| Constant runs | Five runs of 654 rows, one of 759 rows and 354 singleton runs. | At hourly spacing, these are multiweek plateaus: 654 samples span 653 hours between endpoints, not 654 independently verified hours of new measurement. |
| Calendar fields | `hour` has 3,270 fractional entries and 3,371 mismatches with the timestamp hour. `day` has 3,270 fractional entries and 4,023 mismatches. `Month_Num`, `month_x` and `month_y` each have 354 fractional entries and 465 mismatches. | These fields are unsuitable clock features. Timestamp-derived calendar fields would be needed in any later justified reconstruction. |
| Disease cases | 90 fractional entries in `Disease Occurrence (Cases)`. | Not directly interpretable as independently counted cases; no rounding to invented case observations. |
| Oxygen targets | DO ranges 6.34–7.89 in the column's stated mg/L units; no row is below 5. Every low-oxygen label is `Safe`. | Cannot evaluate low-oxygen detection recall or claim demonstrated hypoxia-warning performance. |
| Health labels | 705 `At Risk` and 3,678 `Stable`; exactly matched by `High`/`Normal` thermal-risk values, with zero mismatches. | No independent biological-outcome evidence established. The publisher also describes health status as rule-derived. |

The repeated values, fractional calendar fields and case counts are construction/interpolation warnings. They do not establish exactly how the workbook was made, whether every plateau is artificial, or that the original study fabricated data. Original cadence and the measured-versus-filled status of individual rows remain unknown.

## Model-use decisions

1. Exclude the workbook's water measurements from the current train/validation/test and uncertainty-calibration release. Randomly splitting or treating long plateaus as independent targets could yield misleadingly favorable results.
2. Keep the data for exploratory preparation and lineage checks. Do not repair it by adding noise, dropping repeated rows to manufacture a new cadence, or interpreting every change point as a new measured observation.
3. Exclude normalized/derived columns (`oxigeno_scaled`, lowercase `ph`, `turbidez`), calendar copies, weather summaries and intervention/automatic-control fields from model features. Their construction and issue-time availability are unverified.
4. Exclude risk/health labels and fractional disease counts as biological ground truth. A deterministic risk flag is not a diagnosis or mortality outcome.
5. Keep the recorded timestamp without inventing a timezone, pond identity or species-specific deployment context. The related publisher's tilapia description remains a candidate match for the local file.

Reconsideration requires a matched original source with measurement flags or acquisition records explaining interpolation, sampling and site identity. The present work can proceed on other eligible sources without recovering it.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_colombia_audit -v
.\.venv\Scripts\python.exe -m ml.data.audit_colombia --output Datasets/processed/colombia-new-review
```

Completed audit: `Datasets/processed/colombia-review-2026-11-05/audit.json`. `constant_water_runs.csv` records original worksheet row ranges and timestamps. The utility inspects stored values, does not recalculate formulas or interpolate, and verifies that the raw-file hash is unchanged. This review adds two focused tests; all 18 data-preparation/audit tests pass.
