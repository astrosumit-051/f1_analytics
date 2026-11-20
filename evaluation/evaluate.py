"""Evaluate probability forecasts from the published CSV handoff."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import csv
import hashlib
import json
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTCOMES = {"success_h0", "success_h3", "success_h5", "success_common_h3"}
FITTED_ON = {"train": "train", "tune": "train", "test": "train+tune", "transfer": "train+tune"}
YEARS = {"train": range(2018, 2024), "tune": (2024,), "test": (2025,), "transfer": (2026,)}


def validate_schema(frame, table):
    """Validate the selected split only, using the shared schema without editing it."""
    schema = pd.read_csv(Path(__file__).resolve().parents[1]/"contracts/schema.csv").fillna("")
    spec = schema.loc[schema.table.eq(table)]
    require_columns(frame, spec.column, table)
    if set(frame)-set(spec.column):
        raise ValueError(f"{table} contains columns outside the shared contract.")
    for row in spec.itertuples():
        values = frame[row.column]
        present = values.dropna()
        if row.type in ("int","float"):
            nums = pd.to_numeric(present, errors="raise")
            if not np.isfinite(nums).all() or (row.type=="int" and (nums%1 != 0).any()):
                raise ValueError(f"{row.column} needs finite {row.type} values.")
            match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:-|\.\.)(-?\d+(?:\.\d+)?)",row.allowed)
            if match and not nums.between(float(match[1]),float(match[2])).all():
                raise ValueError(f"{row.column} outside {row.allowed}.")
        elif row.type in ("enum","bool01"):
            if not present.astype(str).isin(row.allowed.split("|")).all():
                raise ValueError(f"Invalid {row.column} category.")
        if row.role=="id" and values.isna().any():
            raise ValueError(f"Missing {row.column} identifier.")


def validate_geometry(pairs):
    """Check agreed clocks/signs without recomputing any outcomes."""
    for field in ("delay","chaser_stop_lap","leader_stop_lap","ref_lap","comparison_lap","common_lap"):
        require_columns(pairs,[field],"Pairs")
    c,l,d = (pd.to_numeric(pairs[x],errors="raise") for x in ("chaser_stop_lap","leader_stop_lap","delay"))
    if (not d.eq(l-c).all() or not pd.to_numeric(pairs.ref_lap).eq(np.minimum(c,l)-1).all()
        or not pd.to_numeric(pairs.comparison_lap).eq(np.maximum(c,l)+1).all()
        or not pd.to_numeric(pairs.common_lap).eq(c+4).all()):
        raise ValueError("Stop delays or reference/comparison/common laps contradict the contract.")
    if "success_h0" in pairs and "signed_gap_comparison_sec" in pairs:
        known = pairs.success_h0.notna() & pairs.signed_gap_comparison_sec.notna()
        if not pd.to_numeric(pairs.loc[known,"success_h0"]).eq(
            pd.to_numeric(pairs.loc[known,"signed_gap_comparison_sec"]).lt(0).astype(int)).all():
            raise ValueError("Immediate success disagrees with signed chaser-minus-leader gap.")


def require_columns(frame, required, label):
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {', '.join(sorted(missing))}")


def read_split(path, split):
    """Select rows as strings before interpreting outcomes. Never parse other splits."""
    if split not in YEARS:
        raise ValueError(f"Unsupported split: {split}")
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames or []
        if "split" not in names or len(names) != len(set(names)):
            raise ValueError("CSV needs unique headers including split.")
        rows = []
        for row in reader:
            if None in row or None in row.values():
                raise ValueError("Malformed CSV row length.")
            if row["split"] not in YEARS:
                raise ValueError("CSV has an unknown split.")
            if "year" in row and row["year"] not in {str(y) for y in YEARS[row["split"]]}:
                raise ValueError("CSV year and split disagree.")
            if row["split"] == split:
                rows.append(row)
    return pd.DataFrame(rows, columns=names).replace({"":np.nan, "NA":np.nan})


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
    y, probability = np.asarray(y, dtype=float), np.asarray(probability, dtype=float)
    if (y.ndim != 1 or y.shape != probability.shape or not len(y)
        or not np.isin(y, [0,1]).all() or not np.isfinite(probability).all()
        or np.any((probability < 0) | (probability > 1))):
        raise ValueError("Scoring requires equal nonempty binary outcomes and probabilities in [0,1].")
    # Clipping is only for log loss, which would otherwise be infinite at 0 or 1.
    p = np.clip(probability, 1e-15, 1-1e-15)
    return np.mean((probability-y)**2), -np.mean(y*np.log(p)+(1-y)*np.log1p(-p))


def crossing(gaps, probabilities, threshold):
    """Return a supported downward crossing or explain why it is unavailable."""
    gaps, probabilities = np.asarray(gaps, dtype=float), np.asarray(probabilities, dtype=float)
    if (gaps.shape != probabilities.shape or gaps.ndim != 1
        or not np.isfinite(gaps).all() or not np.isfinite(probabilities).all()
        or np.any(np.diff(gaps) <= 0) or not 0 < threshold < 1
        or np.any((probabilities<0) | (probabilities>1))):
        raise ValueError("Crossings need ordered unique gaps and finite probabilities.")
    if len(gaps) < 2:
        return np.nan, "insufficient_grid"
    hits = []
    if np.all(probabilities == threshold):
        return np.nan, "flat_at_threshold"
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
    require_columns(pairs, ["battle_id", "event_id", "year", "split", "in_core", "gap_before_sec"], "Pairs")
    require_columns(predictions, ["battle_id", "model_id", "fitted_on", "outcome", "p_success"],
                    "Predictions")
    require_columns(predictions, ["split"], "Predictions")
    if not pairs["split"].eq(split).all() or not predictions["split"].eq(split).all():
        raise ValueError("Filter to one requested split before scoring.")
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
    gaps = pd.to_numeric(core["gap_before_sec"], errors="raise")
    if not ((gaps > 0) & (gaps <= 6)).all():
        raise ValueError("Core starting gaps must be positive and at most six seconds.")
    for column, value in (("clean_window","1"),("teammates","0")):
        if column in core and not core[column].eq(value).all():
            raise ValueError(f"Core cohort contradicts {column}.")
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
            bins = check.groupby("bin").agg(n=("y","size"), p=("p","mean"), y=("y","mean"))
            metrics[-1].update(mean_prediction=float(p.mean()), observed_rate=float(y.mean()),
                               calibration_bias=float(p.mean()-y.mean()),
                               ece_5_bins=float((bins.n * abs(bins.p-bins.y)).sum()/len(check)),
                               evaluation_status="in_sample" if split=="train" else "held_out")
            for bin_id, rows in check.groupby("bin"):
                calibration.append({"outcome": outcome, "model_id": model, "bin": bin_id,
                                    "n": len(rows), "races": rows["race"].nunique(),
                                    "mean_prediction": rows.p.mean(), "observed_rate": rows.y.mean()})
    return pd.DataFrame(metrics), pd.DataFrame(calibration)


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(paths, **metadata):
    return {"inputs_sha256":{str(p):fingerprint(p) for p in paths if p is not None},
            "python":platform.python_version(), "numpy":np.__version__,
            "pandas":pd.__version__, **metadata}


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
    cli.add_argument("--holdout-issue", type=int, help="14 authorizes tuning in the labelled model-selection issue")
    cli.add_argument("--decisions", type=Path, default=root/"DECISIONS.md")
    cli.add_argument("--out", type=Path, required=True)
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    try:
        if args.split in ("test", "transfer"):
            raise ValueError("Protected split: use the separately authorized locked-test/transfer runner; no input opened.")
        if args.split == "tune" and args.holdout_issue != 14:
            raise ValueError("Tuning outcomes require --holdout-issue 14; no input opened.")
        frozen = frozen_model_ids(args.decisions) if args.split == "test" else None
        pred = read_split(args.predictions, args.split)
        if frozen is not None and not set(pred["model_id"]).issubset(frozen):
            raise ValueError("A test prediction model_id is absent from the accepted freeze.")
        pairs = read_split(args.pairs, args.split)
        validate_schema(pairs,"pairs")
        validate_geometry(pairs)
        validate_schema(pred,"predictions")
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
        if "exclusion_reason" in pairs:
            pairs.groupby(["in_core","exclusion_reason"],dropna=False).size().rename("pairs").reset_index().to_csv(
                args.out/"cohort_counts.csv",index=False)
        write_calibration(calibration, args.out/"calibration.png", evidence)
        if args.window_grid:
            pd.DataFrame(crossings).assign(evidence=evidence).to_csv(args.out/"crossings.csv", index=False)
        (args.out/"run.json").write_text(json.dumps(manifest(
            [args.pairs,args.predictions,args.window_grid], split=args.split,
            evidence=evidence, baseline=args.baseline, holdout_issue=args.holdout_issue,
            log_loss_clip=1e-15, calibration_bins=5), indent=2)+"\n", encoding="utf-8")
    except (ValueError, KeyError, OSError) as error:
        cli.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
