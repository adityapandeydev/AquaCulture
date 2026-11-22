# CPU inference benchmark

This benchmark measures persistence, selected ridge models and primary-seed GRU checkpoints on the same validation histories. It fits no parameters, changes no model selection and reads no calibration or final-test targets. Resource gates are reported separately from accuracy and model qualification.

## Run

From the repository root in PowerShell:

```powershell
$modelPython = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-models-v1/Scripts/python.exe'
& $modelPython -B -u -m ml.evaluation.cpu_benchmark --output ml/runs/cpu-new
```

The defaults bind `ml/runs/ridge-first` and `ml/runs/gru-first`; use `--ridge-run` and `--gru-run` for another completed pair. Each invocation requires a new output directory. `--dry-run` verifies release/run/model bindings and prepares inputs without spawning inference workers or measuring performance. A dry run can use the preparation environment without PyTorch.

The runner verifies the approved release, training-source fingerprints, selected artifact/case hashes and completed experiment outputs. It rejects changed files, paths outside the declared run/repository, incomplete selected cases and forecasts that do not cover the exact validation window IDs. GRU uses seed **17**, the predeclared primary artifact; CPU measurements do not select a different seed.

## Measurement scope

Each of the twelve combinations—three model families, two feature configurations and two horizons—runs sequentially, in separate CPU worker processes. BLAS/OpenMP thread environment variables are set to one before importing numeric libraries. PyTorch intra-op and inter-op threads are also one, checkpoint loading maps tensors to CPU, and CUDA devices are hidden in worker environments. The GPU is not used for inference measurements.

- **Fresh-process startup:** three independent interpreter launches per candidate. Each loads the input/model and produces a first forecast. Both worker-internal import/load/first-prediction time and parent-measured process start-to-exit time are saved. The gate conservatively uses the slowest complete process time, including result serialization and shutdown. Fresh process does not mean an empty OS disk cache.
- **Warm model-only latency:** 20 warmups, then 100 timed single-window predictions, cycling across all validation histories. Inputs are already numeric arrays or CPU tensors. Required fitted normalization remains inside the model. Runtime invocation and conversion to a physical-unit NumPy result are included. Median, p95 and individual samples are saved.
- **Hourly-history preprocessing plus model:** the same warmup/repetition counts, starting from six timestamped hourly-bin dictionaries. This includes timezone/cadence checks, feature ordering, finite-value/nonnegative-DO checks, numeric/tensor assembly and prediction. These are previously approved hourly bins; upstream sensor calibration, quality screening, aggregation, network JSON parsing, HTTP and database work are outside this measurement.
- **Batch throughput:** batch size 32, 20 warmups and 100 timed batches. Validation histories repeat cyclically to reach 32; this measures execution throughput and adds no independent environmental observations. It uses runtime-ready model inputs, not the dictionary preprocessing path.
- **Memory:** baseline RSS before numeric/model imports, current RSS and OS high-water peak RSS after inference. The gate uses the largest peak across all cold and warm workers, including runtime-library memory. Windows uses `GetProcessMemoryInfo`; Linux uses `/proc` and `getrusage`. Unsupported systems fail rather than inventing a memory estimate.
- **Artifact size and parameters:** size includes the selected parameter/transform file and its case metadata; it excludes installed framework libraries. Persistence has no parameter artifact. Parameter counts are measured from the loaded model. Runtime/framework memory is still counted in process RSS.

Warm runs check every CPU forecast against the bound development prediction before timing. Cold runs check the first prediction. Both use relative tolerance `1e-6` and absolute tolerance `1e-5 mg/L` for CPU/GPU floating-point differences. No saved observation target is used to repair predictions or update weights.

These measurements characterize the research inference path on the named host, not the full production service or field ingestion system. A CUDA-enabled PyTorch wheel can execute entirely on CPU while retaining a larger runtime memory/disk footprint than a dedicated CPU deployment package; this benchmark reports the installed runtime rather than extrapolating another package's performance.

## Outputs and gates

Generated files remain local under the ignored `ml/runs/` directory. `summary.csv` provides one row per candidate; `run.json` records the protocol, release/source/run hashes, exact validation window IDs, worker results and output checksums. Per-candidate input/result JSON files preserve numerical references, all three cold trials, latency samples, runtime/package versions, CPU identity, thread settings and memory values. A failed worker records a failed run; an existing directory is never overwritten.

The frozen limits are p95 model-only **100 ms**, p95 preprocessing-plus-model **150 ms**, fresh-process startup **15 s**, primary artifact plus transforms **10 MiB**, peak RSS **1,024 MiB**, batch-32 throughput **100 windows/s** and at most **10,000 trainable parameters**. No limit is relaxed after seeing results. All resource results retain `model_qualified: false`; final evaluation and the independent accuracy gates remain outstanding.

In particular, the [GRU validation review](gru.md#first-dataset-training-result) records a failed primary +1 h improvement gate. Fast inference cannot compensate for it, and a resource pass does not unlock held-out data or qualify broader fish/shrimp use.

## Verified host results

The 9 November 2026 `cpu-verified` run used a **12th Gen Intel Core i7-12700H**, Windows, Python 3.10.11, NumPy 2.2.6 and PyTorch 2.9.1+cu126 for GRU. Worker threads were fixed to one and GRU tensors stayed on CPU. All twelve candidate/configuration/horizon combinations passed the frozen resource gates. Values below span the four cases within each family; cold-start values are each case's slowest of three fresh-process trials.

| Family | Model-only p95 (ms) | History preprocessing + model p95 (ms) | Cold process time (s) | Peak RSS (MiB) |
| --- | --- | --- | --- | --- |
| Persistence | 0.0005–0.0006 | 0.0120–0.0150 | 0.326–0.339 | 28.2–28.5 |
| Ridge | 0.0062–0.0067 | 0.0184–0.0204 | 0.325–0.343 | 28.4–28.7 |
| GRU, seed 17 | 0.1808–0.2209 | 0.2422–0.2776 | 2.316–2.405 | 475.7–476.2 |

GRU batch-32 model throughput was approximately 149,000–167,000 windows/s on repeated prepared inputs, with primary artifact plus case metadata below 0.046 MiB. This measures a tiny model's compute path, not sensor-ingestion or service throughput. The runtime accounts for most of GRU's measured memory; the benchmark supplies no reason to increase model size or relax any accuracy requirement.

All recorded output checksums and source fingerprints were verified, CPU/development prediction parity passed, and GRU workers reported CPU placement and one intra-op/inter-op thread. The run's `run.json` SHA-256 is `8994dabac2a8294c866531da2f65b14d999aa361f11067701fa3fcc9f71bb545`. The full local record is `ml/runs/cpu-verified/`; generated payloads, timings and models remain excluded from Git. No weights were trained, no candidate was promoted and no held-out evaluation occurred.
