# Aquaponics pond CSV review

Review date: 2026-11-05. Decision: retain all 11 local `O1D2` files for exploratory preparation and lineage inspection; exclude their channels from the current approved training, validation, test and uncertainty-calibration release. No source values or units were changed.

## Collection and measurement evidence

The files contain **1,114,970 rows** in total. This supersedes earlier approximate descriptions of 1.2 million rows. There is no Pond5 file in this local collection. Filenames do not prove that every file represents a separate physical pond.

The candidate [University of Nigeria aquaponics data paper](https://doi.org/10.1016/j.dib.2022.108400) describes six sensor channels, a twelve-pond study, five-second acquisition and a Kaggle release. It identifies MQ137/MQ135 modules for nitrogen sensing and mentions calibration. These details are source-discovery evidence, not proof of the local files' identity or their chemical conversion. The original acquisition links and release-specific calibration records are unavailable.

The local median positive interval in source-row order is **20 seconds in every file**. This is a file observation, not proof of the original sensor cadence; gaps, clock resets and mixed representations prevent assuming that every adjacent row is a valid sequential sample. It differs from the candidate paper's stated collection interval and requires reconciliation before using that paper as provenance.

## Unit and channel decisions

| Channel | Local evidence | Current decision |
|---|---|---|
| DO | Seven files label the channel `g/ml` (with spacing variations), Pond8 labels it `mg/L`, and Ponds10–12 have no unit in the header. Calibration/source identity is not verified. | No cross-file conversion or calibrated mg/L target is approved. Values inside a plausible DO range do not establish units. |
| Ammonia and nitrate | The same seven/one/three split of `g/ml`, `mg/L` and absent units. Ammonia has 22,079 numeric values above one million in the source's stated units. Chemical basis and aqueous calibration are unverified. | Exclude nitrogen targets and inputs. No assumption of TAN versus NH3, or nitrate versus nitrate-as-nitrogen, and no rescaling to force plausible chemistry. |
| Water temperature | 89 occurrences of -127; other validity questions remain source-specific. | -127 is a sensor-fault/sentinel candidate, never an environmental measurement to smooth into training. Other readings remain exploratory because acquisition/calibration identity is unverified. |
| pH | 138,876 numeric values outside 0–14. | Flag invalid values. Do not clip to comfort ranges or treat remaining numbers as automatically calibrated. |
| Turbidity | 101,618 negative numeric values across the collection. Some files have narrow or saturated-looking distributions requiring further acquisition evidence. | Negative physical turbidity is invalid; sentinel/raw-signal semantics are unknown. No replacement or inferred conversion. |
| Fish weight, length, population and ancillary columns | Measurement timing, provenance and causal availability were not established for this collection. | Excluded from the first DO predictor configuration and from independent biological-outcome evaluation. |

The unit split is based on actual local headers, not on a guessed correction. A nominal g/ml-to-mg/L conversion would change magnitudes by a million; such arithmetic cannot establish whether the original label or measurement was correct. No unit conversion is applied.

## Timestamp and conflict review

Timezone text differs across and within files: CET suffixes, UTC/explicit offsets, and absent suffixes occur. CET is retained as unverified; no location-based timezone is imposed. Explicit offsets are parsed where present, but their presence alone does not prove device clock accuracy.

| File | Rows | Unparseable timestamps | Rows with conflicting values at one parsed wall time |
|---|---:|---:|---:|
| Pond1 | 83,126 | 0 | 0 |
| Pond2 | 172,249 | 0 | 0 |
| Pond3 | 169,185 | 0 | 0 |
| Pond4 | 89,844 | 0 | 0 |
| Pond6 | 91,050 | 1 | 0 |
| Pond7 | 279,612 | 0 | 0 |
| Pond8 | 70,744 | 0 | 0 |
| Pond9 | 151,785 | 0 | 0 |
| Pond10 | 620 | 0 | 310 |
| Pond11 | 3,165 | 0 | 2,421 |
| Pond12 | 3,590 | 0 | 3,564 |

The last column is a **wall-time review flag**, not an automatic assertion that differing explicit UTC instants are identical. Conflicts compare original measurement strings at the parsed local time; formatting and timezone changes require investigation before resolution. These counts are not a replacement for the existing cleaner's absolute-time-aware duplicate rules.

## Shared recordings

The earlier unordered comparison found 77,029 shared unique temperature/pH/DO/turbidity vectors between Pond1 and Pond2, or 99.43% of the smaller unique-vector set. The new check adds the exact recorded timestamp string and source-row ordering:

- **81,215 rows** match the timestamp string and all four water channels, rounded to six decimal places.
- **14 matching runs** have at least 100 adjacent source rows in both files.
- The longest shared run has **54,501 adjacent source rows** in both files.

The join excludes ambiguous duplicated keys and missing join fields, and matches one-to-one. Ammonia, nitrate, fish measurements and population are not part of the match. The different count from the unique-vector audit is expected: a vector can recur at multiple timestamps.

These are duplicated four-channel recording segments in the local files. They do not establish why the segments were copied, which physical pond they originally describe, or whether all other columns share the same origin. They are sufficient to reject Pond1/Pond2 as independent water-forecast holdouts. A source-order run is not necessarily continuous in elapsed time; gap/clock validation remains separate.

## Release disposition

All channels remain exploratory-only and outside the current model-data release. This resolves the collection's role without requiring the lost links to be recovered. The files remain useful for testing fault detection, quarantine and leakage checks, but are not evidence of calibrated nitrogen forecasts, independent pond generalization or biological outcomes.

Reconsideration requires a traceable original release, defensible channel units/chemical basis and acquisition/calibration records. Matching publisher files could resolve identity, but would not itself repair invalid readings or duplicated sequences. Additional traceable data is preferable to manufacturing missing information.

## Reproduction and checks

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_aquaponics_audit -v
.\.venv\Scripts\python.exe -m ml.data.audit_aquaponics --output Datasets/processed/aquaponics-new-review
```

Completed output: `Datasets/processed/aquaponics-review-2026-11-05/`. `audit.json` records source hashes, original headers, channel counts and timestamp findings. `pond1_pond2_shared_rows.csv.gz` retains matching source-row references; `pond1_pond2_shared_runs.csv` records adjacency runs. The utility verifies that source hashes remain unchanged and refuses an existing output directory. All 20 focused data preparation/audit tests pass. No imputation, unit conversion or model training was performed.
