source("config.R")
source("R/data_and_models.R")
source("R/strategy.R")

synthetic_fixture <- function() {
  cfg<-f1_config()
  st<-list(driver="fixture_focal",team="Fixture team",circuit="fixture",year=2024,
    scheduled_laps=60,compound="MEDIUM",tyre_age=12,prior_use=FALSE,position=5,
    boundary=19,arrival_sec=1800,recent_pace_sec=90,recent_slope_sec=.1,
    recent_model_sec=90,history_last_sec=1800,track_temp=30,air_temp=23,
    rainfall=FALSE,flag="1",feasible_compounds=c("HARD","MEDIUM"),new_compound="HARD",
    new_set_prior_age=0,age_min=1,age_max=50)
  rival<-st; rival$driver<-"fixture_rival"; rival$team<-"Other team"
  tm<-st; tm$driver<-"fixture_teammate"; tm$arrival_sec<-1801
  s<-list(id="SYNTHETIC arithmetic fixture",event_id="synthetic",current_lap=20,
    boundary=19,cutoff_sec=1801,states=list(focal=st,rival=rival,teammate=tm),
    gap_sec=0,rival_stop=21,teammate_stop=21,field=data.table(),traffic_loss_sec=0,
    traffic_gap_sec=1.5,box_service_sec=3,extra_focal_delay_sec=0,
    status="SYNTHETIC: no historical interpretation")
  cp<-data.table(event_id=rep(paste0("train",1:5),each=4),circuit="fixture",
                 old="MEDIUM",new="HARD",cycle_excess_sec=rep(c(19,20,21,24),5))
  block<-data.table(circuit="fixture",event_id="training_fixture",DriverId="training_driver",
    Stint=1,LapNumber=1:40,residual=rep(c(-.2,.1,.4,-.3),10))
  list(s=s,model=list(cfg=cfg,selected="baseline",cycles=cp,lap_blocks=block))
}
run_checks <- function() {
  f<-synthetic_fixture(); s<-f$s; m<-f$model
  a<-simulate_plan(s,m,21)
  stopifnot(abs(a$gap_sec)<1e-8)
  delayed<-s; delayed$extra_focal_delay_sec<-1
  stopifnot(abs(simulate_plan(delayed,m,21)$gap_sec-a$gap_sec-1)<1e-8)
  shifted<-s; shifted$gap_sec<-2
  stopifnot(abs(simulate_plan(shifted,m,20)$gap_sec-2)<1e-8)
  ledger<-simulate_plan(s,m,20)$ledger
  stopifnot(ledger[role=="focal" & lap==20,tyre_age]==13,
    ledger[role=="focal" & lap==21,tyre_age]==1,
    ledger[role=="focal",sum(pit_cycle_excess_sec)]==20.5)
  used<-s; used$states$focal$new_set_prior_age<-4
  stopifnot(simulate_plan(used,m,20)$ledger[role=="focal" & lap==21,tyre_age]==5)
  x<-compare_strategies(s,m); y<-compare_strategies(s,m)
  stopifnot(identical(x$trials,y$trials),uniqueN(x$table$end_lap)==1,nrow(x$trials)==30000)
  z<-compare_strategies(s,m,offsets=c(2,0,1))
  stopifnot(identical(x$trials[order(strategy,trial)],z$trials[order(strategy,trial)]))
  teams<-compare_team_timings(s,m)
  stopifnot(nrow(teams)==9,teams[focal_stop==21 & teammate_stop==21,deterministic_box_wait_sec]==2,
            all(is.na(teams$expected_team_points)))
  same_team_rival<-s; same_team_rival$states$teammate<-NULL
  same_team_rival$states$rival$team<-same_team_rival$states$focal$team
  stopifnot(simulate_plan(same_team_rival,m,21)$ledger[role=="focal",sum(box_wait_sec)]==3)
  wet<-s; wet$states$focal$rainfall<-NA
  stopifnot(inherits(try(validate_scenario(wet,m),silent=TRUE),"try-error"))
  bad<-s; bad$states$focal$new_compound<-"INTERMEDIATE"
  stopifnot(inherits(try(validate_scenario(bad,m),silent=TRUE),"try-error"))
  # Appending arbitrary future records cannot change the history at a past cutoff.
  h<-data.table(Time_sec=1:5,Stint=1,clean=TRUE,LapTime_sec=90:94,TyreLife=1:5)
  future<-rbind(h,data.table(Time_sec=100,Stint=1,clean=TRUE,LapTime_sec=1,TyreLife=6))
  stopifnot(isTRUE(all.equal(history_at(h,5),history_at(future,5),check.attributes=FALSE)))
  # Stop matching distinguishes earlier/same/later and leaves unrelated pairs explicit.
  fake<-list(stops=data.table(event_id="e",driver_ref=c("a","b"),stop_lap=c(20,21),stop_status="matched"),
    laps=CJ(event_id="e",DriverId=c("a","b"),LapNumber=19:23))
  fake$laps[,Time_sec:=LapNumber*90+ifelse(DriverId=="a",1,0)]
  stopifnot(historical_pair(fake,"e","a","b",20)$timing_class=="earlier",
    historical_pair(fake,"e","b","a",21)$timing_class=="later")
  fake$stops[driver_ref=="b",stop_lap:=20]
  stopifnot(historical_pair(fake,"e","a","b",20)$timing_class=="same_lap")
  stopifnot(grepl("Unrelated",historical_pair(fake,"e","a","b",20,30)$status))
  data.table(check=c("gap sign and symmetry","one second delay","common endpoints",
    "tyre transitions and prior use","cycle excess counted once","fixed seed and strategy order",
    "10000 paired trials","teammate box wait including rival on same team","wet/unknown rejection",
    "compound feasibility","cutoff invariant","specified-rival stop classification"),status="PASS")
}
if(sys.nframe()==0) {
  result<-run_checks(); print(result)
  dir.create("outputs",showWarnings=FALSE)
  fwrite(result,"outputs/calculation_checks.csv")
  cat("ALL CALCULATION CHECKS PASSED\n")
}
