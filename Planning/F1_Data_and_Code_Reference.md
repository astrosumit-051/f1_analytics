# F1 Pit Wall Data and Code Reference

Prepared November 19 2026

This is the working reference for building and changing the R and Shiny pit wall simulator. Read it before editing data preparation, metrics, models, simulation, or the interface. Use the companion coding procedure to decide what to implement next. The immediate priority is to establish reliable timing and decision-time inputs before fitting a model or building the replay.

The project compares the probability of a focal driver emerging ahead after an undercut, a same-lap cover, or an overcut during one pit cycle. It starts with dry conditions, green-track windows, a fixed rival pit lap, pooled models, and two or three supported historical scenarios. Simulated alternatives are conditional estimates. The observed battle export contains earlier-versus-later stopping pairs and does not provide observed outcomes for all three choices in the same situation.

## 1 How to use and maintain this reference

The original proposal defines the project concept. This reference records the inspected files and recommends implementation decisions. The procedure describes future work; its proposed modules and outputs do not already exist. Changing the research scope, eligibility rules, signs, timing boundaries, or target definitions requires an explicit entry in the project decision log.

Before changing code, locate the relevant source below, read the field dictionary, identify the module that should own the calculation, and check the validation that protects it. Update this reference and the procedure when the implementation changes their assumptions. Retain the original proposal and source exports unchanged.

The machine-readable companions provide exhaustive detail without repeating 193 identical folder descriptions:

- `F1_File_Inventory.csv` lists every original file, its exact path, size, row and column counts where applicable, SHA256 digest, and intended use.
- `F1_Field_Dictionary.csv` lists every CSV field by table family, its intended use, units or representation, decision-time availability, and cautions. A field name is not proof that the exporter implemented its claimed timing correctly.
- `F1_Session_Index.csv` lists all 193 event folders, all seven CSV row counts, and manifest provenance.
- `_audit/` retains the inspection scripts and detailed checks used for these notes. These are documentation support, not the planned R analysis pipeline.

## 2 Current project state

The original workspace contains the proposal and `F1_Pit_Wall_2018_2026/`. No application code, extraction code, model object, R project file, dependency lockfile, or tests were found. The matching accessible GitHub repository, `astrosumit-051/f1_analytics`, returned an empty-repository response on November 19 2026. Treat repository setup as an early implementation task, and verify the intended remote before publishing.

The export records an extraction cutoff of `2026-11-12T18:27:09.485838+00:00`. Its last catalogued event is `2026_20`, labelled Brazilian Grand Prix, dated November 8 2026. This is a frozen snapshot, rather than a claim about coverage after that cutoff. The files total 289,525,641 bytes, approximately 276 MiB, including the proposal. Recorded extraction settings are `max_gap = 3.5` seconds and `max_offset = 1` lap; the initial battle sample is therefore deliberately restricted to close rivals and short stop offsets.

| Source control | Verified amount | Meaning for the project |
| --- | --- | --- |
| Original files | 1,565 | Proposal plus 1,564 data and provenance files |
| Event folders | 193 | Eight files per event, including a manifest |
| Lap observations | 213,132 | Main pool for pace preparation and historical timing |
| Pit-stop rows | 7,054 | 6,767 matched and 287 invalid stop records |
| Candidate battles | 851 | 841 matched pairs and 10 pair errors |
| Initially eligible battles | 354 in 123 races | Subject to additional timing and provenance review |
| Candidate pit offsets | All equal 1 lap | Same-lap cover has no direct example in this candidate sample |

The combined lap key `(year, round, DriverId, LapNumber)` has no duplicates. Feature and target exports each have 354 rows, unique composite keys, and matching key sets. Counts of event laps, stops, battles, weather, and track status reconcile with `race_coverage.csv`. These checks establish structural consistency; they do not establish independent source accuracy or validate alternative strategies.

## 3 Folder map and intended use

### Project root

