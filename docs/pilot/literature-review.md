# Literature review for the first forecasting experiment

Review date: 2026-11-05. This first pass covers two forecasting papers and one field study from the project's paper list, a publisher preview relevant to the supplied shrimp workbook, and an additional uncertainty-method reference. It is not a review of all 29 entries.

Full-paper text was available for the two forecasting studies through the supplied Drive links. The field study and uncertainty paper were accessible from their publishers. Findings below distinguish reported results from implications for this project. No reported score is a performance claim for AquaCulture.

## Evidence table

| Reference | Access and study type | Data, cadence and horizon | Evaluation and preparation | Relevance and limitation |
|---|---|---|---|---|
| **R1. Haq & Harigovindan (2022)**, [Water Quality Prediction for Smart Aquaculture Using Hybrid Deep Learning Models](https://doi.org/10.1109/ACCESS.2022.3180482). [Supplied full paper](https://drive.google.com/file/d/1Un7rK0M4dKkgoGlGaaZYhQJCzKdeWgrN/view). | Full text; forecasting. Locators: §III.D, §IV.A–D, §V. | ADAK: 1,096 daily samples; MAC: 23,200 samples, described as five-minute collection over 80 days. Salinity, pH, DO and temperature. Multistep experiments use 2–12 steps. Species-level validation is not established. | Reports an 80/20 split, min–max scaling, interpolation/smoothing and sliding windows. Compares CNN/LSTM/GRU hybrids and attention variants; reports MAE/MSE/RMSE/MAPE and computation time. | Supports testing compact CNN–recurrent candidates. A step is a different duration in each source. Raw-data download was not established in this review; MAC points to reference [16], Liu et al. (2020). Scaler fitting scope, a distinct tuning set and causal preprocessing need verification. The described timing example is training time, not service latency. No calibrated intervals established. |
| **R2. Yang & Liu (2021)**, [A prediction model of aquaculture water quality based on multiscale decomposition](https://doi.org/10.3934/mbe.2021374). [Supplied full paper](https://drive.google.com/file/d/1dJOEieXZrthqQMpnQq_sUupZD7XQp74P/view). | Full text; single-step forecasting. Locators: §§3.1–3.4, Table 2, Eqs. 3.2–3.4. | Yantai aquaculture: 1,024 DO observations at ten-minute cadence; 634 hourly pH observations. The stated nine-day DO period does not explain the separate pH coverage. | Reports an 80/20 split. CEEMDAN decomposition, entropy-based recombination and LSTM prediction; autocorrelation selects history. Table 2 gives DO MAE 0.1026/RMSE 0.1210 and pH MAE 0.0189/RMSE 0.0107. | The pH pair is inconsistent with the paper's same-sample definitions. Recombination/decomposition fitting scope needs a causal audit; leakage is a risk, not a demonstrated fact. No raw download or calibrated uncertainty result was established. Useful as an optional architecture hypothesis, not an accuracy target. |
| **R3. Venkateswarlu et al. (2019)**, [Water quality in L. vannamei farms in coastal Andhra Pradesh](https://www.fisheriesjournal.com/archives/2019/vol7issue4/PartF/7-4-64-509.pdf). | Full text; observational field study, not forecasting. Locators: pp. 394–396, Table 1, §§3.2–3.3. | 320 farms across four districts, February–June 2019; brackish-water L. vannamei. Samples collected at 6–7 a.m. Published sampling details do not supply a continuous hourly benchmark. | Reports laboratory/instrument measurement procedures, including buffer calibration for pH. Provides descriptive measurements and recommended ranges; no train/test split or prediction metrics. | Supports recording species, salinity, sampling time and measurement method. Its recommendations are context-specific rather than universal fish/shrimp thresholds. No downloadable per-farm time series was established. |
| **R4. Sowmiya et al. (2023 online; 2024 volume)**, [Tiny ML-based reconfigurable IoT platform design for brackish water aquaculture monitoring](https://link.springer.com/article/10.1007/s11276-023-03537-9). | Publisher abstract/metadata only; full text unavailable in this pass. Related to the supplied buoy dataset by author/topic; row-level dataset identity remains unverified. | Preview describes brackish-water shrimp sensing and an ARLSTMIMA forecasting method. Channel units, sampling cadence and exact horizons cannot be verified from the preview. | Abstract reports “95.16” efficiency/accuracy, but its metric definition, split, calibration and comparable timing are unavailable. Publisher states data are included in the manuscript and code availability is not applicable. | Does not justify interpreting the workbook's DO as mg/L or using its pH conversion. No verified accuracy benchmark or calibration recipe is adopted. Full-text access or another primary technical record remains a calibration follow-up. |
| **R5. Xu & Xie (2021)**, [Conformal prediction interval for dynamic time-series](https://proceedings.mlr.press/v139/xu21h.html), [full paper](https://proceedings.mlr.press/v139/xu21h/xu21h.pdf). | Full paper inspected for interval construction and assumptions; additional methods reference outside the original list. Locators: §3, Algorithm 1, §4.1–4.2. | General time-series regression; renewable-energy examples, not aquaculture validation. EnbPI constructs sequential intervals around bootstrap ensembles. | Approximate marginal coverage depends on assumptions about errors and estimation quality. The paper distinguishes its practical construction from a universal finite-sample coverage guarantee. | Supports evaluating interval coverage and width under dependence. It does not establish fish/shrimp transfer or calibrated per-event probabilities. Residual updates must respect when the future measurement actually becomes available. No method is selected before comparing it on our data. |

## Corrections and unresolved questions

### The pH metric inconsistency is in the original paper

R2's Table 2 contains the same MAE/RMSE inconsistency as the spreadsheet summary. For the same finite errors with the same weighting, root mean squared error cannot be below mean absolute error. The paper does not explain a different basis for that pair. The values will remain an unresolved reporting issue rather than being swapped or corrected by assumption.

The nine-day statement and 634 hourly pH samples also require separate coverage evidence. They are not sufficient grounds to reconstruct missing timestamps.

### Published preprocessing is not automatically suitable for deployment

R1 mentions interpolation and smoothing, but that is not enough detail to establish that no future observations entered preprocessing. R2 describes decomposition of the original series without establishing an issue-time implementation in the passages reviewed. These are methodological uncertainties, not findings that the authors definitely leaked data.

For this project, transformations must be reproducible using information available at each forecast issue time. A noncausal preprocessing method is eligible only if reformulated and evaluated causally. Test labels remain reserved even when a paper uses its test set repeatedly to compare settings.

### Forecast steps and runtime measures need explicit definitions

Daily and five-minute recordings do not support the same real-time warning claims. We will compare candidates using physical forecast durations and the same held-out observations. Training time, model-only inference time and end-to-end preprocessing/inference time are separate measurements.

The supplied review's broad claim that a hybrid always wins is too strong. R1's result discussion includes accuracy/runtime tradeoffs involving attention models. Its architecture is a candidate to reproduce fairly, not a predetermined winner.

### Confidence requires a defined calibration protocol

An accuracy percentage from an abstract cannot become a per-forecast confidence score. Candidate intervals require measured coverage, width and sample counts by horizon and source. Any sequential recalibration may use only target measurements that have actually arrived; long-horizon residuals cannot update earlier forecasts prematurely. An online-update experiment and a frozen-calibration experiment will be reported separately.

## Decisions carried into preparation

1. Keep raw measurements and real excursions; document every rejection, conversion and filled input. Published smoothing is not a reason to remove difficult events.
2. Express horizons in elapsed time and state whether the target is an interval average, instantaneous value or minimum. Match history and target availability to each session's coverage.
3. Fit learned transforms and select history/features on development data. Any decomposition or rolling summary needs an issue-time leakage test.
4. Compare persistence, compact lag-feature models and small sequence models on identical eligible targets. Architecture complexity and uncertainty methods remain experimental.
5. Keep species, production environment and measurement method in source metadata. Do not derive a universal fish/shrimp alert threshold from a single regional field study.
6. Retain a calibration/evaluation boundary and document any permitted online updates. Confidence claims require their own measured evidence.

These decisions refine [the experiment specification](experiment-spec.md); they do not approve any dataset or start model training.

## Follow-up work

- The source/reuse review will classify dataset availability and licensing independently of whether a paper is readable.
- The shrimp calibration review still needs a primary description connecting sensor channels, conversions and deployment sessions. The R4 preview cannot resolve it.
- The MAC reference in R1 is a dataset-discovery lead, not a newly acquired dataset.
- Additional papers will be reviewed when they resolve a specific data or evaluation decision; the remaining entries are not prerequisites merely because they appear in the spreadsheet.
