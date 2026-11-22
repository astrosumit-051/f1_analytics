# Extensions

Each result is labelled *evaluated on held-out seasons*, *descriptive* or
*assumption-based*, as the proposal requires. All use the core definitions, the
common lap and the training seasons unless stated.

**1. Pit-stop time tolerance (assumption-based).** Adding the first stopper's
pit-lane time over the race median to the final model (common-lap outcome) gives
-0.40 log-odds per extra second (`analysis/extensions/execution/output/run.json`).
At a 1 s gap a one-lap undercut stays above 25% only if the stop costs less than
2.8 s more than usual; at 1.5 s the margin is 1.2 s, and from 2 s there is none. A
rival who waits two or three laps leaves more room: 4.9 s at 1 s, 2.0 s at 2 s
(`tolerance.csv`). Observed training rates fall the same way: for d23 pairs, 38%
with a normal stop, 28% at 0 to 1 s slow, 15% at 1 to 2 s and 0 of 28 above 2 s
(`observed_by_excess.csv`, descriptive). The model assumes the same slope at every
gap and delay.

**2. The defender's view and the comparison group (descriptive).** Among clean,
different-team training pairs, the trailing car was ahead at the common lap in 21%
of one-lap undercuts, 25% at two laps and 39% at three, against 16% when both
stopped on the same lap and 13% to 16% when the leader stopped first
(`analysis/extensions/defender/`, race-bootstrap intervals in the same file). Seen from the
leader, a rival who answers within a lap concedes about half as often as one who
waits three laps. This is an association, since stops were chosen, not assigned.

**3. Tyre choice at the stop (model-based, training seasons).** Chasers who fitted
the event's middle compound did slightly better than those on the hardest
(+0.12 log-odds per SD, standard error 0.18; 386 pairs in 82 races,
`analysis/extensions/tyre_choice/output/coefficients.csv`). The 25% crossing moves
from 1.7 to 1.9 s for one-lap delays and from 2.7 to 3.2 s for two or three laps
(`crossings.csv`). The difference is within noise, and the compound is the team's
choice. Softest-compound stops (47 training pairs) are reported descriptively only.

**4. Safety car and VSC (descriptive).** Neutralised windows are rarely usable:
most pairs with a safety car in the window have an interrupted follow-up, so their
outcomes are missing (`analysis/extensions/neutralisation/`). Dry status is not
verified for these rows. We report counts and timing gains only and draw no window.

**5. 2026 transfer (descriptive).** PENDING #20: scored once after the locked test,
with the unchanged train+tune model.
