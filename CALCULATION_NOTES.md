# Calculation notes

Implemented November 19, 2026: a small R calculation prototype and one local
Shiny testing page. Original CSVs and the original proposal are preserved.
No race-long optimum or team-points claim is supported by a two-driver cycle.
PR #7 merged a revised undercut-window proposal during implementation. This
calculator is a separately requested companion, not a replacement for that core
analysis. It uses the older, narrower exported candidate sample rather than the
new audit's wider six-second, one-to-three-lap cohort and censored outcomes.

Inputs are the combined lap, stop, catalog and candidate tables plus each event's
timestamped weather and status streams. `F1_DATA_ROOT` selects their location.
The engine uses focal-minus-rival arrival time in seconds, common completed
lap boundaries, five previous clean laps (minimum three) and a shared cutoff.

Files: `config.R`, two calculation files in `R/`, `scripts/run_analysis.R`,
`tests/check_calculations.R`, `app.R`, README and the planning status/work plan.
Data preparation includes stay-out decision rows and backward weather/status
joins. Missing rainfall stays unknown and wet/changing-weather cases are rejected.

Formulas and assumptions:

- Gap = focal arrival minus rival arrival; positive is behind. Gain = before
  gap minus after gap. Ahead = final gap below zero.
- Current decision lap L starts at completed lap L−1. The cutoff is the later
  of the two boundary crossings, before either pit entry in factual evaluation.
  Final lap = max(L+2, assumed rival stop, assumed teammate stop)+2 for all choices.
- Pooled normal pace uses circuit, numeric season, compound × tyre age, race
  progress and track temperature. It is anchored to the median of recent clean
  laps using only prior observations. A flat recent-pace baseline is evaluated
  on identical later-race rows. Model selection uses 2024, training ends in 2023,
  and the untouched later-race evaluation starts in 2025.
  Recent pace won validation, so the primary calculation holds that pace flat.
  The pooled normal pace and final gap are shown as sensitivity columns. This
  makes a tyre-based timing ranking unsupported rather than claiming a fitted
  tyre benefit that did not improve validation.
- Pit-cycle excess = observed inlap + outlap minus predicted normal inlap and
  outlap. Training-circuit medians and empirical excess draws own route loss,
  execution and outlap warm-up once. The full lane duration is never added.
  The excess is booked on the outlap as a schematic joint allocation.
- At an end-of-lap stop, old tyres remain through that lap. The next lap uses
  replacement prior age +1. Prior use and feasible compound transitions are
  explicit assumptions; actual available-set inventory is absent.
- There are 10,000 fixed-seed trials. Each car draws a contiguous training
  forecast-error block after recent-history anchoring, preserving within-block
  serial patterns, and one joint cycle
  excess. These same car/lap and car/stop draws are reused across alternatives.
  This is a conditional uncertainty model; coefficient uncertainty and empirical
  cross-driver dependence are not estimated.
- Probability ahead = fraction of negative final gaps; interval = 5th–95th gap
  percentiles; gain versus waiting is a paired trial difference. Comparisons
  within 0.5 seconds are labelled close.
- Surrounding cars with known same-boundary crossings use constant recent pace
  and no further stops. A 0.5-second rejoin delay applies within 1.5 seconds of a
  slower car ahead. Missing surrounding cars are not imputed. Teammate box
  arrivals use crossing clocks with a common route offset and assumed 3-second
  service; for same-lap stacking the later car waits max(0, service − arrival
  separation). This also handles the rival being on the focal driver's team.
  Cross-lap box overlap and interactions with sampled historical queue delays
  are not separately identified; team timing results remain approximate.
- Team timing comparisons minimize only the local summed arrival time. Expected
  team points is NA: field-to-finish forecasts, later stops, tyre-life constraints
  and applicable points rules are required before that objective is credible.
- Scheduled distances are explicit circuit assumptions in `config.R`, not final
  result-derived predictors. Shortened races need manual distance changes.

Checks actually run: all 19 synthetic/integration checks passed, covering signs,
one-second delay, common endpoints, tyre age/prior use, single cycle excess,
10,000 paired trials, repeatability/order, teammate waiting, wet/compound rejection,
real feature cutoffs, race-separated training/test inputs, exact missing-file
reports, saved results, source fingerprints and Shiny Compare gating. The running
app returned HTTP 200 with the expected title, Compare control and plot element.

The fresh raw-data build completed with exit code 0 in 258.16 seconds. All 390
read input-file MD5 hashes were unchanged. There are 213,132 laps, 7,054 stops,
193,112 decision rows and 147,740 eligible decisions; 143,147 eligible rows stayed
out. Training supplied 2,289 pit cycles in 117 races. All finite within-stint tyre
age increments were exactly one lap. Three real input scenarios and per-lap,
trial, rival-sensitivity and teammate outputs were saved. The third includes an
available teammate. One three-strategy 10,000-trial comparison took 1.05 seconds.

Measured later-race results (provisional source review):

| Diagnostic | Recent-pace primary | Pooled sensitivity |
| --- | ---: | ---: |
| 2024 pace MAE, 17,750 laps in 23 races | 0.416 sec | 0.445 sec |
| 2025–26 pace MAE, 31,424 laps in 41 races | 0.422 sec | 0.460 sec |

On 50 supported factual battles in 18 test races, simulated mean-gap MAE was
2.657 seconds versus 2.646 for the deterministic recent-pace baseline. Ahead
Brier score was 0.135 versus 0.190 for the training-battle frequency baseline;
90% interval coverage was 96%. Only one calibration bin has at least 20 cases;
these probabilities need further calibration. Excluded cases and reasons are
saved. Only factual schedules/realized sets have observed outcomes; the alternative
strategies and their pooled sensitivities have no observed counterfactual result.

Runtime: R 4.6.1; exact installed dependency versions are saved. In this Windows
environment, even a bare `library(shiny)` invocation exits with code 1 after
printing success. The integration assertions and saved PASS file completed before
that shutdown behavior; the full build exited normally and the local HTTP launch
was verified. Browser clicking and independent teammate review were not performed.

Commands from the project root:

```sh
Rscript tests/check_calculations.R
Rscript scripts/run_analysis.R
Rscript tests/check_integration.R
Rscript scripts/run_analysis.R --synthetic
Rscript -e "shiny::runApp('.', launch.browser=TRUE)"
```

The three unnamed timing cases and unusual 2026 event labels remain unresolved.
Any initial historical evaluation is provisional until those reviews are done.
The `2026_16` identity is excluded from factual evaluation and examples. The
historical-pair helper's actual-stop+2 boundary differs from the longer simulated
comparison boundary; each is saved explicitly. Full race tyre life, later stops,
driver interaction, reliable inventory and field-to-finish points remain open.
