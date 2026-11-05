# Measurement lineage and partition rules

Review date: 2026-11-05. The machine-readable [lineage policy](lineage-policy.json) covers all 11 catalog source groups. It records conservative dependencies; it does not establish physical-site independence or approve a dataset for training.

## Compilation and standalone-file overlap

The review compares the six numeric water channels in the completed first preparation batch: nitrate, pH, ammonia, water temperature, DO and turbidity. Complete vectors are rounded to six decimals. Rows with any missing channel are excluded from this comparison, so shared nulls do not inflate the overlap. Counts retain multiplicity rather than comparing unique values alone.

| Compilation table | Standalone table | Complete compilation vectors | Matching rows, limited by multiplicity in both tables |
|---|---|---:|---:|
| `section_2` | `O1D1/Fish Ponds.csv` | 74,758 | 74,758 |
| `section_3` | `O1D1/Ponds.csv` | 18,055 | 18,055 |
| `section_4` | `O1D1/Ponds1.csv` | 74,724 | 74,724 |

Every complete compilation vector in those blocks is contained in the corresponding standalone table. This is sufficient to reject the blocks as additional independent measurements. It does not establish authorship, source licensing, whether station/time fields were reconstructed, or equality of excluded metadata. Incomplete rows are not declared identical by this test.

The earlier raw-table audit found all 74,758 complete measurement vectors in `Fish Ponds.csv` in both `Ponds1.csv` and `Realtime-env2.csv`. The compilation's related blocks, O1D1 variants and O2D3 table therefore share a conservative lineage group. Other compilation sections remain reference material; grouping the whole workbook conservatively does not claim every section shares a physical origin.

## Ordered and time-aligned evidence

The [aquaponics audit](aquaponics-review.md) strengthens its initial unordered match with 81,215 matching exact recorded-time strings/four-channel vectors across Pond1 and Pond2. Fourteen source-order runs contain at least 100 adjacent rows in both files; the longest has 54,501 rows. These copied channel segments cannot become independent holdouts. Other channels, actual collection origin and gap continuity remain separate questions.

The [Oman review](oman-review.md) found no exact timestamp-plus-three-channel matches between the acquired offline/live files. Absence of this match is not proof of independence: device ID is shared, site identity is unverified, and the contexts are pond versus controlled tank within one study. All Oman source files retain a common study lineage group. Author aggregates are supporting representations of raw data, not another independent recording.

The supplied shrimp ZIP contains the extracted workbook; their separate hashes represent container/member identities, not two datasets. Related Colombia publisher descriptions and the local workbook remain one conservative family; the local file is not a verified match to either release. WQD and other untraceable files remain outside the model release regardless of their group IDs.

## Partition policy

Two evaluation claims need different rules:

### Chronological evaluation within a study

Development and test observations may share the same study/site lineage when the claim is explicitly future-time performance in that setting. They must have disjoint source-observation/target identities and correctly ordered target periods. No training target extends into held-out label periods. Causal test history may contain earlier measurements if they would actually be available at issue time; identical historical input values alone are not proof of leakage.

Copies, aggregates, interpolations and other representations of the same underlying observation cannot supply independent labels to opposing partitions. A canonical representation and recoverable parent references are required. Session/quality exclusions and the later gap policy still apply. Random row splits of heavily overlapping windows are not a substitute for this design.

### Independent-site evaluation

Development and held-out sources need disjoint study/lineage groups **and affirmative evidence of physically independent sites**. Disjoint string IDs are necessary bookkeeping, not sufficient proof. Different files, devices, species labels, gap groups or calendar periods do not alone establish separate farms.

Oman pond-to-tank testing, if later justified, is described as transfer between those recorded contexts within a study, not unseen-farm or fish-to-shrimp validation. Fish/shrimp transfer additionally needs eligible, identified species/environment groups. No current group has independent-site verification.

## Scope and limits

All current source groups have a lineage ID and retain `training_approved: false`. Conservative grouping prevents optimistic independence claims, but it does not force a valid chronological study to be all-training or all-test. The later split builder must enforce both observation/target disjointness and the chosen evaluation claim.

New acquisitions need overlap and provenance review before admission. No universal numeric-vector match can prove all physical provenance: repeated natural values are possible, whereas long matching timestamped source-order segments provide stronger evidence. Rounded comparisons are always labeled as such. The current tests do not establish that every possible cross-file overlap has been found.

## Reproduce and verify

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_lineage -v
.\.venv\Scripts\python.exe -m ml.data.lineage --output Datasets/processed/lineage-new-review
```

The completed output is `Datasets/processed/lineage-review-2026-11-05/compilation_overlap.json`. It fingerprints the exact prepared inputs used in the comparison. Ordered aquaponics evidence remains in its source-specific audit; original raw hashes remain in the preparation manifests.

Three new focused tests check multiset overlap counting and the distinction between independent-site and within-study claims. The helper rejects shared lineage for independent-site claims; it is not a complete split validator and does not certify independence of disjoint IDs. All 27 preparation/audit tests pass. No measurements, partitions, features or models were changed or fitted.
