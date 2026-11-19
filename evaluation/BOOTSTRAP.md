# Training bootstrap draft

Install the evaluation dependencies and SciPy. From the repository root:

```sh
python evaluation/bootstrap.py --pairs contracts/fake/pairs_fake.csv --resamples 400 --seed 355 --out evaluation_output/bootstrap_fixture
```

This refits simple logistic stand-ins and resamples entire races. The two fits
see the same race draws. The output window reports pointwise 95% percentile
bands. Crossing intervals are conditional on a crossing being found and report
how many draws supported it. Metric intervals summarize the spread of scores
on out-of-bag races and are an internal training diagnostic.

The default outcome is `success_common_h3` for the same finish line across delay
groups. Specify `--outcome success_h3` to check the pair-specific definition.
The refit callback receives the sampled training frame, the gap grid, and the
out-of-bag frame. Integration with the shared model is pending. Its adapter
must give repeated race copies separate grouping IDs and produce predictions
for the model's agreed grid scenarios.
