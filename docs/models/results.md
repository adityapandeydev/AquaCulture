# Forecast test results

The frozen [candidate](candidate.json) was tested once on 22 November 2026 under the [registered plan](forecast.md) and its [amendment](amendment.json). Code and records were committed first, at `2c897ef`. No model, calibration or limit was changed afterwards. The test data is now exposed, and any later score on it must say so.

## Release decision

| Horizon | Point forecast | 90% interval | Low-oxygen probability |
| --- | --- | --- | --- |
| +1 h | **Pass** | **Pass** | **Pass** |
| +3 h | **Pass** | Fail, too wide | **Pass** |
| +6 h | **Pass** | Fail, too wide | **Pass** |
| +12 h | Fail | Fail, too wide | **Pass** |

The four-model blend may provide point forecasts to +6 h, a 90% interval at +1 h, and low-oxygen probabilities at all four horizons. It must not show a point forecast at +12 h or an interval beyond +1 h. These limits apply to research and demonstration use. The data covers one district and one winter, and the sensors have [substantial reference error](../data/carp.md#measurement-limits).

## Primary test

Four ponds that were never used before, 24–30 January. Errors are averaged within ponds first. The naive forecast is the strongest of three on this test set. The gain range is a 95% interval from resampling pond-days.

| | +1 h | +3 h | +6 h | +12 h |
| --- | ---: | ---: | ---: | ---: |
| Windows | 645 | 637 | 625 | 602 |
| Strongest naive MAE, mg/L | 0.742 | 1.340 | 1.603 | 1.601 |
| **Blend MAE, mg/L** | **0.662** | **1.078** | **1.379** | **1.536** |
| Blend RMSE, mg/L | 1.075 | 1.503 | 1.836 | 2.044 |
| **Gain over naive** | **10.7%** | **19.6%** | **14.0%** | **4.1%** |
| Gain range | 8.0 to 13.9% | 15.2 to 23.7% | 2.7 to 24.2% | -9.7 to 17.0% |
| Required gain | 5% | 10% | 10% | 10% |
| Worst pond, error relative to naive | 0.93 | 0.95 | 0.96 | 1.13 |
| Bias, mg/L | -0.08 | -0.32 | -0.65 | -0.76 |
| 90% interval coverage | 93.3% | 96.7% | 95.9% | 97.6% |
| Interval width, mg/L | 2.95 | 5.85 | 7.30 | 8.95 |

The +6 h gain passes on its estimate, while its range reaches down to 2.7%. The +12 h forecast fails the gain, pond and bias limits. Intervals beyond +1 h cover more than the permitted 95% because the calibration dates were harder to forecast than the test dates. Forecasts run low at longer horizons.

## Low-oxygen probability

Events are hours with a sensor mean below 3 mg/L. Brier skill compares with the usual frequency at that hour of day. Recall and precision use a 50% probability. "New" drops exclude windows that were already low when the forecast was made.

| Unseen ponds, 24–30 January | +1 h | +3 h | +6 h | +12 h |
| --- | ---: | ---: | ---: | ---: |
| All events | 45 | 45 | 40 | 36 |
| Brier skill | 0.80 | 0.67 | 0.57 | 0.54 |
| Recall | 78% | 64% | 60% | 58% |
| Precision | 85% | 72% | 71% | 64% |
| New drops | 11 | 28 | 35 | 36 |
| New drops, recall | 45% | 50% | 60% | 58% |
| New drops, precision | 71% | 74% | 75% | 64% |

The registered limit only requires positive skill, which is a low bar. At a 50% threshold, the system misses 40–55% of new drops in unseen ponds. Event counts are small. A warning can support a farmer's own checks and cannot replace them, and the absence of a warning does not mean a pond is safe.

## Secondary tests

| Gain over strongest naive | +1 h | +3 h | +6 h | +12 h |
| --- | ---: | ---: | ---: | ---: |
| Known ponds, 24–30 January, 9 ponds | 10.5% | 17.7% | 9.4% | 4.9% |
| Worst pond relative to naive | 1.00 | 0.88 | 1.29 | 1.16 |
| Unseen ponds, before 24 January, 4 ponds | 7.5% | 19.3% | 19.8% | 12.5% |

On known ponds the +6 h gain is below 10% and one pond is 29% worse than naive. These sets carry no gates, but they show that the +6 h result is not uniform.

## Comparison model

Boosted trees were reported alongside and cannot replace the blend. On the primary test their MAE was 0.650, 1.085, 1.343 and 1.562 mg/L. They were better than the blend at +1 h and +6 h and worse at +3 h and +12 h. They also passed the +6 h interval gate. The blend's 2% validation advantage did not carry over clearly to the test.

## Numerical sensitivity

Found after the test, while building the backend. Rounding noise of 1e-13 in the inputs can move the trees by up to 0.44 mg/L and the blend by up to 0.11 mg/L, because hourly means often lie on split points. The service rounds its inputs as the dataset was rounded, which reproduces the tested forecasts. The results above are unchanged. [Details](service.md#rounding)

## Records

Outputs are in `ml/runs/carp-final/`. `run.json` has SHA-256 `7cf6cd2e3c4a4231b43a25c971a18eb773a418bfc47cb9699ea6fa99823adcf7`. It identifies the candidate by `190fdf2b6c4c302b3500ba61b07c5bc37d7afa252dca1396dfd55d0e16902026`, the hash of the file with Windows line endings as it was when tested. With the repository's LF endings the hash is `ac8d87237900594a72e6a2a781a3a8a5b9a3af89f3f2296eca70a042e789f1da`. The content is the same.
