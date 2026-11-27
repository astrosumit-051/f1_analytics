"""Frozen inputs for the locked 2025 test (#19) and the 2026 transfer check (#20).

    python models/freeze.py [--pairs data/derived/pairs.csv] [--out data/derived/frozen]
        [--models baseline_gap_v1 final_v1] [--draws 1000] [--seed 355]

Fits each frozen model on the core rows of 2018-2024 (train + tune), one fit per
outcome, and predicts the core rows of every split. Test and transfer rows are read
WITHOUT any outcome column: the columns with role ``outcome`` in contracts/schema.csv
are dropped when the file is read, so no 2025 or 2026 outcome is ever in memory.

Writes, under --out:
- ``predictions.csv``: predictions contract, fitted_on = train+tune.
- ``window_grid.csv``: the grid with p_lo/p_hi filled by a whole-race bootstrap of the
  train+tune races (each draw refits the model; pointwise 2.5/97.5 percentiles).
  Other features are held at their training-season (2018-2023) medians, as the
  contract says.
- ``crossing_intervals.csv``: 50% and 25% crossings with bootstrap ranges and the
  share of draws that never cross (kept separately, as LOCKED_TEST.md asks).
- ``freeze.json``: models, outcomes, seed, draws, row counts and SHA-256 hashes.

Prints coefficients and row counts only, never a score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from build_outputs import grid_profile  # noqa: E402
from core import SPECS, fit  # noqa: E402

OUTCOMES = ("success_h3", "success_common_h3")
GAPS = np.round(np.arange(1, 61) / 10, 1)
FIT_SPLITS = ("train", "tune")
LOCKED_SPLITS = ("test", "transfer")


def outcome_columns() -> list[str]:
    schema = pd.read_csv(ROOT / "contracts/schema.csv")
    return schema.loc[schema.table.eq("pairs") & schema.role.eq("outcome"), "column"].tolist()


def read_pairs(path: Path):
    """Fit rows (train+tune, with outcomes) and locked rows (test+transfer, no outcomes)."""
    header = pd.read_csv(path, nrows=0).columns
    blocked = set(outcome_columns())
    features = [c for c in header if c not in blocked]
    allp = pd.read_csv(path, usecols=features, dtype={"battle_id": str, "event_id": str})
    locked = allp[allp.split.isin(LOCKED_SPLITS) & allp.in_core.eq(1)].copy()
    # Outcomes are parsed only for train/tune file lines; every other line is skipped
    # by the reader itself, so no test or transfer outcome is ever read.
    keep = set((allp.index[allp.split.isin(FIT_SPLITS)] + 1).tolist())  # +1 for the header line
    full = pd.read_csv(path, skiprows=lambda i: i != 0 and i not in keep,
                       dtype={"battle_id": str, "event_id": str})
    assert full.split.isin(FIT_SPLITS).all() and len(full) == len(keep)
    full = full[full.in_core.eq(1)].copy()
    del allp
    assert not set(locked.columns) & blocked
    return full, locked


def crossing(p, thr):
    below = np.nonzero(p < thr)[0]
    if len(below) == 0 or below[0] == 0:
        return np.nan
    i = below[0]
    return float(GAPS[i - 1] + (thr - p[i - 1]) * (GAPS[i] - GAPS[i - 1]) / (p[i] - p[i - 1]))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--out", type=Path, default=ROOT / "data/derived/frozen")
    cli.add_argument("--models", nargs="+", default=["baseline_gap_v1", "final_v1"])
    cli.add_argument("--draws", type=int, default=1000)
    cli.add_argument("--seed", type=int, default=355)
    a = cli.parse_args(argv)

    fit_rows, locked = read_pairs(a.pairs)
    train_only = fit_rows[fit_rows.split.eq("train")]
    target = pd.concat([fit_rows[locked.columns], locked], ignore_index=True)
    races = fit_rows.event_id.unique()
    by_race = {r: g for r, g in fit_rows.groupby("event_id")}
    profiles = {g: grid_profile(train_only, GAPS, g) for g in ("d1", "d23")}

    preds, grids, cross, fails = [], [], [], []
    for model_id in a.models:
        spec = SPECS[model_id]
        for outcome in OUTCOMES:
            m = fit(spec, fit_rows, outcome)
            assert m.converged, (model_id, outcome)
            print(f"\n{model_id} / {outcome}: n={m.n} races={m.races}")
            print(m.coefficients()[["term", "estimate", "std_error"]].round(3).to_string(index=False))
            preds.append(pd.DataFrame({"battle_id": target.battle_id, "model_id": model_id, "outcome": outcome,
                                       "fitted_on": "train+tune", "split": target.split,
                                       "p_success": m.predict(target).round(6)}))
            point = {g: m.predict(profiles[g]) for g in profiles}

            rng = np.random.default_rng([a.seed, a.models.index(model_id), OUTCOMES.index(outcome)])
            draws = {g: [] for g in profiles}
            for d in range(a.draws):
                pick = rng.integers(0, len(races), len(races))
                sample = pd.concat([by_race[races[i]].assign(event_id=f"b{j}") for j, i in enumerate(pick)],
                                   ignore_index=True)
                try:
                    b = fit(spec, sample, outcome)
                    if not b.converged:
                        raise RuntimeError("did not converge")
                except Exception as e:  # recorded, never silently dropped
                    fails.append(dict(model_id=model_id, outcome=outcome, draw=d, reason=str(e)[:200]))
                    continue
                for g in profiles:
                    draws[g].append(b.predict(profiles[g]))

            for g in profiles:
                D = np.array(draws[g])
                grids.append(pd.DataFrame({"model_id": model_id, "outcome": outcome, "delay_group": g,
                                           "gap_sec": GAPS, "p_success": point[g].round(6),
                                           "p_lo": np.quantile(D, .025, axis=0).round(6),
                                           "p_hi": np.quantile(D, .975, axis=0).round(6)}))
                for thr in (.5, .25):
                    c = np.array([crossing(row, thr) for row in D])
                    ok = c[~np.isnan(c)]
                    cross.append(dict(model_id=model_id, outcome=outcome, delay_group=g, threshold=thr,
                                      crossing_gap_sec=crossing(point[g], thr),
                                      lo_sec=np.quantile(ok, .025) if len(ok) else np.nan,
                                      hi_sec=np.quantile(ok, .975) if len(ok) else np.nan,
                                      draws_with_crossing=len(ok), draws=len(D)))

    a.out.mkdir(parents=True, exist_ok=True)
    files = {"predictions": a.out / "predictions.csv", "window_grid": a.out / "window_grid.csv"}
    pd.concat(preds).to_csv(files["predictions"], index=False)
    pd.concat(grids).to_csv(files["window_grid"], index=False)
    pd.DataFrame(cross).round(4).to_csv(a.out / "crossing_intervals.csv", index=False)
    pd.DataFrame(fails, columns=["model_id", "outcome", "draw", "reason"]).to_csv(a.out / "fitting_failures.csv", index=False)
    meta = dict(models=a.models, outcomes=list(OUTCOMES), fitted_on="train+tune", seed=a.seed, draws=a.draws,
                failed_draws=len(fails), fit_pairs=len(fit_rows), fit_races=int(len(races)),
                predicted_rows={s: int(n) for s, n in target.split.value_counts().sort_index().items()},
                grid_profile="training-season (2018-2023) medians",
                sha256={"data/derived/pairs.csv": sha256(a.pairs),
                        **{f"data/derived/frozen/{p.name}": sha256(p) for p in files.values()}})
    (a.out / "freeze.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
