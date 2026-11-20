# Defender technical analysis

Run from the root:

```sh
python analysis/extensions/defender/analyze.py --pairs contracts/fake/pairs_fake.csv --out analysis/extensions/defender/results/fake
python -m pytest analysis/extensions/defender/test_defender.py -q
```

Replace --pairs with the approved handoff unchanged. Only training rows are
interpreted. Outputs cover each exact delay -3..3, overall and by starting gap,
at common_lap = chaser_stop_lap + 4. Positive delays describe the leader responding
after one, two or three laps; zero is same-lap; negative delays are leader-first.
Each result includes counts, missing follow-up, race count, seed, interval status
and descriptive status. No response is not a binary failure or defender success.

Chaser-not-ahead at the common lap is 1 - success_common_h0, retaining NA.
It is not sustained defence. The complement of sustained chaser success would
also include passing and re-passing and cannot establish sustained defence from
this contract. Sustained chaser outcomes are shown directly and separately.

The overlap sensitivity exactly stratifies on season, one-second gap band and
tyre-age difference. Shared strata get min(group counts) weight; exclusions and
zero overlap are explicit. It is a sparse descriptive comparison with no causal
or calibrated prediction claim. Race resampling handles within-race dependence,
but cannot eliminate confounding from teams choosing actions and response delay.
Held-out extension evaluation waits for #19 and collaborator review.
