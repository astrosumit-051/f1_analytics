"""Build reproducible training-only common-lap application figures."""
from __future__ import annotations

import argparse
import json
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.evaluate import read_split, validate_schema, validate_geometry, manifest
from figures.stats import rate_summary

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


OUTCOME = "success_common_h3"
GAP_EDGES = (0, 1, 2, 3, 4, 5, 6)
GAP_LABELS = [f"{lo}–{hi}" for lo, hi in zip(GAP_EDGES[:-1], GAP_EDGES[1:])]
GROUPS = {
    "d1": ("Undercut · 1 lap", "#1d5e85", "o"),
    "d23": ("Undercut · 2–3 laps", "#a34229", "s"),
    "same_lap": ("Same-lap stops", "#63518a", "^"),
    "leader_first": ("Rival stopped first", "#397653", "D"),
}


def validate_grid_provenance(path,grid_path,model):
    if path is None:raise ValueError("Real model curves require --grid-run from the training refit; provenance unavailable.")
    info=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    digest=hashlib.md5(Path(grid_path).read_bytes()).hexdigest()
    if (info.get("split")!="train" or model not in info.get("models",[])
        or info.get("window_grid_md5")!=digest or "synthetic" in info.get("evidence","").lower()):
        raise ValueError("Grid provenance does not match a real training-only refit.")


def read_csv(path, columns, label):
    frame = pd.read_csv(path, dtype=str) if label=="Window grid" else read_split(path,"train")
    missing = set(columns) - set(frame)
    if missing:
        raise ValueError(f"{label} is missing: {', '.join(sorted(missing))}")
    return frame


def eligible_training(frame):
    # Filter out the held-out rows before interpreting any outcome.
    train = frame.loc[frame["split"].eq("train")].copy()
    if train.empty:
        raise ValueError("Input has no training rows.")
    years = pd.to_numeric(train["year"], errors="raise")
    if not years.between(2018, 2023).all():
        raise ValueError("A training row has a year outside 2018–2023.")
    for field in ("clean_window", "teammates"):
        if not train[field].isin(["0", "1"]).all():
            raise ValueError(f"{field} must be 0 or 1.")
    gap = pd.to_numeric(train["gap_before_sec"], errors="raise")
    if not gap.between(0, 10, inclusive="right").all():
        raise ValueError("Expected a positive starting gap through 10 seconds.")
    keep = train["clean_window"].eq("1") & train["teammates"].eq("0") & gap.le(GAP_EDGES[-1])
    return train.loc[keep].assign(gap_before_sec=gap.loc[keep])


def gap_bands(gaps):
    return pd.cut(gaps, GAP_EDGES, labels=GAP_LABELS, right=True)


def summarize_pairs(pairs, resamples=400, seed=355):
    rows = pairs.copy()
    if rows["battle_id"].isna().any() or rows["battle_id"].duplicated().any():
        raise ValueError("Expected a unique battle_id for every eligible training pair.")
    if rows["event_id"].isna().any():
        raise ValueError("Missing training event_id.")
    if not rows["delay_group"].isin(GROUPS).all():
        raise ValueError("Unexpected delay group in eligible training pairs.")
    if not rows["in_core"].isin(["0", "1"]).all():
        raise ValueError("in_core must be 0 or 1.")
    # Honor the producer's core flag for undercuts at rounded gap boundaries.
    is_undercut = rows["delay_group"].isin(["d1", "d23"])
    rows = rows.loc[~is_undercut | rows["in_core"].eq("1")].copy()
    rows[OUTCOME] = pd.to_numeric(rows[OUTCOME], errors="raise")
    if not rows[OUTCOME].dropna().isin([0, 1]).all():
        raise ValueError(f"{OUTCOME} must be 0, 1 or missing.")
    rows["gap_band"] = gap_bands(rows["gap_before_sec"])
    rows["completed_gap"] = rows["gap_before_sec"].where(rows[OUTCOME].notna())
    summary = rows.groupby(["delay_group", "gap_band"], observed=True).agg(
        pairs=("battle_id", "size"),
        completed=(OUTCOME, "count"),
        successes=(OUTCOME, "sum"),
        mean_completed_gap_sec=("completed_gap", "mean"),
    )
    races = rows.loc[rows[OUTCOME].notna()].groupby(
        ["delay_group", "gap_band"], observed=True)["event_id"].nunique()
    summary["completed_races"] = races.reindex(summary.index, fill_value=0)
    summary["missing_outcome"] = summary["pairs"] - summary["completed"]
    # Interrupted cycles have no binary result. Their counts stay visible.
    summary["observed_rate"] = summary["successes"].div(summary["completed"].replace(0, np.nan))
    summary=summary.reset_index()
    bands=rate_summary(rows,["delay_group","gap_band"],OUTCOME,resamples,seed)
    if not bands.empty:
        summary=summary.merge(bands[["delay_group","gap_band","p_lo","p_hi","interval_status",
            "bootstrap_draws","draws_without_observations","seed","status"]],on=["delay_group","gap_band"],validate="one_to_one")
    return summary, rows