`F1_Pit_Wall_Project_Proposal.docx` explains the research question, one-cycle scope, 10,000-trial comparisons, model validation, and interactive presentation. Use it to resolve product intent and distinguish required first-version work from later extensions. It is not an executable specification of every exported metric.

`Planning/` contains this reference, the step-by-step coding procedure, their Word versions, and the inventory companions. Read the Markdown versions during coding because they are easy to search and update. Keep their Word exports synchronized when sharing a revised plan.

### Combined data files

All paths in this subsection are relative to `F1_Pit_Wall_2018_2026/`.

| File | Rows and fields | Use and ownership |
| --- | --- | --- |
| `completed_race_catalog.csv` | 193 by 8 | Event dimension for stable IDs, circuit joins, labels, dates, and chronological splits |
| `catalog_coverage.csv` | 9 by 3 | Count catalogued races by year and detect incomplete refreshes |
| `race_coverage.csv` | 193 by 14 | Reconcile source coverage, matched stops, candidate counts, and model sample losses |
| `all_laps_enriched.csv` | 213,132 by 72 | Canonical combined input for lap filtering, predecision histories, pace fitting, and clock reconstruction |
| `all_pit_stops.csv` | 7,054 by 14 | Pit entry and exit intervals, match status, and observed compound changes |
| `pit_battles_all.csv` | 851 by 81 | Audit all candidate pairs and explain every exclusion |
| `pit_battles_model_ready.csv` | 354 by 81 | Starting observed sample for descriptive analysis and historical evaluation, after further review |
| `model_features.csv` | 354 by 19 | Convenient predecision predictor export for a simple observed-outcome baseline |
| `model_targets.csv` | 354 by 8 | Observed gain and pass targets joined to features by explicit keys |
| `run_metadata.json` | One run record | Snapshot cutoff, extraction settings, source labels, expected totals, and default predictor list |
| `source_access_checks.json` | Two checks | Access smoke tests for `2018_01` and `2026_20`; not validation of all events |

Use the combined lap and stop tables for normal analysis. Read individual sessions to investigate a case or rebuild a combined table. Concatenating the combined data with their event copies would duplicate the same observations.

### Catalog folder

`catalog/2018_winners.json` through `catalog/2026_winners.json` are nine cached responses containing event information and winner records. Use their `fetched_at_utc`, `endpoint`, and `races` entries to trace the catalog back to its recorded source. Winner records are not a complete race classification and cannot supply all driver mappings. The winner identity and finish time are postrace information; they must not enter a decision-time prediction.

### Session folders

Every `sessions/YYYY_RR/` directory has the following files. Derive `event_id`, `year`, and `round` from a validated folder name when the CSV does not contain them.

| File in each event | What it should achieve |
| --- | --- |
| `laps.csv` | Inspect each driver's lap clock, tyres, sectors, accuracy flags, and predecision history |
| `pit_stops.csv` | Connect a stop lap to its next outlap and pit-lane interval |
| `pit_battles.csv` | Trace a combined candidate back to the original event pairing and diagnostics |
| `results.csv` | Map `DriverId`, abbreviation, number, team, and display name within that event; inspect final results only for audit |
| `weather.csv` | Supply timestamped weather for backward joins and observed dry-window checks |
| `track_status.csv` | Build track-status intervals and reject non-green or unknown comparison windows |
| `race_control_messages.csv` | Explain unusual timing, incidents, deletions, or status transitions through source messages |
| `manifest.json` | Record schema version, status, download timestamp, event label, provider version, source, and weather-alignment policy |

Across all sessions there are 3,898 result rows, 29,053 weather observations, 2,429 track-status rows, and 18,655 race-control messages. Inspect these streams on their own clocks; row numbers do not align with lap row numbers.

## 4 Data relationships and import contracts

