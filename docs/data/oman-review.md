# Oman recording and calibration review

Review date: 2026-11-05. Status: restricted preparation candidate, not training-approved. Raw files and existing cleaned outputs remain unchanged.

## Time basis and recording periods

The pinned repository's `docs/data_dictionary.md`, §§1.1–1.2, explicitly describes both raw timestamps as local Oman time, GMT+4. This supports a source-specific fixed-offset mapping in the later canonical adapter. Earlier generic outputs left UTC unknown; this audit does not rewrite them. Clock synchronization and receipt times are not independently established.

| Recording | Actual local date range | Raw rows | Decision |
|---|---|---:|---|
| Offline/pond | March 26–April 27, 2026 | 41,663 | Limit pond candidates to the README's stated March 26–April 1 period, containing 38,456 raw rows. Exclude the remaining 3,207 from the current pond experiment pending acquisition-context evidence. |
| Live/controlled tank | April 1–10, 2026 | 102,670 | Fits the documented period. Keep as a controlled 180 L tank recording, not an independent commercial pond or shrimp dataset. |

Both files use `node_001`, which does not establish independent sites. Offline source order has 23 backwards timestamp steps. No exact timestamp-plus-temperature/pH/DO vectors match across cleaned files, but that does not establish collection independence.

Existing conflict/deduplication rules retain 41,120 offline rows, including 37,913 in the stated pond period, and all 102,670 live rows. Conflicting timestamps stay excluded. Later unexplained records remain preserved, without relabeling them as pond or tank observations.

## Calibration evidence

| Channel | Evidence in downloaded JSON | Decision |
|---|---|---|
| pH | Two buffer voltages for pH 7 and 4, 15 readings per point, capture/settle times, temperature summaries and coefficients. Substitution reproduces approximately 7.0000 and 4.0000. | Declared calibrated input candidate. Arithmetic consistency does not establish accuracy outside those buffers, drift or deployment applicability. |
| DO | Declared mg/L column and zero/air-saturation voltage equation with temperature and saturation concentration. | Declared target candidate with limitations: raw voltages, dated deployment linkage, an independent reference meter and complete compensation history are absent from the acquired files. |
| Water temperature | Declared Celsius column; three-point correction's slope/intercept. | Input candidate. Underlying reference pairs and dated linkage to recordings are unavailable. |

Calibration times are device-relative counters or an ambiguous local value, not a complete calendar record. Counter ordering cannot establish calibration chronology across boots. No already-converted channel is converted a second time, and no replacement calibration is fitted.

The three numeric channels have no missing/non-finite raw values. Offline DO ranges 0–16.676 mg/L with seven zeros; live DO ranges 0–14.138 with two zeros. pH reaches 10.378 offline and 9.931 live. These require quality review, not automatic clipping to preferred pond ranges or interpretation as confirmed biological events.

## Coverage and candidate examples

Occupied five-minute subslots are counted inside hourly bins labeled at their end. Nine, eleven and twelve occupied subslots are sensitivity thresholds, not final acceptance rules. Subslot presence is not proof of valid coverage throughout each five minutes.

| Period after conflict/deduplication | Calendar bins | Populated bins | Bins with at least 11 of 12 occupied subslots |
|---|---:|---:|---:|
| Full offline file | 772 | 84 | 70 |
| Stated pond period | 149 | 74 | 65 |
| Live tank period | 211 | 192 | 188 |

Requiring 11 occupied subslots in every bin from input history through the forecast target gives:

| Environment | History | 1-hour horizon | 3-hour horizon | 6-hour horizon |
|---|---:|---:|---:|---:|
| Pond, stated period | 6 h | 42 | 37 | 31 |
| Pond, stated period | 12 h | 30 | 28 | 25 |
| Pond, stated period | 24 h | 18 | 16 | 13 |
| Live tank | 6 h | 182 | 180 | 177 |
| Live tank | 12 h | 176 | 174 | 171 |
| Live tank | 24 h | 164 | 162 | 159 |

These are overlapping window counts **before** train/validation/test/calibration partitions and further channel/session checks. They are not independent sample counts. Requiring intermediate horizon bins is conservative and remains subject to the gap-policy review.

The pond file supports preparation tests and a limited pilot comparison. Its current hourly coverage is insufficient as strong evidence for broad deep-model or cross-farm claims. Subhourly experiments could change resolution but cannot create independent days or farms. Additional traceable coverage is desirable.

## Decisions for further preparation

1. Restrict offline pond candidates to the documented initial period; keep unexplained later rows out of the current pond experiment.
2. Keep pond and tank environments separate. A pond-to-tank result is not unseen-farm or fish-to-shrimp validation.
3. Carry the documented GMT+4 evidence into the source-specific canonical adapter. Generic imports must not assume that timezone.
4. Preserve zeros and excursions with review flags; no comfort-range clipping or repeated calibration conversion.
5. Treat calibration JSON as supporting evidence, not independent accuracy validation.
6. Keep author aggregates/events separate from raw-target construction. Both raw `events` columns are empty; event-log timing and provenance need review before predictor use.
7. Keep training approval false until coverage rules, session quality, partition sufficiency and supervised-window checks pass.

## Reproduction and evidence

```powershell
.\.venv\Scripts\python.exe -m unittest ml.data.test_oman_audit ml.data.test_shrimp_audit ml.data.test_prepare -v
.\.venv\Scripts\python.exe -m ml.data.audit_oman --output Datasets/processed/oman-new-review
```

Completed output: `Datasets/processed/oman-review-2026-11-05-v2/`. The directory without `-v2` is an incomplete import attempt. Reports include source hashes, declared-period membership, calibration evidence, numeric summaries and hourly occupancy/window sensitivity. Sixteen focused tests pass. No model is fitted.

Evidence is from the checksum-pinned [author repository](https://github.com/AhmedTheNetCoder/DO-Forecasting-Tilapia-Dataset/tree/d95207b6f129c3de1f426ec90eed5a38f46832b8): README, data dictionary §§1.1–1.2, raw CSVs and calibration JSONs. The publisher returned HTTP 429 during this review; no additional measurement-validation claim is inferred from the inaccessible paper.
