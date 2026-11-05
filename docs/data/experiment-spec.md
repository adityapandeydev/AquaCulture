# First forecasting experiment: dissolved oxygen

Version: 0.1 — 2026-11-05. Status: task definition complete; data eligibility and final evaluation settings remain under review.

The [initial literature review](literature-review.md) records the primary evidence, reporting inconsistencies and methodological limits behind the preparation decisions. No published architecture or score is adopted as a guaranteed result.

## Purpose

Develop new forecasting models that estimate future dissolved oxygen (DO), compare their accuracy and computational cost, and quantify uncertainty on measurements not used to select the model. The first experiment establishes a reliable process that can later extend to other water-quality targets and additional fish/shrimp environments.

Existing LSTM artifacts are references only. New models will be trained from scratch on the prepared data. Reuse of pretrained weights or transfer learning, if investigated later, will be a separately named experiment.

## First prediction task

| Item | Specification |
|---|---|
| Target | Future measured dissolved oxygen, in verified mg/L |
| Required input | Historical measured DO with timestamps and quality information |
| Extended input | Historical water temperature and pH, admitted only where their units and quality are defensible |
| Initial cadence | Hourly candidates, subject to coverage and session review |
| Candidate horizons | 1, 3 and 6 hours; each horizon is evaluated separately |
| Candidate history | 6, 12 and 24 hours, subject to contiguous valid coverage |
| Issue time | The time at which all observations in the input window would have become available |
| Output | Issue time, target time, horizon, predicted DO, model version, input-quality summary and, after validation, prediction interval |
| Evaluation unit | Source/site/session and prediction horizon; results also identify species and farming environment when known |

These are an experiment search space, not promises that every combination is feasible. The data-readiness review will select a supported subset before training. The 6-hour window is the shortest initial candidate; longer history is a comparison, not an automatic requirement. A daily seasonal baseline requires at least the relevant previous-day observations even when a candidate predictive model uses shorter history.

If hourly preparation removes too much usable variation or recording coverage, a separate subhourly specification may replace it. A 30-minute forecast cannot be inferred from hourly targets, and sample steps will never be relabeled as hours.

Temperature and pH forecasting are later target extensions. Nitrogen forecasting requires verified units and chemical basis before it enters this experiment family. Disease, mortality, growth and automatic aerator control are outside the first experiment.

## Input configurations

Two configurations keep sensor availability separate from model quality:

1. **DO history:** the minimum configuration, suitable for establishing whether additional sensors improve forecasting.
2. **DO, water temperature and pH history:** a multivariate configuration using the same eligible target observations as the minimum configuration for paired comparisons.

Each configuration receives missingness, measurement age and quality information where appropriate. No configuration requires estimated ammonia or nitrate merely to produce a DO forecast. Additional channels or known operational events need a documented availability and measurement review before inclusion.

Comparisons between configurations use a common evaluation subset. Coverage over the full candidate dataset is reported separately so a model evaluated on an easier, more complete subset cannot appear better through sample selection alone.

## Time and target semantics

An hourly aggregate over `[09:00, 10:00)` is available at 10:00. For a forecast issued at 10:00, the one-hour-ahead aggregate covers `[10:00, 11:00)` and is labeled 11:00. It is an interval-average target, not an instantaneous reading at 11:00. Minimum within-bin DO and its timing remain available for a later event-focused evaluation where sampling supports them.

The preparation release will specify minimum within-bin observation coverage, permissible gaps and target availability. Empty or inadequately observed future bins are not valid labels. A filled target is not silently accepted as measured ground truth.

Records remain inside their source, site and session. A session with an unknown timezone can support an elapsed-time task if its local clock is reliable, but it cannot justify cross-site clock alignment or geographic time-of-day features without additional evidence. Received-time information is retained when present; otherwise retrospective experiments assume the recorded observation was available at its timestamp and disclose that assumption.

## Fish and shrimp evaluation groups

The long-term scope includes fish and shrimp. The following are candidate groups, not validated product claims:

| Group | Current candidate | Prerequisite and claim limit |
|---|---|---|
| Nile tilapia, pond/offline recording | Oman raw offline file | Resolve recording periods, calibration, gaps and the study-window discrepancy. |
| Nile tilapia, controlled tank/live recording | Oman raw live file | Keep the tank environment distinct from the pond. A later session is not automatically an independent farm or site. |
| Other fish/aquaponics | Local O1D2 files; Colombia workbook | Source identity, units, shared sequences and interpolation need review. Unknown pond identity is not evidence of multiple independent ponds. |
| Shrimp, intended brackish-water setting | Supplied shrimp-buoy workbook | Establish channel units, field-versus-calibration sessions and exact species. The publication context does not establish species for every spreadsheet row. |
| Freshwater prawns | No eligible forecasting source established | Unsupported until an appropriate recording is acquired and reviewed. |