Use `event_id = YYYY_RR` as the event key, preserving leading zeroes in the round. Validate its one-to-one mapping to `(year, round)` and join the event dimension before modeling. `all_laps_enriched.csv` does not have an `event_id` column, so create it explicitly from `year` and `round`.

Use `DriverId` and `driver_ref` as canonical driver identifiers. Treat abbreviations, display names, and car numbers as event-scoped aliases. A driver-stop record should be unique by `(event_id, driver_ref, stop_lap)` after validating stop numbering. A battle is identified by its stable `battle_id`; retain `source_row_id` as an audit pointer within this snapshot. Join features and targets using all shared identification columns and confirm one-to-one cardinality, never their row positions.

Laps and results require a many-to-one join on event and canonical driver. Stops attach to a driver's inlap and outlap by explicit lap numbers. Weather and status use time-based joins within an event. Do not join weather by lap number or combine clocks from different races.

Read status codes, IDs, and categorical strings as text. Parse blank booleans as unknown instead of false. Use existing numeric `*_sec` fields for calculations after checking them against their duration-string counterparts. The `index` column is an export artifact, not a key.

The union of field names is the import schema; individual event files vary. `2018_01/laps.csv` has 63 fields instead of 72, `2018_01/weather.csv` has four headers and zero rows, and its race-control file has no header or rows. Twenty-six event battle files have zero rows and only 15 headers. Other battle schemas contain 70, 77, or 78 fields; `2025_06` has the 77-field variant. Import known empty files as typed empty tables and align columns by name with explicit missing values. Do not silently discard unreadable nonempty files.

## 5 Timing and metric definitions

### Lap clocks and pit intervals

`LapTime_sec` is a duration. `Time_sec` is the recorded lap-end session clock. `LapStartTime_sec`, pit entry, pit exit, and sector session clocks are timestamps relative to a session origin. They serve different purposes and must not be subtracted or accumulated as though all were lap durations. Absolute `LapStartDate` timestamps are a separate representation.

`pitlane_elapsed_sec = pit_exit_sec - pit_entry_sec`. It includes driving through the lane and servicing, plus any other delay between those timing points. It is neither stationary service time nor the full time lost relative to staying on the track. The pit route replaces part of the normal racing route.

`TyreLife` is tyre age and can include prior use. `Stint` is a stint label. `FreshTyre` describes the set's state at stint start. Keep tyre age separate from laps since the current stop and verify the exported age convention before increasing it in the simulator. Preserve the historical labels `SUPERSOFT`, `ULTRASOFT`, and `HYPERSOFT`; do not silently equate them with a later season's `SOFT` tyre.

### Historical gap convention

For the existing earlier stopper U and later stopper O, define the same-lap crossing gap as `g(lap) = T_U(lap) - T_O(lap)`. A positive value means U is behind; a negative value means U is ahead. Keep this sign when the focal driver's selected strategy changes.

| Metric | Definition and intended interpretation |
| --- | --- |
| `gap_before_recomputed_sec` | Recomputed precycle gap, positive when the earlier stopper trails |
| `gap_after_recomputed_sec` | Gap at the exported common `comparison_lap` |
| `net_gap_gain_recomputed_sec` | Before gap minus after gap; positive means time gained by the earlier stopper |
| `pass_recomputed` | True exactly when the after gap is below zero in the eligible export |
| `pitlane_duration_delta_over_minus_under_sec` | Later stopper lane duration minus earlier stopper lane duration |
| `gap_gain_excluding_pitlane_duration_diff_sec` | Net gap gain minus that lane-duration delta; an equal-duration sensitivity measure |
| `crew_adjusted_gap_gain_sec` | Unavailable in the snapshot; do not calculate or display it as zero |

The first two algebraic identities reproduce the export to within about 0.000000000001 seconds, and the pass flag agrees with a negative after gap for all 354 eligible rows. Every eligible `comparison_lap` equals `pit_lap_over + 1`. Record the precise before-boundary rule after reconstructing it from event laps; the supplied exporter source is absent.

