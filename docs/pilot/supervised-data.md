# Supervised inputs, targets and window indices

Version: [oman-do-supervised-v1](supervised-contract.json), 2026-11-07. This contract turns the [frozen tank partitions](partition-review.md) into explicit observation references for new forecasting experiments. It defines data access and indexing; it does not fit a model or a learned transformation. Training approval remains false until evaluation, acceptance criteria and release verification are complete.

## Prediction task

An issue occurs at the end of the latest completed hourly input bin. The historical window contains six adjacent hourly bins, ordered oldest to newest. Every input and every future DO bin through the target belongs to the same tank session and partition.

For an issue at 10:00 UTC:

- The history covers `[04:00, 10:00)`, using hourly summaries available at 05:00, 06:00, 07:00, 08:00, 09:00 and 10:00.
- The one-hour target summarizes `[10:00, 11:00)` and becomes available at 11:00.
- The three-hour target summarizes `[12:00, 13:00)` and becomes available at 13:00. It is not an average over all three future hours.

The three-hour example also requires eligible DO observations in the intervening bins ending at 11:00 and 12:00. Those future observations establish retrospective label coverage only; they are not model inputs. Future optional sensor availability does not gate the target. The source has no receipt timestamps, so availability assumes observations were accessible at their recorded times and aggregates at bin end. Actual transport delays are unknown, not measured as zero.

## Numeric input and target schema

| Configuration | Feature order for each historical bin | Input matrix shape |
|---|---|---|
| `do_only` | `do_mgL` | `(6, 1)` |
| `do_temperature_ph` | `do_mgL`, `temperature_c`, `ph` | `(6, 3)` |

DO is in mg/L, temperature in °C and pH on its pH scale. The chronological axis comes first; the column axis uses the exact order above. Timestamps align the sequence and establish availability; they do not automatically become additional numeric features.

Each horizon-specific target is one scalar `do_mgL` value. A joint two-horizon experiment resolves targets in the contract's order `[1, 3]`, giving two values rather than a three-step trajectory. Comparisons between separate and joint models must use an explicitly matched issue set.

All values are the [coverage-gated hourly summaries](aggregation-policy.md): means of supported minute medians from source-reported measurements. They are neither instantaneous meter readings nor independently verified calibration references. The preparation path performs no interpolation or imputation. Missing required input bins and missing future DO coverage remove an example instead of generating substitute values.

Runtime imputation models and the application's existing inference cascade are separate from this research-data contract. Their predictions, risk states and imputed records are not labels or covariates for these new experiments.

## Quality metadata and feature availability

The observation export retains these per-channel fields for historical inspection and gating: supported-minute count, valid/invalid reading counts, last-reading age at bin end, largest in-bin gap, zero-review count and rapid-change-review count. They can be calculated using observations available by the corresponding bin end. The default numeric matrices contain only the measurement columns above. Any later use of metadata as features needs an explicit experiment record and the same issue-time checks.

Review counts do not automatically reject a bin. A rapid-change annotation can reference the previous raw reading, including one before a partition boundary. It is retained as diagnostic metadata, not a split-independent predictor. Any new metadata feature must declare and check its parent support against the permitted window and partition, or recompute it from that support; availability alone does not establish observation disjointness.

**Exact-plateau flags remain diagnostic-only.** The upstream audit identifies a sufficiently long equal-value run and flags the full run. Early flags can therefore depend on readings later than an issue time. They are excluded from supervised observation exports and feature matrices. The audit itself remains available for source review, but its full-run annotations cannot silently become causal predictors or target filters.

Neither future observations nor future coverage/quality indicators enter the matrix. Disease/risk labels, post-outcome interventions, future observed weather, predicted nitrogen and arbitrary extra columns are outside the feature allowlist. The dataset's retrospective target-availability filter is disclosed as sample selection, not information available to a live forecaster.

## Exported records

### Observations

`observations.csv.gz` contains one row per frozen hourly bin: observation ID, session, partition, interval start, availability time, source hash, lineage group, the three measurement values, their eligibility flags and permitted quality metadata. `value_kind` records `aggregate_of_source_reported_measurements`; `preparation_imputed` is false. These annotations describe preparation, not a guarantee of sensor accuracy.

Observation IDs match the partition freeze. The freeze manifest and raw-parent mapping resolve each bin to source-row evidence; this export does not create a new independent measurement by copying an aggregate. Values for all partitions reside in one reference table, while window IDs determine which historical rows a particular example may access.

