"""Package only the files needed for the local historical-data Shiny app.

No fitting, data rebuilding or protected evaluation occurs. Destination must be new.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


CONFIG = r'''configure_desktop <- function(root) {
  root <- normalizePath(root,winslash="/",mustWork=TRUE)
  version <- paste(R.version$major,strsplit(R.version$minor,".",fixed=TRUE)[[1]][1],sep=".")
  .libPaths(c(file.path(Sys.getenv("USERPROFILE"),"AppData/Local/R/win-library",version),
              file.path(Sys.getenv("LOCALAPPDATA"),"R/win-library",version),.libPaths()))
  Sys.unsetenv(c("F1_PAIRS","F1_WINDOW_GRID","F1_NO_RESPONSE","F1_GRID_METADATA"))
  Sys.setenv(F1_PROJECT_ROOT=root,F1_MODE="provisional",F1_LOCAL_LAUNCH="1",
    F1_PAIRS=file.path(root,"data/pairs_train.csv"),
    F1_NO_RESPONSE=file.path(root,"data/no_response_train.csv"),
    F1_WINDOW_GRID=file.path(root,"data/window_grid.csv"))
  invisible(root)
}
'''

LAUNCH = r'''script <- grep("^--file=",commandArgs(),value=TRUE)
root <- if(length(script)) dirname(sub("^--file=","",script[1])) else getwd()
root <- normalizePath(root,winslash="/",mustWork=TRUE)
setwd(root)
check <- "--check" %in% commandArgs(TRUE)
url <- "http://127.0.0.1:3855"
options(timeout=2)
existing <- if(check) "" else tryCatch(paste(readLines(url,warn=FALSE),collapse=""),error=function(e) "")
if(grepl("<title>F1 undercut window</title>",existing,fixed=TRUE)) {
  utils::browseURL(url)
} else {
  dir.create("logs",showWarnings=FALSE)
  log_path <- file.path(root,"logs/launcher.log")
  con <- file(log_path,open="wt"); sink(con); sink(con,type="message")
  failed <- FALSE
  tryCatch({
    source("desktop_config.R",local=TRUE); configure_desktop(root)
    if(!requireNamespace("shiny",quietly=TRUE)) stop("Install the R package shiny in RStudio first.")
    source("data.R",local=TRUE)
    checked <- load_handoffs(root,"provisional")
    cat("READY:",nrow(checked$core),"core training pairs. Historical analysis; real model pending.\n")
    flush(con)
    if(!check) shiny::runApp(root,host="127.0.0.1",port=3855,launch.browser=TRUE)
  },error=function(e) {
    failed <<- TRUE
    cat("LAUNCH ERROR:",conditionMessage(e),"\n",file=stderr()); flush(con)
    if(!check) shell.exec(log_path)
  })
  sink(type="message"); sink(); close(con)
  if(failed) quit(status=2,save="no")
}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out):
    source = Path(__file__).resolve().parents[1]
    inputs = source / "evaluation/local_inputs"
    for name in ("pairs_train.csv", "no_response_train.csv"):
        with (inputs/name).open(encoding="utf-8-sig",newline="") as handle:
            for row in csv.DictReader(handle):
                if row["split"]!="train" or row["year"] not in map(str,range(2018,2024)):
                    raise ValueError("Bundle accepts training-only handoffs")
    out.mkdir() # Never overwrite an existing user folder.
    (out/"data").mkdir();(out/"logs").mkdir()
    for name in ("pairs_train.csv","no_response_train.csv","provenance.json"):
        shutil.copy2(inputs/name,out/"data"/name)
        assert digest(inputs/name)==digest(out/"data"/name)
    shutil.copy2(source/"demo/data.R",out/"data.R")
    shutil.copy2(source/"demo/Open F1 Analytics.vbs",out/"Open F1 Analytics.vbs")
    app=(source/"demo/app.R").read_text(encoding="utf-8-sig")
    old='library(shiny)\nsource("data.R",local=TRUE)\nroot <- normalizePath(Sys.getenv("F1_PROJECT_ROOT",".."),mustWork=FALSE)'
    new='source("desktop_config.R",local=TRUE)\nconfigure_desktop(getwd())\nlibrary(shiny)\nsource("data.R",local=TRUE)\nroot <- normalizePath(".",mustWork=TRUE)'
    if old not in app:raise ValueError("App startup changed; review packaging adapter")
    app=app.replace(old,new,1).replace('tabsetPanel(\n','tabsetPanel(selected="Response comparisons",\n',1)
    (out/"app.R").write_text(app,encoding="utf-8")
    (out/"desktop_config.R").write_text(CONFIG,encoding="utf-8")
    (out/"launch.R").write_text(LAUNCH,encoding="utf-8")
    (out/"F1 Analytics.Rproj").write_text("Version: 1.0\nRestoreWorkspace: No\nSaveWorkspace: No\nAlwaysSaveHistory: No\n",encoding="utf-8")
    (out/"START_HERE.txt").write_text(
        "Double-click Open F1 Analytics.vbs to open the local browser app.\n"
        "Alternatively open F1 Analytics.Rproj in RStudio, open app.R, and click Run App.\n"
        "Keep every file and the data folder together. No tests or raw datasets are needed here.\n"
        "A Shiny app keeps running until you click Stop local app; that is normal.\n"
        "This snapshot uses provisional real 2018-2023 training data. The fitted model is still pending.\n"
        "Response comparisons and Recorded examples work; unavailable model probabilities are expected.\n"
        "Errors are written to logs/launcher.log. R and the shiny package must be installed.\n",encoding="utf-8")
    manifest={"source_commit":subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip(),
        "status":"provisional training-only desktop bundle; model pending",
        "transformations":["self-contained paths","default observed-comparison tab; calculations unchanged"],
        "sha256":{str(p.relative_to(out)):digest(p) for p in out.rglob("*") if p.is_file()}}
    (out/"bundle_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(f"Packaged {len(manifest['sha256'])} runtime/data files in {out}")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    build(parser.parse_args().out.resolve())
