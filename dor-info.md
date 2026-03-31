# WRC_DOR Project Notes

## Project Overview
This is a climate downscaling and bias correction research project. The goal is to take coarse (~100km) GCM (Global Climate Model) data and produce high-resolution (4km) climate data over Iowa for use in hydrological modeling (WEPP).

**Supervisor:** Bhuwan Shah
**Server:** `\\abe-cylo\modelsdev\Projects\WRC_DOR\`
**Note:** `\\abe-cylo\Cylo-bshah\` exists but is not accessible to Elijah.

**Elijah's machine:** Ryzen 9800X3D, RX 7900 XTX, 32GB RAM, ethernet

---

## Current Research Priorities

1. ~~Verify that averaging extremes doesn't converge to an average of averages, even over a long period of time.~~ (Done — see `validate_tas_convergence/`)
2. **Nail down good spatial downscaling** ← active priority (Bhuwan's direction: get the stochastic downscaler right before experimenting with BC/downscaling order)
   - Literature review: find papers that use NN regridding for coarse→fine climate data (Bhuwan requested this specifically)
   - Understand and preserve the important parts of test8's stochastic downscaling when making changes
3. Compare: bias correction first vs. spatial downscaling first (deferred per Bhuwan — do this after downscaling is solid)
4. Stochastic noise: test empirically whether it brings data closer to reality and if it could disrupt things for WEPP.
5. Find/develop and test a bias correction method that takes terrain into account rather than assuming spatial uniformity. Is Iowa too flat for it to matter?
6. Explore post-correction consistency problems.
7. Use data from other organizations' pipelines to verify our pipeline outputs (Bhuwan mentioned this; data not yet on server).

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

**The double BC problem was never about the regridding step.** It was specifically about test7 using spatial interpolation toward observed GridMET values inside the downscaler — effectively a second observational correction on top of OTBC, causing overfitting. test8 avoids this by not interpolating toward observations inside the downscaler. The bilinear regridding is fine because it only uses GCM neighbor values, not observations.

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

### Local pipeline scripts (`C:\drops-of-resilience\bilinear-vs-nn-regridding\pipeline\scripts\`)
| Script | Purpose |
|--------|---------|
| `test8_bilinear.py` | test8 logic with hardcoded local paths pointing to `pipeline/data/bilinear/`. Outputs to `pipeline/output/bilinear/`. |
| `test8_nn.py` | test8 logic with hardcoded local paths pointing to `pipeline/data/nearest_neighbor/`. Outputs to `pipeline/output/nearest_neighbor/`. |
| `regrid_to_gridmet_bilinear.py` | Bilinear variant of regrid_to_gridmet.py. Conservative for PR, bilinear for others. Reads from `source_bc/`, outputs to `pipeline/data/bilinear/`. |
| `regrid_to_gridmet_nn.py` | NN variant of regrid_to_gridmet.py. Reads from `source_bc/`, outputs to `pipeline/data/nearest_neighbor/`. |
| `crop_bc_mpi_local.py` | Crops physics-corrected OTBC MPI data from server to Iowa. Outputs to `source_bc/`. |
| `crop_gridmet_local.py` | Crops GridMET CONUS .nc files from server to Iowa. Outputs to `gridmet_cropped/`. |
| `compare_regrid_methods.py` | Reads the metric CSVs output by test8_bilinear.py and test8_nn.py and diffs them to produce `regrid_comparison_report.html`. Does not reimplement metric logic — all KGE/RMSE/Ext99/Lag1 calculation is in test8 itself (`calculate_pooled_metrics`, `calculate_per_cell_summary_metrics`). |

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

### Server: `\\abe-cylo\modelsdev\Projects\WRC_DOR\`

The server has been reorganized into a clean `Data/` folder (as of March 2026):

```
Data/
├── Cropped_Iowa/
│   ├── Raw/          All 5 GCMs × all vars × yearly .npz (1850–2100, ~11K files)
│   ├── BC/           All 5 GCMs × 8 BC methods (mv_bcca, mv_ecc_schaake,
│   │                 mv_gaussian_copula, mv_mbcn_iterative, mv_otbc,
│   │                 mv_r2d2, mv_spatial_mbc, qdm)
│   ├── BCPC/         Same structure as BC/ but physics-corrected
│   ├── GridMET/      Cropped observations as .npz (9 vars, 1981–2014)
│   │                 vars: pr, tmmx, tmmn, srad, sph, vs, rmax, rmin, vpd
│   ├── Geospatial/   Cropped_CONUSElevation100m.tif, Cropped_GlobalCoastalDistance4km.tif
│   └── WindEffect/   WindEffect_Mean_01..12.npz (monthly)
│
├── Cropped_Colorado/
│   ├── Raw/          Same structure as Iowa (all 5 GCMs)
│   ├── BC/           All 5 GCMs × 8 BC methods
│   ├── BCPC/         Same as BC/ but physics-corrected
│   ├── Geospatial/
│   └── GridMET/
│
├── Regridded_Iowa/
│   ├── MPI/
│   │   └── mv_otbc/  Regridded 4km files (all 6 vars × historical + SSP585)
│   ├── geo_mask.npy
│   └── Regridded_Elevation_4km.npz
│
├── Gridmet-CONUS/    Full CONUS GridMET .nc files (one per var per year)
│                     vars: pr, tmmx, tmmn, srad, sph, vs, rmax, rmin, vpd, th
│                     years: 1979/1981–2014/2024 (varies by var)
│
└── 100km-ScenarioMIP/
    ├── ScenarioMIP-100km-CONUS_CMCC-ESM2-Greg-Unit/
    ├── ScenarioMIP-100km-CONUS_EC-Earth3-Greg-Unit/
    ├── ScenarioMIP-100km-CONUS_GFDL-CM4-Greg-Unit/
    ├── ScenarioMIP-100km-CONUS_MPI-ESM1-2-HR-Greg-Unit/
    └── ScenarioMIP-100km-CONUS_MRI-ESM2-0-Greg-Unit/
