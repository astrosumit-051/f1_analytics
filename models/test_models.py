"""Checks for the A3 models. Run: python -m pytest models -q"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import approx_fprime

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402

FAKE = ROOT / "contracts/fake/pairs_fake.csv"


def simulated(n_races=60, per_race=8, sigma=0.8, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n_races):
        u = rng.normal(0, sigma)
        for i in range(per_race):
            gap = rng.uniform(0.1, 6)
            d23 = rng.random() < 0.4
            eta = 1.0 - 0.8 * gap + 0.7 * d23 + u
            rows.append(dict(event_id=f"r{r}", battle_id=f"r{r}:{i}", gap_before_sec=gap,
                             delay_group="d23" if d23 else "d1", era="pre2022",
                             tyre_age_diff=rng.integers(-5, 6), circuit_pitlane_median_sec=22 + rng.random(),
                             rejoin_traffic_cars=rng.integers(0, 2), cars_between_at_ref=rng.integers(0, 3),
                             overtaking_difficulty=rng.random() / 10,
                             y=float(rng.random() < 1 / (1 + np.exp(-eta)))))
    return pd.DataFrame(rows)


def test_spline_is_linear_beyond_boundary():
    knots = np.array([0.5, 2.0, 3.5, 5.0])
    x = np.array([6.0, 7.0, 8.0])
    b = core.natural_spline_basis(x, knots)
    assert np.allclose(np.diff(b, 2, axis=0), 0, atol=1e-9)
    assert b.shape == (3, 3)


def test_glmm_gradient_matches_finite_differences():
    df = simulated()
    d = core.Design.learn(core.SPECS["primary_v1"], df)
    X = d.matrix(df)
    codes, uniq = pd.factorize(df.event_id)
    theta = np.append(np.random.default_rng(0).normal(0, 0.2, X.shape[1]), np.log(0.7))
    f = lambda t: core._negll_glmm(t, X, df.y.to_numpy(), codes, len(uniq))
    num = approx_fprime(theta, lambda t: f(t)[0], 1e-6)
    assert np.allclose(f(theta)[1], num, rtol=1e-4, atol=1e-3)


def test_glmm_recovers_random_intercept_sd():
    df = simulated(n_races=500, per_race=10, sigma=1.0, seed=4)
    m = core.fit(core.SPECS["primary_v1"], df, "y")
    assert m.converged
    assert 0.6 < m.sigma < 1.4
    assert m.coefficients().loc[lambda c: c.term == "d23", "estimate"].item() == pytest.approx(0.7, abs=0.3)


def test_baseline_matches_plain_logistic():
    statsmodels = pytest.importorskip("statsmodels.api")
    df = simulated()
    m = core.fit(core.SPECS["baseline_gap_v1"], df, "y")
    X = m.design.matrix(df)
    ref = statsmodels.Logit(df.y, X).fit(disp=0)
    assert np.allclose(m.beta, ref.params, atol=1e-4)


def test_marginal_prediction_shrinks_towards_half():
    df = simulated()
    m = core.fit(core.SPECS["primary_v1"], df, "y")
    eta = m.design.matrix(df) @ m.beta
    p = m.predict(df)
    conditional = 1 / (1 + np.exp(-eta))
    assert np.all(np.abs(p - 0.5) <= np.abs(conditional - 0.5) + 1e-12)


@pytest.mark.parametrize("model", ["baseline_gap_v1", "primary_v1"])
def test_entry_point_on_fake_sample(tmp_path, model):
    out = tmp_path / "pred.csv"
    run = subprocess.run([sys.executable, str(HERE / "fit_predict.py"), "--train", str(FAKE),
                          "--predict", str(FAKE), "--model", model, "--out", str(out)],
                         capture_output=True, text=True)
    fake = pd.read_csv(FAKE)
    # the fake sample spans every split; fitting must refuse anything but train/tune
    if set(fake[fake.in_core == 1].split) - {"train", "tune"}:
        assert run.returncode == 2 and "Training rows" in run.stderr
        train = tmp_path / "train.csv"
        fake[fake.split.eq("train")].to_csv(train, index=False)
        run = subprocess.run([sys.executable, str(HERE / "fit_predict.py"), "--train", str(train),
                              "--predict", str(FAKE), "--model", model, "--out", str(out)],
                             capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    pred = pd.read_csv(out)
    assert set(pred.battle_id) == set(fake[fake.in_core == 1].battle_id)
    assert pred.p_success.between(0, 1).all()
    assert (pred.fitted_on == "train").all()
    check = subprocess.run([sys.executable, str(ROOT / "contracts/check_contract.py"), "predictions", str(out)],
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stdout
