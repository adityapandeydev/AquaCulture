# Prepared data release and model-development readiness

Release: **oman-do-pilot-data-v1**, verified 2026-11-07. Status: **ready for scoped model development**. The checksum anchor and exact scope are recorded in [prepared-release.json](prepared-release.json).

The pre-model milestone is complete for a small chronological dissolved-oxygen forecasting experiment on the selected Oman tank recording. The full preparation chain has been rebuilt from pinned source files in an isolated environment, then rebuilt again using the first release's copied code, policies and sources. No new model was fitted, no accuracy score was computed, and no model is qualified for deployment.

## Supported experiment

| Item | Prepared release |
|---|---|
| Species/environment | Publisher-declared Nile tilapia, controlled 180 L tank |
| Source | Oman author repository, pinned commit `d95207b6f129c3de1f426ec90eed5a38f46832b8` |
| Session | `oman-2cbad87a2dbd2a81d6e1` |
| Target | Hourly DO summary in mg/L, using supported minute medians |
| Historical inputs | Six completed hourly DO bins, or DO/temperature/pH bins |
| Horizons | Primary +1 hour; secondary +3 hours, separately evaluated |
| Partition | 100/32/28/28 hours, training/validation/calibration/test |
| Evaluation claim | Chronological within-study pilot; no independent site established |

The release has **188 hourly observations**, **640 horizon/configuration-specific window references**, **312 common-horizon issue records** and **101,666 disjoint raw parent rows**. The 640 records include alternative configurations and horizons, with overlapping histories; they are not 640 independent trials.

| Partition | +1 h examples per configuration | +3 h examples per configuration |
|---|---:|---:|
| Training | 94 | 92 |
| Validation | 26 | 24 |
| Calibration | 22 | 20 |
| Final test | 22 | 20 |

The [supervised contract](supervised-data.md), [evaluation protocol](evaluation-protocol.md) and [pilot acceptance criteria](release-criteria.md) fix the inputs, labels, comparisons, provisional engineering gates and permitted claims. Research-data preparation performs no filling, scaling, learned feature selection or predictive fitting. Calibration-period interval diagnostics remain optional; reliable interval release is deferred.

## Release contents

The authoritative local bundle is `Datasets/releases/oman-do-pilot-v1-a/`. Its independent rebuild is `Datasets/releases/oman-do-pilot-v1-b/`. Both remain outside Git under the existing dataset exclusion.

```text
oman-do-pilot-v1-a/
├── sources/oman_tilapia/   # Ten checksum-pinned publisher files, including LICENSE
├── policies/              # Exact source, lineage, selection, split and experiment settings
├── code/ml/data/          # Preparation code, tests and minimal dependency specification
├── stages/                # Sessions → quality → aggregation → eligibility → partitions
│                          # → supervised indices → evaluation cohorts → readiness audit
├── environment.json       # Verified interpreter, platform and dependency versions
├── build.log              # Preparation-stage output
└── release_manifest.json  # Relative file inventory and scientific-content hashes
```

The bundle inventories 83 files before its top-level manifest. It includes original publisher bytes, row mappings, exclusions, quality flags, cleaned hourly observations, raw-parent lineage, split/window manifests, comparison cohorts and readiness reports. Unverified local internet collections and their raw files are not redistributed in this release. Their restricted dispositions remain documented in the source catalog.

Publisher attribution, commit identity, source URLs, declared reuse terms and checksums are retained in the source snapshot and manifest. The copied Oman LICENSE and README accompany the files. Reuse follows the identified source's declared CC BY 4.0 evidence and documented transformations, not a blanket license for similarly named files. Contributors can obtain the reviewed public acquisitions with `ml.data.acquire`; previously lost source links are not required for this release.

## Verification evidence

- All ten acquired Oman files match the pinned SHA-256 values and sizes, and their original bytes remain unchanged.
- A fresh user-profile environment uses CPython **3.10.11** with the eight exact packages in [the preparation requirements](../../ml/data/requirements.txt). No TensorFlow, Keras, PyTorch, scikit-learn, joblib, notebook runtime or trained artifacts are needed by this chain.
- All **84 preparation tests** pass in that clean environment and again using the copied code snapshot. `pip check` reports no dependency conflicts.
- The eight stages run from copied raw sources in two fresh output directories. All **25 scientific artifacts** match by content, including decoded compressed CSVs and diagnostic reports.
- The rebuilt observation table, windows, paired issues and count tables match the previously reviewed task-13 content.
- Source/row accounting, channel mappings, same-partition/session support, issue-time availability, parent/target disjointness, baseline alignment and readiness counts are checked by the rebuilt stages and focused tests.
- The top-level verifier rejects changed, missing or added files and paths escaping the bundle. Whole-file hashes protect exact containers; content hashes additionally compare decoded gzip payloads.

