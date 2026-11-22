"""Monte Carlo pit-cycle simulation and one-cycle replays (A7, #24; extension 6).

    python models/simulate.py [--draws 2000] [--outcome success_common_h3] [--out models/output/simulation]

Status: assumption-based. Training seasons only (2018-2023). No 2024-2026 outcome is
read: the pairs file is loaded with ``splits=("train",)`` and the script stops if any
other split gets through.

The model is ``final_v1`` (D-010) plus the first stopper's pit-lane excess over the
race median, the same fit as extension 1 (analysis/extensions/execution), so the
simulation can vary the stop time. It is fitted on the core training pairs for
``success_common_h3`` by default, because the simulation compares rival delays and
every delay must be judged at the same lap (contracts/README.md).

One simulated pit cycle, for a chosen gap g, delay group d and extra pit time e:

1. Draw the model's coefficients and race SD from their sampling distribution
   (multivariate normal at the maximum-likelihood fit, inverse numeric Hessian;
   race SD on the log scale). This is parameter uncertainty.
2. Draw a real training pit cycle and keep its other decision-time features (tyre
   age difference, circuit pit-lane median, projected rejoin traffic, cars between,
   overtaking difficulty, recent pace difference, track temperature). Gap, delay group
   and pit-lane excess are set to the scenario. This is race-situation variety.
3. Draw a race effect z ~ N(0, 1) and set p = expit(x b + sigma z).
4. Draw the outcome as Bernoulli(p).

Repeating that ``--draws`` times per scenario gives the success rate (the mean of p)
and the spread of the probability a pit wall would face. The scenario grid is gap
0.25-6.0 s x delay group d1/d23 x 0-5 s extra over a median stop.

Assumptions (all part of the "assumption-based" label): the fitted excess slope holds
at every gap and delay; a slow stop changes nothing else; the other features are
drawn independently of the gap; the model is the true data-generating process.

Outputs (``--out``):
- ``scenario_grid.csv``  one row per scenario: success rate, p quantiles, share of
  simulated situations where the undercut is favoured (p > 0.5).
- ``season_check.csv``   the training seasons replayed through the simulator with
  their real gap, delay and excess, against the observed training rate by gap band
  (in-sample, descriptive).
- ``replays.json``       a few real training pit cycles for the one-cycle replay.
- ``model.json``         coefficients, design constants, covariance Cholesky factor
  and the training contexts, so the HTML can run the same simulation in the browser.
- ``run.json``           settings and counts.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "models"))
from core import SPECS, fit  # noqa: E402
from data import load_pairs  # noqa: E402

EXCESS = "first_stopper_pitlane_excess_sec"
CLIP = (-2.0, 10.0)  # same as extension 1
GAPS = np.round(np.arange(1, 25) * 0.25, 2)
EXTRA = np.round(np.arange(0, 11) * 0.5, 1)
GROUPS = ("d1", "d23")
STATUS = "assumption-based (training seasons 2018-2023)"


def load_training(pairs: Path) -> pd.DataFrame:
    train = load_pairs(pairs, splits=("train",))
    if set(train["split"].unique()) != {"train"}:
        raise SystemExit("refusing to run: non-training rows loaded")
    train = train[train.in_core.eq(1)].copy()
    train[EXCESS] = train[EXCESS].clip(*CLIP)
    return train


def fit_model(train: pd.DataFrame, outcome: str):
    base = SPECS["final_v1"]
    spec = replace(base, model_id="final_v1+excess", numeric=base.numeric + (EXCESS,))
    m = fit(spec, train, outcome)
    if not m.converged:
        raise SystemExit("model did not converge")
    return m


def param_draws(m, n: int, rng: np.random.Generator):
    """(n, k) coefficient draws and (n,) race SD draws from the MLE's normal approximation."""
    theta = np.append(m.beta, np.log(max(m.sigma, 1e-4)))
    cov = m.cov
    # symmetrise and nudge to positive definite if needed
    cov = (cov + cov.T) / 2
    w, v = np.linalg.eigh(cov)
    cov = (v * np.clip(w, 1e-10, None)) @ v.T
    chol = np.linalg.cholesky(cov)
    draws = theta + rng.standard_normal((n, len(theta))) @ chol.T
    return draws[:, :-1], np.exp(draws[:, -1]), theta, chol


