# Evaluation protocol for the DO pilot

Version: [oman-do-evaluation-v1](evaluation-policy.json), 2026-11-07. This protocol fixes the comparisons and reporting rules for the [supervised tank dataset](supervised-data.md). It registers later model candidates and evaluation cohorts without fitting models, generating forecasts or computing accuracy scores. The [partition policy](partition-review.md) remains unchanged.

The primary question is whether a compact model improves one-hour-ahead DO forecasts over persistence on the same held-out observations. Three-hour forecasts are secondary and reported separately. The experiment concerns hourly DO summaries from one publisher-declared Nile tilapia tank recording; it does not validate other sites, species, hazardous events or operational interventions.

## Baselines and model candidates

Let `t` be the issue time, `h` the elapsed-hour horizon and `y(s)` the eligible DO summary available at time `s`.

| Candidate | Definition and role |
|---|---|
| Persistence | `forecast(t,h) = y(t)`. Required main comparator for every eligible example. |
| Daily seasonal persistence | `forecast(t,h) = y(t+h-24h)`. A secondary comparator on explicitly matched observations only. |
| Ridge regression | A compact learned reference using the flattened six-bin measurement history, with any scaling fitted on training only. |
| Compact single-layer GRU | A small sequence candidate using the same ordered historical measurements. Model size and bounded search settings are registered before fitting. |

