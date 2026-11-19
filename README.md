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

## Planning

Start with [the planning index](Planning/README.md), [the data and code reference](Planning/F1_Data_and_Code_Reference.md), and [the detailed coding procedure](Planning/F1_Step_by_Step_Coding_Procedure.md).

See [the two-person work split](Planning/F1_Two_Person_Work_Plan.md) for ownership and handoffs. The coding work is grouped into six major ownership issues, three assigned to each person. The detailed 22-stage procedure remains a supporting reference.

- [My assigned open issues](https://github.com/issues?q=is%3Aissue%20is%3Aopen%20repo%3Aastrosumit-051%2Ff1_analytics%20assignee%3A%40me)
- [Aiden's assigned issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue%20is%3Aopen%20assignee%3Aaidenh144)
- [Sumit's assigned issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue%20is%3Aopen%20assignee%3Aastrosumit-051)

Raw race data remains in the shared project data folder and is not included in this documentation commit. The planning inventory records its paths and hashes. Analysis and application code will be added through the assigned implementation issues.

## Companion R calculation prototype

The separately requested [calculation prototype](PROTOTYPE_README.md) provides R
functions, a reproducible run script and a plain local Shiny tester, and generates
saved example results locally. Its 10,000-trial calculations are an experimental companion and do not
replace the revised proposal or make Monte Carlo simulation a core project
requirement. See [calculation notes](CALCULATION_NOTES.md) for measured validation,
unsupported tyre rankings and remaining limitations. Raw inputs remain unchanged
and are distributed separately.
