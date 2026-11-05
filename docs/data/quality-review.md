# Channel quality and simultaneous coverage

Review date: 2026-11-05. Scope: the seven restricted Oman continuity groups in the [session inventory](session-review.md). Other collections already have documented exploratory/reference/excluded decisions; this review does not readmit them. No model or cleaning transform was fitted.

## Screening versus measurement validity

All retained Oman session rows have finite DO, water temperature and pH values inside the broad screening bounds: DO nonnegative, temperature -3 to 60 °C and pH 0–14. This is **screening validity**, not independent evidence of calibration accuracy, absence of noise or suitability as a target.

The earlier 5,714-row pond group remains excluded pending ordering review. It is included in the diagnostic report for traceability, but excluded from the candidate totals below. The four other pond groups contain 32,199 rows; the two tank groups contain 102,670 rows.

## Non-destructive diagnostic rules

The audit preserves original values and records separate flags:

- **Invalid:** nonnumeric/non-finite or outside the broad screening bounds. No retained Oman session value fails these checks.
- **DO zero review:** zero remains a possible measured value, with an explicit review flag. It is not replaced with a safe reading or silently counted as instrument failure.
- **Rapid-change review:** absolute adjacent rate exceeds 2 mg/L/min for DO, 1 °C/min for temperature, or 0.5 pH units/min. Rates are calculated only for positive intervals between 5 and 60 seconds and two screening-valid endpoints; intervening gaps are not interpreted as a short-interval jump.
- **Exact-plateau review:** at least three consecutive equal values spanning at least five minutes, with no inter-reading gap greater than 60 seconds. Constant values are not automatically faulty: slowly changing water conditions and sensor quantization can produce plateaus.

These rate/plateau thresholds are **diagnostic sensitivity choices**, not species thresholds, learned fault classifiers or final observation-exclusion rules. Their values were not selected to improve model scores. A later target/input quality policy must decide how unresolved flags affect experiment eligibility and report sensitivity where relevant.

## Candidate counts

| Context | Channel | Screening-invalid rows | DO-zero review | Rapid-change review | Plateau-review rows |
|---|---|---:|---:|---:|---:|
| Pond, excluding ordering-review group | DO | 0 | 0 | 11,334 | 0 |
| Pond, excluding ordering-review group | Water temperature | 0 | — | 2 | 4,262 |
| Pond, excluding ordering-review group | pH | 0 | — | 129 | 0 |
| Controlled tank | DO | 0 | 2 | 31,923 | 0 |
| Controlled tank | Water temperature | 0 | — | 30 | 13,633 |
| Controlled tank | pH | 0 | — | 1,498 | 0 |

Counts refer to flagged rows, not independently verified environmental events. A rate flag belongs to the later endpoint of a comparable pair; a plateau flag covers the full run. Counts from different flag categories can overlap and must not be added to claim a number of unique faulty observations.

Frequent DO rate flags show that high-frequency target behavior needs investigation and aggregation sensitivity analysis. They do not justify erasing excursions or assuming that a smooth hourly target is accurate. Independent reference measurements would help distinguish instrument noise from real rapid change.

## Resolution, extremes and saturation

The reports include per-session min/1st/50th/99th/max quantiles, unique-value counts and observed absolute-rate quantiles. DO and pH have observed unique-value increments near 0.001 in their stored units; temperature has minimum unique increments near 0.067–0.068 °C. These are properties of the stored series, not established instrument precision or accuracy.

The longest exact temperature plateau is approximately 15.4 minutes in the main tank group. No DO or pH plateau reaches the five-minute review threshold. Calibration, quantization and dynamics must be considered before calling a temperature plateau a stuck sensor.

No instrument clipping/saturation limit was verified in the acquired recording metadata. The audit therefore records saturation status as unknown rather than classifying repeated minima/maxima as sensor saturation. Existing zero/high-pH/high-DO observations remain visible in source and diagnostic reports.

## Simultaneous sensor coverage

Two configurations are measured separately: DO-only and DO plus water temperature/pH. Both have 100% screening-valid row coverage in each retained group, so adding the two channels loses no rows **under these broad checks**. Calibration validity, diagnostic reviews and time coverage still apply to both.

For continuity sensitivity, a screening-valid span breaks at an invalid input, a nonpositive interval or an inter-reading gap over 60 seconds. The longest spans are:

| Context/group | Rows in group | Longest screening-valid span, DO-only or multivariate |
|---|---:|---:|
| Excluded first pond group | 5,714 | 5.97 h; not a modeling candidate |
| Short pond fragment | 225 | 0.22 h |
| April 1 pond fragment | 3,152 | 5.81 h |
| March 28–30 pond group | 22,715 | 42.77 h |
| March 27 pond group | 6,107 | 11.59 h |
| Main tank group | 102,379 | 72.06 h |
| April 1 tank fragment | 291 | 0.55 h |

Duration is the elapsed time between the first and last observations, not filled time or an assumption of continuous measurement at every instant. A 60-second gap threshold is a diagnostic scenario, not yet the final resampling policy. The shortest fragments cannot support a six-hour history plus future target. Actual window counts must use bin coverage and split boundaries rather than row count or this table alone.

## Decisions and remaining work

The confirmed source/session exclusions remain unchanged. Screening-invalid observations are unsuitable; diagnostic flags stay as review annotations without automatic repair or biological-event labels. DO-only and multivariate configurations remain candidates subject to the next aggregation/missing-data policy and final release selection. No group has training approval.

The next step is to define justified bin coverage, gap/staleness limits, target validity and handling of unresolved rapid-change/plateau flags. That step will select policies before modeling, with explicit caveats where reference-meter evidence is absent. Calibration limitations and lack of independent sites remain documented even if all numeric checks pass.

## Reproduce and verify

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_quality -v
.\.venv\Scripts\python.exe -m ml.data.quality --output Datasets/processed/oman-quality-new-run
```

Completed output: `Datasets/processed/oman-quality-2026-11-05/`. `quality.json` contains seven session/channel reports and rule definitions. `row_quality_flags.csv.gz` contains 140,583 mapped rows, including the excluded group for auditability. `screening_valid_spans.csv` records spans by session and sensor configuration.

Checks verify source hashes against the session inventory, one-to-one source-row joins, complete flag-row accounting and no duplicated session/source-row identities. Three new tests cover zero/event preservation, plateau gap boundaries and invalid-input span splitting. All 30 focused data-preparation/audit tests pass. Raw and prior cleaned measurements remain unchanged.
