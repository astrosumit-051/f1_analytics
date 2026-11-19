# Derived handoff tables

Partner A's pipeline writes the real handoff tables here: `pairs.csv`,
`no_response.csv`, `predictions.csv` and `window_grid.csv`. Their columns are fixed
in [`contracts/schema.csv`](../../contracts/schema.csv). Raw race data never goes in
the repository.

These files contain 2024 and 2025 outcomes. Follow the holdout rules in
[`contracts/README.md`](../../contracts/README.md) before reading any outcome column.
