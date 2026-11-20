# Aiden technical work log

Internal engineering record, started November 19, 2026. No report or presentation
work is included. Scientific conclusions may contradict the hypothesis.

## Repository assessment

Base: main `4980df7a56666951d1c9fd7fa2dfc7ceb77bccdf`. The original local folder is
not a Git checkout. Work takes place in the separate `aiden_work/` clone; existing
files, raw data and another contributor's branches are preserved.

Read: README, CONTRIBUTING, CLAUDE, DECISIONS, contracts README/schema/checker/fake
generator, revised proposal revision 3, coverage audit, issues #8–#24/#27 and
PR #26. Open drafts #29/#30/#31/#33 already implement parts of #21/#12/#13/#17;
extend these rather than duplicate them. PR #28/#32 hold unmerged real pairs and
features. Main has no production model or handoff files.

The accepted split is train 2018–2023, tune 2024, locked test 2025, descriptive
transfer 2026. No freeze or #19 execution authorization is recorded. Do not run
the companion's historical build: its default procedure evaluates 2025 onward.
Protected outcome values will not be inspected or used to debug.

## Initial assumptions and unresolved decisions

- D-004/005/006/007 are proposed on main. Build on the current CSV contract without
  declaring it accepted. R Shiny remains a provisional implementation choice until
  shared technology approval; no alternative modelling pipeline will be built.
- Rejoin traffic in main is observed after the decision despite its feature role.
  PR #32 proposes a decision-time projection. Aiden must review, not silently adopt
  a different scientific definition. Sumit retains ownership of features/models.
- No-response lacks an agreed eligible-opportunity denominator; show counts and an
  unavailable rate until the shared definition is approved. Missing outcomes are
  never converted to losses, defender successes, or no-response failures.
- Whole-race uncertainty preserves repeated stops/pairs. Synthetic software checks
  do not establish historical accuracy, calibration, or submission readiness.

## Work in progress

- #12: harden the existing evaluator, add independent numerical/schema/holdout
  regression tests and reproducibility metadata.
- #13/#17/#18/#20/#21/#27/#19: assessment complete; implement eligible work in
  separate issue branches. Real model integration, frozen evaluation and approvals
  remain pending. No issue is declared complete merely because code exists.

## Reproduction environment

Python 3.13.5 from the existing Anaconda install has numpy, pandas, scipy,
matplotlib and pytest. Use `python -m pip install -r evaluation/requirements.txt`
in a clean Python environment. R 4.6.1 is installed under Program Files (x86);
the user library contains shiny and data.table but requires R_LIBS_USER in this
sandbox. Commands and results will be recorded as they are actually executed.

## #12 verified milestone

Extended `evaluation/evaluate.py` instead of replacing it. Added selected-split
schema and geometry checks, finite probability checks, explicit holdout guards,
calibration bias/ECE, cohort counts and SHA-256 run metadata. Added pinned major
dependency ranges, README and `test_evaluate.py`.

Executed `python contracts/check_contract.py --fake`: all four tables pass.
Executed `python -m pytest evaluation/test_evaluate.py -q`: 22 passed.
Executed the fake CLI command in README: metrics, calibration PNG/CSV, crossings,
cohort counts and run metadata generated successfully. `git diff --check` passes.
These are synthetic checks only. Real final-model scoring is pending #11/#14.

The old CLI could repeatedly score test after a permissively parsed freeze note.
Selected solution: block direct test/transfer invocation before file access and
prepare separate reviewed runners in #19/#20. Tuning is explicit in #14 only.
This is stricter execution control, not a change to the accepted season split.

## #13 verified milestone

Extended bootstrap.py with a subprocess adapter for the published four-argument
entry point, independent race-copy IDs, fitting-failure records and paired fixed-
prediction metric intervals. Stand-ins now refuse unlabelled historical data.
The default common-lap outcome remains separate from pair-specific success_h3.
BOOTSTRAP.md explains conditional crossings, pointwise bands and OOB variability.

Executed test_bootstrap.py: 5 passed. Executed 100 synthetic race refits with seed
355: all 100 succeeded; interval files and failure ledger written. These counts
are software diagnostics, not historical findings. The approved real model and
common-lap prediction interface remain missing; real-model validation is blocked.

## #17 integration milestone

Extended existing plot_windows.py; added reusable figures/stats.py whole-race
rate intervals and numerical tests. Outputs include source tables and run hashes.
Changed the old figure name to undercut_window to keep technical assets distinct
from excluded report work. No-response rates stay NA pending shared approval.

