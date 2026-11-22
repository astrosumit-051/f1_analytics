from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from figures.stats import rate_summary
from figures.plot_windows import eligible_training, summarize_pairs, prepare_window, summarize_no_response, OUTCOME
from figures.plot_windows import validate_grid_provenance
from evaluation.evaluate import read_split

ROOT=Path(__file__).resolve().parents[1]


def test_race_rate_known_counts_and_seed():
    rows=pd.DataFrame(dict(event_id=["a","a","b","b","c"],group="g",y=[1,1,0,0,np.nan]))
    a=rate_summary(rows,["group"],"y",1000,355)
    pd.testing.assert_frame_equal(a,rate_summary(rows,["group"],"y",1000,355))
    assert a.completed.iloc[0]==4 and a.missing_outcome.iloc[0]==1
    assert a.observed_rate.iloc[0]==.5 and a.completed_races.iloc[0]==2
    assert a.p_lo.iloc[0]==0 and a.p_hi.iloc[0]==1


def test_missing_is_not_failure_and_one_race_no_interval():
    a=rate_summary(pd.DataFrame(dict(event_id=["a","a"],group="g",y=[np.nan,np.nan])),["group"],"y")
    assert pd.isna(a.observed_rate.iloc[0]) and pd.isna(a.p_lo.iloc[0])
    b=rate_summary(pd.DataFrame(dict(event_id=["a"],group="g",y=[1])),["group"],"y")
    assert b.observed_rate.iloc[0]==1 and pd.isna(b.p_hi.iloc[0])


def test_supported_plot_and_pending_no_response():
    rows=eligible_training(read_split(ROOT/"contracts/fake/pairs_fake.csv","train"))
    summary,eligible=summarize_pairs(rows)
    assert (summary.completed+summary.missing_outcome).equals(summary.pairs)
    grid=pd.read_csv(ROOT/"contracts/fake/window_grid_fake.csv")
    # Pair-specific predictions cannot appear on a common-lap chart.
    w,_=prepare_window(grid,eligible,"FAKE_primary_v0")
    assert w.empty
    grid["outcome"]=OUTCOME # explicitly synthetic mapping for support tests only
    w,_=prepare_window(grid,eligible,"FAKE_primary_v0")
    for group,sub in w.groupby("delay_group"):
        gaps=eligible.loc[eligible.delay_group.eq(group)&eligible[OUTCOME].notna(),"gap_before_sec"]
        assert sub.gap_sec.between(gaps.min(),gaps.max()).all()
    nr=eligible_training(read_split(ROOT/"contracts/fake/no_response_fake.csv","train"))
    result=summarize_no_response(nr)
    assert result.no_response_rate.isna().all() and result.rate_status.eq("pending_denominator").all()
    with pytest.raises(ValueError):summarize_no_response(pd.concat([nr,nr.iloc[:1]]))


def test_grid_provenance_fails_closed(tmp_path):
    import json,hashlib
    grid=tmp_path/"grid.csv";grid.write_text("example")
    metadata=tmp_path/"run.json"
    metadata.write_text(json.dumps(dict(split="train",models=["m"],evidence="training",
        window_grid_md5=hashlib.md5(grid.read_bytes()).hexdigest())))
    validate_grid_provenance(metadata,grid,"m")
    grid.write_text("changed")
    with pytest.raises(ValueError):validate_grid_provenance(metadata,grid,"m")
    with pytest.raises(ValueError):validate_grid_provenance(None,grid,"m")
