"""Evaluate probability forecasts from the published CSV handoff."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTCOMES = {"success_h0", "success_h3", "success_h5", "success_common_h3"}
FITTED_ON = {"train": "train", "tune": "train", "test": "train+tune", "transfer": "train+tune"}
YEARS = {"train": range(2018, 2024), "tune": (2024,), "test": (2025,), "transfer": (2026,)}


def require_columns(frame, required, label):
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {', '.join(sorted(missing))}")


def read_split(path, split):
    # Parse outcome values only for the requested split.
    chunks = pd.read_csv(path, dtype=str, chunksize=10000)
    return pd.concat([chunk.loc[chunk["split"].eq(split)] for chunk in chunks], ignore_index=True)


def frozen_model_ids(path):
    """A draft freeze note does not unlock the test."""
    if not path.is_file():
        raise ValueError("Locked test requires a model-freeze entry in DECISIONS.md.")
    for block in re.split(r"(?m)^##\s+", path.read_text(encoding="utf-8")):
        heading = block.splitlines()[0] if block else ""
        if not re.search(r"model[ -]freeze|freeze[ -](?:the[ -])?model", heading, re.I):
            continue
        accepted = re.search(r"(?im)^\s*-?\s*status:\s*accepted\s*$", block)
        commit = re.search(r"(?im)^\s*-?\s*commit(?: hash)?:\s*`?([a-f0-9]{40})`?\s*$", block)
        models = re.search(r"(?im)^\s*-?\s*model_ids?:\s*(.+)$", block)
        if accepted and commit and models:
            return set(re.findall(r"[\w.-]+", models.group(1)))
    raise ValueError("Locked test requires an accepted model freeze with model_id and commit hash.")


def score(y, probability):
    # Clipping is only for log loss, which would otherwise be infinite at 0 or 1.
    p = np.clip(probability, 1e-15, 1-1e-15)
    return np.mean((probability-y)**2), -np.mean(y*np.log(p)+(1-y)*np.log1p(-p))


def crossing(gaps, probabilities, threshold):
    """Return a supported downward crossing or explain why it is unavailable."""
    if len(gaps) < 2:
        return np.nan, "insufficient_grid"
    hits = []
    for index in range(len(gaps)-1):
        left, right = probabilities[index:index+2]
        if left >= threshold > right:
            fraction = (left-threshold)/(left-right)
            hits.append(gaps[index]+fraction*(gaps[index+1]-gaps[index]))
    if probabilities[-1] == threshold and probabilities[-2] > threshold:
        hits.append(gaps[-1])
    if len(hits) == 1:
        return hits[0], "crossed"
    status = "multiple_downward_crossings" if hits else "no_downward_crossing"
    return np.nan, status


def prepare_scores(pairs, predictions, baseline_id, split):
    require_columns(pairs, ["battle_id", "event_id", "year", "in_core"], "Pairs")
    require_columns(predictions, ["battle_id", "model_id", "fitted_on", "outcome", "p_success"],
                    "Predictions")
    if pairs.empty or predictions.empty:
        raise ValueError(f"No pairs or predictions for split {split}.")
    if pairs["battle_id"].isna().any() or pairs["battle_id"].duplicated().any():
        raise ValueError("Pairs must have one row per battle_id within a split.")
    if pairs["event_id"].isna().any() or not pairs["in_core"].isin(["0", "1"]).all():
        raise ValueError("Pairs must have race IDs and valid core flags.")
    if not pd.to_numeric(pairs["year"], errors="raise").isin(YEARS[split]).all():
        raise ValueError(f"Pairs contain a year outside the {split} split.")
    keys = ["battle_id", "model_id", "outcome"]
    if predictions[keys].isna().any().any() or predictions.duplicated(keys).any():
        raise ValueError("Predictions must have one row per battle, model and outcome.")
    if not predictions["fitted_on"].eq(FITTED_ON[split]).all():
        raise ValueError(f"Predictions for {split} must be fitted on {FITTED_ON[split]}.")
    if not predictions["outcome"].isin(OUTCOMES).all():
        raise ValueError("Predictions contain an unsupported outcome.")
    predictions = predictions.copy()
    p = pd.to_numeric(predictions["p_success"], errors="raise")
    if not p.between(0, 1).all():
        raise ValueError("Predicted probabilities must be present and in [0, 1].")
    predictions["p_success"] = p
    if not predictions["battle_id"].isin(pairs["battle_id"]).all():
        raise ValueError("Some predictions refer to battles outside the requested pairs split.")
    core = pairs.loc[pairs["in_core"].eq("1")]
    for outcome, rows in predictions.groupby("outcome", sort=True):
        require_columns(core, [outcome], "Pairs")
        if baseline_id not in set(rows["model_id"]):
            raise ValueError(f"Baseline {baseline_id} is missing for {outcome}.")
        wide = rows.pivot(index="battle_id", columns="model_id", values="p_success")
        cohort = core.set_index("battle_id")[["event_id", outcome]].join(wide)
        known = cohort[outcome].notna()
        cohort[outcome] = pd.to_numeric(cohort[outcome], errors="raise")
        if not cohort.loc[known, outcome].isin([0, 1]).all():
            raise ValueError(f"{outcome} must be 0, 1 or missing.")
        complete = cohort[wide.columns].notna().all(axis=1)
        scored = cohort.loc[known & complete].copy()
        if scored.empty:
            raise ValueError(f"No common complete cases for {outcome}.")
        scored[outcome] = scored[outcome].astype(int)
        counts = {"eligible_pairs": len(cohort), "missing_outcome": int((~known).sum()),
                  "missing_prediction_any_model": int((known & ~complete).sum()),
                  "scored_pairs": len(scored), "scored_races": scored["event_id"].nunique()}
        yield outcome, list(wide.columns), scored, counts


def evaluate(pairs, predictions, baseline_id, split):
    metrics, calibration = [], []
    for outcome, models, scored, counts in prepare_scores(pairs, predictions, baseline_id, split):
        y = scored[outcome].to_numpy()
        reference = score(y, scored[baseline_id].to_numpy())
        for model in models:
            p = scored[model].to_numpy()
            brier, log_loss = score(y, p)
            metrics.append({"split": split, "outcome": outcome, "model_id": model, **counts,
                            "brier": brier, "log_loss": log_loss,
                            "brier_minus_baseline": brier-reference[0],
                            "log_loss_minus_baseline": log_loss-reference[1]})
            check = pd.DataFrame({"p": p, "y": y, "race": scored["event_id"].to_numpy()})
            check["bin"] = pd.cut(p, np.linspace(0, 1, 6), include_lowest=True, labels=False) + 1
            for bin_id, rows in check.groupby("bin"):
                calibration.append({"outcome": outcome, "model_id": model, "bin": bin_id,
                                    "n": len(rows), "races": rows["race"].nunique(),
                                    "mean_prediction": rows.p.mean(), "observed_rate": rows.y.mean()})
    return pd.DataFrame(metrics), pd.DataFrame(calibration)


def supported_grid(grid, pairs):
    keys = ["model_id", "outcome", "delay_group", "gap_sec"]
    require_columns(grid, keys+["p_success"], "Window grid")
    require_columns(pairs, ["delay_group", "gap_before_sec"], "Pairs")
    grid = grid.copy()
    grid["gap_sec"] = pd.to_numeric(grid["gap_sec"], errors="raise")
    grid["p_success"] = pd.to_numeric(grid["p_success"], errors="raise")
    if (not grid["p_success"].between(0, 1).all()
        or not grid["gap_sec"].between(0, 6).all() or grid[keys].isna().any().any()
        or grid.duplicated(keys).any()):
        raise ValueError("Window grid has invalid probabilities, gaps or duplicate keys.")
    if not grid["outcome"].isin(OUTCOMES).all() or not grid["delay_group"].isin(["d1","d23"]).all():
        raise ValueError("Window grid has an unsupported outcome or delay group.")
    for (model, outcome, group), rows in grid.groupby(keys[:3], sort=True):
        require_columns(pairs, [outcome], "Pairs")
        sample = pairs.loc[pairs["in_core"].eq("1") & pairs["delay_group"].eq(group)
                           & pairs[outcome].notna(), "gap_before_sec"]
        gaps = pd.to_numeric(sample, errors="raise").dropna()
        keep = rows["gap_sec"].between(gaps.min(), gaps.max()) if not gaps.empty else False
        supported = rows.loc[keep] if not gaps.empty else rows.iloc[0:0]
        yield model, outcome, group, supported.sort_values("gap_sec")


def write_calibration(calibration, out, evidence):
    outcomes = calibration["outcome"].unique()
    fig, axes = plt.subplots(1, len(outcomes), figsize=(5*len(outcomes), 4), squeeze=False)
    for ax, outcome in zip(axes[0], outcomes):
        ax.plot([0, 1], [0, 1], ls="--", color="gray")
        for model, rows in calibration.loc[calibration["outcome"].eq(outcome)].groupby("model_id"):
            ax.scatter(rows["mean_prediction"], rows["observed_rate"], s=15+3*np.sqrt(rows["n"]),
                       label=model)
            for row in rows.itertuples():
                ax.annotate(str(row.n), (row.mean_prediction,row.observed_rate),
                            xytext=(4,4), textcoords="offset points", fontsize=8)
        ax.set(xlim=(0,1), ylim=(0,1), xlabel="Mean predicted probability",
               ylabel="Observed success share", title=outcome)
        ax.legend(fontsize=8)
    fig.suptitle(f"Calibration and bin counts — {evidence}")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def parser():
    root = Path(__file__).resolve().parents[1]
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--pairs", type=Path, required=True)
    cli.add_argument("--predictions", type=Path, required=True)
    cli.add_argument("--window-grid", type=Path)
    cli.add_argument("--baseline", default="baseline_gap_v1")
    cli.add_argument("--split", choices=FITTED_ON, default="train")
    cli.add_argument("--decisions", type=Path, default=root/"DECISIONS.md")
    cli.add_argument("--out", type=Path, required=True)
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    try:
        frozen = frozen_model_ids(args.decisions) if args.split == "test" else None
        pred = read_split(args.predictions, args.split)
        if frozen is not None and not set(pred["model_id"]).issubset(frozen):
            raise ValueError("A test prediction model_id is absent from the accepted freeze.")
        pairs = read_split(args.pairs, args.split)
        metrics, calibration = evaluate(pairs, pred, args.baseline, args.split)
        evidence = "synthetic contract fixture" if (
            pairs["battle_id"].str.contains("fake_", case=False).any()
            or pred["model_id"].str.startswith("FAKE_").any()) else f"{args.split} split"
        crossings = []
        if args.window_grid:
            grid = pd.read_csv(args.window_grid)
            if frozen is not None and not set(grid["model_id"]).issubset(frozen):
                raise ValueError("A test window grid model_id is absent from the accepted freeze.")
            for model, outcome, group, rows in supported_grid(grid, pairs):
                for threshold in (0.50, 0.25):
                    gap, status = crossing(rows["gap_sec"].to_numpy(), rows["p_success"].to_numpy(), threshold)
                    crossings.append({"model_id":model, "outcome":outcome, "delay_group":group,
                                      "threshold":threshold, "crossing_gap_sec":gap, "status":status})
        args.out.mkdir(parents=True, exist_ok=True)
        metrics.assign(evidence=evidence).to_csv(args.out/"metrics.csv", index=False)
        calibration.assign(evidence=evidence).to_csv(args.out/"calibration.csv", index=False)
        write_calibration(calibration, args.out/"calibration.png", evidence)
        if args.window_grid:
            pd.DataFrame(crossings).assign(evidence=evidence).to_csv(args.out/"crossings.csv", index=False)
    except (ValueError, KeyError, OSError) as error:
        cli.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
