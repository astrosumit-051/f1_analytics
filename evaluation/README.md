# Undercut model evaluation

The evaluator reads the shared CSV handoff. It compares the baseline and other
models on the same complete core pairs. It saves Brier score, log loss,
calibration data and a calibration figure. If given a window grid, it also
saves the 50% and 25% downward crossings within the observed gap range for each
delay group. A missing or ambiguous crossing is recorded as unavailable.

Install with `python -m pip install -r evaluation/requirements.txt`.
Run from the repository root:

```sh
python evaluation/evaluate.py --pairs contracts/fake/pairs_fake.csv --predictions contracts/fake/predictions_fake.csv --window-grid contracts/fake/window_grid_fake.csv --baseline FAKE_baseline_gap_v0 --out evaluation/results/fixture
```

The fake files test the CSV interface. Every output identifies them as a
synthetic fixture. To evaluate the shared training output, use the real
`pairs.csv` and `predictions.csv`, and specify the baseline's model ID if it
differs from `baseline_gap_v1`. Missing outcomes and missing model rows are
counted separately. The evaluator does not change any input files.

The default split is `train`. Tuning requires `--split tune --holdout-issue 14`
and must be used only within the labelled model-selection issue. Test and transfer
are refused before input access; use the separately reviewed #19/#20 procedures.
No freeze or authorized locked run exists on the assessed main commit.

`metrics.csv` includes mean predicted/observed probability, calibration bias
(predicted minus observed) and five equal-width-bin ECE. These descriptive
statistics depend on sample/bin size. Training scores are explicitly in-sample.
Log loss clips only for numerical stability at 1e-15; Brier uses original values.
`cohort_counts.csv` counts producer exclusions; missing follow-up and predictions
are separately counted per outcome in metrics. All compared models use the same
complete cases. Pair counts are not independent race counts.

`run.json` records input SHA-256 hashes, versions, baseline and split. Outputs
under `evaluation/results/` are ignored. Inputs are never overwritten. Curves
describe median-feature profiles, while observed bands average actual profiles;
they need not coincide even for a calibrated model. Crossing interpolation is
inside the observed gap range only; ambiguous/flat/absent crossings remain NA.

Run the independent regression checks with
`python -m pytest evaluation/test_evaluate.py -q`. They include hand-calculated
scores, paired exclusions, invalid input rejection and protected-row sentinels.

For the combined reproducible check runner use `python evaluation/run_checks.py`.
Add `--rscript /path/to/Rscript` to include Shiny; an abnormal R exit is reported
as a failed process even when assertion markers pass. Protected evaluation is
prepared separately in [LOCKED_TEST.md](LOCKED_TEST.md); the default preflight
opens no outcome input and cannot grant its own authorization.
