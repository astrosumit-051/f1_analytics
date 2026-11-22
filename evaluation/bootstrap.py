"""Refit on whole training races to estimate pointwise window uncertainty."""
from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from evaluate import crossing, read_split, require_columns, score, prepare_scores, manifest

STAND_IN_MODELS = ("FAKE_standin_gap", "FAKE_standin_gap_delay")
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
    failures = []
    for draw in range(resamples):
        selected = rng.choice(race_ids, size=len(race_ids), replace=True)
        # Keep the original race ID and give repeated copies independent group IDs.
        training = pd.concat([races[race].assign(bootstrap_race_id=f"draw_{i}")
                              for i, race in enumerate(selected)], ignore_index=True)
        oob = core.loc[~core["event_id"].isin(selected)]
        if training[outcome].nunique() < 2:
            failures.append({"draw":draw+1,"reason":"one_outcome_class"})
            continue
        try:
            window_predictions, oob_predictions = refit_and_predict(training, grid, oob, models)
            expected = len(grid)*len(models)
            if len(window_predictions)!=expected or not window_predictions.p_success.between(0,1).all():
                raise ValueError("Incomplete or invalid bootstrap window predictions")
            for model in models:
                if len(oob): score(oob[outcome].to_numpy(),oob_predictions[model])
        except (ValueError, RuntimeError, subprocess.SubprocessError) as error:
            failures.append({"draw":draw+1,"reason":str(error)})
            continue
        windows.append(window_predictions.assign(draw=draw+1))
        if len(oob):
            for model in models:
                brier, log_loss = score(oob[outcome].to_numpy(), oob_predictions[model])
                metrics.append({"draw":draw+1, "model_id":model, "brier":brier,
                                "log_loss":log_loss, "oob_pairs":len(oob),
                                "oob_races":oob.event_id.nunique()})
    if not windows:
        raise ValueError("No bootstrap refits had both outcome classes.")
    return pd.concat(windows, ignore_index=True), pd.DataFrame(metrics), pd.DataFrame(failures,columns=["draw","reason"])


def stand_in(outcome):
    """Temporary logistic fits for development while the shared model is pending."""
    def design(table, model, gap_col):
        terms = [np.ones(len(table)), table[gap_col].to_numpy()]
        if model == STAND_IN_MODELS[1]:
            terms.append(table["delay_group"].eq("d23").to_numpy(dtype=float))
        return np.column_stack(terms)

    def refit_and_predict(training, grid, oob, models):
        if not training.battle_id.str.contains("fake",case=False).all():
            raise ValueError("Stand-in is restricted to labelled synthetic data; supply A's entry point for real data.")
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


