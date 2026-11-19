# F1 Pit Wall Two Person Coding Work Plan

> **Superseded on November 19, 2026.** This was written for the earlier simulator and Shiny scope. Ownership, issues and workflow now live in [CONTRIBUTING.md](../CONTRIBUTING.md); scope lives in the revised proposal. Issues #1 to #6 are closed.

Aiden owns the data and statistical modeling pipeline. Sumit owns the strategy simulator and Shiny application. Each person has three substantial GitHub issues covering major coding areas. The detailed 22-step procedure is a reference for execution within these areas, rather than a list of 22 separately assigned tasks.

## Responsibilities

| Owner | Major coding area | GitHub issue |
| --- | --- | --- |
| Aiden (@aidenh144) | Build the validated data preparation pipeline | [#1](https://github.com/astrosumit-051/f1_analytics/issues/1) |
| Aiden (@aidenh144) | Build pace and pit-cycle models with execution uncertainty | [#2](https://github.com/astrosumit-051/f1_analytics/issues/2) |
| Aiden (@aidenh144) | Own analytical validation and historical evidence | [#3](https://github.com/astrosumit-051/f1_analytics/issues/3) |
| Sumit (@astrosumit-051) | Build the strategy simulation engine and robustness analysis | [#4](https://github.com/astrosumit-051/f1_analytics/issues/4) |
| Sumit (@astrosumit-051) | Build the Shiny pit wall interface and classroom replay | [#5](https://github.com/astrosumit-051/f1_analytics/issues/5) |
| Sumit (@astrosumit-051) | Own reproducible builds, integration testing, and demo packaging | [#6](https://github.com/astrosumit-051/f1_analytics/issues/6) |

## Starting together

Aiden starts source imports and timing validation in issue #1. Sumit starts the R project, configuration, and build setup in issue #6. Agree the scenario schema, prediction-function signatures, gap sign, time units, and result-table schema before building dependent components. This is a shared design discussion; each component keeps one primary owner.

Sumit can build the deterministic clock engine and Shiny layout using clearly labelled fixtures while Aiden prepares real data and fits models. Fixtures must be replaced with verified inputs before accepting numerical results.

## Handoffs

1. **Data handoff:** Aiden supplies validated RDS tables, keys, cutoff-safe histories, race splits, a verified scenario fixture, and an unresolved-review registry. Sumit confirms the engine can consume the agreed schema.
2. **Model handoff:** Aiden supplies preprocessing, pace and joint pit-cycle predictors, residual distributions, support limits, and version metadata. Sumit integrates these through one shared simulation API without duplicating delay terms.
3. **Validation handoff:** Sumit supplies factual-schedule predictions and trial-level results. Aiden evaluates them on later races, returns calibration and support findings, and identifies acceptable demonstration settings.
4. **Demo handoff:** Sumit connects the reviewed outputs to Shiny, benchmarks the workflow, and assembles the package and classroom presentation. Aiden checks every analytical claim; both rehearse the demo.

## Code ownership

- Aiden: import, source validation, battle reconstruction, sample definitions, features, pace fitting, pit-cycle fitting, and analytical evaluation. Primary modules: R/01_import.R through R/06_fit_pit_cycle.R and R/08_evaluate.R.
- Sumit: simulation, robustness analysis, scenario/build assembly, shared configuration, Shiny modules, replay, integrated tests, and packaging. Primary modules: R/07_simulate.R, R/09_scenarios.R, app.R, R/shiny_modules.R, config/, and scripts/.
- Each person writes focused checks for their own components. Sumit owns the integrated test run; Aiden owns analytical acceptance. Review the other person's handoff and avoid concurrent edits to the same module without agreeing first.

## Finding assigned work

GitHub issues #1 through #3 are assigned to Aiden and #4 through #6 to Sumit. They appear in each account's Assigned to me issue view.

- [My assigned project issues](https://github.com/issues?q=is%3Aissue%20is%3Aopen%20repo%3Aastrosumit-051%2Ff1_analytics%20assignee%3A%40me)
- [Aiden's issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue%20is%3Aopen%20assignee%3Aaidenh144)
- [Sumit's issues](https://github.com/astrosumit-051/f1_analytics/issues?q=is%3Aissue%20is%3Aopen%20assignee%3Aastrosumit-051)

Use each issue's checklist and completion criteria to track progress. Link implementation pull requests to the corresponding issue, and close it when its outputs and handoff have been verified. No deadlines or completed coding are implied by these assignments.
