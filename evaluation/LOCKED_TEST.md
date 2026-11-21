# Locked evaluation procedure for issues 19 and 20

This is a proposed engineering procedure; it does not grant approval. No real
2025 or 2026 evaluation has been executed. Sumit owns model choice/refitting.

1. Merge and approve #8, real pairs/features, #11 models, #14 tuning choice and
   final race-bootstrap integration. Resolve common-lap/grid and traffic inputs.
2. Sumit freezes models and refits on 2018–2024 without using test outcomes.
   Both approve a model-freeze section in DECISIONS.md, with Status: accepted,
   Decided by: Sumit, Aiden, model_ids: and full Commit hash:. Merge before access.
3. Through reviewed #19 work, merge evaluation/locked_authorization.json based
   on the disabled example. It must explicitly authorize #19, name both GitHub
   signoffs, exact model IDs/outcomes, baseline, all input SHA-256 hashes, the
   reviewed harness hashes, seed and >=1000 metric resamples. The predictions
   must be fitted_on=train+tune and frozen grid bands must be precomputed without
   test outcomes. Reviewing source and checking hashes/row counts is not scoring.
4. Run `python evaluation/locked_run.py` for governance-only preflight. It reads
   origin/main's merged decisions/authorization, never local draft approval.
   Preflight opens no outcome input. Execute only once after the other partner
   reviews the procedure, confirms issue #19 authorization and review conditions.

```sh
python evaluation/locked_run.py --execute --pairs data/derived/pairs.csv --predictions data/derived/predictions.csv --window-grid data/derived/window_grid.csv
```

Execution must successfully fetch main, verify merged governance and all hashes,
then atomically reserve evaluation/locked_receipts/test.json before outcome
interpretation. Outputs go to the fixed evaluation/locked_results/test directory.
A failed reservation/run is not silently retried; retain failure evidence and
resolve it jointly. Commit results and receipt unchanged, including a wide,
missing or disappointing window. Both partners review/sign off; never optimize
models or thresholds after viewing test results. The lock prevents accidental
reruns in this checkout and rejects receipts already on main. Coordinate one
operator and promptly publish the receipt to prevent concurrent separate clones.

Metric CIs resample complete test races using fixed frozen predictions and paired
model-minus-baseline differences. They are conditional on the fitted model;
precomputed model curve bands represent training-refit uncertainty. Crossing CIs
from the training refit must be retained separately, with missing-crossing rates;
window_grid alone has no field for crossing CIs. No test-driven refitting occurs.

For 2026, first merge the completed 2025 receipt unchanged. Merge a separate
evaluation/transfer_authorization.json with issue=20, split=transfer, both
signoffs, frozen model/input/harness hashes, and test_receipt_sha256 matching the
committed 2025 receipt bytes. Then preflight and execute with --split transfer.
This scores the unchanged train+tune model descriptively. Refitting through 2025
requires another accepted shared decision and a reviewed procedure revision.

Current blockers: no accepted model freeze, production model command, authorized
input hashes, final common-lap model/grid or merged authorization. The example
is disabled, is not read by the runner, and cannot unlock protected data.