def command_adapter(command, outcome, timeout=120):
    """Use A's public command (four arguments, plus --outcome per D-009); never import A's internals.

    Grid rows are explicitly synthetic profiles built from training feature medians.
    They are predictions only, never observations. D-006 must be resolved upstream.
    """
    if outcome not in ("success_h3", "success_common_h3"):
        raise ValueError("The command adapter supports success_h3 and, through D-009's --outcome, success_common_h3.")
    # v1 interface for the primary outcome; D-009 adds --outcome for the common-lap fit
    # so its curves come from a model fitted on that outcome, never relabelled.
    extra = [] if outcome == "success_h3" else ["--outcome", outcome]
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):
        raise ValueError("Entry point must be a nonempty JSON list of command arguments.")

    def refit(training, grid, oob, models):
        train=training.copy()
        if "bootstrap_race_id" in train:
            train["event_id"]="bootstrap_"+train.bootstrap_race_id.astype(str)
            train["battle_id"]=train.event_id+":"+train.battle_id.astype(str)
        # Keep exactly the public pairs columns. Repeated races are independent
        # random-intercept groups; duplicate battle identifiers are also renamed.
        train=train.drop(columns=["bootstrap_race_id"],errors="ignore")
        profiles=pd.concat([train.iloc[[0]].copy() for _ in range(len(grid))],ignore_index=True)
        schema=pd.read_csv(Path(__file__).resolve().parents[1]/"contracts/schema.csv")
        for field in schema.loc[schema.table.eq("pairs") & schema.role.eq("feature"),"column"]:
            numeric=pd.to_numeric(training[field],errors="coerce")
            if numeric.notna().any(): profiles[field]=numeric.median()
            else: profiles[field]=training[field].mode().iloc[0] if training[field].notna().any() else np.nan
        profiles["battle_id"]=[f"synthetic_grid_{i}" for i in range(len(grid))]
        profiles["event_id"]="synthetic_grid_new_race"
        profiles["gap_before_sec"]=grid.gap_sec.to_numpy()
        profiles["delay_group"]=grid.delay_group.to_numpy()
        profiles["delay"]=np.where(profiles.delay_group.eq("d1"),1,2)
        profiles["leader_stop_lap"]=pd.to_numeric(profiles.chaser_stop_lap)+profiles.delay
        profiles["ref_lap"]=pd.to_numeric(profiles.chaser_stop_lap)-1
        profiles["comparison_lap"]=profiles.leader_stop_lap+1
        profiles["common_lap"]=pd.to_numeric(profiles.chaser_stop_lap)+4
        profiles["strategy"]=np.where(profiles.delay_group.eq("d1"),"chaser_first_d1","chaser_first_d2")
        for field in schema.loc[schema.table.eq("pairs") & schema.role.eq("outcome"),"column"]:
            profiles[field]=np.nan
        predict=pd.concat([profiles,oob.drop(columns=["bootstrap_race_id"],errors="ignore")],ignore_index=True)
        predict["split"]="train"
        output=[]; oob_predictions={}
        with tempfile.TemporaryDirectory(prefix="f1_refit_") as directory:
            folder=Path(directory); train_path=folder/"train.csv"; predict_path=folder/"predict.csv"
            train.to_csv(train_path,index=False); predict.to_csv(predict_path,index=False)
            for model in models:
                out=folder/"predictions.csv"
                if out.exists(): out.unlink()
                run=subprocess.run(command+["--train",str(train_path),"--predict",str(predict_path),
                    "--model",model,"--out",str(out)]+extra,capture_output=True,text=True,timeout=timeout)
                if run.returncode or not out.is_file():
                    raise RuntimeError(f"Model {model} command failed ({run.returncode}): {run.stderr[-1000:]}")
                result=pd.read_csv(out,dtype=str)
                require_columns(result,["battle_id","model_id","outcome","p_success","split","fitted_on"],"Entry-point output")
                if (result.battle_id.duplicated().any() or set(result.battle_id)!=set(predict.battle_id)
                    or not result.model_id.eq(model).all() or not result.outcome.eq(outcome).all()
                    or not result.fitted_on.eq("train").all() or not result.split.eq("train").all()):
                    raise ValueError("Entry-point output violates IDs, model, outcome or fit provenance.")
                values=pd.to_numeric(result.set_index("battle_id").p_success,errors="raise")
                if not values.between(0,1).all(): raise ValueError("Entry point returned invalid probabilities")
                output.append(grid.assign(model_id=model,outcome=outcome,p_success=values.loc[profiles.battle_id].to_numpy()))
                oob_predictions[model]=values.loc[oob.battle_id].to_numpy()
        return pd.concat(output,ignore_index=True),oob_predictions
    return refit