`Datasets/releases/oman-do-pilot-v1-verification.json` records the independent comparison. `oman-do-pilot-v1-tests.json` records both test runs and the dependency check. Their hashes and the published scientific-content map are anchored in [prepared-release.json](prepared-release.json).

The entire bundles are not asserted to be byte-identical: gzip metadata, logs and stage manifests containing build paths can differ. The copied source/code/policy bytes and scientific content match. Verification is documented for the tested Windows/CPython environment; other platforms and dependency revisions need their own reproduction check.

## Reproduce from a checkout

Use CPython 3.10.11. Install the preparation environment in the user profile, keeping it separate from both project source and the model-training environment. The commands below use PowerShell and fresh output names.

```powershell
$prepEnvironment = Join-Path $env:USERPROFILE '.codex/tools/aquaculture-preparation'
py -3.10 -m venv $prepEnvironment
$prepPython = Join-Path $prepEnvironment 'Scripts/python.exe'
& $prepPython -m pip install -r ml/data/requirements.txt
& $prepPython -m pip check
& $prepPython -B -m unittest discover -s ml/data -p 'test_*.py' -q
& $prepPython -B -m ml.data.acquire
& $prepPython -B -m ml.data.release build --output Datasets/releases/reproduction-a
```

The acquisition command verifies existing files and downloads only missing cataloged public acquisitions; network access is needed for missing files. The release builder admits only the pinned Oman files and refuses an existing output directory. A failed build leaves a traceable partial directory without a completed manifest; use a new output name rather than replacing it.

To check the copied snapshot independently:

```powershell
$workspace = (Get-Location).Path
$rebuild = Join-Path $workspace 'Datasets/releases/reproduction-b'
Push-Location Datasets/releases/reproduction-a/code
try {
    & $prepPython -B -m unittest discover -s ml/data -p 'test_*.py' -q
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot tests failed' }
    & $prepPython -B -m ml.data.release build --root ../sources --policy-dir ../policies --output $rebuild
    if ($LASTEXITCODE -ne 0) { throw 'Independent rebuild failed' }
} finally {
    Pop-Location
}
& $prepPython -B -m ml.data.release compare Datasets/releases/reproduction-a Datasets/releases/reproduction-b --report Datasets/releases/reproduction-verification.json
& $prepPython -B -m ml.data.release verify Datasets/releases/reproduction-a
```

Use `-B` when executing the frozen code so Python does not add bytecode caches to the write-once bundle. The verifier intentionally detects unlisted caches as extra files. All verification reports are written outside the frozen candidates.

The published scientific anchor can be checked separately:

```powershell
& $prepPython -B -c "import json; published=json.load(open('docs/data/prepared-release.json',encoding='utf-8')); rebuilt=json.load(open('Datasets/releases/reproduction-a/release_manifest.json',encoding='utf-8')); assert published['scientific_content_sha256']==rebuilt['scientific_content_sha256']; print('Published scientific content matches')"
```

The full candidate manifest digest identifies the exact local bundle. The Git-tracked anchor preserves that digest and the scientific-content map. This is write-once, checksum-verified preparation, not a signed artifact-distribution service. The bundled code/policies are the reproducibility snapshot; the source catalog in the working checkout can acquire later review metadata without rewriting the published release.

## Readiness scope and remaining limitations

Training approval applies only to the exact prepared pilot named in the checksum anchor. Earlier stage manifests retain `training_approved: false` as their original review-stage status, and the source-wide catalog default remains conservative. The independent-comparison report and prepared-release descriptor carry the final, narrower data-readiness decision. It is not model qualification or production approval.

The recording is short, measurements lack independent accuracy verification, and the raw series has unresolved rapid-change diagnostics. Hourly summaries can hide brief excursions. The test and calibration periods are dependent and small. These limitations accompany every later result rather than disappearing because preparation is reproducible.

The release does not validate shrimp, generic fish, independent farms, seasons, disease/mortality outcomes, biological event warnings or autonomous intervention. The excluded shrimp/aquaponics/Colombia/local variants remain excluded. Additional traceable and independently verified recordings are needed for broader accuracy and confidence claims. No numeric accuracy gain has been demonstrated yet.

## Model implementation handoff

New model architectures, training/checkpoint routines and evaluation logic belong in importable Python modules. Notebooks serve as thin interfaces for exploration, training calls and plots, using the same functions/configuration as command-line runs. This supports genuine Python source in the repository while retaining interactive training, accelerator access and checkpointing in the model environment.

Existing notebooks and model artifacts remain references; this milestone does not export their cells into scripts or reuse their weights. New candidates are trained from scratch under the frozen contract, with learned transforms fitted only on training data. The next work is model design and implementation, beginning with persistence and the registered compact candidates. Go backend, model serving, frontend and deployment remain separate application phases.
