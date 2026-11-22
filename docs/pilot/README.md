# Oman pilot archive

The first experiment forecast dissolved oxygen in one Nile tilapia tank. It ended on 22 November 2026, when the selected GRU failed its final evaluation. These records are kept unchanged apart from their location and links. Nothing here applies to the current models.

- [Outcome and final evaluation](pilot-closeout.md)
- [Evaluation protocol](evaluation-protocol.md) and [acceptance criteria](release-criteria.md)
- [Model development](development.md), [ridge](ridge.md), [GRU](gru.md), [CPU benchmark](cpu-benchmark.md)
- [Prepared data](readiness-report.md) and [source review](source-review.md)

The code is at commit `1ada193`, tagged `pilot-v1` locally. Commands and paths in these documents refer to that commit, where they were under `docs/data/` and `docs/models/`. To recheck the locked artifacts without scoring, use a separate worktree. `Datasets/` and `ml/runs/` from this machine must be available inside it.

```powershell
git worktree add ../aquaculture-pilot 1ada193
```