```

Also on server (older layout, still present):

| Data | Location |
|------|---------|
| Regridded GridMET + CMIP6 inputs (84×96, .dat memmaps) — **output of regrid_to_gridmet.py** | `Spatial_Downscaling\Data_Regrided_Gridmet\` |
| Wind effect static files | `Spatial_Downscaling\Data_WindEffect_Static\` |
| Physics-corrected BC outputs (CONUS scale, all 5 models, all BC methods) | `Bias_Correction\Data\Physics_Corrected_[MODEL]\` |
| BC publication materials | `Bias_Correction\Data\Manuscript\`, `Publication_*\`, etc. |

### Bhuwan's local machine (not on server)

| Data | Location |
|------|---------|
| Cropped bias-corrected for Iowa (MPI only) | `D:\Research\Projects\WRC\Cropped_BC_MPI\` |
| Cropped bias-corrected for Iowa (all models) | `D:\Research\Projects\WRC\Cropped_BC_All_Models\` |
| Regridded all-model inputs (.npy per model/var/scenario) | `E:\SpatialDownscaling\Data_Regrided_Gridmet_All_Models\` |
| Downscaling output (test6) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final\` |
| Downscaling output (test8) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final_v8\` |

### On .dat files vs .nc files
The `.dat` files on the server (`Data_Regrided_Gridmet/`) are the *output* of `regrid_to_gridmet.py` — the final processed format ready for test8 to memmap. They contain GCM inputs and GridMET targets already aligned on the same 4km grid, shape `(N_days, 6, 84, 96)`, float32. No coordinate metadata.

The GridMET `.nc` files (one per variable per year, with lat/lon coordinate axes) are an *input* to `regrid_to_gridmet.py`. These are now available on the server at `Data/Gridmet-CONUS/` (full CONUS, not cropped).

### GCM Models
- CMCC-ESM2
- EC-Earth3
- GFDL-CM4
- MPI-ESM1-2-HR (used for pipeline development — not the best GCM, good for stress-testing)
- MRI-ESM2-0

---

## Pipeline Assessment

**Strengths:**
- Double-BC problem identified and fixed (test8 removes test7's extra correction)
- Physics correction enforcing variable consistency (tasmax > tasmin, huss bounds)
- AR(1) noise in test8 captures temporal structure — more sophisticated than independent daily noise
- Schaake Shuffle for inter-variable rank correlations is best practice
- Semi-monthly windows (24 vs 12) better captures seasonal transitions
- Conservative regridding for PR preserves physical mass balance
- Pipeline architecture (interpolation + stochastic refinement) aligns with the community trajectory — ISIMIP3 independently arrived at the same three-step structure (see comparison below)

**Weaknesses / open questions:**
- PR and wind KGE near zero — pipeline isn't capturing day-to-day variability for those variables. Bhuwan acknowledged this as a weakness of the pipeline. Root cause not yet identified; not a regridding problem.
- ML/DL alternatives were explored but abandoned without a well-tuned benchmark comparison — stochastic approach hasn't been rigorously compared against a strong ML baseline

**Why MPI + OTBC:** Confirmed with Bhuwan as a good combination. OTBC is a strong bias correction technique. MPI was chosen deliberately because it is *not* the best-performing GCM — this makes it a good stress test for the pipeline (gives the pipeline something to fix). `Physics_Corrected_MPI` on the server contains ~8 BC methods (BCCA, ECC-Schaake, Gaussian Copula, MBCN iterative, OTBC, QDM, R2D2, Spatial MBC).

### Why Interpolation + Stochastic (Not Constructed Analogs)

Major downscaling pipelines fall into two camps:
1. **Interpolation-based** (NEX-GDDP, ISIMIP, Bhuwan): interpolate GCM → fine grid, then bias-correct and/or stochastically refine. All use bilinear.
2. **Observation-library / analog-based** (MACA, LOCA2, BCCA, BCCAQ2, GARD): use GCM as a search key into the historical observed record. Fine-scale spatial structure comes from real observed days, never from interpolating the GCM.

Bhuwan's pipeline uses interpolation + stochastic refinement. This is the right choice for several reasons:
- **Variable coverage:** Analogs are battle-tested for temperature and precipitation but much less so for radiation, humidity, pressure, and wind. Our pipeline handles 11 variables uniformly.
- **Extrapolation under climate change:** Delta/ratio mapping naturally extends beyond the historical range. Analog methods can only produce spatial patterns that have actually been observed — a fundamental limitation under novel future climates.
- **Clean separation of concerns:** Modular pipeline (crop → regrid → BC → stochastic downscaling → physics correction) makes each step independently debuggable. Analog methods merge regridding and spatial refinement into one step.
- **test8 already achieves what analogs aim for:** Per-pixel observed climatology (`m_obs`) supplies the fine-scale spatial structure. The GCM contributes only the daily anomaly. This is philosophically similar to analogs but implemented per-pixel rather than per-pattern, with the advantage of extrapolability.
- **Computational simplicity:** Bilinear interpolation of 11 variables is trivial. Analog search at 4km resolution across 11 variables simultaneously would be orders of magnitude more expensive.

### Bhuwan's Pipeline vs ISIMIP3

Both share the same three-step architecture:
1. Bias-correct at coarse GCM resolution
2. Bilinearly interpolate to fine grid
3. Apply stochastic spatial refinement

| | ISIMIP3 (Lange 2019) | Bhuwan (test8) |
|---|---------|----------------|
| Resolution jump | 2° → 0.5° (factor ~4) | ~1° → ~0.04° (factor ~25) |
| Stochastic method | MBCnSD (multivariate quantile mapping with random rotations) | Delta/ratio mapping + AR(1) noise + Schaake Shuffle |
| What the stochastic step does | Redistributes interpolated values within each coarse cell to match observed multivariate distributions; preserves coarse-cell aggregate | Applies per-pixel observed climatological offset/ratio, then adds correlated noise |
| Where spatial structure comes from | Emerges from stochastic redistribution matching observed distributions — bilinear starting values give cross-cell gradients to work with | Dominated by per-pixel observed climatology (`m_obs`); interpolated GCM contributes the daily anomaly, not the spatial pattern |
| Interpolation choice matters because... | MBCnSD redistributes the interpolated values — smoother input → smoother output (ISIMIP3 tested bilinear vs conservative, chose bilinear) | `m_obs` pins the spatial pattern; `in_val` only affects the anomaly; bilinear vs NN produced near-identical metrics empirically |

**Key insight:** In ISIMIP3, the interpolation method matters more because MBCnSD directly rearranges the interpolated values. In test8, the interpolation method matters less because the spatial structure is dominated by `m_obs`, not by the interpolated field. This is consistent with our empirical finding that bilinear and NN produced equivalent metrics.

---

## Key Context from Bhuwan

### From Teams messages (bhuwan-info.txt)
- ML/DL downscaling tested but failed: "Pure stochastic method works better than ML hybrids"
- EQM after ML didn't fix variance collapse either
- **Do not bias correct inside test6** — bias correction is done once (before downscaling), not twice
- test6 is the latest spatial downscaling script Bhuwan was working on
- Bias correction method: MV-QDM (multivariate)
- Iowa is flat but terrain-based bias correction may still be worth exploring (Bhuwan's suggestion)
- Only temperature is clearly slope-dependent; other variables may have other spatial features worth exploring

### From in-person meeting (March 2026)
- **MPI + OTBC confirmed as a good combination.** OTBC is a good BC technique. MPI is good for evaluation because it's not the strongest GCM — it gives the pipeline something to fix.
- **PR and wind KGE near zero** acknowledged as a weakness. Root cause not discussed in detail.
- **Focus on spatial downscaling first** before experimenting with BC-first vs downscale-first ordering. Make sure the important parts of the stochastic downscaler are preserved.
- **Literature review on NN regridding** — Bhuwan wants to see papers that use nearest-neighbor for coarse→fine climate regridding before committing to the switch. Review is substantially complete (`papers/nn-regridding-literature-review.md`): no operational pipeline uses NN, but our pipeline design makes the interpolation choice largely inconsequential.
- **External verification** — eventually use data from other organizations' pipelines to verify our outputs. Data not yet available on server.
- **Colorado data** now on server alongside Iowa — same structure (Raw, BC, BCPC, Geospatial, GridMET).

---

## Bilinear vs Nearest-Neighbor Comparison (Complete)

**Question:** Does bilinear interpolation in the 100km→4km regridding step produce better final downscaled output than nearest-neighbor?

**Setup:** Two parallel pipelines using identical test8 logic, differing only in regridding method. Both used the same physics-corrected OTBC source data (`source_bc/`) for a fair comparison. Validated on 1981–2014 period, Iowa domain, MPI-ESM1-2-HR.

**Original report (non-pr variables only):** `C:\drops-of-resilience\bilinear-vs-nn-regridding\regrid_comparison_report.html`

**Recommendation: Switch to NN for non-precipitation variables.** NN makes fewer assumptions than bilinear (no smoothing of GCM cell boundaries), matches or outperforms bilinear on the metrics that matter, and has a modest computational advantage. For precipitation, use conservative regridding (see pr 3-way comparison below).

**Literature review outcome:** No operational pipeline uses NN. Bilinear is the community default, but no one has quantitatively justified it — it is an unquestioned convention. ISIMIP3 is the only pipeline that questioned the interpolation method (bilinear vs conservative, qualitative only). Our experiment is the only quantitative comparison we've found. See `papers/nn-regridding-literature-review.md`.

**Precipitation 3-way comparison:** In the main NN vs bilinear pipeline, both paths used conservative regridding for pr. To answer Bhuwan's question about whether NN or bilinear could work for pr, we ran a separate 3-way test: conservative, bilinear, and NN regridding of pr only, each fed through test8's multiplicative downscaler.

**Result:** All three methods perform poorly on KGE (~0.03), Ext99 Bias% (−13% to −17%), and Lag1 Error (0.017–0.033) — all below "moderate" tier thresholds. Test8's stochastic downscaling overwhelms the regridding signal for precipitation. Bilinear shows ~3% lower RMSE, but this is a smoothing artifact: bilinear dampens variance (reducing squared error) while simultaneously worsening extreme underprediction (Ext99 −17.3% vs −13.3% for conservative/NN) and temporal autocorrelation (Lag1 error nearly 2x worse). The empirical metrics do not strongly differentiate the methods, but they offer no reason to deviate from the conventional practice of using conservative for pr, which is supported by physical reasoning (mass/flux conservation across grid cells).

**Report:** `C:\drops-of-resilience\bilinear-vs-nn-regridding\combined_regrid_report.html` (comprehensive report combining all metrics, charts, and qualitative plots for the full NN vs bilinear comparison and the pr 3-way comparison).

### Key findings by variable

| Variable | Verdict | Reasoning |
|----------|---------|-----------|
| tasmax | Toss-up → NN | No meaningful differences on any metric. NN preferred for fewer assumptions. |
| tasmin | Toss-up → NN | Same as tasmax. |
| rsds | Toss-up → NN | Same as tasmax. |
| huss | Toss-up → NN | Same as tasmax. |
| wind | NN | NN reduces Ext99 Bias% by 2.1pp (meaningful). Bilinear wins RMSE by 1.3% but Ext99 is more important for wind applications. |
| pr | Conservative | 3-way comparison (conservative / bilinear / NN) showed all methods perform poorly on KGE, Ext99, and Lag1 — test8's stochastic downscaling overwhelms the regridding signal. Bilinear has ~3% lower RMSE (a smoothing artifact, not a genuine advantage). Conservative recommended on physical grounds (mass/flux conservation). |

### Notes on interpretation
- **KGE and Ext99 are independent**: low KGE (poor day-to-day skill) does not invalidate an Ext99 result. Ext99 measures distributional properties across the full record; a model can fail at tracking specific days but still capture extremes reasonably.
- All "meaningful" differences are small (≤2pp absolute, ≤10% relative). Regridding method is not the dominant source of error in this pipeline.
- **RMSE can be misleading for pr**: bilinear's lower RMSE is a smoothing artifact — dampening variance reduces squared error but worsens extremes. For precipitation, Ext99 and Lag1 are more decision-relevant than RMSE.
- **Stochastic threshold instability**: Some variable–metric pairs sit very close to the meaningfulness thresholds (0.5% for RMSE, 5.0% for Lag1). Because test8 includes a stochastic component, small run-to-run variations can flip borderline cases (e.g. tasmin RMSE, rsds Lag1) across the threshold without any change in regridding. Any metric near the threshold is effectively negligible regardless of which side it falls on.

---

## Open Questions / To Investigate

- **Literature review: NN regridding** — **Substantially complete.** See `papers/nn-regridding-literature-review.md`. Conclusion: no operational pipeline uses NN; bilinear is the community default but no one has quantitatively justified it. ISIMIP3 is the only pipeline that questioned the interpolation method at all — they compared bilinear vs conservative qualitatively (one visual example, no skill metrics) and assumed smoother input to their stochastic step would be better. Our bilinear vs NN comparison is the only quantitative test on this question we've found, and it shows the methods are equivalent after test8. Awaiting Bhuwan's review.
- **Bilinear vs NN comparison**: **Complete.** Recommendation: switch to NN (non-precip variables). PR 3-way comparison also complete — all methods perform poorly; conservative recommended on physical grounds. See combined report at `bilinear-vs-nn-regridding/combined_regrid_report.html`.
- **Spatial downscaling quality** — Understand and preserve the critical components of test8's stochastic downscaling. Must be solid before exploring BC/downscaling ordering. (active)
- **BC-first vs downscale-first**: Deferred per Bhuwan — do this after spatial downscaling is nailed down.
- **PR and wind KGE near zero**: Acknowledged weakness. Root cause unknown.
- **Stochastic noise**: Has not been empirically tested for WEPP compatibility.
- **Terrain-based BC**: Not yet explored; Bhuwan suggested looking into whether DEM/slope/aspect are used in any existing BC methods.
- **External pipeline verification**: Bhuwan wants to eventually compare against other organizations' pipeline outputs. Data not yet on server.
