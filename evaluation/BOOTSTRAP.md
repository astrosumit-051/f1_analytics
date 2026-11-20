# Race bootstrap implementation

Install evaluation/requirements.txt. From the repository root:

```sh
python evaluation/bootstrap.py --pairs contracts/fake/pairs_fake.csv --resamples 400 --seed 355 --predictions contracts/fake/predictions_fake.csv --baseline FAKE_baseline_gap_v0 --out evaluation/results/bootstrap_fixture
```

Entire races are sampled with replacement; both models see the same draws.
Window bands are pointwise 95% percentile intervals, not simultaneous bands.
Crossing intervals are conditional on a supported crossing and report how many
draws had one. Missing crossings remain missing. Out-of-bag ranges describe
refit variability; they are not test-score confidence intervals. Optional
--predictions adds paired whole-race percentile intervals for fixed training
predictions and model-minus-baseline differences, conditional on the fitted
model. Training accuracy remains optimistic.

The default outcome is success_common_h3 for comparing delays at a common lap.
Stand-ins are restricted to fake-labelled training data with FAKE model IDs.
For A's public command use --outcome success_h3 and --entry-point-json containing
a JSON argv list such as ["python","models/ENTRY_POINT.py"], then repeat --model
for each requested model. ENTRY_POINT is a placeholder: no approved model entry
point exists on the assessed main. The adapter never invokes a shell and appends
exactly --train --predict --model --out. It is tested with an explicit mock
process; that does not validate the missing scientific model.

Repeated race copies receive distinct event/battle IDs in temporary public pairs
files so a random-intercept model treats them as separate sampled groups.
Prediction profiles use training feature medians and synthetic IDs, with all
outcomes removed. These profiles are assumptions, not observations. Other
training-only preprocessing must stay inside A's entry point. Review integer
median handling and population/new-race predictions with Sumit before production.

The public command promises success_h3 only. It cannot honestly produce
common-lap curves; requesting that outcome through the adapter raises an error.
An approved common-lap model/grid interface remains a dependency (#8/#11).

fitting_failures.csv records failed/one-class draws; run.json records seed,
requested/effective draws, input hashes, command and fit status. Conditional
crossing intervals carry missing-crossing counts and an instability flag. For
final reviewed runs use at least 1,000 resamples and examine convergence and
failures. Small runs are development diagnostics, not final uncertainty evidence.

Run python -m pytest evaluation/test_bootstrap.py -q. Checks cover whole-race
copies, paired draws, seeds, deliberate fitting failure, metric intervals,
synthetic refits and the four-argument command adapter.
