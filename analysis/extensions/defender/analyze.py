"""Descriptive defender comparisons at the agreed common lap; train only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from evaluation.evaluate import read_split,validate_schema,validate_geometry,manifest
from figures.plot_windows import eligible_training,gap_bands
from figures.stats import rate_summary


def defender_rows(pairs):
    rows=eligible_training(pairs)
    rows["delay"]=pd.to_numeric(rows.delay,errors="raise")
    if not rows.delay.isin(range(-3,4)).all():raise ValueError("Defender delay must be -3..3")
    rows["gap_band"]=gap_bands(rows.gap_before_sec)
    for col in ("success_common_h0","success_common_h3"):
        rows[col]=pd.to_numeric(rows[col],errors="raise")
        if not rows[col].dropna().isin([0,1]).all():raise ValueError("Nonbinary common-lap outcome")
    # Complement is valid only for the point-in-time event. Failure to stay ahead
    # at EVERY boundary does not imply the defender stayed ahead throughout.
    rows["chaser_not_ahead_common_h0"]=1-rows.success_common_h0
    return rows


def matched_overlap(rows, left="d1", right="same_lap"):
    """Exact observed overlap by season, gap band and integer tyre-age difference.

    Weight each shared stratum by min(n_left,n_right). No causal interpretation.
    """
    sample=rows.loc[rows.delay_group.isin([left,right])].copy()
    sample["tyre_age_diff"]=pd.to_numeric(sample.tyre_age_diff,errors="raise")
    missing=int(sample[["tyre_age_diff","success_common_h3"]].isna().any(axis=1).sum())
    sample=sample.dropna(subset=["tyre_age_diff","success_common_h3"])
    grouped=sample.groupby(["year","gap_band","tyre_age_diff","delay_group"],observed=True).success_common_h3.agg(["mean","size"])
    means=grouped["mean"].unstack("delay_group").reindex(columns=[left,right])
    counts=grouped["size"].unstack("delay_group").reindex(columns=[left,right])
    overlap=means.dropna()
    weights=counts.loc[overlap.index].min(axis=1)
    return pd.DataFrame([dict(left=left,right=right,common_strata=len(overlap),
        matched_pairs_per_group=int(weights.sum()),missing_matching_or_outcome=missing,
        left_rate=np.average(overlap[left],weights=weights) if weights.sum() else np.nan,
        right_rate=np.average(overlap[right],weights=weights) if weights.sum() else np.nan,
        status="descriptive_overlap_only" if weights.sum() else "unsupported_no_overlap")])


def run(pairs,out,resamples=400,seed=355):
    validate_schema(pairs,"pairs");validate_geometry(pairs)
    rows=defender_rows(pairs)
    if rows.empty:raise ValueError("No eligible defender rows")
    tables=[]
    for outcome in ("success_common_h0","success_common_h3","chaser_not_ahead_common_h0"):
        for groups,level in [(["delay"],"overall"),(["delay","gap_band"],"gap_band")]:
            table=rate_summary(rows,groups,outcome,resamples,seed)
            tables.append(table.assign(outcome=outcome,level=level))
    summary=pd.concat(tables,ignore_index=True)
    out.mkdir(parents=True,exist_ok=True)
    evidence="synthetic fixture" if rows.battle_id.str.contains("fake",case=False).all() else "training observations; producer review pending"
    summary.assign(evidence=evidence).to_csv(out/"defender_rates.csv",index=False)
    pd.concat([matched_overlap(rows,"d1",g) for g in ("d23","same_lap","leader_first")]).assign(
        evidence=evidence).to_csv(out/"matched_overlap.csv",index=False)
    shown=summary.loc[summary.level.eq("overall") & summary.outcome.eq("chaser_not_ahead_common_h0")]
    fig,ax=plt.subplots(figsize=(9,4.8),layout="constrained")
    ax.scatter(shown.delay,shown.observed_rate,color="#205c80")
    for r in shown.dropna(subset=["p_lo","p_hi"]).itertuples():ax.vlines(r.delay,r.p_lo,r.p_hi,color="#205c80")
    for r in shown.itertuples():ax.annotate(f"n={r.completed}",(r.delay,r.observed_rate),xytext=(5,6),textcoords="offset points")
    ax.set(ylim=(0,1),xticks=range(-3,4),xlabel="Leader stop minus chaser stop (laps)",
        ylabel="Chaser not ahead at common lap",title=f"Defender comparisons · {evidence}\n95% race-bootstrap intervals; chosen strategies are not causal effects")
    fig.savefig(out/"defender.png",dpi=150);plt.close(fig)
    return summary,rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--resamples",type=int,default=400);p.add_argument("--seed",type=int,default=355)
    a=p.parse_args()
    try:
        run(read_split(a.pairs,"train"),a.out,a.resamples,a.seed)
        (a.out/"run.json").write_text(json.dumps(manifest([a.pairs],split="train",status="descriptive",
            seed=a.seed,resamples=a.resamples),indent=2)+"\n")
    except (ValueError,OSError,KeyError) as e:p.exit(2,str(e)+"\n")


if __name__=="__main__":main()
