# Hourly aggregation and missing-data policy

Version: `oman-hourly-v1`, 2026-11-05. This policy applies to the restricted Oman candidate sessions. It completes the preparation rules in readiness task 10; it does not approve training or establish sensor accuracy.

## What an hourly value represents

The first experiment uses summaries of measured DO, water temperature and pH. Each UTC hour is a half-open interval: `[09:00, 10:00)` is labeled and available at 10:00. A reading at exactly 10:00 belongs to the following hour. Oman timestamps use the documented GMT+4 offset before conversion to UTC; the hour boundaries also align in local time.

Within each hour, each minute needs at least three screening-valid readings. Its value is their median. The hourly value is the equally weighted mean of those supported minute medians. This reduces the influence of unequal sampling density and isolated spikes while keeping the original measurements, extrema and diagnostic flags available for inspection. It deliberately changes the prediction target from high-frequency readings to an observed-minute hourly summary. It is not an instantaneous measurement, a complete continuous-hour integral or proof that the underlying water conditions were smooth.

The observed source cadence is approximately several seconds, so a minute normally contains multiple readings. Three readings provide minimal support for a median; they do not establish measurement accuracy. Hourly cadence follows the first experiment's candidate horizons and keeps the target contract manageable. A different cadence or reducer requires a separately versioned policy and a consistent benchmark; choices must not be tuned on final test errors.

## Coverage and freshness requirements

Every channel is checked independently within its own session:

| Rule | Requirement |
|---|---|
| Supported minute | At least 3 screening-valid readings |
| Hour coverage | At least 54 of 60 supported minutes (90%) |
| Largest observation gap | At most 180 seconds between valid readings, including the hour's leading and trailing edges |
| Freshness at availability | Last screening-valid reading at most 60 seconds before the hour ends |
| Source/session | No aggregation across source or session boundaries |
| Session exclusion | An excluded session cannot supply candidate inputs or targets even when its bins pass numeric checks |

These are conservative experimental limits, not manufacturer specifications, biological thresholds or thresholds learned from forecast accuracy. The coverage gate prevents a dense short burst from representing an hour. The gap gate limits internal outages, and the final-age gate prevents an otherwise populated hour from ending on stale data. Leading/trailing partial hours receive the same checks as every other hour.

The 180-second gap allowance does not interpolate across that gap. The covered-minute requirement still applies. Gaps are measured using all screening-valid readings, including readings in minutes with fewer than three observations; those sparse minutes do not contribute to the hourly value.

## Missing inputs and targets

There is no interpolation, forward fill, backward fill, smoothing across hours, learned imputation or normalization in this policy. Empty internal hours remain explicit rows. Invalid observations do not contribute to minute summaries or count as coverage.

An hour that fails any coverage, gap or freshness requirement has a missing usable `value`. Its diagnostic `measured_mean`, observed minimum/maximum, valid/invalid counts and rejection reasons remain available. `measured_mean` means the summary of supported minutes; it is not permission to use an inadequately observed hour as a label.

Historical inputs require eligible bins for every required channel. DO-only inputs depend on DO; multivariate inputs require eligible DO, temperature and pH for the same bin. A missing optional sensor therefore need not remove a DO-only example. The later window builder must reject a history containing a required missing bin, stay inside one session and use only bins available by the forecast issue time. Missingness flags describe coverage; they do not manufacture substitute sensor values.

Targets require an eligible measured DO bin at the requested future hour. Missing targets are excluded from evaluation and reported in coverage counts. There is no substitute label from an adjacent hour or a model estimate. Paired DO-only/multivariate comparisons must use common eligible target examples, as specified in the [experiment contract](experiment-spec.md).

Each retrospective forecast issue is anchored to its latest completed input hour. An older hour is not carried forward to impersonate a new issue. The 60-second observation-age limit applies at that hour's end. Actual ingestion delays are unavailable, so these experiments assume observations were available at their recorded timestamps. Production scheduling, late arrivals and abstention behavior need separate implementation and validation.

## Treatment of quality flags

Screening-invalid observations and previously excluded sessions remain excluded. Valid zeros, abrupt changes and exact plateaus remain measured observations with review annotations. Each hourly channel row reports how many valid readings carry each review flag; categories can overlap. The observed minimum and maximum include valid readings in sparse minutes too.

Automatic removal of these flags is not justified by the available reference-meter evidence. The diagnostic rate thresholds flag some readings in every otherwise eligible DO hour. A blanket rejection would leave no DO hours, rather than demonstrate that all measurements were faulty. The export includes `review_free_eligible` as a diagnostic counterfactual, not an approved alternative data release. Calibration uncertainty and possible sensor noise remain limits on later conclusions.

An hourly summary can hide a brief low-oxygen excursion. Raw observations and extrema are preserved, but this release does not turn an hourly forecast into a validated event detector or aerator-control recommendation.

## Results on the reviewed sessions

The preparation run exports 798 channel/hour rows across seven sessions, including traceable diagnostics for the excluded ordering-review session. The two input configurations have the same candidate counts under this policy:

| Context | DO-only hours | DO + temperature + pH hours |
|---|---:|---:|
| Pond, eligible session candidates only | 58 | 58 |
| Controlled tank | 188 | 188 |

The pond contribution is 42, 11 and 5 hours from three continuity groups. The remaining candidate fragments contribute none. The excluded ordering-review group contributes no candidate hours. The tank contribution comes from the main tank group.

Changing only the minimum covered-minute requirement to 48 (80%) or 57 (95%), while retaining the same gap/freshness checks, produces the same counts. This local sensitivity check does not prove that the thresholds generalize. Every candidate DO hour contains at least one diagnostic review flag; no hour qualifies for the review-free counterfactual.

These are eligible hourly summaries under preparation rules, not independent examples, frozen train/test counts or evidence of enough data for every history and horizon. Task 11 will select the first data release and quantify usable windows. Task 12 will freeze partitions, and task 13 will enforce the supervised-window contract.

## Reproduction and checks

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_aggregation -v
.\.venv\Scripts\python.exe -m ml.data.aggregation --output Datasets/processed/oman-aggregation-new-run
```

Completed output: `Datasets/processed/oman-aggregation-2026-11-05/`.

- `hourly_channels.csv.gz`: values, coverage, diagnostic summaries, session exclusions and rejection reasons by channel/hour.
- `hourly_configurations.csv`: simultaneous eligibility by input configuration and session/hour.
- `aggregation.json`: exact policy settings, input hashes, channel/configuration counts and coverage sensitivity results. Training approval remains false.

The command checks raw hashes against the session inventory, one-to-one joins to quality flags, complete row accounting, configuration channel completeness and unchanged inputs during processing. It refuses an existing output directory. Tests cover hour boundaries, availability, missing targets, empty hours, dense bursts, long gaps, stale endings, minimum minute support, invalid readings, zero preservation, review flags, unequal sampling density, future-value isolation and session isolation. Raw files and previous preparation outputs remain unchanged.
