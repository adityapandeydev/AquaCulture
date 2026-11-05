# Timestamp and recording-session inventory

Review date: 2026-11-05. The current modeling candidates are the restricted Oman recordings. Other collections already have explicit exploratory/reference/excluded dispositions; their unresolved clocks are not repaired by assigning invented timezones or ponds.

## Oman time mapping

The pinned data dictionary explicitly states local Oman time, GMT+4, for both raw files. The timestamp sidecar applies a fixed +04:00 offset and stores UTC separately, with an evidence identifier and dictionary checksum. For example, local April 1 at 01:00 maps to March 31 at 21:00 UTC. No receipt or feature-availability time is invented.

The conversion is source-specific. Explicit offsets are honored without applying +04:00 a second time. Raw strings and source-row numbers remain present; original CSVs, generic cleaning outputs and sensor values remain unchanged. This sidecar implements the timestamp/session portion of the [measurement contract](measurement-schema.md), not a complete canonical observation migration.

## Inventory and exclusions

The inventory uses the existing conflict/deduplication policy, then restricts each file to its documented local date period. A gap **greater than one hour** creates a candidate continuity boundary. Groups are source/device-specific with stable IDs tied to source hash, recording, device, start time and gap policy.

| Recording | Raw rows | Timestamp-mapped rows in stated period | Separately excluded rows | One-hour-gap groups |
|---|---:|---:|---:|---:|
| Offline/pond | 41,663 | 37,913 | 3,750 | 5 |
| Live/tank | 102,670 | 102,670 | 0 | 2 |

Offline exclusions comprise 543 conflict/deduplication rows and 3,207 otherwise retained rows outside the documented pond period. Counts differ from raw date-period totals because deduplication/conflict quarantine occurs first. Every original row belongs to exactly one timestamp-mapped or excluded output.

The raw offline file has 23 backwards steps. Both adjacent source rows are flagged, producing 46 retained review rows in the earliest continuity group. All **5,714 rows in that affected group** are marked `excluded_pending_ordering_review`; they remain in the timestamp inventory for traceability, not as eligible model examples. Sorting alone cannot distinguish delayed/concatenated exports from a sensor-clock issue. No clock reset is asserted without evidence.

The other four pond groups contain **32,199 rows** before later quality/coverage/partition checks. The tank has no backwards source-order steps. Both datasets have unknown physical site/pond identifiers in the inventory; `node_001` is retained as a recorded device identifier. A device ID reused across files does not establish independent sites.

## Gap sensitivity

| Boundary threshold | Pond groups | Tank groups |
|---|---:|---:|
| More than 60 seconds | 15 | 10 |
| More than 300 seconds | 6 | 2 |
| More than 3,600 seconds | 5 | 2 |

These are sensitivity checks, not alternative counts of physical deployments. The one-hour threshold is an inventory rule; shorter gaps still require per-window coverage checks. A window must never bridge a continuity boundary simply because observations share a source file.

One tank group contains 291 rows over approximately 33 minutes on April 1; the other contains 102,379 rows from April 2 to April 10. The longer pond group has 22,715 rows from March 28 to March 30. Short fragments cannot support the specified 6–24-hour histories and 1–6-hour targets; usable example counts will be recomputed after final gap policy and channel-quality checks.

All IDs have status `candidate_continuity_group`, not `verified_recording`. Publisher-declared pond versus controlled-tank context is kept distinct, while a conservative common study lineage group records that independent-site evidence is absent. No group is training-approved.

## Other source collections

- **Shrimp buoy:** reverse chronological ordering and 77 one-hour-gap candidates were recorded in the [channel review](shrimp-calibration.md). Pond/session/timezone identity remains unknown; all channels are outside the current benchmark.
- **Colombia:** [review](colombia-review.md) verified an hourly row grid but not an hourly measured target series or independent pond identity. No timezone or genuine acquisition session is inferred.
- **Aquaponics:** [review](aquaponics-review.md) preserves CET/UTC/offset differences and flags wall-time conflicts. Their unresolved source/calibration status keeps them outside the model release.
- **O1D1/O2D3 and compilation blocks:** derived/reconstructed time provenance and related measurement lineage remain unverified. They are not admitted by parsing a date successfully.
- **Untimestamped classification/reference data and Cure4Aqua:** reference roles do not require inventing an hourly sensor-session structure.

Unknown identity is addressed through restriction or exclusion, not by labeling separate files as separate ponds. Additional sources require their own timestamp/session review before entering a later release.

## Reproduction and validation

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_sessions -v
.\.venv\Scripts\python.exe -m ml.data.sessions --output Datasets/processed/oman-sessions-new-run
```

The current output is `Datasets/processed/oman-sessions-2026-11-05-v2/`; it supersedes the earlier run's narrower row-level ordering flags. `inventory.json` records UTC boundaries, gap statistics, evidence, source hashes, contexts and use restrictions. Compressed timestamp sidecars map every retained row; separate files record excluded rows and original ordering issues.

Validation checked complete/disjoint raw-row accounting, +04:00-to-UTC mapping, chronological ordering inside groups, stable group IDs, and group-wide exclusion when ordering remains unresolved. All 24 focused preparation/audit tests pass. No model or imputer was fitted, no calibration reapplied, and no original measurement altered.