Water chemistry/reference tables and timestamp-free quality-classification data are not DO forecasting benchmarks. Related local variants remain in one lineage group. In particular, Pond1/Pond2 and the O1D1/O2D3 variants cannot be assigned to opposing training/test groups without resolving their shared records.

Initial models may be source-specific or pooled across eligible development groups. Both choices are experimental. Pooling does not grant cross-species validity: fish-to-shrimp transfer requires a separately held-out, eligible shrimp evaluation, and the reverse requires eligible fish evaluation. A common software interface is possible even when separate models are needed.

## Accuracy and generalization

The later model-development phase will compare:

- Persistence and, where supported, daily seasonal persistence.
- Compact models using historical values, trends and causal rolling summaries.
- Small sequence architectures trained from scratch, with additional complexity justified by measured improvements.

Every candidate uses the same frozen partition rules and eligible targets. Training includes only development observations and labels; model choice and uncertainty calibration use the designated development/calibration periods. The final test is reserved for evaluation after choices have been fixed.

Reports will include MAE and RMSE in mg/L per horizon, improvement over the appropriate baseline, valid-example counts, coverage, and source/session results. Independently held-out sites and species are reported only when those partitions exist. Low-DO and rapid-change subsets need definitions fixed using domain evidence and development data, not chosen after seeing test errors.

The experiment aims to improve accuracy; no numerical accuracy gain is claimed or guaranteed before the benchmark. Practical error thresholds and release criteria are a separate readiness task and will be set before comparing trained candidates.

## Uncertainty and confidence

The intended uncertainty output is a prediction interval around the measured target. Initial candidates are a central forecast with 80% and 90% nominal intervals, subject to adequate calibration data. Quantile estimates and residual-based calibration are methods to compare later; neither is selected as the winner in advance.

Interval quality is assessed through empirical coverage, width, sample counts and results by horizon/source. Calibration observations must be separated appropriately from model fitting and final testing. Time dependence and domain shifts limit what calibration results establish; very short or sparse recordings may not support a reliable interval claim.

If an online calibration method is tested, residual updates use only targets already observed at that issue time. Frozen-calibration and online-update evaluations remain distinct; delayed multi-hour targets cannot update earlier predictions.

Three different concepts remain separate:

- **Input quality:** whether the measurements are fresh, valid and sufficiently complete.
- **Prediction uncertainty:** the evaluated range of plausible target values.
- **Event probability:** a calibrated probability of a specifically defined threshold event, if the data supports a later event model.

A point model's R-squared is not a per-prediction confidence percentage. An interval crossing a threshold is not automatically a calibrated probability of crossing it. Until calibration is evaluated, the interval is experimental and no reliability score is displayed as established confidence.

## Computational performance

Later benchmarks will measure model artifact size, peak inference memory, cold-start/warmup time, single-window CPU latency and batch throughput. Model-only timing and preprocessing-plus-model timing will be reported separately on named hardware with the same input configuration. Repeated measurements will include median and tail latency.

Training duration and hardware will also be recorded, but a faster training run does not compensate for inadequate forecast quality. The target is a practical CPU inference service; measured resource budgets and tradeoffs will be fixed before model selection. A more complex model must justify its additional cost relative to simpler candidates.

## How this guides cleaning

The preparation pipeline preserves real excursions, source lineage and quality flags. Screening and calibration decisions rely on sensor/measurement evidence rather than making series easier to predict. Shared copies, long gaps, unverified unit conversions, post-event features and future-dependent filling are excluded from the supervised-data contract.

No scaler, learned imputer, feature selector or predictive model is fitted as part of this specification. Those transformations will be fitted on training data only when model development begins.

## Decisions still required before training

- Select eligible source/session/channel combinations with documented measurement and reuse decisions.
- Set final cadence, bin coverage, permitted gaps, history/horizon subset and sample sufficiency requirements.
- Freeze lineage-aware chronological partitions, independent holdouts where possible and a calibration strategy.
- Prepare and verify input/target window indices and release metadata.
- Specify evaluation formulas, practical acceptance thresholds and CPU resource budgets.

The [first release eligibility review](eligibility-review.md) narrows the initial pilot to a six-hour history on the main Oman tank recording, with a primary one-hour horizon. Final partitions, evaluation settings and release verification remain outstanding; this specification does not approve any dataset for training.
