# Undercut model evaluation

The evaluator reads the shared CSV handoff. It compares the baseline and other
models on the same complete core pairs. It saves Brier score, log loss,
calibration data and a calibration figure. If given a window grid, it also
saves the 50% and 25% downward crossings within the observed gap range for each
delay group. A missing or ambiguous crossing is recorded as unavailable.

Install the Python dependencies with `python -m pip install numpy pandas matplotlib`.
Run from the repository root:

```sh
python evaluation/evaluate.py --pairs contracts/fake/pairs_fake.csv --predictions contracts/fake/predictions_fake.csv --window-grid contracts/fake/window_grid_fake.csv --baseline FAKE_baseline_gap_v0 --out evaluation_output/fixture
```

The fake files test the CSV interface. Every output identifies them as a
synthetic fixture. To evaluate the shared training output, use the real
`pairs.csv` and `predictions.csv`, and specify the baseline's model ID if it
differs from `baseline_gap_v1`. Missing outcomes and missing model rows are
counted separately. The evaluator does not change any input files.

The default split is `train`. Use `tune` only for the model-selection issue.
The test split requires a model-freeze section in `DECISIONS.md` with
`Status: accepted`, `model_id:` or `model_ids:`, and a full `Commit hash:`.
The names in that accepted record must cover every evaluated test model. This
field format is provisional pending confirmation in the shared freeze issue.
Run the locked test only during the agreed test pass.

