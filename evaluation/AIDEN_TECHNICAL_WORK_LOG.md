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
