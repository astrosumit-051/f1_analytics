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

## D-006  How rejoin traffic is measured (open)
- Date: 2026-11-19
- Status: proposed
- Decided by: to decide in the contracts issue
- Issue or PR: contracts issue
- Decision: v1 measures `rejoin_traffic_cars` as cars within 2 s ahead of the first
  stopper at the end of their out-lap, as the coverage audit did. That is observed
  after the stop, so it is a proxy. The alternative is a decision-time projection:
  cars that would be within 2 s ahead after subtracting the circuit's pit-lane median
  from the first stopper's time at `ref_lap`.
- Why: a feature that is only known after the stop can make the window look better
  than a pit wall could use.
- Affects: `pairs.rejoin_traffic_cars`, issue A2.

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
