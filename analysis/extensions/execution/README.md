# Extension 1: pit-stop time tolerance (A5, #15)

`python analysis/extensions/execution/analyze.py` (default base model `final_v1`).
Fits `final_v1` plus the first stopper's pit-lane excess over the race median on the
core training pairs (2018-2023, `success_h3`) and asks how many extra seconds in the
pit lane push the predicted chance below 50% and 25% at each gap and delay.

| File | Status label |
| --- | --- |
| `output/observed_by_excess.csv` | descriptive, training seasons |
| `output/tolerance_grid.csv` (gap x delay x 0-6 s extra; data for B's chart) | assumption-based |
| `output/tolerance.csv` (extra seconds to close the window) | assumption-based |
| `output/coefficients.csv`, `output/run.json` | assumption-based (training fit) |
| `output/counts.csv` | row counts, all splits |

Assumptions: the excess slope is the same at every gap and delay, a slow stop changes
nothing else, excess is clipped to [-2, 10] s. No 2024-2026 outcome is read.

Count check: 100 core pairs have excess > 2 s with the pipeline's race median (stops
outside 10-60 s dropped first); the coverage audit's 98 used the median over every
matched stop. With the audit's median the pipeline gives 99; the last pair was not
traced.
