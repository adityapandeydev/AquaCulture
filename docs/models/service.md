# Forecast service

A private Python service computes forecasts from the tested [blend](results.md). The Go backend will assemble hourly histories, call it and store the results. The service keeps no data and does not decide who may use it.

## Forecast request

`POST /v2/forecasts`

```json
{
  "species": "rohu_catla",
  "timezone": "Asia/Kolkata",
  "issue_time": "2026-01-24T00:30:00Z",
  "history": [
    {"start": "2026-01-23T00:30:00Z", "coverage": 1.0, "do_mgL": 5.41, "ph": 8.4, "temperature_c": 25.9}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `species` | Only `rohu_catla` is supported |
| `timezone` | IANA name of the pond's timezone, used for the hour of day |
| `issue_time` | End of the latest hour. It must fall on a whole local hour. India's is at half past in UTC. |
| `history` | Up to 24 hourly means, oldest first. Hours without data may be left out. |
| `coverage` | Share of the hour's expected DO readings that were valid. Below 0.75 the hour counts as missing. |

A forecast needs 20 of the 24 hours for each of DO, pH and temperature, and the latest three hours of DO. Missing hours are never invented by the caller. The caller checks that the data is fresh, because the service has no clock of its own.

## Forecast response

```json
{
  "model_id": "carp-blend-1",
  "manifest_sha256": "e3a10350…",
  "scope": "research_and_demonstration",
  "issue_time": "2026-01-24T00:30:00Z",
  "forecasts": [
    {
      "horizon_hours": 1,
      "point_mgL": 4.87,
      "interval_90": {"low_mgL": 3.60, "high_mgL": 6.21},
      "low_oxygen": {"threshold_mgL": 3.0, "probability": 0.0312},
      "withheld": [],
      "target_start": "2026-01-24T00:30:00Z",
      "target_end": "2026-01-24T01:30:00Z"
    }
  ],
  "warnings": []
}
```

The numbers are illustrative. There is one entry each for +1, +3, +6 and +12 hours. An output that failed its test is `null` and named in `withheld`. The decisions are stored in the bundle and cannot be overridden by a request.

| Warning | Meaning |
| --- | --- |
| `outside_training_range:<channel>` | A value lies beyond those seen during fitting |
| `outside_training_season` | The local month is not November, December or January |

A low probability is not a statement that a pond is safe.

## Errors

Errors have the form `{"error": {"code": "...", "message": "...", "reasons": []}}` and never include a forecast.

| Status | Code | Cause |
| ---: | --- | --- |
| 400 | `invalid_request` | Malformed body, value out of bounds, or invalid times |
| 401 | `unauthorized` | Missing or wrong service token |
| 411, 413 | `length_required`, `request_too_large` | Body without a length or above 64 KiB |
| 422 | `unsupported_species` | No model for this species, including shrimp |
| 422 | `history_unavailable` | Not enough history, with reasons |
| 503 | `model_unavailable` | No verified bundle is loaded |
| 503 | `prediction_unavailable` | The computation failed |

`GET /health` reports that the process is alive. `GET /ready` reports that a verified model is loaded. `GET /v2/model` describes the model.

This replaces the [pilot's proposed v1 contract](../pilot/pilot-closeout.md#forecast-interface-v1), which was never implemented. There is no compatibility between them.

## Model bundle

`ml.training.export` writes the bundle to `ml/bundles/carp-1`. Networks are ONNX files, and the tree and ridge models are plain arrays. Nothing in it executes on loading. [release.json](release.json) records every hash, and the service refuses a bundle that differs from it. Exported forecasts match the tested models within 1.3e-6 mg/L on all 2,657 validation histories. A further 300 histories sent through the service, including time conversion, matched to the three decimals returned.

## Rounding

Hourly means often lie exactly on a tree's split point. Rounding noise as small as 1e-13 can then choose the other branch, which moved some test forecasts by up to 0.11 mg/L. The service therefore rounds every input to 10 significant digits, as the prepared dataset was. This reproduces the tested forecasts exactly and removes noise from the caller. It does not change the model. A genuine small change in a reading can still cause a step of this size.

## Run

Python 3.10, from the repository root.

```powershell
$service = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-service/Scripts/python.exe'
& $service -B -m ml.service.app
```

It listens on `127.0.0.1:8100`. Set `MODEL_TOKEN` to require a bearer token. The service refuses to listen on other addresses without one. The environment is created from `ml/service/requirements.txt`.

## Performance

Measured on 22 November 2026 on an Intel i7-12700H that was about 78% busy with other work, over local HTTP with one compute thread per forecast.

| | Measured | Limit |
| --- | ---: | ---: |
| Single forecast, 95th percentile | 27 ms | 150 ms |
| Startup to first forecast | 1.1 s | 15 s |
| Peak memory | 97 MiB | 1,024 MiB |
| Bundle size | 3.9 MiB | 20 MiB |

Eight simultaneous callers received about 65 forecasts per second, with a 95th percentile of 241 ms. That exceeds 150 ms, but the limit applies to single forecasts. These figures exclude sensor ingestion and database work.

```powershell
& $service -B -m ml.service.benchmark --output ml/runs/service-benchmark-new.json
```
