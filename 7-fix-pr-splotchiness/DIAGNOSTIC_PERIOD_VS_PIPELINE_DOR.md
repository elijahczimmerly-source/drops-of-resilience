# Period comparison vs pipeline DOR figures

## Question

Why does `figures/period-comparison/<period>/3_dor_output.png` look different from `figures/pr-splotch-side-by-side/pipeline_dor_MPI.png` (and from `pipeline_dor_MPI_blend065_experiment.png`)?

**Also:** Maps for **different calendar ranges** (e.g. 2006–2014 vs 1981–2014) answer **different** questions — short-window means can look alarming while **full historical** means align better with GridMET; see [`WORKLOG.md`](WORKLOG.md) §12 and [`../dor-info.md`](../dor-info.md).

## Answer (short)

1. **`plot_period_comparison.py` now uses the same color convention as pipeline default:** independent **2–98%** Blues per panel (`_vmin_vmax_one`), two colorbars, matching [`plot_validation_agg_mean_pr_obs_vs_gcm.py`](scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py). For the same period and inputs, `3_dor_output.png` should match pipeline `dor` styling (minor layout differences only).
2. **`pipeline_dor_MPI_blend065_experiment.png`** uses a **different DOR NPZ** (blend experiment), so the **values** are not the same as baseline `Stochastic_V8_Hybrid_pr.npz` even before color scale.

## Verified inputs (baseline MPI)

Both workflows use the same server paths as in `plot_period_comparison.py`:

- `GRIDMET_TARGETS`: `.../Regridded_Iowa/gridmet_targets_19810101-20141231.dat`
- `GEO_MASK`: `.../Regridded_Iowa/geo_mask.npy`
- `DOR_NPZ`: `.../Iowa_Downscaled/v8_2/Stochastic_V8_Hybrid_pr.npz`
- For 2006–2014: `val_start=2006-01-01`, `val_end=2014-12-31`

## Numeric scales (historical note)

`diagnose_period_vs_pipeline_dor.py` compared the **old** period-comparison policy (single min/max over six stage-3 arrays) to pipeline defaults. After aligning period plots to pipeline-style **2–98% per panel**, stage 3 scales in that script should match `_vmin_vmax_one` on each field for 2006–2014.

**Pipeline `--shared-scale`**: **2–98%** on the **concatenation** of both fields for that window only — still different from independent panels.

**Array check:** max absolute difference between period loaders and pipeline `cmd_dor` means on **land** should be **0** when day slicing and paths match.

## Related

- [`figures/pr-splotch-side-by-side/README.txt`](figures/pr-splotch-side-by-side/README.txt) — how each pipeline figure is produced.
