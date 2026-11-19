"""Coverage counts that decide the scope of the undercut-window proposal.

Reconstructs every pit-cycle pair from the combined lap and stop tables (not
from the 354-row export, which is limited to one-lap offsets and gaps up to
3.5 s) and counts how much data each planned comparison would have.

Usage:
    python analysis/coverage/coverage_counts.py <path to F1_Pit_Wall_2018_2026> [output dir]

Inputs (read only): all_laps_enriched.csv, all_pit_stops.csv,
completed_race_catalog.csv, pit_battles_model_ready.csv.

Definitions
-----------
Pair: two drivers in the same race whose matched stops are at most
MAX_DELAY laps apart, with no other stop by either driver in between.

Reference lap r: the lap before the first of the two stops. The gap is the
difference in line-crossing times at the end of lap r. The car behind at r is
the "chaser" and the car ahead is the "leader", whoever stopped first.

Delay d = leader stop lap - chaser stop lap.
    d = +1..+3  chaser stopped first (undercut; d is the rival's delay)
    d = 0       both stopped on the same lap
    d = -1..-3  leader stopped first (chaser stayed out; comparison group)

Censored undercut: the chaser stops at p with a leader within the gap at
p - 1, and the leader makes no stop from p - 3 to p + 3 (stayed out 4+ laps
or never stopped again).

Comparison lap e: the later of the two out-laps. Immediate success: chaser
ahead at e. Sustained success at horizon h: chaser ahead at every lap
boundary e..e+h. A horizon is "clean" when both cars complete e+h with no
further stop and green, dry lap status throughout.

Clean window (approximates the exporter's model_ready rule using lap-level
fields): every lap r..e for both drivers has TrackStatus "1", Rainfall
False, a finite clock, is not deleted or generated, and both old and new
compounds are dry.

Outcome rates are only computed for 2018-2023 (the proposed training
years) so that the tuning and test seasons stay unseen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

MAX_DELAY = 3
MAX_GAP_COUNTED = 10.0
GAP_BINS = [0, 1, 2, 3, 3.5, 4, 5, 6, 8, 10]
DRY = {"SOFT", "MEDIUM", "HARD", "SUPERSOFT", "ULTRASOFT", "HYPERSOFT", "SUPERHARD"}
TRAIN_YEARS = range(2018, 2024)
HORIZONS = (0, 3, 5)
TRAFFIC_WINDOW_SEC = 2.0
SLOW_STOP_MARGIN_SEC = 5.0

LAP_COLS = [
    "year", "round", "DriverId", "Team", "LapNumber", "Time_sec", "TrackStatus",
    "Rainfall", "Compound", "Position", "Deleted", "FastF1Generated", "PitInTime_sec",
    "PitOutTime_sec", "TyreLife",
]


def gap_bin(series: pd.Series) -> pd.Series:
    return pd.cut(series, GAP_BINS, right=True).astype(str)


def strategy_label(d: int) -> str:
    if d > 0:
        return f"chaser_first_d{d}"
    if d == 0:
        return "same_lap"
    return f"leader_first_d{-d}"


def load(root: Path):
    laps = pd.read_csv(root / "all_laps_enriched.csv", usecols=LAP_COLS,
                       dtype={"TrackStatus": str, "DriverId": str}, low_memory=False)
    laps["event_id"] = laps["year"].astype(str) + "_" + laps["round"].astype(int).map("{:02d}".format)
    laps["LapNumber"] = laps["LapNumber"].astype(int)
    rain = laps["Rainfall"].map({True: False, False: True, "True": False, "False": True})
    laps["lap_ok"] = (
        laps["Time_sec"].notna()
        & laps["Deleted"].map({False: True, "False": True}).fillna(False).astype(bool)
        & ~laps["FastF1Generated"].astype(bool)
    )
    laps["green"] = laps["TrackStatus"].eq("1")
    laps["dry"] = rain.fillna(False).astype(bool)
    laps["dry_compound"] = laps["Compound"].isin(DRY)

    stops = pd.read_csv(root / "all_pit_stops.csv", dtype={"driver_ref": str})
    stops = stops[stops["stop_status"].eq("matched")].copy()
    stops["outlap_number"] = stops["outlap_number"].astype(int)
    catalog = pd.read_csv(root / "completed_race_catalog.csv")
    export = pd.read_csv(root / "pit_battles_model_ready.csv")
    return laps, stops, catalog, export


class Event:
    """Lap-indexed lookups for one race."""

    def __init__(self, laps: pd.DataFrame, stops: pd.DataFrame):
        self.laps = laps.set_index(["DriverId", "LapNumber"]).sort_index()
        self.stops = stops
        self.stop_laps = stops.groupby("driver_ref")["stop_lap"].apply(lambda s: sorted(s)).to_dict()
        hardness = ["HYPERSOFT", "ULTRASOFT", "SUPERSOFT", "SOFT", "MEDIUM", "HARD", "SUPERHARD"]
        used = [c for c in hardness if c in set(stops["new_compound"]) | set(stops["old_compound"])]
        names = {1: ["only"], 2: ["softer", "harder"], 3: ["softest", "middle", "hardest"]}
        self.compound_role = dict(zip(used, names.get(len(used), used)))
        self.median_pitlane = float(stops["pitlane_elapsed_sec"].median()) if len(stops) else np.nan
        self.time_by_lap = laps.pivot_table(index="LapNumber", columns="DriverId", values="Time_sec")

    def row(self, drv, lap):
        try:
            return self.laps.loc[(drv, lap)]
        except KeyError:
            return None

    def t(self, drv, lap):
        r = self.row(drv, lap)
        return np.nan if r is None else float(r["Time_sec"])

    def in_pits_at(self, drv, clock):
        s = self.stops[self.stops["driver_ref"].eq(drv)]
        return bool(((s["pit_entry_sec"] <= clock) & (s["pit_exit_sec"] > clock)).any())

    def window_flags(self, drv, lo, hi):
        rows = [self.row(drv, k) for k in range(lo, hi + 1)]
        if any(r is None for r in rows):
            return dict(complete=False, green=False, dry=False, timing_ok=False, sc=False, vsc=False)
        codes = "".join(str(r["TrackStatus"]) for r in rows)
        return dict(
            complete=True,
            sc="4" in codes,
            vsc="6" in codes or "7" in codes,
            green=all(r["green"] for r in rows),
            dry=all(r["dry"] for r in rows),
            timing_ok=all(r["lap_ok"] for r in rows),
        )

    def dry_compounds(self, drv, lo, hi):
        rows = [self.row(drv, k) for k in range(lo, hi + 1)]
        return all(r is not None and r["dry_compound"] for r in rows)

    def other_stop(self, drv, lo, hi, own):
        return any(lo <= s <= hi and s != own for s in self.stop_laps.get(drv, []))

    def cars_close_ahead(self, drv, lap, exclude):
        """Cars crossing the line up to TRAFFIC_WINDOW_SEC before drv at the end of lap."""
        if lap not in self.time_by_lap.index:
            return np.nan
        mine = self.time_by_lap.loc[lap].get(drv, np.nan)
        if not np.isfinite(mine):
            return np.nan
        # Any other car crossing the line in the window, whatever lap it is on.
        others = self.time_by_lap.drop(columns=[drv, exclude], errors="ignore")
        hits = ((others < mine) & (others >= mine - TRAFFIC_WINDOW_SEC)).any(axis=0)
        return int(hits.sum())

    def cars_between(self, a, b, lap):
        row = self.time_by_lap.loc[lap] if lap in self.time_by_lap.index else None
        if row is None:
            return np.nan
        ta, tb = row.get(a, np.nan), row.get(b, np.nan)
        lo, hi = min(ta, tb), max(ta, tb)
        others = row.drop(labels=[a, b], errors="ignore").dropna()
        return int(((others > lo) & (others < hi)).sum())


def build_pairs(laps, stops, catalog):
    circuit = catalog.set_index("event_id")["circuitRef"].to_dict()
    pairs, censored = [], []
    for event_id, ev_laps in laps.groupby("event_id"):
        ev_stops = stops[stops["event_id"].eq(event_id)]
        ev = Event(ev_laps, ev_stops)
        recs = ev_stops[["driver_ref", "stop_lap", "outlap_number", "pitlane_elapsed_sec",
                         "old_compound", "new_compound"]].to_dict("records")
        year = int(ev_laps["year"].iloc[0])
        # Pit-cycle pairs, both stops within MAX_DELAY laps.
        for i, a in enumerate(recs):
            for b in recs[i + 1:]:
                if a["driver_ref"] == b["driver_ref"]:
                    continue
                if abs(a["stop_lap"] - b["stop_lap"]) > MAX_DELAY:
                    continue
                first = min(a["stop_lap"], b["stop_lap"])
                r = first - 1
                if r < 1:
                    continue
                ta, tb = ev.t(a["driver_ref"], r), ev.t(b["driver_ref"], r)
                if not (np.isfinite(ta) and np.isfinite(tb)):
                    continue
                if ev.in_pits_at(a["driver_ref"], ta) or ev.in_pits_at(b["driver_ref"], tb):
                    continue
                chaser, leader = (a, b) if ta > tb else (b, a)
                gap = abs(ta - tb)
                if gap == 0 or gap > MAX_GAP_COUNTED:
                    continue
                c, l = chaser["driver_ref"], leader["driver_ref"]
                d = int(leader["stop_lap"] - chaser["stop_lap"])
                e = int(max(chaser["outlap_number"], leader["outlap_number"]))
                if ev.other_stop(c, r, e, chaser["stop_lap"]) or ev.other_stop(l, r, e, leader["stop_lap"]):
                    continue
                fc, fl = ev.window_flags(c, r, e), ev.window_flags(l, r, e)
                compounds_dry = all(x in DRY for x in [chaser["old_compound"], chaser["new_compound"],
                                                       leader["old_compound"], leader["new_compound"]])
                clean = (fc["complete"] and fl["complete"] and fc["green"] and fl["green"]
                         and fc["dry"] and fl["dry"] and fc["timing_ok"] and fl["timing_ok"]
                         and compounds_dry)
                rc, rl = ev.row(c, r), ev.row(l, r)
                rec = dict(
                    event_id=event_id, year=year, circuitRef=circuit.get(event_id),
                    chaser=c, leader=l, chaser_stop_lap=chaser["stop_lap"],
                    leader_stop_lap=leader["stop_lap"], delay=d, strategy=strategy_label(d),
                    ref_lap=r, comparison_lap=e, gap_before_sec=gap,
                    teammates=bool(rc["Team"] == rl["Team"]),
                    cars_between_at_ref=ev.cars_between(c, l, r),
                    chaser_pitlane_sec=chaser["pitlane_elapsed_sec"],
                    leader_pitlane_sec=leader["pitlane_elapsed_sec"],
                    first_stopper_traffic_on_outlap=ev.cars_close_ahead(
                        c if d >= 0 else l, int((chaser if d >= 0 else leader)["outlap_number"]),
                        exclude=l if d >= 0 else c),
                    chaser_tyre_age=rc["TyreLife"],
                    leader_tyre_age=rl["TyreLife"],
                    clean_window=bool(clean),
                    # Extension flags: everything clean except the named condition.
                    neutralised_window=bool(fc["complete"] and fl["complete"] and fc["dry"] and fl["dry"]
                                            and fc["timing_ok"] and fl["timing_ok"] and compounds_dry
                                            and (fc["sc"] or fl["sc"] or fc["vsc"] or fl["vsc"])),
                    sc_in_window=bool(fc["sc"] or fl["sc"]),
                    vsc_in_window=bool(fc["vsc"] or fl["vsc"]),
                    wet_window=bool(fc["complete"] and fl["complete"] and fc["green"] and fl["green"]
                                    and fc["timing_ok"] and fl["timing_ok"]
                                    and not (fc["dry"] and fl["dry"] and compounds_dry)),
                    chaser_new_compound_role=ev.compound_role.get(chaser["new_compound"], "non_dry"),
                    first_stopper_pitlane_excess_sec=(chaser if d >= 0 else leader)["pitlane_elapsed_sec"]
                    - ev.median_pitlane,
                    battle_id=f"{event_id}:{c}:{chaser['stop_lap']}:{l}:{leader['stop_lap']}",
                )
                # Outcomes and horizon availability.
                for h in HORIZONS:
                    last = e + h
                    ok = True
                    ahead_all = True
                    for k in range(e, last + 1):
                        tc, tl = ev.t(c, k), ev.t(l, k)
                        if not (np.isfinite(tc) and np.isfinite(tl)):
                            ok = False
                            break
                        ahead_all &= tc < tl
                    if ok and h > 0:
                        hc, hl = ev.window_flags(c, e + 1, last), ev.window_flags(l, e + 1, last)
                        ok = (hc["green"] and hl["green"] and hc["dry"] and hl["dry"]
                              and hc["timing_ok"] and hl["timing_ok"]
                              and not ev.other_stop(c, e + 1, last, -1)
                              and not ev.other_stop(l, e + 1, last, -1))
                    rec[f"horizon{h}_available"] = bool(ok)
                    rec[f"success_h{h}"] = bool(ahead_all) if ok else np.nan
                pairs.append(rec)

        # Censored undercuts: leader makes no stop within +-MAX_DELAY of the chaser's stop.
        for a in recs:
            p, c = a["stop_lap"], a["driver_ref"]
            r = p - 1
            if r < 1 or r not in ev.time_by_lap.index:
                continue
            tc = ev.t(c, r)
            if not np.isfinite(tc) or ev.in_pits_at(c, tc):
                continue
            row = ev.time_by_lap.loc[r].drop(labels=[c], errors="ignore").dropna()
            for l, tl in row.items():
                gap = tc - tl
                if not (0 < gap <= MAX_GAP_COUNTED):
                    continue
                if ev.in_pits_at(l, tl):
                    continue
                if any(p - MAX_DELAY <= s <= p + MAX_DELAY for s in ev.stop_laps.get(l, [])):
                    continue
                later = [s for s in ev.stop_laps.get(l, []) if s > p + MAX_DELAY]
                fc = ev.window_flags(c, r, int(a["outlap_number"]))
                fl = ev.window_flags(l, r, int(a["outlap_number"]))
                censored.append(dict(
                    event_id=event_id, year=year, chaser=c, leader=l, chaser_stop_lap=p,
                    gap_before_sec=gap, leader_next_stop=later[0] if later else np.nan,
                    leader_no_further_stop=not later,
                    teammates=bool(ev.row(c, r)["Team"] == ev.row(l, r)["Team"]),
                    clean_window=bool(fc["complete"] and fl["complete"] and fc["green"] and fl["green"]
                                      and fc["dry"] and fl["dry"] and fc["timing_ok"] and fl["timing_ok"]
                                      and a["old_compound"] in DRY and a["new_compound"] in DRY
                                      and ev.dry_compounds(l, r, int(a["outlap_number"]))),
                ))
    return pd.DataFrame(pairs), pd.DataFrame(censored)


def crosstab(df, rows, cols):
    return pd.crosstab(df[rows], df[cols], margins=True, margins_name="total")


def main():
    root = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("analysis/coverage/output")
    out.mkdir(parents=True, exist_ok=True)
    laps, stops, catalog, export = load(root)
    pairs, censored = build_pairs(laps, stops, catalog)
    pairs["gap_bin"] = gap_bin(pairs["gap_before_sec"])
    pairs["tyre_age_diff"] = pairs["chaser_tyre_age"] - pairs["leader_tyre_age"]
    censored["gap_bin"] = gap_bin(censored["gap_before_sec"])
    pairs.to_csv(out / "pit_cycle_pairs.csv", index=False)
    censored.to_csv(out / "censored_undercuts.csv", index=False)

    clean = pairs[pairs["clean_window"]]
    nt = clean[~clean["teammates"]]
    order = ["leader_first_d3", "leader_first_d2", "leader_first_d1", "same_lap",
             "chaser_first_d1", "chaser_first_d2", "chaser_first_d3"]
    tables = {}

    def save(name, tab):
        tables[name] = tab
        tab.to_csv(out / f"{name}.csv")

    save("all_pairs_strategy_by_gap", crosstab(pairs, "gap_bin", "strategy").reindex(columns=order + ["total"]))
    save("clean_pairs_strategy_by_gap", crosstab(clean, "gap_bin", "strategy").reindex(columns=order + ["total"]))
    save("clean_nonteammate_strategy_by_season",
         crosstab(nt, "year", "strategy").reindex(columns=order + ["total"]))
    under = nt[nt["delay"] > 0]
    save("clean_undercuts_delay_by_gap", crosstab(under, "gap_bin", "delay"))
    save("clean_undercuts_delay_by_season", crosstab(under, "year", "delay"))

    # Recommended core scope: clean, non-teammate, rival delay 1-3, gap <= 6 s.
    core = under[under["gap_before_sec"] <= 6].copy()
    core["split"] = np.select(
        [core["year"] <= 2023, core["year"] == 2024, core["year"] == 2025],
        ["train_2018_2023", "tune_2024", "test_2025"], "transfer_2026")
    save("core_scope_delay_by_split", crosstab(core, "split", "delay"))
    save("core_scope_races_by_split", core.groupby("split").agg(
        pairs=("battle_id", "size"), races=("event_id", "nunique"),
        circuits=("circuitRef", "nunique")))
    save("core_scope_pairs_per_circuit", core.groupby("circuitRef").size()
         .describe().round(1).to_frame("pairs_per_circuit"))

    # Is the rival's delay related to tyre state? (decision-time fields only)
    # Data behind candidate extensions (non-teammate, gap <= 6 s, |delay| <= 3).
    base = pairs[~pairs["teammates"] & (pairs["gap_before_sec"] <= 6)]
    neut = base[base["neutralised_window"]].assign(
        condition=lambda x: np.where(x["sc_in_window"], "safety_car", "vsc_only"))
    save("ext_neutralised_by_strategy", crosstab(neut, "condition", "strategy").reindex(columns=order + ["total"]))
    save("ext_neutralised_races", neut.groupby("condition")["event_id"].nunique().to_frame("races"))
    wet = base[base["wet_window"]]
    save("ext_wet_by_strategy", pd.crosstab(wet["year"] >= 0, wet["strategy"]).reindex(columns=order))
    core_all = base[base["clean_window"]]
    save("ext_clean_by_strategy_split", crosstab(core_all.assign(
        split=np.where(core_all["year"] <= 2023, "train", np.where(core_all["year"] == 2024, "tune",
                       np.where(core_all["year"] == 2025, "test", "2026")))), "split", "strategy")
         .reindex(columns=order + ["total"]))
    core_u = core_all[core_all["delay"] > 0]
    save("ext_core_new_compound_role", core_u["chaser_new_compound_role"].value_counts().to_frame("pairs"))
    ex = core_u["first_stopper_pitlane_excess_sec"]
    save("ext_core_execution", pd.Series({
        "pairs": len(core_u), "excess_over_1s": int((ex > 1).sum()),
        "excess_over_2s": int((ex > 2).sum()), "excess_over_5s": int((ex > 5).sum()),
        "iqr_sec": round(float(ex.quantile(0.75) - ex.quantile(0.25)), 2)}).to_frame("value"))

    save("delay_vs_tyre_age", under[under["gap_before_sec"] <= 6].groupby("delay").agg(
        n=("battle_id", "size"),
        leader_tyre_age_median=("leader_tyre_age", "median"),
        chaser_tyre_age_median=("chaser_tyre_age", "median"),
        tyre_age_diff_median=("tyre_age_diff", "median")).round(1))

    # Teammates.
    tm = pairs.groupby(["clean_window", "teammates"]).size().unstack(fill_value=0)
    save("teammate_pairs", tm)

    # Horizon availability for clean non-teammate undercuts, gap <= 6 s.
    u6 = under[under["gap_before_sec"] <= 6]
    hz = u6.groupby("delay")[[f"horizon{h}_available" for h in HORIZONS]].sum()
    hz["pairs"] = u6.groupby("delay").size()
    save("clean_undercut_horizon_availability", hz)

    # Training-year outcome rates by gap bin (one-lap delay, plus all delays).
    tr = under[under["year"].isin(TRAIN_YEARS)]
    rate = tr.groupby(["delay", "gap_bin"]).agg(
        n=("success_h0", "size"),
        n_h0=("success_h0", "count"), success_h0=("success_h0", "mean"),
        n_h3=("success_h3", "count"), success_h3=("success_h3", "mean"),
        n_h5=("success_h5", "count"), success_h5=("success_h5", "mean"),
        races=("event_id", "nunique"),
    ).round(3)
    save("train_years_undercut_success_by_gap", rate)

    # Comparison group: leader-first and same-lap pairs where the chaser ends ahead.
    comp = nt[nt["delay"] <= 0]
    comp_tr = comp[comp["year"].isin(TRAIN_YEARS)]
    save("train_years_comparison_chaser_ahead",
         comp_tr.groupby(["strategy", "gap_bin"]).agg(
             n=("success_h0", "size"), chaser_ahead_h0=("success_h0", "mean"),
             n_h3=("success_h3", "count"), chaser_ahead_h3=("success_h3", "mean")).round(3))

    # Censored undercuts.
    cn = censored[censored["clean_window"] & ~censored["teammates"]]
    save("censored_undercuts_by_gap", crosstab(cn, "gap_bin", "leader_no_further_stop"))

    # Adjacency, traffic, pit loss.
    adj = nt.assign(adjacent=nt["cars_between_at_ref"].eq(0)).groupby("gap_bin")["adjacent"].agg(["size", "mean"]).round(3)
    save("clean_pairs_adjacent_share_by_gap", adj)
    traffic = under.groupby("gap_bin")["first_stopper_traffic_on_outlap"].agg(
        ["count", "mean", lambda s: (s > 0).mean()]).round(3)
    traffic.columns = ["n", "mean_cars_within_2s_ahead", "share_with_any_traffic"]
    save("clean_undercut_rejoin_traffic", traffic)

    ms = stops.merge(catalog[["event_id", "circuitRef"]], on="event_id")
    ms = ms[ms["pitlane_elapsed_sec"].between(10, 60)]
    circ = ms.groupby("circuitRef")["pitlane_elapsed_sec"].agg(["count", "median"]).round(2)
    circ["races"] = ms.groupby("circuitRef")["event_id"].nunique()
    save("pitlane_time_by_circuit", circ.sort_values("median"))
    med = ms.groupby("event_id")["pitlane_elapsed_sec"].transform("median")
    slow = (ms["pitlane_elapsed_sec"] > med + SLOW_STOP_MARGIN_SEC)

    # Reconciliation with the 354-row export.
    mine = set(clean.loc[(clean["delay"] == 1) & (clean["gap_before_sec"] <= 3.5), "battle_id"])
    theirs = set(export["battle_id"])
    recon = pd.Series({
        "export_rows": len(theirs),
        "reconstructed_d1_gap_le_3p5_clean": len(mine),
        "in_both": len(mine & theirs),
        "export_only": len(theirs - mine),
        "reconstruction_only": len(mine - theirs),
    })
    save("reconciliation_with_export", recon.to_frame("count"))

    independence = pd.Series({
        "clean_nonteammate_undercuts_gap_le_6": len(u6),
        "distinct_races": u6["event_id"].nunique(),
        "distinct_chaser_stops": u6[["event_id", "chaser", "chaser_stop_lap"]].drop_duplicates().shape[0],
        "distinct_leader_stops": u6[["event_id", "leader", "leader_stop_lap"]].drop_duplicates().shape[0],
        "matched_stops_10_60s": len(ms),
        "slow_stops_over_event_median_plus_5s": int(slow.sum()),
    })
    save("independence_and_execution", independence.to_frame("count"))

    with pd.option_context("display.width", 200, "display.max_columns", 30):
        for name, tab in tables.items():
            print(f"\n=== {name} ===")
            print(tab)


if __name__ == "__main__":
    main()
