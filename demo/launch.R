# Local desktop entry point. Reads handoffs only; never rebuilds or scores holdouts.
script <- sub("^--file=", "", grep("^--file=", commandArgs(), value=TRUE)[1])
root <- normalizePath(file.path(dirname(script), ".."), winslash="/", mustWork=TRUE)
setwd(root)
dir.create("evaluation/results",recursive=TRUE,showWarnings=FALSE)
log_path <- file.path(root,"evaluation/results/launcher.log")
con <- file(log_path,open="wt")
sink(con); sink(con,type="message")
tryCatch({
  user_lib <- file.path(Sys.getenv("LOCALAPPDATA"),"R/win-library",
                        paste(R.version$major,strsplit(R.version$minor,".",fixed=TRUE)[[1]][1],sep="."))
  desktop_lib <- file.path(Sys.getenv("USERPROFILE"),"AppData/Local/R/win-library",basename(user_lib))
  .libPaths(c(desktop_lib,user_lib,.libPaths()))
  if(!requireNamespace("shiny",quietly=TRUE)) stop("The R package shiny is missing. Install it in RStudio first.")
  Sys.unsetenv(c("F1_PAIRS","F1_WINDOW_GRID","F1_NO_RESPONSE","F1_GRID_METADATA"))
  approved <- file.path(root,"data/derived/pairs.csv")
  if(file.exists(approved)) {
    pairs <- approved; nr <- file.path(root,"data/derived/no_response.csv")
    grid <- file.path(root,"data/derived/window_grid.csv"); mode <- "real"
  } else {
    pairs <- file.path(root,"evaluation/local_inputs/pairs_train.csv")
    nr <- file.path(root,"evaluation/local_inputs/no_response_train.csv")
    grid <- file.path(root,"evaluation/local_inputs/MODEL_PENDING.csv"); mode <- "provisional"
  }
  if(!file.exists(pairs)) stop("Real training handoff files are missing. See demo/README.md; no synthetic data was substituted.")
  Sys.setenv(F1_PROJECT_ROOT=root,F1_MODE=mode,F1_PAIRS=pairs,F1_NO_RESPONSE=nr,
             F1_WINDOW_GRID=grid,F1_LOCAL_LAUNCH="1")
  source("demo/data.R",local=TRUE)
  data <- load_handoffs(root,mode)
  cat("READY: validated",nrow(data$core),"core training rows; mode",mode,"\n")
  if(!"--check" %in% commandArgs(TRUE)) {
    url <- "http://127.0.0.1:3855"
    options(timeout=2)
    existing <- tryCatch(paste(readLines(url,warn=FALSE),collapse=""),error=function(e) "")
    if(grepl("<title>F1 undercut window</title>",existing,fixed=TRUE)) utils::browseURL(url) else
      shiny::runApp("demo",host="127.0.0.1",port=3855,launch.browser=TRUE)
  }
},error=function(e) {
  cat("LAUNCH ERROR:",conditionMessage(e),"\n",file=stderr())
  if(!"--check" %in% commandArgs(TRUE)) shell.exec(log_path)
})
