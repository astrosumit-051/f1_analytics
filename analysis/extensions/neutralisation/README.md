# Safety car VSC and transfer development

```sh
python analysis/extensions/neutralisation/analyze.py --pairs contracts/fake/pairs_fake.csv --out analysis/extensions/neutralisation/results/fake
python -m pytest analysis/extensions/neutralisation/test_neutralisation.py -q
```

The same command accepts approved real pairs. Development reads train only. It
shows clean control, SC only, VSC only, both, and other unclean rows separately,
with exact delay strata. Timing gain is starting chaser-minus-leader gap minus
observed signed comparison gap: positive means the chaser gained time. This
endpoint is pair-specific and must not be pooled across different delays as a
common-lap strategy effect. Figures display observed means; CSVs include race
percentile intervals, medians, counts, missing gains and seeds.

These are descriptive associations. SC/VSC flags cover ref_lap..comparison_lap,
not a forecast at the decision. The exclusion_reason is a first failure, not a
complete list: a non_green row can also be wet or incompletely timed. The current
handoff cannot certify a dry neutralisation cohort. All such rows are clearly
labelled dry-status-unverified; no unsupported dry causal effect is estimated.
Common-lap sustained outcomes are separately reported with interrupted outcomes
counted. Other unclean rows are retained as a visible category.

2026 transfer is prepared through evaluation/locked_run.py --split transfer
(#19 dependency). It must verify an accepted merged freeze, a completed immutable
2025 receipt, explicit merged #20 authorization and frozen model/input hashes
before parsing transfer outcomes. It scores supplied frozen predictions without
retraining. Use train+tune+test only if an additional shared decision explicitly
approves that post-test refit; v1 evaluates the unchanged train+tune model. The
proposal's ambiguous 2018–2025 transfer wording does not authorize test tuning.
No 2026 execution is authorized or performed in this development milestone.
