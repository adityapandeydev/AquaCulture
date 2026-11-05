# Shrimp-buoy calibration review

Review date: 2026-11-05. Status: channel review complete for the current release. The workbook remains exploratory-only; no channel is approved for supervised forecasting. Measurement and calibration evidence is insufficient, so the decision is exclusion from the current benchmark rather than an assumed conversion.

## Workbook inspected

`Datasets/external/shrimp_buoy/TestData_DBT6.xlsx`, SHA-256 `7970d5e95bc55d013716900005ced1a1b4b5c0fdbe39e2732d1a709563cd95f0`. The file was read without executing macros or recalculating formulas. The inspection used both stored values and formula text.

## Calculated pH

Cell `Data!K1` contains an array formula covering `K1:K94730`:

```text
=IF(ROW(C:C)=1, "Calculated Ph", IF(ISBLANK(C:C), "", C:C*0.01020408+0.979591836734693))
```

This applies a single linear conversion to column C. It does not establish whether every row in C has the same measurement basis.

For example, `Data!C2` is 8.2 and its stored calculated result is approximately 1.0633. The following row has C=590 and a calculated result near 7.0. Some later entries contain concatenated numeric strings rather than valid numbers. These examples are consistent with mixed raw/calibrated representations or editing errors, but the workbook alone does not establish which interpretation is correct for each session.

The `Data` sheet contains 13,389 stored `#VALUE!` error cells. These are not measured pH values. The array conversion is not applied by the cleaning pipeline, and the stored calculated-pH column is not used as a target or predictor.

## Reference readings

`Sheet2!B1` is labeled `PH7`; `F1` is labeled `PH9`. The first sample readings are approximately 6.66 and 7.37 respectively. Row 55 introduces a `PH4` heading. The sheet contains times but no explicit dates linking these readings to particular sessions in the main sheet.

These labels suggest calibration/reference experiments, but they do not independently establish buffer preparation, instrument traceability, sensor response stability or the validity of the conversion coefficients. They also do not explain whether the displayed values are already converted.

## Channel decisions

The reproducible audit examined the original stored values and formulas. Counts below refer to the 94,729 rows under the `Data` header, including 1,005 rows without parseable timestamps. A numeric value inside a screening range is not automatically a calibrated observation.

| Channel | Observed evidence | Decision for this release |
|---|---|---|
| pH, column C | 67,746 numeric entries between 0 and 14; 12,558 negative; 31 above 14; 13,389 nonnumeric; 1,005 missing. The column includes both pH-like values and values such as 590. | Excluded as a measured target or model input. The representation cannot be assigned reliably by plausibility alone. |
| Calculated pH, column K | One array formula transforms all column-C rows; 13,389 stored `#VALUE!` errors. The formula transforms 8.2 into approximately 1.0633 but 590 into approximately 7.0. | Excluded. The coefficients and applicable input representation have no established calibration basis. Cached spreadsheet outputs are not independent measurements. |
| DO | 19,509 negative values; 21,565 zeros; finite values range from -13 to 1,721. No unit is stated in the column header. | Excluded as a DO mg/L target or input. Zero values remain preserved; they are not automatically treated as sensor failure, true hypoxia, or missingness. |
| Turbidity | Finite values range from 13 to 1,775; no unit or conversion is documented in the workbook. | Excluded as a calibrated input. Raw-count versus NTU interpretation remains unknown. |
| TDS | 42,473 negative values and 6,470 zeros; finite range -1 to 845. | Excluded. Negative values are invalid as physical concentration, but the meaning of zeros and the measurement basis are unresolved. No TDS-to-salinity conversion is justified. |
| Water temperature | Finite range -127 to 85, including 1,250 negative values. Median is 27.75. | Exploratory review only; no approved model input. Plausible stretches do not establish units, calibration or field-session identity. It is retained separately from room temperature. |
| Humidity and room temperature | Each has 29,650 nonnumeric entries, many -1 values and no usable acquisition/calibration record. | Excluded from the first experiment. These are not substitutes for water measurements. |
| `Sheet2` reference readings | PH7: 23 numeric readings, median 6.70; PH9: 31, median 7.32; PH4: 22, median 5.48. No dates link these groups to main-sheet sessions. | Reference-only. The labels and readings do not identify whether values are raw or already transformed, or establish the correct calibration for a field session. |

No fitted calibration line, clipping rule or rescaling was applied. Fitting coefficients to the reference labels without acquisition context could produce a plausible-looking series with no defensible physical meaning.

## Recording-period assessment

All 93,723 successive differences between parseable timestamps in source-row order are negative. The workbook is strictly reverse chronological among those records; this is a file ordering property, not evidence of a sensor clock fault. There are 93,724 parseable timestamps and no repeated parseable timestamps in the audit.

After sorting timestamps, gaps greater than one hour produce **77 candidate continuity groups**. These group IDs are for inspection only. An hour was chosen as an audit gap rule, not as a claim about physical deployment boundaries or a final training gap policy. Gaps inside a group may still make particular forecast windows unusable.

Examples show changes in representation across different periods:

- July 11–13: a group of 11,359 rows has numeric column-C values in the 0–14 range.
- August 20–22: 10,323 of 10,339 rows in one group have negative column-C values.
- September 7–9: 8,120 of 8,149 rows in one group have nonnumeric column-C entries.

These periods are not classified as field or calibration sessions. They expose changes requiring acquisition evidence. Exact species, pond identity, timezone, sensor changes and links to the reference sheet remain unverified. No period is selected for a forecasting release solely because its values look reasonable.

## Reproduction and verification

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_shrimp_audit ml.data.test_prepare -v
.\.venv\Scripts\python.exe -m ml.data.audit_shrimp --output Datasets/processed/shrimp-channel-new-review
```

The completed audit is `Datasets/processed/shrimp-channel-review-2026-11-05/audit.json`. It includes channel summaries, formulas, error counts, reference-group summaries and candidate continuity periods. `candidate_session_rows.csv.gz` retains source-row mappings, and `ph_representation_runs.csv` records contiguous representation blocks in original row order. None is a training split or a recalibrated dataset.

Fourteen focused tests pass. The audit checks that the workbook checksum is unchanged after inspection. Original archive/workbook and prior cleaning outputs remain untouched.

## Evidence needed to reconsider the decision

The [related platform paper's publisher preview](https://link.springer.com/article/10.1007/s11276-023-03537-9) was inspected during the literature review. Its accessible text does not establish channel units, conversion coefficients or the link between calibration readings and workbook sessions. No conversion was approved from that preview.

A focused search also identified the paper in an ICAR institutional publication record, but its repository page was inaccessible during this run. Institutional association does not establish the meaning of this workbook's channels. The available primary technical description remains insufficient for a conversion decision.

- Establish the sensor/channel definition and units from a primary technical description or accompanying acquisition code, if available.
- Check whether the linear coefficients have a documented calibration basis and whether they apply to any identifiable subset of recordings.
- Locate representation changes, malformed segments and reference/test periods without inferring corrected values from plausibility alone.
- Determine the meaning of DO and turbidity values, including zeros and large values, before any unit conversion.
- A new channel/session decision requires new primary measurement evidence. The present exclusions remain in effect; a known spreadsheet formula is not sufficient calibration evidence.

The relevant repository is [Tiny ML Based Reconfigurable Water Buoy for Intensive Brackishwater Aquaculture](https://data.mendeley.com/datasets/k2jpng5vy6/1). Its description does not by itself establish the units and session boundaries of the supplied workbook.
