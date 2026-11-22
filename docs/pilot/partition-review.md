# Chronological partitions for the tank pilot

Freeze date: 2026-11-07. Policy: [oman-tank-chronological-v1](partition-policy.json). Scope: the main Oman tank session selected in the [eligibility review](eligibility-review.md). No new model, preprocessing transform or uncertainty method has been fitted.

The split assigns the 188 eligible hourly bins to four consecutive periods. Every candidate example's complete historical window and future DO observation path must remain inside one period. The resulting observation-disjoint split supports a small chronological point-forecast pilot. Statistical sufficiency for broader claims is not established, and interval reliability remains deferred.

## Frozen periods

All times below are UTC. Periods describe the underlying observation intervals and are half-open: a period starting at 11:00 includes the bin `[11:00, 12:00)`, not the bin ending at 11:00. Each hourly bin's availability is its end time. The source's documented GMT+4 offset is applied before the split; local timestamps are not relabeled as UTC.

| Partition | Observation interval, start inclusive / end exclusive | Hourly bins | Permitted use |
|---|---|---:|---|
| Training | Apr 2, 07:00 → Apr 6, 11:00 | 100 | Fit model parameters and learned preprocessing |
| Validation | Apr 6, 11:00 → Apr 7, 19:00 | 32 | Select model, features, hyperparameters and stopping rule |
| Calibration | Apr 7, 19:00 → Apr 8, 23:00 | 28 | Optional interval diagnostics after the point model is fixed |
| Final test | Apr 8, 23:00 → Apr 10, 03:00 | 28 | Final evaluation after all development choices are fixed |

All dates are in 2026. The source is publisher-declared Nile tilapia in a controlled 180 L tank. The primary session is `oman-2cbad87a2dbd2a81d6e1`; the raw file SHA-256 is pinned in the policy.

The allocation gives training just over half the record and reserves three later periods for distinct uses. It favors inspectable development and held-out results over maximizing fitting rows. The boundaries were fixed using the reviewed recording support and task requirements, without training models, comparing errors or optimizing a split against target values. They are experiment choices, not evidence that roughly four days of training covers seasonal or farm variation.

The final-test observations appeared in source-wide metadata, quality diagnostics and range summaries before this freeze. They have not been used for fitting, new-model error comparisons, hyperparameter selection or calibration. This is a holdout for the new forecasting pilot, not a claim that nobody has ever inspected the raw recording. Further diagnostic inspection must not become a reason to move boundaries after observing forecast errors.

## Boundary rules and example counts

The supported history is six completed hourly bins. A one-hour forecast issued at 10:00 uses the six input bins ending at 05:00 through 10:00, then targets the DO summary over `[10:00, 11:00)`. For a three-hour forecast, DO must also be observed in the intervening hours through the target bin ending at 13:00. Optional future temperature/pH observations are not inputs or eligibility requirements.

Every input bin, intervening future DO bin and target bin must belong to the same partition and session. The first six bins of a period build its initial history; they cannot borrow readings from the preceding period. A fitting label cannot extend into validation, calibration or test. No random split or shuffled-window split is used.

Both DO-only and DO/temperature/pH configurations have identical support. Counts below apply to each configuration separately; adding them together would count the same observation periods twice.

| Partition | 1-hour horizon | 3-hour horizon |
|---|---:|---:|
| Training | 94 | 92 |
| Validation | 26 | 24 |
| Calibration | 22 | 20 |
| Final test | 22 | 20 |
| Total | 164 | 156 |

Before partitioning the counts were 182 and 180. Strict containment rejects 18 and 24 boundary-crossing examples respectively. These are horizon-specific counts; a model returning both horizons for a common issue set uses the smaller paired issue set. The later supervised-window contract will materialize and verify those indices rather than assuming that different horizons automatically use identical issues.

No additional time embargo is imposed beyond rejecting all cross-boundary support. This separates source observations across partitions, but does not remove temporal dependence between nearby water conditions. Examples within a partition also overlap heavily. The 22 final-test targets at one-hour horizon are not 22 independent environmental trials.