### Horizon-specific windows

Each line of `windows.jsonl` describes one example:

| Field | Meaning |
|---|---|
| `window_id` | Stable identifier derived from contract version, configuration, ordered support IDs, partition and session |
| `comparison_id` | Shared key for the same issue/horizon across input configurations |
| `session_id`, `partition`, `configuration` | Context and permitted feature configuration |
| `issue_time`, `horizon_hours` | Forecast issue and elapsed-hour horizon |
| `input_observation_ids` | Six ordered historical references, all available by the issue |
| `future_do_observation_ids` | Ordered retrospective DO coverage through the target; labels/eligibility only |
| `target_observation_id` | Last future DO bin, supplying the scalar target |
| `target_available_at` | Target interval end and assumed availability |
| `target_interval_start`, `target_interval_end` | Exact one-hour target support, start inclusive/end exclusive |

`input_matrix` in `ml/data/windows.py` resolves a verified index into the measurement columns in the declared order. It performs no fitting or scaling. It is a preparation helper for complete historical examples, not a live inference endpoint: it also validates the recorded target references. Deployment input validation needs its own interface without requiring future labels.

### Common issues for paired experiments

`paired_issues.jsonl` links the one-hour and three-hour window IDs for issues with both targets available, separately for each input configuration. It does not fill a missing horizon or duplicate an issue to balance counts. `comparison_id` permits matching the same horizon between DO-only and multivariate experiments.

The current export verifies that both input configurations share the same issues and target IDs. Generic indexing still treats optional historical sensors separately: missing pH can remove a multivariate example without removing a DO-only example, while missing future pH does not remove either label. Changed support in this frozen release fails the recorded-count check and requires a reviewed data/policy revision.

## Counts and dependence

The export contains **188 observation rows**, **640 horizon-specific window records** and **312 joint-horizon issue records**. The latter two totals include both alternative input configurations and are not counts of independent environmental trials.

| Partition | +1 h windows per configuration | +3 h windows per configuration | Common issues per configuration |
|---|---:|---:|---:|
| Training | 94 | 92 | 92 |
| Validation | 26 | 24 | 24 |
| Calibration | 22 | 20 | 20 |
| Final test | 22 | 20 | 20 |
| Total | 164 | 156 | 156 |

All counts match the partition freeze. Repeated targets across horizons/configurations remain paired observations within their partition; overlapping historical windows remain dependent. No target identity crosses a partition. The short tank recording supports a limited chronological point-forecast pilot, with interval reliability still deferred. It does not provide independent-site, shrimp or general fish validation.

## Learned preprocessing and permitted use

Physical-unit summaries and the explicit indices are exported unchanged. There is no scaler, learned imputer, feature selector, synthetic sample generator or fitted predictor in this preparation step.

During model development, training alone fits parameters and any learned transforms. Validation chooses model and feature settings. The reserved calibration period can support frozen-model diagnostics under the partition policy; it cannot refit the point model. Final-test labels are used after choices are fixed, not for preprocessing statistics or model selection. Full-dataset normalization would violate this contract even if no labels were passed to the scaler explicitly.

## Reproduction and verification

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_windows -v
.\.venv\Scripts\python.exe -m ml.data.windows --output Datasets/processed/oman-supervised-new-run
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

Default inputs are the authoritative `oman-partitions-2026-11-07-v2` freeze and [supervised contract](supervised-contract.json). `--partitions` can select a separately reproduced matching freeze. Completed output: `Datasets/processed/oman-supervised-2026-11-07/`.

Alongside the three observation/index files, `window_counts.csv` and `paired_issue_counts.csv` summarize support. `supervised_manifest.json` records the contract snapshot, partition version, input/output hashes, counts and verification results. The command checks all upstream freeze inputs and artifacts before use, validates every window, checks configuration pairing and count agreement, and checks inputs again before export. It refuses an existing output directory.

Eleven focused tests cover reference alignment, feature order and shape, session/partition boundaries, missing historical/future measurements, gaps, imputed targets, future-value isolation, unapproved columns, forged references/target intervals, and stable pairing. Raw files, prior outputs, trained artifacts and application code remain unchanged. Evaluation specification, release acceptance criteria and final reproducibility checks remain the next preparation tasks.

The subsequent [evaluation protocol](evaluation-protocol.md) registers baseline references and exact comparison cohorts against these indices, along with metric definitions, coverage reporting and fixed model-selection rules.
