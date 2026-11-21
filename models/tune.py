"""Choose the final model on the 2024 tuning season (issue A4, #14; label: holdout).

    python models/tune.py [--pairs data/derived/pairs.csv]
        [--candidates data/derived/tuning_candidates.csv] [--out models/output/tuning]

This is the only Partner A script that reads 2024 outcomes. It never reads 2025
(test) or 2026 (transfer) rows: they are dropped before anything else happens.

Selection rule, fixed before the tuning outcomes were scored (committed first):

1. Fit every model on the core training rows (2018-2023), outcome success_h3.
2. Score the core tune rows (2024) that have the outcome, all models on the same
   rows: log loss (primary criterion) and Brier score.
3. A candidate term (era, recent pace difference, track temperature) enters only if
   adding it to primary_v1 lowers BOTH tune log loss and tune Brier. If more than one
   qualifies, all qualifying terms are added together and that combined model must
   again beat every single-term model on log loss; otherwise the best single-term
   model is kept.
4. primary_v1 (or its extension) is chosen over baseline_gap_v1 only if its tune log
   loss is lower. Otherwise the final model is the baseline.
5. Paired whole-race bootstrap intervals (2,000 draws, seed 355) are reported for
   every model-minus-primary_v1 difference. They describe uncertainty; the rule above
   uses point estimates, as fixed in advance.

Teammate sensitivity: refit primary_v1 on training core rows plus training teammate
pairs that otherwise meet the core definition, and compare coefficients and the tune
score on the core tune rows; also score primary_v1 on tune teammate pairs.

Writes, under --out: tune_predictions.csv (predictions contract format), tune_metrics.csv,
tune_differences.csv, teammate_sensitivity.csv, teammate_coefficients.csv,
selection.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from core import CANDIDATES, SPECS, fit  # noqa: E402
from data import load_pairs  # noqa: E402

OUTCOME = "success_h3"
ORDER = ["baseline_gap_v1", "primary_v1", *CANDIDATES]
TERM = {"primary_era_v1": "era", "primary_pace_v1": "recent_pace_diff_sec", "primary_temp_v1": "track_temp_c"}
EPS = 1e-15


def scores(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p)))), float(np.mean((p - y) ** 2))


def paired_bootstrap(frame, models, ref, draws=2000, seed=355):
    rng = np.random.default_rng(seed)
    races = [g for _, g in frame.groupby("event_id")]
    out = {m: [] for m in models}
    for _ in range(draws):
        s = pd.concat([races[i] for i in rng.integers(0, len(races), len(races))])
        y = s[OUTCOME].to_numpy()
        r = scores(y, s[ref].to_numpy())
        for m in models:
            v = scores(y, s[m].to_numpy())
            out[m].append((v[0] - r[0], v[1] - r[1]))
    return {m: np.array(v) for m, v in out.items()}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--candidates", type=Path, default=ROOT / "data/derived/tuning_candidates.csv")
    cli.add_argument("--out", type=Path, default=HERE / "output/tuning")
    a = cli.parse_args(argv)

    pairs = load_pairs(a.pairs, splits=("train", "tune"), candidates=a.candidates)  # never test/transfer
    core = pairs[pairs.in_core.eq(1)]
    train, tune = core[core.split.eq("train")], core[core.split.eq("tune")]
    scored = tune.dropna(subset=[OUTCOME]).copy()
    y = scored[OUTCOME].to_numpy(float)

    fits, preds = {}, []
    for m in ORDER:
        fits[m] = fit(SPECS[m], train, OUTCOME)
        assert fits[m].converged, m
        scored[m] = fits[m].predict(scored)
        preds.append(pd.DataFrame({"battle_id": tune.battle_id, "model_id": m, "outcome": OUTCOME,
                                   "fitted_on": "train", "split": "tune",
                                   "p_success": fits[m].predict(tune).round(6)}))

    metrics = []
    for m in ORDER:
        ll, br = scores(y, scored[m].to_numpy())
        metrics.append(dict(model_id=m, scored_pairs=len(scored), scored_races=scored.event_id.nunique(),
                            missing_outcome=int(tune[OUTCOME].isna().sum()), log_loss=ll, brier=br,
                            mean_prediction=float(scored[m].mean()), observed_rate=float(y.mean())))
    metrics = pd.DataFrame(metrics).set_index("model_id")

    # Selection rule (see docstring).
    p_ll, p_br = metrics.loc["primary_v1", ["log_loss", "brier"]]
    qualifying = [m for m in CANDIDATES if metrics.loc[m, "log_loss"] < p_ll and metrics.loc[m, "brier"] < p_br]
    chosen_primary = "primary_v1"
    if len(qualifying) == 1:
        chosen_primary = qualifying[0]
    elif len(qualifying) > 1:
        from core import Spec
        base = SPECS["primary_v1"]
        num = base.numeric + tuple(TERM[m] for m in qualifying if TERM[m] != "era")
        combo = Spec("primary_combined_v1", numeric=num, delay_terms=True, random_intercept=True,
                     era="primary_era_v1" in qualifying, description="primary_v1 plus " + ", ".join(TERM[m] for m in qualifying))
        SPECS[combo.model_id] = combo
        fits[combo.model_id] = fit(combo, train, OUTCOME)
        scored[combo.model_id] = fits[combo.model_id].predict(scored)
        ll, br = scores(y, scored[combo.model_id].to_numpy())
        metrics.loc[combo.model_id] = dict(scored_pairs=len(scored), scored_races=scored.event_id.nunique(),
                                           missing_outcome=int(tune[OUTCOME].isna().sum()), log_loss=ll, brier=br,
                                           mean_prediction=float(scored[combo.model_id].mean()), observed_rate=float(y.mean()))
        preds.append(pd.DataFrame({"battle_id": tune.battle_id, "model_id": combo.model_id, "outcome": OUTCOME,
                                   "fitted_on": "train", "split": "tune",
                                   "p_success": fits[combo.model_id].predict(tune).round(6)}))
        best_single = min(qualifying, key=lambda m: metrics.loc[m, "log_loss"])
        chosen_primary = combo.model_id if ll < metrics.loc[best_single, "log_loss"] else best_single
    final = chosen_primary if metrics.loc[chosen_primary, "log_loss"] < metrics.loc["baseline_gap_v1", "log_loss"] \
        else "baseline_gap_v1"

    models = list(metrics.index)
    boot = paired_bootstrap(scored, models, "primary_v1")
    diffs = []
    for m in models:
        d = boot[m]
        diffs.append(dict(model_id=m, log_loss_minus_primary=metrics.loc[m, "log_loss"] - p_ll,
                          ll_lo=np.quantile(d[:, 0], .025), ll_hi=np.quantile(d[:, 0], .975),
                          brier_minus_primary=metrics.loc[m, "brier"] - p_br,
                          br_lo=np.quantile(d[:, 1], .025), br_hi=np.quantile(d[:, 1], .975)))

    # Teammate sensitivity.
    tm_rule = (pairs.clean_window.eq(1) & pairs.teammates.eq(1) & pairs.delay.between(1, 3)
               & pairs.gap_before_sec.gt(0) & pairs.gap_before_sec.le(6))
    tm = pairs[tm_rule]
    tm_train, tm_tune = tm[tm.split.eq("train")], tm[tm.split.eq("tune")].dropna(subset=[OUTCOME])
    with_tm = fit(SPECS["primary_v1"], pd.concat([train, tm_train]), OUTCOME)
    sens = [dict(check="primary_v1 fitted with training teammate pairs, scored on core tune",
                 pairs=len(scored), teammate_train_pairs=len(tm_train),
                 log_loss=scores(y, with_tm.predict(scored))[0], brier=scores(y, with_tm.predict(scored))[1])]
    if len(tm_tune):
        yt = tm_tune[OUTCOME].to_numpy(float)
        ll, br = scores(yt, fits["primary_v1"].predict(tm_tune))
        sens.append(dict(check="primary_v1 (core fit) scored on tune teammate pairs", pairs=len(tm_tune),
                         teammate_train_pairs=len(tm_train), log_loss=ll, brier=br,
                         observed_rate=float(yt.mean()), mean_prediction=float(fits["primary_v1"].predict(tm_tune).mean())))
    coef = fits["primary_v1"].coefficients()[["term", "estimate"]].rename(columns={"estimate": "core_only"})
    coef["with_teammates"] = with_tm.coefficients()["estimate"].to_numpy()

    a.out.mkdir(parents=True, exist_ok=True)
    pd.concat(preds).to_csv(a.out / "tune_predictions.csv", index=False)
    metrics.reset_index().round(5).to_csv(a.out / "tune_metrics.csv", index=False)
    pd.DataFrame(diffs).round(5).to_csv(a.out / "tune_differences.csv", index=False)
    pd.DataFrame(sens).round(5).to_csv(a.out / "teammate_sensitivity.csv", index=False)
    coef.round(4).to_csv(a.out / "teammate_coefficients.csv", index=False)
    sel = dict(rule="see models/tune.py docstring", qualifying_terms=[TERM[m] for m in qualifying],
               chosen_primary=chosen_primary, final_model=final, outcome=OUTCOME,
               tune_pairs=len(scored), tune_races=int(scored.event_id.nunique()))
    (a.out / "selection.json").write_text(json.dumps(sel, indent=2) + "\n")
    print(metrics.round(4).to_string())
    print(pd.DataFrame(diffs).round(4).to_string(index=False))
    print(pd.DataFrame(sens).round(4).to_string(index=False))
    print(coef.round(3).to_string(index=False))
    print(json.dumps(sel, indent=2))


if __name__ == "__main__":
    main()
