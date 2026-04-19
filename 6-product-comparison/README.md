# Product comparison (LOCA2 / NEX-GDDP vs DOR)

Self-contained benchmark: compare **your** stochastic downscaled output (**test8_v2 PR-intensity**, blend **0.65**) against **LOCA2** and **NASA NEX-GDDP-CMIP6** for **MPI-ESM1-2-HR**, on the **2006–2014** period and **Iowa GridMET grid** (216×192), using the same pooled metrics as `test8_v2_pr_intensity.py` (KGE, RMSE, Ext99 bias %, Lag1 error; WDF for pr).

**Why read `WORKLOG.md`:** Every non-obvious choice (regrid target, units, scoring for “best blend”) is documented there with alternatives considered.

## Requirements

- Conda env from repo root [`environment.yml`](../environment.yml): `drops-of-resilience` (Python 3.11, `xarray`, `netcdf4`, `numpy`, `pandas`, `matplotlib`).
- Read access to `\\abe-cylo\modelsdev\Projects\WRC_DOR\`.

## Run

```powershell
conda activate drops-of-resilience
cd c:\drops-of-resilience
python product-comparison\scripts\verify_blend_choice.py
python product-comparison\scripts\run_benchmark.py
python product-comparison\scripts\plot_validation_period.py
python product-comparison\scripts\diagnose_nex_rsds.py
```

`plot_validation_period.py` writes **validation-period figures** (same 2006–2014 alignment as `run_benchmark.py`): one **domain-mean daily time series** per variable (`GridMET`, **DOR blend 0.65**, **LOCA2** where available — `pr` / `tasmax` / `tasmin` only — and **NEX**), plus **side-by-side maps** (GridMET | DOR): **snapshot days** under `output/figures/dor side-by-side/individual days/`, **time-mean** and **seasonal-mean** (DJF/MAM/JJA/SON) maps under `output/figures/dor side-by-side/time aggregated/`. Snapshot dates come from `config.VALIDATION_MAP_DATES_FIXED` plus the day of **maximum domain-mean observed `pr`**. First run can be slow over UNC (same I/O profile as the benchmark).

`diagnose_nex_rsds.py` breaks down the large **NEX vs GridMET `rsds` mean bias** (native vs target grid, monthly, cloudiness regimes, metadata). See `WORKLOG.md` § “NEX rsds mean bias pinned down”.

Outputs:

- `output/benchmark_summary.csv` — wide table per variable × product.
- `output/figures/` — bar charts for key metrics; `validation_ts_<var>.png` at the `figures/` root from `plot_validation_period.py`; `dor side-by-side/individual days/validation_maps_<var>_<YYYYMMDD>.png` and `dor side-by-side/time aggregated/validation_agg_mean_<var>.png`, `validation_agg_seasonal_<var>.png`.
- After `diagnose_nex_rsds.py`: `output/nex_rsds_*.csv`, `nex_rsds_metadata.txt`, `nex_rsds_bias_native_vs_targetgrid.json`, and `figures/nex_rsds_*.png`.

## Interpretation

This is **product vs product** validation against a **common observational reference** (GridMET), not a controlled method intercomparison. LOCA2 and NEX use different algorithms, BC, and native grids than your OTBC + regrid + stochastic pipeline. See [`LITERATURE.md`](LITERATURE.md) for published context and safe citation language.

## Native-resolution suites (LOCA2 / NEX grids)

Parallel benchmarks and figures for evaluation on **LOCA2** and **NEX** native grids use `DOR_BENCHMARK_SUITE=gridmet_4km|loca2_native|nex_native` (default `gridmet_4km`). Outputs for non-legacy suites live under [`output/suites/`](output/suites/README.md). End-to-end orchestration: [`scripts/run_e2e_suite.py`](scripts/run_e2e_suite.py) (env `DOR_E2E_SUITES`). Details: [`WORKLOG_NATIVE_RESOLUTION.md`](WORKLOG_NATIVE_RESOLUTION.md).

## Config

Paths and bounds live in [`config.py`](config.py). Override with environment variables if needed:

- `DOR_PRODUCT_ROOT` — folder containing `Stochastic_V8_Hybrid_*.npz` (default: blend 0.65 output dir).
- `WRC_DOR_SERVER` — UNC root for `Spatial_Downscaling` / `Data`.
- `VALIDATION_MAP_DATES_FIXED` — calendar strings used for snapshot maps (winter / spring / summer / fall); the script appends one high–domain-mean-`pr` day from GridMET automatically.
- `FIG_VALIDATION_INDIVIDUAL_DAYS` / `FIG_VALIDATION_TIME_AGG` — output folders for snapshot vs aggregated side-by-side maps (see `config.py`).
