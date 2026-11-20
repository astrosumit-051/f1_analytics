"""Descriptive SC/VSC timing, stratified by exact delay; never fit a new model."""
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
from figures.stats import rate_summary


def prepare(pairs):
    validate_schema(pairs,"pairs");validate_geometry(pairs)
    if not pairs.split.eq("train").all():raise ValueError("Neutralisation development is training-only")
    rows=pairs.copy()
    gap=pd.to_numeric(rows.gap_before_sec,errors="raise")
    for col in ("sc_in_window","vsc_in_window","clean_window","teammates"):
        if not rows[col].isin(["0","1"]).all():raise ValueError("Invalid cohort flag")
    rows=rows.loc[rows.teammates.eq("0") & gap.gt(0) & gap.le(6)].copy()
    sc=rows.sc_in_window.eq("1");vsc=rows.vsc_in_window.eq("1")
    rows["condition"]=np.select([sc&vsc,sc,vsc,rows.clean_window.eq("1")],
        ["SC_and_VSC","SC_only","VSC_only","clean_control"],default="other_unclean")
    rows["delay"]=pd.to_numeric(rows.delay,errors="raise")
    rows["observed_gain_sec"]=pd.to_numeric(rows.gap_before_sec)-pd.to_numeric(rows.signed_gap_comparison_sec,errors="raise")
    return rows


def gain_summary(rows,resamples=400,seed=355):
    if resamples<1:raise ValueError("Resamples must be positive")
    race_ids=sorted(rows.event_id.unique())
    if not race_ids:raise ValueError("No eligible neutralisation rows")
    weights=np.random.default_rng(seed).multinomial(len(race_ids),np.full(len(race_ids),1/len(race_ids)),size=resamples)
    result=[]
    for (condition,delay),group in rows.groupby(["condition","delay"]):
        known=group.dropna(subset=["observed_gain_sec"])
        sums=known.groupby("event_id").observed_gain_sec.agg(["sum","count"]).reindex(race_ids,fill_value=0)
        den=weights@sums["count"].to_numpy()
        draws=np.divide(weights@sums["sum"].to_numpy(),den,out=np.full(resamples,np.nan),where=den>0)
        races=known.event_id.nunique()
        lo,hi=np.nanquantile(draws,[.025,.975]) if races>=2 else (np.nan,np.nan)
        result.append(dict(condition=condition,delay=delay,pairs=len(group),completed=len(known),
            missing_gain=len(group)-len(known),races=races,mean_gain_sec=known.observed_gain_sec.mean(),
            median_gain_sec=known.observed_gain_sec.median(),p_lo_sec=lo,p_hi_sec=hi,
            draws_without_observations=int((den==0).sum()),resamples=resamples,seed=seed,
            interval_status="race_percentile" if races>=2 else "unsupported_fewer_than_two_races",
            status="descriptive; dry status unverified for neutralised rows"))
    return pd.DataFrame(result)


def run(pairs,out,resamples=400,seed=355):
    rows=prepare(pairs);summary=gain_summary(rows,resamples,seed)
    evidence="synthetic fixture" if rows.battle_id.str.contains("fake",case=False).all() else "unmerged training handoff; provisional"
    out.mkdir(parents=True,exist_ok=True)
    summary.assign(evidence=evidence).to_csv(out/"timing_gain.csv",index=False)
    rate_summary(rows,["condition","delay"],"success_common_h3",resamples,seed).assign(
        evidence=evidence).to_csv(out/"common_lap_followup.csv",index=False)
    rows.groupby(["condition","exclusion_reason"],dropna=False).size().rename("pairs").reset_index().to_csv(out/"cohort_counts.csv",index=False)
    fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
    for condition,sub in summary.groupby("condition"):
        ax.scatter(sub.delay,sub.mean_gain_sec,label=condition)
    ax.axhline(0,color="gray",ls=":")
    ax.set(xlabel="Leader stop minus chaser stop (laps)",ylabel="Starting gap minus observed comparison gap (s)",
        title=f"SC/VSC observed timing · {evidence}\nPair-specific endpoint; chosen strategies and conditions are confounded")
    ax.legend(fontsize=8);fig.savefig(out/"neutralisation.png",dpi=150);plt.close(fig)
    return summary


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
