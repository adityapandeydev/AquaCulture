# Carp pond release

`fwi-do-release-v2` is the second prepared forecasting dataset. It contains hourly dissolved oxygen (DO), pH and temperature from 17 Rohu/Catla ponds in Eluru, Andhra Pradesh, between November 2025 and January 2026. The [policy](carp-policy.json) fixes every exclusion and split. The [anchor](carp-release.json) records the released bytes. The policy was written before any forecast was fitted or scored.

| | Oman pilot | This release |
| --- | ---: | ---: |
| Independent recordings | 1 tank | 17 ponds |
| Eligible hours | 188 | 17,320 |
| Fitting windows, +1 h | 94 | 5,534 |
| Held-out ponds | 0 | 4 |
| Horizons | +1, +3 h | +1, +3, +6, +12 h |

## Review decisions

**Species.** The publisher's [companion dataset](https://github.com/fish-welfare-initiative/fwi-farm-data-india) lists stocking events under the same pond identifiers. All 17 ponds held Rohu and Catla. Culture stages differ between ponds.

**Shared records.** `ara2_29660d32` repeats three other ponds one after another. It matches `ara2_858b914c` until 9 December, `ara2_c9cdacda` until 10 December and `ara2_3eab831e` until 11 December. Every row of `ara2_29660d32` before 14 December 01:15 is excluded. A search at other time lags found no further repeated sequences of eight readings. Three further rows, shared by `ara2_3b2f3973` and `ara2_3ed4df8e`, fall on a calibration day and are excluded.

**Device events.** Each listed installation, calibration, removal or reinstallation day is excluded. History and target must lie on the same side of it. Outages need no rule of their own because missing hours are never filled.

**Duplicate timestamps.** Every repeated timestamp has conflicting values. Those hours are excluded. Days with more than 20 such rows are excluded, which removes 17–19 January from `ara2_3ed4df8e`.

**Zeros and low readings.** Exact zeros are missing, as the publisher directs. Small positive readings and flat stretches are kept. Long flat stretches in the raw data occur mainly near zero around dawn, when real oxygen depletion is plausible. Deleting them would remove the events a warning system needs. Publisher flags are kept as counts and exclude nothing.

**Hours.** An hour needs at least three of its four expected readings. Its value is their mean. Clock-hour bins accept timestamps that are offset from the quarter hour, which restores four ponds that an exact-grid rule had almost emptied.

## Windows and splits

An hour labelled `h` covers `[h, h+1)`. A forecast is issued when that hour closes. The `+1 h` target is the mean of the next hour. Each window uses the last 24 hours, with at least 20 present and the latest three complete.

Seven ponds linked by shared records or possible device reuse are always used for development. From the other ponds with enough test-period coverage, a salted hash selects four test ponds and three calibration ponds.

| Use | Ponds | Issue and target dates | +1 h | +3 h | +6 h | +12 h |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Fitting | 10 | Until 12 January | 5,534 | 5,462 | 5,341 | 5,221 |
| Validation, seen ponds | 9 | 13–18 January | 1,130 | 1,114 | 1,089 | 1,046 |
| Validation, unseen ponds | 3 | Until 12 January | 1,492 | 1,466 | 1,435 | 1,398 |
| Interval calibration | 3 | 13–23 January | 505 | 492 | 480 | 455 |
| **Test, unseen ponds** | 4 | 24–30 January | 645 | 637 | 625 | 602 |
| Test, seen ponds | 9 | 24–30 January | 1,362 | 1,339 | 1,310 | 1,260 |
| Test, unseen ponds, earlier dates | 4 | Until 23 January | 3,052 | 2,999 | 2,938 | 2,837 |

The unseen-pond test at later dates is the primary result. The last row shares weather and dates with fitting data, so it is secondary. The unseen-pond validation set and the calibration set use the same three ponds at different dates. Windows overlap heavily within a pond and are not independent trials.

## Measurement limits

Targets are sensor readings, and the sensors disagree with other instruments.

| Reference | Pairs | Mean absolute difference | Mean signed difference, monitor minus reference |
| --- | ---: | ---: | ---: |
| ProDSS handheld meter | 48 | 0.93 mg/L | -0.41 mg/L |
| Winkler titration, within 15 minutes | 39 | 2.73 mg/L | +0.81 mg/L |
| Winkler, morning only | 19 | 2.37 mg/L | -0.93 mg/L |
| Winkler, evening only | 20 | 3.07 mg/L | +2.47 mg/L |

The sample depth and position of the visits are unknown, and both instruments have error. The correlation with Winkler is 0.88. The differences are descriptive and no correction is fitted. A model trained here predicts what the monitor will report. Small forecast errors do not establish the same accuracy for the true oxygen level, and absolute alert thresholds inherit the sensor error.

Further limits:

- All ponds share one district, one season and one campaign. Nothing here supports other regions, summer conditions or other species.
- Farm ownership is anonymised. Ponds may share a farm, so "unseen pond" does not mean "unseen farm".
- The publisher retracted water-quality records from Nellore after finding fabricated data. All ponds used here are in Eluru, and the retracted file is not used. The campaign data itself has not been retracted.
- The companion dataset is CC BY 4.0. The monitoring repository has no separate licence file. Its README asks users to cite Fish Welfare Initiative. Raw and prepared data stay outside Git.

## Rebuild

```powershell
$python = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $python -B -m ml.data.acquire --catalog docs/data/sources.json
& $python -B -m ml.data.carp --output Datasets/releases/carp-v2-new
& $python -B -m unittest ml.tests.test_carp -q
```

The monitoring snapshot's `acquisition.json` must be present beside its files. Two builds on 22 November 2026 were byte-identical.
