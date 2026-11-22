# Dataset provenance and reuse decisions

Review date: 2026-11-05. The review covers 11 source groups and all 26 local CSV, Excel and ZIP source files, including the publisher-provided aggregate and the supplied shrimp archive/workbook. Archive and extracted-file counts are not independent dataset counts.

The machine-readable decisions are in [sources.json](sources.json). Current decisions apply to the first DO forecasting experiment. A file being available online, included in a paper, or readable locally does not by itself establish its origin, reuse terms or scientific suitability.

## Disposition definitions

- **Eligible candidate:** source identity and stated reuse terms support moving into scientific review. Calibration, session quality and evaluation eligibility are still separate requirements.
- **Exploratory-only:** retained for local inspection, cleaning research and lineage investigation; excluded from the approved training/benchmark release and raw-data redistribution while the stated issues remain unresolved.
- **Reference-only:** retained for background, schema or chemistry context; not a forecasting target dataset for this experiment. This role does not imply its reuse terms are verified.
- **Excluded:** not available or not part of the current data release. The decision can be revisited if new evidence appears.

No source is training-approved. Unknown provenance is recorded as unknown; a candidate publisher's DOI or license is not assigned to an unmatched local file as established provenance.

Subsequent scoped decision, 2026-11-07: the [prepared tank release](readiness-report.md) passes the data-readiness checkpoint for the named chronological DO pilot. The source-wide defaults above are retained; that later approval is limited to the exact checksum-anchored subset and does not admit excluded sources or claim field validity.

## Decisions by source group

| Source group | Disposition | Identity and reuse evidence | Current role and restriction |
|---|---|---|---|
| Oman tilapia recordings | Eligible candidate | Direct downloads from a pinned author-repository commit; SHA-256 checks for the acquired files and the repository's declared CC BY 4.0 license. | First DO candidate after session/date/calibration review. Offline pond and live tank recordings remain separate. Author aggregates overlap raw data and are reference material, not independent test data. |
| Cure4Aqua tank chemistry | Reference-only | Direct Zenodo download. Local workbook MD5 `512e950c7137facc4372214c3b9873b7` matches the publisher checksum in the saved record; metadata declares CC BY 4.0. | Chemistry/unit reference for flow-through/RAS tanks. Not selected for the initial hourly pond experiment. |
| Supplied shrimp-buoy archive | Exploratory-only | User downloaded the archive associated with the identified Mendeley page; local archive/workbook hashes recorded. Publisher checksum not independently matched; page declares CC BY 4.0. | Channel/session review completed: all channels excluded from the current forecasting release because conversion and deployment evidence is insufficient. No raw redistribution approval. |
| WorldFish Vietnam 2016 lead | Excluded | File/schema/license verification was not completed because repository access returned HTTP 403. No file acquired. | Dataset-discovery lead only; absent from the current release. |
| Local Colombia workbook (`O1D3`) | Exploratory-only | A publisher record resembles the title/schema, but the original link is lost and the local file has not been matched. Its listed CC BY license is not proof of this file's identity. | Cadence/label review completed: multiweek constant runs and fractional metadata leave measured status unresolved. Excluded from current forecasting/biological-outcome benchmarks; exploratory inspection only. |
| Local aquaponics pond files (`O1D2`) | Exploratory-only | Names/schema resemble the Nigeria aquaponics study; exact acquisition and release/license are unknown. | Unit/fault/lineage review completed: all channels excluded from the current model-data release. Pond1/Pond2 share long timestamp/water segments and cannot serve as independent holdouts. |
| Local quality workbook (`O3D1`) | Reference-only | The 4,300-row threshold-classification source is a plausible match, not confirmed file provenance. Local reuse terms remain unverified. | Background classification/schema comparison only; no timestamps or DO forecasting benchmark role. |
| Local pond variants (`O1D1`) | Exploratory-only | Unknown online origin and transformations; no established publisher or reuse terms. | Lineage/cleaning investigation. Related variants are not independent measurements or approved benchmark sources. |
| Local environmental table (`O2D3`) | Exploratory-only | Unknown water/environmental data origins and reuse terms; related measurement vectors occur in O1D1. | Conflict/lineage inspection only. Environmental columns are not approved covariates and pond identity is unresolved. |
| Compilation workbook labeled shrimp sensor data | Reference-only | Mixed tables with unavailable original links and unverified reuse terms. | Background/lineage inspection only. Its title cannot establish the species or origin of the individual blocks. |
| Local `archive.zip` | Exploratory-only | Contains a 1,000-row assessment table; origin, author and reuse terms unknown. | Tabular preparation exploration only. No established chronological forecasting role. |

## Evidence and attribution

The acquired Oman files are pinned to commit `d95207b6f129c3de1f426ec90eed5a38f46832b8` in the [author repository](https://github.com/AhmedTheNetCoder/DO-Forecasting-Tilapia-Dataset). The saved LICENSE is the basis for the recorded reuse decision; repository and publication attribution still need reconciliation before an academic citation is finalized. Author-provided events and derived aggregates are supporting files rather than additional independent datasets.

The [Cure4Aqua record](https://zenodo.org/records/17278396) supplies the workbook checksum. Its saved API metadata records the creators, version v2, DOI and license. The checksum match establishes identity with that published file, not the validity of each chemical measurement.

The [shrimp-buoy page](https://data.mendeley.com/datasets/k2jpng5vy6/1) lists the dataset and CC BY 4.0. The supplied ZIP and its contents are preserved and locally fingerprinted, but a matching filename and local checksum do not independently establish publisher identity. The [calibration review](shrimp-calibration.md) records the separate scientific concerns.

The candidate [Colombia](https://data.mendeley.com/datasets/3g2b4sh65m/1), [Nigeria aquaponics](https://doi.org/10.1016/j.dib.2022.108400) and [quality-classification](https://data.mendeley.com/datasets/y78ty2g293/1) references remain discovery leads for the corresponding local groups. Candidate metadata is kept separately from verified local-file identity.

Raw redistribution is currently recorded as permitted by the declared license evidence only for the pinned Oman acquisition and checksum-matched Cure4Aqua file, with attribution, license notice and changes documented. This project decision is limited to the identified release; it does not grant blanket permission for similarly named files. Large raw/prepared files remain excluded from Git regardless of license.

## Verification performed

- Every current source CSV, Excel workbook and ZIP maps to exactly one catalog source group; publisher-supplied aggregate data is included in this coverage check.
- All 25 preparation-input checksum entries across the two completed batches still match their source bytes.
- All 12 downloaded Oman/Cure4Aqua files still match their acquisition SHA-256 values.
- Cure4Aqua's local MD5 matches its publisher record.
- All 11 groups have explicit identity evidence, reuse evidence, benchmark status, redistribution decision and `training_approved: false`.

The local verification record is `Datasets/processed/source-review-2026-11-05.json`. It describes the files present for this review; additions require a new review. No raw or cleaned measurements were modified.

## Effect on the next experiment

The initial evidence-backed path is a scientifically reviewed subset of the Oman recordings. It is not yet ready to train. Shrimp coverage remains an active research requirement. The supplied buoy workbook's channel review ended in exclusion from the current forecasting benchmark; it remains available for exploratory inspection if new calibration evidence appears.

Lost links do not block the project: unverified files already have a restricted disposition. New traceable acquisitions can replace them. Source-level eligibility will not automatically apply to all channels, sessions or derived labels in a file.
