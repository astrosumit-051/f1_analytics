"""Candidate model terms for the 2024 tuning comparison (issue A4, #14).

Usage:
    python pipeline/candidates.py <path to F1_Pit_Wall_2018_2026> [--pairs data/derived/pairs.csv]
        [--out data/derived/tuning_candidates.csv]

Writes one row per pair (battle_id) with two decision-time candidates that the
proposal says enter the model only if they improve the 2024 tuning results:

- recent_pace_diff_sec: chaser minus leader median lap time over laps ref_lap - 2 ..
  ref_lap, using only green (TrackStatus "1"), accurate, undeleted laps that are not
  in- or out-laps. Positive means the chaser has been slower. NA unless both drivers
  have at least 2 such laps.
- track_temp_c: track temperature on the chaser's ref_lap (TrackTemp; the archived
  observation when TrackTemp is missing).

Both are known at the end of ref_lap. Both were selected on 2024 (A4, #14), so
--write-pairs also writes them into `pairs` (contract columns since DECISIONS D-010).
Reads no outcome column.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLS = ["year", "round", "DriverId", "LapNumber", "LapTime_sec", "TrackStatus", "IsAccurate",
        "PitInTime_sec", "PitOutTime_sec", "Deleted", "TrackTemp", "archive_observed_TrackTemp"]
PACE_LAPS = 3
MIN_LAPS = 2


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("data", type=Path)
    cli.add_argument("--pairs", type=Path, default=ROOT / "data/derived/pairs.csv")
    cli.add_argument("--out", type=Path, default=ROOT / "data/derived/tuning_candidates.csv")
    cli.add_argument("--write-pairs", action="store_true",
                     help="also write both columns into pairs.csv in contract order (D-010)")
    a = cli.parse_args(argv)

    laps = pd.read_csv(a.data / "all_laps_enriched.csv", usecols=COLS, dtype={"TrackStatus": str, "DriverId": str},
                       low_memory=False)
    laps["event_id"] = laps["year"].astype(str) + "_" + laps["round"].astype(int).map("{:02d}".format)
    laps["LapNumber"] = laps["LapNumber"].astype(int)
    ok = (laps.TrackStatus.eq("1") & laps.IsAccurate.astype(str).eq("True")
          & ~laps.Deleted.astype(str).eq("True") & laps.PitInTime_sec.isna() & laps.PitOutTime_sec.isna()
          & laps.LapTime_sec.notna())
    laps["pace"] = laps.LapTime_sec.where(ok)
    laps["temp"] = laps.TrackTemp.fillna(laps.archive_observed_TrackTemp)
    idx = laps.set_index(["event_id", "DriverId", "LapNumber"])[["pace", "temp"]]

    pairs = pd.read_csv(a.pairs, usecols=["battle_id", "event_id", "chaser", "leader", "ref_lap"], dtype=str)
    pairs["ref_lap"] = pairs.ref_lap.astype(int)

    def pace(ev, drv, ref):
        keys = [(ev, drv, k) for k in range(ref - PACE_LAPS + 1, ref + 1)]
        v = idx.reindex(keys)["pace"].dropna()
        return v.median() if len(v) >= MIN_LAPS else np.nan

    rows = []
    for r in pairs.itertuples(index=False):
        pc, pl = pace(r.event_id, r.chaser, r.ref_lap), pace(r.event_id, r.leader, r.ref_lap)
        t = idx["temp"].get((r.event_id, r.chaser, r.ref_lap), np.nan)
        rows.append((r.battle_id, round(pc - pl, 3) if np.isfinite(pc) and np.isfinite(pl) else np.nan,
                     round(float(t), 1) if pd.notna(t) else np.nan))
    out = pd.DataFrame(rows, columns=["battle_id", "recent_pace_diff_sec", "track_temp_c"])
    out.to_csv(a.out, index=False, na_rep="NA")
    print(f"wrote {len(out)} rows to {a.out}")
    if a.write_pairs:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from build_pairs import to_contract
        full = pd.read_csv(a.pairs, dtype={"battle_id": str}, keep_default_na=True)
        full = full.drop(columns=[c for c in out.columns[1:] if c in full.columns]).merge(out, on="battle_id", how="left")
        to_contract(full, "pairs").to_csv(a.pairs, index=False, na_rep="NA")
        print(f"wrote recent_pace_diff_sec and track_temp_c into {a.pairs}")
    print("missing share:", out[["recent_pace_diff_sec", "track_temp_c"]].isna().mean().round(3).to_dict())


if __name__ == "__main__":
    main()
