# Dissolved oxygen pilot decision and inference contract

## Candidate decision

The Oman tank pilot keeps **DO-only persistence** as its baseline and demo fallback. Persistence forecasts the latest hourly dissolved oxygen (DO) value at either horizon. The research candidate is the **DO-only residual GRU**, with a separate checkpoint for each horizon. Both selected settings use hidden size 16 and learning rate 0.003. Seed 17 is the primary artifact. Seeds 29 and 43 are retained for evaluation of training variability.

| Horizon | Validation windows | Persistence MAE (mg/L) | Ridge MAE (mg/L) | GRU mean MAE (mg/L) | GRU mean improvement | GRU validation gates |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| +1 h, primary | 26 | 0.246824 | 0.244892 | 0.236942 | 4.00% | Seed 17 and the seed mean miss 5% |
| +3 h, secondary | 24 | 0.349044 | 0.336433 | 0.318983 | 8.61% | Seed 17 and the seed mean pass |

DO-only GRU had the lowest validation MAE at both horizons. Adding temperature and pH raised GRU mean MAE at both horizons. The measured CPU resource gates passed for the selected GRU and persistence. The primary validation miss closes the learned-model release decision for this pilot. The +3 h result merits a separate research estimate. Operational forecast availability remains disabled for this release. See the [ridge results](ridge.md#first-training-result), [GRU results](gru.md#first-dataset-training-result), and [CPU benchmark](cpu-benchmark.md#verified-host-results).

The [evaluation lock](pilot-evaluation-lock.json) identifies the exact prepared release, policies, development evidence, inference code and six GRU checkpoints. All six reproduced their saved validation forecasts on CPU within the recorded tolerance. Checkpoints and run outputs stay in the local ignored run directories. The lock identifies the original bytes. A regenerated checkpoint is a new artifact whenever its digest differs.

## One-time final evaluation

The final evaluation is a descriptive research comparison of the frozen DO-only GRU against persistence. Score the complete horizon-specific `test` cohort for +1 h and +3 h separately, with 22 and 20 expected windows respectively. Use the frozen evaluation index and match forecasts and observed targets by window ID. Persistence and all three GRU replicas receive the same six eligible historical bins for each window. Use CPU inference with the frozen fitted transforms and unmodified point outputs. Use the common-horizon subset as a paired diagnostic.

Before scoring, verify the release manifest, policy and artifact hashes against the committed lock, and confirm that the execution path reproduces the bound validation forecasts within the documented CPU tolerance. Publish per-window forecasts, errors and coverage counts together with per-seed MAE, RMSE, signed bias and skill against persistence. Report seed means and ranges, mean absolute per-seed bias for gating, and paired absolute-error differences against persistence. Apply the existing accuracy limits to seed 17 and the seed mean, with complete coverage required for every replica. Report the lower-DO subgroup using the frozen training-only threshold in the lock, with its own denominator and coverage.

Report both horizons and every registered replica together. Treat missing or invalid forecasts under the frozen coverage rules and record any failed evaluation attempt. Once test results are exposed, any rerun must disclose the prior exposure and the reason. Calibration stays reserved, and interval release is deferred. This evaluation leaves the recorded +1 h validation result in force. The lock was prepared before final scoring using the [frozen evaluation protocol](evaluation-protocol.md) and [acceptance criteria](release-criteria.md).

## Final evaluation result

The evaluation ran once on 22 November 2026, after the evaluator was committed as `ad53d3c`. All 21 locked files matched. The saved validation forecasts were reproduced within 9.6e-7 mg/L. Persistence and all three seeds returned a forecast for every window. No earlier attempt scored test data.

| Horizon | Windows | Forecast | MAE (mg/L) | RMSE (mg/L) | Signed bias (mg/L) | MAE improvement |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| +1 h | 22 | Persistence | 0.4035 | 0.6578 | -0.018 | |
| | | GRU seed 17 | 0.3946 | 0.6257 | -0.095 | 2.2% |
| | | GRU seed 29 | 0.3918 | 0.6239 | -0.091 | 2.9% |
| | | GRU seed 43 | 0.3934 | 0.6242 | -0.094 | 2.5% |
| +3 h | 20 | Persistence | 0.6385 | 1.0094 | -0.167 | |
| | | GRU seed 17 | 0.6301 | 0.9373 | -0.296 | 1.3% |
| | | GRU seed 29 | 0.6327 | 0.9286 | -0.328 | 0.9% |
| | | GRU seed 43 | 0.6091 | 0.9095 | -0.333 | 4.6% |

The candidate fails both horizons. Seed 17 and the seed mean miss the 5% improvement gate at +1 h and +3 h. The mean absolute bias at +3 h is 0.319 mg/L, above its 0.30 limit. The +3 h validation pass did not carry over to the test period. Persistence and the GRU both have larger errors on the test period than on validation. The lower-DO subgroup has one target at +1 h and none at +3 h, so it provides no usable evidence.

The calibration partition remains unused. Any further scoring of these test windows must state that they were exposed on this date. Reproduce the checks without scoring with `python -B -m ml.evaluation.pilot_final --check-only` in the model environment. Outputs are in `ml/runs/pilot-final/`, and `run.json` has SHA-256 `2ba8831f5763bb6e61e3cecfe1ec7250fed892d0f10c2832e6d15146f92c4055`.

## Forecast interface v1

The Go backend will call the internal Python service with `POST /v1/forecasts` and a JSON body. The operation computes a point forecast without writing records. Go owns authorization, trusted observation assembly and forecast history. The Python service owns history readiness checks, configured artifact loading, inference and forecast identity. Both pilot profiles are restricted to authorized research replay of the frozen Oman tank context. Go returns `model_unavailable` for operational forecast requests under the current release policy.

| Request field | Contract |
| --- | --- |
| `profile` | Required. `persistence` or `research_gru`. A caller explicitly requests persistence when using the demo fallback. |
| `horizon_hours` | Required integer, `1` or `3`. |
| `issue_time` | Required UTC timestamp ending in `Z`, aligned to the hour. It is the last bin's availability time. |
| `requested_at` | Required UTC timestamp ending in `Z`. For authorized replay, Go supplies the original or simulated historical request time. |
| `history` | Six adjacent approved hourly aggregates, oldest first. Every bin belongs to the same recording and to a single development partition (`train` or `validation`). |

Each history entry carries `observation_id`, `available_at`, `partition`, `session_id`, `source_sha256`, `lineage_group_id`, `preparation_imputed`, `do_mgL`, `do_mgL_eligible` and the `do_mgL_` quality fields `covered_minutes`, `valid_rows`, `invalid_rows`, `maximum_gap_seconds` and `end_age_seconds`. Numeric values must be finite JSON numbers. Booleans use JSON booleans. Go populates provenance and quality fields from the approved records. Python validates the pilot context and history against the locked criteria. End timestamps refer to hourly intervals `[available_at - 1 hour, available_at)`. History contains only observations available by the issue time.

The history check requires at least 54 supported minutes per bin, at least three readings per supported minute, gaps of at most 180 seconds and a bin-end reading age of at most 60 seconds. The inclusive request delay is 0–60 seconds from issue and the latest reading age at request is at most 120 seconds. A target at `issue_time + horizon_hours` describes the hourly DO aggregate ending at that time. The forecast response keeps the original issue and target times when Go caches or displays it later.

A successful `200` response has the following shape. The numbers and times are illustrative. The `model_version` for research GRU is `compact-do-gru-v1:` followed by the selected seed 17 checkpoint SHA-256 for the requested horizon.

```json
{
  "status": "ok",
  "profile": "persistence",
  "model_version": "persistence-v1",
  "release_id": "oman-do-pilot-data-v1",
  "scope": "research_replay",
  "configuration": "do_only",
  "issue_time": "2025-03-29T12:00:00Z",
  "target_time": "2025-03-29T13:00:00Z",
  "horizon_hours": 1,
  "point_mgL": 7.2,
  "input_quality": {"inputs_ready": true, "reasons": []},
  "prediction_interval": null
}
```

Failures use `{"error":{"code":"history_unavailable","message":"The request is outside the issue window.","reasons":["stale_issue"]}}`, with a stable top-level error code and a `reasons` array, which may be empty. A `400` with `invalid_request` means malformed JSON, invalid field types or an unsupported profile or horizon. A `422` with `history_unavailable` means a well-formed request has unusable history, with the underlying readiness codes in `reasons`. Use `unsupported_partition` for calibration or final-test histories. A `503` means `model_unavailable` for a missing, invalid or disallowed artifact, or `prediction_unavailable` if inference fails or produces a negative or non-finite result. Error responses contain no point estimate. The result always identifies the profile that produced it, and uncertainty remains `null` pending calibration evidence.
