# Independent arithmetic checks; run from a separate PR #26 CODE checkout.
# Never run its historical build or read its saved factual/test bundles here.
source("tests/check_calculations.R")
setDTthreads(1L)
fixture<-synthetic_fixture();s<-fixture$s;m<-fixture$model
checks<-run_checks()
set.seed(901);before<-.Random.seed
d<-paired_draws(s,m,25,n=10000L,seed=355L)
stopifnot(identical(before,.Random.seed))
result<-compare_strategies(s,m,n=10000L,seed=355L)
for(i in seq_len(nrow(result$table))) {
  row<-result$table[i];trials<-result$trials[strategy==row$strategy]
  ledger<-result$ledger[strategy==row$strategy]
  stopifnot(abs(mean(trials$final_gap_sec)-row$expected_gap_sec)<1e-10,
    mean(trials$final_gap_sec<0)==row$probability_ahead,
    abs(quantile(trials$final_gap_sec,.05,names=FALSE)-row$gap_p05_sec)<1e-10,
    abs(quantile(trials$final_gap_sec,.95,names=FALSE)-row$gap_p95_sec)<1e-10,
    abs((sum(ledger[role=="focal",lap_total_sec])+s$gap_sec)-
      sum(ledger[role=="rival",lap_total_sec])-row$deterministic_gap_sec)<1e-10)
}
delayed<-s;delayed$extra_focal_delay_sec<-1
x<-simulate_plan(s,m,20,end=25,draws=d)
y<-simulate_plan(delayed,m,20,end=25,draws=d)
stopifnot(all(abs(y$gap_sec-x$gap_sec-1)<1e-10))
stopifnot(all(result$table$probability_ahead %between% c(0,1)),all(is.na(result$table$expected_team_points)))
short<-s;short$states$focal$scheduled_laps<-20
stopifnot(inherits(try(compare_strategies(short,m),silent=TRUE),"try-error"))
checks<-rbind(checks,data.table(check=c("Independent trial means and probability counts",
  "Independent quantiles and clock-ledger sums","Caller RNG restored",
  "Paired one-second delay in every trial","Missing points remain missing and distance rejected"),status="PASS"))
dir.create("outputs",showWarnings=FALSE)
fwrite(checks,"outputs/independent_review_checks.csv")
cat("ALL 17 COMPANION SYNTHETIC CHECK GROUPS PASSED\n")

if("--shiny" %in% commandArgs(TRUE)) {
  # A NEW ignored review checkout only: never replace a historical model bundle.
  if(file.exists("models/prototype.rds")) stop("Refusing to overwrite any existing companion bundle")
  dir.create("models",showWarnings=FALSE)
  scenarios<-list(s);names(scenarios)<-s$id
  saveRDS(list(model=m,scenarios=scenarios,metadata=list(evidence="SYNTHETIC REVIEW ONLY",
    code_md5=tools::md5sum(c("config.R","R/data_and_models.R","R/strategy.R")))),"models/prototype.rds")
  app<-new.env(parent=globalenv());sys.source("app.R",envir=app)
  shiny::testServer(app$server, {
    session$setInputs(scenario=s$id,gap=s$gap_sec,age=s$states$focal$tyre_age,
      compound=s$states$focal$new_compound,prior_age=0,rival_stop=s$rival_stop,teammate_stop=s$teammate_stop)
    session$setInputs(compare=1)
    offline<-compare_strategies(s,m)
    stopifnot(identical(comparison()$table,offline$table),nchar(output$results)>0)
    session$setInputs(gap=s$gap_sec+1)
    stopifnot(identical(comparison()$table,offline$table))
    session$setInputs(compare=2)
    stopifnot(comparison()$scenario$gap_sec==s$gap_sec+1)
  })
  writeLines("PASS: companion synthetic Shiny/offline parity and Compare gating","outputs/synthetic_shiny_review.txt")
  cat("COMPANION SYNTHETIC SHINY CHECKS PASSED\n")
}
