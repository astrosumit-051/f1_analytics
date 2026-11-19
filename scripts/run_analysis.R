# Rebuild from raw inputs on every run; no stale processed cache is reused.
source("tests/check_calculations.R")
setDTthreads(1L)
cfg<-f1_config(); dir.create("outputs",showWarnings=FALSE)
started<-proc.time()[3]
checks<-run_checks(); fwrite(checks,"outputs/calculation_checks.csv")
fixture<-synthetic_fixture()
synthetic<-compare_strategies(fixture$s,fixture$model)
fwrite(synthetic$table[,evidence:="SYNTHETIC arithmetic only"],"outputs/synthetic_example.csv")
if("--synthetic" %in% commandArgs(TRUE)) {
  cat("Synthetic checks complete; no historical data used.\n")
} else {
  cat("Loading real sources and constructing decision rows...\n")
  src<-load_sources(cfg)
  if(is.null(src$laps)) {
    writeLines(c("Missing real-data inputs:",src$missing),"outputs/missing_inputs.txt")
    cat(paste(c("Historical work unavailable. Exact missing files:",src$missing),collapse="\n"),"\n")
  } else {
    paths<-src$source_paths[file.exists(src$source_paths)]
    before<-tools::md5sum(paths)
    if(length(src$missing)) writeLines(src$missing,"outputs/missing_inputs.txt")
    cat("Fitting training-only pace and pit-cycle models...\n")
    model<-fit_models(src,cfg)
    pace<-evaluate_pace(src,model)
    metrics<-pace[,.(laps=.N,races=uniqueN(event_id),
      pooled_mae_sec=mean(abs(pooled_sec-observed_sec)),
      baseline_mae_sec=mean(abs(baseline_sec-observed_sec))),by=split]
    v<-metrics[split=="validation"]
    model$selected<-if(nrow(v)&&v$pooled_mae_sec<v$baseline_mae_sec) "pooled" else "baseline"
    # Use forecast errors after recent-history anchoring, so the driver/race
    # offset already in recent pace is not sampled a second time.
    training_predictions<-evaluate_pace(src,model,training=TRUE)
    training_predictions[,residual:=observed_sec-if(model$selected=="pooled") pooled_sec else baseline_sec]
    model$lap_blocks<-training_predictions[is.finite(residual),
      .(circuit,event_id,DriverId,Stint,LapNumber,residual)]
    fwrite(metrics,"outputs/pace_metrics.csv")
    fwrite(pace,"outputs/pace_predictions.csv")
    fwrite(src$decisions,"outputs/decision_inputs.csv")
    # Explicit provisional review status: no assertion that unidentified cases cleared.
    writeLines(c("event_id,battle_id,reason,status",
      ",,Three timing cases named in original proposal have no supplied IDs,unresolved",
      "2026_16,,Unusual catalog event identity,excluded from historical examples/evaluation"),
      "outputs/timing_review.csv")
    candidates<-src$candidates[year>=cfg$test_start & event_id!="2026_16"]
    factual<-list(); skipped<-list(); scenarios<-list(); observed_pairs<-list()
    cat("Evaluating factual schedules on later held-out races...\n")
    for(i in seq_len(nrow(candidates))) {
      row<-candidates[i]
      tryCatch({
        s<-historical_scenario(src,row,model)
        out<-compare_strategies(s,model)
        end<-out$table$end_lap[1]
        observed<-src$laps[row$event_id,on="event_id"][LapNumber==end &
          DriverId %in% c(row$driver_undercut,row$driver_overcut)]
        gap<-observed[DriverId==row$driver_undercut,Time_sec]-observed[DriverId==row$driver_overcut,Time_sec]
        factual[[length(factual)+1]]<-data.table(battle_id=row$battle_id,event_id=row$event_id,
          year=row$year,before_lap=s$boundary,end_lap=end,
          observed_gap_sec=gap,expected_gap_sec=out$table$expected_gap_sec[1],
          baseline_gap_sec=simulate_plan(s,model,s$current_lap,end=end,method="baseline")$gap_sec,
          probability_ahead=out$table$probability_ahead[1],observed_ahead=gap<0,
          gap_p05_sec=out$table$gap_p05_sec[1],gap_p95_sec=out$table$gap_p95_sec[1],
          evidence="Factual schedule and realized sets; provisional source review")
        observed_pairs[[length(observed_pairs)+1]]<-historical_pair(src,row$event_id,
          row$driver_undercut,row$driver_overcut,row$pit_lap_under,row$pit_lap_over)
        have_teammate<-any(vapply(scenarios,function(x) "teammate" %in% names(x$states),TRUE))
        if(length(scenarios)<3 || !have_teammate) {
          # Rebuild a decision scenario with proposed defaults, not realized future sets.
          demo<-make_scenario(src,row$event_id,row$driver_undercut,row$driver_overcut,
            row$pit_lap_under,row$pit_lap_over,model)
          if(length(scenarios)<3) scenarios[[demo$id]]<-demo else
            if("teammate" %in% names(demo$states)) { scenarios[[3]]<-demo; names(scenarios)[3]<-demo$id }
        }
      },error=function(e) {skipped[[length(skipped)+1]]<<-data.table(
        battle_id=row$battle_id,event_id=row$event_id,reason=conditionMessage(e))})
    }
    facts<-rbindlist(factual); fwrite(facts,"outputs/factual_predictions.csv")
    fwrite(rbindlist(skipped),"outputs/factual_exclusions.csv")
    fwrite(rbindlist(observed_pairs),"outputs/observed_pairs.csv")
    if(nrow(facts)) {
      fm<-facts[,.(battles=.N,races=uniqueN(event_id),
        gap_mae_sec=mean(abs(expected_gap_sec-observed_gap_sec)),
        baseline_gap_mae_sec=mean(abs(baseline_gap_sec-observed_gap_sec)),
        brier=mean((probability_ahead-observed_ahead)^2),
        baseline_brier=mean((model$baseline_ahead_probability-observed_ahead)^2),
        coverage90=mean(observed_gap_sec>=gap_p05_sec & observed_gap_sec<=gap_p95_sec))]
      fwrite(fm,"outputs/factual_metrics.csv")
      facts[,bin:=cut(probability_ahead,c(-.001,.2,.4,.6,.8,1.001))]
      calibration<-facts[,.(n=.N,races=uniqueN(event_id),predicted=mean(probability_ahead),
        observed=mean(observed_ahead)),by=bin]
      calibration[,interpretation:=ifelse(n>=20 & races>=5,"Descriptive calibration bin","Too few cases to interpret")]
      fwrite(calibration,"outputs/calibration.csv")
    }
    # Include a real teammate scenario if one of the supported examples permits it.
    dir.create("models",showWarnings=FALSE)
    source_code<-c("config.R","R/data_and_models.R","R/strategy.R")
    saveRDS(list(model=model,scenarios=scenarios,metadata=list(
      source_md5=before,code_md5=tools::md5sum(source_code),config=cfg,
      R_version=R.version.string,seed=cfg$seed,trials=cfg$trials)),"models/prototype.rds")
    fwrite(rbindlist(lapply(scenarios,function(s) {
      f<-s$states$focal; r<-s$states$rival
      data.table(scenario_id=s$id,event_id=s$event_id,focal=f$driver,rival=r$driver,
        current_lap=s$current_lap,before_lap=s$boundary,cutoff_sec=s$cutoff_sec,
        initial_gap_sec=s$gap_sec,focal_compound=f$compound,focal_tyre_age=f$tyre_age,
        proposed_focal_compound=f$new_compound,proposed_focal_set_prior_age=f$new_set_prior_age,
        rival_compound=r$compound,rival_tyre_age=r$tyre_age,proposed_rival_compound=r$new_compound,
        assumed_rival_stop=s$rival_stop,track_temp=f$track_temp,air_temp=f$air_temp,
        weather_sec=f$weather_sec,flag=f$flag,rainfall=f$rainfall,
        teammate=if("teammate" %in% names(s$states)) s$states$teammate$driver else NA_character_,
        assumed_teammate_stop=s$teammate_stop,traffic_loss_sec=s$traffic_loss_sec,
        box_service_sec=s$box_service_sec,points_status="Unavailable",source_review="Provisional")
    })),"outputs/scenario_inputs.csv")
    for(i in seq_along(scenarios)) {
      s<-scenarios[[i]]; out<-compare_strategies(s,model)
      fwrite(out$table[,scenario_id:=s$id],sprintf("outputs/example_%d_results.csv",i))
      fwrite(out$ledger,sprintf("outputs/example_%d_ledger.csv",i))
      fwrite(out$trials,sprintf("outputs/example_%d_trials.csv",i))
      fwrite(compare_team_timings(s,model),sprintf("outputs/example_%d_team.csv",i))
      sensitivity<-rbindlist(lapply(pmax(s$current_lap,s$rival_stop+c(-1,0,1)),function(k) {
        ss<-s; ss$rival_stop<-k
        compare_strategies(ss,model)$table[,assumed_rival_stop:=k]
      }))
      fwrite(sensitivity,sprintf("outputs/example_%d_rival_sensitivity.csv",i))
    }
    stopifnot(identical(before,tools::md5sum(paths)))
    manifest<-data.table(path=names(before),md5=unname(before))
    fwrite(manifest,"outputs/source_hashes.csv")
    summary<-data.table(metric=c("lap_rows","stop_rows","decision_rows","eligible_decisions",
      "eligible_stay_out","training_cycles","training_cycle_races","historical_examples",
      "factual_holdout_cases","age_increments_equal_one","elapsed_sec"),
      value=c(nrow(src$laps),nrow(src$stops),nrow(src$decisions),sum(src$decisions$eligible),
      src$decisions[eligible & observed_action=="stayed_out",.N],nrow(model$cycles),uniqueN(model$cycles$event_id),
      length(scenarios),nrow(facts),mean(src$laps$age_increment[is.finite(src$laps$age_increment)]==1),
      proc.time()[3]-started))
    fwrite(summary,"outputs/run_summary.csv")
    # Record loaded metadata directly: installed.packages() does not enumerate
    # this Windows sandbox's user library reliably even when namespaces load.
    dependencies<-sort(loadedNamespaces())
    fwrite(data.table(package=dependencies,version=vapply(dependencies,
      function(p) as.character(getNamespaceVersion(p)),"")),"outputs/dependency_versions.csv")
    writeLines(c(capture.output(sessionInfo()),paste("Selected pace model:",model$selected),
      paste("Seed:",cfg$seed,"Trials:",cfg$trials),"RAW INPUT HASHES UNCHANGED",
      "RUN COMPLETED SUCCESSFULLY"),"outputs/run_status.txt")
    print(summary); print(metrics); if(exists("fm")) print(fm)
    cat("RUN COMPLETED SUCCESSFULLY\n")
  }
}
