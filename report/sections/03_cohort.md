# Study population and outcomes

*Section owner: Sumit.*

**Pairs.** A pair is two drivers in the same race whose stops are at most three laps
apart, with no other stop by either in between. The *reference lap* is the lap
before the first stop; all decision-time features are measured at its end. The car
behind at that point is the chaser and the car ahead the leader. The *delay* is the
leader's stop lap minus the chaser's: 1 to 3 is an undercut and the rival's delay
(definitions: `contracts/README.md`, `contracts/schema.csv`). The pipeline finds
7,933 pairs (`data/derived/pairs.csv`).

**Core cohort.** Clean window (green and dry on every lap, complete timing, dry
compounds, no extra stop), different teams, delay 1 to 3, and a starting gap above
0 and up to 6.0 s: **922 pairs in 151 races**, of which 564 pairs in 98 races are in
the training seasons, 165 / 19 in 2024, 130 / 20 in 2025 and 63 / 14 in 2026
(`analysis/coverage/output/core_scope_races_by_split.csv`). Delays 2 and 3 are
pooled (`d23`) because 2025 has only 13 delay-3 pairs. Teammate pairs (393 of 3,157
clean pairs) are excluded and used as a sensitivity check.

**Outcomes.** The primary outcome, *sustained success* (`success_h3`), is the
chaser ahead at every lap boundary from the later out-lap through three more laps.
When delays are compared, every pair is judged from the same *common lap*
(chaser stop lap + 4) instead (`success_common_h3`). A follow-up interrupted by a
stop, neutralisation, rain, retirement or missing timing is missing, never a
failure. In the training core, 473 of 564 pairs have a complete sustained outcome
(91 missing) and 108 of them succeed (22.8%); 449 have a complete common-lap outcome
(`evaluation/TRAINING_INTEGRATION.json`, `models/output/fit_summary.csv`).

**No response.** A chaser stop with a rival up to 10 s ahead who made no stop
within three laps either side is not a pair; it is its own outcome category
(`data/derived/no_response.csv`, 6,798 records).
