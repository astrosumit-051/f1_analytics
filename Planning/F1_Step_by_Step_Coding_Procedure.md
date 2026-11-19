# F1 Pit Wall Coding Procedure

Prepared November 19 2026

We will build the project in R and Shiny in the order below. First establish reliable source tables and timing, then fit and validate the analytical components, then connect the shared simulator to the interface. Each numbered step contains concrete substeps, proposed code ownership, an output, and a condition for moving forward. These are implementation tasks, not a record of completed coding.

The first release compares one pit cycle in dry, green-track conditions with a fixed rival stop lap. It uses a pooled pace model, 10,000 paired trials per strategy, and two or three historical scenarios. Alternative rival responses, traffic behavior, broader weather conditions, and full-race optimization follow only after the first release works and its limitations are clear.

Use `F1_Data_and_Code_Reference.md` before changing calculations. Use the field dictionary for individual columns and the file inventory to find the original evidence. Preserve the source exports throughout this procedure.

## 1 Establish the project contract

1.1 Read the research question and first-version scope in the proposal alongside the reference. List the required analytical outputs: historical comparisons, pace predictions, strategy probabilities, expected gaps, prediction intervals, delay tolerance, and validation results.

1.2 Write a short `docs/decision_log.md`. Record R and Shiny as the selected stack, one pit cycle as the unit of strategy comparison, and observed versus simulated outcomes as distinct result types.

1.3 Define focal driver and rival as stable identities. Historical labels `driver_undercut` and `driver_overcut` describe an observed ordering; they must not swap identities when a user selects another strategy.

1.4 Adopt signed gap `focal time minus rival time`: positive means behind. Define a pass outcome as being ahead at the common comparison boundary, rather than gaining any positive amount of time.

1.5 Fix initial scenario conventions: rival pit lap K, focal pit laps K minus 1, K, and K plus 1; one common initial boundary; and one terminal lap after both stops and the latest outlap. Record which choices are assumptions requiring sensitivity analysis.

1.6 Create an open-questions list for the unnamed three timing cases, source event labels, undocumented pace lookbacks, tyre-age convention, and pit-cycle overlap. Give each question an evidence path and a resolution criterion.

Output: a decision log and a concise model contract. Move forward when everyone can interpret the same final-gap number and identify which claims are observed and which are conditional.

## 2 Create the R project and repository structure

2.1 Verify that `astrosumit-051/f1_analytics` is the intended shared remote. It was empty during this review. Check team access during actual repository setup; do not assume a branch or an existing application is available.

2.2 Create an RStudio project with `R/`, `config/`, `scripts/`, `tests/`, `docs/`, `data_processed/`, `models/`, and `outputs/`. Retain `F1_Pit_Wall_2018_2026/` as the input root. Create directories as they become useful rather than adding empty scaffolding for every possible extension.

2.3 Set up dependency management and record the R version. Keep the initial package set small: a CSV reader, data manipulation, plotting, Shiny, and testing. Use base R modeling first; add a modeling package only for a defined need. Record actual package versions in the lockfile when installed.

2.4 Keep input roots relative to the project or configurable through an environment variable. Do not hardcode a team member's OneDrive path in analysis functions. Add a sample configuration that contains no personal paths or credentials.

2.5 Write `.gitignore` for local caches, temporary files, generated renders, and large raw inputs. Decide whether the source snapshot is distributed separately or through Git LFS. The 140,206,211-byte combined lap CSV is larger than GitHub's ordinary 100 MiB file limit. Do not attempt a normal Git commit of that file.

2.6 Put installation, data placement, build, and app-launch instructions in `README.md`. Keep source code and regenerable outputs clearly distinguished. Plan short commits around completed procedure steps.

Output: a portable project skeleton and reproducible environment definition. Move forward when the project opens from its root and the data location resolves on a second machine or a clean-path test.

## 3 Centralize configuration and output contracts

3.1 Create `config/project_config.R` with source root, snapshot cutoff, eligibility settings, timing tolerances, feature lookbacks, train and test years, random seed, trial count, and support rules. Store assumptions once.

3.2 Set a production simulation default of 10,000 trials per strategy. Use a smaller named development setting only for development and label it in intermediate results.

3.3 Define result-table schemas before coding consumers. Include scenario ID, stable drivers, strategy, rival and focal pit laps, initial and terminal boundaries, trial ID, final signed gap, and model version.