def context_matrix(m, train: pd.DataFrame) -> np.ndarray:
    """Standardised non-scenario features of every training pit cycle (n_ctx, n_numeric - 1)."""
    cols = [c for c in m.design.spec.numeric if c != EXCESS]
    out = []
    for c in cols:
        v = pd.to_numeric(train[c], errors="coerce").fillna(m.design.impute[c]).to_numpy(float)
        out.append((v - m.design.centre[c]) / m.design.scale[c])
    return np.column_stack(out), cols


def scenario_rows(m, gap, group, excess, ctx):
    """Design matrix rows for one scenario across all training contexts."""
    n = len(ctx)
    prof = pd.DataFrame({"gap_before_sec": np.full(n, gap), "delay_group": group})
    for c in m.design.spec.numeric:
        prof[c] = 0.0  # placeholder, overwritten below
    X = m.design.matrix(prof)
    names = m.design.names
    numeric = list(m.design.spec.numeric)
    ctx_cols = [c for c in numeric if c != EXCESS]
    for i, c in enumerate(ctx_cols):
        X[:, names.index(f"{c}_z")] = ctx[:, i]
    X[:, names.index(f"{EXCESS}_z")] = (excess - m.design.centre[EXCESS]) / m.design.scale[EXCESS]
    return X


def simulate_cell(Xc, B, S, ctx_idx, z, u):
    """p and outcomes for one scenario. Xc: (n_ctx, k); B: (n, k); S: (n,)."""
    eta = np.einsum("ij,ij->i", Xc[ctx_idx], B) + S * z
    p = expit(eta)
    return p, (u < p)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--outcome", default="success_common_h3", choices=["success_common_h3", "success_h3"])
    cli.add_argument("--draws", type=int, default=4000)
    cli.add_argument("--seed", type=int, default=20261122)
    cli.add_argument("--out", type=Path, default=ROOT / "models/output/simulation")
    a = cli.parse_args(argv)
    rng = np.random.default_rng(a.seed)

    train = load_training(a.pairs)
    m = fit_model(train, a.outcome)
    ctx, ctx_cols = context_matrix(m, train)
    base_excess = float(train[EXCESS].median())
    n = a.draws

    # Common random numbers across scenarios so the surface is smooth and comparable.
    B, S, theta, chol = param_draws(m, n, rng)
    ctx_idx = rng.integers(0, len(ctx), n)
    z = rng.standard_normal(n)
    u = rng.random(n)

    rows = []
    for g in GROUPS:
        for gap in GAPS:
            for extra in EXTRA:
                Xc = scenario_rows(m, gap, g, min(base_excess + extra, CLIP[1]), ctx)
                p, y = simulate_cell(Xc, B, S, ctx_idx, z, u)
                q = np.quantile(p, [0.05, 0.25, 0.5, 0.75, 0.95])
                rows.append(dict(delay_group=g, gap_sec=gap, extra_pit_sec=extra,
                                 success_rate=y.mean(), mean_p=p.mean(),
                                 p05=q[0], p25=q[1], p50=q[2], p75=q[3], p95=q[4],
                                 share_favoured=(p > 0.5).mean()))
    grid = pd.DataFrame(rows).round(4).assign(draws=n, status=STATUS)

    # Season check: every training pit cycle replayed with its own gap, delay, excess.
    obs = train.dropna(subset=[a.outcome]).copy()
    reps = 200
    Xo = m.design.matrix(obs)
    idx = rng.integers(0, n, reps)
    # one race effect per event and repetition, shared by every pair in that race (as in the fit)
    ev_codes, ev_uniq = pd.factorize(obs["event_id"].astype(str))
    race_z = rng.standard_normal((len(ev_uniq), reps))[ev_codes]
    eta = Xo @ B[idx].T + S[idx] * race_z
    sim_y = rng.random(eta.shape) < expit(eta)
    obs["band"] = pd.cut(obs.gap_before_sec, [0, 1, 2, 3, 4, 5, 6], labels=["0-1", "1-2", "2-3", "3-4", "4-5", "5-6"])
    check = []
    for (dg, band), gi in obs.groupby(["delay_group", "band"], observed=True):
        rates = sim_y[obs.index.get_indexer(gi.index)].mean(axis=0)
        check.append(dict(delay_group=dg, gap_band=band, pairs=len(gi), observed_rate=gi[a.outcome].mean(),
                          simulated_rate=rates.mean(), sim_lo=np.quantile(rates, 0.05), sim_hi=np.quantile(rates, 0.95)))
    check = pd.DataFrame(check).round(4).assign(status="in-sample check, training seasons 2018-2023")

    # One-cycle replays: real training pit cycles, two per (delay group, outcome), spread in gap.
    pick_rng = np.random.default_rng(7)
    replays = []
    pool = obs[obs.recent_pace_diff_sec.notna()]
    for dg in GROUPS:
        for res in (1, 0):
            sub = pool[(pool.delay_group == dg) & (pool[a.outcome] == res)]
            for lo, hi in ((0.3, 2.0), (2.0, 4.5)):
                cand = sub[(sub.gap_before_sec > lo) & (sub.gap_before_sec <= hi)]
                if len(cand) == 0:
                    continue
                r = cand.iloc[pick_rng.integers(0, len(cand))]
                replays.append({
                    "battle_id": r.battle_id, "year": int(r.year), "round": int(r["round"]),
                    "circuit": r.circuitRef, "chaser": r.chaser, "leader": r.leader,
                    "chaser_stop_lap": int(r.chaser_stop_lap), "leader_stop_lap": int(r.leader_stop_lap),
                    "delay": int(r.delay), "delay_group": dg, "gap_before_sec": float(r.gap_before_sec),
                    "pitlane_median_sec": float(r.circuit_pitlane_median_sec),
                    "excess_sec": float(r[EXCESS]),
                    "signed_gap_comparison_sec": float(r.signed_gap_comparison_sec),
                    "outcome": int(res),
                    "model_p": float(m.predict(r.to_frame().T.infer_objects())[0]),
                    "context_z": [float(v) for v in ctx[train.index.get_loc(r.name)]],
                })

    model_json = {
        "model_id": m.spec.model_id, "outcome": a.outcome, "fitted_on": "train", "status": STATUS,
        "names": m.design.names, "beta": m.beta.tolist(), "sigma": m.sigma,
        "theta": theta.tolist(), "chol": chol.tolist(),
        "knots": m.design.knots.tolist(), "gap_centre": m.design.centre["gap"],
        "basis_scale": [3.0] + [10.0] * (m.design.spec.spline_df - 1),
        "excess": {"centre": m.design.centre[EXCESS], "scale": m.design.scale[EXCESS],
                   "median_train": base_excess, "clip": CLIP},
        "context_cols": ctx_cols, "contexts": np.round(ctx, 4).tolist(),
        "pairs": m.n, "races": m.races,
    }

    a.out.mkdir(parents=True, exist_ok=True)
    grid.to_csv(a.out / "scenario_grid.csv", index=False)
    check.to_csv(a.out / "season_check.csv", index=False)
    (a.out / "replays.json").write_text(json.dumps(replays, indent=1) + "\n")
    (a.out / "model.json").write_text(json.dumps(model_json) + "\n")
    (a.out / "run.json").write_text(json.dumps(dict(
        model=m.spec.model_id, outcome=a.outcome, fitted_on="train", pairs=m.n, races=m.races,
        draws_per_scenario=n, scenarios=len(grid), seed=a.seed, median_excess_train=base_excess,
        race_sd=m.sigma, status=STATUS), indent=2) + "\n")
    print(f"fit: {m.n} pairs, {m.races} races, race SD {m.sigma:.3f}")
    print(check.to_string(index=False))
    show = grid[grid.extra_pit_sec.isin([0, 2, 4]) & grid.gap_sec.isin([0.5, 1, 2, 3, 4, 5, 6])]
    print(show.pivot_table(index="gap_sec", columns=["delay_group", "extra_pit_sec"], values="success_rate").to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
