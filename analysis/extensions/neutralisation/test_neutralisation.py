from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import numpy as np
import pandas as pd
import pytest
from analysis.extensions.neutralisation.analyze import prepare,gain_summary,run
from evaluation.evaluate import read_split

ROOT=Path(__file__).resolve().parents[3]


def test_signed_gain_and_missing():
    p=read_split(ROOT/"contracts/fake/pairs_fake.csv","train")
    rows=prepare(p)
    expected=pd.to_numeric(rows.gap_before_sec)-pd.to_numeric(rows.signed_gap_comparison_sec)
    pd.testing.assert_series_equal(rows.observed_gain_sec,expected,check_names=False)
    rows.loc[rows.index[0],"observed_gain_sec"]=np.nan
    a=gain_summary(rows,40,355);b=gain_summary(rows,40,355)
    pd.testing.assert_frame_equal(a,b)
    assert a.missing_gain.sum()==1
    assert {"SC_only","VSC_only","SC_and_VSC","other_unclean","clean_control"} >= set(rows.condition)


def test_fake_pipeline(tmp_path):
    run(read_split(ROOT/"contracts/fake/pairs_fake.csv","train"),tmp_path,30,355)
    assert (tmp_path/"neutralisation.png").exists()
    p=read_split(ROOT/"contracts/fake/pairs_fake.csv","train");p["split"]="test"
    with pytest.raises(ValueError):prepare(p)
