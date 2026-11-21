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