3.4 Define summary columns for probability ahead, mean signed gap, 5th and 95th gap percentiles, Monte Carlo standard error, and sample support. Bootstrap confidence intervals will be separate columns when available.

3.5 Decide tie handling explicitly. The existing export uses `gap_after < 0`; retain that rule for reproduction. If the simulator uses a numerical tolerance, report ties separately and do not silently redefine the historical target.

3.6 Save source hash, configuration hash, preprocessing version, model version, seed, and run time with every generated result. Separate the data cutoff from the date when the output was generated.

Output: configuration and shared table contracts. Move forward when each later module has declared inputs and outputs and no repeated hidden constants.

## 4 Import every source with explicit types

4.1 Implement `R/01_import.R`. Read the combined catalog, coverage, laps, stops, battles, features, and targets without editing the CSVs. Import identifiers and status strings as text and preserve unknown logical values.

4.2 Parse numeric seconds and date fields deliberately. Retain original duration strings for cross-checks. Reject impossible year-round combinations and malformed folder names.

4.3 Create `event_id` in combined laps from `year` and zero-padded `round`. Join the event dimension to add circuit and date. Fail clearly on missing or conflicting event matches.

4.4 Write a session reader that adds folder-derived keys, recognizes documented empty files, and aligns columns by name. Cover the 63-field first-event lap file, four-field empty weather file, headerless empty message file, and the different battle schemas.

4.5 Import event results as a driver identity dimension. Check car numbers, abbreviations, and canonical IDs within each event. Retain finishing results for audit separately from prediction features.

4.6 Import JSON metadata, session manifests, and catalog responses for provenance. Record schema version and weather policy without assuming that a provider label proves every measurement is valid.

Output: typed R tables and a source manifest in `data_processed/`. Move forward when all 193 events import, documented empty files are handled explicitly, and unexpected parse failures remain visible.

## 5 Reconcile counts and relationships

5.1 Implement structural checks in `R/02_validate_sources.R`. Reproduce 193 catalog events, 213,132 combined laps, 7,054 stop rows, 851 candidates, and 354 initially eligible battles.

5.2 Compare each event file's row counts with `race_coverage.csv` and compare grouped totals with `run_metadata.json`. Separate the 6,767 matched stops from 287 invalid rows.

5.3 Assert uniqueness of the lap key, event key, and intended stop key. Investigate duplicates before choosing any deduplication rule. Compare combined records with event copies on stable keys and relevant values, not counts alone.

5.4 Join features and targets by identifiers with a one-to-one relationship. Assert matching key sets and ensure no accidental row multiplication. Retain keys as audit columns and exclude them from predictors.

5.5 Summarize missingness by year, race, circuit, and table. Verify whether missing fields are structural, such as the empty weather stream, or intermittent observations.

5.6 Create `outputs/source_validation.csv` containing each check, expected value, observed value, and evidence. Stop dependent processing when a required source contract fails, while allowing independent diagnostics to run.

Output: reconciled source tables and a validation report. Move forward when unexplained key or value mismatches have been resolved or explicitly isolated from analysis.

## 6 Resolve source questions and timing review

6.1 Inspect the original analysis materials for the three timing cases referenced in the proposal. If the IDs remain unavailable, record this as unresolved rather than guessing from large gains.

6.2 Create `docs/timing_review.csv` with `event_id`, `battle_id`, affected metric, diagnostic, evidence, reviewer decision, and resolution date. Add identified suspect cases before constructing final training and evaluation samples.

6.3 Verify event identity for unusual source labels, especially `2026_16` labelled Bahrain Grand Prix in Malaysia at Sepang. Check catalog keys against the recorded upstream response and an authoritative event source. Correct a mapping in a derived lookup only after documenting the evidence; preserve the original files.

6.4 Compare lap duration with consecutive end-clock differences, available sector sums, and inlap/outlap order around candidate cycles. Handle missing laps, retirements, and mixed timing representations explicitly.

6.5 Investigate invalid stop rows using `stop_error`. Separate impossible clock order, missing entry or exit, and genuine unusually long intervals. Do not trim a real slow stop merely because it affects a strategy result.

6.6 Confirm the accuracy flags' behavior in this archive. Define separate quality rules for normal pace fitting, pit-cycle reconstruction, and descriptive source audit.