Training-only handoffs were selected as strings from PR #32 commit
ad2b6f1ca201e3c04c31325036ad5d582ba4f3e7 into ignored evaluation/local_inputs.
Provenance records source SHA-256 and selection. All 4,796 training pairs and 4,129
training no-response records are available locally. Fake and unmerged real
training figures generated; the real chart has no supplied common-lap model
curve and explicitly labels it pending. Production integration remains unapproved.

## #18 verified milestone

Implemented analysis/extensions/defender/analyze.py and README with exact delays,
common-lap outcomes, whole-race intervals and exact overlap on gap band, tyre-age
difference and season. Every result is descriptive with counts and missingness.
The defender point-in-time event complements common_h0 only. Sustained defence
cannot be inferred by complementing common_h3; unsupported cases stay unavailable.

Executed defender tests: 2 passed. Ran the same workflow on unmerged PR #32's
training handoff successfully. Held-out extension evaluation and final producer
review are pending. This does not demonstrate causal strategy superiority.

## #20 development milestone

Added neutralisation/analyze.py with SC-only, VSC-only, both, clean-control and
other-unclean categories, exact-delay timing gains, missingness and whole-race
intervals. The first-failure exclusion flag cannot certify dry neutralised rows;
outputs explicitly state dry status unverified rather than silently discarding
possibly inconvenient observations. Comparison-lap gain is not a common-lap or
causal strategy effect. Common follow-up is reported separately.

Executed neutralisation tests: 2 passed. Training-only PR #32 workflow generated
its CSVs and figure. The 2026 procedure is specified but remains locked pending
#19, the frozen model, explicit transfer authorization and both partners' review.

## #21 application milestone

Separated pure CSV/statistical logic into demo/data.R; app.R calls these tested
functions. Added gap/model/outcome/delay controls, common-lap response overlay,
interpolated supported probabilities and available intervals, explicit missing
model messages, crossing status, source fingerprints, deterministic observed
success/failure examples and CSV export. Synthetic and real evidence cannot mix.
The app loads selected training strings before parsing outcomes, and never fits.

Executed demo/test_app.R: all assertion groups and Shiny server controls passed.
Independent Python checks matched R observed counts/rates for all four groups.
Chrome visually rendered model, delay and examples; selecting another model and
response changed the probability and table. Detected and fixed locale-corrupted
Unicode labels. Live app served normally in Chrome.

Process caveat: tests write ALL SHINY CHECKS PASSED but R exits abnormally after
loading shiny. A minimal base-R q(status=0) exits 0; minimal library(shiny) plus q
reproduced exit -1073741569. This indicates a local R/package teardown problem,
not proof of a clean test process. A clean exit on the submission environment is
still required. Pure calculations and the live server worked; no final production
integration or browser acceptance on real frozen outputs is claimed.

## #27 review milestone

Reviewed PR #26 at 76929e3c1720d337dcf54fa148a5d0ebbcf75a93 in a separate ignored
code-only checkout. Reproduced scripts/run_analysis.R --synthetic: 12 supplied
check groups passed, process exit 0. evaluation/review_companion.R added five
independent invariant groups: all 17 total groups passed, process exit 0.
The optional --shiny review built a NEW labelled synthetic bundle in that ignored
checkout and verified exact offline/Shiny table equality and Compare gating.
Assertions and saved marker pass; Shiny-loaded process again exits abnormally.

Did not run the unrestricted historical build or tests/check_integration.R because
they read 2025+ outcomes/bundles. Documented in COMPANION_REVIEW.md: realized-set
conditional factual evaluation, narrow cohort, provisional calibration, missing
cross-driver shock dependence, schematic queue/traffic and selected-pace/cycle
compatibility. None of the simulator is integrated into the primary application.
Sumit's independent scientific review and both partners' integration decision
remain pending. Existing published historical numbers were not revalidated.

## #8 and #19 final development milestones

#8 has its own branch with contracts/AIDEN_REVIEW.md and proposed D-008. It
records Aiden's conditional engineering signoff without accepting decisions on
Sumit's behalf. No schema/fake data or accepted definitions changed; all four
contract checks still pass. Traffic projection, common-lap command/grid, median
profiles, no-response denominator, technology and protected-run governance need
shared review. Branch protection was not changed or verified.