def prepare_window(grid, eligible, model):
    exact = grid.loc[grid["outcome"].eq(OUTCOME)].copy()
    models = exact["model_id"].dropna().unique()
    if not model and len(models) > 1:
        raise ValueError("Pass --model when the common-lap grid contains multiple model IDs.")
    model = model or (models[0] if len(models) else None)
    if model is None:
        return exact.iloc[:0], model
    exact = exact.loc[exact["model_id"].eq(model)].copy()
    if exact.empty:
        return exact, model
    if not exact["delay_group"].isin(["d1", "d23"]).all():
        raise ValueError("A window curve has an unsupported delay group.")
    for field in ("gap_sec", "p_success", "p_lo", "p_hi"):
        exact[field] = pd.to_numeric(exact[field], errors="raise")
    if (not exact["gap_sec"].between(0, 6, inclusive="right").all()
        or not exact["p_success"].between(0, 1).all()
        or exact.duplicated(["delay_group", "gap_sec"]).any()):
        raise ValueError("Invalid or duplicate points in the selected window grid.")
    incomplete = exact["p_lo"].isna() ^ exact["p_hi"].isna()
    bands = exact.dropna(subset=["p_lo", "p_hi"])
    if (incomplete.any() or not bands["p_lo"].between(0, 1).all()
        or not bands["p_hi"].between(0, 1).all() or bands["p_lo"].gt(bands["p_hi"]).any()):
        raise ValueError("Expected ordered probability bands or two missing endpoints.")
    # Support is based on complete cases in each delay group, before plotting.
    support = (eligible.loc[eligible[OUTCOME].notna()]
               .groupby("delay_group")["gap_before_sec"].agg(["min", "max"]))
    exact = exact.join(support, on="delay_group")
    inside = exact["gap_sec"].between(exact["min"], exact["max"])
    return exact.loc[inside, grid.columns].sort_values(["delay_group", "gap_sec"]), model


def summarize_no_response(rows):
    keys = ["event_id", "chaser", "leader", "chaser_stop_lap"]
    if rows[keys].isna().any().any() or rows.duplicated(keys).any():
        raise ValueError("Expected one no-response row per race, chaser, rival, and stop lap.")
    return (rows.groupby(gap_bands(rows["gap_before_sec"]), observed=False).size()
            .rename_axis("gap_band").rename("no_response_count").reset_index()
            .assign(eligible_opportunities=pd.NA, no_response_rate=pd.NA,
                    rate_status="pending_denominator"))


def probability_panel(ax, title):
    ax.set(title=title, xlim=(0, 6), ylim=(0, 1), xlabel="Starting gap (s)")
    ax.set_xticks(range(7))
    ax.set_yticks(np.linspace(0, 1, 6), ["0%", "20%", "40%", "60%", "80%", "100%"])
    ax.grid(axis="y", color="#e5e7eb")
    ax.set_axisbelow(True)