Output: a source correction lookup where justified and a timing review registry. Move forward with model fitting only when the intended sample's unresolved timing cases can be identified and withheld, or the proposal's original diagnostic has been reproduced and its concern resolved.

## 7 Rebuild observed battle outcomes

7.1 Implement `R/03_reconstruct_battles.R`. Match each candidate's two drivers to its stop records and lap histories. Validate that the specified stop lap and outlap form a complete cycle.

7.2 Recover the exported precycle boundary rule from the laps. Show that both drivers are compared at the same completed lap and that the initial gap is measured before the focal stop decision. Record the exact rule in the reference.

7.3 Recompute the common comparison gap at `comparison_lap`. In the current ready export, this is the later stop lap plus one. Reject cycles where either driver lacks the required endpoint or has an additional stop inside the window.

7.4 Recompute net gain as before minus after, pass as after below zero, lane-duration delta as rival minus focal, and adjusted gain as net gain minus that delta. Assert identities using a small documented tolerance.

7.5 Compare each rebuilt target with the combined export, retaining discrepancy columns and review status. `input_net_gain_difference_sec` is empty in the source and cannot substitute for this check.

7.6 Review representative ordinary and extreme outcomes by printing a short timing ledger. Include the Alonso and Leclerc Canadian 2018 case as a simple sign check, plus a slow-stop case and a missing-data case.

Output: `data_processed/battles_rebuilt.rds` and an event-level discrepancy report. Move forward when each retained target has a traceable ledger and no unexplained timing mismatch.

## 8 Define final samples and describe the evidence

8.1 Build a retrospective battle eligibility function requiring a verified pair, complete comparison boundary, dry known conditions, green known status, valid timing, known dry compounds, and no extra stop. Apply the timing review registry.

8.2 Parse semicolon-separated exclusion reasons into a long audit table, while keeping one row per candidate in the main table. Record the unique retained and excluded totals as well as overlapping reason counts.

8.3 Build a separate normal-lap sample for pace estimation. Exclude pit inlaps and outlaps, generated or unusable laps, unknown tyre state, non-green periods, wet conditions, and other documented contamination. Do not apply that normal-lap filter blindly to the pit-cycle sample.

8.4 Produce sample flow summaries by year and circuit. Show battle counts, independent race counts, valid laps, and supported compound transitions. Choose support thresholds using training data and record the rationale before evaluating held-out performance.

8.5 Describe observed initial gaps, gains, pass rates, tyre ages, and lane-duration distributions. Compare raw and equal-lane-duration outcomes, with sample counts beside subgroup summaries.

8.6 Write a short historical-results note explaining that the selected sample includes only one-lap earlier-versus-later stops. Do not use its pass rate as proof of an undercut advantage over cover or overcut in otherwise identical conditions.

Output: final sample tables, a sample-flow report, and descriptive plots. Move forward when the distinction between the battle sample and pace sample is explicit and the descriptive results reconcile with retained records.

## 9 Freeze chronological validation splits

9.1 Implement split assignment before learning imputation, feature scaling, category pooling, pace models, or residual distributions. Keep every record from an event in the same split, across all table types.

9.2 Start with the proposed split of 2018 through 2023 for development training, 2024 for model selection, and 2025 through the snapshot cutoff for final testing. Revisit this only if final sample support makes it unusable, and document any change before looking at final results.

9.3 For tuning within earlier years, use expanding chronological training windows followed by later validation races. Avoid random row splits that place the same race in both training and validation.

9.4 Save `data_processed/split_manifest.rds` keyed by event. Check that no event appears in more than one partition and that all dependent tables use this same manifest.

9.5 Distinguish fitting from within-race updating. A test scenario may use laps completed before its decision to estimate current relative pace, but cannot use future laps, full-race averages, or event effects learned from its later observations.

9.6 Set aside the final test metrics until the pipeline, baseline, and uncertainty settings are frozen. Use development and validation results for implementation decisions.

Output: a saved split manifest and validation protocol. Move forward when preprocessing and fitting can consume training data without reading final-test outcomes.

## 10 Build features available at the decision

10.1 Implement `R/04_build_features.R`. For every scenario, define one decision clock and attach only observations recorded no later than that clock. Preserve both the source timestamp and the cutoff used for each derived feature.

10.2 Rebuild recent driver pace using a documented trailing window, such as the last three eligible completed laps, with a minimum count and a missing fallback. Treat this window as an initial design choice, not a recovered exporter fact.

