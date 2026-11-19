# Small data preparation and pooled models. All elapsed times are seconds.
library(data.table)
as_bool <- function(x) as.logical(toupper(as.character(x)))
local_slope <- function(x,y) {
  x<-x-mean(x); denom<-sum(x*x)
  if(denom>0) sum(x*(y-mean(y)))/denom else NA_real_
}
dry_compounds <- c("HARD", "MEDIUM", "SOFT", "SUPERSOFT", "ULTRASOFT", "HYPERSOFT")
key_check <- function(x, columns, label) {
  if (anyNA(x[, ..columns]) || anyDuplicated(x[, ..columns]))
    stop(label, ": missing or duplicate key: ", paste(columns, collapse=", "))
}
read_csv <- function(path) {
  if (!file.exists(path)) stop("Missing input: ", path)
  if (file.info(path)$size == 0) return(data.table())
  headers <- names(fread(path,nrows=0,showProgress=FALSE))
  fread(path, na.strings=c("", "NA", "NaN"), showProgress=FALSE,
        colClasses=list(character=intersect(headers,c("event_id", "DriverId", "driver_ref", "TrackStatus", "Status"))))
}
scheduled_distance <- function(circuit, year, cfg) {
  n <- unname(cfg$scheduled_laps[circuit])
  n[circuit == "yas_marina" & year >= 2021] <- 58
  n[circuit == "marina_bay" & year >= 2023] <- 62
  n
}
load_sources <- function(cfg=f1_config()) {
  required <- file.path(cfg$data_root, c("all_laps_enriched.csv", "all_pit_stops.csv",
                                        "completed_race_catalog.csv", "pit_battles_model_ready.csv"))
  missing <- required[!file.exists(required)]
  if (length(missing)) return(list(missing=missing))
  catalog <- read_csv(required[3]); key_check(catalog, "event_id", "catalog")
  laps <- read_csv(required[1]); stops <- read_csv(required[2])
  cat("Read",nrow(laps),"laps and",nrow(stops),"stops.\n")
  laps[, event_id := sprintf("%04d_%02d", year, round)]
  key_check(laps, c("event_id", "DriverId", "LapNumber"), "laps")
  key_check(stops, c("event_id", "driver_ref", "stop_lap"), "stops")
  if (any(!laps$event_id %in% catalog$event_id)) stop("Unmatched lap event")
  laps[, circuit := catalog$circuitRef[match(event_id, catalog$event_id)]]
  laps[, scheduled_laps := scheduled_distance(circuit, year, cfg)]
  laps[, progress := LapNumber / scheduled_laps]
  for (n in c("Rainfall", "FreshTyre", "IsAccurate", "FastF1Generated", "Deleted"))
    set(laps, j=n, value=as_bool(laps[[n]]))
  setorder(laps, event_id, DriverId, LapNumber)
  laps[, clock_error_sec := abs((Time_sec - shift(Time_sec)) - LapTime_sec), by=.(event_id, DriverId)]
  laps[, age_increment := TyreLife - shift(TyreLife), by=.(event_id, DriverId, Stint)]
  laps[, clean := !is.na(IsAccurate) & IsAccurate & !is.na(FastF1Generated) & !FastF1Generated &
    !is.na(Deleted) & !Deleted & TrackStatus == "1" & !is.na(Rainfall) & !Rainfall &
    Compound %in% dry_compounds & is.finite(TyreLife) & TyreLife >= 1 &
    is.na(PitInTime_sec) & is.na(PitOutTime_sec) & is.finite(LapTime_sec) &
    is.finite(clock_error_sec) & clock_error_sec <= cfg$timing_tolerance_sec &
    is.finite(WeatherSampleAge_sec) & WeatherSampleAge_sec >= 0 &
    WeatherSampleAge_sec <= cfg$weather_max_age_sec & WeatherTime_sec <= LapStartTime_sec &
    is.finite(progress) & progress <= 1]
  laps[is.na(clean), clean := FALSE]
  # Only allow the preceding completed laps of this same stint into a baseline.
  laps[, c("recent_pace_sec", "recent_slope_sec", "history_n", "history_last_sec",
            "known_pace", "known_slope", "known_n", "known_last") := {
    pace <- slope <- last <- rep(NA_real_, .N); count <- integer(.N)
    kp<-ks<-kl<-rep(NA_real_,.N); kn<-integer(.N)
    good <- integer()
    p<-sl<-la<-NA_real_; nn<-0L
    for (i in seq_len(.N)) {
      pace[i]<-p; slope[i]<-sl; last[i]<-la; count[i]<-nn
      if(clean[i]) {
        good<-c(good,i); h<-tail(good,cfg$lookback); nn<-length(h)
        if(nn>=3) { p<-median(LapTime_sec[h]); sl<-local_slope(TyreLife[h],LapTime_sec[h]); la<-max(Time_sec[h]) }
      }
      kp[i]<-p; ks[i]<-sl; kl[i]<-la; kn[i]<-nn
    }
    list(pace,slope,count,last,kp,ks,kn,kl)
  }, by=.(event_id, DriverId, Stint)]
  cat("Built cutoff-safe pace histories.\n")
  stream_missing <- character(); streams <- list()
  for (e in catalog$event_id) {
    paths <- file.path(cfg$data_root, "sessions", e, c("weather.csv", "track_status.csv"))
    stream_missing <- c(stream_missing, paths[!file.exists(paths)])
    streams[[e]] <- list(weather=if (file.exists(paths[1])) read_csv(paths[1]) else data.table(),
                         status=if (file.exists(paths[2])) read_csv(paths[2]) else data.table())
  }
  # One row for every potential driver/lap decision, including all stay-out laps.
  # The current lap's duration, result, tyre transition, and weather are NOT copied.
  decisions <- laps[, .(event_id, driver=DriverId, decision_lap=LapNumber+1L,
    cutoff_sec=Time_sec, completed_lap=LapNumber, circuit, year, compound=Compound,
    tyre_age=TyreLife, prior_use=!FreshTyre, position=Position, team=Team,
    scheduled_laps, laps_remaining=scheduled_laps-LapNumber, progress=LapNumber/scheduled_laps,
    recent_pace_sec=known_pace,recent_slope_sec=known_slope,history_n=known_n,history_last_sec=known_last)]
  decisions <- decisions[is.finite(cutoff_sec) & is.finite(tyre_age) &
                         compound %in% dry_compounds & decision_lap < scheduled_laps]
  # Relative state uses only same-boundary crossings already seen by this cutoff.
  setorder(decisions,event_id,completed_lap,cutoff_sec)
  decisions[, c("rival_driver","rival_gap_sec","relative_pace_sec") :=
    list(shift(driver),cutoff_sec-shift(cutoff_sec),recent_pace_sec-shift(recent_pace_sec)),
    by=.(event_id,completed_lap)]
  decisions[, c("teammate_driver","teammate_gap_sec","teammate_position",
    "teammate_compound","teammate_tyre_age","teammate_prior_use") := {
      other<-if(.N==2) c(2L,1L) else rep(NA_integer_,.N)
      available<-!is.na(other) & cutoff_sec[other]<=cutoff_sec
      other[!available]<-NA_integer_
      list(driver[other],cutoff_sec-cutoff_sec[other],position[other],compound[other],
        tyre_age[other],prior_use[other])
    },by=.(event_id,completed_lap,team)]
  decisions[,proposed_teammate_stop:=NA_integer_]
  decisions[, c("track_temp", "air_temp", "rainfall", "weather_sec", "flag") := {
    w <- streams[[.BY$event_id]]$weather; s <- streams[[.BY$event_id]]$status
    wi <- if (nrow(w)) findInterval(cutoff_sec, w$Time_sec) else rep(0L,.N)
    si <- if (nrow(s)) findInterval(cutoff_sec, s$Time_sec) else rep(0L,.N)
    at <- function(d, col, ix, blank=NA_real_) {
      v <- rep(blank,length(ix)); ok <- ix>0; if (any(ok)) v[ok] <- d[[col]][ix[ok]]; v
    }
    wt <- at(w,"Time_sec",wi); stale <- is.na(wt) | cutoff_sec-wt>cfg$weather_max_age_sec
    tt <- at(w,"TrackTemp",wi); aa <- at(w,"AirTemp",wi); rr <- as_bool(at(w,"Rainfall",wi,NA_character_))
    tt[stale] <- aa[stale] <- NA_real_; rr[stale] <- NA
    list(tt,aa,rr,wt,at(s,"Status",si,NA_character_))
  }, by=event_id]
  decisions[, eligible := history_n>=3 & !is.na(rainfall) & !rainfall & flag=="1"]
  decisions[is.na(eligible), eligible:=FALSE]
  si <- match(paste(decisions$event_id,decisions$driver,decisions$decision_lap),
              paste(stops$event_id,stops$driver_ref,stops$stop_lap))
  decisions[, observed_action := ifelse(is.na(si),"stayed_out","pitted")]
  decisions[, decision_id := paste(event_id,driver,decision_lap,sep=":")]
  key_check(decisions,"decision_id","decisions")
  cat("Built",nrow(decisions),"decision rows.\n")
  list(laps=laps, stops=stops, catalog=catalog, streams=streams, decisions=decisions,
       candidates=read_csv(required[4]), missing=stream_missing,
       source_paths=c(required, unlist(lapply(catalog$event_id, function(e)
         file.path(cfg$data_root,"sessions",e,c("weather.csv","track_status.csv"))))))
}
history_at <- function(z, cutoff, cfg=f1_config()) {
  known <- z[is.finite(Time_sec) & Time_sec <= cutoff]
  if (!nrow(known)) return(list(pace=NA_real_,slope=NA_real_,n=0L,last=NA_real_,rows=known))
  st <- tail(known$Stint,1); h <- tail(known[clean & Stint==st],cfg$lookback)
  list(pace=if(nrow(h)>=3) median(h$LapTime_sec) else NA_real_,
       slope=if(nrow(h)>=3) local_slope(h$TyreLife,h$LapTime_sec) else NA_real_,
       n=nrow(h), last=if(nrow(h)) max(h$Time_sec) else NA_real_, rows=h)
}
pace_design <- function(z, temp) {
  x <- copy(z)
  x[, season := year-2020]
  x[, temp := fifelse(is.finite(TrackTemp),TrackTemp,temp)]
  x
}
fit_models <- function(src, cfg=f1_config()) {
  train <- pace_design(src$laps[clean & year<=cfg$train_end], 30)
  temp <- median(train$TrackTemp,na.rm=TRUE); train <- pace_design(train,temp)
  fit <- lm(LapTime_sec ~ circuit + season + Compound * TyreLife + progress + temp, data=train)
  effects <- as.data.table(expand.grid(circuit=sort(unique(train$circuit)),
                                      Compound=sort(unique(train$Compound)),stringsAsFactors=FALSE))
  support <- train[,.(laps=.N,races=uniqueN(event_id),age_min=min(TyreLife),age_max=max(TyreLife)),by=.(circuit,Compound)]
  model <- list(fit=fit,temp=temp,support=support,selected="pooled",cfg=cfg,
    train_events=unique(train$event_id),
    baseline_ahead_probability=mean(as_bool(src$candidates[year<=cfg$train_end,pass_recomputed])))
  model$cycles <- fit_cycles(src,model,cfg)
  model
}
predict_normal <- function(z, model) {
  as.numeric(predict(model$fit, newdata=pace_design(z,model$temp)))
}
normal_for_state <- function(state, lap, compound, age, model, method=model$selected) {
  if (method=="baseline") return(rep(state$recent_pace_sec,length(lap)))
  z <- data.table(circuit=state$circuit,year=state$year,Compound=compound,
    TyreLife=age,progress=lap/state$scheduled_laps,TrackTemp=state$track_temp)
  state$recent_pace_sec + predict_normal(z,model) - state$recent_model_sec
}
fit_cycles <- function(src, model, cfg) {
  ans <- lapply(seq_len(nrow(src$stops)), function(i) {
    s <- src$stops[i]
    if (s$year>cfg$train_end || s$stop_status!="matched" ||
        !is.finite(s$pitlane_elapsed_sec) || s$pitlane_elapsed_sec<=0 ||
        !s$old_compound %in% dry_compounds || !s$new_compound %in% dry_compounds) return(NULL)
    z <- src$laps[s$event_id,on="event_id"][DriverId==s$driver_ref]
    pair <- z[LapNumber %in% c(s$stop_lap,s$stop_lap+1)]
    if (nrow(pair)!=2 || s$outlap_number!=s$stop_lap+1 ||
        any(!is.finite(pair$LapTime_sec) | !is.finite(pair$clock_error_sec) |
            pair$clock_error_sec>cfg$timing_tolerance_sec | pair$TrackStatus!="1" |
            is.na(pair$Rainfall) | pair$Rainfall | is.na(pair$TyreLife) |
            is.na(pair$WeatherSampleAge_sec) | pair$WeatherSampleAge_sec>cfg$weather_max_age_sec) ||
        anyNA(pair$TrackStatus)) return(NULL)
    h <- history_at(z,pair$LapStartTime_sec[1],cfg)
    if (h$n<3) return(NULL)
    old_pred <- predict_normal(h$rows,model)
    normal <- predict_normal(pair,model)+median(h$rows$LapTime_sec-old_pred)
    excess <- sum(pair$LapTime_sec-normal)
    if (!is.finite(excess) || excess<=0) return(NULL)
    data.table(event_id=s$event_id,driver=s$driver_ref,stop_lap=s$stop_lap,
      circuit=pair$circuit[1],old=s$old_compound,new=s$new_compound,
      cycle_excess_sec=excess,pitlane_elapsed_sec=s$pitlane_elapsed_sec)
  })
  rbindlist(ans)
}
evaluate_pace <- function(src, model, training=FALSE) {
  z <- src$laps[clean & (if(training) year<=model$cfg$train_end else year>model$cfg$train_end) &
                history_n>=3 & is.finite(recent_pace_sec)]
  z <- z[circuit %in% model$fit$xlevels$circuit & Compound %in% model$fit$xlevels$Compound]
  # Use lagged pooled predictions from clean history, never the target lap.
  all <- copy(src$laps[circuit %in% model$fit$xlevels$circuit & Compound %in% model$fit$xlevels$Compound])
  all[, pred := predict_normal(.SD,model)]
  all[, recent_model := {
    out <- rep(NA_real_,.N); good <- integer()
    for(i in seq_len(.N)) { h<-tail(good,model$cfg$lookback); if(length(h)>=3) out[i]<-median(pred[h]); if(clean[i]) good<-c(good,i) }; out
  },by=.(event_id,DriverId,Stint)]
  idx <- match(paste(z$event_id,z$DriverId,z$LapNumber),paste(all$event_id,all$DriverId,all$LapNumber))
  z[, pooled_sec := recent_pace_sec + all$pred[idx]-all$recent_model[idx]]
  z[, baseline_sec := recent_pace_sec]
  z[, split := ifelse(year==model$cfg$validation_year,"validation","test")]
  z[,.(event_id,DriverId,Stint,circuit,LapNumber,year,split,observed_sec=LapTime_sec,pooled_sec,baseline_sec)]
}
