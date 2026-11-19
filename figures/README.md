# Undercut report figures

From the repository root, with pandas, NumPy and Matplotlib installed:

```sh
python figures/plot_windows.py --pairs data/derived/pairs.csv --no-response data/derived/no_response.csv --window-grid data/derived/window_grid.csv --model primary_v1 --out figure_output/training
```

Use a window grid from a training fit. The grid contract has no split column.
Pass the model ID in the supplied grid or omit it when only one common-lap
model is present. To check the software, the same command accepts the three
matching CSVs under `contracts/fake/` and labels the output as synthetic.
The published fake grid contains the pair-specific outcome, so the model curve
is pending with that fixture. Use the draft bootstrap's common-lap grid to
check curve drawing and interval bands.

The command writes a three-panel PNG and SVG plus the tables behind the
charts. All four comparison groups use `success_common_h3`. The chart
uses clean non-teammate training pairs at gaps above zero through six seconds.
An interrupted follow-up is counted separately and excluded from the
observed rate. Points sit at the mean starting gap of completed cases in
each one-second band. Curves and 95% bands use the supplied fit within the
observed gap range for each delay group. When no matching common-lap fit is
supplied, the observed rates still display.

The no-response panel shows stop–rival records by gap band. The shared handoff
has the numerator. Its denominator is pending a decision on which
opportunities to count with the same cohort rules. Both the denominator and
rate are left blank in the output CSV until that definition is agreed.