10.3 Define pace-difference sign explicitly and verify it with a case where one driver is visibly faster. Build degradation slopes from past eligible laps only and record the minimum tyre-age range and number of observations required.

10.4 Capture both old compounds, predecision tyre ages, tyre-age difference, circuit, season or era, lap progress, and backward-aligned weather. Verify tyre-life increments on actual stop transitions. Normalize progress only with a known scheduled race distance; otherwise use lap number directly, rather than a driver's eventual completed laps.

10.5 Join weather backward with an age limit, initially the recorded 120-second policy. Expose stale or missing weather. Use planned weather assumptions beyond the decision, instead of later observed samples, when forecasting.

10.6 Fit numeric imputation and missingness indicators on the training fold. Handle unseen compounds and circuits through a documented pooled fallback or unsupported status. Do not convert missing pace or rain to zero by default.

10.7 Keep observed postdecision values out of the feature matrix. A user-selected replacement compound and assumed rival stop lap belong in a scenario-input object with their assumption labels.

Output: cutoff-audited battle features, pace-learning rows, and fitted preprocessing. Move forward when a deliberately added future observation cannot change an earlier scenario's predictor values.

## 11 Fit simple baselines first

11.1 Implement a recent-pace lap baseline, using only the predecision history available for that driver. Define a fallback when fewer than the required number of laps exist.

11.2 Fit a simple observed-battle probability baseline on the verified predecision predictors, alongside a training-frequency baseline. Keep the classifier's role separate from the mechanism that simulates new schedules.

11.3 Evaluate lap mean absolute error and observed-outcome Brier score on the validation period. Keep predicted values per record so later models can be compared on exactly the same rows.

11.4 Check baseline behavior by circuit, era, tyre age, and missing-history status. Report counts before interpreting a subgroup difference.

11.5 Save the baseline models, preprocessing, and evaluation rows. Use their performance to decide whether more complexity earns its cost.

Output: baseline predictions and a comparison table. Move forward when later models have an explicit reference to beat and failures are visible without the interface.

## 12 Fit and validate the pooled pace model

12.1 Implement `R/05_fit_pace.R` with a simple pooled model of normal lap duration. Include circuit, compound, tyre age, race progress, track temperature, and a driver pace offset estimated from available prior history. Represent season or tyre era deliberately.

12.2 Start with interpretable linear or modest nonlinear effects. Avoid a separate fitted model for every circuit-compound combination when independent race support is weak.

12.3 Separate tyre age from race progress so a downward race-time trend is not automatically interpreted as improving tyres. Check correlation and instability before adding interactions.

12.4 Do not estimate a held-out race's intercept from all its laps. Use the trained pooled model and allowed early-race information to anchor a scenario. Define a fallback for a driver with no recent usable history.

12.5 Evaluate held-out lap mean absolute error, signed bias, and error by tyre age and compound. Compare with recent pace on the same rows. Inspect residuals by race and within-driver sequence.

12.6 Save a training-only residual pool with event IDs and context. Use validation residuals to assess the noise design, not to populate the final training noise pool without an explicit refit stage.

12.7 If the pooled model does not improve on the baseline or behaves implausibly, retain the baseline for that component and document the limitation. A more complicated model is not a completion criterion.

Output: a selected pace predictor, preprocessing object, model card, and residual diagnostics. Move forward when performance is measured on later races and the predictor can score a supported scenario without future data.

## 13 Model pit cycles and warm up without overlap

13.1 Implement `R/06_fit_pit_cycle.R`. Build complete inlap and outlap pairs for matched stops, maintaining observed tyre transitions and the pit entry and exit interval.

13.2 Predict the corresponding normal-lap components using the appropriate old and replacement tyre states. Define joint cycle excess as observed inlap plus outlap duration minus those predicted normal components.

13.3 Treat that excess as the initial owner of route loss, pit execution, and any outlap warm-up already present. Add it to the simulated clock once. Do not also add the full `pitlane_elapsed_sec` or an observed outlap penalty on top.

13.4 If pit-lane duration is used to model excess, fit its relationship on training races and sample it jointly with the remaining excess residual. For example, use duration deviation from a conditional center as a predictor of excess; do not sample a duplicate independent execution shock.

