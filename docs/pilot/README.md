# Oman pilot

The first experiment forecast dissolved oxygen (DO) in one tilapia tank. It ended on 22 November 2026, when the selected GRU failed its final evaluation. Nothing here applies to the current models. The record is kept because the method carried over, and because a failed result should stay visible.

## Data

| | |
| --- | --- |
| Source | Oman author repository, commit `d95207b6f129c3de1f426ec90eed5a38f46832b8`, CC BY 4.0 |
| Recording | One 180 L tank, publisher-declared Nile tilapia, 2 to 10 April 2026 |
| Release | `oman-do-pilot-data-v1`, 188 hourly bins from 101,666 raw rows |
| Target | Hourly DO in mg/L, the mean of supported minute medians |

An hour needed at least 54 supported minutes with three readings each, no gap above 180 seconds, and a last reading within 60 seconds of its end. Nothing was filled or smoothed. Zeros, jumps and plateaus were flagged and kept. The pond recording from the same study was left out, because only 58 of its hours qualified and 5,714 of its rows had unresolved time order. Sensor calibration was declared by the author and could not be verified independently.

The 188 hours were cut into four consecutive periods before any model was fitted. History and target had to lie inside one period.

| Period | Hours | Windows, +1 h | Windows, +3 h |
| --- | ---: | ---: | ---: |
| Training | 100 | 94 | 92 |
| Validation | 32 | 26 | 24 |
| Calibration, never opened | 28 | 22 | 20 |
| Final test | 28 | 22 | 20 |

## Method

Forecasts used the last six hours, with DO alone or with temperature and pH. Persistence was the reference. Ridge was tried with four penalties. A single-layer GRU that corrects persistence was tried with hidden sizes 8 and 16, two learning rates and seeds 17, 29 and 43. Settings were chosen by mean validation error, and seed 17 was always the primary artifact.

Limits were fixed before fitting: a 5% lower mean absolute error (MAE) than persistence, MAE at most 0.50 mg/L at +1 h and 0.75 at +3 h, root mean square error (RMSE) at most 0.75 and 1.00 and no higher than persistence, bias within 0.20 and 0.30, and full coverage. +1 h was mandatory. These were engineering choices, since no farm operator had supplied an acceptable error.

## Validation

| Inputs | Model | +1 h MAE | Gain | +3 h MAE | Gain |
| --- | --- | ---: | ---: | ---: | ---: |
| DO | Persistence | 0.246824 | | 0.349044 | |
| DO | Ridge | 0.244892 | 0.78% | 0.336433 | 3.61% |
| DO | GRU, mean of seeds | 0.236942 | 4.00% | 0.318983 | 8.61% |
| DO, temperature, pH | Ridge | 0.276987 | -12.22% | 0.437217 | -25.26% |
| DO, temperature, pH | GRU, mean of seeds | 0.240976 | 2.37% | 0.329869 | 5.49% |

The mandatory +1 h limit was already missed here. The GRU with DO alone stayed a research candidate, and operational use was disabled.

## Final evaluation

The test ran once on 22 November 2026, after the evaluator was committed as `ad53d3c`. All 21 locked files matched, and saved validation forecasts were reproduced within 9.6e-7 mg/L.

| Horizon | Forecast | MAE (mg/L) | RMSE (mg/L) | Bias (mg/L) | Gain |
| --- | --- | ---: | ---: | ---: | ---: |
| +1 h, 22 windows | Persistence | 0.4035 | 0.6578 | -0.018 | |
| | GRU seed 17 | 0.3946 | 0.6257 | -0.095 | 2.2% |
| | GRU seed 29 | 0.3918 | 0.6239 | -0.091 | 2.9% |
| | GRU seed 43 | 0.3934 | 0.6242 | -0.094 | 2.5% |
| +3 h, 20 windows | Persistence | 0.6385 | 1.0094 | -0.167 | |
| | GRU seed 17 | 0.6301 | 0.9373 | -0.296 | 1.3% |
| | GRU seed 29 | 0.6327 | 0.9286 | -0.328 | 0.9% |
| | GRU seed 43 | 0.6091 | 0.9095 | -0.333 | 4.6% |

Both horizons fail. The gain misses 5% everywhere, and the +3 h bias averages 0.319 mg/L in size, above its limit of 0.30. The +3 h validation pass did not carry over. Only one test target was in the low-oxygen group, so the pilot says nothing about low oxygen. Any later score on these windows must say that they were opened on this date.

Speed was never the problem. On one thread of an i7-12700H, the GRU took 0.18 to 0.22 ms per forecast at the 95th percentile, 2.4 s to start and 476 MiB of memory.

## What carried over

- Splits, limits and search size are fixed before fitting, and the test opens once.
- Six hours cannot contain a daily oxygen cycle, so the current models use 24.
- One tank and 22 test windows cannot support a claim. The current data has 17 ponds.
- Beating persistence is too easy at longer horizons. The current reference is the strongest of three simple forecasts.

The reading behind these choices found no published result that could be adopted as it stood. [Haq and Harigovindan (2022)](https://doi.org/10.1109/ACCESS.2022.3180482) and [Yang and Liu (2021)](https://doi.org/10.3934/mbe.2021374) smooth or decompose series without showing that only past values were used, and the second reports an RMSE below its MAE, which is impossible for the same errors. [Xu and Xie (2021)](https://proceedings.mlr.press/v139/xu21h.html) set out what an interval's coverage depends on.

## Reproduce

The code and every original document are at commit `1ada193`, tagged `pilot-v1` locally. `Datasets/` and `ml/runs/` from the original machine are needed, with the GPU environment rebuilt from the requirement files at that commit.

```powershell
git worktree add ../aquaculture-pilot 1ada193
cd ../aquaculture-pilot
python -B -m ml.evaluation.pilot_final --check-only
```

This checks the locked files and reproduces validation forecasts without scoring the test. The files in this folder are the [evaluation lock](pilot-evaluation-lock.json), the release anchor and policies it binds, and the download catalog. Paths inside them refer to that commit. Outputs are in `ml/runs/pilot-final/`, where `run.json` has SHA-256 `2ba8831f5763bb6e61e3cecfe1ec7250fed892d0f10c2832e6d15146f92c4055`.

Full documents: [data](https://github.com/adityapandeydev/AquaCulture/tree/1ada193/docs/data), [models](https://github.com/adityapandeydev/AquaCulture/tree/1ada193/docs/models). The closest to this page are the [final decision](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/models/pilot-closeout.md), [evaluation protocol](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/evaluation-protocol.md), [limits](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/release-criteria.md), [GRU](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/models/gru.md) and [literature review](https://github.com/adityapandeydev/AquaCulture/blob/1ada193/docs/data/literature-review.md).
