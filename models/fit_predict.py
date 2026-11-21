"""Fit-and-predict entry point (contracts/README.md, issue A3 #11).

    python models/fit_predict.py --train <pairs.csv> --predict <pairs.csv> \
        --model <model_id> --out <predictions.csv> [--outcome success_h3]

Fits ``model_id`` on the ``in_core = 1`` rows of ``--train`` that have the outcome,
predicts the ``in_core = 1`` rows of ``--predict`` and writes a ``predictions`` file.
``--outcome`` defaults to ``success_h3`` (the v1 contract); ``success_common_h3`` is
allowed for the common-lap curves (DECISIONS D-009).

``fitted_on`` is worked out from the splits present in the training rows. The
command never prints an outcome rate or a score, so running it on a file that
contains tuning or test rows does not "read" their outcomes; scoring is done by
``evaluation/``. It refuses to fit on rows from the test or transfer split.

Model ids: see ``SPECS`` in models/core.py (``python models/fit_predict.py --list``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import OUTCOMES, SPECS, fit  # noqa: E402

FITTED_ON = {
    frozenset({"train"}): "train",
    frozenset({"train", "tune"}): "train+tune",
}


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"battle_id": str, "event_id": str, "split": str})
    return df[df["in_core"].astype(str).isin(["1", "1.0"])].copy()


def run(train_path, predict_path, model_id, out_path, outcome="success_h3"):
    if model_id not in SPECS:
        raise ValueError(f"Unknown model {model_id!r}; choose from {sorted(SPECS)}")
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown outcome {outcome!r}")
    train = load(train_path)
    splits = frozenset(train["split"].unique())
    if splits not in FITTED_ON:
        raise ValueError(f"Training rows must come from train (or train+tune), got {sorted(splits)}")
    model = fit(SPECS[model_id], train, outcome)
    if not model.converged:
        raise RuntimeError(f"{model_id} did not converge")
    target = load(predict_path)
    out = pd.DataFrame({
        "battle_id": target["battle_id"],
        "model_id": model_id,
        "outcome": outcome,
        "fitted_on": FITTED_ON[splits],
        "split": target["split"],
        "p_success": model.predict(target).round(6),
    })
    out.to_csv(out_path, index=False)
    return model, out


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--train", type=Path)
    cli.add_argument("--predict", type=Path)
    cli.add_argument("--model")
    cli.add_argument("--out", type=Path)
    cli.add_argument("--outcome", default="success_h3", choices=OUTCOMES)
    cli.add_argument("--list", action="store_true", help="list model ids and exit")
    a = cli.parse_args(argv)
    if a.list:
        for k, s in SPECS.items():
            print(f"{k}: {s.description}")
        return 0
    if not all([a.train, a.predict, a.model, a.out]):
        cli.error("--train, --predict, --model and --out are required")
    try:
        run(a.train, a.predict, a.model, a.out, a.outcome)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