13.5 Estimate additional early-stint pace effects on subsequent full laps, separately from the outlap. Use compound, tyre age, and context where supported. Call these pace patterns warm-up proxies because tyre temperatures and fuel loads are absent.

13.6 Preserve valid long-stop tails and condition or pool by circuit and era when needed. Reject impossible intervals with reasons. Do not label lane-duration differences as measured crew mistakes.

13.7 Verify a component ledger against observed cycles. Where inlap/outlap allocation is not identified reliably, retain a joint excess and use a labelled schematic allocation in the replay rather than implying precise physical location.

Output: a joint pit-cycle model, documented early-stint treatment, and training-only uncertainty distribution. Move forward when the same observed delay cannot enter two components of the clock.

## 14 Implement the deterministic strategy engine

14.1 Implement `R/07_simulate.R` as pure functions that accept a scenario, model bundle, configuration, and optional random draws. They must not depend on Shiny state.

14.2 Validate the scenario before simulating: stable driver IDs, a supported circuit and compounds, feasible tyre ages, known initial gap, sufficient remaining laps, and a declared rival pit lap.

14.3 For rival lap K, set the shared initial completed lap to K minus 2 as a proposed default. Initialize the two arrival clocks with the observed signed gap and simulate focal stops on K minus 1, K, and K plus 1.

14.4 Evolve normal-lap pace, compound transitions, tyre age, and the single pit-cycle excess. Show explicitly which lap receives each part of the excess. Reject a stop that would occur before the initial boundary.

14.5 Evaluate all strategies at the same endpoint, initially K plus 2. Do not stop a strategy's calculation as soon as its own driver has left the pits.

14.6 Save a per-driver, per-lap ledger of base pace, tyre state, cycle excess, extra assumed delay, arrival time, and gap. Reconstruct a simple historical cycle before adding uncertainty.

14.7 Check symmetric drivers with identical schedules, gap sign reversal, zero-delay behavior, and a one-second added focal delay. Confirm that adding one second increases the final focal-minus-rival gap by one second when other effects are fixed.

Output: a deterministic simulator with readable ledgers. Move forward when every second of a result can be traced to one clock component.

## 15 Add paired Monte Carlo simulation

15.1 Generate a draw object keyed by trial, driver, lap, and shared race context. Use the same trial object across all three alternatives so shared conditions cancel appropriately in paired comparisons.

15.2 Separate shared race variation from driver-specific variation and stop-specific uncertainty. Estimate dependence from training data where possible; otherwise document a simple dependence assumption and test its sensitivity.

15.3 Preserve plausible correlation across adjacent laps and between pit duration and cycle excess. Avoid treating every residual in the simulation as an unrelated normal draw.

15.4 Run 10,000 trials per strategy with a saved seed. Keep the full gap vector for distributions and uncertainty calculations; use a smaller sampled set of trajectories for animation.

15.5 Calculate probability ahead as `mean(final_gap_sec < 0)`, expected final gap as the mean signed gap, and the 5th and 95th gap quantiles. Report Monte Carlo standard error as `sqrt(p * (1 - p) / n)`.

15.6 At 10,000 trials, the maximum probability Monte Carlo standard error is 0.5 percentage points. Use repeated seeds or more trials when a close ranking could be driven by simulation noise; do not present small numerical differences as decisive.

15.7 Verify fixed-seed reproducibility and marginal distributions under alternative strategy ordering. Check that paired draws reduce noise in comparisons without forcing all lap or stop shocks to be identical.

Output: reproducible trial tables and strategy summaries. Move forward when each displayed summary can be independently recomputed from saved trials.

## 16 Evaluate outcomes on later races

16.1 Implement `R/08_evaluate.R`. Run each held-out historical case with the schedule that actually occurred and with only its predecision inputs. Compare that factual prediction with the observed common-boundary outcome.

16.2 Report lap mean absolute error, factual final-gap or gain error, Brier score for ahead probability, and central prediction-interval coverage. Use identical eligible rows when comparing models and baselines.

16.3 Plot calibration with counts and avoid bins with too few outcomes to interpret. Calculate uncertainty by resampling whole races, preserving all battles within each sampled race.

16.4 Distinguish a lightweight race bootstrap of fixed held-out predictions from a full refit bootstrap that also changes model estimates. Label which source of uncertainty each result includes.

