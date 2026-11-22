# Additional fish and shrimp data

Review date 18 November 2026. This acquisition batch adds a pinned fish-farm monitoring snapshot and a shrimp chemistry reference. The source catalog records seven leads and the hashes of 27 acquired files. The Fish Welfare Initiative snapshot contains 26 files totaling 4.91 MB. The shrimp table adds 43 KB. Original measurements are preserved under `Datasets/external/`.

## Fish Welfare Initiative campaign

The publisher collected continuous water-quality readings at farms in Eluru, Andhra Pradesh, during November 2025–January 2026. The acquired repository is pinned to commit `4cfa138e725db541e7ae14b89170909bef7dafb1`. Its 17 pond CSVs contain DO in mg/L, pH, temperature and cell-level quality flags. Supporting material includes installation/maintenance events, handheld readings, monitor comparisons and three workbooks. The publisher describes 16 devices, including transfers between installations. Pond IDs require a device/session interpretation before they can define independent evaluation groups. [Publisher context](https://www.fishwelfareinitiative.org/post/cm-data), [pinned repository](https://github.com/fish-welfare-initiative/Data-Campaign-Data/tree/4cfa138e725db541e7ae14b89170909bef7dafb1).

The first audit found the following.

| Check | Observed result |
| --- | --- |
| Pond-table rows | 72,750 across 17 CSVs |
| Recorded time extent, IST | 28 November 2025 21:30 through 30 January 2026 23:45:39 |
| CSV/workbook agreement | Timestamps and three measurement channels match for all 17 pond sheets, numeric tolerance `1e-10` |
| Repeated timestamps | 512 row memberships, concentrated in two ponds |
| Source-order time reversals | Zero |
| DO exact zeros | 131, identified as equipment artifacts by publisher documentation |
| Cross-pond exact timestamp/DO/pH/temperature matches | Four pairs, including 501 shared rows in one pair |
| Longest shared exact quarter-hour sequence | 208 consecutive rows, spanning 51 h 45 min |
| Publisher spot DO comparisons | 48 paired rows, mean absolute difference 0.926 mg/L, median 0.660, maximum 3.420 |

The raw extent reaches 30 January, while the publisher narrative says monitoring continued through 29 January. The audit records the discrepancy. CSV timestamps explicitly use IST, which is interpreted as `Asia/Kolkata` from the stated Indian collection location. Exact seconds vary between ponds. Four tables have very little exact quarter-hour-grid support, so rounding timestamps would materially change their apparent capacity.

The spot comparison is a descriptive difference between listed monitor and ProDSS readings. Several times are approximate. A field calibration model would require stronger pairing and measurement evidence. The separate comparison-study workbook has additional headers, devices and sampling context and remains available for detailed review.

The publisher's README identifies exact-zero DO, pH and temperature as device artifacts, including calibration/reset periods and longer outages. Other flags identify near-zero DO, rapid changes and high morning DO. Their flags apply to individual channels. An exported pH flag does not automatically invalidate a DO-only history. Large real DO excursions and small positive values remain recorded for review. The flags legend also warns that workbook conditional-format colors can override one another, so exported flags need an availability and completeness review.

### Structural capacity

A deliberately strict diagnostic counts hours with exactly four distinct timestamps at `:00`, `:15`, `:30` and `:45`, zero seconds, positive finite DO and no exported DO flag. It finds **11,182 supported pond-hours**, **4,630 six-hour-history/+1 h structural windows**, and **3,448 six-hour-history/+3 h structural windows**, requiring complete future support. These counts precede event/session exclusions, lineage grouping and partitioning. They overlap across time and include unresolved shared records. They describe a possible data resource before release preparation.

This diagnostic leaves measurements at their original timestamps and performs no imputation, interpolation, resampling, label creation or learned fitting. The old Oman policy's three readings per minute cannot apply to a sensor sampled every 15 minutes. A second release needs a documented cadence and aggregation policy derived from this source's evidence.

### Reuse and admission

The pinned README invites research use with citation to Fish Welfare Initiative. The publisher website states that its information is freely available for use. The pinned repository has no separate LICENSE file or named Creative Commons identifier. These statements are recorded verbatim in the acquired README and linked publisher context. Training and distribution decisions need the intended use and attribution terms recorded explicitly. Raw files stay outside Git.

The source remains under scientific review. Device transfer, harvest/reinstallation intervals, calibration dates, duplicate timestamps and shared sequences must be resolved before choosing training and independent evaluation groups. Per-pond species is unresolved in this snapshot. The campaign's common source and overlapping collection dates also limit any proposed farm/season generalization claim. The original Oman pilot remains its own frozen experiment.

## Shrimp findings and other leads

| Lead | Evidence and disposition |
| --- | --- |
| Indonesia shrimp chemistry, PANGAEA 889316 | Downloaded with CC BY 3.0 attribution terms. The table has 60 rows and 33 columns, including biological fractions/replicates. Sampling at cultivation days 10/20/30/40/50/70 supports chemistry context. The publisher's `HDO [mg/l]` parameter name requires semantic confirmation. Sampling is too sparse for hourly forecasting. [Dataset](https://doi.pangaea.de/10.1594/PANGAEA.889316). |
| Ecuador commercial shrimp anomaly study | The article describes static samples, proprietary measurements and a synthetic public sample. Its exposed schema lacks continuous DO targets. Excluded from hourly-forecast candidates. [Article and availability statement](https://www.mdpi.com/2673-6470/6/2/27). |
| Indonesia industrial shrimp growth study | Reports daily operational observations with DO over several years. Data is available through an author request. Recorded as a longer-term context lead, with access and temporal resolution unresolved for the present task. [Article](https://www.mdpi.com/2673-9496/5/4/27). |
| Colombia Mendeley `8s73jfvgr5` | Version 2 metadata describes tilapia water-quality and health tables under CC BY 4.0. Version 3 fetches failed. Files may share lineage with earlier Colombia candidates, so identity and transformations need checking before acquisition can establish additional evidence. [Version 2](https://data.mendeley.com/datasets/8s73jfvgr5/2). |
| Zambia WorldFish reference ponds | Four ponds over six months, with twice-daily sampling and a restricted file. Useful as a contextual lead with access restrictions. Cadence is insufficient for the hourly task. [Publisher record](https://doi.org/10.7910/DVN/XJCD0Z). |
| Mexico RAS operational logbook | Automatic monitoring covers other variables, while DO has only 17 manual observations. Excluded from hourly DO forecasting candidates. [Publisher record](https://zenodo.org/records/20277084). |

This search batch establishes no additional eligible hourly shrimp recording. The FWI admission questions raised here are resolved in the [carp pond release](carp.md).

## Reproduce the audit

The acquisition catalog contains pinned URLs, byte sizes, SHA-256 digests and Git blob identifiers for FWI. Download verification checked every file against the pinned Git tree. The PANGAEA table has its own URL and SHA-256. The original XLSX workbooks provide a second representation for CSV measurement verification.

From the repository root in PowerShell, using the existing preparation environment and an acquired source snapshot, run the following with a fresh output directory.

```powershell
$python = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $python -B -m ml.data.audit --output Datasets/processed/fwi-new-audit
& $python -B -m unittest ml.tests.test_audit -q
```

The reviewed output is `Datasets/processed/fwi-discovery-2026-11-18-v2/`. It includes per-pond summaries, source and audit-code hashes, paired-comparison statistics and cross-pond matching diagnostics. The first local audit directory precedes the added shared-sequence lengths. The source catalog's audit hash identifies the reviewed version. [Acquisition catalog](sources.json).
