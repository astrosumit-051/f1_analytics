# Undercut window Shiny demo

Install the R package `shiny`. From the repository root, launch with:

```sh
Rscript -e "shiny::runApp('demo', launch.browser=TRUE)"
```

The app reads training rows from the shared `pairs.csv` and uses
`success_common_h3` rows from `window_grid.csv`. It reads `no_response.csv`
when available. The default paths are under `data/derived/`. Set
`F1_PAIRS`, `F1_WINDOW_GRID`, and `F1_NO_RESPONSE` to absolute paths to use
alternate input files. The demo loads the files and performs no model fitting.

For a walkthrough, pick a rival delay and compare the model curve with the
observed gap bands. Then show the recorded success and failure near a
two-second starting gap. The chart is limited to observed support. An
unavailable model grid, crossing, or no-response denominator is labelled as
pending or unavailable.
