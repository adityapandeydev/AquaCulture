# Canonical measurement schema

Version: 1.0 — 2026-11-05. This is the contract for the next preparation release, not a claim that earlier exploratory CSVs already implement it. No data is converted or approved for training by this document.

## Representation

One observation record represents one channel value from one source row. Water measurements, derived values and imputed values remain distinguishable. This long format accommodates different sensor sets without inventing missing ammonia, salinity or pH observations.

Three related files describe a prepared release:

1. **Source manifest:** original file hashes, acquisition/source evidence, license decision, dataset version and preparation policy version. The current source-group catalog is [sources.json](sources.json).
2. **Series manifest:** source/site/pond/device/session identity, species and farming environment with evidence, timezone, calibration references and lineage group. Unknown identity is explicitly null.
3. **Observations:** original channel/value and source-row reference, parsed time, any verified normalized value, quality and modeling-use decision.

Transforms/aggregates additionally reference their parent observations through a lineage file or manifest. Derived output cannot be mistaken for another independent sensor sample.

## Identity and context

| Field | Meaning |
|---|---|
| `schema_version` | `1.0` for this contract. |
| `source_id`, `source_version` | Catalog source group and immutable acquisition identifier; use file hashes when a publisher version is unknown. |
| `source_file`, `source_sha256` | Relative original-file path and SHA-256. A readable filename is not sufficient identity. |
| `source_table`, `source_row`, `source_column` | Sheet/archive-table identifier, original one-based row and exact header. CSV header is row 1; worksheet rows retain their original numbering. |
| `observation_id` | Stable unique ID derived from source hash, table, row, column and representation version; no random replacement on rerun. |
| `series_id` | Stable preparation grouping key. A technical key may exist when physical pond identity is unknown; that does not establish an independent pond. |
| `site_id`, `pond_id`, `device_id`, `session_id` | Physical or recorded identity where evidenced; otherwise null. An identified device is not automatically an identified pond/site. |
| `session_status` | `unknown`, `candidate_continuity_group` or `verified_recording`. A gap-based group is not automatically a field deployment. |
| `species`, `environment`, `context_evidence` | Source-supported species/system, including freshwater fish, shrimp/brackish water or controlled tank. Preserve whether the claim is publisher-declared, independently verified or unknown. Unknown species is not labeled generic fish. |
| `lineage_group_id` | Conservative group that must stay together in leakage-sensitive partitioning. Unknown independence never becomes a new independent farm by filename. |
| `calibration_evidence_id` | Link to calibration record/version and applicability decision; null if none. A JSON with coefficients alone does not mean calibration accuracy is verified. |

Site, species, environment and calibration may reside in the series manifest rather than repeat on every observation. The observation's `series_id` must resolve unambiguously to the exact manifest version.

## Timestamps and availability

| Field | Meaning |
|---|---|
| `timestamp_original` | Original timestamp text, or preserved date/time components with their source columns. |
| `timestamp_local` | Parsed source wall clock without invented offset. Null when no defensible calendar time exists. |
| `timestamp_utc` | Offset-aware UTC instant only when explicit offset or source-specific timezone evidence supports it; otherwise null. |
| `time_basis`, `timezone_evidence_id` | `explicit_offset`, `source_documented_offset`, `unknown` or `invalid`, with evidence for source-documented offsets. Unresolved CET is unknown, not silently mapped to UTC. |
| `observed_at`, `received_at`, `available_at` | Measurement-event, receipt and earliest feature-availability times when known. Unknown receipt/availability remains null. Retrospective timestamp-availability assumptions are declared in the experiment manifest. |
| `interval_start`, `interval_end`, `statistic` | Aggregation support and statistic (`instantaneous`, `mean`, `minimum`, etc.). Raw timestamped samples are instantaneous only according to their declared acquisition semantics. |
| `availability_assumption` | Source-backed or experiment-declared rule used when exact arrival times are absent; not a fabricated received timestamp. |

The Oman dictionary supports local GMT+4; a later source adapter can derive UTC and record that evidence. A host computer's timezone is never a conversion source. Mixed-offset source series retain correct absolute instants when known. Unknown wall clocks cannot be globally aligned merely by their displayed time.