16.5 Begin with 200 race-bootstrap resamples for development diagnostics, then assess stability before final reporting. This count is a proposed computational setting rather than a promise of sufficient precision.

16.6 Inspect performance by circuit, era, gap range, compound transition, and missing predictor status. Show event counts and suppress unsupported subgroup conclusions.

16.7 Validate only the factual observed schedule against an observed outcome. Check alternative schedules through timing invariants, plausibility, and sensitivity analysis; do not claim direct observed validation for all counterfactual choices.

Output: an evaluation report, calibration plot, interval coverage, and saved holdout predictions. Move forward when factual performance and limitations are acceptable for the intended demonstration, or simplify the model and repeat affected checks.

## 17 Calculate robustness and sensitivity outputs

17.1 Implement delay-tolerance calculations using the same scenario, draws, and gap convention as the strategy comparison. Add focal delay in seconds and locate the crossing of a declared probability threshold, initially 50 percent.

17.2 Return a numeric crossing only within the searched range. Use explicit statuses for already below threshold, no crossing found, and unsupported scenario. Preserve zero as a real result when applicable.

17.3 Run equal pit-lane-duration or equal execution-condition sensitivity as a secondary comparison with a declared implementation. Explain what remains different between strategies, including tyre state and route assumptions.

17.4 Build a gap-by-tyre-age grid within supported ranges. Reuse paired draws across nearby settings to reduce artificial variation. Store both the preferred strategy and its probability advantage over the runner-up.

17.5 Mark near ties using a stated practical difference together with Monte Carlo and model uncertainty. Show unsupported cells explicitly rather than filling the entire grid with confident rankings.

17.6 Test rival pit-lap shifts and traffic assumptions as labelled extensions. Keep the first-version result conditional on the fixed rival lap and declared traffic treatment.

Output: delay curves, equal-duration comparisons, and a supported decision heatmap. Move forward when changes in assumptions can be traced to corresponding changes in the engine inputs.

## 18 Choose demonstration scenarios and build saved artifacts

18.1 Implement `R/09_scenarios.R`. Select two or three timing-reviewed cases with enough pace, pit-cycle, weather, and compound support. Begin the search with well-represented circuits, then check the exact transition and event support.

18.2 Prefer cases that illustrate different mechanisms or uncertainty levels. Do not choose solely because the preferred strategy is dramatic or because the simulated choice happens to match history.

18.3 Save scenario metadata, initial histories, feasible input ranges, assumptions, historical outcome, and model support counts. Ensure changing a slider changes a scenario assumption without rewriting the historical record.

18.4 Produce a compact model bundle containing preprocessing, selected models, residual pools, configuration, and source hashes. Produce a separate scenario bundle containing summaries, heatmaps, and sampled replay paths.

18.5 Write `scripts/build_project.R` to rebuild these artifacts in dependency order. Rebuild affected components when data, code, or configuration hashes change; do not reuse a cache only because its filename exists.

18.6 Test the build from a clean processed-output directory or an isolated temporary output location. Confirm that sources remain unchanged and logs identify each generated artifact.

Output: versioned model and scenario bundles and one offline build entry point. Move forward when the app can load ready-to-use objects without fitting models during launch.

## 19 Build the Shiny pit wall

19.1 Create `app.R` and focused interface modules. Start with scenario selection, stable driver identities, current assumptions, and three strategy result columns. Connect all values to the shared result contract.

19.2 Add initial gap, tyre age, planned replacement compound, and extra delay controls with supported ranges. Display specific messages for missing or unsupported combinations.

19.3 Run expensive simulation after a clear action such as Compare strategies. Use event-controlled reactivity and a cache keyed by every relevant input, seed, trial count, configuration version, and model version.

19.4 Show probability ahead, expected signed gap, and the central 90 percent gap interval with plain unit and sign labels. Provide definitions where they help interpretation, and separate historical evidence from simulated results.

19.5 Add outcome distributions and the gap-by-tyre-age heatmap. Keep support counts and assumption settings accessible. Avoid treating an unavailable crew metric as a zero-valued result.

19.6 Add a schematic replay from the saved per-lap trajectories. Use common start and end points across strategies. State that the movement is schematic because the export does not contain track-position telemetry sufficient for a physical replay.

19.7 Add a classroom choice stage with Box now, Cover, and Stay out before revealing the results. Keep the choice and reveal logic separate from the computation so it cannot alter the simulation outcome.

