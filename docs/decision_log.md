# Project decisions

## November 19 2026 calculation prototype

The implementation request narrows the original roadmap to R calculations and
one local Shiny test page. Keep two calculation files rather than creating every
planned module. Companion review is assigned to both partners separately from
the current core-project assignments. The original proposal and Word planning copies
are retained as historical design documents; current implementation status is in
`Planning/IMPLEMENTATION_STATUS.md` and `CALCULATION_NOTES.md`.

During this task, PR #7 merged the revised undercut-window proposal and coverage
audit into main. Preserve both. Publish the requested Monte Carlo calculator as
a companion prototype in a separate pull request, without replacing the core
proposal's wider gap/delay cohort, censoring outcome or replay stretch goal.

Use stop choices L, L+1 and L+2 from completed lap L−1, with shared cutoff equal
to the later focal/rival crossing. All simulated alternatives finish at
max(L+2, assumed rival stop, assumed teammate stop)+2. This is a deliberately
longer endpoint than the export's later actual stop+1. Recompute observed timing
at the simulator endpoint for factual evaluation. The separate historical-pair
helper reports its own explicit actual-stop+2 boundary. No exported outcome at
another boundary is substituted for this factual outcome.

Fit on races through 2023, select the primary pace method on 2024, and evaluate
2025 onward without refitting. Recent clean pace beats the pooled model on the
validation split, so retain the recent-pace primary forecast. Show the pooled
compound/age response only as a sensitivity, and label a tyre-based stop ranking
unsupported when the primary model has no validated tyre response.

One joint inlap/outlap excess owns route loss, execution and outlap warm-up.
Book it once on the outlap for transparent accounting. Resample training-only
forecast-error blocks after recent-pace anchoring; unanchored race/driver offsets
must not be added again as uncertainty.

Scheduled race distance, usable replacement inventory, future rival/teammate
stops, continued dry/green conditions, traffic loss and box service are explicit
assumptions. No final classification, future weather, actual future stop or
replacement compound enters a decision feature. Realized sets/schedules are
declared only in the separate factual evaluation.

Return team points as unavailable until credible field-to-finish projections,
later stops and applicable points rules exist. Compare local teammate timing
costs in the meantime. Keep the unnamed timing cases unresolved and exclude
the unusual `2026_16` identity from historical examples/evaluation.
