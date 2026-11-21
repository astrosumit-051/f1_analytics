# Decisions

One entry per decision that changes scope, a shared definition, a handoff contract,
the season split, or who owns what. Chat is for talking; this file is the record.

**How to add one.** Copy the template to the bottom, take the next number, and open a
PR. The other partner reviews it like any other PR. Never rewrite an accepted entry:
add a new one that says which entry it supersedes, and change the old one's status to
`superseded by D-0xx`.

```
## D-0xx  Short title
- Date: YYYY-MM-DD
- Status: proposed | accepted | superseded by D-0yy
- Decided by: Sumit, Aiden
- Issue or PR: #nn
- Decision: what we will do, in one or two sentences.
- Why: the reason, with the number or table that backs it.
- Affects: files, columns or issues that must change.
```

---

## D-001  Scope follows proposal revision 3
- Date: 2026-11-19
- Status: accepted
- Decided by: Sumit, Aiden
- Issue or PR: #7
- Decision: The question is the undercut window as a probability curve. Gap range up to
  6 s, rival delays of 1 to 3 laps, rivals who do not stop within 3 laps are their own
  outcome category, cars between the two drivers are a model feature, and the Monte
  Carlo simulator becomes the one-cycle replay stretch goal. Extensions in order:
  execution tolerance, defender's view, tyre choice, safety car (descriptive), 2026
  transfer, replay. Rain is out of scope.
- Why: the coverage audit (`analysis/coverage/README.md`) found 922 core pairs in 151
  races and showed the window's edge lies between 3.5 and 6 s.
- Affects: everything. `Planning/` and the old issues #1 to #6 describe the earlier
  simulator and Shiny scope and are superseded.

## D-002  Division of labour
- Date: 2026-11-19
- Status: accepted
- Decided by: Sumit, Aiden
- Issue or PR: this PR
- Decision: Partner A (Sumit, @astrosumit-051) owns data and models: pairs, features,
  the success model, model selection, and extensions 1 and 3. Partner B (Aiden,
  @aidenh144) owns evaluation and the story: validation, bootstrap, charts, extension
  2, extensions 4 and 5, the demo and the report. The contracts, the model freeze and
  the locked test are shared.
- Why: splitting by pipeline stage means the two of you only meet at the handoff files.
- Affects: `CONTRIBUTING.md`, labels `owner: A` and `owner: B`.

## D-003  Season split and holdout rules
- Date: 2026-11-19
- Status: accepted
- Decided by: Sumit, Aiden
- Issue or PR: this PR
- Decision: Train 2018 to 2023, tune 2024, test 2025 once, 2026 as a descriptive
  transfer check. Resampling is by whole race. 2024 outcomes are read only in issues
  labelled `holdout`; 2025 outcomes only in the locked-test issue after a model-freeze
  entry exists here.
- Why: only 2018 to 2023 outcome rates were inspected during the audit, so 2024 and
  2025 are still unseen.
- Affects: `contracts/README.md`, every evaluation script.

## D-004  Handoff contracts v1
- Date: 2026-11-19
- Status: proposed (accepted when both partners approve the contracts issue)
- Decided by: Sumit, Aiden
- Issue or PR: this PR
- Decision: The tables, columns, units and definitions in `contracts/schema.csv` and
  `contracts/README.md`, version 1. B builds against `contracts/fake/` until A's real
  files land.
- Why: fixing names and definitions first lets both partners work in parallel.
- Affects: all handoff files.

## D-005  Where handoff files live
- Date: 2026-11-19
- Status: proposed
- Decided by: Sumit, Aiden
- Issue or PR: this PR
- Decision: Derived handoff tables are committed under `data/derived/` so both partners
  and their agents get them with `git pull`. Raw race data is never committed; it stays
  in the shared data folder and the pipeline reads it from a path given on the command
  line.
- Why: the derived tables are a few MB at most, and B cannot run A's pipeline without
  the raw snapshot.
- Affects: `data/derived/`, `.gitignore`.

## D-006  How rejoin traffic is measured
- Date: 2026-11-19
- Status: accepted
- Decided by: Sumit, Aiden
- Issue or PR: #8, #10
- Decision: `rejoin_traffic_cars` is projected at decision time: the cars, rival
  excluded, whose next line crossing after the first stopper's crossing at the end of
  `ref_lap` (their last crossing plus their last lap time) falls between P - 2 s and
  P s later, where P is `circuit_pitlane_median_sec`. Those are the cars that would be
  up to 2 s ahead after the stop. The audit's measure (cars within 2 s ahead at the
  end of the out-lap) is observed after the stop and is no longer used as a feature.
