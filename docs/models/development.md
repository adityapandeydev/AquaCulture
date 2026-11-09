# Model experiments: Python modules and notebook interfaces

The experiment foundation resolves the [approved DO release](../data/readiness-report.md) into training and validation arrays and records exact configuration, source and dataset hashes. The same Python functions serve the command line and notebook. The [baseline runner](baselines.md) adds development-only scoring; no learned model has been fitted.

## Code organization

```text
ml/
├── training/
│   ├── configs/do_pilot.json       # Versioned configuration, horizon, seed and GPU intent
│   ├── data.py                    # Anchored release loader and development arrays
│   ├── experiment.py              # Inspection/provenance CLI and notebook function
│   ├── runtime.py                 # Explicit CPU/CUDA preflight
│   └── tests/                     # Leakage, configuration and device-policy checks
├── notebooks/05_experiment_setup.ipynb
└── runs/                          # Generated metadata, later checkpoints/logs; ignored by Git
```

Forecast methods live in `ml/modeling/`, including the non-parametric baselines. Physical-unit scoring lives in `ml/evaluation/`. These modules share the contract and contain reusable logic. Notebooks import the functions and display results instead of duplicating training loops.

The current application still uses `ml/inference/` and its existing artifacts. New research code neither imports that predictor nor reuses its weights. The unused `ml/pipeline.py` manual runner and empty `ml/utils/preprocess_input.py` placeholder were removed after checking references. Existing notebooks are retained as experiment history until their relevant logic has a tested replacement. Cleanup proceeds with each replacement rather than deleting active application dependencies.

## Inspect a development experiment

From the repository root, the preparation environment can run this step without PyTorch:

```powershell
$prepPython = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-prep-v1/Scripts/python.exe'
& $prepPython -B -m ml.training.experiment inspect --config ml/training/configs/do_pilot.json --output ml/runs/foundation-check
```

Use a fresh output directory. The command verifies the exact published release manifest and artifact hashes, resolves the selected train/validation windows and records `config.json`, `prepared-release.json` and `run.json`. Console messages show verification, partition resolution and shapes. No scaler, model, baseline forecast or score is created.

The default DO-only/+1 h configuration resolves training `X=(94,6,1), y=(94,)` and validation `X=(26,6,1), y=(26,)`. Features remain in physical units as float32, without learned normalization. The multivariate feature order is DO/temperature/pH, with three columns; +3 h has 92 training and 24 validation examples. Only registered configurations, horizons and seeds 17/29/43 are accepted.

`PreparedRelease.development(...)` admits only `train` and `validation`. Calibration and final-test access is deliberately absent from this development API. This is a workflow guard, not a filesystem security system: the local dataset contains all frozen observations, but development code must not use held-out values for fitting or selection. A later final-evaluation interface will require locked run/model provenance.

Each run records exact development window IDs, feature order, shapes, configuration/descriptor/release digests, experiment/preparation source hashes, Python version and current Git revision. The Git revision alone is not sufficient for uncommitted code, so source hashes are retained as well. Generated runs stay outside commits under `/ml/runs/`.

## GPU environment on this system

Hardware inspected on 2026-11-09: **NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4,096 MiB VRAM, driver 610.62**. NVIDIA reports a working device, but that does not prove a Python framework can execute CUDA. PyTorch was absent from the existing project/preparation environment, so CUDA execution is not yet verified.

New neural experiments use PyTorch in a separate user-profile environment. The native-Windows CUDA wheels avoid changing the existing application's TensorFlow environment. TensorFlow documents 2.10 as its last native-Windows CUDA release; newer TensorFlow GPU installations use WSL2. See the official [TensorFlow installation guide](https://www.tensorflow.org/install/pip) and [PyTorch versioned CUDA installation commands](https://pytorch.org/get-started/previous-versions/).

The requirements use **PyTorch 2.9.1 with CUDA 12.6 wheels**, a documented compatibility pin for this Python 3.10 workflow, rather than a claim that it is the newest PyTorch. The official PyTorch version table supplies the Linux/Windows `cu126` command. Image/audio companion packages are unnecessary for these numeric sequences.

Install when preparing the model environment; the CUDA wheel download can be large. All packages and the notebook kernel live in the user profile, outside the repository:

```powershell
$modelEnvironment = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-models-v1'
py -3.10 -m venv $modelEnvironment
$modelPython = Join-Path $modelEnvironment 'Scripts/python.exe'
& $modelPython -m pip install -r ml/data/requirements.txt
& $modelPython -m pip install -r ml/training/requirements-gpu-windows.txt
& $modelPython -m pip check
& $modelPython -u -m ml.training.experiment doctor --device cuda
```

The doctor checks `torch.cuda.is_available()`, runs a small matrix operation on `cuda:0`, synchronizes the device and reports GPU name, memory, framework version and CUDA runtime. The code follows the [PyTorch CUDA device APIs](https://docs.pytorch.org/docs/2.9/notes/cuda.html). An unavailable CUDA device or failed tensor operation stops with an actionable error. There is no automatic CPU fallback for a requested neural GPU run. Successful doctor output verifies device execution only; it does not train or benchmark a model.

Persistence is not trained; ridge is a CPU reference. GPU use applies to the neural optimizer/tensors during the GRU implementation. The later CPU inference benchmark remains a separate acceptance test. With 4 GiB VRAM the initial neural architecture is kept compact under the registered parameter/search limits; actual memory and training behavior must be measured, not inferred from the hardware name.

## Open the thin notebook

```powershell
& $modelPython -m pip install ipykernel jupyterlab
& $modelPython -m ipykernel install --user --name aquaculture-models --display-name 'AquaCulture models'
& $modelPython -m jupyterlab
```

Choose the **AquaCulture models** kernel and open `ml/notebooks/05_experiment_setup.ipynb`. Its cells locate the repository and call `inspect_experiment`, giving the same checked data and run records as the CLI. The notebook contains no model architecture or training loop and is committed without executed outputs. New kernel packages do not alter the frozen preparation environment.

## Training progress handoff

The foundation provides `inspect` and `doctor`, while `python -m ml.training.baselines` runs the [baseline benchmark](baselines.md). Regression and GRU training entrypoints are subsequent implementation slices. Their executable commands will be documented when those functions exist; there is no placeholder learned-model training command to run now.

The neural trainer will require successful CUDA preflight, move the model and batches to the selected device, and report epoch, train/validation loss, elapsed time and checkpoint improvements through the same callable used by a notebook. Training commands use unbuffered Python (`-u`) so progress appears immediately. Long training runs will be started by the developer in their own terminal, with logs/checkpoints in the ignored run directory. The final test remains reserved until development choices and artifacts are locked.
