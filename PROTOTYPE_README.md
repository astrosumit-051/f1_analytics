# F1 pit decision calculation prototype

Generated historical outputs and the model bundle are local artifacts, ignored
by Git. The commands below reproduce them from the separately shared raw data.

Compare pitting at the end of the current lap with waiting one or two laps. The
R functions return time gained, a signed focal-minus-rival gap, probability of
emerging ahead and a central 90% simulated gap interval. A positive gap is behind.
The plain local Shiny page uses the same result table and one deterministic gap plot.

## Run

Use R from this directory. Install only `data.table` and `shiny`:

```r
install.packages(c("data.table", "shiny"))
```

Place the original shared `F1_Pit_Wall_2018_2026/` directory here, or set
`F1_DATA_ROOT` to that directory. Required combined files are
`all_laps_enriched.csv`, `all_pit_stops.csv`, `completed_race_catalog.csv`, and
`pit_battles_model_ready.csv`; each event also needs `sessions/YYYY_RR/weather.csv`
and `track_status.csv`. Source data is distributed separately and never modified.

```sh
Rscript tests/check_calculations.R
Rscript scripts/run_analysis.R
Rscript tests/check_integration.R
Rscript -e "shiny::runApp('.', launch.browser=TRUE)"
```

If Rscript is not on PATH, run `source("scripts/run_analysis.R")` from RStudio
with the project root as the working directory. For arithmetic-only checks:

```sh
Rscript scripts/run_analysis.R --synthetic
```

Missing required real inputs are listed exactly in `outputs/missing_inputs.txt`;
synthetic results remain labelled synthetic. Rebuilds always read the sources;
there is no cache that can silently reuse an old model. The app loads the locally
built `models/prototype.rds`, so rerun analysis after source or model changes.

## Files and limits

- `config.R`: paths, chronological split, support thresholds and assumptions.
- `R/data_and_models.R`: keys, decision rows, historical-only pace and cycle fitting.
- `R/strategy.R`: pure clock engine, 10,000 paired trials, teammate timing combinations.
- `scripts/run_analysis.R`: reproducible build and later-race factual evaluation.
- `tests/check_calculations.R`: labelled synthetic invariants.
- `tests/check_integration.R`: real cutoffs, saved results and Shiny server consistency.
- `CALCULATION_NOTES.md`: actual checks, measured results and remaining limitations.

These are provisional, conditional local-cycle estimates. Unnamed timing cases
in the original proposal still require review. Wet/changing-weather cases are
unsupported. Usable tyre sets and scheduled race distance are explicit assumptions.
Only the actual schedule has an observed outcome. No two-driver gap is converted
to final points; expected team points is unavailable until a credible race-to-finish
field model and applicable points rules exist. Later tyre life and further stops
are not modeled, so the recommendation is not a race-long optimum.

Recent clean pace beat the pooled regression on 2024 validation races, so it is
the primary forecast. The pooled compound/age response appears as a sensitivity;
the app explicitly labels a tyre-based timing ranking unsupported. Dependency
versions, measured errors and a Windows Shiny shutdown-exit quirk are recorded in
`outputs/` and the calculation notes. The Shiny server and local HTTP launch were
tested; independent teammate acceptance remains open.

The [planning index](Planning/README.md), [reference](Planning/F1_Data_and_Code_Reference.md),
[procedure](Planning/F1_Step_by_Step_Coding_Procedure.md), and
[two-person assignments](Planning/F1_Two_Person_Work_Plan.md) retain project context.
Issues #1–#3 remain Aiden's analytical ownership; #4–#6 remain Sumit's engine,
minimal tester and integration ownership. The prototype is the shared starting
point; no independent teammate review is implied.