Daily seasonal persistence needs older observations than the six-hour predictive input contract. Its feasible subset and any permitted history access require an explicit baseline rule in the evaluation protocol; these counts do not establish that a daily baseline can be compared on every example.

## Observation identity and lineage checks

The export assigns each canonical hourly bin a stable observation ID derived from its raw source hash, session ID, aggregation-policy version and availability time. All 188 IDs are unique and belong to exactly one partition. This disjoint set includes every possible DO target bin, so no target observation can appear in two partitions. Different horizons or input configurations can share targets within a partition for paired comparisons; that is not additional independent evidence.

Raw parents are recorded as `(source_sha256, source_row)` identities. The selected hourly support contains **101,666 raw source rows**. They map to exactly one hourly bin and one partition; none is reused across partitions. A reading at an exact partition boundary belongs to the following hour, while the preceding bin ending at that boundary remains in the earlier period. Partial hours outside the selected support are not included.

The freeze also verifies the source/session inventory, quality and aggregation input hashes, and the exact prepared artifacts recorded by the task-11 eligibility review. Data or selection changes since that review fail closed. Unreviewed sources, excluded sessions, duplicate hourly labels, missing frozen support, nonmatching configurations and empty partition counts are rejected.

All periods share `oman_single_study_unverified_site_independence`. Shared study lineage is disclosed and permitted for this chronological evaluation because the canonical observation identities and support intervals are disjoint. It is not an independent-site holdout. The short pond groups, other files from this study and related publisher aggregates are not additional fitting or held-out data in this release. The other species/source exclusions remain in force.

## Calibration and claims

The calibration period is reserved so uncertainty diagnostics cannot quietly reuse tuning or test targets. It supplies only 22 one-hour or 20 three-hour examples, with overlapping histories and a little over one day of observation support. This is not adequate evidence for a reliable 80%/90% interval claim across sites, species or operating conditions. The policy therefore records interval release as deferred; the primary benchmark is a point-forecast pilot.

If interval diagnostics are explored, they use a point model fixed using training and validation only. They cannot select/refit the point model or use test outcomes. No online residual updates or expanding-window fitting is authorized by this split. A different evaluation regime requires its own policy and verification before results are compared.

The final test is also short and dependent. Its errors will describe this recorded tank period, with counts and physical-unit metrics, rather than establish field readiness. Larger independent recordings remain necessary for the broader accuracy and confidence goals. Numeric screening, hourly coverage and observation-disjoint partitions do not resolve the existing calibration and sensor-noise limitations.

## Reproduce and verify

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_partitions -v
.\.venv\Scripts\python.exe -m ml.data.partitions --output Datasets/processed/oman-partitions-new-run
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

The default inputs are the reviewed November 5 aggregation, timestamp/session inventory and eligibility report. `--prepared`, `--sessions` and `--eligibility` can point to a separately reproduced matching chain. The command refuses an existing output directory; a new run does not replace a freeze.

Authoritative local output: `Datasets/processed/oman-partitions-2026-11-07-v2/`. The unsuffixed directory is an intermediate local run before the explicit task-11 artifact-hash check was added; it is not the authoritative freeze.

- `observation_partitions.csv`: the 188 canonical hourly bins, stable IDs and partition assignments.
- `raw_parent_partitions.csv.gz`: source-row identities and their bin/partition assignments.
- `split_counts.csv`: structural example counts by partition, configuration and horizon.
- `split_manifest.json`: frozen policy snapshot, input/output hashes, row accounting, boundary losses and claim limitations. Training approval remains false.

Eight focused tests cover complete-bin boundary ownership, overlapping/gapped periods, missing support, wrong sessions, duplicate labels, contained histories/targets, missing target coverage, shared observation identity rejection and raw-parent boundary mapping. Full supervised input/target index export remains task 13. This freeze does not train or evaluate a predictive model.

The subsequent [supervised-data contract](supervised-data.md) materializes those horizon-specific indices and common-issue mappings against this freeze, with exact count agreement and additional issue-time feature checks.
