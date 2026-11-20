"""Independent arithmetic, common-case, malformed-input and protection checks."""
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from evaluate import crossing, evaluate, prepare_scores, read_split, score, supported_grid

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data():
    pairs = pd.DataFrame(dict(battle_id=list("abcd"), event_id=["2018_01"]*2+["2019_01"]*2,
        year=["2018"]*2+["2019"]*2, split="train", in_core="1",
        gap_before_sec=[1.,2.,3.,4.], success_h3=[1,0,np.nan,1]))
    pred = pd.DataFrame([dict(battle_id=b,model_id=m,outcome="success_h3",fitted_on="train",
        split="train",p_success=p) for m,ps in [("base",[.5]*4),("model",[.8,.2,.3,.7])]
        for b,p in zip("abcd",ps)])
    return pairs,pred


def test_hand_calculated_metrics(data):
    metrics,cal = evaluate(*data,"base","train")
    model = metrics.set_index("model_id").loc["model"]
    assert model.brier == pytest.approx((.04+.04+.09)/3)
    assert model.log_loss == pytest.approx(-(2*math.log(.8)+math.log(.7))/3)
    assert model.brier_minus_baseline == pytest.approx(model.brier-.25)
    assert model.scored_pairs == 3 and model.missing_outcome == 1
    assert cal.groupby("model_id").n.sum().tolist() == [3,3]
    assert model.calibration_bias == pytest.approx((.8+.2+.7)/3-2/3)


def test_paired_missing_prediction(data):
    p,f=data
    f=f.loc[~(f.model_id.eq("model") & f.battle_id.eq("d"))]
    metrics,_=evaluate(p,f,"base","train")
    assert set(metrics.scored_pairs)=={2}
    assert set(metrics.missing_prediction_any_model)=={1}


@pytest.mark.parametrize("change", ["duplicate", "unknown", "futurefit", "range", "nan", "outcome", "split"])
def test_bad_predictions(data,change):
    p,f=data
    if change=="duplicate": f=pd.concat([f,f.iloc[:1]])
    if change=="unknown": f.loc[0,"battle_id"]="unknown"
    if change=="futurefit": f.loc[0,"fitted_on"]="train+tune"
    if change=="range": f.loc[0,"p_success"]=1.1
    if change=="nan": f.loc[0,"p_success"]=np.nan
    if change=="outcome": f.loc[0,"outcome"]="future_feature"
    if change=="split": f.loc[0,"split"]="test"
    with pytest.raises(ValueError): list(prepare_scores(p,f,"base","train"))


@pytest.mark.parametrize("change",["id","race","year","gap","outcome","baseline"])
def test_bad_pairs(data,change):
    p,f=data
    if change=="id": p.loc[0,"battle_id"]="b"
    if change=="race": p.loc[0,"event_id"]=np.nan
    if change=="year": p.loc[0,"year"]="2025"
    if change=="gap": p.loc[0,"gap_before_sec"]=-1
    if change=="outcome": p.loc[0,"success_h3"]=2
    with pytest.raises(ValueError): evaluate(p,f,"missing" if change=="baseline" else "base","train")


def test_crossings():
    assert crossing([1,2],[.75,.25],.5)==(1.5,"crossed")
    assert crossing([1,2],[.75,.5],.5)==(2.,"crossed")
    assert crossing([1,2],[.2,.1],.5)[1]=="no_downward_crossing"
    assert crossing([1,2],[.5,.5],.5)[1]=="flat_at_threshold"
    assert crossing([1,2,3,4],[.8,.2,.8,.2],.5)[1]=="multiple_downward_crossings"
    with pytest.raises(ValueError): crossing([2,1],[.8,.2],.5)


def test_score_extremes():
    assert score([0,1],[0,1])[0]==0
    assert np.isfinite(score([0,1],[1,0])[1])
    with pytest.raises(ValueError): score([],[])
    with pytest.raises(ValueError): score([0],[float("inf")])


def test_protected_sentinels_filtered_before_parsing(tmp_path):
    path=tmp_path/"rows.csv"
    path.write_text("split,year,success_h3\ntrain,2018,1\ntest,2025,DO_NOT_PARSE\n",encoding="utf-8")
    assert read_split(path,"train").success_h3.tolist()==["1"]
    path.write_text("split,year,success_h3\ntrain,2025,DO_NOT_PARSE\n",encoding="utf-8")
    with pytest.raises(ValueError,match="year and split"): read_split(path,"train")


@pytest.mark.parametrize("split",["tune","test","transfer"])
def test_cli_blocks_before_file_access(tmp_path,split):
    run=subprocess.run([sys.executable,str(ROOT/"evaluation/evaluate.py"),"--pairs","ABSENT",
        "--predictions","ABSENT","--split",split,"--out",str(tmp_path/"out")],capture_output=True,text=True)
    assert run.returncode==2
    assert "no input opened" in run.stderr
    assert not (tmp_path/"out").exists()


def test_fake_end_to_end(tmp_path):
    run=subprocess.run([sys.executable,str(ROOT/"evaluation/evaluate.py"),
        "--pairs",str(ROOT/"contracts/fake/pairs_fake.csv"),
        "--predictions",str(ROOT/"contracts/fake/predictions_fake.csv"),
        "--window-grid",str(ROOT/"contracts/fake/window_grid_fake.csv"),
        "--baseline","FAKE_baseline_gap_v0","--out",str(tmp_path)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert {"metrics.csv","calibration.csv","calibration.png","crossings.csv","run.json"} <= {p.name for p in tmp_path.iterdir()}
    assert pd.read_csv(tmp_path/"metrics.csv").evidence.str.contains("synthetic").all()
