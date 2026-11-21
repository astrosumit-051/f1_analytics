"""Extension 1: pit-stop time tolerance (issue A5, #15).

    python analysis/extensions/execution/analyze.py [--base-model final_v1] [--out ...]

Question: how many extra seconds in the pit lane close the undercut window, at each
gap and rival delay?

Method. Fit the base model (the A4 choice) plus one term for the first stopper's
pit-lane excess over the race median (`first_stopper_pitlane_excess_sec`, an
extension column, measured after the decision) on the core training rows
(2018-2023), outcome success_h3. The excess is clipped to [-2, 10] s so a handful of
very slow stops (up to 26 s) do not set the slope. Then predict on a grid of
gap x delay group x extra seconds (0 to 6 s), other features at training medians,
and find for each gap and delay the extra time at which the predicted probability
falls below 50% and 25%.

Status labels (proposal, Extensions section):
- `observed_by_excess.csv`: descriptive, training seasons.
- `tolerance_grid.csv`, `tolerance.csv`, `coefficients.csv`: assumption-based. They
  assume the fitted excess slope holds at every gap and delay (no interaction) and
  that a slower stop does not change anything else.
No 2024-2026 outcome is read (this issue is not labelled holdout).

Counts check: the issue expects 98 core pairs with excess > 2 s (coverage audit).
`counts.csv` reports the pipeline's count and explains the difference: the audit's
race median used every matched stop, the pipeline drops implausible pit-lane times
(outside 10-60 s) before taking the median.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "models"))
from core import SPECS, fit  # noqa: E402
from data import load_pairs  # noqa: E402

OUTCOME = "success_h3"
EXCESS = "first_stopper_pitlane_excess_sec"
CLIP = (-2.0, 10.0)
GAPS = np.round(np.arange(1, 13) * 0.5, 1)
EXTRA = np.round(np.arange(0, 61) * 0.1, 1)


def medians(train, spec):
    return {c: float(pd.to_numeric(train[c], errors="coerce").median()) for c in spec.numeric if c != EXCESS}


def first_crossing(extra, p, threshold):
    below = np.nonzero(p < threshold)[0]
    if len(below) == 0:
        return np.nan, "not_closed_within_6s"
    i = below[0]
    if i == 0:
        return 0.0, "already_below"
    x0, x1, y0, y1 = extra[i - 1], extra[i], p[i - 1], p[i]
    return round(float(x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)), 2), "crossed"


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--base-model", default="final_v1")
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "output")
    a = cli.parse_args(argv)

    allp = load_pairs(a.pairs, splits=("train", "tune", "test", "transfer"))
    core_all = allp[allp.in_core.eq(1)]
    counts = pd.DataFrame([
        dict(measure="core pairs", value=len(core_all)),
        dict(measure="core pairs, excess > 2 s (pipeline race median, 10-60 s stops)",
             value=int((core_all[EXCESS] > 2).sum())),
        dict(measure="coverage audit figure (race median over all matched stops)", value=98),
        *[dict(measure=f"core pairs, excess > 2 s, split {s}", value=int((g[EXCESS] > 2).sum()))
          for s, g in core_all.groupby("split")],
    ])
    del allp, core_all  # only row counts were taken from non-training splits

    train = load_pairs(a.pairs, splits=("train",))
    train = train[train.in_core.eq(1)].copy()
    train[EXCESS] = train[EXCESS].clip(*CLIP)

    base = SPECS[a.base_model]
    spec = replace(base, model_id=f"{a.base_model}+excess", numeric=base.numeric + (EXCESS,))
    m = fit(spec, train, OUTCOME)
    assert m.converged

    # Descriptive: observed training success by excess band.
    obs = train.dropna(subset=[OUTCOME]).assign(
        excess_band=pd.cut(train[EXCESS], [-np.inf, 0, 1, 2, 5, np.inf],
                           labels=["<=0 s", "0-1 s", "1-2 s", "2-5 s", ">5 s"]))
    observed = (obs.groupby(["delay_group", "excess_band"], observed=False)[OUTCOME]
                .agg(pairs="count", successes="sum", rate="mean").reset_index()
                .assign(status="descriptive, training seasons 2018-2023"))

    med = medians(train, spec)
    base_excess = float(train[EXCESS].median())
    rows, tol = [], []
    for g in ("d1", "d23"):
        for gap in GAPS:
            prof = pd.DataFrame({"gap_before_sec": gap, "delay_group": g, "era": train.era.mode().iloc[0],
                                 **med, EXCESS: np.minimum(base_excess + EXTRA, CLIP[1])})
            p = m.predict(prof)
            rows.append(pd.DataFrame({"delay_group": g, "gap_sec": gap, "extra_sec": EXTRA, "p_success": p.round(4)}))
            for thr in (0.5, 0.25):
                x, status = first_crossing(EXTRA, p, thr)
                tol.append(dict(delay_group=g, gap_sec=gap, threshold=thr, p_at_median_stop=round(float(p[0]), 4),
                                extra_sec_to_close=x, status=status))
    grid = pd.concat(rows).assign(status="assumption-based")
    tolerance = pd.DataFrame(tol).assign(status="assumption-based")
    coef = m.coefficients().assign(status="assumption-based (training fit)")

    a.out.mkdir(parents=True, exist_ok=True)
    counts.to_csv(a.out / "counts.csv", index=False)
    observed.round(4).to_csv(a.out / "observed_by_excess.csv", index=False)
    grid.to_csv(a.out / "tolerance_grid.csv", index=False)
    tolerance.to_csv(a.out / "tolerance.csv", index=False)
    coef.round(4).to_csv(a.out / "coefficients.csv", index=False)
    (a.out / "run.json").write_text(json.dumps(dict(
        base_model=a.base_model, outcome=OUTCOME, fitted_on="train", pairs=m.n, races=m.races,
        excess_clip=CLIP, median_excess_train=base_excess,
        excess_coef_per_sd=float(coef.loc[coef.term == f"{EXCESS}_z", "estimate"].item()),
        excess_sd=m.design.scale[EXCESS]), indent=2) + "\n")
    print(counts.to_string(index=False))
    print(observed.round(3).to_string(index=False))
    print(coef.round(3).to_string(index=False))
    print(tolerance.pivot_table(index="gap_sec", columns=["delay_group", "threshold"],
                                values="extra_sec_to_close").to_string())


if __name__ == "__main__":
    main()
