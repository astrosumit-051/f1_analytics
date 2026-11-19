# Working together

Two people, two sets of Claude agents, one repository, due **Thursday December 3,
2026**. This page says who owns what, how work moves from an issue to `main`, and how
we talk. The rules for agents are in [`CLAUDE.md`](CLAUDE.md).

## Who owns what

We split by pipeline stage, so each of us owns a stage and we only meet at the
handoff files in [`contracts/`](contracts/README.md).

| | Partner A: Sumit (@astrosumit-051) | Partner B: Aiden (@aidenh144) |
| --- | --- | --- |
| Owns | Data and models | Evaluation and the story |
| Work | Pit-cycle pairs, decision-time features, the success model, model selection, extensions 1 (pit-stop time tolerance) and 3 (tyre choice) | Validation (season split, Brier score, calibration, race bootstrap), window charts, extension 2 (defender's view), extensions 4 (safety car) and 5 (2026 transfer), the demo, the report |
| Folders | `pipeline/`, `models/`, `data/derived/`, `analysis/coverage/`, `analysis/extensions/` (ext 1 and 3) | `evaluation/`, `figures/`, `demo/`, `report/`, `analysis/extensions/` (ext 2, 4, 5) |
| Label | `owner: A (Sumit)` | `owner: B (Aiden)` |

**Shared** (label `shared`, both must approve): `contracts/`, `DECISIONS.md`, this file,
`CLAUDE.md`, the model freeze and the locked 2025 test.

B never waits for A: until the real `data/derived/*.csv` files land, B builds against
`contracts/fake/`, which has the same columns. When A's files arrive, B's code should
run unchanged.

## The plan

Issues carry an owner, a due date and a milestone. Find yours with
[my open issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue+is%3Aopen+assignee%3A%40me).

| Milestone | Sumit (A) | Aiden (B) | Both |
| --- | --- | --- | --- |
| **Week 1** (due Wed Nov 25) | #9 pairs (Nov 23), #10 features (Nov 24), #11 baseline and primary model (Nov 25) | #12 evaluation harness on fake data (Nov 23), #13 race bootstrap (Nov 25) | #8 freeze the contracts (Nov 21) |
| **Week 2** (due Mon Nov 30) | #14 model choice on 2024 (Nov 28), #15 ext 1 (Nov 30), #16 ext 3 (Nov 30) | #17 window charts (Nov 28), #18 ext 2 (Nov 30) | |
| **Final** (due Thu Dec 3) | methods and model sections of the report | #20 ext 4 and 5 (Dec 1), #21 demo (Dec 2), #22 report (Dec 3) | #19 model freeze and locked test (Dec 1), #23 read-through and rehearsal (Dec 3) |
| Stretch | #24 one-cycle replay | | |

Old issues #1 to #6 described the earlier simulator and Shiny plan and are closed.
The `Planning/` folder is kept for its data reference but is superseded wherever it
disagrees with the proposal.

## From issue to `main`

1. **Pick an issue** assigned to you and move it to *Doing* on the board. If what you
   need is not an issue yet, open one first (use the *Task* template).
2. **Branch** from the latest `main`: `a/<issue>-<short-name>` or
   `b/<issue>-<short-name>`, for example `a/9-pairs-table`. Agent sessions may use
   their own branch names; that is fine as long as the PR links the issue.
3. **Keep it small.** One issue per PR, ideally under about 400 changed lines of code.
   Split big issues into several PRs that each say `Part of #N`.
4. **Open a PR** using the template. The last PR for an issue says `Closes #N`.
   Run `python contracts/check_contract.py ...` on any handoff file you wrote.
5. **The other partner reviews.** Request their review. Reviews happen within 24 hours;
   if you cannot, say so in the group chat. The reviewer checks the scope, the holdout
   rules and that the numbers make sense, not style.
6. **The reviewer merges** after approving, with *Squash and merge*. Nobody merges
   their own work, and nobody pushes straight to `main`.

Anything that changes `contracts/` or a shared definition needs a `DECISIONS.md`
entry in the same PR.

### Commit rhythm

- **Commit whenever something works**, even a small step. Commits are free and give you points to roll back to.
- **Push your branch at least once a day**, so the other partner can see progress and your work is backed up.
- **Open small PRs every day or two**, one per finished piece of an issue. The other partner reviews before anything merges into `main`; avoid one huge PR at the end.
- **Pull `main` before starting new work each day** (`git checkout main && git pull`, then branch or merge `main` into your branch), so you build on the latest shared version.

### One-time setup (Sumit, as the repository owner)

- **Protect `main`:** Settings, Branches, *Add branch ruleset* for `main`: require a
  pull request with 1 approval, and block force pushes. If GitHub says rulesets need
  a paid plan for private repositories, keep the rule by habit; the PR template
  reminds you.
- **Board:** create a GitHub Project (Board layout) named *F1 Undercut Window* with
  columns *To do*, *Doing*, *Review*, *Done*, then add issues #8 to #24.

## How we talk

- **Async check-in every other day** in our group chat, three lines:
  *Done:* what you finished (link the PR), *Next:* what you start, *Blocked:* what you
  need from the other person, or "nothing".
- **Two 20-minute calls a week, Monday and Thursday.** Thanksgiving week moves the
  Thursday call to Wednesday Nov 25. Calls are for decisions and looking at results
  together, not status. Planned calls: Mon Nov 23, Wed Nov 25, Mon Nov 30, Wed Dec 2
  (rehearsal).
- **Decisions go in [`DECISIONS.md`](DECISIONS.md)**, not only in chat. If a call
  decides something, whoever owns the area opens the PR that records it the same day.
- **Questions about a task go on its issue**, so both people and both sets of agents
  can see them.
- **Blocked for more than half a day?** Say so in the chat and in a comment on the
  issue that starts with "Blocked:", and pick up another issue meanwhile.

## Working with Claude

Each of us starts threads from our own Claude project, **one thread per issue**.
Start the thread with the issue link, for example "Work on
https://github.com/astrosumit-051/f1_analytics/issues/12". The agent reads
`CLAUDE.md`, stays in that issue's scope and folders, and opens a PR that links the
issue. You still review and merge; agents never merge.

Ask your agent to review the other partner's PRs if you like, but approve and merge
them yourself.
