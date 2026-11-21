"""Build the `pairs` and `no_response` handoff tables (issue A1, #9).

Usage:
    python pipeline/build_pairs.py <path to F1_Pit_Wall_2018_2026> [--out data/derived]

Reads all_laps_enriched.csv, all_pit_stops.csv and completed_race_catalog.csv from
the raw snapshot (never committed) and writes data/derived/pairs.csv and
data/derived/no_response.csv with the columns of contracts/schema.csv.

The pair rebuild follows analysis/coverage/coverage_counts.py; the definitions are in
contracts/README.md. Choices this script makes that the contract leaves open:

- exclusion_reason is the first failing check in this order: incomplete (a lap row
  is missing for either driver in ref_lap..comparison_lap), non_green, wet, timing,
  non_dry_compound.
- horizon3_status is the first failing check over comparison_lap+1..comparison_lap+3
  in this order: retired (a driver's race ends before the last lap), stop (another
  stop by either driver), neutralised, wet, missing_timing. The comparison lap
  itself only needs a line-crossing time for both drivers. The same rule decides
  whether success_h5 is missing.
- success_common_h0 and success_common_h3 use the same rule over
  comparison_lap+1..common_lap+h, so a stop, neutralisation, rain or missing lap
  anywhere between the comparison lap and the end of the follow-up makes them NA.

Of the feature and extension columns, only gap_before_sec, era, overtaking_imputed
and the two compound-role columns are filled here (the contract does not allow
those enums blank); issue A2 (#10) fills the rest. A compound outside the event's
dry compounds gets the role non_dry; with more than three dry compounds at an event
the role is the compound name itself.

This script prints row counts only. It never prints outcome rates, so it is safe
to run on every split.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "schema.csv"

MAX_DELAY = 3
MAX_GAP_SEC = 10.0
CORE_MAX_GAP_SEC = 6.0
COMMON_OFFSET = MAX_DELAY + 1
DRY = {"SOFT", "MEDIUM", "HARD", "SUPERSOFT", "ULTRASOFT", "HYPERSOFT", "SUPERHARD"}
HARDNESS = ["HYPERSOFT", "ULTRASOFT", "SUPERSOFT", "SOFT", "MEDIUM", "HARD", "SUPERHARD"]
LAP_COLS = [
    "year", "round", "DriverId", "Team", "LapNumber", "Time_sec", "TrackStatus",
    "Rainfall", "Compound", "Deleted", "FastF1Generated", "TyreLife",
]


def split_of(year: int) -> str:
    if year <= 2023:
        return "train"
    return {2024: "tune", 2025: "test"}.get(year, "transfer")


def strategy_label(d: int) -> str:
    if d > 0:
        return f"chaser_first_d{d}"
    return "same_lap" if d == 0 else f"leader_first_d{-d}"


def delay_group(d: int) -> str:
    if d == 1:
        return "d1"
    if d > 1:
        return "d23"
    return "same_lap" if d == 0 else "leader_first"


def load(root: Path):
    laps = pd.read_csv(root / "all_laps_enriched.csv", usecols=LAP_COLS,
                       dtype={"TrackStatus": str, "DriverId": str}, low_memory=False)
    laps["event_id"] = laps["year"].astype(str) + "_" + laps["round"].astype(int).map("{:02d}".format)
    laps["LapNumber"] = laps["LapNumber"].astype(int)
    laps["lap_ok"] = (
        laps["Time_sec"].notna()
        & laps["Deleted"].map({False: True, "False": True}).fillna(False).astype(bool)
        & ~laps["FastF1Generated"].astype(bool)
    )
    laps["green"] = laps["TrackStatus"].eq("1")
    laps["dry"] = laps["Rainfall"].map({True: False, False: True, "True": False, "False": True}) \
        .fillna(False).astype(bool)
    stops = pd.read_csv(root / "all_pit_stops.csv", dtype={"driver_ref": str})
    stops = stops[stops["stop_status"].eq("matched")].copy()
    stops["outlap_number"] = stops["outlap_number"].astype(int)
    catalog = pd.read_csv(root / "completed_race_catalog.csv")
    return laps, stops, catalog


class Event:
    """Lap-indexed lookups for one race."""

    def __init__(self, laps: pd.DataFrame, stops: pd.DataFrame):
        self.laps = laps.set_index(["DriverId", "LapNumber"]).sort_index()
        self.stops = stops
        self.stop_laps = stops.groupby("driver_ref")["stop_lap"].apply(sorted).to_dict()
        self.last_lap = laps.groupby("DriverId")["LapNumber"].max().to_dict()
        self.time_by_lap = laps.pivot_table(index="LapNumber", columns="DriverId", values="Time_sec")
        used = [c for c in HARDNESS if c in set(stops["new_compound"]) | set(stops["old_compound"])]
        names = {1: ["only"], 2: ["softer", "harder"], 3: ["softest", "middle", "hardest"]}
        self.compound_role = dict(zip(used, names.get(len(used), used)))

    def row(self, drv, lap):
        try:
            return self.laps.loc[(drv, lap)]
        except KeyError:
            return None

    def t(self, drv, lap) -> float:
        r = self.row(drv, lap)
        return np.nan if r is None else float(r["Time_sec"])

    def in_pits_at(self, drv, clock) -> bool:
        s = self.stops[self.stops["driver_ref"].eq(drv)]
        return bool(((s["pit_entry_sec"] <= clock) & (s["pit_exit_sec"] > clock)).any())

    def other_stop(self, drv, lo, hi, own) -> bool:
        return any(lo <= s <= hi and s != own for s in self.stop_laps.get(drv, []))

    def window(self, drv, lo, hi) -> dict:
        rows = [self.row(drv, k) for k in range(lo, hi + 1)]
        if any(r is None for r in rows):
            return dict(complete=False, green=False, dry=False, timing_ok=False,
                        dry_compound=False, sc=False, vsc=False)
        codes = "".join(str(r["TrackStatus"]) for r in rows)
        return dict(
            complete=True,
            green=all(r["green"] for r in rows),
            dry=all(r["dry"] for r in rows),
            timing_ok=all(r["lap_ok"] for r in rows),
            dry_compound=all(r["Compound"] in DRY for r in rows),
            sc="4" in codes,
            vsc="6" in codes or "7" in codes,
        )

    def follow_up_status(self, c, l, lo, hi) -> str:
        """Why laps lo..hi (after the comparison lap) are or are not a clean follow-up."""
        if hi < lo:
            return "ok"
        if self.last_lap.get(c, 0) < hi or self.last_lap.get(l, 0) < hi:
            return "retired"
        if self.other_stop(c, lo, hi, -1) or self.other_stop(l, lo, hi, -1):
            return "stop"
        fc, fl = self.window(c, lo, hi), self.window(l, lo, hi)
        if not (fc["complete"] and fl["complete"]):
            return "missing_timing"
        if not (fc["green"] and fl["green"]):
            return "neutralised"
        if not (fc["dry"] and fl["dry"]):
            return "wet"
        if not (fc["timing_ok"] and fl["timing_ok"]):
            return "missing_timing"
        return "ok"

    def ahead_throughout(self, c, l, lo, hi):
        """1 if the chaser crosses the line before the leader at every lap lo..hi, NA if untimed."""
        ahead = True
        for k in range(lo, hi + 1):
            tc, tl = self.t(c, k), self.t(l, k)
            if not (np.isfinite(tc) and np.isfinite(tl)):
                return np.nan
            ahead &= tc < tl
        return int(ahead)

    def outcome(self, c, l, start, length, follow_from):
        """Success from lap `start` over `length` more laps, NA if the follow-up is interrupted."""
        if self.follow_up_status(c, l, follow_from, start + length) != "ok":
            return np.nan
        return self.ahead_throughout(c, l, start, start + length)


def exclusion_reason(fc, fl, compounds_dry) -> str:
    if not (fc["complete"] and fl["complete"]):
        return "incomplete"
    if not (fc["green"] and fl["green"]):
        return "non_green"
    if not (fc["dry"] and fl["dry"]):
        return "wet"
    if not (fc["timing_ok"] and fl["timing_ok"]):
        return "timing"
    if not compounds_dry:
        return "non_dry_compound"
    return "none"


def event_pairs(ev: Event, recs, base) -> list[dict]:
    out = []
    for i, a in enumerate(recs):
        for b in recs[i + 1:]:
            if a["driver_ref"] == b["driver_ref"] or abs(a["stop_lap"] - b["stop_lap"]) > MAX_DELAY:
                continue
            r = min(a["stop_lap"], b["stop_lap"]) - 1
            if r < 1:
                continue
            ta, tb = ev.t(a["driver_ref"], r), ev.t(b["driver_ref"], r)
            if not (np.isfinite(ta) and np.isfinite(tb)):
                continue
            if ev.in_pits_at(a["driver_ref"], ta) or ev.in_pits_at(b["driver_ref"], tb):
                continue
            chaser, leader = (a, b) if ta > tb else (b, a)
            gap = abs(ta - tb)
            if gap == 0 or gap > MAX_GAP_SEC:
                continue
            c, l = chaser["driver_ref"], leader["driver_ref"]
            cs, ls = int(chaser["stop_lap"]), int(leader["stop_lap"])
            d = ls - cs
            e = int(max(chaser["outlap_number"], leader["outlap_number"]))
            if ev.other_stop(c, r, e, cs) or ev.other_stop(l, r, e, ls):
                continue
            fc, fl = ev.window(c, r, e), ev.window(l, r, e)
            compounds_dry = all(x in DRY for x in [chaser["old_compound"], chaser["new_compound"],
                                                   leader["old_compound"], leader["new_compound"]])
            reason = exclusion_reason(fc, fl, compounds_dry)
            rc, rl = ev.row(c, r), ev.row(l, r)
            teammates = int(rc["Team"] == rl["Team"])
            common = cs + COMMON_OFFSET
            tc_e, tl_e = ev.t(c, e), ev.t(l, e)
            h3_status = ev.follow_up_status(c, l, e + 1, e + 3)
            rec = dict(
                base,
                battle_id=f"{base['event_id']}:{c}:{cs}:{l}:{ls}",
                chaser=c, leader=l, chaser_stop_lap=cs, leader_stop_lap=ls, delay=d,
                strategy=strategy_label(d), delay_group=delay_group(d),
                ref_lap=r, comparison_lap=e, common_lap=common,
                teammates=teammates,
                clean_window=int(reason == "none"),
                exclusion_reason=reason,
                sc_in_window=int(fc["sc"] or fl["sc"]),
                vsc_in_window=int(fc["vsc"] or fl["vsc"]),
                in_core=int(reason == "none" and not teammates and 1 <= d <= MAX_DELAY
                            and 0 < gap <= CORE_MAX_GAP_SEC),
                gap_before_sec=gap,
                signed_gap_comparison_sec=tc_e - tl_e,
                horizon3_status=h3_status,
                success_h0=ev.ahead_throughout(c, l, e, e),
                success_h3=ev.ahead_throughout(c, l, e, e + 3) if h3_status == "ok" else np.nan,
                success_h5=ev.outcome(c, l, e, 5, e + 1),
                success_common_h0=ev.outcome(c, l, common, 0, e + 1),
                success_common_h3=ev.outcome(c, l, common, 3, e + 1),
                chaser_new_compound_role=ev.compound_role.get(chaser["new_compound"], "non_dry"),
                leader_new_compound_role=ev.compound_role.get(leader["new_compound"], "non_dry"),
            )
            out.append(rec)
    return out


def event_no_response(ev: Event, recs, base) -> list[dict]:
    out = []
    for a in recs:
        p, c = int(a["stop_lap"]), a["driver_ref"]
        r = p - 1
        if r < 1 or r not in ev.time_by_lap.index:
            continue
        tc = ev.t(c, r)
        if not np.isfinite(tc) or ev.in_pits_at(c, tc):
            continue
        row = ev.time_by_lap.loc[r].drop(labels=[c], errors="ignore").dropna()
        for l, tl in row.items():
            gap = tc - tl
            if not (0 < gap <= MAX_GAP_SEC) or ev.in_pits_at(l, tl):
                continue
            if any(p - MAX_DELAY <= s <= p + MAX_DELAY for s in ev.stop_laps.get(l, [])):
                continue
            later = [s for s in ev.stop_laps.get(l, []) if s > p + MAX_DELAY]
            out_lap = int(a["outlap_number"])
            fc, fl = ev.window(c, r, out_lap), ev.window(l, r, out_lap)
            clean = (exclusion_reason(fc, fl, a["old_compound"] in DRY and a["new_compound"] in DRY) == "none"
                     and fl["dry_compound"])
            out.append(dict(
                event_id=base["event_id"], year=base["year"], split=base["split"],
                chaser=c, leader=l, chaser_stop_lap=p, gap_before_sec=gap,
                teammates=int(ev.row(c, r)["Team"] == ev.row(l, r)["Team"]),
                clean_window=int(clean),
                leader_next_stop=later[0] if later else np.nan,
                leader_no_further_stop=int(not later),
            ))
    return out


def build(laps, stops, catalog):
    info = catalog.set_index("event_id")[["circuitRef", "round"]].to_dict("index")
    pairs, no_resp = [], []
    for event_id, ev_laps in laps.groupby("event_id"):
        ev_stops = stops[stops["event_id"].eq(event_id)]
        ev = Event(ev_laps, ev_stops)
        recs = ev_stops[["driver_ref", "stop_lap", "outlap_number", "old_compound",
                         "new_compound"]].to_dict("records")
        year = int(ev_laps["year"].iloc[0])
        base = dict(event_id=event_id, year=year, round=int(info[event_id]["round"]),
                    circuitRef=info[event_id]["circuitRef"], split=split_of(year),
                    era="post2022" if year >= 2022 else "pre2022")
        pairs += event_pairs(ev, recs, base)
        no_resp += event_no_response(ev, recs, base)
    pairs = pd.DataFrame(pairs)
    train_circuits = set(pairs.loc[pairs["split"].eq("train"), "circuitRef"])
    pairs["overtaking_imputed"] = (~pairs["circuitRef"].isin(train_circuits)).astype(int)
    return pairs, pd.DataFrame(no_resp)


def to_contract(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Order and type columns as in contracts/schema.csv; unfilled columns stay blank."""
    spec = pd.read_csv(SCHEMA, dtype=str).fillna("")
    spec = spec[spec["table"].eq(table)]
    out = pd.DataFrame(index=df.index)
    for _, col in spec.iterrows():
        name, kind = col["column"], col["type"]
        values = df[name] if name in df.columns else pd.Series(np.nan, index=df.index)
        if kind in ("int", "bool01"):
            values = pd.to_numeric(values).round().astype("Int64")
        elif kind == "float":
            values = pd.to_numeric(values).round(3)
        out[name] = values
    return out


