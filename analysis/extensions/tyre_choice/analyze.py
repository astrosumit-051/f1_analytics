"""Extension 3: tyre choice at the stop (issue A6, #16).

    python analysis/extensions/tyre_choice/analyze.py [--base-model final_v1] [--out ...]

Question: does fitting the middle compound rather than the hardest widen the window?

Compound roles are relative to each event (softest / middle / hardest, or softer /
harder at two-compound events), never named compounds across seasons.

Method. On core training rows (2018-2023) where the chaser fitted the hardest or the
middle compound, fit the base model (the A4 choice) plus an indicator for middle,
outcome success_h3, and compare the two curves at training-median features. The
compound fitted is chosen by the team after the decision, so this is an association,
not the effect of switching compounds.

Status labels:
- `counts.csv`: row counts by role and split (all splits; counting rows is allowed).
- `observed_by_role.csv`: descriptive, training seasons. Softest is descriptive only.
- `coefficients.csv`, `curves.csv`, `crossings.csv`: model-based on training seasons
  (in-sample, not evaluated on held-out seasons: this issue is not labelled holdout).
"""
from __future__ import annotations

import argparse
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
ROLE = "chaser_new_compound_role"
GAPS = np.round(np.arange(1, 61) / 10, 1)


def crossing(gaps, p, thr):
    below = np.nonzero(p < thr)[0]
    if len(below) == 0 or below[0] == 0:
        return np.nan
    i = below[0]
    return round(float(gaps[i - 1] + (thr - p[i - 1]) * (gaps[i] - gaps[i - 1]) / (p[i] - p[i - 1])), 2)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--base-model", default="final_v1")
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "output")
    a = cli.parse_args(argv)

    allp = pd.read_csv(a.pairs, usecols=["in_core", "split", ROLE])
    core_all = allp[allp.in_core.eq(1)]
    counts = (core_all.groupby([ROLE, "split"]).size().unstack(fill_value=0)
              .assign(all=lambda d: d.sum(axis=1)).reset_index())
    del allp, core_all

    train = load_pairs(a.pairs, splits=("train",))
    train = train[train.in_core.eq(1)].copy()
    obs = (train.dropna(subset=[OUTCOME])
           .assign(gap_band=lambda d: pd.cut(d.gap_before_sec, [0, 1, 2, 3, 4, 6]))
           .groupby([ROLE, "gap_band"], observed=False)[OUTCOME]
           .agg(pairs="count", successes="sum", rate="mean").reset_index()
           .assign(status=lambda d: np.where(d[ROLE].eq("softest"), "descriptive only, training seasons",
                                             "descriptive, training seasons")))

    sub = train[train[ROLE].isin(["hardest", "middle"])].copy()
    sub["middle"] = sub[ROLE].eq("middle").astype(float)
    base = SPECS[a.base_model]
    spec = replace(base, model_id=f"{a.base_model}+middle", numeric=base.numeric + ("middle",))
    m = fit(spec, sub, OUTCOME)
    assert m.converged

    med = {c: float(pd.to_numeric(sub[c], errors="coerce").median()) for c in base.numeric}
    curves, cross = [], []
    for g in ("d1", "d23"):
        for role, flag in (("hardest", 0.0), ("middle", 1.0)):
            prof = pd.DataFrame({"gap_before_sec": GAPS, "delay_group": g, "era": sub.era.mode().iloc[0],
                                 **med, "middle": flag})
            p = m.predict(prof)
            curves.append(pd.DataFrame({"delay_group": g, "compound_role": role, "gap_sec": GAPS,
                                        "p_success": p.round(4)}))
            cross.append(dict(delay_group=g, compound_role=role, gap_at_50=crossing(GAPS, p, .5),
                              gap_at_25=crossing(GAPS, p, .25)))
    label = "model-based, training seasons (in-sample)"
    coef = m.coefficients().assign(status=label)

    a.out.mkdir(parents=True, exist_ok=True)
    counts.to_csv(a.out / "counts.csv", index=False)
    obs.round(4).to_csv(a.out / "observed_by_role.csv", index=False)
    coef.round(4).to_csv(a.out / "coefficients.csv", index=False)
    pd.concat(curves).assign(status=label).to_csv(a.out / "curves.csv", index=False)
    pd.DataFrame(cross).assign(status=label).to_csv(a.out / "crossings.csv", index=False)
    print(counts.to_string(index=False))
    print(obs.round(3).to_string(index=False))
    print(coef.round(3).tail(4).to_string(index=False), f"\npairs={m.n} races={m.races}")
    print(pd.DataFrame(cross).to_string(index=False))


if __name__ == "__main__":
    main()
