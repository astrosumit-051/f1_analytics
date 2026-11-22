# Run from the repository root; all statistical checks use labelled fake inputs.
source("demo/data.R")
root<-normalizePath(".",winslash="/")
Sys.setenv(F1_MODE="fake",F1_PROJECT_ROOT=root)
Sys.unsetenv(c("F1_PAIRS","F1_WINDOW_GRID","F1_NO_RESPONSE"))
d<-load_handoffs(root,"fake")
stopifnot(all(d$pairs$year %in% as.character(2018:2023)),all(d$pairs$split=="train"))
grid_file<-tempfile();writeLines("explicit synthetic provenance unit fixture",grid_file)
metadata<-tempfile()
info<-list(split="train",models="mock",window_grid_md5=unname(tools::md5sum(grid_file)),evidence="training provenance unit check")
jsonlite::write_json(info,metadata,auto_unbox=TRUE)
stopifnot(grid_metadata_valid(metadata,grid_file,"mock"))
info$split<-"test";jsonlite::write_json(info,metadata,auto_unbox=TRUE)
stopifnot(!grid_metadata_valid(metadata,grid_file,"mock"))
info$split<-"train";jsonlite::write_json(info,metadata,auto_unbox=TRUE)
writeLines("changed",grid_file)
stopifnot(!grid_metadata_valid(metadata,grid_file,"mock"))

# Known interpolation, signs, missingness and crossing arithmetic.
w<-data.frame(gap_sec=c(1,2),p_success=c(.75,.25),p_lo=c(.6,.1),p_hi=c(.9,.4))
v<-lookup_probability(w,1.5)
stopifnot(v$probability==.5,v$lo==.35,v$hi==.65,
  is.na(lookup_probability(w,.5)$probability),crossing_gap(w,.5)$gap_sec==1.5)
bad<-d$window;bad$p_success[1]<-1.1
stopifnot(inherits(try(validate_window(bad),silent=TRUE),"try-error"))
bad<-d$pairs;bad$gap_before_sec[1]<--1
stopifnot(inherits(try(validate_pairs(bad),silent=TRUE),"try-error"))
bad<-d$pairs;bad$delay[1]<-7
stopifnot(inherits(try(validate_pairs(bad),silent=TRUE),"try-error"))
sentinel<-tempfile(fileext=".csv")
writeLines(c("split,year,success_h3","train,2018,1","test,2025,DO_NOT_PARSE"),sentinel)
stopifnot(identical(read_training(sentinel)$success_h3,"1"))
writeLines(c("split,year,success_h3","train,2025,DO_NOT_PARSE"),sentinel)
stopifnot(inherits(try(read_training(sentinel),silent=TRUE),"try-error"))

for(outcome in c("success_h3","success_common_h3")) for(delay in c("d1","d23")) {
  s<-scenario_snapshot(d,"FAKE_primary_v0",outcome,delay,2)
  stopifnot(identical(s,scenario_snapshot(d,"FAKE_primary_v0",outcome,delay,2)))
  stopifnot(all(s$rates$completed+s$rates$missing==s$rates$pairs))
  if(nrow(s$window)) stopifnot(all(s$window$p_success>=0&s$window$p_success<=1))
}

app<-new.env(parent=globalenv());sys.source("demo/app.R",envir=app,chdir=TRUE)
shiny::testServer(app$make_server(d), {
  session$setInputs(outcome="success_h3",delay="d1",model="FAKE_primary_v0",gap=2,compare_delays=TRUE)
  s<-snapshot();expected<-scenario_snapshot(d,"FAKE_primary_v0","success_h3","d1",2)
  stopifnot(identical(s,expected),output$probability==app$pct(expected$value$probability))
  stopifnot(nchar(output$gap_rates)>0,nchar(output$comparison)>0,nchar(output$examples)>0,
    nchar(output$defender)>0,nchar(output$no_response)>0)
  output$window
  session$setInputs(gap=3)
  stopifnot(snapshot()$value$probability!=s$value$probability)
  session$setInputs(model="FAKE_baseline_gap_v0",delay="d23",compare_delays=FALSE)
  stopifnot(identical(snapshot(),scenario_snapshot(d,"FAKE_baseline_gap_v0","success_h3","d23",3)))
  session$setInputs(outcome="success_common_h3")
  stopifnot(is.na(snapshot()$value$probability),output$probability=="Unavailable")
})

# Numerical export is also compared with the Python producer in integration checks.
dir.create("evaluation/results",showWarnings=FALSE,recursive=TRUE)
write.csv(observed_summary(d$pairs,"success_common_h3"),"evaluation/results/r_observed.csv",row.names=FALSE)
writeLines(c("PASS: interpolation and no extrapolation","PASS: probabilities and invalid input rejection",
  "PASS: protected sentinels and year mismatch","PASS: deterministic scenario functions",
  "PASS: Shiny controls and numeric output agreement","PASS: honest missing common-lap model"),"evaluation/results/shiny_test_status.txt")
cat("ALL SHINY CHECKS PASSED\n")
