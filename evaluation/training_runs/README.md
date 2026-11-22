# Training-season bootstrap runs (2018–2023 only)

Summaries of two 1,000-draw whole-race bootstraps. Each draw refits the models
through `models/fit_predict.py`. Seed 355. Inputs are `data/derived/pairs.csv`
and `predictions.csv` (the hashes are in each `run.json`). No 2024, 2025 or 2026
outcomes are read.

| Folder | Outcome | Models | Failed draws |
|---|---|---|---|
| `common_h3/` | `success_common_h3` (used to compare delays) | baseline_gap_v1, primary_v1, final_v1 | 1 (draw 861, an overflow in the final_v1 refit, recorded in `fitting_failures.csv`) |
| `h3/` | `success_h3` (primary outcome) | baseline_gap_v1, final_v1 | 0 |

```
python evaluation/bootstrap.py --pairs data/derived/pairs.csv --outcome <outcome> \
  --resamples 1000 --seed 355 --entry-point-json '["python","models/fit_predict.py"]' \
  --model baseline_gap_v1 --model final_v1 --predictions data/derived/predictions.csv --out <dir>
```

The per-draw out-of-bag file (`out_of_bag_draws.csv`) is left out to keep the
repository small; rerun the command to regenerate it. The intervals are pointwise
percentile intervals over refits on training races. The out-of-bag ranges describe
variability; they are not test-set confidence intervals.

`figures/training/` is drawn from `common_h3/`:
`python figures/plot_windows.py --pairs data/derived/pairs.csv --no-response data/derived/no_response.csv --window-grid evaluation/training_runs/common_h3/window_grid.csv --grid-run evaluation/training_runs/common_h3/run.json --model final_v1 --resamples 1000 --out figures/training`