Persistence and seasonal persistence follow the naive and seasonal-naive definitions in Hyndman and Athanasopoulos, [Forecasting: Principles and Practice, §5.2](https://otexts.com/fpp3/simple-methods.html). The 24-hour period is a comparator choice, not a demonstrated biological seasonality in this short recording. The [literature review](literature-review.md) motivates comparing compact lag-based and sequence models without assuming that a hybrid architecture wins.

The seasonal reference is aligned to the **target hour**, not always `t-24h`. It must be screening/aggregation-eligible, non-imputed in preparation, available by the issue, and inside the same session and partition. This is an explicit baseline-only exception to the predictive model's six-hour input history. The older reference cannot be borrowed from another partition. Missing references produce an unavailable seasonal comparison, not filled values.

The learned candidates use new parameters trained from scratch. Existing application model weights, pretrained models and runtime imputation artifacts are excluded. Start with separate horizon-specific comparisons; any joint-output experiment uses the common-issue cohort for matched comparisons and records its differing training support. Additional architectures require a development-only experiment amendment before fitting or accessing final-test errors.

## Comparison cohorts and denominators

`evaluation_index.csv` records one row for each of the 640 horizon/configuration-specific windows. It references the latest historical bin for persistence and the applicable older bin for seasonal persistence. It stores no predicted value or score.

Four named cohorts prevent changing the comparison sample silently:

1. **All horizon-specific:** the primary set of eligible windows for that horizon and configuration.
2. **Common horizons:** issues with both one-hour and three-hour targets, used for matched joint-horizon comparisons.
3. **Seasonal matched:** horizon-specific windows with an eligible daily seasonal reference. Evaluate persistence and learned candidates on the same subset when comparing with that baseline.
4. **Common horizons, seasonal matched:** common issues where both horizons also have seasonal references.

Counts below apply to each input configuration separately. The configurations share the same issue/target identities; they are paired alternatives, not independent datasets.

| Partition | All +1 h | All +3 h | Common issues | Seasonal +1 h | Seasonal +3 h | Common seasonal issues |
|---|---:|---:|---:|---:|---:|---:|
| Training | 94 | 92 | 92 | 76 | 76 | 74 |
| Validation | 26 | 24 | 24 | 8 | 8 | 6 |
| Calibration | 22 | 20 | 20 | 4 | 4 | 2 |
| Final test | 22 | 20 | 20 | 4 | 4 | 2 |

The seasonal test results have only four targets per horizon, and the common-seasonal comparison only two issues. They are descriptive diagnostics, not a basis for selecting a winner or asserting seasonality. The main results retain the full persistence comparison. Never compare a model's error on the seasonal subset with a baseline error on the full cohort.

Each report identifies dataset/source, session, species/environment, input configuration, horizon, partition, cohort and model/seed. The present release has one source/session/environment group. If groups are added later, each needs its own result table; larger groups cannot hide poor performance in smaller ones through one pooled headline.

## Point-forecast metrics

For `n` valid matched predictions in a named cohort, define `e_i = forecast_i - observed_i`. The observed value is the referenced hourly DO summary in mg/L.

| Metric | Definition | Interpretation |
|---|---|---|
| MAE | `sum(abs(e_i)) / n` | Primary error measure, mg/L |
| RMSE | `sqrt(sum(e_i^2) / n)` | Error measure with greater weight on large errors, mg/L |
| Mean signed bias | `sum(e_i) / n` | Positive means overprediction, negative means underprediction, mg/L |
| MAE skill vs persistence | `1 - MAE_model / MAE_persistence` | Positive is improvement on the identical matched cohort |

MAE and RMSE use their standard physical-unit definitions; [FPP3 §5.8](https://otexts.com/fpp3/accuracy.html) distinguishes genuine held-out forecasts from fitting residuals. Bias uses the explicitly declared forecast-minus-observation sign here. No R-squared value becomes per-prediction confidence, and percentage error is not the primary measure.

Every metric includes its actual sample count. If `n = 0`, report no score and the reason. If persistence MAE is zero, skill is undefined: report null with `baseline_zero_error`, without adding an arbitrary denominator offset. Report the raw errors and paired absolute-error differences alongside aggregate scores so a small improvement cannot conceal a large error on one target. Training errors are fitting diagnostics and do not establish forecast accuracy.

Before any scoring, join predictions to windows by `window_id`, not row order. Reject duplicate or unknown IDs and mismatched configuration, horizon or issue/target times. Convert outputs back to physical units using training-fitted transforms. Preserve failed/non-finite outputs as failures; never repair a forecast using the observed target. Any output constraint or clipping rule must be selected during development and recorded before final testing.

## Coverage, missing predictions and subgroup diagnostics

Each cohort report includes expected windows, finite predictions, failures, abstentions and prediction coverage `finite / expected`. Missing target coverage is already addressed by the frozen dataset and is not a reason to shrink the forecast denominator further. A model with incomplete primary-cohort predictions can have conditional error diagnostics, but does not qualify for model ranking. Common-success subsets are clearly labeled diagnostics and cannot replace the expected cohort to make a model appear more accurate.

The relevant lower-DO diagnostic is defined before scoring: compute the linearly interpolated 10th percentile of the **100 distinct training DO bins**, then freeze it. Interpolation uses the sorted sample position `(n-1)*0.1`. Report target errors where observed DO is at or below this threshold, with counts and prediction coverage, separately by horizon. The threshold is not computed in this preparation step and cannot be chosen from validation or test errors. Duplicate targets across horizons/configurations do not receive extra weight when defining it.

This is a relative lower-tail diagnostic, not a species safety threshold or hypoxia-event definition. No independently established event labels, species/environment thresholds or adequate event evidence exist in the selected pilot. Sensitivity, specificity, event precision/recall, warning lead time and disease/mortality accuracy are therefore unsupported here. A zero-sized lower-tail test subset is reported as no evidence, not perfect performance. A later event benchmark must first register threshold evidence, minimum duration, event deduplication, observation cadence and warning-to-event matching rules.

## Model selection and the final test

Training fits model parameters and learned preprocessing. Validation selects model family, feature configuration, hyperparameters and stopping rule using complete-cohort MAE, separately for each horizon. The one-hour result is primary; a favorable three-hour result cannot replace it after the fact. If validation MAE is exactly tied, prefer the simpler model using the recorded parameter count, with measured CPU latency as a further tie-break. Search settings and trial limits are registered before fitting rather than expanded in response to test results.

Stochastic candidates use seeds **17, 29 and 43**. Validation selection uses mean seed MAE; reports show each seed and the mean/range of MAE/RMSE. Seed 17 is the predeclared primary artifact. It is not selected as the most favorable seed, and the three replicas do not automatically form an ensemble. Seed variation describes optimization variability, not independent environmental sampling or a prediction interval.

After development choices are locked, the reserved calibration period may support optional diagnostics for that fixed model. It cannot refit the point model. Perform the final test once for the locked model/settings and predeclared replicas, reporting all results without choosing the best test seed. No online parameter fitting or residual updates are part of this frozen experiment. A result-driven redesign requires a new development protocol and an honestly disclosed evaluation history, not repeated selection on the same final test.

The short dependent test record does not justify ordinary independent-sample significance claims or an IID bootstrap confidence interval. Report counts, per-target errors and descriptive variability. This protocol does not establish a statistically reliable performance margin across farms or seasons.

## Optional interval diagnostics

Interval release remains deferred under the partition policy. If exploratory central 80% or 90% intervals are examined after point-model selection, their method and settings are fixed without test outcomes and any calibration uses the reserved calibration observations only. A nominal level is a target to assess, not achieved reliability. [FPP3 §5.5](https://otexts.com/fpp3/prediction-intervals.html) describes prediction intervals and the assumptions behind particular constructions; this protocol adopts no automatic normal-error or independent-residual guarantee.

For each nominal coverage `c`, report on the same expected cohort:

- Empirical coverage: `count(lower_i <= observed_i <= upper_i) / n`.
- Mean width in mg/L: `mean(upper_i - lower_i)`.
- Fractions below the lower bound and above the upper bound.
- Coverage gap in percentage points: `100 * (empirical_coverage - c)`.
- Expected and finite valid interval counts, missing/invalid interval counts, nominal level, horizon, source/session and calibration sample count.

Bounds must be finite and ordered. Crossed bounds are invalid, not silently reordered after observing targets. Conditional metrics on valid intervals retain a coverage-of-predictions denominator report and do not qualify as complete-cohort results. Calibration-period scores are diagnostic rather than independent confirmation. Twenty to twenty-two dependent calibration examples and a similarly short test cannot support a reliable field-confidence claim. Forecast intervals, input-quality metadata and probabilities of biological events remain separate concepts.

## Prediction-result and resource records

A later scoring run records run/model version, source and supervised/split manifest hashes, configuration, seed, window ID, issue/target times, horizon, physical-unit point prediction, status and failure/abstention reason. Optional intervals have explicit nominal levels and lower/upper columns. Target values are resolved from the frozen observation IDs; models do not supply their own evaluation truth. Result files remain traceable to the exact dataset, settings and model artifact.

Accuracy is reported alongside resource measurements. On named CPU hardware, record OS, runtime/library versions, thread settings, batch size, artifact size, parameter count and memory. Separate fresh-process loading/first-prediction time, warm model-only latency and preprocessing-plus-model latency. For warm timing, use at least 20 warmups and 100 timed single-window repetitions, then report median and p95; record batch throughput separately at batch size 32. Use representative development inputs and identical settings across candidates. Memory reports include baseline and peak process memory; fresh-process cold-start results include individual trials rather than one unqualified average. Numerical resource budgets and promotion requirements are task 15.

## Reproduce the evaluation index

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_evaluation_plan -v
.\.venv\Scripts\python.exe -m ml.data.evaluation_plan --output Datasets/processed/oman-evaluation-new-run
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

Completed output: `Datasets/processed/oman-evaluation-plan-2026-11-07/`. `evaluation_index.csv` stores baseline reference IDs and cohort membership. `cohort_counts.csv` makes the expected denominators explicit. `evaluation_manifest.json` records the policy, source/session grouping, complete input/output hashes and checks. No threshold, baseline prediction, trained model, accuracy metric or interval is computed by this command.

Six focused tests check latest-observation persistence references, horizon-aligned seasonal references, partition isolation, imputed-reference rejection, matched common-horizon cohorts and future-reference rejection. The command verifies the entire supervised hash chain, validates each indexed window and checks that all expected rows remain present. It refuses an existing output directory. Acceptance criteria and final prepared-release verification remain separate readiness tasks.

The subsequent [pilot acceptance criteria](release-criteria.md) record provisional accuracy/resource gates, input availability and explicit claim boundaries before model comparisons. They do not represent achieved model results or field qualification.
