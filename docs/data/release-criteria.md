# Pilot acceptance criteria and forecast availability

Version: [oman-do-pilot-criteria-v1](release-criteria.json), 2026-11-07. These criteria are recorded before model comparisons. They define qualification for a small research point-forecast pilot using the [evaluation protocol](evaluation-protocol.md), not permission to operate a fish farm or claim field reliability. No new model has been fitted, evaluated or qualified.

## Status and basis of the targets

The numerical error and resource limits below are **provisional engineering targets** adopted for this pilot. No farm operator has supplied an acceptable forecast error, verified sensor-error budget or intervention requirement. The limits are not inferred from biological safety thresholds, published scores, final-test outcomes or an assumed sensor precision.

They make the intended tradeoff explicit: bound physical-unit error, require a measurable improvement over a simple baseline, retain complete prediction coverage and keep a compact CPU artifact. Meeting these limits would establish only that a model passes this declared pilot comparison. The short, dependent recording and unresolved measurement accuracy remain claim limits even after a numerical pass.

Targets may be revised through a separately versioned, explained protocol change before model fitting/test access when better operational evidence arrives. A failed comparison is not a reason to lower the bar silently or keep selecting on the same test. Broader field qualification requires additional independent recordings and measurement validation.

## Accuracy and coverage gates

Apply the following gates separately on the **complete validation and final-test cohorts** for each claimed configuration/horizon. Validation identifies an eligible candidate; the locked candidate's final test confirms or rejects pilot qualification. The target is the source-reported, coverage-gated hourly DO summary, in mg/L.

| Criterion | Primary +1 h | Optional +3 h |
|---|---:|---:|
| MAE | ≤ 0.50 mg/L | ≤ 0.75 mg/L |
| RMSE | ≤ 0.75 mg/L | ≤ 1.00 mg/L |
| Absolute signed bias | ≤ 0.20 mg/L | ≤ 0.30 mg/L |
| MAE skill vs persistence | ≥ 0.05 (5% relative MAE improvement) | ≥ 0.05 |
| RMSE vs persistence | No greater than persistence RMSE | No greater than persistence RMSE |
| Finite valid prediction coverage | 100% of the expected cohort | 100% of the expected cohort |

Persistence comparisons use identical issue/target IDs and the same cohort. The seasonal subset cannot replace the primary cohort. If persistence MAE is zero, the improvement gate is unavailable; report the baseline and no learned-model improvement qualification rather than adding a denominator offset.

For a stochastic candidate, every registered replica must have complete prediction coverage. Apply the accuracy/improvement gates to primary seed 17 and to arithmetic means of the per-seed MAE, RMSE, absolute bias and skill for seeds 17/29/43. Average absolute per-seed biases rather than allowing opposite signed biases to cancel. Report all replicas and their variability; do not replace the primary artifact with the best test seed. Deterministic ridge results use the corresponding single fitted artifact.

The one-hour horizon is mandatory. A passing three-hour model cannot replace a failed primary task. A primary-only qualified artifact may omit the three-hour output; claiming both horizons requires both to qualify separately. Each input configuration qualifies separately. A claim of benefit from additional sensors also requires paired improvement over DO-only; beating persistence alone does not demonstrate added sensor value.

Lower-DO diagnostics, per-target errors and prediction failure counts are mandatory reporting fields. A missing lower-tail subgroup is recorded as unsupported evidence, not a successful safety result. Those diagnostics do not establish low-oxygen-event detection or replace the full-cohort gates. If no learned candidate qualifies, retain the honest baseline result and research findings; there is no obligation to manufacture an improved-model release.

## Resource and search limits

Use the timing procedure in the evaluation protocol, on a CPU host declared before fitting and retained for comparisons. Record processor, OS, library versions, thread settings, warmups, repetitions and batch size. No GPU acceleration is used for these CPU measurements.

| Resource criterion | Provisional limit per selected configuration/horizon artifact |
|---|---:|
| Warm model-only single-window p95 | ≤ 100 ms |
| Warm preprocessing-plus-model p95 | ≤ 150 ms |
| Fresh-process model load plus first prediction | ≤ 15 seconds, each recorded cold-start trial |
| Selected artifact including required transforms/configuration | ≤ 10 MiB |
| Peak total process resident memory | ≤ 1,024 MiB |
| Batch throughput, batch size 32 | ≥ 100 windows/second |
| Trainable parameters | ≤ 10,000 |

Peak process memory includes the loaded runtime, not merely the weight array. Record baseline memory too. Artifact size includes the fitted scaler and other required transforms, while dependency/runtime distribution size is reported separately. Model-only and preprocessing-plus-model timings are distinct from HTTP/database latency. No resource measurements have been performed for a new model, so none of these gates has passed yet. These budgets are not portable service-level promises.

Register at most **four settings per learned family/configuration/horizon**, using the fixed stochastic seeds. Each stochastic fit has at most **100 epochs** and **600 seconds**; its stopping rule is fixed before fitting. Ridge has no epoch budget but retains the per-fit wall limit. Reaching a limit is a logged trial outcome, not permission to hide the run or expand the search after test access. The bounds keep the small validation set from supporting an open-ended search. Model architecture and exact settings are implemented and recorded during the later model phase.

## When inputs permit a new issue

Historical input readiness and model qualification are different checks. A complete history can support a prospective issue before any future measurement exists; future target coverage is required for retrospective scoring, not for issuing a forecast.