def summarise(pairs: pd.DataFrame, no_resp: pd.DataFrame) -> None:
    """Row counts only: no outcome rates, so no held-out outcomes are read."""
    core = pairs[pairs["in_core"].eq(1)]
    order = ["train", "tune", "test", "transfer"]
    print(f"pairs: {len(pairs)} rows, {pairs['event_id'].nunique()} races")
    print("\npairs by exclusion_reason and split")
    print(pd.crosstab(pairs["exclusion_reason"], pairs["split"], margins=True,
                      margins_name="total").reindex(columns=order + ["total"]))
    print(f"\ncore cohort: {len(core)} pairs, {core['event_id'].nunique()} races")
    print(core.groupby("split").agg(pairs=("battle_id", "size"), races=("event_id", "nunique"))
          .reindex(order))
    print("\ncore pairs by delay and split")
    print(pd.crosstab(core["delay"], core["split"]).reindex(columns=order))
    print("\ncore pairs by horizon3_status and split")
    print(pd.crosstab(core["horizon3_status"], core["split"]).reindex(columns=order))
    print(f"\nno_response: {len(no_resp)} rows; clean non-teammate with gap <= 6 s: "
          f"{int(((no_resp['clean_window'] == 1) & (no_resp['teammates'] == 0) & (no_resp['gap_before_sec'] <= 6)).sum())}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw", type=Path, help="path to the F1_Pit_Wall_2018_2026 snapshot")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "derived")
    args = ap.parse_args()
    laps, stops, catalog = load(args.raw)
    pairs, no_resp = build(laps, stops, catalog)
    pairs = to_contract(pairs, "pairs").sort_values(["event_id", "chaser_stop_lap", "battle_id"])
    no_resp = to_contract(no_resp, "no_response").sort_values(["event_id", "chaser_stop_lap", "chaser", "leader"])
    args.out.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.out / "pairs.csv", index=False, na_rep="NA")
    no_resp.to_csv(args.out / "no_response.csv", index=False, na_rep="NA")
    summarise(pairs, no_resp)


if __name__ == "__main__":
    main()
