# Model

*Section owner: Sumit.*

**Specification.** The window model is a logistic regression for sustained success
with a race random intercept, because pairs in one race share conditions and stops
(`models/core.py`). Starting gap enters as a natural cubic spline with three degrees
of freedom; the rival delay enters as a shift for `d23` and a `d23` x gap slope. The
other decision-time terms are tyre-age difference, circuit pit-lane median time,
projected rejoin traffic (cars that would be within 2 s ahead after the stop,
projected at the reference lap, D-006), cars between the two drivers, and circuit
overtaking difficulty. The model is fitted by maximum likelihood with 25-node
Gauss-Hermite quadrature over the race intercept. Predictions are for a new race:
the intercept is integrated out. The gap-only baseline is the same spline in a
plain logistic regression.

**Selection on 2024.** Recent pace difference, track temperature and a post-2022
era term were candidates. The rule for adding them was committed before any 2024
outcome was scored (`models/tune.py`): a term enters if it lowers both log loss and
Brier score on 2024. On 139 core 2024 pairs with a complete outcome (18 races):

| Model | Log loss | Brier |
| --- | --- | --- |
| Gap-only baseline | 0.470 | 0.150 |
| Primary model | 0.422 | 0.136 |
| + era | 0.426 | 0.139 |
| + recent pace difference | 0.415 | 0.132 |
| + track temperature | 0.417 | 0.133 |
| **+ pace + temperature (final model)** | **0.411** | **0.129** |

Source: `models/output/tuning/tune_metrics.csv`. The primary model's gain over the
baseline is clear (log-loss difference 0.048, race-bootstrap 95% interval 0.012 to
0.092, `tune_differences.csv`). The further gains from pace and temperature are
inside the bootstrap noise, but they met the rule fixed in advance, so the final
model `final_v1` includes both (D-010). It has 13 fixed effects plus the race SD,
above the proposal's limit of about ten for 108 training successes; we report this
as a limitation rather than change the rule after seeing 2024. Adding 68 training
teammate pairs barely changes the fit (2024 log loss 0.421 vs 0.422,
`teammate_sensitivity.csv`).

**Final model, fitted on 2018 to 2023** (`models/output/coefficients.csv`,
standardised terms; standard errors in brackets): d23 shift 1.00 (0.31); tyre-age
difference -0.26 (0.16); cars between 0.43 (0.14); recent pace difference -0.57
(0.16, chaser slower lowers the chance); track temperature -0.20 (0.15); pit-lane
median, rejoin traffic and overtaking difficulty all within one standard error of
zero; race SD 0.50.

The locked test refits `final_v1` on 2018 to 2024 and scores 2025 once
(`evaluation/LOCKED_TEST.md`).
