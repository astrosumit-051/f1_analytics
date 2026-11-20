# Pipeline (Partner A)

Builds the handoff tables in `data/derived/` from the raw snapshot. The raw data is
never committed; pass its path on the command line. Needs pandas and numpy.

```
python pipeline/build_pairs.py <path to F1_Pit_Wall_2018_2026>      # pairs.csv, no_response.csv (A1, #9)
python contracts/check_contract.py pairs data/derived/pairs.csv
python contracts/check_contract.py no_response data/derived/no_response.csv
```

`build_pairs.py` runs in about 80 seconds and prints row counts only, never outcome
rates, so it can be run without reading held-out outcomes. The choices it makes where
the contract is silent (order of exclusion reasons, how interrupted follow-ups are
classified) are in its docstring.
