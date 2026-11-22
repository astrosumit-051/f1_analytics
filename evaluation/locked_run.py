"""Preflight and a single authorized frozen evaluation. Defaults to no outcome access."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pandas as pd
from evaluate import (evaluate,read_split,validate_schema,validate_geometry,fingerprint,
                      supported_grid,crossing,write_calibration,manifest)
from bootstrap import metric_intervals

PARTNERS={"aidenh144","astrosumit-051"}
HARNESS=["evaluation/evaluate.py","evaluation/bootstrap.py","evaluation/locked_run.py"]


def git(root,*args):
    run=subprocess.run(["git","-C",str(root),*args],capture_output=True)
    if run.returncode:raise ValueError("Required committed governance is unavailable: "+" ".join(args))
    return run.stdout


def parse_freeze(text):
    for block in re.split(r"(?m)^##\s+",text):
        heading=block.splitlines()[0] if block else ""
        if not re.search(r"model[ -]freeze|freeze[ -](?:the[ -])?model",heading,re.I):continue
        if not re.search(r"(?im)^-?\s*Status:\s*accepted\s*$",block):continue
        commit=re.search(r"(?im)^-?\s*Commit(?: hash)?:\s*`?([a-f0-9]{40})`?\s*$",block)
        models=re.search(r"(?im)^-?\s*model_ids?:\s*(.+)$",block)
        both=re.search(r"(?im)^-?\s*Decided by:\s*(.+)$",block)
        if commit and models and both and {"sumit","aiden"}<=set(re.findall(r"\w+",both[1].lower())):
            return commit[1],set(re.findall(r"[\w.-]+",models[1]))
    raise ValueError("No accepted merged model freeze with both partners, model IDs and full commit hash; no outcome input opened.")


def validate_authorization(auth,freeze,split):
    commit,models=freeze
    if (auth.get("authorized") is not True or auth.get("issue")!={"test":19,"transfer":20}[split]
        or auth.get("split")!=split or set(auth.get("signoffs",[]))!=PARTNERS
        or auth.get("model_commit")!=commit or set(auth.get("model_ids",[]))!=models
        or auth.get("baseline") not in models):
        raise ValueError("Merged authorization does not match the shared frozen model and issue.")
    if not auth.get("outcomes") or not set(auth["outcomes"])<={"success_h3","success_common_h3","success_h0","success_h5"}:
        raise ValueError("Authorization must name supported outcomes.")
    if not isinstance(auth.get("resamples"),int) or auth["resamples"]<1000 or not isinstance(auth.get("seed"),int):
        raise ValueError("Authorize a fixed integer seed and at least 1000 metric resamples.")
    for key in ("pairs_sha256","predictions_sha256","window_grid_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}",str(auth.get(key,""))):raise ValueError("Missing authorized input hash: "+key)


def governance(root,split):
    # Only origin/main counts; a proposed local decision or branch cannot unlock.
    text=git(root,"show","origin/main:DECISIONS.md").decode("utf-8-sig")
    freeze=parse_freeze(text)
    auth_path=f"evaluation/{'locked' if split=='test' else 'transfer'}_authorization.json"
    raw=git(root,"show",f"origin/main:{auth_path}")
    auth=json.loads(raw);validate_authorization(auth,freeze,split)
    git(root,"cat-file","-e",freeze[0]+"^{commit}")
    for path in HARNESS:
        if auth.get("harness_sha256",{}).get(path)!=fingerprint(root/path):
            raise ValueError("Harness differs from approved source: "+path)
    # Reject a prior run recorded on main as well as a local reservation.
    receipt_path=f"evaluation/locked_receipts/{split}.json"
    prior=subprocess.run(["git","-C",str(root),"cat-file","-e","origin/main:"+receipt_path],capture_output=True)
    if prior.returncode==0:raise ValueError("A committed receipt already exists; do not rerun this split.")
    if (root/receipt_path).exists():raise ValueError("A local run reservation already exists; do not rerun.")
    if split=="transfer":
        test=git(root,"show","origin/main:evaluation/locked_receipts/test.json")
        if (json.loads(test).get("status")!="completed" or
            hashlib.sha256(test).hexdigest()!=auth.get("test_receipt_sha256")):
            raise ValueError("Transfer needs the approved completed 2025 receipt.")
    return auth,hashlib.sha256(raw).hexdigest(),git(root,"rev-parse","origin/main").decode().strip()


def reserve(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as handle:json.dump(payload,handle,indent=2)


def execute(root,split,auth,pairs_path,predictions_path,grid_path,governance_sha,main_sha):
    """Called only after merged approval and a fresh origin/main check."""
    for path,key in ((pairs_path,"pairs_sha256"),(predictions_path,"predictions_sha256"),(grid_path,"window_grid_sha256")):
        if fingerprint(path)!=auth[key]:raise ValueError("Input differs from authorized hash: "+str(path))
    receipt=root/f"evaluation/locked_receipts/{split}.json"
    out=root/f"evaluation/locked_results/{split}"
    if out.exists():raise ValueError("Locked output directory already exists; do not rerun.")
    record=dict(status="started",split=split,issue=auth["issue"],model_commit=auth["model_commit"],
        main_sha=main_sha,authorization_sha256=governance_sha,
        started_utc=datetime.now(timezone.utc).isoformat(),input_hashes={k:auth[k] for k in
        ("pairs_sha256","predictions_sha256","window_grid_sha256")})
    reserve(receipt,record) # Atomic, persistent; failure is still a consumed run.
    try:
        pairs=read_split(pairs_path,split);pred=read_split(predictions_path,split)
        validate_schema(pairs,"pairs");validate_geometry(pairs);validate_schema(pred,"predictions")
        if set(pred.model_id)!=set(auth["model_ids"]) or set(pred.outcome)!=set(auth["outcomes"]):
            raise ValueError("Predictions differ from approved models/outcomes")
        metrics,calibration=evaluate(pairs,pred,auth["baseline"],split)
        intervals=metric_intervals(pairs,pred,auth["baseline"],split,auth["resamples"],auth["seed"])
        grid=pd.read_csv(grid_path)
        if set(grid.model_id)!=set(auth["model_ids"]) or not set(grid.outcome)<=set(auth["outcomes"]):
            raise ValueError("Grid differs from approved models/outcomes")
        validate_schema(grid.astype(str).replace("nan",float("nan")),"window_grid")
        if grid[["p_lo","p_hi"]].isna().any().any():raise ValueError("Frozen grid lacks precomputed race-bootstrap bands")
        if (grid.p_lo>grid.p_hi).any():raise ValueError("Unordered grid bands")
        crossing_rows=[];supported=[]
        for model,outcome,delay,rows in supported_grid(grid,pairs):
            supported.append(rows)
            for threshold in (.5,.25):
                gap,status=crossing(rows.gap_sec,rows.p_success,threshold)
                crossing_rows.append(dict(model_id=model,outcome=outcome,delay_group=delay,
                    threshold=threshold,crossing_gap_sec=gap,status=status))
        out.mkdir(parents=True,exist_ok=False)
        evidence="locked 2025 evaluation" if split=="test" else "descriptive 2026 transfer; no retraining"
        metrics.assign(evidence=evidence).to_csv(out/"metrics.csv",index=False)
        intervals.assign(evidence=evidence).to_csv(out/"metric_intervals.csv",index=False)
        calibration.to_csv(out/"calibration.csv",index=False)
        write_calibration(calibration,out/"calibration.png",evidence)
        pd.DataFrame(crossing_rows).to_csv(out/"crossings.csv",index=False)
        pd.concat(supported).to_csv(out/"supported_window_grid.csv",index=False)
        (out/"run.json").write_text(json.dumps(manifest([pairs_path,predictions_path,grid_path],
            split=split,evidence=evidence,seed=auth["seed"],resamples=auth["resamples"]),indent=2)+"\n")
        record.update(status="completed",outputs_sha256={p.name:fingerprint(p) for p in out.iterdir()})
    except Exception as error:
        record.update(status="failed_do_not_retry",error=str(error))
        raise
    finally:
        receipt.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split",choices=["test","transfer"],default="test")
    p.add_argument("--execute",action="store_true",help="Consume the single authorized run")
    p.add_argument("--pairs",type=Path);p.add_argument("--predictions",type=Path);p.add_argument("--window-grid",type=Path)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    try:
        if a.execute:git(root,"fetch","origin","main")
        auth,digest,revision=governance(root,a.split)
        if not a.execute:
            print("Governance preflight passed. No outcome input opened; no evaluation run.");return
        if not all([a.pairs,a.predictions,a.window_grid]):raise ValueError("Execution needs all three approved input paths")
        out=execute(root,a.split,auth,a.pairs,a.predictions,a.window_grid,digest,revision)
        print("Completed authorized run; commit outputs and receipt unchanged: "+str(out))
    except (ValueError,OSError,KeyError) as error:p.exit(2,str(error)+"\n")


if __name__=="__main__":main()
