"""Fill the decision-time feature and extension columns of `pairs` (issue A2, #10).

Usage:
    python pipeline/features.py <path to F1_Pit_Wall_2018_2026> [--pairs data/derived/pairs.csv]
                                [--rejoin projected|observed]

Run pipeline/build_pairs.py first. This script reads its pairs.csv, adds the
columns below and writes the file back in contract order.

Features (known at the end of ref_lap):
- chaser_tyre_age, leader_tyre_age: TyreLife on ref_lap. tyre_age_diff = chaser - leader.
- cars_between_at_ref: cars crossing the line between the two drivers at the end of ref_lap.
- circuit_pitlane_median_sec: median matched pit-lane time (10 to 60 s) at the circuit
  over training seasons; a circuit with no training race uses its first race.
- overtaking_difficulty: green-flag position gains per car-lap at the circuit over
  training seasons. A lap counts only if every car is on track status 1, nobody has
  an in-lap or out-lap, and the field is the same size as on the lap before (no
  retirement); lap 1 is excluded. Gains are summed over cars, so one pass is one gain.
  Circuits with no training race get the median over training circuits
  (overtaking_imputed = 1).
- rejoin_traffic_cars, measured as DECISIONS D-006 says:
  observed  = cars (any lap count) crossing the line up to 2.0 s ahead of the first
              stopper at the end of the first stopper's out-lap, rival excluded (the
              coverage audit's measure; known only after the stop).
  projected = cars, rival excluded, whose next line crossing after the first stopper's
              crossing at the end of ref_lap is projected (last crossing + last lap time)
              to fall between P - 2 s and P s later, P = circuit_pitlane_median_sec.
              Those are the cars that would be up to 2 s ahead after the stop.
  The first stopper is the chaser when delay >= 0, otherwise the leader.

Extension columns (measured after the decision, extensions 1 to 3 only):
- first_stopper_pitlane_sec and first_stopper_pitlane_excess_sec (minus the race
  median of matched stops). Pit-lane times outside 10 to 60 s (red flags,
  mismatched stops) are left NA and kept out of the race median. The compound roles are filled by build_pairs.py.

The circuit tables use rows with year <= 2023 only. --check rebuilds them with every
2024 to 2026 lap and stop removed and fails if any training circuit's value changes.
This script reads no outcome column.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pairs import ROOT, to_contract  # noqa: E402

LAST_TRAIN_YEAR = 2023
TRAFFIC_WINDOW_SEC = 2.0
LAP_COLS = ["year", "round", "DriverId", "LapNumber", "Time_sec", "LapTime_sec", "TrackStatus",
            "Position", "TyreLife"]


def load(root: Path):
    laps = pd.read_csv(root / "all_laps_enriched.csv", usecols=LAP_COLS,
                       dtype={"TrackStatus": str, "DriverId": str}, low_memory=False)
    laps["event_id"] = laps["year"].astype(str) + "_" + laps["round"].astype(int).map("{:02d}".format)
    laps["LapNumber"] = laps["LapNumber"].astype(int)
    stops = pd.read_csv(root / "all_pit_stops.csv", dtype={"driver_ref": str})
    stops = stops[stops["stop_status"].eq("matched")].copy()
    stops["outlap_number"] = stops["outlap_number"].astype(int)
    catalog = pd.read_csv(root / "completed_race_catalog.csv")
    return laps, stops, catalog


# ---------------------------------------------------------------- circuit tables

def event_overtaking(ev_laps: pd.DataFrame, ev_stops: pd.DataFrame) -> tuple[int, int]:
    """(position gains, car-laps) on eligible green laps of one race."""
    pos = ev_laps.pivot_table(index="LapNumber", columns="DriverId", values="Position")
    green = ev_laps.groupby("LapNumber")["TrackStatus"].apply(lambda s: s.eq("1").all())
    pit_laps = set(ev_stops["stop_lap"]) | set(ev_stops["outlap_number"])
    gains = car_laps = 0
    for k in pos.index:
        if k < 2 or k - 1 not in pos.index or k in pit_laps or not green.get(k, False):
            continue
        prev, cur = pos.loc[k - 1].dropna(), pos.loc[k].dropna()
        if set(prev.index) != set(cur.index):
            continue
        gains += int((prev - cur[prev.index]).clip(lower=0).sum())
        car_laps += len(cur)
    return gains, car_laps


def circuit_tables(laps, stops, catalog) -> pd.DataFrame:
    """Per-circuit pit-lane median and overtaking difficulty from training seasons only."""
    circuit = catalog.set_index("event_id")["circuitRef"]
    years = catalog.set_index("event_id")["year"]
    ms = stops[stops["pitlane_elapsed_sec"].between(10, 60)].assign(
        circuitRef=lambda x: x["event_id"].map(circuit), year=lambda x: x["event_id"].map(years))
    train_ms = ms[ms["year"] <= LAST_TRAIN_YEAR]
    pit = train_ms.groupby("circuitRef")["pitlane_elapsed_sec"].median()
    first_event = catalog.sort_values(["year", "round"]).groupby("circuitRef")["event_id"].first()
    for c, ev in first_event.items():
        if c not in pit.index:
            pit[c] = ms.loc[ms["event_id"].eq(ev), "pitlane_elapsed_sec"].median()

    train_laps = laps[laps["year"] <= LAST_TRAIN_YEAR]
    train_stops = stops[stops["year"] <= LAST_TRAIN_YEAR]
    totals = {}
    for event_id, ev_laps in train_laps.groupby("event_id"):
        g, n = event_overtaking(ev_laps, train_stops[train_stops["event_id"].eq(event_id)])
        c = circuit[event_id]
        tg, tn = totals.get(c, (0, 0))
        totals[c] = (tg + g, tn + n)
    ot = pd.Series({c: g / n for c, (g, n) in totals.items() if n > 0})
    out = pd.DataFrame({"circuit_pitlane_median_sec": pit})
    out["overtaking_difficulty"] = ot
    out["overtaking_imputed"] = out["overtaking_difficulty"].isna().astype(int)
    out["overtaking_difficulty"] = out["overtaking_difficulty"].fillna(ot.median())
    return out


def check_training_only(laps, stops, catalog, table: pd.DataFrame) -> None:
    """Rebuild the circuit table without any post-training rows; training circuits must not change."""
    keep = catalog["year"] <= LAST_TRAIN_YEAR
    again = circuit_tables(laps[laps["year"] <= LAST_TRAIN_YEAR], stops[stops["year"] <= LAST_TRAIN_YEAR],
                           catalog[keep])
    train_circuits = again.index[again["overtaking_imputed"].eq(0)]
    a = table.loc[train_circuits, ["circuit_pitlane_median_sec", "overtaking_difficulty"]]
    b = again.loc[train_circuits, ["circuit_pitlane_median_sec", "overtaking_difficulty"]]
    if not np.allclose(a.to_numpy(), b.to_numpy(), equal_nan=True):
        raise SystemExit("leak check FAILED: a training circuit's value depends on 2024+ data")
    imputed = table.loc[table["overtaking_imputed"].eq(1), "overtaking_difficulty"].unique()
    if len(imputed) and not np.allclose(imputed, b["overtaking_difficulty"].median()):
        raise SystemExit("leak check FAILED: imputed overtaking value is not the training median")
    print(f"leak check passed: {len(train_circuits)} training circuits unchanged with 2024-2026 removed; "
          f"imputed value equals the training median")


# ---------------------------------------------------------------- pair-level features

class Event:
    def __init__(self, ev_laps: pd.DataFrame, ev_stops: pd.DataFrame):
        self.laps = ev_laps.set_index(["DriverId", "LapNumber"]).sort_index()
        self.time_by_lap = ev_laps.pivot_table(index="LapNumber", columns="DriverId", values="Time_sec")
        self.crossings = ev_laps[["DriverId", "Time_sec", "LapTime_sec"]].dropna(subset=["Time_sec"])
        self.stops = ev_stops.set_index(["driver_ref", "stop_lap"])
        plausible = ev_stops["pitlane_elapsed_sec"].where(ev_stops["pitlane_elapsed_sec"].between(10, 60))
        self.race_median_pitlane = float(plausible.median()) if plausible.notna().any() else np.nan

    def val(self, drv, lap, col):
        try:
            return self.laps.at[(drv, lap), col]
        except KeyError:
            return np.nan

    def cars_between(self, a, b, lap):
        if lap not in self.time_by_lap.index:
            return np.nan
        row = self.time_by_lap.loc[lap]
        ta, tb = row.get(a, np.nan), row.get(b, np.nan)
        if not (np.isfinite(ta) and np.isfinite(tb)):
            return np.nan
        lo, hi = min(ta, tb), max(ta, tb)
        others = row.drop(labels=[a, b], errors="ignore").dropna()
        return int(((others > lo) & (others < hi)).sum())

    def observed_traffic(self, drv, lap, exclude):
        if lap not in self.time_by_lap.index:
            return np.nan
        mine = self.time_by_lap.loc[lap].get(drv, np.nan)
        if not np.isfinite(mine):
            return np.nan
        others = self.time_by_lap.drop(columns=[drv, exclude], errors="ignore")
        hits = ((others < mine) & (others >= mine - TRAFFIC_WINDOW_SEC)).any(axis=0)
        return int(hits.sum())

    def projected_traffic(self, drv, lap, exclude, pit_sec):
        t = self.val(drv, lap, "Time_sec")
        if not (np.isfinite(t) and np.isfinite(pit_sec)):
            return np.nan
        x = self.crossings[~self.crossings["DriverId"].isin([drv, exclude]) & (self.crossings["Time_sec"] <= t)]
        last = x.sort_values("Time_sec").groupby("DriverId").last()
        nxt = last["Time_sec"] + last["LapTime_sec"]
        behind_by = (nxt - t).dropna()
        return int(((behind_by >= pit_sec - TRAFFIC_WINDOW_SEC) & (behind_by < pit_sec)).sum())


def add_features(pairs, laps, stops, circuits, rejoin: str) -> pd.DataFrame:
    pairs = pairs.copy()
    pairs = pairs.drop(columns=list(circuits.columns), errors="ignore") \
        .merge(circuits, left_on="circuitRef", right_index=True, how="left")
    cols = {k: [] for k in ["chaser_tyre_age", "leader_tyre_age", "cars_between_at_ref",
                            "rejoin_traffic_cars", "rejoin_observed", "rejoin_projected",
                            "first_stopper_pitlane_sec", "first_stopper_pitlane_excess_sec"]}
    idx = []
    for event_id, grp in pairs.groupby("event_id", sort=False):
        ev = Event(laps[laps["event_id"].eq(event_id)], stops[stops["event_id"].eq(event_id)])
        for i, p in grp.iterrows():
            c, l, r, d = p["chaser"], p["leader"], int(p["ref_lap"]), int(p["delay"])
            first, rival = (c, l) if d >= 0 else (l, c)
            first_stop = int(p["chaser_stop_lap"] if d >= 0 else p["leader_stop_lap"])
            try:
                stop = ev.stops.loc[(first, first_stop)]
                outlap, pitlane = int(stop["outlap_number"]), float(stop["pitlane_elapsed_sec"])
                if not 10 <= pitlane <= 60:  # red-flag or mismatched stop
                    pitlane = np.nan
            except KeyError:
                outlap, pitlane = first_stop + 1, np.nan
            obs = ev.observed_traffic(first, outlap, rival)
            proj = ev.projected_traffic(first, r, rival, p["circuit_pitlane_median_sec"])
            cols["chaser_tyre_age"].append(ev.val(c, r, "TyreLife"))
            cols["leader_tyre_age"].append(ev.val(l, r, "TyreLife"))
            cols["cars_between_at_ref"].append(ev.cars_between(c, l, r))
            cols["rejoin_observed"].append(obs)
            cols["rejoin_projected"].append(proj)
            cols["rejoin_traffic_cars"].append(proj if rejoin == "projected" else obs)
            cols["first_stopper_pitlane_sec"].append(pitlane)
            cols["first_stopper_pitlane_excess_sec"].append(pitlane - ev.race_median_pitlane)
            idx.append(i)
    feats = pd.DataFrame(cols, index=idx)
    for k in feats.columns:
        pairs[k] = feats[k]
    pairs["tyre_age_diff"] = pairs["chaser_tyre_age"] - pairs["leader_tyre_age"]
    return pairs


def summarise(pairs: pd.DataFrame) -> None:
    """Median and missing count of each feature by split (features only, no outcomes)."""
    order = ["train", "tune", "test", "transfer"]
    core = pairs[pairs["in_core"].eq(1)]
    feats = ["gap_before_sec", "chaser_tyre_age", "leader_tyre_age", "tyre_age_diff",
             "cars_between_at_ref", "circuit_pitlane_median_sec", "rejoin_traffic_cars",
             "rejoin_observed", "rejoin_projected", "overtaking_difficulty", "overtaking_imputed",
             "first_stopper_pitlane_sec", "first_stopper_pitlane_excess_sec"]
    for name, df in [("core cohort", core), ("all pairs", pairs)]:
        med = df.groupby("split")[feats].median().T.reindex(columns=order).round(3)
        miss = df.groupby("split")[feats].apply(lambda g: g.isna().sum()).T.reindex(columns=order)
        print(f"\n{name}: median by split")
        print(med)
        print(f"\n{name}: missing by split")
        print(miss)
    print("\ncore cohort era by split")
    print(pd.crosstab(core["era"], core["split"]).reindex(columns=order))
    a, b = core["rejoin_observed"], core["rejoin_projected"]
    ok = a.notna() & b.notna()
    print(f"\nrejoin observed vs projected (core, {ok.sum()} rows): same count in "
          f"{(a[ok] == b[ok]).mean():.1%}; correlation {a[ok].corr(b[ok]):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw", type=Path)
    ap.add_argument("--pairs", type=Path, default=ROOT / "data" / "derived" / "pairs.csv")
    ap.add_argument("--rejoin", choices=["projected", "observed"], required=True,
                    help="rejoin traffic measure; see DECISIONS D-006")
    ap.add_argument("--no-check", action="store_true", help="skip the training-only leak check")
    args = ap.parse_args()
    laps, stops, catalog = load(args.raw)
    circuits = circuit_tables(laps, stops, catalog)
    if not args.no_check:
        check_training_only(laps, stops, catalog, circuits)
    pairs = pd.read_csv(args.pairs, keep_default_na=True, na_values=["NA"])
    pairs = add_features(pairs, laps, stops, circuits, args.rejoin)
    summarise(pairs)
    to_contract(pairs, "pairs").to_csv(args.pairs, index=False, na_rep="NA")


if __name__ == "__main__":
    main()