Hourly `[09:00, 10:00)` means are labeled at 10:00, never 09:00. Their recorded availability cannot precede interval end; actual transport/processing delay is represented if known. Parent counts, valid counts, coverage and maximum observed gap accompany aggregates. Empty bins have no measured target value.

## Values, units and chemical basis

| Field | Meaning |
|---|---|
| `parameter` | Explicit analyte/channel identity; e.g. `dissolved_oxygen`, `water_temperature`, `ph`, `turbidity`, `ammonia_unspecified`, `nitrate_unspecified`, `air_temperature`, `tds`. |
| `raw_value`, `raw_unit` | Original cell representation and exact declared unit, if present. Preserve malformed text, spreadsheet error codes and unknown unit as such. |
| `parsed_value` | Finite numeric interpretation in the source representation, or null. Numeric parse success is not a validity or calibration assertion. |
| `normalized_value`, `normalized_unit` | Verified common physical representation, or null. Here “normalized” means unit harmonization, not min–max/z-score scaling. |
| `unit_status`, `measurement_basis` | Unit evidence (`source_declared`, `verified_conversion`, `unknown`, `conflicting`) and analyte basis. A declared unit may still have a failed scientific review. |
| `representation` | `source_reported`, `verified_unit_conversion`, `aggregate`, `imputed` or `derived_label`. Source-reported records may already have publisher preprocessing; they are not automatically original instrument reads. |
| `origin_quality` | `measured`, `publisher_preprocessed`, `mixed_or_unknown`; retain whether the distinction is actually established. |
| `transform_id`, `parent_lineage_id` | Versioned conversion/derivation and parent references. Null only for an unchanged source representation. |

Preferred common representations, **when justified**, are DO in mg/L, water/air temperature in Celsius, and pH on its dimensionless scale. Celsius water and room-temperature channels remain different parameters. Turbidity NTU, FTU and water-clarity depth in cm are different measurement bases; no synonym mapping silently converts them. TDS is not salinity.

Nitrogen records identify the chemical basis separately from the concentration unit:

- Total ammonia nitrogen (`TAN`, mass as N).
- Unionized ammonia (`NH3`, mass as NH3) or ammonia nitrogen (`NH3-N`, mass as N).
- Ammonium (`NH4` or `NH4-N`).
- Nitrate (`NO3` or `NO3-N`) and nitrite (`NO2` or `NO2-N`).
- Combined nitrate/nitrite nitrogen remains a combined parameter, not nitrate alone.

If only “ammonia” or “nitrate” is declared, the basis is `unknown`. No molar-mass/speciation conversion is permitted without known basis and required contextual measurements. A conversion record includes formula/constants, input units, output basis, evidence and applicable sessions. pH/temperature alone do not establish every missing speciation assumption.

Salinity preserves its original basis: a ppt label, practical salinity, conductivity-derived estimate and g/L mass concentration are not automatically interchangeable. Temperature, pressure, salinity and other compensation metadata remain available where the sensor method requires them.

## Quality and modeling eligibility

| Field | Meaning |
|---|---|
| `quality_flags` | Explicit list such as `missing`, `nonnumeric`, `nonfinite`, `screening_range`, `sentinel_candidate`, `timestamp_conflict`, `unit_unverified`, `interpolation_unknown`, `suspect_extreme`, `duplicate_source_segment`. Flags are observations/reasons, not biological-risk labels. |
| `value_status` | `valid_candidate`, `suspect`, `invalid`, `missing` or `unknown`. Valid candidate is not a final model-use approval. |
| `model_use` | `candidate`, `exploratory_only`, `reference_only` or `excluded`, with separate input/target decisions where they differ. |
| `use_reason`, `review_version` | Justification and exact review/policy version. Source-level eligibility does not automatically approve every channel/session. |
| `training_approved` | Explicit boolean. False throughout the current exploratory releases. True requires the complete readiness checks for the selected task and frozen release. |

Invalid screened values are not replaced by safe readings. Raw values are preserved even if parsed/normalized fields are null. A zero DO can be a real event or instrument problem; flags and evidence determine handling, not convenience for the model. A long plateau is flagged without inventing replacement measurements.