For example, `2018_07:alonso:18:leclerc:19` starts at +0.660 seconds and ends at -0.734 seconds, giving +1.394 seconds of gain. The lane-duration delta is +0.599 seconds, so the adjusted gain is +0.795 seconds. This arithmetic is a useful sign check, rather than proof of a causal tyre advantage.

An observed pass means emerging ahead at the comparison boundary. It does not prove a wheel-to-wheel overtake occurred, and positive time gain alone does not imply the initial gap was erased.

### Predecision predictors

The metadata lists 15 default predictors: `year`, `circuitRef`, recomputed initial gap, both old compounds, both predecision tyre ages, tyre-age difference, relative recent pace, later stopper degradation slope, and five decision-weather measurements. Identification columns are for joins and grouped splits.

The names `pace_delta_pre_recomputed_sec` and `over_deg_slope_pre_sec_per_lap` suggest a pace difference and a slope, but their exact lookback, sign, minimum lap count, and clock cutoff need to be recovered or redefined explicitly. Check that both drivers' inputs are available at the same decision cutoff. A `_pre` suffix alone does not establish this.

The ready sample has 45 missing pace differences and 37 missing degradation slopes. Imputation, missingness indicators, and category pooling must be learned inside each training fold. Do not drop rows silently or fit preprocessing to the final holdout. Keep a simpler fallback predictor set if these features remain unreliable.

### Outcomes and diagnostics that arrive later

Observed new compounds, warm-up proxies, inlap times, outlap times, outlap sectors, pit-lane durations, postcycle gaps, pass outcomes, and full-window contamination flags describe the realized stop cycle. Use them for training targets, reconstruction, distribution estimation on training races, and later validation. They are not ordinary predictors available before the stop.

A planned replacement compound, user-assumed extra delay, or fixed rival pit lap is a scenario assumption, which must be labelled separately from an observed measurement. Future actual weather must not leak into a decision-time forecast. Historical full-window dry/green filters define the retrospective sample; a future green window remains a scenario condition.

`under_warmup_proxy_observed_sec` and its over-stopper counterpart are pace proxies, with 47 and 59 missing values respectively in the eligible sample. They do not measure tyre temperature. `under_stationary_sec`, `over_stationary_sec`, and `crew_adjusted_gap_gain_sec` are entirely missing across all 851 candidates. `input_net_gain_difference_sec` is also entirely missing and therefore cannot certify target agreement.

### Lap fields that serve supporting roles

Keep sector durations and sector clocks for reconstruction and double-counting checks. Speed measurements can explain odd laps but are optional extensions. `LapTimeSeconds`, `LapTime_sec`, and the duration-string lap time represent overlapping information; choose one validated numeric owner. The units and meaning of `ms1`, `ms2`, and `ms3` are undocumented in the supplied export and should remain excluded until verified.

Use `IsAccurate`, `FastF1Generated`, `Deleted`, and `DeletedReason` to define purpose-specific quality rules. Normal pace training and pit-cycle timing need different rules: pit laps cannot be removed merely because a normal-lap accuracy rule excludes them. Current FastF1 documentation treats `IsAccurate` as a synchronization flag, rather than a universal certificate of timing truth. The archived exporter may implement its flags differently and needs its own checks.

Read `TrackStatus` as a string of status codes, not a continuous number. Values such as `12` and `671` occur. Combine the lap string with timestamped `track_status.csv` intervals when evaluating a window. A missing status is unknown. For a strict first version, require a documented green state throughout the window.

Use the backward-aligned weather fields `WeatherTime_sec`, `TrackTemp`, `AirTemp`, `Humidity`, `Pressure`, `Rainfall`, `WindDirection`, `WindSpeed`, and `WeatherSampleAge_sec`. Manifests describe backward alignment at lap start with a 120-second tolerance. Preserve `archive_observed_*` fields for comparison, since they can refer to a different sampling time. The combined aligned weather fields are missing on 1,064 laps; never replace unknown rainfall with dry conditions.