#19 now has locked_run.py, a disabled authorization example and LOCKED_TEST.md.
It requires merged origin/main decisions and authorization, both partner names,
exact model/source/input hashes, an explicit issue number and fixed seed. Execute
must fetch main. A persistent atomic receipt is written before outcome parsing;
failed or completed runs cannot be silently repeated. Transfer additionally
requires the completed committed 2025 receipt and separate #20 authorization.
There is no model training in this runner and no actual protected run occurred.
Twelve synthetic governance/single-use tests passed. Actual main preflight refused
because no accepted freeze exists, before opening any outcome input.

## Integrated verification and remaining acceptance work

Executed python -m pytest evaluation figures analysis/extensions -q: 46 passed.
R app assertion groups and server tests passed again; process shutdown remains
abnormal only after loading shiny. A pure-R real-training-handoff check exited 0:
564 core pairs, 98 races, loading 0.86 s and mean scenario calculation 0.093 s over
100 refreshes on this machine. No missing model was replaced by a fabricated
number. Python and R independently matched the four synthetic observed groups.

TRAINING_INTEGRATION.json records unmerged PR #32's primary sample: 473 complete,
91 missing, 108 successes; common-lap: 449 complete, 115 missing, 103 successes.
These reproduce the proposal's primary training-success count and demonstrate
contract compatibility only. They are descriptive observations, not a predictive
accuracy or causal superiority result. No final model calibration is available.

Reproduce synthetic checks using python evaluation/run_checks.py, optionally
--rscript /path/to/Rscript. The JSON report distinguishes assertions from process
exit and returns failure on a crashing R process. Source requirements and app
launch instructions are in evaluation/README.md and demo/README.md.

Remaining: Sumit must review/merge pair/features, implement #11 and select #14;
both resolve #8 and the common-lap/bootstrap interface. Then integrate/retest the
approved model, finalize frozen training-refit bands and crossing intervals,
authorize #19 and score 2025 once, sign off results, authorize descriptive #20
transfer and test clean startup/exit on the submission computer. #17's rate is
blocked by the agreed denominator; #18/#20 final held-out evaluation is pending.
The code is reviewable development, not a submission-ready or approved model.
Issues #22/#23, report text, presentation and rehearsal materials were excluded.

Final rerun after provenance guards: all 47 Python tests and all four contract
checks passed. demo/test_app.R passed its assertions including grid fingerprint
and protected-split rejection checks, then the Shiny-loaded process returned
3221225727 (Windows 0xC00000FF). run_checks.py correctly returned failure and saved
the distinction between assertions and process status. No failure is suppressed.
The primary curves now require matching training-refit provenance; unknown
provenance withholds predictions. Mixed no-response/model evidence is rejected.

The CLI push waited on Windows credential manager and was cancelled. Publishing
uses the already connected GitHub app instead, preserving existing PR heads as
commit parents and keeping each issue separate. No main push or self-merge is
performed. Local native commit milestones are retained for rollback.

## Published review handoff

All PRs are drafts; review was requested from astrosumit-051. No issue was closed,
no work was self-approved or merged, and main was not pushed. Changes are stacked
for small issue diffs; review/merge dependencies from the bottom upward. Rebase or
retarget after collaborator merges, without overwriting their work.

| Issue | Pull request | Status |
| --- | --- | --- |
| #8 | https://github.com/astrosumit-051/f1_analytics/pull/34 | Conditional shared review; decisions pending |
| #12 | https://github.com/astrosumit-051/f1_analytics/pull/30 | Harness implemented and fake-tested; review pending |
| #13 | https://github.com/astrosumit-051/f1_analytics/pull/31 | Stand-in/adapter tested; real model integration pending |
| #17 | https://github.com/astrosumit-051/f1_analytics/pull/33 | Figures implemented; model and denominator pending |
| #18 | https://github.com/astrosumit-051/f1_analytics/pull/35 | Training descriptive analysis; held-out approval pending |
| #20 | https://github.com/astrosumit-051/f1_analytics/pull/36 | SC/VSC development; transfer remains locked |
| #21 | https://github.com/astrosumit-051/f1_analytics/pull/29 | App controls verified; final model/clean R exit pending |
| #27 | https://github.com/astrosumit-051/f1_analytics/pull/37 | Synthetic review done; scientific/historical review pending |
| #19 | https://github.com/astrosumit-051/f1_analytics/pull/38 | Procedure prepared; no real locked run authorized |

The connector-published trees matched the tested local tree hashes. Local branches
were synchronized after fetch; pre-publication native milestones are retained
under refs/aiden-native/. The integration checkout is b/19-locked-test-procedure.
The separate b/8-contract-review branch contains the shared D-008 proposal; it is
not silently applied to the integration branch or main. No raw data was committed.
