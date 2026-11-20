# Handoff contracts (v1)

This folder fixes what Partner A hands to Partner B, so each of you can work without
waiting on the other. Every column, unit and definition lives in
[`schema.csv`](schema.csv). This page explains the ideas behind it.

**Changing anything here needs a `DECISIONS.md` entry and the other partner's review
first.** That includes renaming a column, changing a unit, a definition, a split or
a horizon. Adding a column is also a change.

| File | Made by | Used by | Where the real file goes |
| --- | --- | --- | --- |
| `pairs` | A (issues A1, A2) | B, and A's models | `data/derived/pairs.csv` |
| `no_response` | A (A1) | B (no-response rate) | `data/derived/no_response.csv` |
| `predictions` | A (A3, A4) | B (evaluation, bootstrap) | `data/derived/predictions.csv` |
| `window_grid` | A (A3), B fills the bands | B (charts, demo) | `data/derived/window_grid.csv` |
| fit and predict entry point | A (A3) | B (race bootstrap) | `models/` |

Until A's real files exist, use the fake ones in [`fake/`](fake/). They have the same
columns and roughly the right shapes, and every id starts with `fake_` or `FAKE_` so
they cannot be mistaken for results.

```
python contracts/make_fake.py                          # rebuild the fake sample
python contracts/check_contract.py --fake              # check the fake sample
python contracts/check_contract.py pairs data/derived/pairs.csv   # check a real file
```

Run the checker before opening any PR that writes a handoff file.

## Units and encoding

- Times and gaps are in **seconds** (float, three decimals). Laps are whole lap
  numbers. Probabilities are between 0 and 1.
- Yes/no columns (`bool01`) are written as `1` or `0`. A missing value is an empty
  cell or `NA`.
- Files are UTF-8 CSV with a header row and no index column.

## Definitions

These follow the proposal (revision 3) and the coverage audit
(`analysis/coverage/coverage_counts.py`).

- **Pair.** Two drivers in the same race whose matched stops are at most 3 laps
  apart, with no other stop by either driver in between.
- **Reference lap** (`ref_lap`). The lap before the first of the two stops. All
  decision-time features are measured at the end of this lap.
- **Chaser and leader.** The car behind at the end of `ref_lap` is the chaser, the car
  ahead is the leader (the rival), whoever stopped first.
- **Gap** (`gap_before_sec`). Chaser line-crossing time minus leader line-crossing
  time at the end of `ref_lap`. Always positive.
- **Delay** (`delay`). Leader stop lap minus chaser stop lap. 1 to 3 is an undercut
  and the value is the rival's delay; 0 is the same lap; -1 to -3 means the leader
  stopped first.
- **Signed gap after the stops** (`signed_gap_comparison_sec`). Chaser minus leader,
  so **negative means the chaser is ahead**.
- **Comparison lap.** The later of the two out-laps.
- **Common lap** (`common_lap = chaser_stop_lap + 4`). The out-lap after the latest
  possible rival stop. Use it whenever you compare delays, so every delay is judged
  at the same point in the race.
- **Outcomes.** Immediate success (`success_h0`) is the chaser ahead at the end of
  the comparison lap. **Sustained success over 3 laps (`success_h3`) is the primary
  outcome**: ahead at every lap boundary from the comparison lap through 3 more laps.
  Five laps (`success_h5`) is secondary.
- **Interrupted follow-up.** If the follow-up is broken by a stop, a neutralisation,
  rain, a retirement or missing timing, the outcome is missing (`NA`) and
  `horizon3_status` says why. It is never counted as a failure.
- **No response.** A chaser stop with a rival up to 10 s ahead who made no stop within
  3 laps either side goes in `no_response`, not in `pairs`. It is its own outcome
  category, reported as a rate.
- **Core cohort** (`in_core = 1`). Clean window, different teams, delay 1 to 3, gap
  above 0 and up to 6 s. The primary model is fitted only on these rows. Teammate
  pairs are a sensitivity check.

## Season split

| Split | Seasons | Who may look at outcomes, and when |
| --- | --- | --- |
| `train` | 2018 to 2023 | Anyone, any time. |
| `tune` | 2024 | Only in issues labelled `holdout`, for model selection (A4). |
| `test` | 2025 | **Locked.** Read once, in the locked-test issue, after the model freeze is recorded in `DECISIONS.md`. |
| `transfer` | 2026 | Descriptive check at the end (extension 5). |

"Looking" means any rate, plot, metric or model fit that uses the outcome columns.
Counting rows by split is fine.

## Features known at decision time

The model may only use columns with role `feature` in `schema.csv`. Columns with role
`extension` (pit-lane time actually taken, compound fitted) happen after the decision
and are used only in extensions 1 to 3. Circuit-level features (pit-lane median and
overtaking difficulty) are computed from training seasons only. Rejoin traffic is projected
at `ref_lap` from the circuit's pit-lane median (`DECISIONS.md` D-006).

## Fit and predict entry point

So that B can refit the model on resampled races without knowing how it is built, A
provides one command:

```
<models entry point> --train <pairs.csv> --predict <pairs.csv> --model <model_id> --out <predictions.csv>
```

It fits `model_id` on the `in_core = 1` rows of `--train`, predicts `success_h3` for
the `in_core = 1` rows of `--predict`, and writes a `predictions` file. A also writes
`window_grid` for each model. B fills `p_lo` and `p_hi` from the race bootstrap. The
language is decided in D-007; the command shape stays the same either way.
