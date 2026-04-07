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
```

Outputs:

- `output/benchmark_summary.csv` — wide table per variable × product.
- `output/figures/` — bar charts for key metrics.

## Interpretation

This is **product vs product** validation against a **common observational reference** (GridMET), not a controlled method intercomparison. LOCA2 and NEX use different algorithms, BC, and native grids than your OTBC + regrid + stochastic pipeline. See [`LITERATURE.md`](LITERATURE.md) for published context and safe citation language.

## Config

Paths and bounds live in [`config.py`](config.py). Override with environment variables if needed:

- `DOR_PRODUCT_ROOT` — folder containing `Stochastic_V8_Hybrid_*.npz` (default: blend 0.65 output dir).
- `WRC_DOR_SERVER` — UNC root for `Spatial_Downscaling` / `Data`.
