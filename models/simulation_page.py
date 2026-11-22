"""Build the Undercut Lab page from models/simulate.py outputs (A7, #24).

    python models/simulation_page.py [--sim models/output/simulation] [--out <html>]

Writes one self-contained HTML file (no external scripts or fonts). Status:
assumption-based, training seasons 2018-2023 only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "models/simulation_template.html"


def build(sim: Path, out: Path) -> Path:
    grid = pd.read_csv(sim / "scenario_grid.csv")
    data = {
        "grid": grid.drop(columns=["status"]).to_dict(orient="records"),
        "check": pd.read_csv(sim / "season_check.csv").drop(columns=["status"]).to_dict(orient="records"),
        "replays": json.loads((sim / "replays.json").read_text()),
        "model": json.loads((sim / "model.json").read_text()),
        "run": json.loads((sim / "run.json").read_text()),
    }
    html = TEMPLATE.read_text().replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--sim", type=Path, default=ROOT / "models/output/simulation")
    cli.add_argument("--out", type=Path, default=ROOT / "models/output/simulation/undercut_lab.html")
    a = cli.parse_args(argv)
    print(build(a.sim, a.out))


if __name__ == "__main__":
    main()
