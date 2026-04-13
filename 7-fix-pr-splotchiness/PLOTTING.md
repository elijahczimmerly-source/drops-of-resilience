# Canonical PR mean-map styling (“pipeline default”)

This folder’s side-by-side **precipitation** validation figures use a single agreed convention so maps are comparable and the **model/DOR** panel is not flattened by GridMET’s color range.

## Rule (default)

1. **Colormap:** `Blues`.
2. **Per-panel scaling:** **2nd–98th percentile** of finite values in **that** panel’s 2D field (`_vmin_vmax_one` in [`scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py`](scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py)).
3. **Two colorbars** — one per panel, same label as the obs-vs-GCM script: **Mean pr (mm day⁻¹)** (`VAR_YLABEL_PR`).

**Rationale:** Independent stretches let spatial structure show in **both** panels when their distributions differ (the usual case for GCM vs obs). This is the **default** behavior of:

- [`scripts/plot_gridmet_pipeline_side_by_side.py`](scripts/plot_gridmet_pipeline_side_by_side.py) **`dor`** (do **not** pass `--shared-scale`)
- [`scripts/plot_period_comparison.py`](scripts/plot_period_comparison.py) → figures under [`figures/period-comparison/`](figures/period-comparison/)
- [`scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py`](scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py) (drivers on 4 km grid; default is independent panels)

## Optional: one scale for both panels

When you need **strict** comparability of mm/day across left and right in **one** figure:

- `plot_gridmet_pipeline_side_by_side.py dor --shared-scale` — uses `_pair_vmin_vmax` from [`scripts/plot_validation_agg_mean_pr.py`](scripts/plot_validation_agg_mean_pr.py) (2–98% on **concatenated** finite values from both fields), one colorbar.

## Example commands

From repo root, with UNC paths reachable:

**Pipeline DOR vs GridMET (default styling):**

```text
python 7-fix-pr-splotchiness/scripts/plot_gridmet_pipeline_side_by_side.py dor ^
  --gridmet-targets \\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat ^
  --geo-mask \\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy ^
  --dor-npz \\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\Stochastic_V8_Hybrid_pr.npz ^
  --val-start 1981-01-01 --val-end 2014-12-31 ^
  --out 7-fix-pr-splotchiness/figures/pr-splotch-side-by-side/pipeline_dor_MPI_full_hist.png
```

Use `--val-start 2006-01-01 --val-end 2014-12-31` only when you explicitly want the **validation** window.

**All four pipeline stages × three calendar periods (12 PNGs):**

```text
python 7-fix-pr-splotchiness/scripts/plot_period_comparison.py
```

Outputs: `figures/period-comparison/<period>/{0..3}_*.png`.

## Aggregation window (read this before interpreting maps)

**Short** spans (e.g. **2006–2014**, ~9 years) can make DOR–GridMET **mean** maps look worse than **long** spans (e.g. **1981–2014**). For questions about **climatological** fidelity, prefer a **full historical** mean on the memmaps. See [`../dor-info.md`](../dor-info.md) (section *Time-mean PR maps*) and [`WORKLOG.md`](WORKLOG.md).

## Related files

- [`figures/pr-splotch-side-by-side/README.txt`](figures/pr-splotch-side-by-side/README.txt) — figure index and regeneration notes
- [`DIAGNOSTIC_PERIOD_VS_PIPELINE_DOR.md`](DIAGNOSTIC_PERIOD_VS_PIPELINE_DOR.md) — history of scale choices between scripts