def metric_intervals(pairs,predictions,baseline,split,resamples,seed):
    """Paired whole-race CIs for fixed predictions, conditional on the fitted model."""
    results=[]
    for outcome,models,scored,counts in prepare_scores(pairs,predictions,baseline,split):
        races=[r for _,r in scored.groupby("event_id")]
        rng=np.random.default_rng(seed)
        draws=[]
        for draw in range(resamples):
            sample=pd.concat([races[i] for i in rng.integers(0,len(races),len(races))])
            ref=score(sample[outcome],sample[baseline])
            for model in models:
                value=score(sample[outcome],sample[model])
                draws.append((model,*value,value[0]-ref[0],value[1]-ref[1]))
        frame=pd.DataFrame(draws,columns=["model_id","brier","log_loss","brier_minus_baseline","log_loss_minus_baseline"])
        for model,rows in frame.groupby("model_id"):
            reference=score(scored[outcome],scored[baseline]); point=score(scored[outcome],scored[model])
            points=dict(zip(frame.columns[1:],[*point,point[0]-reference[0],point[1]-reference[1]]))
            for metric in frame.columns[1:]:
                lo,hi=interval(rows[metric])
                results.append(dict(model_id=model,outcome=outcome,metric=metric,estimate=points[metric],
                    p_lo=lo,p_hi=hi,resamples=resamples,seed=seed,**counts,
                    interval_status="conditional_on_fitted_model" if len(races)>1 else "unsupported_one_race"))
    return pd.DataFrame(results)


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
                              "conditional_gap_lo_sec":lo, "conditional_gap_hi_sec":hi,
                              "interval_status":"conditional_on_crossing" if len(supported)==len(results) else "unstable_missing_crossings",
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
    cli.add_argument("--entry-point-json", help='JSON argv, e.g. ["python","models/fit.py"]')
    cli.add_argument("--model", action="append", help="Repeat for paired model comparisons")
    cli.add_argument("--predictions",type=Path,help="Optional fixed training predictions for paired metric CIs")
    cli.add_argument("--baseline",default="baseline_gap_v1")
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    if args.resamples < 1:
        cli.error("--resamples must be positive")
    try:
        core, missing = training_cases(args.pairs, args.outcome)
        grid = make_grid(core)
        if grid.empty:
            raise ValueError("No grid points fall inside observed training gaps.")
        models=args.model or STAND_IN_MODELS
        refit = command_adapter(json.loads(args.entry_point_json),args.outcome) if args.entry_point_json else stand_in(args.outcome)
        point, _ = refit(core, grid, core.iloc[0:0], models)
        windows, metrics, failures = bootstrap_training(core, args.outcome, grid, refit,
                                                        models, args.resamples, args.seed)
        window, crossings, ranges = summarize(point, windows, metrics)
        evidence = ("synthetic contract fixture" if core["battle_id"].str.contains("fake_", case=False).any()
                    else "historical training data, draft logistic fit")
        args.out.mkdir(parents=True, exist_ok=True)
        window.to_csv(args.out/"window_grid.csv", index=False)
        crossings.to_csv(args.out/"crossing_intervals.csv", index=False)
        ranges.to_csv(args.out/"out_of_bag_intervals.csv", index=False)
        failures.to_csv(args.out/"fitting_failures.csv",index=False)
        metrics.to_csv(args.out/"out_of_bag_draws.csv",index=False)
        if args.predictions:
            metric_intervals(read_split(args.pairs,"train"),read_split(args.predictions,"train"),
                args.baseline,"train",args.resamples,args.seed).to_csv(args.out/"metric_intervals.csv",index=False)
        run = {"evidence":evidence, "split":"train", "outcome":args.outcome, "seed":args.seed,
               "resamples_requested":args.resamples, "missing_outcomes":missing,
               "failed_draws":len(failures), "successful_draws":windows.draw.nunique(),
               "fit_status":"unstable_failures" if len(failures) else "all_refits_succeeded",
               "interval_type":"pointwise percentile, race refits; OOB ranges are variability not test CIs",
               "models":list(models),"entry_point":json.loads(args.entry_point_json) if args.entry_point_json else "synthetic stand-in",
               "scored_pairs":len(core),
               "race_count":core["event_id"].nunique()}
        run.update(manifest([args.pairs,args.predictions]))
        run["window_grid_md5"]=hashlib.md5((args.out/"window_grid.csv").read_bytes()).hexdigest()
        (args.out/"run.json").write_text(json.dumps(run, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(run))
    except (ValueError, KeyError, OSError) as error:
        cli.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
