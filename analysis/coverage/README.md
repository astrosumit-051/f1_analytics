# Coverage audit for the undercut-window proposal

`coverage_counts.py` rebuilds every pit-cycle pair from the combined lap and stop
tables and counts how much data each planned comparison has. It decides the scope
of the revised proposal (`Proposal/F1_Undercut_Window_Proposal_v2.docx`).

```
python analysis/coverage/coverage_counts.py <path to F1_Pit_Wall_2018_2026> analysis/coverage/output
```

It needs pandas and numpy and runs in about two minutes. The data folder is not in
the repository. Summary tables are committed in `output/`; the two row-level tables
are regenerated locally and ignored by git. Definitions are in the script's docstring.

## Check against the existing export

The rebuild reproduces all 354 battles in `pit_battles_model_ready.csv`, plus 2
more that the exporter excluded, most likely through its timestamp-based status or
weather check, which this script approximates with lap-level fields
(`output/reconciliation_with_export.csv`).

## Results (snapshot of November 12, 2026)

Outcome rates were computed only for the 2018 to 2023 training seasons.

| Finding | Number | Table |
| --- | --- | --- |
| Core cohort: clean window, different teams, rival delay 1 to 3 laps, gap up to 6 s | 924 pairs in 151 races (2.6 times the 354 export) | `core_scope_delay_by_split.csv` |
| Split sizes (train / tune / test / 2026) | 564 / 167 / 130 / 63 pairs; 98 / 19 / 20 / 14 races | `core_scope_races_by_split.csv` |
| Delay 3 in the 2025 test season | 13 pairs, so delays 2 and 3 are pooled for testing | `core_scope_delay_by_split.csv` |
| One-lap undercut success by gap (training) | 65% at 0 to 1 s, 35% at 1 to 2 s, 27% at 2 to 3 s, 18% at 3 to 3.5 s, 2% to 9% from 3.5 to 6 s, 0% beyond 6 s | `train_years_undercut_success_by_gap.csv` |
| Success by delay, gap up to 6 s (training) | 21% (delay 1), 27% (delay 2), 39% (delay 3) | same |
| Comparison group, gap up to 6 s (training) | trailing driver ahead in 13% of same-lap stops (171) and 13% when the rival stopped first (352) | `train_years_comparison_chaser_ahead.csv` |
| Rival made no stop within 3 laps either side, gap up to 6 s | 2,426 cases, 585 with no further stop at all | `censored_undercuts_by_gap.csv` |
| Teammate pairs among clean pairs | 395 of 3,170 (12%) | `teammate_pairs.csv` |
| Clean 3-lap and 5-lap follow-up, one-lap core pairs | 484 (90%) and 462 (86%) of 537 | `clean_undercut_horizon_availability.csv` |
| No car between the two drivers | 93% at 0 to 1 s, 48% at 2 to 3 s, about 25% at 4 to 6 s | `clean_pairs_adjacent_share_by_gap.csv` |
| Undercutter with a car within 2 s ahead after the out-lap | 19% to 32% depending on gap | `clean_undercut_rejoin_traffic.csv` |
| Median pit-lane time by circuit | 18.6 s (Albert Park) to 31.6 s (Madrid, one race) | `pitlane_time_by_circuit.csv` |
| Slow stops (over race median + 5 s) | 530 of 6,285 | `independence_and_execution.csv` |
| Stop reuse in core cohort | 594 undercutting stops used once, 112 twice, 32 three or more times | (printed by the script) |
| Pairs per circuit in core cohort | median 29.5, minimum 4, across 30 circuits | `core_scope_pairs_per_circuit.csv` |

## Caveats

- Green and dry are checked with each lap's `TrackStatus` and aligned `Rainfall`,
  not the exporter's timestamped intervals, so the clean flag is a close
  approximation.
- Delays 2 and 3 are evaluated at each pair's own comparison lap here. The proposal
  requires a common evaluation lap when delays are compared.
- "Rival made no stop within 3 laps" includes rivals on different strategies, not
  only rivals who chose to extend in response.
- All rates are descriptive. Strategies were chosen, not assigned.
