"""Shared loading for Partner A model scripts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_COLS = ("recent_pace_diff_sec", "track_temp_c")


def load_pairs(path=ROOT / "data/derived/pairs.csv", splits=("train",),
               candidates=ROOT / "data/derived/tuning_candidates.csv") -> pd.DataFrame:
    """Pairs restricted to ``splits`` (test/transfer never loaded unless asked), with the
    A4 candidate columns merged in when the pairs file does not carry them."""
    p = pd.read_csv(path, dtype={"battle_id": str, "event_id": str})
    p = p[p.split.isin(splits)].copy()
    missing = [c for c in CANDIDATE_COLS if c not in p.columns]
    if missing and Path(candidates).exists():
        p = p.merge(pd.read_csv(candidates, dtype={"battle_id": str})[["battle_id", *missing]],
                    on="battle_id", how="left")
    return p
