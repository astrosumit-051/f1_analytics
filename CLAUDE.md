# Rules for agents working in this repository

Two people share this repository: Sumit (Partner A, @astrosumit-051) and Aiden
(Partner B, @aidenh144). Each runs their own Claude agents. Follow these rules so the
two sets of agents never step on each other. `CONTRIBUTING.md` has the full workflow
for the people.

## Before you change anything

1. **Find the issue.** Every task is a GitHub issue, titled with a code such as
   `[A3]` or `[B1]`. If the person did not give you one, ask which issue, or open one
   with the *Task* template and confirm it with them before writing code.
2. **Read, in this order:** the issue; `contracts/README.md` and `contracts/schema.csv`;
   `DECISIONS.md`; the proposal (`Proposal/F1_Undercut_Window_Proposal_v2.docx`,
   revision 3); `analysis/coverage/README.md` for the numbers the data supports.
3. **Check the owner.** The issue's `owner:` label tells you whose area you are in.
   Work only in the folders the issue lists under *Scope and rules*.

## Scope

- Stay inside the issue. If you find something else that needs doing, say so in your
  reply or open a new issue; do not fix it in the same PR.
- Do not edit files in the other partner's folders. Partner A: `pipeline/`,
  `models/`, `data/derived/`, `analysis/coverage/`. Partner B: `evaluation/`,
  `figures/`, `demo/`, `report/`. Shared: `contracts/`, `DECISIONS.md`,
  `CONTRIBUTING.md`, this file.
- `Planning/` and the closed issues #1 to #6 describe an earlier simulator and Shiny
  plan. Do not follow them where they disagree with the proposal.

## Contracts and shared definitions

- **Never change `contracts/` or a shared definition** (column names, units, gap sign,
  delay, reference, comparison or common lap, horizons, exclusions, the season split)
  without adding a `DECISIONS.md` entry in the same PR. Adding a column counts as a
  change.
- After changing `contracts/schema.csv`, rerun `python contracts/make_fake.py` and
  `python contracts/check_contract.py --fake`.
- Any PR that writes a handoff file under `data/derived/` must pass
  `python contracts/check_contract.py <table> <file>`.
- Partner B's code reads only the handoff files and the fit-and-predict entry point,
  never Partner A's internal modules. Build and test against `contracts/fake/` until
  the real file exists.

## Holdout rules (do not break these)

- **2018 to 2023 (`train`)**: use freely.
- **2024 (`tune`)**: read outcome columns only in issues labelled `holdout`.
- **2025 (`test`)**: locked. Read outcome columns only in the locked-test issue, and
  only after `DECISIONS.md` has a model-freeze entry. Do not run it twice.
- **2026 (`transfer`)**: descriptive check at the end only.
- "Reading" means any rate, metric, plot, printout or model fit that uses
  `success_*`, `signed_gap_comparison_sec` or `no_response` outcomes. Counting rows by
  split is fine. If a task seems to need held-out outcomes and the issue is not
  labelled `holdout`, stop and ask.
- Missing outcomes (`NA`) are dropped and counted, never treated as failures.
- Model features must be known at the end of `ref_lap` (role `feature` in
  `schema.csv`). Columns with role `extension` are only for extensions 1 to 3.

## Data

- Raw race data is not in the repository and must never be committed. Take its path
  as a command-line argument.
- Derived handoff tables go in `data/derived/`.
- Results computed from `contracts/fake/` are not results. Never quote them as
  findings.

## Git and pull requests

- Never push to `main`. Work on a branch and open a pull request.
- Start from the latest `main`: fetch and merge it into your branch before new work.
- Commit whenever a step works, and push the branch at least once a day.
- Open a small PR every day or two for each finished piece, rather than one large PR
  at the end. The other partner reviews before it merges.
- One issue per PR. Use the PR template. Put `Closes #N` (or `Part of #N`) in the
  description.
- Request review from the other partner. Never merge, approve or close the other
  partner's PRs or issues.
- Keep PRs small and say in the description what you ran and what you did not check.
- Say which numbers changed, if any, and which file they come from.
