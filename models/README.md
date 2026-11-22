# Models (Partner A, issue A3 #11)

Python, numpy + pandas + scipy only.

| File | What it does |
| --- | --- |
| `core.py` | Model specs, natural-spline basis, logistic and random-intercept logistic fits |
| `fit_predict.py` | The public fit-and-predict entry point in `contracts/README.md` |
| `build_outputs.py` | Writes `data/derived/predictions.csv` and `window_grid.csv`, plus `output/coefficients.csv` and `output/fit_summary.csv` |
| `test_models.py` | `python -m pytest models -q` |

```
python models/build_outputs.py                       # fit on train, predict train + tune
python contracts/check_contract.py predictions data/derived/predictions.csv
python contracts/check_contract.py window_grid data/derived/window_grid.csv
python models/fit_predict.py --train <pairs.csv> --predict <pairs.csv> --model primary_v1 --out p.csv [--outcome success_common_h3]
```

## Models

- `baseline_gap_v1`: logistic regression on a natural cubic spline in
  `gap_before_sec` (3 df, knots at the 0, 33, 67 and 100% training quantiles). 4
  parameters.
- `primary_v1`: the same spline, a d23 shift and a d23 x gap slope (gap centred),
  tyre-age difference, circuit pit-lane median, projected rejoin traffic, cars
  between, overtaking difficulty (all standardised on the fitting rows), and a race
  random intercept. 11 fixed effects + race SD. Fitted by maximum likelihood with
  25-node Gauss-Hermite quadrature.

Predictions are for a new race (the random intercept integrated out), the same rule
for every split. Missing `tyre_age_diff` (one core row) is filled with the fitting
rows' median. Everything learnt from data is learnt from the rows the model is
fitted on, so the race bootstrap can refit on any resample.

`build_outputs.py` writes both `success_h3` (primary) and `success_common_h3`
(common-lap curves), for train and tune rows. It never predicts test or transfer
rows and never prints a score; scoring tune rows belongs to A4 (#14).

## Model selection on 2024 (A4, #14)

`python models/tune.py` (holdout issue only) fits every candidate on train, scores the
2024 core rows and applies the rule in its docstring. Outputs: `output/tuning/`. The
choice is `final_v1` (D-010): `primary_v1` plus `recent_pace_diff_sec` and
`track_temp_c`. `pipeline/candidates.py <data> --write-pairs` builds both columns.

## Monte Carlo simulation and one-cycle replay (A7, #24)

Assumption-based, training seasons (2018-2023) only. No 2024-2026 outcome is read.

```
python models/simulate.py            # writes models/output/simulation/*.csv, *.json
python models/simulation_page.py     # builds models/output/simulation/undercut_lab.html
```

`simulate.py` fits `final_v1` plus the first stopper's pit-lane excess (the extension 1
fit) on the core training pairs, outcome `success_common_h3`, then plays 4,000 pit
cycles for each of 528 scenarios (gap 0.25-6 s x delay group x 0-5 s slower stop).
Each cycle draws the coefficients from their fitted uncertainty, a real training pit
cycle for the other features, a race effect, and the outcome. `season_check.csv`
replays the training seasons through the simulator as an in-sample check.
`undercut_lab.html` is a self-contained page (no external scripts): a rotating 3D
window surface, a heatmap, a live 500-race simulation that runs the same model in the
browser, and animated replays of eight real training pit cycles.
