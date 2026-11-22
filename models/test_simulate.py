"""Tests for the Monte Carlo simulation (A7, #24): python -m pytest models -q"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate  # noqa: E402

PAIRS = Path(__file__).resolve().parents[1] / "data/derived/pairs.csv"
pytestmark = pytest.mark.skipif(not PAIRS.exists(), reason="needs data/derived/pairs.csv")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("sim")
    simulate.main(["--draws", "300", "--out", str(d)])
    return d


def test_training_rows_only():
    train = simulate.load_training(PAIRS)
    assert set(train["split"]) == {"train"}
    assert train["year"].between(2018, 2023).all()


def test_grid_shape_and_ranges(out):
    g = pd.read_csv(out / "scenario_grid.csv")
    assert len(g) == len(simulate.GAPS) * len(simulate.EXTRA) * len(simulate.GROUPS)
    for c in ("success_rate", "mean_p", "p05", "p95", "share_favoured"):
        assert g[c].between(0, 1).all()
    assert (g.p05 <= g.p50).all() and (g.p50 <= g.p95).all()


def test_slower_stop_and_bigger_gap_lower_the_chance(out):
    g = pd.read_csv(out / "scenario_grid.csv")
    for grp, sub in g.groupby("delay_group"):
        piv = sub.pivot(index="gap_sec", columns="extra_pit_sec", values="mean_p")
        assert (piv.diff(axis=1).iloc[:, 1:] < 0).all().all()   # common random numbers: strictly lower
        assert piv.iloc[0, 0] > piv.iloc[-1, 0]


def test_model_json_matches_fit(out):
    m = json.loads((out / "model.json").read_text())
    assert m["fitted_on"] == "train"
    assert len(m["beta"]) == len(m["names"]) == len(m["theta"]) - 1
    assert len(m["contexts"][0]) == len(m["context_cols"])
