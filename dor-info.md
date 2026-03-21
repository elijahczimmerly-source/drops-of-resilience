# WRC_DOR Project Notes

## Project Overview
This is a climate downscaling and bias correction research project. The goal is to take coarse (~100km) GCM (Global Climate Model) data and produce high-resolution (4km) climate data over Iowa for use in hydrological modeling (WEPP).

**Supervisor:** Bhuwan Shah
**Server:** `\\abe-cylo\modelsdev\Projects\WRC_DOR\`
**Note:** `\\abe-cylo\Cylo-bshah\` exists but is not accessible to Elijah.

**Elijah's machine:** Ryzen 9800X3D, RX 7900 XTX, 32GB RAM, ethernet

---

## Current Research Priorities (from Priorities.txt)

1. Verify that averaging extremes doesn't converge to an average of averages, even over a long period of time.
2. **Compare: bias correction first vs. spatial downscaling first** ← active priority
3. Stochastic noise: test empirically whether it brings data closer to reality and if it could disrupt things for WEPP.
4. Find/develop and test a bias correction method that takes terrain into account rather than assuming spatial uniformity. Is Iowa too flat for it to matter?
5. Explore post-correction consistency problems.

---

## Pipeline (Standard Workflow)

```
1. Regrid observed GridMET (4km) → 100km GCM grid
         Script: regrid-gridmet-100km.py

2. Bias correct GCM at 100km using regridded historical observations
         Scripts: in Bias_Correction/ (MV-QDM / OTBC method)

3. Crop bias-corrected 100km data to Iowa region (with 3-degree buffer)
         Script: crop_2_scott_bc_mpi.py  (MPI only)
                 [multi-model equivalent likely exists for all 5 GCMs]

4. Regrid bias-corrected GCM from 100km → 4km (GridMET grid)
         Script: regrid_to_gridmet.py  (MPI only, uses xarray-regrid)
                 regrid_all_models_iowa.py  (all 5 GCMs)
         Method: conservative for PR, bilinear (linear) for all others
         THIS IS WHERE THE SPATIAL SMOOTHING HAPPENS (cell boundary discontinuities resolved)

5. Apply stochastic downscaling
         Script: test8.py  (current/latest — replaces test6)
                 test6.py  (previous version, still on server)
