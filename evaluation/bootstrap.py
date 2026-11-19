"""Refit on whole training races to estimate pointwise window uncertainty."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from evaluate import crossing, read_split, require_columns, score

STAND_IN_MODELS = ("draft_gap_only", "draft_gap_plus_delay")
GRID_KEYS = ["delay_group", "gap_sec"]
THRESHOLDS = (0.50, 0.25)


def training_cases(path, outcome):
    pairs = read_split(path, "train")
    require_columns(pairs, ["battle_id", "event_id", "in_core", "year", "delay_group",
                            "gap_before_sec", outcome], "Pairs")
    if pairs["battle_id"].isna().any() or pairs["battle_id"].duplicated().any():
        raise ValueError("Training battle IDs must be present and unique.")
    if not pairs["year"].isin([str(year) for year in range(2018, 2024)]).all():
        raise ValueError("The draft bootstrap accepts 2018–2023 training races only.")
    if pairs["event_id"].isna().any() or not pairs["in_core"].isin(["0","1"]).all():
        raise ValueError("Training pairs must have race IDs and valid core flags.")
    core = pairs.loc[pairs.in_core.eq("1")].copy()
    missing = int(core[outcome].isna().sum())
    core = core.dropna(subset=[outcome]).copy()
    core[outcome] = pd.to_numeric(core[outcome], errors="raise")
    if (not core[outcome].isin([0, 1]).all()
        or not core["delay_group"].isin(["d1", "d23"]).all()):
        raise ValueError("Core outcomes must be binary and core delay groups must be d1 or d23.")
    core[outcome] = core[outcome].astype(int)
    core["gap_before_sec"] = pd.to_numeric(core["gap_before_sec"], errors="raise")
    if (not core["gap_before_sec"].between(0, 6, inclusive="both").all()
        or core["gap_before_sec"].eq(0).any()):
        raise ValueError("Core gaps must be present and above zero through six seconds.")
    if core["event_id"].nunique() < 2 or core[outcome].nunique() != 2:
        raise ValueError("At least two races and both outcomes are needed to refit.")
    return core, missing


def make_grid(core, supplied=None):
    """Use the agreed 0.1-second grid inside observed support per delay group."""
    if supplied is None:
        supplied = pd.DataFrame([(g, d/10) for g in ("d1", "d23") for d in range(1, 61)],
                                columns=GRID_KEYS)
    require_columns(supplied, GRID_KEYS, "Grid")
    support = core.groupby("delay_group")["gap_before_sec"].agg(["min", "max"])
    grid = supplied.merge(support, left_on="delay_group", right_index=True, how="inner")
    grid = grid.loc[grid["gap_sec"].between(grid["min"], grid["max"]), GRID_KEYS]
    return grid.drop_duplicates().sort_values(GRID_KEYS).reset_index(drop=True)


def bootstrap_training(core, outcome, grid, refit_and_predict, models, resamples, seed):
    """All models see the same sampled races and the same out-of-bag races."""
    races = {race: rows for race, rows in core.groupby("event_id")}
    race_ids = list(races)
    rng = np.random.default_rng(seed)
    windows = []
    metrics = []
    skipped = 0
    for draw in range(resamples):
        selected = rng.choice(race_ids, size=len(race_ids), replace=True)
        # Keep the original race ID and give repeated copies independent group IDs.
        training = pd.concat([races[race].assign(bootstrap_race_id=f"draw_{i}")
                              for i, race in enumerate(selected)], ignore_index=True)
        oob = core.loc[~core["event_id"].isin(selected)]
        if training[outcome].nunique() < 2:
            skipped += 1
            continue
        window_predictions, oob_predictions = refit_and_predict(training, grid, oob, models)
        windows.append(window_predictions.assign(draw=draw+1))
        if len(oob):
            for model in models:
                brier, log_loss = score(oob[outcome].to_numpy(), oob_predictions[model])
                metrics.append({"draw":draw+1, "model_id":model, "brier":brier,
                                "log_loss":log_loss, "oob_pairs":len(oob),
                                "oob_races":oob.event_id.nunique()})
    if not windows:
        raise ValueError("No bootstrap refits had both outcome classes.")
    return pd.concat(windows, ignore_index=True), pd.DataFrame(metrics), skipped


def stand_in(outcome):
    """Temporary logistic fits for development while the shared model is pending."""
    def design(table, model, gap_col):
        terms = [np.ones(len(table)), table[gap_col].to_numpy()]
        if model == STAND_IN_MODELS[1]:
            terms.append(table["delay_group"].eq("d23").to_numpy(dtype=float))
        return np.column_stack(terms)

    def refit_and_predict(training, grid, oob, models):
        windows, oob_predictions = [], {}
        y = training[outcome].to_numpy()
        for model in models:
            x = design(training, model, "gap_before_sec")

            def loss(beta):
                linear = x @ beta
                return np.sum(np.logaddexp(0, linear)-y*linear), x.T @ (expit(linear)-y)

            fit = minimize(loss, np.zeros(x.shape[1]), jac=True, method="BFGS")
            if not fit.success and np.linalg.norm(fit.jac, ord=np.inf) > 1e-4:
                raise ValueError(f"Stand-in logistic fit failed for {model}: {fit.message}")
            windows.append(grid.assign(model_id=model, outcome=outcome,
                                        p_success=expit(design(grid, model, "gap_sec") @ fit.x)))
            oob_predictions[model] = expit(design(oob, model, "gap_before_sec") @ fit.x)
        return pd.concat(windows, ignore_index=True), oob_predictions

    return refit_and_predict


def interval(values):
    return tuple(np.quantile(values, [0.025, 0.975])) if len(values) else (np.nan, np.nan)


def summarize(point, windows, metrics):
    keys = ["model_id", "outcome"] + GRID_KEYS
    bands = windows.groupby(keys)["p_success"].quantile([.025, .975]).unstack()
    bands.columns = ["p_lo", "p_hi"]
    grid = point.merge(bands.reset_index(), on=keys, validate="one_to_one")
    crossings = []
    for (model, group), observed in point.groupby(["model_id", "delay_group"]):
        draws = windows.loc[windows.model_id.eq(model) & windows.delay_group.eq(group)]
        for threshold in THRESHOLDS:
            point_gap, status = crossing(observed.gap_sec.to_numpy(), observed.p_success.to_numpy(), threshold)
            results = [crossing(rows.gap_sec.to_numpy(), rows.p_success.to_numpy(), threshold)[0]
                       for _, rows in draws.groupby("draw")]
            supported = [gap for gap in results if np.isfinite(gap)]
            lo, hi = interval(supported)
            crossings.append({"model_id":model, "delay_group":group, "threshold":threshold,
                              "crossing_gap_sec":point_gap, "status":status,
                              "conditional_p_lo":lo, "conditional_p_hi":hi,
                              "draws_with_crossing":len(supported), "draws":len(results)})
    ranges = []
    if not metrics.empty:
        for model, sample in metrics.groupby("model_id"):
            for metric in ("brier", "log_loss"):
                lo, hi = interval(sample[metric])
                ranges.append({"model_id":model, "metric":metric, "median_oob":sample[metric].median(),
                              "p_lo":lo, "p_hi":hi, "draws":len(sample)})
    return grid, pd.DataFrame(crossings), pd.DataFrame(ranges)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--pairs", type=Path, required=True)
    cli.add_argument("--outcome", choices=("success_h3", "success_common_h3"), default="success_common_h3")
    cli.add_argument("--resamples", type=int, default=400)
    cli.add_argument("--seed", type=int, default=355)
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    if args.resamples < 1:
        cli.error("--resamples must be positive")
    try:
        core, missing = training_cases(args.pairs, args.outcome)
        grid = make_grid(core)
        if grid.empty:
            raise ValueError("No grid points fall inside observed training gaps.")
        refit = stand_in(args.outcome)
        point, _ = refit(core, grid, core.iloc[0:0], STAND_IN_MODELS)
        windows, metrics, skipped = bootstrap_training(core, args.outcome, grid, refit,
                                                        STAND_IN_MODELS, args.resamples, args.seed)
        window, crossings, ranges = summarize(point, windows, metrics)
        evidence = ("synthetic contract fixture" if core["battle_id"].str.contains("fake_", case=False).any()
                    else "historical training data, draft logistic fit")
        args.out.mkdir(parents=True, exist_ok=True)
        window.to_csv(args.out/"window_grid.csv", index=False)
        crossings.to_csv(args.out/"crossing_intervals.csv", index=False)
        ranges.to_csv(args.out/"out_of_bag_intervals.csv", index=False)
        run = {"evidence":evidence, "split":"train", "outcome":args.outcome, "seed":args.seed,
               "resamples_requested":args.resamples, "missing_outcomes":missing,
               "skipped_one_class_draws":skipped, "scored_pairs":len(core),
               "race_count":core["event_id"].nunique()}
        (args.out/"run.json").write_text(json.dumps(run, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(run))
    except (ValueError, KeyError, OSError) as error:
        cli.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
