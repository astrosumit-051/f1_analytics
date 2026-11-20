"""Governance and single-run tests use invented fixtures only."""
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
from evaluate import fingerprint,read_split
from locked_run import PARTNERS,parse_freeze,validate_authorization,reserve,execute

ROOT=Path(__file__).resolve().parents[1]


def approval():
    return dict(issue=19,authorized=True,split="test",model_commit="a"*40,
        model_ids=["FAKE_baseline_gap_v0","FAKE_primary_v0"],baseline="FAKE_baseline_gap_v0",
        outcomes=["success_h3"],signoffs=list(PARTNERS),resamples=1000,seed=355,
        pairs_sha256="b"*64,predictions_sha256="c"*64,window_grid_sha256="d"*64)


def test_freeze_requires_accepted_both_and_commit():
    block="## D-009 Model freeze\n- Status: accepted\n- Decided by: Sumit, Aiden\n- model_ids: baseline_gap_v1, primary_v1\n- Commit hash: "+"a"*40+"\n"
    assert parse_freeze(block)==("a"*40,{"baseline_gap_v1","primary_v1"})
    for bad in [block.replace("accepted","proposed"),block.replace("Sumit, Aiden","Aiden"),block.replace("a"*40,"abc")]:
        with pytest.raises(ValueError):parse_freeze(bad)


@pytest.mark.parametrize("field,value",[("authorized",False),("signoffs",["aidenh144"]),("issue",12),
    ("model_commit","e"*40),("predictions_sha256",""),("resamples",10),("outcomes",["bogus"])])
def test_approval_rejections(field,value):
    a=approval();a[field]=value
    with pytest.raises(ValueError):validate_authorization(a,("a"*40,{"FAKE_baseline_gap_v0","FAKE_primary_v0"}),"test")


def test_atomic_reservation(tmp_path):
    path=tmp_path/"test.json"
    reserve(path,{"status":"started"})
    with pytest.raises(FileExistsError):reserve(path,{"status":"again"})
    assert json.loads(path.read_text())["status"]=="started"


def fixture_files(tmp_path,invalid=False):
    pairs=read_split(ROOT/"contracts/fake/pairs_fake.csv","test")
    pred=read_split(ROOT/"contracts/fake/predictions_fake.csv","test")
    pred["fitted_on"]="train+tune"
    if invalid:pred.loc[0,"p_success"]="2"
    grid=pd.read_csv(ROOT/"contracts/fake/window_grid_fake.csv")
    grid["p_lo"]=0.;grid["p_hi"]=1.
    paths=[tmp_path/n for n in ("pairs.csv","predictions.csv","grid.csv")]
    for df,path in zip([pairs,pred,grid],paths):df.to_csv(path,index=False)
    a=approval()
    for key,path in zip(["pairs_sha256","predictions_sha256","window_grid_sha256"],paths):a[key]=fingerprint(path)
    return a,paths


def test_synthetic_once_and_receipt(tmp_path):
    a,paths=fixture_files(tmp_path)
    out=execute(tmp_path,"test",a,*paths,"f"*64,"f"*40)
    receipt=json.loads((tmp_path/"evaluation/locked_receipts/test.json").read_text())
    assert receipt["status"]=="completed" and "metrics.csv" in receipt["outputs_sha256"]
    assert pd.read_csv(out/"metrics.csv").scored_pairs.min()>0
    with pytest.raises(ValueError,match="already exists"):execute(tmp_path,"test",a,*paths,"f"*64,"f"*40)


def test_failure_remains_consumed(tmp_path):
    a,paths=fixture_files(tmp_path,invalid=True)
    with pytest.raises(ValueError):execute(tmp_path,"test",a,*paths,"f"*64,"f"*40)
    receipt=tmp_path/"evaluation/locked_receipts/test.json"
    assert json.loads(receipt.read_text())["status"]=="failed_do_not_retry"
    with pytest.raises(FileExistsError):execute(tmp_path,"test",a,*paths,"f"*64,"f"*40)


def test_preflight_opens_no_outcome_inputs():
    receipt=ROOT/"evaluation/locked_receipts/test.json"
    existed=receipt.exists()
    r=subprocess.run([sys.executable,str(ROOT/"evaluation/locked_run.py"),"--pairs","ABSENT"],capture_output=True,text=True)
    assert r.returncode in (0,2) and "ABSENT" not in r.stderr
    assert receipt.exists()==existed
