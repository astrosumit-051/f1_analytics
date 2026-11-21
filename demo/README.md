# Shiny window application

R Shiny is a provisional implementation under proposed D-007; Sumit must approve
technology and production handoffs before this is called submission-ready.
Statistical and CSV logic lives in demo/data.R, not in the interface. There is no
model fitting at startup or on control changes. The companion simulator is not
integrated.

Install R and shiny (install.packages("shiny")). Run from the repository root:

```sh
Rscript -e "shiny::runApp('demo', launch.browser=TRUE)"
```

Approved real handoffs belong in data/derived/pairs.csv, window_grid.csv and
optional no_response.csv. A missing pairs file shows an explicit setup message;
missing model/common-lap outputs leave model calculations unavailable while
observed tables stay usable. Set F1_PAIRS, F1_WINDOW_GRID and F1_NO_RESPONSE to
absolute alternative paths. Set F1_MODE=provisional for unmerged real handoffs;
F1_MODE=real is the default. Inputs are read as text and filtered to 2018-2023
before outcome conversion. Synthetic/real mixtures are rejected.

For an explicit fake software demonstration in PowerShell:

```powershell
$env:F1_MODE='fake'
Rscript -e "shiny::runApp('demo', launch.browser=TRUE)"
```

The published fake grid supplies the primary pair-specific outcome. The common-
lap view correctly says pending. To exercise common-lap curves and bands first
run the synthetic bootstrap command in evaluation/BOOTSTRAP.md, then set
F1_WINDOW_GRID to the absolute generated window_grid.csv path. This does not turn
fake probabilities into findings.

Controls select gap, model, outcome, response delay and a response overlay. The
primary view plots only one response group because it uses pair-specific laps;
response comparisons always use common-lap outcomes. Values interpolate inside
the supplied supported grid only, never extrapolate. Intervals are pointwise
model bands. Table counts retain missing outcomes. Source fingerprints and a
CSV download make displayed values traceable. Recorded success/failure examples
are chosen deterministically from complete training cycles near the selected gap.
No-response rates wait for an agreed denominator.

Real curves require the training refit's run.json (F1_GRID_METADATA, defaulting
to the grid directory). Its split, model IDs, evidence and grid fingerprint must
match. Unknown provenance withholds the model curve with a clear message; observed
tables remain available. jsonlite is a Shiny dependency. Current development
permits training-only grids; final frozen-fit integration is pending review.

```sh
Rscript --vanilla demo/test_app.R
```

The tests check arithmetic, protected sentinels, deterministic values, Shiny
controls, numeric agreement, missing outputs, signs and support. A local Chrome
session also exercised model/delay selectors and rendered comparisons. Windows
R 4.6.1 in this environment writes all PASS assertions, then crashes during
shutdown after loading shiny; even a minimal library(shiny);q(status=0) reproduces
it. Base R exits normally. Do not interpret the assertion marker as a clean
process-exit pass. The live server remains functional; verify clean exit on the
submission machine. Unicode separators were replaced with ASCII after visual
inspection caught locale corruption.

## Double-click desktop launch

On Windows, double-click demo/Open F1 Analytics.vbs. The local workspace also has
an Open F1 Analytics shortcut in the parent F1_analytics folder. R and the user's
Shiny library are located automatically; no RStudio console commands are needed.
The launcher opens the browser at http://127.0.0.1:3855, uses approved-location
handoffs when present or the existing provisional training-only snapshot, and
never builds/scans protected outcomes or substitutes synthetic predictions.
Reopening the launcher reuses an existing F1 dashboard on that port. Click Stop
local app in the sidebar to stop this local session. Startup errors open
 evaluation/results/launcher.log. This launcher is local; it does not publish a
website or merge the companion simulator. Model outputs remain unavailable until
real model handoffs and their provenance are supplied.

Verification: launch.R --check validated 564 core training rows. Windows Script
Host requires normal desktop access (sandbox settings access was denied); the
normal desktop launch succeeded and the HTTP endpoint was independently checked.

## Self-contained local app and workspace bins

For local use, demo/build_local_bundle.py --out <new folder> copies only the
runtime app, pure helpers, startup/configuration files, training-only handoffs and
provenance. It rejects non-training input rows and verifies copied input hashes.
No raw data, test code, simulator, fitting code or generated test results are
needed in the runtime bundle. The app opens on observed response comparisons;
model outputs remain pending. The runtime root is independent of the source
checkout, so moving/organizing development files does not break its data paths.

The bundle supports double-click startup and RStudio's Run App after opening its
Rproj. A running Shiny session does not finish like a batch script: use Stop local
app to close its server. Full statistical/model completion is still outstanding.
