"""Write a small FAKE sample of every handoff table in contracts/schema.csv.

The numbers are invented. They follow the contract's columns, types and
rough shapes (gap mostly under 6 s, success falling with gap, longer rival
delays helping) so evaluation, charts and the demo can be built before the
real tables exist. Never report a result computed from these files.

Usage:
    python contracts/make_fake.py          # writes contracts/fake/*.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "fake"
SEED = 355
N_RACES_PER_YEAR = {2018: 6, 2019: 6, 2020: 5, 2021: 6, 2022: 6, 2023: 6, 2024: 5, 2025: 5, 2026: 3}
CIRCUITS = [f"fake_circuit_{c}" for c in "abcdefghij"]
DRIVERS = [f"fake_drv{i:02d}" for i in range(1, 21)]
STRATEGY = {1: "chaser_first_d1", 2: "chaser_first_d2", 3: "chaser_first_d3", 0: "same_lap",
            -1: "leader_first_d1", -2: "leader_first_d2", -3: "leader_first_d3"}


def split_of(year: int) -> str:
    return "train" if year <= 2023 else {2024: "tune", 2025: "test"}.get(year, "transfer")


def delay_group(d: int) -> str:
    return "d1" if d == 1 else "d23" if d > 1 else "same_lap" if d == 0 else "leader_first"


def true_p(gap, d, tyre_diff, traffic, between):
    """Invented 'truth' used only to draw fake outcomes."""
    z = 0.9 - 0.85 * gap + 0.7 * (d >= 2) - 0.04 * tyre_diff - 0.35 * traffic - 0.15 * between
    z = np.where(d <= 0, z - 1.0, z)
    return 1 / (1 + np.exp(-z))


def main() -> None:
    rng = np.random.default_rng(SEED)
    pit_median = {c: round(rng.uniform(18.5, 26), 2) for c in CIRCUITS}
    overtaking = {c: round(rng.uniform(0.01, 0.08), 4) for c in CIRCUITS}
    rows, nr = [], []
    for year, n_races in N_RACES_PER_YEAR.items():
        for rnd in range(1, n_races + 1):
            event_id = f"{year}_{rnd:02d}"
            circuit = CIRCUITS[(year + rnd) % len(CIRCUITS)]
            race_median = pit_median[circuit] + rng.normal(0, 0.4)
            used = set()
            for _ in range(rng.integers(5, 12)):
                c, l = rng.choice(DRIVERS, 2, replace=False)
                d = int(rng.choice([1, 1, 1, 2, 2, 3, 0, -1, -1, -2, -3]))
                stop_c = int(rng.integers(12, 45))
                stop_l = stop_c + d
                bid = f"{event_id}:{c}:{stop_c}:{l}:{stop_l}"
                if bid in used:
                    continue
                used.add(bid)
                gap = round(float(min(rng.gamma(2.0, 1.6), 9.9)) + 0.01, 3)
                age_c, age_l = int(rng.integers(8, 35)), int(rng.integers(8, 35))
                between = int(min(rng.poisson(gap * 0.4), 19))
                traffic = int(rng.choice([0, 0, 0, 1, 1, 2]))
                teammates = int(rng.random() < 0.1)
                reason = rng.choice(["none"] * 17 + ["non_green", "wet", "timing"])
                clean = int(reason == "none")
                first_pit = round(race_median + abs(rng.normal(0, 1.2)) + (rng.random() < 0.08) * rng.uniform(2, 8), 3)
                p = float(true_p(gap, d, age_c - age_l, traffic, between))
                s0 = int(rng.random() < p)
                s3 = int(s0 and rng.random() < 0.9)
                status = rng.choice(["ok"] * 9 + ["stop", "neutralised", "retired"])
                ref = min(stop_c, stop_l) - 1
                comparison = max(stop_c, stop_l) + 1
                rows.append(dict(
                    battle_id=bid, event_id=event_id, year=year, round=rnd, circuitRef=circuit,
                    split=split_of(year), chaser=c, leader=l, chaser_stop_lap=stop_c,
                    leader_stop_lap=stop_l, delay=d, strategy=STRATEGY[d], delay_group=delay_group(d),
                    ref_lap=ref, comparison_lap=comparison, common_lap=stop_c + 4,
                    teammates=teammates, clean_window=clean, exclusion_reason=reason,
                    sc_in_window=int(reason == "non_green" and rng.random() < 0.6),
                    vsc_in_window=int(reason == "non_green" and rng.random() < 0.4),
                    in_core=int(clean and not teammates and 1 <= d <= 3 and gap <= 6),
                    gap_before_sec=gap, chaser_tyre_age=age_c, leader_tyre_age=age_l,
                    tyre_age_diff=age_c - age_l, cars_between_at_ref=between,
                    circuit_pitlane_median_sec=pit_median[circuit], rejoin_traffic_cars=traffic,
                    overtaking_difficulty=overtaking[circuit], overtaking_imputed=0,
                    era="pre2022" if year < 2022 else "post2022",
                    first_stopper_pitlane_sec=first_pit,
                    first_stopper_pitlane_excess_sec=round(first_pit - race_median, 3),
                    chaser_new_compound_role=rng.choice(["hardest", "hardest", "middle", "softest"]),
                    leader_new_compound_role=rng.choice(["hardest", "hardest", "middle", "softest"]),
                    signed_gap_comparison_sec=round((-1 if s0 else 1) * (abs(float(rng.normal(1.0, 0.8))) + 0.01), 3),
                    horizon3_status=status,
                    success_h0=s0,
                    success_h3=s3 if status == "ok" else "NA",
                    success_h5=(int(s3 and rng.random() < 0.95) if status == "ok" else "NA"),
                    success_common_h0=s0, success_common_h3=s3 if status == "ok" else "NA",
                ))
                if rng.random() < 0.6:
                    nostop = rng.random() < 0.25
                    nr.append(dict(
                        event_id=event_id, year=year, split=split_of(year), chaser=c,
                        leader=rng.choice([x for x in DRIVERS if x not in (c, l)]), chaser_stop_lap=stop_c,
                        gap_before_sec=round(float(rng.uniform(0.2, 9.9)), 3), teammates=int(rng.random() < 0.1),
                        clean_window=int(rng.random() < 0.85),
                        leader_next_stop="NA" if nostop else stop_c + int(rng.integers(4, 20)),
                        leader_no_further_stop=int(nostop),
                    ))
    pairs = pd.DataFrame(rows)
    # D-010 columns, from a separate stream so the rest of the sample is unchanged.
    extra = np.random.default_rng(SEED + 10)
    pairs["recent_pace_diff_sec"] = np.round(extra.normal(0.2, 0.5, len(pairs)), 3)
    pairs.loc[extra.random(len(pairs)) < 0.03, "recent_pace_diff_sec"] = np.nan
    pairs["track_temp_c"] = np.round(extra.uniform(16, 55, len(pairs)), 1)

    preds = []
    core = pairs[pairs["in_core"].eq(1)]
    gap, d = core["gap_before_sec"], core["delay"]
    fake_models = {
        "FAKE_baseline_gap_v0": 1.1 - 0.8 * gap + rng.normal(0, 0.2, len(core)),
        "FAKE_primary_v0": 0.9 - 0.85 * gap + 0.7 * (d >= 2) + rng.normal(0, 0.4, len(core)),
    }
    for model_id, z in fake_models.items():
        preds.append(pd.DataFrame(dict(
            battle_id=core["battle_id"], model_id=model_id, outcome="success_h3", fitted_on="train",
            split=core["split"], p_success=np.round(1 / (1 + np.exp(-z)), 4))))
    preds = pd.concat(preds, ignore_index=True)

    grid = []
    for model_id in ["FAKE_baseline_gap_v0", "FAKE_primary_v0"]:
        for dg, dval in [("d1", 1), ("d23", 2)]:
            for gap in np.round(np.arange(0.1, 6.01, 0.1), 1):
                p = float(true_p(gap, dval if model_id.endswith("primary_v0") else 1, 0, 0, 0))
                grid.append(dict(model_id=model_id, outcome="success_h3", delay_group=dg, gap_sec=gap,
                                 p_success=round(p, 4), p_lo="NA", p_hi="NA"))

    OUT.mkdir(exist_ok=True)
    order = pd.read_csv(Path(__file__).resolve().parent / "schema.csv").query("table == 'pairs'")["column"]
    pairs[list(order)].to_csv(OUT / "pairs_fake.csv", index=False)
    pd.DataFrame(nr).to_csv(OUT / "no_response_fake.csv", index=False)
    preds.to_csv(OUT / "predictions_fake.csv", index=False)
    pd.DataFrame(grid).to_csv(OUT / "window_grid_fake.csv", index=False)
    print(f"pairs {len(pairs)} (core {int(pairs['in_core'].sum())}), no_response {len(nr)}, "
          f"predictions {len(preds)}, window_grid {len(grid)} -> {OUT}")


if __name__ == "__main__":
    main()
