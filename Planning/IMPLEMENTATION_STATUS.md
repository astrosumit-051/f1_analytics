# Calculation prototype status

This page tracks the companion prototype requested in the November 19 calculation
task. The revised undercut-window proposal merged in PR #7 remains the core
research plan; this prototype does not replace its cohort or scope decisions.
`CALCULATION_NOTES.md` is the maintained record of formulas, actual checks,
measured results and limitations. The original proposal and the reference and
procedure Word documents remain archived planning snapshots; the full 22-stage
design is a longer-term roadmap, not the acceptance checklist for this prototype.

The active files are `config.R`, `R/data_and_models.R`, `R/strategy.R`,
`scripts/run_analysis.R`, `tests/check_calculations.R`, and `app.R`. The prototype
groups responsibilities into two calculation files rather than creating every
module proposed in the roadmap. All calculation functions remain outside Shiny.

The decision is whether to stop at the end of the current lap or wait one or two
laps, with an explicit rival stop assumption. The alternatives share the same
starting information and ending lap. A schematic teammate box queue and simple
surrounding-car rejoin assumption support sensitivity checks. Race-to-finish team
points, wet strategies, animations, replay, heatmaps, deployment and presentation
work are outside the current request.

The current core project assignments #8–#24 supersede archived issues #1–#6.
Companion review is tracked in issue #27: Sumit reviews data/model/engine calculations and
Aiden reviews factual evaluation and the local tester. The implementation
provides a starting point for both people. Neither a commit
nor automated checks imply their independent review or approval. Unidentified
timing cases remain unresolved and numerical historical results are provisional.