def draw_figure(window, summary, no_response, evidence, out):
    fig, (curve, comparison, response) = plt.subplots(1, 3, figsize=(15, 5.9), layout="constrained")
    probability_panel(curve, "Undercut window")
    probability_panel(comparison, "Observed comparison groups")
    curve.set_ylabel("Stayed ahead at all four boundaries")
    for probability in (0.25, 0.50):
        curve.axhline(probability, color="#7b8490", linestyle=":", linewidth=0.8)
    for group, (label, color, marker) in GROUPS.items():
        values = summary.loc[summary["delay_group"].eq(group) & summary["completed"].gt(0)]
        counts = int(values["completed"].sum())
        if counts:
            comparison.scatter(values["mean_completed_gap_sec"], values["observed_rate"],
                               color=color, marker=marker, s=35, label=f"{label} (n={counts})")
            for row in values.dropna(subset=["p_lo","p_hi"]).itertuples():
                comparison.vlines(row.mean_completed_gap_sec,row.p_lo,row.p_hi,color=color,alpha=.5)
        if group not in ("d1", "d23"):
            continue
        grid = window.loc[window["delay_group"].eq(group)]
        if counts:
            curve.scatter(values["mean_completed_gap_sec"], values["observed_rate"], color=color,
                          marker=marker, s=35, label=f"{label} observed", zorder=3)
        if len(grid) >= 2:
            x, y, lo, hi = (grid[k].to_numpy(dtype=float)
                            for k in ("gap_sec", "p_success", "p_lo", "p_hi"))
            curve.plot(x, y, color=color, label=f"{label} fit")
            curve.fill_between(x, lo, hi, color=color, alpha=0.15)
    if not any(window.groupby("delay_group").size() >= 2):
        curve.text(0.5, 0.98, "Common-lap model curve pending", transform=curve.transAxes,
                   va="top", ha="center", fontsize=9)
    has_bands = window[["p_lo", "p_hi"]].notna().all(axis=1).any()
    for ax in (curve, comparison):
        handles, labels = ax.get_legend_handles_labels()
        if ax is curve and has_bands:
            handles.append(Patch(facecolor="#526779", alpha=0.15))
            labels.append("95% bootstrap bands")
        if handles:
            ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.16),
                      fontsize=8, ncol=2, frameon=False)
    counts = no_response["no_response_count"]
    bars = response.bar(GAP_LABELS, counts, color="#48736a")
    response.bar_label(bars, padding=3, fontsize=8)
    response.set(title="Rival no response", xlabel="Starting gap band (s)",
                 ylabel="Observed no-response records")
    response.set_ylim(0, max(1, counts.max())*1.28)
    response.text(0.5, 0.98, "Rate pending an eligible-opportunity denominator",
                  va="top", ha="center", transform=response.transAxes, fontsize=8)
    fig.suptitle(f"F1 undercut window | {evidence}", fontsize=14)
    for kind in ("png", "svg"):
        fig.savefig(out/f"undercut_window.{kind}", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--no-response", type=Path, required=True)
    parser.add_argument("--window-grid", type=Path, required=True, help="Grid from a training-only fit")
    parser.add_argument("--model", help="Model ID to chart if several are available")
    parser.add_argument("--resamples",type=int,default=400)
    parser.add_argument("--seed",type=int,default=355)
    parser.add_argument("--grid-run",type=Path,help="Training-refit run.json for real model curves")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        cohort_columns = ["split", "year", "event_id", "gap_before_sec", "clean_window", "teammates"]
        pairs = read_csv(args.pairs, cohort_columns+["battle_id", "delay_group", "in_core", OUTCOME], "Pairs")
        no_response = read_csv(args.no_response, cohort_columns+["chaser", "leader", "chaser_stop_lap"],
                               "No response")
        grid_columns = ["outcome", "model_id", "delay_group", "gap_sec", "p_success", "p_lo", "p_hi"]
        grid = read_csv(args.window_grid, grid_columns, "Window grid")
        validate_schema(pairs,"pairs"); validate_geometry(pairs)
        validate_schema(no_response,"no_response")
        observations, eligible = summarize_pairs(eligible_training(pairs),args.resamples,args.seed)
        if eligible.empty:
            raise ValueError("No eligible training pairs for the report figure.")
        window, model = prepare_window(grid, eligible, args.model)
        counts = summarize_no_response(eligible_training(no_response))
        fixture_markers = pd.concat([
            eligible["battle_id"].str.contains("fake_", case=False),
            no_response.loc[no_response["split"].eq("train"), "chaser"].str.startswith("fake_", na=False),
        ], ignore_index=True)
        fixture_pairs = fixture_markers.all()
        if ((fixture_markers.any() and not fixture_pairs)
            or ((model or "").startswith("FAKE_") and not fixture_pairs)):
            raise ValueError("Use synthetic pairs and no-response records in a separate run.")
        if fixture_pairs:
            evidence = "Synthetic handoff fixture"
        elif (model or "").startswith("draft_"):
            evidence = "2018–2023 training races · draft fit"
        else:
            evidence = "2018–2023 training races"
        if not fixture_pairs and not window.empty:
            validate_grid_provenance(args.grid_run,args.window_grid,model)
        args.out.mkdir(parents=True, exist_ok=True)
        observations.assign(evidence=evidence).to_csv(args.out/"observed_by_gap.csv", index=False)
        counts.assign(evidence=evidence).to_csv(args.out/"no_response_counts.csv", index=False)
        window.assign(evidence=evidence).to_csv(args.out/"displayed_grid.csv", index=False)
        draw_figure(window, observations, counts, evidence, args.out)
        (args.out/"run.json").write_text(json.dumps(manifest([args.pairs,args.no_response,args.window_grid],
            split="train",evidence=evidence,model=model,seed=args.seed,resamples=args.resamples,
            outcome=OUTCOME,no_response_status="pending_denominator"),indent=2)+"\n",encoding="utf-8")
        print(f"Wrote technical panels from {len(eligible)} training pairs to {args.out}.")
    except (ValueError, OSError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