The readiness checker applies to the prepared pilot's admitted source/session and declared feature configuration. It checks six complete historical hourly bins in their recorded order, with no duplicates or borrowed partition history. All required values must be finite, within the broad source-screening bounds and aggregation-eligible. No preparation-imputed history is admitted. Broad numeric bounds remain screening rules, not biological limits.

| Input requirement | Limit |
|---|---|
| History | Exactly 6 adjacent hourly bins, ending at the issue time |
| Minute support | At least 3 valid readings for a supported minute |
| Hour coverage | At least 54 supported minutes in every required channel/bin |
| Observation gaps | At most 180 seconds, including bin edges |
| Freshness within each bin | Last valid reading no more than 60 seconds before that bin ends |
| New-issue scheduling allowance | Request at or after issue time and at most 60 seconds later |
| Latest raw-reading age at request | At most 120 seconds, including bin-end age plus issue delay |

The scheduling allowance is provisional: real ingestion delays are unobserved. Historical bins are assessed at their respective ends, so an old but valid member of the six-hour sequence is not rejected simply because it predates the issue. The most recent bin additionally satisfies the request-time age check. Boundaries are inclusive: an age of exactly 60 seconds at bin end is admitted; 61 seconds is not.

DO-only readiness depends on DO. Missing pH or temperature blocks the multivariate configuration without silently blocking or changing the DO-only configuration. A caller cannot silently switch the feature configuration or model artifact: any fallback is explicitly identified and must itself be qualified. Valid DO zero remains a measured value; it is not filled, discarded as missing or converted into an automatic intervention decision.

Cached forecasts retain their original issue and target times. Displaying one later does not create a new issue or refresh its input provenance. A new forecast request outside the scheduling allowance is unavailable; it cannot carry the last accepted bin forward under a fresh timestamp.

## Unavailable reasons and output handling

The preparation helper `check_history` returns `inputs_ready` and explicit reason codes, with no prediction or safety status. Reasons include unsupported configuration/context, missing metadata, insufficient history, duplicate observation identity, cross-partition history, unknown/mismatched time support, imputed history, invalid required measurement, invalid quality metadata, insufficient coverage/readings, excessive gaps, stale sensors, a future issue or a stale issue request. Nullable missing values fail closed rather than being accepted by a missing-skipping comparison.

Any later inference adapter also needs to reject an absent/unqualified model, model/transform/schema mismatch, unsupported horizon and non-finite or negative DO prediction. It must not hide errors with a normal-looking forecast, a benign risk label or a fabricated confidence percentage. An output constraint can be part of a model only if registered before evaluation; post-test clipping is not a repair strategy.

The checker uses trusted, hash-verified prepared aggregates and their metadata. It does not ingest arbitrary devices, verify new sensor units, measure transport delay, qualify models or implement an API. Those integration responsibilities require separate implementation and tests. Diagnostic rapid-change/plateau flags are not new automatic rejection rules; the supervised feature and parent-availability restrictions remain in force.

## What a qualified pilot can claim

The permitted claim is narrow: the named configuration/horizon met the recorded point-error, baseline-improvement, completeness and CPU gates on the disclosed chronological tilapia tank pilot, with exact counts and measurement limitations. The model artifact, transforms, source/split/window hashes, seed, hardware, trial settings and per-target predictions must make that result reproducible.

Passing this comparison does not establish independent-site or cross-species accuracy, shrimp validation, calibrated field confidence, disease/mortality prediction, treatment recommendations or autonomous aeration control. Risk thresholds in the existing application do not become scientifically validated through this DO experiment. Forecasts summarize expected measurement behavior; a model error metric does not prescribe an intervention.

Interval release remains deferred. Exploratory 80%/90% intervals may have diagnostic coverage/width reports under the evaluation protocol, but no reliable confidence claim is authorized. Operational alert thresholds need separate species/environment evidence and expert requirements. No universal fish/shrimp threshold is invented to complete this milestone.

## Readiness audit and reproduction

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_release_readiness -v
.\.venv\Scripts\python.exe -m ml.data.release_readiness --output Datasets/processed/oman-criteria-new-run
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

Authoritative output: `Datasets/processed/oman-criteria-2026-11-07-v2/`. The unsuffixed directory is an intermediate local audit before nullable-input hardening and the explicit replica/bias wording; it is not the authoritative criteria record. The command refuses an existing output directory and verifies the evaluation/supervised/source hash chain before and after the audit.

`readiness_index.csv` records each bin/configuration's historical-input readiness, simulating a request exactly at issue time. `readiness_counts.csv` summarizes it. `criteria_manifest.json` captures the criteria snapshot, hashes, counts and explicit not-assessed qualification status. It does not evaluate prediction errors or resource performance.

There are 376 issue/configuration rows and **336 input-ready rows**. For each configuration, training/validation/calibration/test contribute 95/27/23/23 ready issues; the first five bins of each period lack the six-bin history. These are potential issues without future-label checks, so the counts exceed the 164/156 retrospective examples per configuration/horizon. They are not live uptime or model availability measurements.

Ten focused tests cover historical-only readiness, inclusive delay/age boundaries, future issues, incomplete/ordered history, optional sensors, coverage/gaps, missing and nullable metadata, context/partition isolation, imputation, duplicates and valid-zero preservation. No model is trained, no score is computed and training approval remains false. Final prepared-release reproduction and verification remain task 16.
