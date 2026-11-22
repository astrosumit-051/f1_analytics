from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import numpy as np
import pandas as pd
from analysis.extensions.defender.analyze import defender_rows,matched_overlap,run
from evaluation.evaluate import read_split

ROOT=Path(__file__).resolve().parents[3]


def test_complement_only_point_in_time():
    p=read_split(ROOT/"contracts/fake/pairs_fake.csv","train")
    p.loc[p.index[:3],"success_common_h0"]=["1","0",np.nan]
    rows=defender_rows(p)
    assert rows.chaser_not_ahead_common_h0.equals(1-rows.success_common_h0)
    assert "defender_sustained" not in rows
    assert rows.delay.isin(range(-3,4)).all()


def test_fake_pipeline_and_overlap(tmp_path):
    summary,rows=run(read_split(ROOT/"contracts/fake/pairs_fake.csv","train"),tmp_path,40,355)
    assert (summary.completed+summary.missing_outcome).equals(summary.pairs)
    assert summary.status.eq("descriptive").all()
    assert (tmp_path/"defender.png").exists()
    overlap=matched_overlap(rows)
    assert overlap.matched_pairs_per_group.iloc[0]>=0
