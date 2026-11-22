# Limitations

- **Chosen, not assigned.** Every observed undercut was chosen by a team that
  expected it to work, and the rival chose its delay. Effects of gap and delay are
  associations within this cohort, not causal effects.
- **Small held-out seasons.** 2024 has 139 scored pairs in 18 races; 2025 has 130
  pairs in 20 races, so a rate near 25% has a 95% interval of about plus or minus
  7.5 points.
- **Model size.** The final model has 13 fixed effects for 108 training successes,
  more than the proposal's target of about ten.
- **Lap-boundary outcomes.** Passes and re-passes within a lap are invisible.
- **Missing context.** Setup, fuel load and tyre temperature are not in the data.
  Recent pace is missing for about 3% of core pairs and is filled with the training
  median.
- **Projected traffic.** Rejoin traffic is projected from the circuit's full
  pit-lane median, not the time actually lost, so it is a rough measure (D-006).
- **Holdout exposure.** A separate companion prototype (PR #26) computed 2025
  scores before the model freeze. It used a different model and none of its numbers
  enter this report. It will be recorded in `DECISIONS.md` before the locked test is run.
