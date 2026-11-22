"""Shared descriptive statistics; rows are weighted equally, races are resampled."""
import numpy as np
import pandas as pd


def rate_summary(rows, groups, outcome, resamples=400, seed=355):
    if resamples<1: raise ValueError("Resamples must be positive")
    rows=rows.copy()
    rows[outcome]=pd.to_numeric(rows[outcome],errors="raise")
    if not rows[outcome].dropna().isin([0,1]).all(): raise ValueError("Nonbinary outcome")
    if rows.event_id.isna().any(): raise ValueError("Missing race ID")
    if rows.empty: return pd.DataFrame()
    race_ids=sorted(rows.event_id.unique())
    weights=np.random.default_rng(seed).multinomial(len(race_ids),np.full(len(race_ids),1/len(race_ids)),size=resamples)
    result=[]
    for key,group in rows.groupby(groups,observed=True,dropna=False):
        key=key if isinstance(key,tuple) else (key,)
        known=group.loc[group[outcome].notna()]
        counts=known.groupby("event_id")[outcome].agg(["sum","count"]).reindex(race_ids,fill_value=0)
        denominators=weights@counts["count"].to_numpy()
        rates=np.divide(weights@counts["sum"].to_numpy(),denominators,
                        out=np.full(resamples,np.nan),where=denominators>0)
        supported=rates[np.isfinite(rates)]
        races=known.event_id.nunique()
        lo,hi=np.quantile(supported,[.025,.975]) if len(supported) and races>=2 else (np.nan,np.nan)
        result.append(dict(zip(groups,key)) | dict(pairs=len(group),completed=len(known),
            missing_outcome=len(group)-len(known),successes=int(known[outcome].sum()),
            completed_races=races,observed_rate=known[outcome].mean(),p_lo=lo,p_hi=hi,
            bootstrap_draws=resamples,draws_without_observations=int((denominators==0).sum()),seed=seed,
            interval_status="race_percentile" if races>=2 else "unsupported_fewer_than_two_races",
            status="descriptive"))
    return pd.DataFrame(result)
