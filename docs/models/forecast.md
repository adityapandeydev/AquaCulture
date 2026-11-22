# Dissolved oxygen forecast experiment

This plan was committed before any model was fitted to the [carp release](../data/carp.md). The limits are in [criteria.json](criteria.json).

## Task

At the close of each hour, forecast the mean sensor DO of the hours ending 1, 3, 6 and 12 hours later. Inputs are the previous 24 hourly means of DO, pH and temperature, their availability, and the hour of day. Pond identity is never an input, so every model can be applied to a new pond.

Each model produces nine quantiles. The median is the point forecast. Forecasts are limited to nonnegative values. Gaps within a history are carried forward from earlier hours, and any leading gap takes the first later value inside the same history. Models also receive the gap locations. Targets are never filled.

## Candidates

| Family | Forecast |
| --- | --- |
| Persistence | Latest hourly value |
| Yesterday | Value at the same hour one day before the target, or persistence if missing |
| Profile | Latest value plus the average daily change learned from fitting ponds |
| Ridge | Linear regression on the history, with fitted residual quantiles |
| Boosted trees | One quantile model per horizon and quantile |
| GRU and TCN | Compact neural networks trained from scratch with quantile loss |

The learned models predict the change from the latest value.

## Changes from the pilot

| Pilot | This experiment | Reason |
| --- | --- | --- |
| 6 h history | 24 h | Six hours cannot contain a daily oxygen cycle |
| Compared with persistence | Compared with the strongest of three naive forecasts | Persistence is weak at longer horizons, where beating it alone means little |
| 5% gain required | 5% at +1 h, 10% at longer horizons | Longer horizons leave more structure to learn |
| Fixed error limits | Gain, per-pond and bias limits | Pond oxygen here varies far more than in the tank, so tank error limits do not transfer |
| No intervals | 90% interval coverage limits | Calibration ponds and dates are now available |

The limits are engineering choices. No farm operator has supplied an acceptable error.

## Selection and testing

Settings and stopping epochs are chosen on the two validation sets. A neural model must score at least 2% better than the best ridge or tree model to be selected. Otherwise the simpler model is kept. The calibration partition is opened only to calibrate the chosen model's intervals. The test partitions are scored once, after the choice and its calibration are recorded.

The interval calibration ponds also form the unseen-pond validation set at earlier dates. Their calibration is therefore slightly optimistic. Test ponds have no such overlap.

A 90% interval covers the sensor reading. It does not include the sensor's own error, which is [substantial](../data/carp.md#measurement-limits).

The point, interval and alert gates are separate. A model that fails one may still be used for the others, and the product must show which are available. The alert thresholds are diagnostics for this dataset and carry no biological claim.

## Validation results and amendment

Scores are error relative to the strongest naive forecast, as registered. Lower is better.

| Model | Score |
| --- | ---: |
| Persistence | 2.4147 |
| Yesterday | 1.4506 |
| Profile | 1.0833 |
| GRU, three-seed mean | 0.8684 |
| TCN, three-seed mean | 0.8662 |
| Ridge | 0.8654 |
| Boosted trees | 0.8611 |

A neural model needed 0.8439 or less. Neither reached it, so the registered rule selects boosted trees.

The four learned families make partly different errors. Their equal average scores 0.8418. This was found after the validation results were known, as the best of four blends tried, and it passes the 2% margin narrowly. On 22 November 2026, before calibration or test data were opened, it was adopted as the shipping candidate in [amendment.json](amendment.json). The acceptance limits did not change. The blend and the trees are both tested once, and only the blend can be released.

Validation already shows two risks. Dates after the fitting period are harder than new ponds, and gains there are near the limits at +1 h and +3 h. Uncalibrated 90% intervals cover only 75–84% of readings on those dates with the blend.
