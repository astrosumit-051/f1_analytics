# Run after scripts/run_analysis.R. Real artifacts are never treated as fixtures.
source("tests/check_calculations.R")
setDTthreads(1L)
checks<-run_checks()
bundle<-readRDS("models/prototype.rds"); model<-bundle$model
stopifnot(length(bundle$scenarios)>0,
  identical(bundle$metadata$code_md5,tools::md5sum(names(bundle$metadata$code_md5))),
  all(as.integer(substr(model$train_events,1,4))<=model$cfg$train_end))
for(scenario in bundle$scenarios) for(state in scenario$states)
  stopifnot(state$history_last_sec<=state$arrival_sec,state$weather_sec<=scenario$cutoff_sec)
d<-fread("outputs/decision_inputs.csv")
stopifnot(all(d$history_last_sec[is.finite(d$history_last_sec)]<=d$cutoff_sec[is.finite(d$history_last_sec)]),
  all(d$weather_sec[is.finite(d$weather_sec)]<=d$cutoff_sec[is.finite(d$weather_sec)]),
  d[eligible & observed_action=="stayed_out",.N]>0)
facts<-fread("outputs/factual_predictions.csv")
stopifnot(!any(facts$event_id %in% model$train_events),all(facts$year>=model$cfg$test_start))
missing_cfg<-model$cfg; missing_cfg$data_root<-file.path(tempdir(),"definitely_missing_f1_snapshot")
missing<-load_sources(missing_cfg)
stopifnot(length(missing$missing)==4,all(grepl("definitely_missing_f1_snapshot",missing$missing)))
s<-bundle$scenarios[[1]]
before<-Sys.time(); reference<-compare_strategies(s,model); elapsed<-as.numeric(Sys.time()-before)
again<-compare_strategies(s,model)
stopifnot(identical(reference$trials,again$trials))
saved<-fread("outputs/example_1_results.csv",colClasses=c(expected_team_points="numeric"))[,scenario_id:=NULL]
stopifnot(isTRUE(all.equal(saved,reference$table,tolerance=1e-8,check.attributes=FALSE)))
app_env<-new.env(parent=globalenv()); sys.source("app.R",envir=app_env)
shiny::testServer(app_env$server, {
  session$setInputs(scenario=s$id,gap=s$gap_sec,age=s$states$focal$tyre_age,
    compound=s$states$focal$new_compound,prior_age=0,rival_stop=s$rival_stop,
    teammate_stop=s$teammate_stop)
  session$setInputs(compare=1)
  stopifnot(identical(comparison()$table,reference$table))
  stopifnot(nchar(output$recommendation)>0,nchar(output$results)>0)
  # Changing assumptions changes the engine input only after Compare.
  session$setInputs(gap=s$gap_sec+1)
  stopifnot(identical(comparison()$table,reference$table))
  session$setInputs(compare=2)
  stopifnot(comparison()$scenario$gap_sec==s$gap_sec+1)
})
checks<-rbind(checks,data.table(check=c("real feature cutoff audit","whole-race holdout",
  "exact missing-file report","bundle source fingerprints","real fixed-seed reproduction",
  "saved result matches engine","Shiny server result and Compare gating"),status="PASS"))
fwrite(checks,"outputs/integration_checks.csv")
dependencies<-sort(loadedNamespaces())
fwrite(data.table(package=dependencies,version=vapply(dependencies,
  function(p) as.character(getNamespaceVersion(p)),"")),"outputs/dependency_versions.csv")
fwrite(data.table(operation="One 10000-trial three-strategy comparison",elapsed_sec=elapsed),
  "outputs/benchmark.csv")
cat("ALL INTEGRATION CHECKS PASSED\n")
