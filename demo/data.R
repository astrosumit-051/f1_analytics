# Pure CSV, validation and analysis helpers. No model fitting or Shiny dependency.
required <- function(x, fields, label) {
  absent <- setdiff(fields,names(x))
  if(length(absent)) stop(label,": missing ",paste(absent,collapse=", "),call.=FALSE)
}
number <- function(x, label, missing=TRUE) {
  y <- suppressWarnings(as.numeric(x))
  if(any(!is.na(x) & (is.na(y) | !is.finite(y))) || (!missing && anyNA(y)))
    stop("Invalid numeric ",label,call.=FALSE)
  y
}
read_training <- function(path) {
  if(!file.exists(path)) stop("Missing handoff CSV: ",path,call.=FALSE)
  x <- read.csv(path,colClasses="character",check.names=FALSE,na.strings=c("","NA"))
  required(x,c("split","year"),"Handoff")
  if(anyDuplicated(names(x))) stop("Duplicate CSV headers")
  allowed <- list(train=as.character(2018:2023),tune="2024",test="2025",transfer="2026")
  if(anyNA(x$split) || any(!x$split %in% names(allowed)) || anyNA(x$year)) stop("Invalid season split")
  for(group in names(allowed))
    if(any(!x$year[x$split==group] %in% allowed[[group]])) stop("Year and split disagree")
  # Never interpret protected outcome values before selecting training records.
  x[x$split=="train",,drop=FALSE]
}
binary <- function(x,label) {
  value <- number(x,label)
  if(any(!is.na(value) & !value %in% 0:1)) stop("Nonbinary ",label)
  value
}
validate_pairs <- function(pairs) {
  required(pairs,c("battle_id","event_id","year","split","chaser","leader","delay","delay_group",
    "clean_window","teammates","in_core","gap_before_sec","chaser_stop_lap","leader_stop_lap",
    "ref_lap","comparison_lap","common_lap","success_h3","success_common_h0","success_common_h3"),"Pairs")
  if(anyNA(pairs$battle_id) || anyDuplicated(pairs$battle_id) || anyNA(pairs$event_id)) stop("Missing or duplicate identifiers")
  for(col in c("clean_window","teammates","in_core")) {
    pairs[[col]] <- binary(pairs[[col]],col)
    if(anyNA(pairs[[col]])) stop("Missing cohort flag ",col)
  }
  for(col in c("gap_before_sec","delay","chaser_stop_lap","leader_stop_lap","ref_lap","comparison_lap","common_lap"))
    pairs[[col]] <- number(pairs[[col]],col,FALSE)
  if(any(pairs$gap_before_sec<=0 | pairs$gap_before_sec>10) || any(!pairs$delay %in% -3:3)) stop("Invalid gaps or delays")
  if(any(pairs$delay!=pairs$leader_stop_lap-pairs$chaser_stop_lap) ||
     any(pairs$ref_lap!=pmin(pairs$chaser_stop_lap,pairs$leader_stop_lap)-1) ||
     any(pairs$comparison_lap!=pmax(pairs$chaser_stop_lap,pairs$leader_stop_lap)+1) ||
     any(pairs$common_lap!=pairs$chaser_stop_lap+4)) stop("Contract clock mismatch")
  expected <- ifelse(pairs$delay==1,"d1",ifelse(pairs$delay>1,"d23",ifelse(pairs$delay==0,"same_lap","leader_first")))
  if(anyNA(pairs$delay_group) || any(expected!=pairs$delay_group)) stop("Delay group mismatch")
  core <- pairs$in_core==1
  if(any(core & (pairs$clean_window!=1 | pairs$teammates!=0 | pairs$delay<1 | pairs$gap_before_sec>6))) stop("Contradictory core flags")
  for(col in c("success_h3","success_common_h0","success_common_h3")) pairs[[col]] <- binary(pairs[[col]],col)
  pairs
}
validate_window <- function(window) {
  required(window,c("model_id","outcome","delay_group","gap_sec","p_success","p_lo","p_hi"),"Window grid")
  if(!nrow(window)) return(window)
  for(col in c("gap_sec","p_success","p_lo","p_hi")) window[[col]] <- number(window[[col]],col,col %in% c("p_lo","p_hi"))
  if(anyNA(window$model_id) || anyNA(window$outcome) || anyNA(window$delay_group) ||
     any(!window$delay_group %in% c("d1","d23")) ||
     any(!window$outcome %in% c("success_h0","success_h3","success_h5","success_common_h3")) ||
     any(window$gap_sec<=0 | window$gap_sec>6) || any(window$p_success<0 | window$p_success>1) ||
     anyDuplicated(window[c("model_id","outcome","delay_group","gap_sec")])) stop("Invalid window keys or probabilities")
  if(any(xor(is.na(window$p_lo),is.na(window$p_hi)))) stop("Incomplete uncertainty endpoints")
  known <- !is.na(window$p_lo)
  if(any(window$p_lo[known]<0 | window$p_hi[known]>1 | window$p_lo[known]>window$p_hi[known])) stop("Invalid uncertainty interval")
  window
}
grid_metadata_valid <- function(metadata_path,window_path,models) {
  if(!file.exists(metadata_path) || !requireNamespace("jsonlite",quietly=TRUE)) return(FALSE)
  info<-tryCatch(jsonlite::fromJSON(metadata_path),error=function(e) NULL)
  isTRUE(!is.null(info) && identical(info$split,"train") &&
    all(models %in% info$models) &&
    identical(unname(tools::md5sum(window_path)),info$window_grid_md5) &&
    !grepl("synthetic",if(is.null(info$evidence)) "" else info$evidence,ignore.case=TRUE))
}
load_handoffs <- function(root, mode=Sys.getenv("F1_MODE","real")) {
  if(!mode %in% c("fake","real","provisional")) stop("F1_MODE must be fake, real or provisional")
  base <- if(mode=="fake") "contracts/fake" else "data/derived"
  name <- function(table) file.path(root,base,paste0(table,if(mode=="fake") "_fake" else "",".csv"))
  pair_path <- Sys.getenv("F1_PAIRS",name("pairs")); window_path <- Sys.getenv("F1_WINDOW_GRID",name("window_grid"))
  nr_path <- Sys.getenv("F1_NO_RESPONSE",name("no_response"))
  pairs <- validate_pairs(read_training(pair_path))
  window <- if(file.exists(window_path)) validate_window(read.csv(window_path,colClasses="character",na.strings=c("","NA"))) else
    data.frame(model_id=character(),outcome=character(),delay_group=character(),gap_sec=numeric(),p_success=numeric(),p_lo=numeric(),p_hi=numeric())
  nr <- if(file.exists(nr_path)) read_training(nr_path) else NULL
  fake_pairs <- grepl("fake",pairs$battle_id,ignore.case=TRUE)
  if(nrow(pairs) && (any(fake_pairs)!=all(fake_pairs) || (mode=="fake")!=all(fake_pairs))) stop("Synthetic and real evidence must be separate")
  if(nrow(window) && ((mode=="fake")!=all(grepl("^FAKE_",window$model_id)) ||
      any(grepl("^FAKE_",window$model_id))!=all(grepl("^FAKE_",window$model_id)))) stop("Synthetic and real model evidence must be separate")
  if(!is.null(nr) && nrow(nr)) {
    required(nr,"chaser","No response")
    fake_nr<-grepl("fake",nr$chaser,ignore.case=TRUE)
    if((mode=="fake")!=all(fake_nr) || any(fake_nr)!=all(fake_nr)) stop("Synthetic and real no-response evidence must be separate")
    no_response_summary(nr) # Validate before using counts anywhere in the UI.
  }
  grid_status<-"Supplied grid"
  if(nrow(window) && mode!="fake") {
    metadata_path<-Sys.getenv("F1_GRID_METADATA",file.path(dirname(window_path),"run.json"))
    verified<-grid_metadata_valid(metadata_path,window_path,unique(window$model_id))
    if(!isTRUE(verified)) {
      window<-window[FALSE,,drop=FALSE]
      grid_status<-"Model unavailable: training provenance or grid fingerprint is missing or mismatched"
    }
  }
  eligible <- pairs[pairs$clean_window==1 & pairs$teammates==0 & pairs$gap_before_sec<=6,,drop=FALSE]
  list(pairs=eligible,core=eligible[eligible$in_core==1,,drop=FALSE],window=window,nr=nr,mode=mode,grid_status=grid_status,
    evidence=switch(mode,fake="Synthetic software fixture | no research findings",provisional="Unmerged training handoff | producer review pending",real="2018-2023 training observations | model review pending"),
    source_md5=tools::md5sum(c(pair_path,if(file.exists(window_path)) window_path,if(file.exists(nr_path)) nr_path)))
}
observed_summary <- function(rows,outcome,groups="delay_group") {
  if(!nrow(rows)) return(data.frame())
  required(rows,c(outcome,groups),"Observed rows")
  keys <- interaction(rows[groups],drop=TRUE,lex.order=TRUE)
  do.call(rbind,lapply(split(rows,keys),function(z) {
    y <- z[[outcome]];known <- !is.na(y)
    cbind(z[1,groups,drop=FALSE],data.frame(pairs=nrow(z),completed=sum(known),missing=sum(!known),
      races=length(unique(z$event_id[known])),successes=sum(y[known]),
      observed=if(any(known)) mean(y[known]) else NA_real_,
      mean_gap=if(any(known)) mean(z$gap_before_sec[known]) else NA_real_))
  }))
}
supported_window <- function(data,model,outcome,delay) {
  cases <- data$core[data$core$delay_group==delay & !is.na(data$core[[outcome]]),,drop=FALSE]
  w <- data$window[data$window$model_id==model & data$window$outcome==outcome & data$window$delay_group==delay,,drop=FALSE]
  if(!nrow(cases) || !nrow(w)) return(w[FALSE,,drop=FALSE])
  bounds <- range(cases$gap_before_sec)
  w <- w[w$gap_sec>=bounds[1] & w$gap_sec<=bounds[2],,drop=FALSE]
  w[order(w$gap_sec),,drop=FALSE]
}
lookup_probability <- function(w,gap) {
  empty <- list(probability=NA_real_,lo=NA_real_,hi=NA_real_,status="Unsupported: no model grid inside observed support")
  if(!is.finite(gap) || nrow(w)<2 || gap<min(w$gap_sec) || gap>max(w$gap_sec)) return(empty)
  at <- function(col) if(anyNA(w[[col]])) NA_real_ else approx(w$gap_sec,w[[col]],xout=gap,rule=1)$y
  list(probability=at("p_success"),lo=at("p_lo"),hi=at("p_hi"),status="Linear interpolation of supplied grid; median-feature profile")
}
crossing_gap <- function(w,threshold) {
  if(nrow(w)<2) return(data.frame(threshold=threshold,gap_sec=NA_real_,status="insufficient_grid"))
  y<-w$p_success;x<-w$gap_sec
  ix<-which(head(y,-1)>=threshold & tail(y,-1)<threshold)
  hits<-vapply(ix,function(i) x[i]+(y[i]-threshold)/(y[i]-y[i+1])*(x[i+1]-x[i]),0.)
  if(tail(y,1)==threshold && y[length(y)-1]>threshold) hits<-c(hits,tail(x,1))
  status<-if(all(y==threshold)) "flat_at_threshold" else if(length(hits)==1) "crossed" else
    if(length(hits)>1) "multiple_downward_crossings" else "no_downward_crossing"
  data.frame(threshold=threshold,gap_sec=if(length(hits)==1) hits else NA_real_,status=status)
}
scenario_snapshot <- function(data,model,outcome,delay,gap) {
  if(!outcome %in% c("success_h3","success_common_h3") || !delay %in% c("d1","d23")) stop("Unsupported scenario")
  cases<-data$core[data$core$delay_group==delay,,drop=FALSE]
  cases$gap_band<-cut(cases$gap_before_sec,0:6,right=TRUE)
  w<-supported_window(data,model,outcome,delay)
  list(window=w,value=lookup_probability(w,gap),rates=observed_summary(cases,outcome,"gap_band"),
    crossings=rbind(crossing_gap(w,.5),crossing_gap(w,.25)),
    comparison=observed_summary(data$pairs,"success_common_h3"),
    defender=observed_summary(data$pairs,"success_common_h0","delay"),cases=cases)
}
no_response_summary <- function(nr) {
  if(is.null(nr)) return("No-response handoff unavailable. Rate pending an agreed opportunity denominator.")
  required(nr,c("clean_window","teammates","gap_before_sec","event_id","chaser","leader","chaser_stop_lap"),"No response")
  for(col in c("clean_window","teammates")) {
    nr[[col]]<-binary(nr[[col]],col)
    if(anyNA(nr[[col]])) stop("Missing no-response cohort flag")
  }
  gap<-number(nr$gap_before_sec,"no-response gap",FALSE)
  keys<-c("event_id","chaser","leader","chaser_stop_lap")
  if(anyNA(nr[keys]) || anyDuplicated(nr[keys])) stop("Missing or duplicate no-response keys")
  n<-sum(nr$clean_window==1 & nr$teammates==0 & gap>0 & gap<=6)
  paste(n,"eligible training no-response records. Rate pending an agreed opportunity denominator.")
}