- Why: a feature that is only known after the stop can make the window look better
  than a pit wall could use. On the 922 core pairs the two measures agree in 61% of
  rows (correlation 0.15), so the choice matters.
- Affects: `contracts/schema.csv` (`pairs.rejoin_traffic_cars` description),
  `pipeline/features.py`, issue A2 (#10).

## D-007  Language for models and demo (open)
- Date: 2026-11-19
- Status: proposed
- Decided by: to decide in the contracts issue
- Issue or PR: contracts issue
- Decision: Recommended: Python (pandas, statsmodels or a mixed-model package) for the
  pipeline and models, since the coverage audit is already Python. The demo can be
  Python or R Shiny; it only reads `window_grid` and `pairs`, so it does not have to
  match.
- Why: the handoff contracts are plain CSV plus one command, so either language works,
  but each partner's code should use one.
- Affects: `models/`, `demo/`, `requirements.txt` or `renv.lock`.

## D-008  Aiden implementation review and remaining contract decisions
- Date: 2026-11-19
- Status: proposed
- Decided by: Aiden implementation review; Sumit's shared approval pending
- Issue or PR: #8
- Decision: Keep v1 unchanged during development. Aiden has verified that the four
  tables support primary evaluation, observed common-lap comparisons and the local
  application. This is conditional engineering signoff, not acceptance by both
  partners of D-004 through D-007. Resolve the items in contracts/AIDEN_REVIEW.md
  before production integration or declaring the contracts frozen.
- Why: Independent implementation found that the public command promises only
  success_h3 while response curves need success_common_h3, no-response rates lack
  an agreed denominator, and observed rejoin traffic cannot be a live feature.
- Affects: #8, #11, #13, #17, #19, #20, #21. Proposed implementation choices are
  Python evaluation/figures with an R Shiny CSV-only app; a model-owned common-lap
  prediction/grid interface; merged model/input hashes and both signoffs before
  one locked evaluation. None is silently marked accepted by this entry.

## D-009  Entry point takes an optional outcome; models use Python
- Date: 2026-11-21
- Status: proposed
- Decided by: Sumit; Aiden to review
- Issue or PR: #11
- Decision: The fit-and-predict command keeps its four arguments and adds an
  optional `--outcome` (default `success_h3`, also `success_h0`, `success_h5`,
  `success_common_h3`), so the common-lap curves come from a model fitted on the
  common-lap outcome rather than relabelled primary probabilities. The models are
  Python (numpy, pandas, scipy); this settles the models half of D-007. Predictions
  are for a new race: the race random intercept is integrated out, not set to zero.
  The primary model has 11 fixed effects plus the race SD (the proposal's "about 10"):
  the delay interaction is a d23 shift plus a d23 x linear-gap slope, not a full
  spline-by-delay interaction, to stay near that limit.
- Why: Aiden's contract review (PR #34, proposed D-008) found the v1 command could
  only promise `success_h3`, while the window charts compare delays at the common lap.
  108 sustained successes in training support about 10 parameters.
- Affects: `models/fit_predict.py`, `contracts/README.md` (entry point section),
  `evaluation/bootstrap.py` command adapter (Aiden: it can now pass `--outcome`).

## D-010  Final model chosen on 2024; pace and temperature join the pairs contract
- Date: 2026-11-21
- Status: proposed (Sumit chose the model; Aiden to review the contract change)
- Decided by: Sumit; Aiden to review
- Issue or PR: #14
- Decision: The final model is `final_v1`: `primary_v1` plus recent pace difference
  and track temperature, 13 fixed effects plus the race SD, chosen by the selection
  rule in `models/tune.py`, which was committed before any 2024 outcome was scored.
  Two `pairs` columns are added with role `feature`: `recent_pace_diff_sec` and
  `track_temp_c` (definitions in `contracts/schema.csv`, built by
  `pipeline/candidates.py`). The era term is not used.
- Why: on the 2024 core pairs with a complete 3-lap outcome (139 pairs, 18 races),
  tune log loss was 0.470 for the gap-only baseline, 0.422 for `primary_v1`, 0.415
  with pace, 0.417 with temperature, 0.426 with era, and 0.411 with pace and
  temperature together. Brier fell the same way (0.150, 0.136, 0.129 combined). The
  primary-minus-baseline interval excludes zero; the pace/temperature gains are
  within race-bootstrap noise but met the rule fixed in advance
  (`models/output/tuning/`). Adding teammate pairs to the fit barely changes the
  coefficients or the tune score.
- Affects: `contracts/schema.csv`, `contracts/fake/`, `data/derived/pairs.csv`,
  `models/`, the freeze and locked test (#19). The model exceeds the proposal's
  "about 10 parameters"; that is stated as a limitation.
