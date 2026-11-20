# Companion PR 26 independent technical review

Reviewed head `76929e3c1720d337dcf54fa148a5d0ebbcf75a93`, issue #27.
This is an engineering review, not collaborator approval or a core-model test.

## Reproduced safely

Extract the code at that SHA into a separate checkout. No raw inputs or prior
historical artifacts are needed. From that checkout run:

```sh
Rscript --vanilla scripts/run_analysis.R --synthetic
Rscript --vanilla /path/to/current/evaluation/review_companion.R
```

The first command reproduced the 12 supplied synthetic check groups and exited
normally. The independent review adds direct checks of trial means, negative-gap
probability counts, quantiles, ledger sums, RNG restoration, paired one-second
perturbations and unsupported race distance. See the work log for actual results.

The unrestricted scripts/run_analysis.R evaluates years >= 2025 and its pace
routine includes all later seasons. tests/check_integration.R loads a historical
bundle and factual predictions. Neither was executed on real inputs: a core
freeze and #19 execution authorization are absent. The companion's published
historical metrics are earlier claims, not independently reproduced results here.
Its documented Shiny launch requires that historical bundle. A separate
synthetic Shiny test can verify interface/engine parity without opening it.

## Findings and reuse

| Component | Evidence and disposition |
| --- | --- |
| Decision-time state | Backward histories and timestamped weather/status cutoffs are explicit. Synthetic future-row invariant passes. Real source cutoffs remain unverified in this run. |
| Clock accounting | Chaser-minus-rival sign, common endpoint and a single joint pit-cycle excess are testable. Reuse sign/ledger invariants; intra-cycle excess allocation is schematic. |
| Paired trials and RNG | Fixed car/lap and car/stop draws are shared across alternative strategies and local RNG is restored. This pairs alternatives, not the two drivers' residual race shocks. |
| Pit-cycle decomposition | Excess is estimated relative to pooled normal pace before the selected recent-pace baseline is chosen. A final baseline forecast needs an audit that excess/residual decomposition remains compatible with that selected pace method. |
| Teammate wait | A three-second service and same-lap crossing-clock proxy are assumptions. Cross-lap queue overlap and queue already in empirical excess are unresolved; not a validated team-strategy model. |
| Factual validation | Conditions on realized schedules and replacement sets/ages, excludes contaminated or unsupported cycles, and uses the older narrow candidate export. It does not estimate the revised cohort's sustained/common-lap target or validate counterfactual alternatives. |
| Calibration | Empirical ahead frequency under these conditional simulation assumptions is not a calibrated core success probability. No real held-out calibration was reproduced. |
| Tyres | Flat recent pace cannot establish a tyre-based ranking. Pooled compound response is a sensitivity only. Inventory, subsequent stops, wet strategies and race-long team points remain unsupported. |

Keep this simulator separate. Reusable components are the pure-function pattern,
ledger/RNG invariants, uncertainty labels and explicit unsupported states. None
requires adding the simulator to the primary app. Sumit still reviews the model,
feature and engine assumptions; both partners must decide any scope integration.

The primary app's independent Windows process tests reproduce a local shiny
shutdown crash even for library(shiny);q(status=0), while base R exits normally.
Numerical PASS markers and a functioning server are distinct from clean exit.
