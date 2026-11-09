# Compact GRU training

The GRU learns a correction to the latest observed dissolved oxygen from six hourly bins. It uses newly initialized recurrent weights, a single recurrent layer and a scalar linear head. A zero-initialized head starts at persistence; training learns the correction. It uses neither pretrained parameters nor the application's existing TensorFlow weights.

## Run in PowerShell

From the repository root, with the [separate model environment](development.md#gpu-environment-on-this-system) installed:

```powershell
$modelPython = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-models-v1/Scripts/python.exe'
& $modelPython -B -u -m ml.training.gru --matrix --output ml/runs/gru-first
```

The runner requires CUDA and stops if preflight fails. It never substitutes CPU training. Each epoch prints training MAE, validation MAE, elapsed time and checkpoint improvements. `--matrix` covers both input configurations and both horizons: four cases, four settings per case and three seeds, totaling 48 fits. Omit `--matrix` for only the configuration/horizon in `do_pilot.json`. Use a fresh output directory for every invocation.

On this Windows system, the user-profile environment is installed and CUDA execution was verified on the RTX 3050 Ti with PyTorch 2.9.1+cu126. Verification used synthetic training, checkpoint roundtrips and a full synthetic experiment, plus a real-release matrix preflight. Dataset training is launched with the command above.

For a data/configuration preflight without PyTorch, GPU initialization, fitting or scoring:

```powershell
$prepPython = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $prepPython -B -u -m ml.training.gru --matrix --dry-run --output ml/runs/gru-check
```

The notebook `ml/notebooks/08_gru_training.ipynb` calls the same function. Run it in the model-environment kernel; it contains no duplicate model or training implementation.

## Architecture and transforms

Inputs have shape `[examples, 6, features]`, ordered oldest to newest, with DO first and temperature/pH following when available. Per-channel means and population standard deviations are fitted only on flattened **training histories**. Overlapping windows therefore contribute repeated historical values to this transform; validation never updates it. Constant channels receive unit scale and exact centering. The model stores these transforms as buffers in the checkpoint.

The forward calculation standardizes inputs, passes them through `GRU(..., num_layers=1, batch_first=True)`, and maps the final hidden state through a linear head. The predicted correction is multiplied by the training DO standard deviation and added to the latest measured DO. Predictions remain in mg/L. Outputs are not clipped; invalid or negative validation forecasts make an epoch ineligible for checkpoint selection.

The four registered settings combine hidden sizes **8/16** with AdamW learning rates **0.001/0.003**. All use weight decay 0.01, batches of 16, gradient norm clipping at 1, and mean squared forecast error divided by the squared training DO standard deviation. This is equivalent to squared normalized-change error because the persistence term is added explicitly. Canonical arrays and scoring preserve float64 measurements; model tensors and optimizer calculations use float32. There is no mixed precision, bidirectionality, pretrained encoder or cross-window hidden-state carryover.

The largest model has 1,025 trainable parameters with three inputs, below the frozen 10,000-parameter limit. Small size is appropriate to this limited pilot; it does not establish forecast skill or field reliability.

## Checkpoints and selection

Each setting trains seeds **17, 29 and 43**. A fit runs at most 100 epochs and stops after 15 consecutive epochs without strictly improved complete-cohort validation MAE. It saves and restores the best epoch, rather than the last epoch. The 600-second budget is checked at epoch boundaries and after restoration; it is not a preemptive process timeout. A budget failure disqualifies the replica even if a partial checkpoint exists.

Settings are ranked by the mean of all three complete validation MAEs, then parameter count and registered order for exact ties. A failed or incomplete replica disqualifies its setting. Seed 17 always supplies the primary artifact; the three replicas are not an ensemble, and the best individual seed cannot replace it. Per-seed errors, mean/range and mean absolute per-seed bias remain visible. Validation error gates apply separately to seed 17 and the seed mean, with complete predictions required for every replica. These checks do not qualify the model: CPU resource measurements and locked final evaluation remain separate.

Python, NumPy and PyTorch RNGs are seeded for every fit. The batch permutation uses an explicitly seeded generator. Deterministic algorithms are required, cuDNN benchmarking and TF32 are disabled, and `CUBLAS_WORKSPACE_CONFIG` is set before CUDA preflight. These controls support repeatability on the recorded runtime; bitwise identity across different PyTorch/CUDA versions or devices is not promised. See PyTorch's [GRU API](https://docs.pytorch.org/docs/2.9/generated/torch.nn.GRU.html) and [reproducibility guidance](https://docs.pytorch.org/docs/2.9/notes/randomness.html).

## Saved files and failure handling

Each configuration/horizon contains `trial_XX/seed_YY/best.pt`, `epochs.jsonl` and per-replica predictions. `progress.json` records the latest completed replica, `trials.json` records all settings and `case.json` binds the selected setting to feature order, window IDs, metrics and gate results. Selected checkpoints are copied to `selected_seed_17.pt`, `selected_seed_29.pt` and `selected_seed_43.pt`.

Root `run.json` records code, data, policy and settings hashes, runtime information, planned cases and output checksums. `predictions.csv` and `metrics.csv`/`metrics.json` compare each selected replica with both baselines on the same cohorts, with explicit seed labels. Baseline rows are repeated per seed for pairing; they are not extra independent observations. The progress log is flushed each epoch. All generated artifacts stay in the Git-ignored run directory.

Checkpoint files contain tensors and primitive metadata, loaded explicitly with `weights_only=True`, strict state shapes and finite-value checks. Use `ml.modeling.gru.load_checkpoint(path, device='cpu')` for CPU inference; keep its case/run metadata alongside it to preserve horizon, feature order and release bindings. Checkpoints contain the selected model and transforms, not optimizer/RNG state; interrupted runs are restarted in a new directory, not resumed mid-fit.

Numerical and time-budget failures are recorded per replica. CUDA/device/runtime failures abort with an error, leaving the experiment incomplete rather than silently changing its execution policy. Only a `development_gru_completed` run with verified outputs represents a completed experiment. It still has no calibrated confidence or production approval. Calibration and final-test partitions remain locked throughout training and selection.