Output: a usable Shiny demo connected to the validated engine. Move forward when every displayed value matches the corresponding offline result for the same inputs.

## 20 Test the integrated workflow and performance

20.1 Add focused tests for the contracts most likely to change a conclusion: key cardinality, gap algebra, shared endpoints, predecision cutoffs, timing quarantine, missing-data handling, one-second delay monotonicity, and fixed-seed reproducibility.

20.2 Test the app's supported scenarios and boundary inputs. Verify that selecting a scenario resets dependent controls correctly and that changing one input invalidates the appropriate cache.

20.3 Check that a failed prerequisite remains visible. An unknown compound, stale weather, missing model bundle, or unavailable timing endpoint must not become an empty chart or a healthy zero.

20.4 Measure cold app launch, cached scenario load, one 10,000-trial comparison, and replay responsiveness on the presentation machine. Record measured times rather than promising a startup speed before testing.

20.5 Move repeatable preparation and heatmap work into the offline build. Use vectorized R calculations and sampled animation paths before adding parallel processing or extra runtime dependencies.

20.6 Run a fresh R session from the documented launch command. Test the intended projector or screen dimensions and rehearse the choice-reveal interaction without relying on an internet connection for routine calculations.

Output: a concise test and performance report. Move forward when the demo is usable, errors are explicit, and all core numerical checks pass.

## 21 Prepare the final analysis and presentation

21.1 Write the research question, sample definition, snapshot cutoff, and conditional strategy assumptions in the final report. Explain the distinction between 7,054 stop rows and 6,767 matched stops.

21.2 Include the historical evidence, held-out pace comparison, factual outcome calibration, execution-risk distributions, and two or three scenario results. Keep sample sizes beside comparisons.

21.3 Explain the pit-cycle ledger and why full lane duration is not added on top of complete racing laps. Define warm-up proxies and acknowledge missing stationary service measurements.

21.4 Show a case in which uncertainty or a small margin limits the recommendation. Explain that only the realized strategy has an observed outcome and that the alternatives depend on the model and scenario assumptions.

21.5 Rehearse the classroom sequence: show the situation, collect the choice, reveal the distribution, and explain how tyre state or extra delay changes the result. Keep projected text concise and put technical detail in the written report or notes.

21.6 Record unresolved limitations, supported operating ranges, and deferred extensions. Do not present an unresolved timing or event identity question as verified.

Output: a reproducible written analysis and rehearsed interactive presentation. Move forward when a reader can distinguish source facts, fitted relationships, and chosen assumptions.

## 22 Package the project and keep the reference current

22.1 Confirm that the source snapshot, field dictionary, and reference agree with the final implemented schema. Update formulas, actual lookbacks, support thresholds, endpoints, and code ownership where the implementation differs from this plan.

22.2 Include the R source, environment lockfile, build and launch instructions, final model metadata, evaluation results, and data-acquisition or placement instructions. Keep large-data distribution consistent with the repository decision from Step 2.

22.3 Check source hashes against `F1_File_Inventory.csv`. Document intentional derived corrections without overwriting the original evidence.

22.4 Run the final numerical checks and a documented fresh-session build or artifact-load launch. Record exactly which rebuilds were performed and which relied on previously generated, version-matched artifacts.

22.5 Review the final diff and commit the completed work in coherent units. If publishing is requested during implementation, verify the intended remote and content first; this planning phase does not publish a repository or application.

22.6 For later changes, start with the reference, identify the owning module, update the decision log when semantics change, and rerun the affected validation. Export refreshed Word planning documents when sharing a revised version with the team.

Output: a reviewable project package and current maintenance documentation. The first release is complete when the offline analysis, held-out evidence, shared engine, and Shiny demonstration all satisfy their stated contracts.

## Supporting documentation

The project-specific evidence is in the original proposal, the complete file inventory, the field dictionary, the session index, and the reference's audit links. External software guidance used for this procedure is limited to official sources:

- FastF1 timing fields and synchronization flags: https://github.com/theOehrly/Fast-F1/blob/main/docs/api_reference/timing_data.rst
- FastF1 session clocks and pit timestamps: https://github.com/theOehrly/Fast-F1/blob/main/docs/data_reference/time_explanation.rst
- Posit Shiny caching and event-controlled calculation: https://shiny.posit.co/r/articles/improve/caching/
- GitHub large-file limits: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
