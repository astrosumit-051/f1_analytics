# Results

## The undercut window (training seasons, 2018 to 2023)

![The undercut window (left), the comparison groups (middle) and rival no-response records (right), 2018 to 2023 training races. Curves: final model, common-lap outcome, other features at training medians; bands: pointwise 95% intervals from 1,000 whole-race bootstrap refits.](figures/undercut_window.png)

The window is judged at the common lap so that one-lap and two-to-three-lap delays
are compared at the same point in the race. With other features at their training
medians, the final model gives (`figures/training/displayed_grid.csv`,
`evaluation/training_runs/common_h3/window_grid.csv`):

| Starting gap | Rival waits 1 lap | Rival waits 2-3 laps |
| --- | --- | --- |
| 0.5 s | 60% (39-85%) | 70% (46-90%) |
| 1.0 s | 46% (30-69%) | 57% (38-79%) |
| 2.0 s | 23% (13-37%) | 34% (19-53%) |
| 3.0 s | 13% (6-21%) | 22% (11-37%) |
| 5.0 s | 6% (1-13%) | 12% (5-23%) |

**The window.** For a one-lap delay the chance falls below 50% at a gap of 0.85 s
(bootstrap 0.42 to 1.50 s, crossing found in 916 of 999 refits) and below 25% at
1.87 s (1.29 to 2.71 s). If the rival waits two or three laps the crossings move
out to 1.28 s (0.45 to 2.16 s) and 2.63 s (1.68 to 4.70 s)
(`evaluation/training_runs/common_h3/crossing_intervals.csv`). Beyond about 3 s
an undercut rarely works: below 15% for one-lap delays.

**Primary outcome.** Judged at the pair's own lap three after the stop (`success_h3`) rather than the
common lap, the crossings barely move: 0.96 s (0.44 to 1.50 s) and 1.81 s (1.34 to 2.41 s) for a
one-lap delay, and 1.34 s (0.58 to 2.11 s) and 2.58 s (1.69 to 4.63 s) for two or three laps
(`evaluation/training_runs/h3/crossing_intervals.csv`, 1,000 refits, none failed).

**Observed rates agree with the curve.** One-lap undercuts kept the place in 56% of
pairs within 1 s, 31% at 1 to 2 s, 24% at 2 to 3 s and 7% to 12% beyond 3 s. Same-lap
stops (18% at 1 to 2 s) and stops where the rival went first (19% at 1 to 2 s) did
worse than undercuts in every gap band up to 3 s (`figures/training/observed_by_gap.csv`,
descriptive). Rival no-response records are shown as counts because the
eligible-opportunity denominator is not yet agreed (D-008).

**Out-of-bag check.** On training races left out of each bootstrap refit, the final
model's log loss (median 0.497) is barely better than the baseline's (0.500)
(`evaluation/training_runs/common_h3/out_of_bag_intervals.csv`). Most of the
model's gain over the gap-only curve shows on 2024 rather than within the training
seasons, which is one reason the locked test matters.

## Validation on 2024

The final model's 2024 scores are in the model section. It improves on the gap-only
baseline by 0.059 in log loss and 0.021 in Brier score
(`models/output/tuning/tune_metrics.csv`).

## Locked test on 2025

PENDING #19. Filled only from `evaluation/locked_results/test/` after the single
authorised run: Brier score and log loss against the baseline with race-bootstrap
intervals, the calibration plot, and the 50% and 25% crossings. A wide or absent
window is a valid result.
