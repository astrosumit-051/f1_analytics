# F1 Undercut Window

DSC 355 project on when pitting before a nearby rival produces a sustained positional advantage, and how that depends on the starting gap and on how long the rival waits to stop.

## Current plan

Start with [the revised proposal](Proposal/F1_Undercut_Window_Proposal_v2.docx) (revision 3, November 19, 2026). It sets the scope from [the coverage audit](analysis/coverage/README.md), which counts the available data for every planned comparison and extension.

Scope decisions made on November 19, 2026:

- The starting gap range extends to 6 seconds, with rival delays of one to three laps.
- Rivals who do not stop within three laps are reported as their own outcome category.
- Cars running between the two drivers are a model feature, not a filter.
- The full Monte Carlo simulator is replaced by a one-cycle replay stretch goal. Extensions follow in the order listed in the proposal.

The planning documents below were written for the earlier pit wall simulator scope (undercut, cover and overcut in R and Shiny). Where they disagree with the revised proposal, the proposal wins.

## Working on this project

- [CONTRIBUTING.md](CONTRIBUTING.md): who owns what, the week-by-week plan, branch and PR rules, and how we check in.
- [CLAUDE.md](CLAUDE.md): rules for the coding agents both partners use.
- [contracts/](contracts/README.md): the handoff tables, units and definitions, with a fake sample to build against.
- [DECISIONS.md](DECISIONS.md): the log of scope and definition decisions.
- [My open issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue+is%3Aopen+assignee%3A%40me), and the milestones [Week 1](https://github.com/astrosumit-051/f1_analytics/milestone/1), [Week 2](https://github.com/astrosumit-051/f1_analytics/milestone/2) and [Final](https://github.com/astrosumit-051/f1_analytics/milestone/3).

## Earlier planning documents

[Planning/](Planning/README.md) was written for the earlier pit wall simulator scope (R and Shiny). Its data reference, field dictionary and session index are still useful; its work split and issues #1 to #6 are superseded by CONTRIBUTING.md and issues #8 to #24.

Raw race data remains in the shared project data folder and is not included in the repository.