```

**Important:** The ML/DL downscaling scripts (stage1_ml_downscaling.py, stage1_dl_super_resolution.py, etc.) were experimental and **ultimately failed/abandoned**. Bhuwan confirmed: "Pure stochastic method works better than ML hybrids."

**OTBC** — appears in code comments and Bhuwan's messages. Likely stands for Optimal Transport Bias Correction (the MV-QDM multivariate method used in step 2). **Unconfirmed — verify with Bhuwan or Bias_Correction scripts.**

**Physics correction** — a post-processing step applied after bias correction to enforce physical consistency between variables. Confirmed from `generate_physics_impact_table.py` and file naming. Specifically corrects: (1) huss values that exceed physically plausible bounds, and (2) tasmax/tasmin inconsistencies (e.g., tasmax < tasmin). Tracked via "Violation_Rate_%" (% of space-time points needing correction) and "Tmax_Consistency_Fixed_%". Applied to all BC methods, not just OTBC. Physics-corrected outputs are stored separately from the plain BC outputs and are named `*_physics_corrected.npz`. Bhuwan described these as "bias corrected + physics corrected" — the version used in the existing pipeline (referenced in test7 context as "OTBC bias corrected and physics corrected outputs").

**On double BC:** test7 (not on server) used OTBC-corrected inputs AND then applied its own spatial climatology adjustment (using observed GridMET means) on top — two rounds of bias correction, causing overfitting. The double BC concern is specifically about applying a second observationally-derived correction, not about interpolation per se. test8 removes test7's extra correction.

**On interpolation in regrid_to_gridmet.py:** The bilinear interpolation is staying in the new pipeline. Bhuwan confirmed: you have to regrid 100km → 4km somehow; conservative for PR, bilinear for others. Critically, GridMET is only used as a grid skeleton (target lat/lon coordinates) — the bilinear interpolation uses surrounding GCM neighbor values, not observed GridMET values. This is why it does not count as bias correction — it's pure spatial resampling with no observational correction.

**The double BC problem was never about the regridding step.** It was specifically about test7 using spatial interpolation toward observed GridMET values inside the downscaler — effectively a second observational correction on top of OTBC, causing overfitting. test9 avoids this by not interpolating toward observations inside the downscaler. The bilinear regridding is fine because it only uses GCM neighbor values, not observations.

---

## Key Scripts

### `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Scripts\`

| Script | Purpose |
|--------|---------|
| `regrid-gridmet-100km.py` | Regrids GridMET 4km → 100km GCM grid using xESMF. Conservative regridding for PR/fluxes, bilinear for state variables. Pre-builds weight matrices for efficiency. |
| `crop_gridmet.py` | Crops GridMET 4km data to Iowa region (39.5–44.5°N, -97.5 to -89.5°W). No regridding. |
| `crop_geospatial.py` | Crops GeoTIFF rasters (elevation, coastal distance) to Iowa domain using rasterio. |
| `crop_2_scott_bc_mpi.py` | Crops bias-corrected MPI model output (100km) to Iowa region with 3° buffer. Saves as `Cropped_*.npz`. References `regrid_to_gridmet.py` as the next step. |
| `regrid_to_gridmet.py` | Regrids bias-corrected MPI GCM from 100km → 4km GridMET grid. Also builds `geo_static.npy` and `geo_mask.npy`. Uses xarray-regrid. |
| `regrid_all_models_iowa.py` | Multi-model version of regrid_to_gridmet.py — handles all 5 GCMs (CMCC, EC, GFDL, MPI, MRI). Output to `E:\SpatialDownscaling\Data_Regrided_Gridmet_All_Models\`. References `test7_v2.py`. |
| `test8.py` | **Current/latest stochastic downscaling script** — replaces test6. See details below. |
| `test6.py` | Previous stochastic downscaling script. Still on server. |
| `test1.py`–`test5.py` | Earlier iterations of the stochastic downscaler (development history). |
| `stage1_ml_downscaling.py` | ML downscaling (HistGradientBoosting) — **abandoned/experimental** |
| `stage1_dl_super_resolution.py` | cGAN super-resolution — **abandoned/experimental** |
| `stage1_dl_super_resolution_2stage.py` | Two-stage cGAN — **abandoned/experimental** |
| `stage1_eqm_postprocessor.py` | EQM post-processing for ML outputs — **abandoned/experimental** |

### `\\abe-cylo\modelsdev\Projects\WRC_DOR\Bias_Correction\Scripts\`
Only plotting/analysis scripts (no pipeline scripts):
`plot_ensemble_consensus.py`, `plot_physics_analysis.py`, `generate_physics_impact_table.py`, `generate_publication_metrics.py`, `generate_publication_tables.py`, `plot_publication_figures_with_csv.py`, `plot_fig1.py`, `plot_metric_summary.py`

### Also note
- There is a **test7 / test7_v2.py** referenced in `regrid_all_models_iowa.py` — not yet found or read. On Bhuwan's machine.
- **`gridmet_paths.py`** — shared config module imported by `regrid_to_gridmet.py` and `test8.py`. Provides `GRIDMET_DATA_DIR`. On Bhuwan's machine, not on server. Not needed for local pipeline scripts (paths are hardcoded in those).

### Local pipeline scripts (`C:\drops-of-resilience\pipeline\scripts\`)
| Script | Purpose |
|--------|---------|
| `test8_bilinear.py` | test8 logic with hardcoded local paths pointing to `pipeline/data/bilinear/`. Outputs to `pipeline/output/bilinear/`. Ready to run. |
| `test8_nn.py` | test8 logic with hardcoded local paths pointing to `pipeline/data/nearest_neighbor/`. Outputs to `pipeline/output/nearest_neighbor/`. Needs NN-regridded .dat files first. |
| `regrid_to_gridmet_nn.py` | Nearest-neighbor variant of regrid_to_gridmet.py. Reads `Cropped_BC_MPI/*.npz` from `pipeline/source_bc/` and GridMET .nc files from Bhuwan's machine. Writes .dat files to `pipeline/data/nearest_neighbor/`. Blocked on Bhuwan sharing source files. |

---

## test8.py — Current/Latest Stochastic Downscaler

**Title in script:** "V8: STOCHASTIC SPATIAL DISAGGREGATION (OTBC PRESERVING)"
**Replaces:** test6.py
**Key motivation:** test6's scaling approach was a form of bias correction; test8 avoids that to prevent double-BC.

### What's new vs test6
| Feature | test6 | test8 |
|---------|-------|-------|
| Continuous downscaling | Pure delta `y = m_o + (in - m_g)` | Same core delta, but calibrates `resid_std` separately for noise scaling |
| Noise model | Independent per day | **AR(1) autocorrelation** (ρ=0.8 additive, ρ=0.5 multiplicative) — consecutive days correlated |
| Temporal windows | 12 monthly | **24 semi-monthly** (tighter seasonal resolution) |
| Lapse-rate correction | None | Optional elevation correction for tasmax/tasmin (disabled by default: `USE_GEO_STATIC=False`) |
| Multivariate consistency | Frobenius norm only | **Schaake Shuffle** applied post-downscaling to restore inter-variable rank correlations |
| Validation metrics | KGE, RMSE, extremes, WDF | Adds **lag-1 autocorrelation error**, per-cell KGE/RMSE, domain-mean timeseries RMSE |
| Run modes | Stochastic only | **Both stochastic and deterministic** (noise=0) |
| Output dir | `Data_Stochastic_Kriging_Final` | `Data_Stochastic_Kriging_Final_v8` |

### Core Logic (same two pathways as test6)

**Additive (`StochasticSpatialDisaggregatorAdditive`)** — tasmax, tasmin, rsds, huss:
- Calibrates: `spatial_delta[p] = m_obs - m_gcm` per semi-monthly period per pixel
- Calibrates: `resid_std[p]` = std of daily residuals after applying delta
- Inference: `y = in_val + delta + AR1_noise * resid_std * 0.06`

**Multiplicative (`StochasticSpatialDisaggregatorMultiplicative`)** — pr, wind:
- Calibrates: `spatial_ratio[p] = clip(m_obs / m_gcm, 0.05, 20)`
- Calibrates: `resid_cv[p]` and WDF threshold
- Inference: `y = in_val * ratio * (1 + AR1_noise * resid_cv * 0.15)`

### Imports from `gridmet_paths.py`
Both `regrid_to_gridmet.py` and `test8.py` import `GRIDMET_DATA_DIR` from a shared module `gridmet_paths.py`. This file must exist locally but is not on the server.

### Note on "no interpolation"
Bhuwan said test8 uses "no interpolation" — this refers to not doing any *additional* interpolation/smoothing within the downscaling step itself. The inputs to test8 are still bilinearly interpolated (by `regrid_to_gridmet.py`). The comment in the code (line 238) says: "inputs = 100km OTBC bilinearly interpolated to 4km".

---

## test6.py — Previous Stochastic Downscaler

**Title in script:** "THE HYBRID PHYSICAL ENGINE"
**Method:** Stochastic regression-based. No ML.
**Note from Bhuwan:** Inputs to test6 should be bias-corrected already (don't bias correct again inside test6 — that would be doing it twice).

### Data
- **Input:** `cmip6_inputs_*.dat` — CMIP6 data on the 84×96 grid, float32 memmap
- **Target (training):** `gridmet_targets_*.dat` — GridMET observations, same grid
- **Static features:** `geo_static.npy` (elevation, slope, aspect, monthly wind climatology), `geo_mask.npy`
- **Location (as hardcoded in script):** `E:\SpatialDownscaling\Data_Regrided_Gridmet\` (Bhuwan's local E: drive)
- **Mirror on server:** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Data_Regrided_Gridmet\`
- **Output dir:** `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final\`
- **Grid:** 84 rows × 96 cols, 6 variables (pr, tasmax, tasmin, rsds, wind, huss)
- **Periods:** Historical 1981–2014 (12,418 days), Early 1850–1980, Future SSP585 2015–2100

### Training / Test Split
- Train: 1981–2005
- Test: 2006–2014

### Two Downscaling Pathways

**Continuous variables** (tasmax, tasmin, rsds, huss) — `ContinuousDownscaler`:
- **Pure delta/anomaly mapping**: `y_bc = m_o + (in_val - m_g)`
  - Shifts GCM anomaly onto the observed climatological mean; slope is exactly 1.0
  - No regression, no bi-partite scaling (LinearRegression is imported but unused)
- Monthly obs mean (`m_o`), GCM mean (`m_g`), and obs std (`std_o`) are precomputed per pixel per month from the training period
- Adds spatially correlated Gaussian noise: `noise × std_o × 0.10`

**Zero-inflated variables** (pr, wind) — `MultiplicativeDownscaler`:
- Dynamic intensity-dependent multiplicative ratios:
  - `storm_intensity_weight = clip(in_val / gcm_95th, 0, 1)`
  - `ratio_dynamic = r_base + (r_ext - r_base) × storm_intensity_weight`
  - `y_bc = in_val × ratio_dynamic`
- Calibrated: `r_base = mean_tar / mean_in`, `r_ext = p95_tar / p95_in` (clipped)
- Multiplicative noise: `1.0 + noise × cv × intensity` (intensity = 0.20 for PR, 0.15 for wind), clipped [0.5, 2.0]
- Precipitation: post-scale WDF threshold — calibrated per pixel/month to match observed wet-day frequency; values below threshold set to 0, then anything < 0.1mm also set to 0

### Stochastic Noise
- FFT-filtered spatially correlated Gaussian noise
- Correlation length ~5 pixels (~50–100km)
- Deterministically seeded per day: `seed = year*10000 + month*100 + day` (reproducible)

### Output
- `Stochastic_4km_[VAR]_1981_2014.npz`, `..._1850_1980_...`, `..._SSP585_2015_2100_...`
- Metrics: `Overall_Univariate_Metrics.csv`, `Overall_Multivariate_Metrics.csv` (Frobenius norm)

### Evolution of test scripts
| Script | Key change |
|--------|-----------|
| test1 | Basic regression + kriging-style noise |
| test2 | Better documented dual-pathway |
| test3 | Added Yeo-Johnson power transform for extremes |
| test4 | Variance inflation factor scaling |
| test5 | Iterated toward pure delta approach |
| test6 | Pure delta anomaly mapping for continuous vars, dynamic ratio for PR/wind + full diagnostic plotting, publication-ready figures |

**Note:** The agent's earlier description claiming test6 uses "bi-partite tail-matched scaling" and "linear regression" was inaccurate. The actual ContinuousDownscaler is a pure delta mapping (anomaly at slope 1.0). LinearRegression is imported but never called.

---

## Data Locations

| Data | Location |
|------|---------|
| Regridded GridMET + CMIP6 inputs (84×96, .dat memmaps) — **output of regrid_to_gridmet.py** | `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Data_Regrided_Gridmet\` |
| Bias-corrected outputs (MV-QDM, CONUS scale) | `\\{Bhuwan's IP}\cylo-bshah\Bias-Correction\BC-Outputs-MV-QDM-Fixed\` (not accessible) |
| Physics-corrected BC outputs (CONUS scale, all 5 models, all BC methods) | `\\abe-cylo\modelsdev\Projects\WRC_DOR\Bias_Correction\Data\Physics_Corrected_[MODEL]\` — subfolders per BC method, files named `{var}_GROUP-..._METHOD-mv_otbc_..._physics_corrected.npz`. **Needs cropping before use.** |
| Cropped bias-corrected for Iowa (MPI only) | `D:\Research\Projects\WRC\Cropped_BC_MPI\` (Bhuwan's local) |
| Cropped bias-corrected for Iowa (all models) | `D:\Research\Projects\WRC\Cropped_BC_All_Models\` (Bhuwan's local) |
| Cropped GridMET observations (.nc, one file per variable per year) | `D:\Research\Projects\WRC\Cropped_GridMET\` (Bhuwan's local — not on server) |
| Regridded all-model inputs (.npy per model/var/scenario) | `E:\SpatialDownscaling\Data_Regrided_Gridmet_All_Models\` (Bhuwan's local) |
| Downscaling output (test6) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final\` (Bhuwan's local) |
| Downscaling output (test8) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final_v8\` (Bhuwan's local) |
| Wind effect static files | `E:\SpatialDownscaling\Data_WindEffect_Static\` (Bhuwan's local) |
| 100km ScenarioMIP model data | `\\abe-cylo\modelsdev\Projects\WRC_DOR\100km-ScenarioMIP\` (5 GCM subfolders, NPZ files) |

### On .dat files vs .nc files
The `.dat` files on the server are the *output* of `regrid_to_gridmet.py` — the final processed format ready for test8 to memmap. They contain GCM inputs and GridMET targets already aligned on the same 4km grid, shape `(N_days, 6, 84, 96)`, float32. No coordinate metadata.

The GridMET `.nc` files (one per variable per year, with lat/lon coordinate axes) are an *input* to `regrid_to_gridmet.py`, consumed on Bhuwan's machine and never uploaded to the server. We have the output but not the input.

**Implication for NN comparison:** `regrid_to_gridmet_nn.py` needs the GridMET `.nc` files only to extract the target lat/lon coordinate arrays for xarray-regrid. A potential workaround is to reconstruct these arrays from known Iowa GridMET grid parameters (bounds ~39.5-44.5°N, -97.5 to -89.5°W, spacing ~0.0417°) rather than reading them from file — not yet attempted.

### GCM Models in 100km-ScenarioMIP
- CMCC-ESM2
- EC-Earth3
- GFDL-CM4
- MPI-ESM1-2-HR
- MRI-ESM2-0

---

## Key Context from Bhuwan (bhuwan-info.txt)

- ML/DL downscaling tested but failed: "Pure stochastic method works better than ML hybrids"
- EQM after ML didn't fix variance collapse either
- **Do not bias correct inside test6** — bias correction is done once (before downscaling), not twice
- test6 is the latest spatial downscaling script Bhuwan was working on
- Bias correction method: MV-QDM (multivariate)
- Iowa is flat but terrain-based bias correction may still be worth exploring (Bhuwan's suggestion)
- Only temperature is clearly slope-dependent; other variables may have other spatial features worth exploring

---

## Bilinear vs Nearest-Neighbor Comparison (Complete)

**Question:** Does bilinear interpolation in the 100km→4km regridding step produce better final downscaled output than nearest-neighbor?

**Setup:** Two parallel pipelines using identical test8 logic, differing only in regridding method. Both used the same physics-corrected OTBC source data (`source_bc/`) for a fair comparison. Validated on 1981–2014 period, Iowa domain, MPI-ESM1-2-HR.

**Report:** `C:\drops-of-resilience\week3\regrid_comparison_report.html`

**Recommendation: Switch to NN for all variables.** NN makes fewer assumptions than bilinear (no smoothing of GCM cell boundaries), matches or outperforms bilinear on the metrics that matter, and has a modest computational advantage. The one area of uncertainty (pr Lag1) warrants follow-up with multiple seeds but is not a reason to retain bilinear.

**Caveat for Bhuwan:** Bilinear has precedent in the literature for coarse-to-fine regridding and the switch requires justification in a paper. "Metrics were equivalent, NN makes fewer assumptions" is defensible but less intuitive to reviewers than bilinear.

### Key findings by variable

| Variable | Verdict | Reasoning |
|----------|---------|-----------|
| tasmax | Toss-up → NN | No meaningful differences on any metric. NN preferred for fewer assumptions. |
| tasmin | Toss-up → NN | Same as tasmax. |
| rsds | Toss-up → NN | Same as tasmax. |
| huss | Toss-up → NN | Same as tasmax. |
| wind | NN | NN reduces Ext99 Bias% by 2.1pp (meaningful). Bilinear wins RMSE by 1.3% but Ext99 is more important for wind applications. |
| pr | NN (provisional) | Both methods score near-zero KGE — regridding is not the bottleneck. NN wins Lag1 Error by 9.5% (only meaningful result), but this should be verified across multiple seeds given pr's poor overall skill. |

### Notes on interpretation
- **KGE and Ext99 are independent**: low KGE (poor day-to-day skill) does not invalidate an Ext99 result. Ext99 measures distributional properties across the full record; a model can fail at tracking specific days but still capture extremes reasonably.
- **Lag1 at near-zero KGE**: when KGE ≈ 0, model outputs are largely noise. A Lag1 win in this regime may not be structural — could flip with a different random seed.
- All "meaningful" differences are small (≤2pp absolute, ≤10% relative). Regridding method is not the dominant source of error in this pipeline.

---

## Open Questions / To Investigate

- **Bilinear vs NN comparison (Priority sub-task)**: **Complete.** Recommendation: switch to NN. See report at `week3/regrid_comparison_report.html`. Pending: verify pr Lag1 result across multiple seeds.
- **Priority #2 (BC-first vs downscale-first)**: Deferred until downscaling method is validated.
- **Stochastic noise (Priority #3)**: Has not been empirically tested for WEPP compatibility.
- **Terrain-based BC (Priority #4)**: Not yet explored; Bhuwan suggested looking into whether DEM/slope/aspect are used in any existing BC methods.
