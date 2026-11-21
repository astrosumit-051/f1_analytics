# Extension 3: tyre choice at the stop (A6, #16)

`python analysis/extensions/tyre_choice/analyze.py` (default base model `final_v1`).
Compares chasers who fitted the middle compound with those who fitted the hardest
(roles relative to each event), on core training pairs (2018-2023, `success_h3`), by
adding a middle indicator to `final_v1`. The compound is chosen by the team, so this
is an association, not the effect of switching.

| File | Status label |
| --- | --- |
| `output/counts.csv` | row counts by role and split (reproduces the audit: hardest 507, middle 246, softest 67) |
| `output/observed_by_role.csv` | descriptive, training seasons; softest descriptive only |
| `output/coefficients.csv`, `curves.csv`, `crossings.csv` | model-based, training seasons (in-sample) |

Not evaluated on held-out seasons: issue #16 is not labelled `holdout`. Doing so
would need either a holdout-labelled follow-up or inclusion in the locked test plan.
