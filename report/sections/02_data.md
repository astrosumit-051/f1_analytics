# Data

*Section owner: Sumit.*

The source is the F1 Pit Wall snapshot of November 12, 2026: 213,132 driver laps
from 193 Grands Prix (2018 to Brazil 2026) and 6,767 matched pit stops, with lap
times, positions, track status, compounds, tyre age and weather per lap. The raw
files are not in the repository; every derived table is rebuilt from them by
`pipeline/build_pairs.py`, `pipeline/features.py` and `pipeline/candidates.py`.

A coverage audit (`analysis/coverage/`, run before any model was fitted) rebuilt
every pit-cycle pair from the lap and stop tables and reproduced all 354 battles in
the original export, which checks the gap and stop logic. Seasons before 2018 were
ruled out: the public historical source has lap times and stops but no compounds,
tyre age, track status or rain, so clean windows cannot be built.

The seasons are split by race and fixed in advance (D-003): 2018 to 2023 for
training, 2024 for model selection, 2025 as a locked test used once, and 2026 as a
descriptive check under the new regulations.
