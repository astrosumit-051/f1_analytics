import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from bootstrap import (STAND_IN_MODELS, bootstrap_training, command_adapter, make_grid,
                       metric_intervals, stand_in, summarize, training_cases)
from evaluate import read_split

ROOT=Path(__file__).resolve().parents[1]


def test_races_are_whole_and_repeated_copies_independent():
    core=pd.DataFrame(dict(event_id=np.repeat(["a","b","c"],2),battle_id=list("abcdef"),
        success_h3=[0,1]*3))
    seen=[]
    def refit(train,grid,oob,models):
        for group,rows in train.groupby("bootstrap_race_id"):
            assert len(rows)==2 and rows.event_id.nunique()==1
            assert set(rows.battle_id)==set(core.loc[core.event_id.eq(rows.event_id.iloc[0]),"battle_id"])
        assert not set(train.event_id)&set(oob.event_id)
        seen.append(train.copy())
        return grid.assign(model_id="m",outcome="success_h3",p_success=.5),{"m":np.full(len(oob),.5)}
    grid=pd.DataFrame(dict(delay_group=["d1"],gap_sec=[1.]))
    one=bootstrap_training(core,"success_h3",grid,refit,["m"],20,355)
    two=bootstrap_training(core,"success_h3",grid,refit,["m"],20,355)
    pd.testing.assert_frame_equal(one[0],two[0])
    assert any(t.event_id.nunique()<3 for t in seen)


def test_failure_accounting():
    core=pd.DataFrame(dict(event_id=["a","a","b","b"],success_h3=[0,1,0,1]))
    calls=[]
    def refit(train,grid,oob,models):
        calls.append(1)
        if len(calls)==1: raise RuntimeError("intentional fit failure")
        return grid.assign(model_id="m",outcome="success_h3",p_success=.5),{"m":np.full(len(oob),.5)}
    grid=pd.DataFrame(dict(delay_group=["d1"],gap_sec=[1.]))
    windows,metrics,failures=bootstrap_training(core,"success_h3",grid,refit,["m"],3,2)
    assert len(failures)==1 and failures.reason.iloc[0]=="intentional fit failure"
    assert windows.draw.nunique()==2


def test_fake_refits_and_missing_crossings():
    core,missing=training_cases(ROOT/"contracts/fake/pairs_fake.csv","success_common_h3")
    grid=make_grid(core); refit=stand_in("success_common_h3")
    point,_=refit(core,grid,core.iloc[:0],STAND_IN_MODELS)
    windows,metrics,failures=bootstrap_training(core,"success_common_h3",grid,refit,STAND_IN_MODELS,12,355)
    out,crossings,ranges=summarize(point,windows,metrics)
    assert out.p_lo.between(0,1).all() and out.p_hi.between(0,1).all()
    assert (out.p_lo<=out.p_hi).all() and len(failures)==0
    assert (crossings.draws_with_crossing<=crossings.draws).all()
    real=core.copy();real["battle_id"]="real_"+real.index.astype(str)
    with pytest.raises(ValueError,match="synthetic"):refit(real,grid,core.iloc[:0],STAND_IN_MODELS)


def test_metric_intervals_are_paired():
    p=read_split(ROOT/"contracts/fake/pairs_fake.csv","train")
    f=read_split(ROOT/"contracts/fake/predictions_fake.csv","train")
    a=metric_intervals(p,f,"FAKE_baseline_gap_v0","train",30,355)
    b=metric_intervals(p,f,"FAKE_baseline_gap_v0","train",30,355)
    pd.testing.assert_frame_equal(a,b)
    baseline=a.loc[a.model_id.eq("FAKE_baseline_gap_v0") & a.metric.str.endswith("minus_baseline")]
    assert baseline.p_lo.eq(0).all() and baseline.p_hi.eq(0).all()


def test_public_command_adapter(tmp_path):
    # This mock checks the interface, not A's unprovided scientific model.
    script=tmp_path/"fake_command.py"
    script.write_text('''import argparse,csv
p=argparse.ArgumentParser()
for k in ["train","predict","model","out"]: p.add_argument("--"+k,required=True)
a=p.parse_args()
train=list(csv.DictReader(open(a.train)))
assert len({r["battle_id"] for r in train})==len(train)
predict=list(csv.DictReader(open(a.predict)))
with open(a.out,"w",newline="") as h:
 w=csv.DictWriter(h,fieldnames=["battle_id","model_id","outcome","fitted_on","split","p_success"]);w.writeheader()
 for r in predict:w.writerow(dict(battle_id=r["battle_id"],model_id=a.model,outcome="success_h3",fitted_on="train",split="train",p_success=0.4))
''',encoding="utf-8")
    core,_=training_cases(ROOT/"contracts/fake/pairs_fake.csv","success_h3")
    grid=make_grid(core).iloc[:3]
    refit=command_adapter([sys.executable,str(script)],"success_h3")
    w,o=refit(core,grid,core.iloc[:2],["FAKE_mock"])
    assert w.p_success.eq(.4).all() and len(o["FAKE_mock"])==2
    bootstrap_training(core,"success_h3",grid,refit,["FAKE_mock"],2,355)
    with pytest.raises(ValueError,match="common-lap"): command_adapter(["mock"],"success_common_h3")
