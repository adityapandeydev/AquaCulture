# Data sources

Every source considered for the project, and the decision on it. Being online, published or readable was never enough. A source needed a known origin, reuse terms, units and real measurement times. Decisions were made from 5 to 22 November 2026. Pinned downloads and checksums are in [sources.json](sources.json), and those of the first experiment in [the pilot catalog](../pilot/sources.json).

## In use

| Source | Use | Terms |
| --- | --- | --- |
| [Fish Welfare Initiative monitoring campaign](https://github.com/fish-welfare-initiative/Data-Campaign-Data), 17 carp ponds, Andhra Pradesh | Training and testing of the current models. [Dataset record](carp.md) | README invites research use with citation. No licence file. |
| [FWI farm data](https://github.com/fish-welfare-initiative/fwi-farm-data-india), same ponds | Species, stocking dates and reference measurements | CC BY 4.0 |
| [Oman tilapia recordings](https://github.com/AhmedTheNetCoder/DO-Forecasting-Tilapia-Dataset) | The first experiment only. [Pilot record](../pilot/README.md) | CC BY 4.0 |

The first audit of the monitoring campaign found 72,750 rows in 17 ponds, 512 rows with repeated timestamps, 131 exact oxygen zeros, and four pond pairs sharing records. CSV and workbook values matched for every pond. The [dataset record](carp.md#review-decisions) explains how each was resolved.

## Not used for training

| Source | Why not |
| --- | --- |
| Shrimp buoy workbook, [candidate page](https://data.mendeley.com/datasets/k2jpng5vy6/1) | Channels have no units and no usable calibration. See below. |
| Nigerian-style aquaponics files, `O1D2`, 1,114,970 rows, [candidate paper](https://doi.org/10.1016/j.dib.2022.108400) | Oxygen labelled g/ml in seven files, mg/L in one and nothing in three. 138,876 pH values lie outside 0 to 14. Pond 1 and Pond 2 share 81,215 rows, with one run of 54,501. |
| Colombian tilapia workbook, `O1D3`, [candidate page](https://data.mendeley.com/datasets/3g2b4sh65m/1) | 4,383 hourly rows hold only 360 distinct water readings, in plateaus of up to 759 rows. Health labels are copies of a temperature rule. No oxygen value is below 5 mg/L. |
| Pond variants `O1D1` and environment table `O2D3` | Unknown origin. Three blocks of a compilation workbook are copies of these tables. |
| Quality table `O3D1`, [plausible match](https://data.mendeley.com/datasets/y78ty2g293/1) | 4,300 rows without times. Labels come from thresholds. |
| `archive.zip`, 1,000 rows, and the compilation labelled shrimp | Unknown origin. A title cannot establish species. |
| [Cure4Aqua](https://zenodo.org/records/17278396) | Tank chemistry. Verified, but not a forecasting series. |
| [PANGAEA 889316](https://doi.pangaea.de/10.1594/PANGAEA.889316), Indonesian shrimp | 60 rows on six cultivation days. Too sparse. |

Candidate pages resemble the local files. The original links are lost, so no page's licence or description is assigned to a local file. These files stay local and are not redistributed.

## Looked at and not acquired

| Lead | Reason |
| --- | --- |
| [Ecuador shrimp anomaly study](https://www.mdpi.com/2673-6470/6/2/27) | Static samples, private measurements and a synthetic public sample |
| [Indonesian shrimp growth study](https://www.mdpi.com/2673-9496/5/4/27) | Daily values, on request from the authors |
| [WorldFish Zambia](https://doi.org/10.7910/DVN/XJCD0Z) | Two samples a day, restricted file |
| WorldFish Vietnam 2016 | Repository refused access |
| [Mexico recirculating system](https://zenodo.org/records/20277084) | 17 manual oxygen readings |
| [Colombia 8s73jfvgr5](https://data.mendeley.com/datasets/8s73jfvgr5/2) | Version 3 could not be fetched, and it may repeat the workbook above |

## Shrimp

No source can train an hourly oxygen forecast for shrimp. The buoy workbook was the only recorded series. Its oxygen column has no unit and runs from -13 to 1,721, with 19,509 negative values. Its pH column mixes readings near 8 with readings near 590, and one spreadsheet formula converts both. Reference readings have no dates linking them to a deployment. No channel was rescaled to look plausible. The decision changes only with primary evidence of units, calibration and sessions.

Shrimp ponds in the product have monitoring and the operator's own limits, without forecasts.

## Rules that came out of the review

- Copies, aggregates and interpolations of one recording never appear on both sides of a split.
- Different files, device names or species labels do not prove independent farms.
- Unknown units, times or identity are recorded as unknown. Nothing is converted to look right.
- Interpolated or rule-derived values are not labels.

The full reviews, with counts, hashes and audit commands, are at commit `1ada193`: [sources](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/source-review.md), [shrimp](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/shrimp-calibration.md), [aquaponics](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/aquaponics-review.md), [Colombia](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/colombia-review.md), [lineage](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/lineage-review.md), [campaign and shrimp search](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/expansion-review.md).

## Download and audit

```powershell
$python = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $python -B -m ml.data.acquire --catalog docs/data/sources.json
& $python -B -m ml.data.audit --output Datasets/processed/fwi-new-audit
```

Downloads are checked against recorded hashes, and existing files are never overwritten.
