# Pure clock calculations. No Shiny dependencies and no future observations.
state_at <- function(src, event, driver, boundary, cutoff, model) {
  z <- src$laps[event,on="event_id"][DriverId==driver]
  row <- z[LapNumber==boundary & Time_sec<=cutoff]
  if(nrow(row)!=1) stop("Missing boundary for ",driver)
  h <- history_at(z,cutoff,model$cfg)
  if(h$n<3 || !is.finite(h$pace)) stop("Fewer than three clean history laps for ",driver)
  # Fresh weather is joined again at the SHARED cutoff, not either driver's later lap.
  w <- src$streams[[event]]$weather; flag <- src$streams[[event]]$status
  wi <- if(nrow(w)) findInterval(cutoff,w$Time_sec) else 0
  fi <- if(nrow(flag)) findInterval(cutoff,flag$Time_sec) else 0
  if(!wi || !fi || cutoff-w$Time_sec[wi]>model$cfg$weather_max_age_sec ||
     is.na(as_bool(w$Rainfall[wi])) || as_bool(w$Rainfall[wi]) || flag$Status[fi]!="1")
    stop("Unsupported weather/flag at cutoff for ",event)
  support <- model$support[circuit==row$circuit & Compound==row$Compound]
  if(nrow(support)!=1 || support$races<3 || support$laps<100) stop("Unsupported pace state")
  cycles <- model$cycles[circuit==row$circuit & old==row$Compound]
  feasible <- cycles[,.(cycles=.N,races=uniqueN(event_id)),by=new][
    cycles>=model$cfg$min_transition_cycles & races>=model$cfg$min_transition_races,new]
  if(!length(feasible)) stop("No supported compound transition")
  list(driver=driver,team=row$Team,circuit=row$circuit,year=row$year,
       scheduled_laps=row$scheduled_laps,compound=row$Compound,tyre_age=row$TyreLife,
       prior_use=!row$FreshTyre,position=row$Position,boundary=boundary,
       arrival_sec=row$Time_sec,recent_pace_sec=h$pace,recent_slope_sec=h$slope,
       recent_model_sec=median(predict_normal(h$rows,model)),history_last_sec=h$last,
       track_temp=w$TrackTemp[wi],air_temp=w$AirTemp[wi],rainfall=FALSE,
       weather_sec=w$Time_sec[wi],cutoff_sec=cutoff,flag=flag$Status[fi],
       feasible_compounds=sort(feasible),new_compound=sort(feasible)[1],
       new_set_prior_age=0,inventory_assumption="One usable proposed set; actual inventory unavailable",
       age_min=support$age_min,age_max=support$age_max)
}
make_scenario <- function(src,event,focal,rival,current_lap,rival_stop,model,teammate=NULL) {
  boundary <- current_lap-1
  rows <- src$laps[event,on="event_id"][DriverId %in% c(focal,rival) & LapNumber==boundary]
  if(nrow(rows)!=2 || any(!is.finite(rows$Time_sec))) stop("Missing shared initial boundary")
  cutoff <- max(rows$Time_sec)
  states <- list(focal=state_at(src,event,focal,boundary,cutoff,model),
                 rival=state_at(src,event,rival,boundary,cutoff,model))
  if(is.null(teammate)) {
    teammates <- unique(src$laps[event,on="event_id"][Team==states$focal$team & DriverId!=focal,DriverId])
    if(length(teammates)==1 && teammates!=rival) teammate <- teammates
  }
  if(!is.null(teammate)) {
    tm <- tryCatch(state_at(src,event,teammate,boundary,cutoff,model),error=function(e) NULL)
    if(!is.null(tm)) states$teammate <- tm
  }
  # Surrounding cars with the SAME boundary already known by the shared cutoff.
  field <- src$laps[event,on="event_id"][LapNumber==boundary & Time_sec<=cutoff &
    !DriverId %in% vapply(states,`[[`,"", "driver")]
  field[, initial_sec := Time_sec-states$rival$arrival_sec]
  field[, pace_sec := vapply(DriverId,function(d) history_at(
    src$laps[event,on="event_id"][DriverId==d],cutoff,model$cfg)$pace,0.)]
  field <- field[is.finite(pace_sec),.(driver=DriverId,initial_sec,pace_sec)]
  s <- list(id=paste(event,focal,rival,current_lap,sep=":"),event_id=event,
    current_lap=current_lap,boundary=boundary,cutoff_sec=cutoff,states=states,
    gap_sec=states$focal$arrival_sec-states$rival$arrival_sec,rival_stop=rival_stop,
    teammate_stop=current_lap+1,field=field,traffic_loss_sec=model$cfg$traffic_loss_sec,
    traffic_gap_sec=model$cfg$traffic_gap_sec,box_service_sec=model$cfg$box_service_sec,
    extra_focal_delay_sec=0,conditions="Assume dry and green through endpoint",
    status="Provisional local-cycle estimate; unresolved source timing review")
  validate_scenario(s,model); s
}
validate_scenario <- function(s,model,focal_stops=s$current_lap+0:2) {
  end <- max(c(focal_stops,s$rival_stop,s$teammate_stop))+2
  if(!is.finite(s$gap_sec) || any(!is.finite(c(focal_stops,s$rival_stop,s$teammate_stop))) ||
     any(c(focal_stops,s$rival_stop,s$teammate_stop)<s$current_lap) ||
     any(c(focal_stops,s$rival_stop,s$teammate_stop)%%1!=0)) stop("Invalid gap or stop timing")
  for(st in s$states) {
    if(is.na(st$rainfall) || st$rainfall || is.na(st$flag) || st$flag!="1") stop("Unsupported wet or unknown conditions")
    if(!is.finite(st$tyre_age) || st$tyre_age<0 || end>st$scheduled_laps ||
       !st$new_compound %in% st$feasible_compounds || st$new_set_prior_age<0 ||
       st$tyre_age+max(focal_stops,s$rival_stop,s$teammate_stop)-s$boundary>st$age_max)
      stop("Unsupported tyre age, compound, distance, or set")
    cp <- model$cycles[circuit==st$circuit]
    if(nrow(cp)<model$cfg$min_pit_cycles || uniqueN(cp$event_id)<model$cfg$min_pit_races)
      stop("Insufficient independent pit-cycle support")
  }
  invisible(end)
}
paired_draws <- function(s,model,end,n=10000L,seed=355L) {
  # Local RNG scope: callers get reproducibility without changing their RNG state.
  existed <- exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)
  if(existed) old <- get(".Random.seed",envir=.GlobalEnv)
  on.exit(if(existed) assign(".Random.seed",old,envir=.GlobalEnv) else
    if(exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)) rm(".Random.seed",envir=.GlobalEnv))
  set.seed(seed)
  h <- end-s$boundary
  blocks <- model$lap_blocks[circuit==s$states$focal$circuit]
  # Sample complete adjacent driver/stint blocks, retaining serial dependence.
  starts <- which(seq_len(nrow(blocks))+h-1<=nrow(blocks))
  ends <- starts+h-1
  starts <- starts[blocks$event_id[starts]==blocks$event_id[ends] &
    blocks$DriverId[starts]==blocks$DriverId[ends] & blocks$Stint[starts]==blocks$Stint[ends] &
    blocks$LapNumber[ends]-blocks$LapNumber[starts]==h-1]
  if(!length(starts)) stop("No complete training residual blocks")
  out <- lapply(names(s$states),function(role) {
    ix <- sample(starts,n,replace=TRUE)
    lap <- sapply(0:(h-1),function(j) blocks$residual[ix+j])
    st <- s$states[[role]]; cp <- model$cycles[circuit==st$circuit]
    # One joint excess draw already includes route, execution and outlap warm up.
    list(lap=lap,cycle=sample(cp$cycle_excess_sec,n,replace=TRUE))
  }); names(out)<-names(s$states)
  list(drivers=out,n=n,seed=seed,end=end)
}
simulate_plan <- function(s,model,focal_stop,teammate_stop=s$teammate_stop,
                          end=max(s$current_lap+2,s$rival_stop,teammate_stop)+2,
                          draws=NULL,method=model$selected) {
  validate_scenario(s,model,focal_stop)
  roles <- names(s$states); n <- if(is.null(draws)) 1L else draws$n
  stops <- c(focal=focal_stop,rival=s$rival_stop,teammate=teammate_stop)[roles]
  if(end<max(stops)+1 || end<=s$boundary) stop("Endpoint precedes complete pit cycle")
  initial <- vapply(s$states,function(st) st$arrival_sec-s$states$rival$arrival_sec,0.)
  initial["focal"] <- s$gap_sec
  clock <- matrix(rep(initial,each=n),nrow=n,dimnames=list(NULL,roles))
  queue <- matrix(0,nrow=n,ncol=length(roles),dimnames=list(NULL,roles)); ledger <- list()
  for(lap in seq.int(s$current_lap,end)) {
    j <- lap-s$boundary
    for(role in roles) {
      st <- s$states[[role]]; after <- lap>stops[role]
      comp <- if(after) st$new_compound else st$compound
      age <- if(after) st$new_set_prior_age+lap-stops[role] else st$tyre_age+lap-s$boundary
      pace <- normal_for_state(st,lap,comp,age,model,method)
      pooled_pace <- if(!is.null(model$fit)) normal_for_state(st,lap,comp,age,model,"pooled") else pace
      cp <- model$cycles[circuit==st$circuit]
      excess <- if(lap==stops[role]+1) {
        if(is.null(draws)) median(cp$cycle_excess_sec) else draws$drivers[[role]]$cycle
      } else rep(0,n)
      noise <- if(is.null(draws)) rep(0,n) else draws$drivers[[role]]$lap[,j]
      wait <- if(lap==stops[role]+1) queue[,role] else rep(0,n)
      extra <- if(role=="focal" && lap==focal_stop+1) s$extra_focal_delay_sec else 0
      predicted <- clock[,role]+pace+excess+noise+wait+extra
      traffic <- rep(0,n)
      if(lap==stops[role]+1 && nrow(s$field) && s$traffic_loss_sec>0) {
        # Constant-pace, no-stop surrounding-field assumption; only rejoin lap.
        for(k in seq_len(nrow(s$field))) {
          other <- s$field$initial_sec[k]+j*s$field$pace_sec[k]
          gap <- predicted-other
          blocked <- gap>0 & gap<s$traffic_gap_sec & pace<s$field$pace_sec[k]
          traffic[blocked] <- s$traffic_loss_sec
        }
      }
      clock[,role] <- predicted+traffic
      if(is.null(draws)) ledger[[length(ledger)+1]] <- data.table(role=role,driver=st$driver,
        lap=lap,compound=comp,tyre_age=age,normal_lap_sec=pace,pooled_sensitivity_normal_sec=pooled_pace,
        pit_cycle_excess_sec=excess,box_wait_sec=wait,traffic_sec=traffic,
        extra_delay_sec=extra,lap_total_sec=pace+excess+wait+traffic+extra,
        arrival_sec=clock[,role],pit_stop_lap=stops[role])
    }
    team_roles<-roles[vapply(s$states,function(st) st$team==s$states$focal$team,TRUE)]
    together<-team_roles[stops[team_roles]==lap]
    if(length(together)==2) {
      # Schematic pit-box arrivals from crossing clocks, common route offset=0.
      first<-together[1]; second<-together[2]
      diff <- clock[,first]-clock[,second]
      queue[,first] <- ifelse(diff>=0,pmax(0,s$box_service_sec-diff),0)
      queue[,second] <- ifelse(diff<0,pmax(0,s$box_service_sec+diff),0)
    }
  }
  tab <- if(is.null(draws)) rbindlist(ledger) else NULL
  if(!is.null(tab)) tab[,gap_sec:=arrival_sec-arrival_sec[role=="rival"],by=lap]
  list(gap_sec=clock[,"focal"]-clock[,"rival"],clock=clock,ledger=tab,end=end)
}
compare_strategies <- function(s,model,n=model$cfg$trials,seed=model$cfg$seed,
                                offsets=0:2) {
  focal_stops <- s$current_lap+offsets
  end <- validate_scenario(s,model,focal_stops)
  draws <- paired_draws(s,model,end,n,seed)
  sims <- lapply(focal_stops,function(k) simulate_plan(s,model,k,end=end,draws=draws))
  det <- lapply(focal_stops,function(k) simulate_plan(s,model,k,end=end))
  sensitivity <- if(!is.null(model$fit)) lapply(focal_stops,function(k)
    simulate_plan(s,model,k,end=end,method="pooled")) else det
  reference <- which(offsets==2)
  if(length(reference)!=1) stop("Waiting two laps must be present as reference")
  table <- rbindlist(lapply(seq_along(sims),function(i) {
    gap <- sims[[i]]$gap_sec; gain <- sims[[reference]]$gap_sec-gap
    p <- mean(gap<0); q <- quantile(gap,c(.05,.95),names=FALSE)
    data.table(strategy=c("Pit now","Wait 1 lap","Wait 2 laps")[offsets[i]+1],
      focal_stop=focal_stops[i],rival_stop=s$rival_stop,end_lap=end,
      expected_time_gained_vs_wait2_sec=mean(gain),
      expected_cycle_gain_sec=s$gap_sec-mean(gap),expected_gap_sec=mean(gap),
      probability_ahead=p,gap_p05_sec=q[1],gap_p95_sec=q[2],mc_se=sqrt(p*(1-p)/n),
      deterministic_gap_sec=det[[i]]$gap_sec,
      pooled_sensitivity_gap_sec=sensitivity[[i]]$gap_sec,
      pace_method=model$selected,expected_team_points=NA_real_)
  }))
  now <- which(offsets==0); wait1 <- which(offsets==1)
  if(length(now)&&length(wait1)) table[,time_gained_vs_wait1_sec:=
    vapply(sims,function(x) mean(sims[[wait1]]$gap_sec-x$gap_sec),0.)]
  ordered <- order(table$expected_gap_sec); margin <- diff(table$expected_gap_sec[ordered[1:2]])
  recommendation <- if(margin<model$cfg$close_margin_sec)
    "Close comparison: the best two estimates differ by less than 0.5 seconds." else
    paste(table$strategy[ordered[1]],"has the lowest expected local-cycle gap.")
  if(model$selected=="baseline" && !is.null(model$fit)) recommendation<-paste(
    "Unsupported tyre-based timing ranking: recent clean pace beat the pooled model in validation.",
    "The primary baseline is flat across tyre states; pooled tyre response is a sensitivity only.",
    recommendation)
  recommendation <- paste(recommendation,
    "Conditional on proposed sets, rival timing, dry/green conditions and traffic assumptions; not a race-long optimum.")
  trials <- rbindlist(lapply(seq_along(sims),function(i) data.table(
    trial=seq_len(n),strategy=table$strategy[i],final_gap_sec=sims[[i]]$gap_sec)))
  ledger <- rbindlist(lapply(seq_along(det),function(i) copy(det[[i]]$ledger)[,strategy:=table$strategy[i]]))
  list(table=table,ledger=ledger,trials=trials,recommendation=recommendation,
       seed=seed,n=n,scenario=s,team_points_reason="Unavailable: no credible field-to-finish projection, later-stop model or applicable points-rule engine")
}
compare_team_timings <- function(s,model,n=model$cfg$trials,seed=model$cfg$seed) {
  if(!"teammate" %in% names(s$states)) return(data.table(status="Teammate state unavailable at shared cutoff"))
  end <- validate_scenario(s,model)
  draws <- paired_draws(s,model,end,n,seed)
  grid <- CJ(focal_stop=s$current_lap+0:2,teammate_stop=s$current_lap+0:2)
  result<-rbindlist(lapply(seq_len(nrow(grid)),function(i) {
    x <- simulate_plan(s,model,grid$focal_stop[i],grid$teammate_stop[i],end,draws)
    d <- simulate_plan(s,model,grid$focal_stop[i],grid$teammate_stop[i],end)
    data.table(focal_stop=grid$focal_stop[i],teammate_stop=grid$teammate_stop[i],end_lap=end,
      expected_sum_arrival_sec=mean(x$clock[,"focal"]+x$clock[,"teammate"]),
      deterministic_box_wait_sec=sum(d$ledger$box_wait_sec),expected_team_points=NA_real_,
      objective="Local summed arrival time; team points unavailable")
  }))
  reference<-result[focal_stop==s$current_lap+2 & teammate_stop==s$current_lap+2,expected_sum_arrival_sec]
  result[,time_gained_vs_both_wait2_sec:=reference-expected_sum_arrival_sec]
  result
}
historical_pair <- function(src,event,focal,rival,focal_stop,rival_stop=NULL,max_offset=2L) {
  a <- src$stops[event_id==event & driver_ref==focal & stop_lap==focal_stop & stop_status=="matched"]
  b <- src$stops[event_id==event & driver_ref==rival & stop_status=="matched"]
  if(is.null(rival_stop)) b<-b[abs(stop_lap-focal_stop)<=max_offset] else b<-b[stop_lap==rival_stop]
  if(nrow(a)!=1 || nrow(b)!=1) return(data.table(event_id=event,focal=focal,rival=rival,
    status="Unrelated or ambiguous stops; no unique specified-rival pairing"))
  before <- min(a$stop_lap,b$stop_lap)-1; after<-max(a$stop_lap,b$stop_lap)+2
  z <- src$laps[event,on="event_id"][DriverId %in% c(focal,rival)]
  gap <- function(l) { x<-z[LapNumber==l]; if(nrow(x)!=2) return(NA_real_)
    x$Time_sec[x$DriverId==focal]-x$Time_sec[x$DriverId==rival] }
  g0<-gap(before); g1<-gap(after)
  data.table(event_id=event,focal=focal,rival=rival,focal_stop=focal_stop,rival_stop=b$stop_lap,
    before_lap=before,after_lap=after,gap_before_sec=g0,gap_after_sec=g1,
    time_gained_sec=g0-g1,emerged_ahead=g1<0,
    timing_class=ifelse(a$stop_lap<b$stop_lap,"earlier",ifelse(a$stop_lap==b$stop_lap,"same_lap","later")),
    status=ifelse(is.finite(g0)&&is.finite(g1),"Observed timing pair; strategic intent unknown","Missing timing boundary"))
}
historical_scenario <- function(src,row,model) {
  event<-row$event_id; focal<-row$driver_undercut; rival<-row$driver_overcut
  s<-make_scenario(src,event,focal,rival,row$pit_lap_under,row$pit_lap_over,model)
  # Evaluation ONLY: declared realized schedule/sets, kept out of state features.
  a<-src$stops[event_id==event & driver_ref==focal & stop_lap==row$pit_lap_under]
  b<-src$stops[event_id==event & driver_ref==rival & stop_lap==row$pit_lap_over]
  s$states$focal$new_compound<-a$new_compound; s$states$rival$new_compound<-b$new_compound
  for(role in c("focal","rival")) {
    st<-s$states[[role]]; k<-if(role=="focal") a$stop_lap else b$stop_lap
    out<-src$laps[event,on="event_id"][DriverId==st$driver & LapNumber==k+1]
    if(nrow(out)!=1 || !is.finite(out$TyreLife)) stop("Missing factual replacement age")
    s$states[[role]]$new_set_prior_age<-out$TyreLife-1
  }
  # Teammate future is not observed here: omit from factual two-driver evaluation.
  s$states$teammate<-NULL
  end<-validate_scenario(s,model)
  z<-src$laps[event,on="event_id"][DriverId %in% c(focal,rival) & LapNumber %between% c(s$current_lap,end)]
  if(nrow(z)!=2*(end-s$boundary) || any(!is.finite(z$clock_error_sec) |
    z$clock_error_sec>model$cfg$timing_tolerance_sec | is.na(z$Rainfall) | z$Rainfall |
    is.na(z$TrackStatus) | z$TrackStatus!="1" | is.na(z$WeatherSampleAge_sec) |
    z$WeatherSampleAge_sec>model$cfg$weather_max_age_sec)) stop("Contaminated factual window")
  flags<-src$streams[[event]]$status
  if(any(flags[Time_sec>s$cutoff_sec & Time_sec<=max(z$Time_sec),Status]!="1")) stop("Non-green status interval")
  extra<-src$stops[event_id==event & driver_ref %in% c(focal,rival) &
    stop_lap %between% c(s$current_lap,end)]
  if(nrow(extra)!=2) stop("Additional stop within factual window")
  # Shared cutoff must precede both actual pit entries.
  if(s$cutoff_sec>=min(a$pit_entry_sec,b$pit_entry_sec)) stop("Cutoff after pit entry")
  s
}