Imputation creates a separate representation and parent lineage; it never overwrites measured ground truth. Target eligibility requires an established measured/acceptable source basis. Risk flags derived from thresholds, health-status strings and interpolated disease counts do not become independently observed biological outcomes.

## Source mappings for the next release

| Source group | Channels and time/identity mapping | Modeling use |
|---|---|---|
| Oman raw offline/live | `do_mgL` → dissolved oxygen, declared mg/L; `temp_c` → water temperature, declared Celsius; `ph` → pH. `timestamp` plus documented GMT+4; `node_id` is a device, not a pond. Separate offline/live series and documented contexts. Calibration JSON references retained without reapplication. | Restricted candidates; exclude offline rows outside the stated pond period. No training approval or independent-site assumption. |
| Oman author aggregates/events | Aggregate names preserve statistic and five-minute interval support. Event log retains event and recording time; no invented availability. | Reference/supporting data only until lineage and availability are established. No independent test copies. |
| Cure4Aqua | Tank ID, date and original parameter/unit from long table. Preserve mmol/L, concentration, salinity and oxygen basis separately. | Reference-only; no automatic hourly targets or inter-parameter resampling. |
| Shrimp buoy | `Water Temperature` and `Room Temperature` are distinct. pH, calculated pH, DO, turbidity, TDS retain their raw names/basis. Combined date/time remains unknown-zone local time; continuity IDs remain candidates only. | All channels outside current model release; calculated-pH values are derived, not independent targets. Reference-buffer sheet remains reference-only. |
| O1D2 aquaponics | Map header aliases to parameter names but preserve g/ml, mg/L or absent-unit evidence. Ammonia/nitrate chemical basis unknown. Keep exact time strings/offset status and filename/device evidence without inventing physical ponds. | Exploratory-only; no concentration conversions or nitrogen targets. Pond1/Pond2 share a conservative lineage group. |
| O1D3 Colombia | Use original named water columns, not lowercase derived/normalized copies. Keep timestamp and unknown pond/timezone. Calendar copies, interventions and health labels retain their derived/unknown origin. | Excluded from forecasting/biological benchmarks; local origin remains unverified. |
| O1D1 pond variants | Station and date/time preserved if supplied. Concentration/temperature headers are source declarations, not verified origin. No timestamps added to `Fish Ponds.csv`. | Exploratory-only; group shared O1D1/O2D3 content conservatively. |
| O2D3 environmental table | Preserve original water/environment headers, unknown pond, timestamp ambiguity and covariate origin. | Exploratory-only; no approved weather inputs or independent holdout. |
| O3D1 quality workbook | Preserve units including turbidity cm, unspecified temperature unit and threshold-derived quality label. | Reference-only, no calendar time or independent disease labels. |
| Compilation workbook | Map each extracted table as a distinct source-table component, with original worksheet coordinates; do not infer species from workbook title. | Reference-only; copied blocks share their known lineage warnings. |
| Local assessment archive | Preserve ZIP/member identity and original columns; missing acquisition, time and measurement basis remain unknown. | Exploratory-only; not a forecasting source. |
| WorldFish Vietnam lead | No observations exist locally; source catalog entry only. | Excluded/not acquired. No fabricated mapping. |

## Required validation before adopting the schema

- Source and series references resolve to immutable manifests; IDs are unique and raw source rows remain recoverable.
- All numeric modeling values are finite; null means missing/unavailable, not zero. Unknown unit/time/chemical basis is explicit.
- Source-specific unit conversion and timestamp mapping have evidence and applicable session boundaries. No geography or comfort range supplies missing calibration.
- Aggregates have interval/availability semantics and recoverable parent observations; imputed/derived values cannot masquerade as new measured samples.
- Modeling windows never cross unknown session/site boundaries or lineage-sensitive partitions. Eligibility is checked at observation/channel/session and release levels.
- Any feature scaling or learned imputation is later fitted on training data only. It is not a unit-normalization step and never alters stored source observations.

Adapters and these validation checks will be implemented in subsequent preparation runs. Existing exploratory CSVs keep their original layout; no bulk migration or training is part of this schema-definition milestone.
