"""Check that a handoff table matches contracts/schema.csv.

Usage:
    python contracts/check_contract.py <table> <file.csv>
    python contracts/check_contract.py --fake      # check every fake sample

<table> is one of: pairs, no_response, predictions, window_grid.
Exits with status 1 and lists every problem if the file does not match.
Needs pandas only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SCHEMA = pd.read_csv(HERE / "schema.csv", dtype=str).fillna("")
RANGE = re.compile(r"^(-?\d+(?:\.\d+)?)(?:-|\.\.)(-?\d+(?:\.\d+)?)$")
FAKE = {
    "pairs": HERE / "fake" / "pairs_fake.csv",
    "no_response": HERE / "fake" / "no_response_fake.csv",
    "predictions": HERE / "fake" / "predictions_fake.csv",
    "window_grid": HERE / "fake" / "window_grid_fake.csv",
}


def check(table: str, path: Path) -> list[str]:
    spec = SCHEMA[SCHEMA["table"].eq(table)]
    if spec.empty:
        return [f"unknown table {table!r}"]
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    problems = []
    expected = list(spec["column"])
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected]
    if missing:
        problems.append(f"missing columns: {missing}")
    if extra:
        problems.append(f"columns not in the contract (add them with a DECISIONS entry first): {extra}")
    for _, col in spec.iterrows():
        name = col["column"]
        if name not in df.columns:
            continue
        values = df[name]
        present = values[~values.isin(["", "NA"])]
        kind, allowed = col["type"], col["allowed"]
        if kind in ("int", "float"):
            nums = pd.to_numeric(present, errors="coerce")
            if nums.isna().any():
                problems.append(f"{name}: non-numeric values {sorted(present[nums.isna()].unique())[:5]}")
            if kind == "int" and (nums.dropna() % 1 != 0).any():
                problems.append(f"{name}: expected whole numbers")
            m = RANGE.match(allowed)
            if m:
                lo, hi = float(m.group(1)), float(m.group(2))
                bad = nums[(nums < lo) | (nums > hi)]
                if len(bad):
                    problems.append(f"{name}: {len(bad)} values outside {allowed}")
        elif kind in ("enum", "bool01"):
            options = set(allowed.split("|"))
            if "NA" in options:
                options.add("")
            bad = set(values.unique()) - options
            if bad:
                problems.append(f"{name}: values {sorted(bad)[:5]} not in {allowed}")
    if table == "pairs" and "battle_id" in df.columns and df["battle_id"].duplicated().any():
        problems.append("battle_id is not unique")
    return problems


def main(argv: list[str]) -> int:
    jobs = list(FAKE.items()) if argv[1:] == ["--fake"] else [(argv[1], Path(argv[2]))] if len(argv) == 3 else []
    if not jobs:
        print(__doc__)
        return 2
    failed = False
    for table, path in jobs:
        problems = check(table, path)
        print(f"{table}: {path} ... {'OK' if not problems else 'FAILED'}")
        for p in problems:
            print(f"  - {p}")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
