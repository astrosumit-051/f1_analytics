"""Write data/derived/predictions.csv and window_grid.csv for the A3 models (#11).

    python models/build_outputs.py [--pairs data/derived/pairs.csv] [--out data/derived]
        [--models baseline_gap_v1 primary_v1] [--fit-splits train]

Fits each model on the core training rows, for ``success_h3`` (primary) and
``success_common_h3`` (common-lap curves), and predicts the core rows of the
train and tune splits. Test and transfer rows are never predicted here: that is the
locked test (#19) and the transfer check (#20).

Also writes ``models/output/coefficients.csv`` and ``models/output/fit_summary.csv``.
Prints coefficient tables and fit diagnostics only; it never prints an outcome rate
or a score on tune rows.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core import SPECS, fit  # noqa: E402

ROOT = HERE.parent
GRID_OUTCOMES = ("success_h3", "success_common_h3")


def grid_profile(train_core: pd.DataFrame, gaps: np.ndarray, delay_group: str) -> pd.DataFrame:
    """Gap grid with every other feature at its training-season median (core rows)."""
    prof = pd.DataFrame({"gap_before_sec": gaps, "delay_group": delay_group})
    for col in ("tyre_age_diff", "circuit_pitlane_median_sec", "rejoin_traffic_cars",
                "cars_between_at_ref", "overtaking_difficulty"):
        prof[col] = pd.to_numeric(train_core[col], errors="coerce").median()
    prof["era"] = train_core["era"].mode().iloc[0]
    return prof


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--out", type=Path, default=ROOT / "data/derived")
    cli.add_argument("--models", nargs="+", default=["baseline_gap_v1", "primary_v1"])
    cli.add_argument("--fit-splits", nargs="+", default=["train"], choices=["train", "tune"])
    cli.add_argument("--predict-splits", nargs="+", default=["train", "tune"], choices=["train", "tune"])
    cli.add_argument("--diag", type=Path, default=HERE / "output")
    a = cli.parse_args(argv)

    pairs = pd.read_csv(a.pairs, dtype={"battle_id": str, "event_id": str})
    core = pairs[pairs.in_core.eq(1)]
    train = core[core.split.isin(a.fit_splits)]
    target = core[core.split.isin(a.predict_splits)]
    fitted_on = "+".join(s for s in ("train", "tune") if s in a.fit_splits)
    gaps = np.round(np.arange(1, 61) / 10, 1)

    preds, grids, coefs, summary = [], [], [], []
    for model_id in a.models:
        spec = SPECS[model_id]
        for outcome in GRID_OUTCOMES:
            m = fit(spec, train, outcome)
            preds.append(pd.DataFrame({
                "battle_id": target.battle_id, "model_id": model_id, "outcome": outcome,
                "fitted_on": fitted_on, "split": target.split,
                "p_success": m.predict(target).round(6)}))
            for g in ("d1", "d23"):
                prof = grid_profile(train, gaps, g)
                grids.append(pd.DataFrame({
                    "model_id": model_id, "outcome": outcome, "delay_group": g, "gap_sec": gaps,
                    "p_success": m.predict(prof).round(6), "p_lo": "NA", "p_hi": "NA"}))
            c = m.coefficients().assign(model_id=model_id, outcome=outcome)
            coefs.append(c)
            k = len(m.beta) + int(spec.random_intercept)
            summary.append(dict(model_id=model_id, outcome=outcome, fitted_on=fitted_on,
                                pairs=m.n, races=m.races, parameters=k, loglik=round(m.loglik, 3),
                                aic=round(2 * k - 2 * m.loglik, 3), race_sd=round(m.sigma, 4),
                                converged=m.converged))
            print(f"\n{model_id} / {outcome}: n={m.n} races={m.races} k={k} "
                  f"loglik={m.loglik:.2f} converged={m.converged}")
            print(c[["term", "estimate", "std_error"]].round(3).to_string(index=False))

    a.out.mkdir(parents=True, exist_ok=True)
    a.diag.mkdir(parents=True, exist_ok=True)
    pd.concat(preds).to_csv(a.out / "predictions.csv", index=False)
    pd.concat(grids).to_csv(a.out / "window_grid.csv", index=False)
    pd.concat(coefs).round(6).to_csv(a.diag / "coefficients.csv", index=False)
    pd.DataFrame(summary).to_csv(a.diag / "fit_summary.csv", index=False)
    print(f"\nwrote {a.out / 'predictions.csv'} and {a.out / 'window_grid.csv'}")


if __name__ == "__main__":
    main()