## 6 Quality issues and decisions before modeling

### Timing cases named in the proposal

The proposal calls for withholding three flagged timing cases but gives no battle IDs. The supplied tables have no explicit three-case quarantine flag. Initial checks found no eligible row with more than 0.05 seconds of disagreement in the exported initial gap, or more than 0.10 seconds of consecutive lap-end clock versus lap-duration disagreement in the checked cycle windows. These limited checks do not identify or clear the three cases.

Recover their IDs from the original analysis or reproduce the original diagnostic. Maintain `timing_review.csv` with event, battle, reason, evidence, and disposition. Hold named cases out until resolved, and do not call the 354-row export fully cleared while this issue is unresolved. Extreme gains alone are not a valid way to choose three rows for deletion.

### Coverage and representativeness

The eligible sample ranges from about 0.254 to 3.496 seconds of initial gap and contains only one-lap offsets. Bahrain has 34 eligible battles, Hungaroring 30, and Spa 28, while several circuits have one to three. Display counts with every subgroup and fit a pooled model before adding circuit-specific effects. Support thresholds should consider independent races, laps, and compound transitions after final filtering, rather than candidate battle counts alone.

Observed net gains span approximately -28.242 to +28.716 seconds. Large lane-duration differences explain part of those extremes, so preserve genuine slow stops when modeling execution risk. Audit impossible intervals and incomplete stops separately. The 31.1 percent observed pass rate is descriptive for this selected sample, not the expected win probability of a new strategy.

The exclusion labels overlap. Among all candidates, 408 carry a non-green or unknown-status reason, 337 incomplete or flagged timing, 277 an additional stop, 137 unknown or non-dry compounds, and 103 rain or unknown weather. Do not add these counts to produce a unique excluded total; exactly 497 candidates are outside the initial 354-row sample.

### Provenance and event labels

All combined lap rows are labelled `data_source = archive`; track status is labelled as derived from race-control messages and lap status. Provider version `0.11.3` is recorded without supplied extraction code. Keep those limitations visible in the technical documentation and preserve source timestamps.

The catalog labels `2026_16` as `Bahrain Grand Prix in Malaysia` with `circuitRef = sepang`. Also, the latest event uses Brazilian Grand Prix in the catalog and Sao Paulo Grand Prix in its manifest. Resolve event identity through stable keys and verify unusual labels against the recorded upstream source before using them in the demo. The inspection establishes what the files contain, not that all labels are correct.

## 7 Proposed R code ownership

The following paths are planned responsibilities. Create them in the coding phase only when needed. Keep the existing data directory as the read-only input root.

| Proposed path | Responsibility |
| --- | --- |
| `config/project_config.R` | Input root, cutoff, eligibility, seeds, trial counts, timing tolerance, and support thresholds |
| `R/01_import.R` | Typed imports, schema alignment, event and driver keys, source inventory |
| `R/02_validate_sources.R` | Structural checks, coverage reconciliation, review records, and source diagnostics |
| `R/03_reconstruct_battles.R` | Lap clocks, shared boundaries, gaps, pass flags, stop matching, and eligibility |
| `R/04_build_features.R` | Cutoff-safe histories, lap samples, battle predictors, and split assignments |
| `R/05_fit_pace.R` | Baseline and pooled pace models fitted using training data only |
| `R/06_fit_pit_cycle.R` | Pit-cycle excess, warm-up treatment, and execution uncertainty without duplicate delays |
| `R/07_simulate.R` | Deterministic clock engine and paired Monte Carlo trials |
| `R/08_evaluate.R` | Held-out pace errors, gain errors, Brier scores, calibration, and race bootstrap |
| `R/09_scenarios.R` | Supported demo cases, input ranges, sensitivity grids, and replay summaries |
| `scripts/build_project.R` | Ordered offline preparation, fitting, evaluation, and saved artifacts |
| `app.R` and `R/shiny_modules.R` | Shiny launch and interface components using saved results and the shared simulator |
| `data_processed/` and `models/` | Regenerable RDS tables, fitted objects, preprocessing, and version manifests |
| `outputs/` and `tests/` | Analysis results and meaningful contract tests |

