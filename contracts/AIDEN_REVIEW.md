# Aiden handoff review for issue 8

Reviewed main 4980df7 and the revised proposal revision 3. This review does not
change the schema, accepted scientific definitions, Sumit's owned code or any
decision status. D-008 records this proposed review through the shared process.

Primary scoring, gaps/signs, matched stop IDs, explicit interruption missingness,
training-only observed rates and CSV application integration are implementable.
The existing fake sample passes the shared checker for all four tables. D-004
and D-005 have Aiden's conditional implementation signoff; Sumit must confirm
source feasibility and both partners must approve the shared freeze.

| Item | Evidence | Required shared resolution |
| --- | --- | --- |
| Traffic feature D-006 | Main calls an out-lap observation a feature. PR #32 proposes a decision-time projection. | Prefer a genuine decision-time input over observed future traffic. Review PR #32 with Sumit; its full pit-lane duration is not route time lost and can displace the projected rejoin. Do not silently replace it or claim accuracy. |
| Technology D-007 | Existing B drafts already use Python scoring/figures and R Shiny. | Proposed: retain those languages with CSV-only Shiny. Both approve before calling the implementation the agreed final technology. |
| Common-lap model | Command promises success_h3; window schema also permits success_common_h3. | A must supply a fitted common-lap target and a bootstrap-compatible prediction/grid interface, not relabel primary probabilities. An optional outcome/grid output extension needs a recorded schema/interface decision. |
| Grid profile and race effects | Window says training medians; integer pair columns may have fractional medians; repeated bootstrap races need independent grouping IDs. | Prefer A-owned grid generation for each refit, with training-derived medians and explicit new-race/population random-effect treatment. Review B's synthetic-query adapter before real use. |
| No response | Numerator is supplied; matched/ref windows differ and stops can have several rivals. | Agree the opportunity key, eligibility window, duplicate policy and denominator built at a consistent chaser decision. Until then show counts and NA rate; do not divide arbitrary row totals. |
| Defender | common_h0 exists; signed common-lap gaps and sustained-defence outcomes do not. | Complement immediate chaser success only as chaser-not-ahead at that boundary. Do not complement sustained success to claim sustained defence. |
| Neutralisation | First exclusion reason can hide simultaneous wet/timing failures. | Existing descriptive summaries label dry status unverified. A defensible dry SC/VSC subset needs additional approved eligibility evidence. |
| Freeze and transfer | No model freeze or locked-run authorization exists. Proposal also mentions transfer fitting through 2025. | Record exact models/code/input hashes and both signoffs on main, explicitly authorize #19 once, then authorize #20. Do not refit using 2025 without a separate accepted shared decision. |

No scientific definition is newly accepted here. No fake generator rerun is
needed because schema/fake data were not changed. Main branch protection remains
the repository owner's setup responsibility and has not been verified or changed.