No interface component should redefine a gap, select a training sample, or fit a separate model. No model should depend on Shiny inputs. Store configuration and model metadata with outputs so an offline result and the displayed result are traceable to the same computation.

## 8 Simulation contract

Use stable focal and rival identities. If the rival pits on lap K, the focal options are K minus 1, K, and K plus 1. Begin all three simulations at the same earlier completed-lap boundary with the same gap and tyre state. Choose a common terminal lap after the latest focal outlap; for this schedule, K plus 2 is a proposed default. Verify both cars complete that boundary without another stop or retirement in historical validation.

Store focal-minus-rival final gap in seconds. Report the fraction of trials with gap below zero, expected signed gap, and the 5th to 95th percentile interval of final gaps. This central 90 percent prediction interval describes simulated outcomes. A bootstrap confidence interval for an estimated probability and the Monte Carlo sampling error describe different uncertainties and need separate labels.

Start with a deterministic engine and zero uncertainty. Add shared race conditions, driver and lap residuals, and stop uncertainty only after the timing ledger reconciles. Use the same trial IDs and shared random conditions across alternatives. Preserve dependence between the two drivers and between adjacent laps where the data support it. Use training residuals, rather than assuming every source of variation is independent and normally distributed.

A normal-lap prediction already includes racing through the part of track that the pit route replaces. Adding full pit-lane duration on top would count overlapping time. The proposed first implementation models a joint inlap and outlap excess over the corresponding normal-lap predictions, then adds that excess once. Any pit-duration effect and outlap warm-up effect already represented in that excess must not be added again. Model additional early-stint effects on subsequent full laps separately. Compare detailed decompositions only after route and timing overlap have been established.

Compute extra pit-delay tolerance by adding nonnegative delay to the focal driver's clock and finding when its chance of finishing ahead crosses a declared threshold, initially 50 percent. State when it is already below the threshold or the crossing lies outside the tested range. This is a delay sensitivity, not a diagnosis of crew performance.

## 9 Change checklist and evidence

For every substantive code change, record the affected file and metric, the reason, the sample impact, and the checks rerun. Gap or stop changes require sign identities and event reconstruction. Feature changes require a cutoff audit and fold preprocessing checks. Model changes require held-out comparison with the same baseline and split. Simulation changes require deterministic ledgers, delay monotonicity, common endpoints, and fixed-seed reproducibility. UI changes require confirming that displayed values match saved engine outputs.

Maintain a decision log with date, decision, evidence, and affected modules. Resolve timing IDs, source labels, pace-feature definitions, tyre-age increments, support limits, and pit-cycle overlap before presenting model conclusions. Do not substitute an unavailable measurement or silently widen the first-version scope.

Local evidence is retained in `_audit/summary.json`, `_audit/schemas.json`, `_audit/profiles.json`, `_audit/sessions.json`, and the complete inventory. Source definitions were also checked against the official FastF1 timing and time-reference documentation; Shiny caching design was checked against Posit guidance. These external references describe software semantics, while the local archive still requires exporter-specific verification.

- FastF1 timing fields: https://github.com/theOehrly/Fast-F1/blob/main/docs/api_reference/timing_data.rst
- FastF1 timing clocks: https://github.com/theOehrly/Fast-F1/blob/main/docs/data_reference/time_explanation.rst
- Posit Shiny event and cache guidance: https://shiny.posit.co/r/articles/improve/caching/
- Matching GitHub repository: https://github.com/astrosumit-051/f1_analytics
