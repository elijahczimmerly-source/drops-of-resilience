# WRC_DOR Project Notes

## Local repository layout

Top-level work folders use numeric prefixes: `1-week1`, `2-validate-tas-convergence`, `3-bilinear-vs-nn-regridding`, `4-test8-v2-pr-intensity`, `5-bias-correction-validation`, `6-product-comparison`, `7-fix-pr-splotchiness` (includes [`PLOTTING.md`](7-fix-pr-splotchiness/PLOTTING.md) for PR mean-map conventions), `8-WDF-overprediction-fix`, `9-additional-pr-RMSE-fixes`, `9-fix-pr-splotchiness-attempt-2` (blend 0.62 + ratio smooth σ=1 experiment — **negative result**, archived; see [`FINDINGS.md`](9-fix-pr-splotchiness-attempt-2/FINDINGS.md)), `10-improve-wind`. **Spatial downscaling (test8 line) lives in the repo-root [`pipeline/`](pipeline/)** — scripts, README, and (when run) `output/test8_v2/`, `output/test8_v3/`, and `output/test8_v4/`. **100 km→4 km regridding** harness scripts live under [`pipeline/scripts/regrid/`](pipeline/scripts/regrid/) (see README there); the folder `3-bilinear-vs-nn-regridding/pipeline/` retains **deprecated stubs** that forward to those paths for the bilinear vs NN comparison study, not the main stochastic pipeline. Ignore any stray root-level `pipeline/output/` from older experiments unless documented elsewhere. Paths in this file use these names; older chat logs may omit the prefix or use outdated numbers (e.g. `9-improve-wind` → now `10-improve-wind`).

### Clarifications (avoid common confusion)

| Topic | What to know |
|-------|----------------|
| **Server `test8_v2.py` vs local [`pipeline/scripts/test8_v2.py`](pipeline/scripts/test8_v2.py)** | Bhuwan’s file on `\\abe-cylo\...\Spatial_Downscaling\Scripts\test8_v2.py` is the lab canonical script. The repo **entry point** runs **[`_test8_sd_impl.py`](pipeline/scripts/_test8_sd_impl.py)** with Bhuwan-parity-oriented env defaults — the same fork used for v3/v4, **not** a byte copy of the server file. |
| **`_test8_sd_impl.py` / `dor_test8_lock.py`** | **`_test8_sd_impl.py`** holds the full stochastic pipeline (calibration, AR noise, Schaake, metrics, NPZ output). `test8_v2.py` / `v3` / `v4` only set `DOR_PIPELINE_ID` and env, then execute the impl. **`dor_test8_lock.py`** is a Windows single-instance lock so two long runs don’t share the same output directory. |
| **`6-product-comparison` and regridding** | **[`run_benchmark.py`](6-product-comparison/scripts/run_benchmark.py)** does **not** call [`regrid_to_gridmet.py`](#key-scripts) or [`pipeline/scripts/regrid/`](pipeline/scripts/regrid/). It reads **DOR** from existing `Stochastic_V8_Hybrid_*.npz` (built when you ran the downscaler on memmaps whose **GCM inputs** were produced earlier by server/local regrid). It reads **LOCA2** / **NEX** NetCDFs and **interpolates** them onto the Iowa GridMET grid in code ([`load_loca2.py`](6-product-comparison/scripts/load_loca2.py), [`load_nex.py`](6-product-comparison/scripts/load_nex.py)). **Obs** = GridMET targets memmap. |
| **What the product benchmark does *not* measure** | It compares **2006–2014 simulated vs GridMET** (KGE, RMSE, Ext99, etc.). It does **not** assess preservation of a **climate change signal** (e.g. future minus historical vs other products); that would require a separate analysis with SSP outputs. |
| **LOCA2 vs NEX native grids** | Before interpolation to GridMET, archives are roughly **LOCA2 ~6 km** (≈1/16°) and **NEX-GDDP-CMIP6 0.25° × 0.25°** (~25–28 km at Iowa). See [`6-product-comparison/LITERATURE.md`](6-product-comparison/LITERATURE.md). The benchmark still evaluates everyone on the **same** Iowa 216×192 GridMET grid. |

### Where data lives (repo, local drives, server)

**All three are valid places to find or stage data**—use whichever matches how the machine is set up:

| Location | Typical role |
|----------|----------------|
| **`C:\drops-of-resilience`** | Git repo: code, small outputs, task folders, `pipeline/output/` for runs, junctions to other trees. May point at memmaps via env vars or a **local cache path** (see below)—the repo itself usually does **not** hold multi‑GB `.dat` memmaps. |
| **Local drives (e.g. `D:\`, or another volume)** | **Preferred for large inputs and outputs**: copy server `Regridded_Iowa` memmaps, GridMET crop NPZs, and pipeline write targets here when you need speed and stable I/O. Example cache layout: `D:\drops-resilience-data\WRC_DOR_cache\` mirroring UNC paths (see [`6-product-comparison/config.py`](6-product-comparison/config.py) `DOR_LOCAL_WRC_CACHE` and `6-product-comparison/WORKLOG.md`). |
| **`\\abe-cylo\modelsdev\Projects\WRC_DOR\` (server)** | **Canonical source of truth** for project data: `Data/`, `Spatial_Downscaling/`, `Regridded_Iowa`, downscaled products, etc. Use when browsing, verifying paths, or **copying** files to a local machine. |

**Pipeline runs (test8 / `_test8_sd_impl`, regrid jobs, anything reading multi‑GB memmaps for hours):** **Copy the required inputs from the server onto this machine first**, then point `DOR_TEST8_*` / `DOR_TEST8_PR_DATA_DIR` (and related env vars) at those **local** paths. Running entirely over UNC may work for spot checks but is slower, more sensitive to disconnects, and risks saturating the link—**local disk is the default expectation for full pipeline runs.**

**Choosing a drive (C:, D:, or another volume):** Decide from **(1)** how directories are organized (e.g. dedicated `D:\…\WRC_DOR_cache\` vs repo-adjacent folders on `C:\`) and **(2)** **how much free space** is available **before** you start. Memmaps and full stochastic outputs are **tens of gigabytes per stack**; a single run can consume **many GB** of writes. **Check free space and leave comfortable headroom** so the job does not **run out of storage mid-run** (which corrupts or truncates outputs and wastes runtime). If one volume is tight, use another or free space first—**never assume** the default path will fit without checking.

### Server path verification (AI agents)

The canonical UNC is `\\abe-cylo\modelsdev\Projects\WRC_DOR\`. It is the **authoritative archive**; for heavy local runs, copy from here to `C:\` or `D:\` as described in **Where data lives (repo, local drives, server)** above. Access requires **VPN / domain reachability** (and sometimes explicit credentials). On some machines, `\\abe-cylo` alone does not enumerate even when `\\abe-cylo\modelsdev\Projects\WRC_DOR\` works—**use the full path** in Explorer or scripts.

**Spot-check (2026-04-17):** Top-level folders present: `Bias_Correction/`, `Data/`, `Spatial_Downscaling/`. Under `Data/`: `100km-ScenarioMIP/`, `Cropped_Colorado/`, `Cropped_Iowa/`, `Gridmet-CONUS/`, `Regridded_Iowa/` — **note:** `Data/Regridded_Iowa/` contains only `MPI/`, `Regridded_Elevation_4km.npz`, and `geo_mask.npy` (no `geo_static.npy` or `gridmet_targets_*.dat`). Under `Spatial_Downscaling/`: `Data_Regrided_Gridmet/`, `Data_WindEffect_Static/`, `Downscaled_Products/`, `Scripts/` (includes `test8.py`, `test8_v2.py`, `regrid_to_gridmet.py`, etc.), `test8_v2/` (`Iowa_Downscaled/`, `Regridded_Iowa/`). **`Spatial_Downscaling/test8_v2/Regridded_Iowa/`** contains `MPI/`, `Regridded_Elevation_4km.npz`, `geo_mask.npy`, **`geo_static.npy`**, and **`gridmet_targets_19810101-20141231.dat`** — this is the complete dataset for test8_v2 work. Under `Bias_Correction/Data/`: `BC-Outputs-MV-Unified/`, `BC-Outputs-Univariate-QDM/`, `Manuscript/`, `Physics_Corrected_Unified/`. Re-verify after major reorganizations.

## Project Overview
This is a climate downscaling and bias correction research project. The goal is to take coarse (~100km) GCM (Global Climate Model) data and produce high-resolution (4km) climate data over Iowa for use in hydrological modeling (WEPP).

**Supervisor:** Bhuwan Shah
**Server:** `\\abe-cylo\modelsdev\Projects\WRC_DOR\`
**Note:** `\\abe-cylo\Cylo-bshah\` exists but is not accessible to Elijah.

**Elijah's machine:** Ryzen 9800X3D, RX 7900 XTX, 32GB RAM, ethernet

---

## Current Research Priorities

1. ~~Verify that averaging extremes doesn't converge to an average of averages, even over a long period of time.~~ (Done — see `2-validate-tas-convergence/`)
2. **Nail down good spatial downscaling** ← active priority (Bhuwan's direction: get the stochastic downscaler right before experimenting with BC/downscaling order)
   - Literature review: find papers that use NN regridding for coarse→fine climate data (Bhuwan requested this specifically)
   - Understand and preserve the important parts of test8's stochastic downscaling when making changes
3. Compare: bias correction first vs. spatial downscaling first (deferred per Bhuwan — do this after downscaling is solid)
4. Stochastic noise: test empirically whether it brings data closer to reality and if it could disrupt things for WEPP.
5. Find/develop and test a bias correction method that takes terrain into account rather than assuming spatial uniformity. Is Iowa too flat for it to matter?
6. Explore post-correction consistency problems.
7. ~~Use data from other organizations' pipelines to verify our pipeline outputs~~ — **Done (MPI)** — see [`6-product-comparison/`](6-product-comparison/) and server `Spatial_Downscaling/Downscaled_Products/`.

---

## Pipeline (Standard Workflow)

**Inputs:** Before a long local run, **copy required memmaps and masks from the server** (or another source) onto the machine—see **Where data lives (repo, local drives, server)**—and pick a drive with **enough free space** so the run cannot exhaust disk mid-pipeline.

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
         Method (test8 / pre-test8_v2 default in `regrid_to_gridmet.py`): conservative for PR, bilinear (linear) for all others
         **Method actually used to produce the test8_v2 inputs (`Regridded_Iowa/MPI/mv_otbc/`): bilinear for PR.** Bhuwan confirmed this in chat (`bhuwan-info.txt` line 414: "I also used bilinear interpolation for precipitation. Which worked well for extremes"). For the other 5 variables in test8_v2, Bhuwan was unsure when asked and said he'd check (`bhuwan-info.txt` line 479: "I'm not sure about the other variables, let me check") and never followed up — assumption is bilinear via the same `regrid_to_gridmet.py` defaults, but this is **not explicitly confirmed**. Any test8_v2-comparable rerun should use bilinear for all variables until Bhuwan says otherwise.
         THIS IS WHERE THE SPATIAL SMOOTHING HAPPENS (cell boundary discontinuities resolved)

5. Apply stochastic downscaling
         Script: test8.py  (current/latest — replaces test6)
                 test6.py  (previous version, still on server)
         Local repo: [`pipeline/scripts/test8_v4.py`](pipeline/scripts/test8_v4.py) — Bhuwan **test8_v2**-based fork with PR intensity + tuned WDF (see **Local: test8 PR intensity pipeline** below).
```

**Important:** The ML/DL downscaling scripts (stage1_ml_downscaling.py, stage1_dl_super_resolution.py, etc.) were experimental and **ultimately failed/abandoned**. Bhuwan confirmed: "Pure stochastic method works better than ML hybrids."

**OTBC** — Optimal Transport Bias Correction. Confirmed as the selected production BC method: `test8.py` and `test8_v2.py` both consume `mv_otbc` output (line 45 of test8_v2: `F_INPUTS_DIR = os.path.join(BASE_DIR, "MPI", "mv_otbc")`). Script headers: "Stochastic Spatial Disaggregation (Post-OTBC)". Among 8 evaluated BC methods, OTBC ranks #2 in Frobenius norm (inter-variable dependence), #3 in MAE, #4 in lag-1 error — consistently near the top with no weakness on any dimension.

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
| `test8_v2.py` | **Bhuwan's newest iteration** (last modified 3/30/2026). Reads from `Regridded_Iowa/MPI/mv_otbc/` (new data layout). Outputs to `E:\SpatialDownscaling\Iowa_Downscaled\v8_2\`. See detailed comparison with test8 below. |
| `test6.py` | Previous stochastic downscaling script. Still on server. |
| `test1.py`–`test5.py` | Earlier iterations of the stochastic downscaler (development history). |
| `stage1_ml_downscaling.py` | ML downscaling (HistGradientBoosting) — **abandoned/experimental** |
| `stage1_ml_downscaling_2step.py` | Two-step ML downscaling variant — **abandoned/experimental** |
| `stage1_dl_super_resolution.py` | cGAN super-resolution — **abandoned/experimental** |
| `stage1_dl_super_resolution_2stage.py` | Two-stage cGAN — **abandoned/experimental** |
| `stage2_dl_2stage.py` | Second stage for 2-stage DL pipeline — **abandoned/experimental** |
| `stage1_eqm_postprocessor.py` | EQM post-processing for ML outputs — **abandoned/experimental** |

### `\\abe-cylo\modelsdev\Projects\WRC_DOR\Bias_Correction\Scripts\`
Only plotting/analysis scripts (no pipeline scripts):
`plot_ensemble_consensus.py`, `plot_physics_analysis.py`, `generate_physics_impact_table.py`, `generate_publication_metrics.py`, `generate_publication_tables.py`, `plot_publication_figures_with_csv.py`, `plot_fig1.py`, `plot_metric_summary.py`
Also contains `BiasCorrection_Bhuwan.pdf` — Bhuwan's bias correction results report.

**Note:** All of Bhuwan's BC scripts import `evaluate_multivariate_v2.py` from `E:\SpatialDownscaling` (his local machine) and point to `\\10.27.15.33\cylo-bshah\Bias-Correction\` for CONUS-scale outputs — paths Elijah cannot access. The cropped Iowa data at `Data/Cropped_Iowa/` contains all 8 BC methods × 5 GCMs × 6 vars and is what we use for independent validation.

### `C:\drops-of-resilience\5-bias-correction-validation\`
Independent validation of all 8 BC methods over the Iowa crop (2006–2014). Self-contained HTML report at `report.html`; scripts in `scripts/`; metrics CSVs and plots in `output/`.

**Key validation findings:**
- All BC implementations behave as expected. Method rankings on Iowa are consistent with Bhuwan's CONUS-scale Tables 2–3.
- OTBC confirmed as a strong all-around choice (see above).
- BCCA has severe precipitation tail artifacts: compresses P99 by ~25 mm/d on Iowa (Bhuwan's CONUS result shows +18 mm/d inflation — opposite sign, same root cause: analogue blending distorts extremes, direction depends on domain size).
- Physics correction eliminates all tasmax<tasmin violations. Huss saturation violations drop to near-zero; small residuals (~0.001–0.5%) remain for Spatial MBC due to numerical tolerance in qsat formula.
- Iowa violation rates are much lower than CONUS (e.g., QDM: 0.048% vs 17%) because Iowa's continental climate rarely approaches psychrometric saturation limits.
- GridMET observation regridding for validation used simple linear interpolation (convenience only). Bhuwan's production regridding (`regrid-gridmet-100km.py`) correctly uses xESMF conservative_normed for pr/flux and bilinear for state variables.

### Also note
- **`test8_v2.py`** is now on the server (see table above). It reads from the new `Regridded_Iowa/` data layout rather than the older `Data_Regrided_Gridmet/` layout. Its `GRIDMET_DATA_DIR` points to `E:\SpatialDownscaling\Regridded_Iowa` on Bhuwan's machine, which mirrors `Data/Regridded_Iowa/` on the server.
- There is a **test7 / test7_v2.py** referenced in `regrid_all_models_iowa.py` — not yet found or read. On Bhuwan's machine.
- **`gridmet_paths.py`** — shared config module imported by `regrid_to_gridmet.py` and `test8.py`. Provides `GRIDMET_DATA_DIR`. On Bhuwan's machine, not on server. Not needed for local pipeline scripts (paths are hardcoded in those). Note: `test8_v2.py` does not import `gridmet_paths.py` — it hardcodes `GRIDMET_DATA_DIR` directly.

### Local regridding + bilinear-vs-NN harness (`3-bilinear-vs-nn-regridding/`)

**Canonical regrid scripts:** [`pipeline/scripts/regrid/regrid_to_gridmet_bilinear.py`](pipeline/scripts/regrid/regrid_to_gridmet_bilinear.py), [`pipeline/scripts/regrid/regrid_to_gridmet_nn.py`](pipeline/scripts/regrid/regrid_to_gridmet_nn.py) — env-configurable paths; see [`pipeline/scripts/regrid/README.md`](pipeline/scripts/regrid/README.md). Deprecated wrappers under `3-bilinear-vs-nn-regridding/pipeline/scripts/` print a notice and delegate to these files.

| Script (task folder) | Purpose |
|--------|---------|
| `test8_bilinear.py` | test8 logic with paths pointing to regridded bilinear data. Outputs under task `pipeline/output/`. |
| `test8_nn.py` | Same for nearest-neighbor regrid path. |
| `crop_bc_mpi_local.py` | Crops physics-corrected OTBC MPI data from server to Iowa. Outputs to `source_bc/`. |
| `crop_gridmet_local.py` | Crops GridMET CONUS .nc files from server to Iowa. Outputs to `gridmet_cropped/`. |
| `compare_regrid_methods.py` | Reads metric CSVs from bilinear vs NN test8 runs and produces `regrid_comparison_report.html`. |

## Local: test8 PR intensity pipeline (`pipeline/`)

Local fork of Bhuwan’s **test8_v2** with optional **PR-only** storm-intensity–dependent ratio scaling and an optional **blend** that scales `(ratio_ext - ratio) × weight` when intensity is on (full technique, blend sweep, and expectations vs results: [`4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md`](4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md)).

**Naming (Apr 2026):** **`test8_v2`** = Bhuwan-parity-oriented preset (default WDF **1.65**, pr corr length **35**, noise debias **off**; no blend preset — see entry script). **`test8_v3`** = PR-intensity path with **legacy** wet-day scaling default **`PR_WDF_THRESHOLD_FACTOR=1.15`**. **`test8_v4`** = same path with **tuned** WDF default **`1.65`** (Iowa 216×192; see [`8-WDF-overprediction-fix/`](8-WDF-overprediction-fix/)). Shared implementation: [`pipeline/scripts/_test8_sd_impl.py`](pipeline/scripts/_test8_sd_impl.py). Overview: [`pipeline/README.md`](pipeline/README.md).

| Path | Role |
|------|------|
| [`pipeline/scripts/test8_v2.py`](pipeline/scripts/test8_v2.py) | Bhuwan-parity-oriented entry point; sets `DOR_PIPELINE_ID=test8_v2` (fork, not a byte copy of server `test8_v2.py`). |
| [`pipeline/scripts/test8_v4.py`](pipeline/scripts/test8_v4.py) | **Recommended** for PR-intensity work; sets `DOR_PIPELINE_ID=test8_v4`, default blend **0.65**, default WDF factor **1.65**. |
| [`pipeline/scripts/test8_v3.py`](pipeline/scripts/test8_v3.py) | Same as v4 with **WDF default 1.15** (parity with older “v2 + intensity” WDF scale). |
| [`4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py`](4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py) | **Deprecated wrapper** — delegates to v4 and sets `DOR_PIPELINE_ROOT` to the task folder so old relative layouts still work. |
| [`4-test8-v2-pr-intensity/scripts/sweep_pr_intensity_blend.py`](4-test8-v2-pr-intensity/scripts/sweep_pr_intensity_blend.py) | Sweeps `PR_INTENSITY_BLEND`; invokes `pipeline/scripts/test8_v4.py`; can write `blend_sweep_results.csv` under `pipeline/output/test8_v4/`. |

**Outputs** live under **`<DOR_PIPELINE_ROOT>/output/<test8_v2|test8_v3|test8_v4>/`**: `parity/`, `experiment/` (or `experiment_<PR_INTENSITY_OUT_TAG>/`), `experiment_blend*/`, etc., each with `V8_Table1_Pooled_Metrics_Stochastic.csv`, `V8_Table2_…`, `run_manifest.json`. If `DOR_PIPELINE_ROOT` is unset, it defaults to the parent of `pipeline/scripts/` (i.e. **`pipeline/`**). **Older runs** may still be under `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/` from before the rename.

**Environment variables** (see [`pipeline/scripts/_test8_sd_impl.py`](pipeline/scripts/_test8_sd_impl.py) docstring for the full list):

| Variable | Role |
|----------|------|
| `PR_USE_INTENSITY_RATIO` | `0` / `1`: parity (flat PR ratio) vs experiment (intensity-weighted PR ratio only). |
| `PR_INTENSITY_BLEND` | Float in `[0, 2]`; v3/v4 entry points default **0.65** when unset; v2 does not set a default (impl default **1.0**). Scales `(ratio_ext - ratio) × weight` when intensity is on. |
| `PR_INTENSITY_OUT_TAG` | Optional suffix for the experiment output subdir (avoids overwrites during sweeps). |
| `PR_WDF_THRESHOLD_FACTOR` | Wet-day threshold scale at inference; defaults **1.15** (v3) or **1.65** (v2, v4) if unset. |
| `TEST8_MAIN_PERIOD_ONLY` | Default `1`: main 1981–2014 stack + metrics only. |
| `TEST8_SEED` | Optional int; fixes RNG for reproducibility (may differ from Bhuwan’s published v2 numbers). |
| `DOR_PIPELINE_ROOT` | Absolute path to experiment root (`scripts/`, `data/`, `output/`). |
| `DOR_PIPELINE_ID` | `test8_v2`, `test8_v3`, or `test8_v4` (normally set by the entry-point scripts). |
| `DOR_TEST8_V2_PR_INTENSITY_ROOT` | Legacy alias for `DOR_PIPELINE_ROOT`. |
| `DOR_TEST8_PR_DATA_DIR` | Optional override for memmap directory (default `<root>/data`). |

**Reading metrics (PR vs other variables, multivariate):**

- In code, intensity/blend applies only to **pr**; **Schaake** is applied **per variable** (loop over `v`), so the PR intensity change is **not** wired into tas/wind/etc. downscale formulas.
- In **`V8_Table1_Pooled_Metrics_Stochastic.csv`**, comparing **`parity/`** vs **`experiment/`**: **pr** moves materially (e.g. KGE on the order of **~10–20%** relative change, RMSE **several percent** in the saved parity vs experiment runs). **tasmax, tasmin, rsds, wind, huss** show only **tiny** relative shifts (roughly **1e-4–1e-3** on KGE/RMSE) — not proportional to the pr change, so **not** a meaningful “pr drove the other rows” effect for those per-variable Table1 lines.
- **Joint / multivariate summaries** that aggregate the full variable stack (e.g. Frobenius-style metrics in run logs) **do** move when **pr** moves, because **pr** is in the aggregate.
- Do **not** expect non-pr Table1 rows to match **bit-for-bit** across separate runs unless **`TEST8_SEED`** (and run conditions) are aligned; without a fixed seed, small drift can appear on **all** variables.

**Cross-product benchmark:** **[`6-product-comparison/`](6-product-comparison/)** compares this DOR output (blend **0.65**) to **LOCA2** and **NEX-GDDP-CMIP6** on **MPI**, using the same **GridMET** memmap and **2006–2014** pooled metrics. See **External product comparison** later in this file.

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

## test8_v2.py — Bhuwan's Latest Iteration

**Last modified:** 3/30/2026
**Data layout:** Reads from new `Regridded_Iowa/MPI/mv_otbc/` structure (not the old `Data_Regrided_Gridmet/` flat layout). `GRIDMET_DATA_DIR` hardcoded to `E:\SpatialDownscaling\Regridded_Iowa` (no `gridmet_paths.py` import).
**Output dir:** `E:\SpatialDownscaling\Iowa_Downscaled\v8_2`

### What changed vs test8

| Change | test8 | test8_v2 | Impact |
|--------|-------|----------|--------|
| Noise correlation length | Fixed 5.0 px for all vars | **Variable-specific**: tasmax/rsds=100, wind=50, tasmin/huss/pr=35 | Much larger spatial correlation in noise — synoptic-scale for temp/radiation, mesoscale for pr/moisture. Noise structures are now physically-scaled rather than arbitrary. |
| Continuous noise factor | 0.06 | **0.05** | Slightly less noise for additive vars |
| Multiplicative noise factor | 0.15 | **0.16** | Slightly more noise for pr/wind |
| Multiplicative noise clip | [0.1, 5.0] | **[0.1, 8.5]** | Allows much higher storm multipliers — explicitly "allow high storms" |
| PR physical cap | None | **250 mm/day** | "Absolute physical cap for SWAT+ stability" — prevents runaway values for downstream WEPP/SWAT+ |
| WDF threshold factor | 1.2 | **1.65** (was 1.15; updated Apr 2026 via `8-WDF-overprediction-fix/`) | Tuned to match observed WDF on 216×192 grid. Original 1.15 undercompensated for noise-threshold asymmetry (+3.4pp overprediction). |
| Lapse rate | Single constant −6.5 °C/km | **Monthly dictionary** (−4.5 to −6.5 °C/km, varying by season) | More realistic: steeper in summer, shallower in winter |
| `device` | Global variable | **Per-worker** | Fix for CUDA deadlocks with ProcessPoolExecutor |
| `MAX_WORKERS` | 2 | **1** | More conservative parallelism |
| Schaake Shuffle | Rank-based quantile mapping on full training set as one block | **Year-by-year, month-by-month** cycling through historical reference years | More granular temporal matching; applied to future & early historical periods too (not just 1981–2014) |
| Data input to downscale loop | Single-variable slice `inputs[:, v_idx]` | **Full 6-variable array** `inputs` (method extracts its variable internally) | Refactored interface; same net effect |

### PR-specific changes summary

The changes most relevant to precipitation downscaling quality:
1. **Noise correlation length 5→35 px**: noise spatial structures are now ~7× larger — mesoscale storm-sized patterns rather than pixel-scale noise
2. **Noise clip [0.1, 5.0]→[0.1, 8.5]**: extreme storms can reach 8.5× the base ratio-scaled value (was capped at 5×)
3. **WDF threshold 1.2→1.65** (updated from 1.15 in Apr 2026): compensates for noise pushing dry days above threshold; matches observed WDF to ~0.02pp
4. **250 mm/day cap**: physical safety valve for SWAT+ stability
5. **Noise factor 0.15→0.16**: marginal increase in pr noise amplitude

### Bhuwan's results (from Teams, April 2026)
- test8_v2 **was better** on extremes and WDF metrics vs test8.
- He used **bilinear interpolation for precipitation** (not conservative), and it **worked well for extremes**.
- This reverses the earlier recommendation from the bilinear-vs-NN comparison (which used test8, not v2). With v2's wider noise clip and larger correlation length, bilinear apparently provides a better base for the multiplicative stochastic step to generate realistic extreme events — consistent with ISIMIP3's reasoning that smoother input to the stochastic step produces better output.
- The script on the server **won't reproduce the exact same results** because he has "edited the weights for spatial autocorrelation" since uploading it. He is still tuning.

### Metric comparison: test8 → test8_v2 → v9

Results uploaded to `\\abe-cylo\...\Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\` and `v9\`.

**PR (the focus variable):**

| Metric | test8 (our baseline) | test8_v2 | v9 |
|--------|---------------------|----------|-----|
| KGE | ~0.03 | 0.022 | 0.023 |
| Ext99 Bias% | ~-13.3% | **-6.7%** | **+1.3%** |
| RMSE | ~9.5 | 9.50 | 10.09 |
| WDF gap (Sim−Obs) | ~+6pp | **+3.3pp** | **+3.1pp** |
| Lag1 Err | ~0.02 | 0.055 | **0.285** |

**All variables (test8_v2):**

| Variable | KGE | RMSE | Ext99 Bias% | Lag1 Err |
|----------|-----|------|-------------|----------|
| pr | 0.022 | 9.50 | -6.73% | 0.055 |
| tasmax | 0.801 | 8.14 | -0.25% | 0.008 |
| tasmin | 0.818 | 7.06 | +0.18% | 0.009 |
| rsds | 0.764 | 56.60 | +0.82% | 0.004 |
| wind | 0.080 | 2.22 | -7.34% | 0.053 |
| huss | 0.775 | 0.0029 | +2.05% | 0.005 |

**Key interpretation:**
- test8_v2 cut pr Ext99 underprediction roughly in half and halved WDF overprediction. Solid improvement.
- v9 nearly nailed Ext99 (+1.3%) but **destroyed temporal coherence** (Lag1 Err 0.285 — simulated lag-1 autocorrelation is 0.08 vs observed 0.36). Precipitation is essentially independent between days.
- v9 was run on 3/24, six days **before** test8_v2 (3/30). Bhuwan likely tried something aggressive in v9, saw it fixed extremes but wrecked autocorrelation, then backed off to the more conservative v2 tuning. The v9 script is not on the server.
- KGE stayed near zero across all versions — this is a fundamental limitation of the delta/ratio approach (the GCM determines daily patterns; the downscaler can't fix timing mismatches).
- Bhuwan's current focus is tuning the spatial autocorrelation weights to find the sweet spot between v9's extreme-preserving aggressiveness and maintaining realistic temporal structure.

### Unchanged from test8
- Core logic (additive delta for continuous vars, multiplicative ratio for pr/wind)
- Semi-monthly calibration windows (24 periods)
- AR(1) temporal autocorrelation in noise (ρ=0.8 additive, ρ=0.5 multiplicative)
- All metric engines (`calculate_pooled_metrics`, `calculate_per_cell_summary_metrics`, `calculate_climatology_summary`)
- Train/test split (train 1981–2005, test 2006–2014)

### `hist_temp_mean` field
`StochasticSpatialDisaggregatorMultiplicative` has `self.hist_temp_mean = 288.15` — set in `__init__` but never referenced. Likely a placeholder for a planned temperature-dependent precipitation adjustment that hasn't been implemented yet.

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
| test8 | Removed test7's double-BC, added AR(1) noise, semi-monthly windows, Schaake Shuffle, lag-1 metric, deterministic mode |
| test8_v2 | Variable-specific noise correlation lengths (physically scaled), wider storm multiplier clip, monthly lapse rates, month-by-month Schaake Shuffle, 250mm/day PR cap |

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
│   (NOTE: geo_static.npy and gridmet_targets_*.dat are NOT here — use Spatial_Downscaling/test8_v2/Regridded_Iowa/)
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

Also on server under `Spatial_Downscaling/`:

| Data | Location |
|------|---------|
| **Downscaled_Products/** — External pipeline outputs for verification | `Spatial_Downscaling\Downscaled_Products\` |
| → LOCA2 | `LOCA2\{EC-Earth3, GFDL-CM4, MPI-ESM1-2-HR, MRI-ESM2-0}\{historical, ssp585}\{pr, tasmax, tasmin}\` — single .nc per var (1950–2014 historical) |
| → NEX-GDDP-CMIP6 | `NEX-GDDP-CMIP6_Files\{MODEL}\{historical, ssp585}\{huss, pr, rsds, sfcWind, tasmax, tasmin}\` — yearly .nc files (e.g. **MPI-ESM1-2-HR** and **CMCC-ESM2** present) |

### CRITICAL: Only one correct input dataset — `Regridded_Iowa` on the server

Bhuwan's `test8_v2.py` hardcodes `GRIDMET_DATA_DIR = r"E:\SpatialDownscaling\Regridded_Iowa"`. The server mirror is `Spatial_Downscaling\test8_v2\Regridded_Iowa\`. **This is the only correct data for all test8_v2/v3/v4 work and all benchmark-comparable runs.** It has 6,147 NaN border pixels in the CMIP6 inputs, leaving 35,325 valid land pixels per day.

There are **two other 216×192 datasets in this repo that look similar but are NOT the same data** and produce different metrics:

| Dataset | Location | NaN border pixels | WDF Obs% | Use |
|---------|----------|-------------------|----------|-----|
| **`Regridded_Iowa`** (CORRECT) | Server: `Spatial_Downscaling\test8_v2\Regridded_Iowa\` | **6,147** | **32.317** | **All production runs and benchmarks** |
| `bilinear` regridding output | Local: `3-bilinear-vs-nn-regridding/pipeline/data/bilinear/` | 3,999 | 32.547 | **Regridding comparison only.** Different regridding pipeline with different border handling. Do NOT use for downscaling experiments. |
| **`Data_Regrided_Gridmet`** (OLD) | Server: `Spatial_Downscaling\Data_Regrided_Gridmet\` | different grid entirely | different | **test6 only.** 84×96 grid, not 216×192. |

**When writing sweep or experiment scripts, always use the server `Regridded_Iowa` paths:**
```
DOR_TEST8_CMIP6_HIST_DAT=\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat
DOR_TEST8_GRIDMET_TARGETS_DAT=\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat
DOR_TEST8_GEO_MASK_NPY=\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy
```

**Do NOT use `3-bilinear-vs-nn-regridding/pipeline/data/bilinear/` as a "local fallback"** — it is a different dataset produced by a different regridding pipeline with different border coverage (3,999 vs 6,147 NaN pixels). Metrics computed on it (WDF, RMSE, Ext99) will not match published benchmarks.

**Incident history:**
- WDF threshold sweep (Apr 2026): accidentally ran on `Data_Regrided_Gridmet` (wrong grid entirely, 120×192). Had to redo.
- Corr_len sweep (Apr 2026): accidentally ran on local `bilinear` data (right grid size, wrong data). Relative findings valid but absolute numbers don't match benchmarks.

Also on server (older layout, still present):

| Data | Location |
|------|---------|
| Regridded GridMET + CMIP6 inputs (84×96, .dat memmaps) — **output of regrid_to_gridmet.py**. **Legacy — do not use for test8_v2.** | `Spatial_Downscaling\Data_Regrided_Gridmet\` |
| Wind effect static files | `Spatial_Downscaling\Data_WindEffect_Static\` |
| test8_v2 input data (216×192, .dat memmaps, `MPI/mv_otbc/` subdir) — **use this for all test8_v2 work** | `Spatial_Downscaling\test8_v2\Regridded_Iowa\` |
| test8_v2 output (v8_2): all 6 vars × 3 periods × shuffled variants + metric CSVs | `Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\` |
| v9 output: all 6 vars (1981–2014 only) + metric CSVs. Script not on server. | `Spatial_Downscaling\test8_v2\Iowa_Downscaled\v9\` |
| BC outputs (CONUS, all 5 models, 7 MV methods) | `Bias_Correction\Data\BC-Outputs-MV-Unified\BC-Outputs-Spatial-{MODEL}\GROUP_huss-pr-rsds-tasmax-tasmin-wind\` — `.npz` per var × method × scenario, plus `_metrics/` and `_plots/` |
| BC outputs (CONUS, all 5 models, univariate QDM) | `Bias_Correction\Data\BC-Outputs-Univariate-QDM\BC-Outputs-Fixed-{MODEL}\` |
| BC manuscript (LaTeX + PDF) | `Bias_Correction\Data\Manuscript\` |
| BC results report PDF | `Bias_Correction\BiasCorrection_Bhuwan_Results_report.pdf` |

### Bhuwan's local machine (not on server)

| Data | Location |
|------|---------|
| Cropped bias-corrected for Iowa (MPI only) | `D:\Research\Projects\WRC\Cropped_BC_MPI\` |
| Cropped bias-corrected for Iowa (all models) | `D:\Research\Projects\WRC\Cropped_BC_All_Models\` |
| Regridded all-model inputs (.npy per model/var/scenario) | `E:\SpatialDownscaling\Data_Regrided_Gridmet_All_Models\` |
| Downscaling output (test6) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final\` |
| Downscaling output (test8) | `E:\SpatialDownscaling\Data_Stochastic_Kriging_Final_v8\` |
| Downscaling output (test8_v2) | `E:\SpatialDownscaling\Iowa_Downscaled\v8_2\` |
| Regridded Iowa data (test8_v2 input) | `E:\SpatialDownscaling\Regridded_Iowa\` (local mirror of server `Data/Regridded_Iowa/`) |

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
- **Literature review on NN regridding** — Bhuwan wants to see papers that use nearest-neighbor for coarse→fine climate regridding before committing to the switch. Review is substantially complete (`3-bilinear-vs-nn-regridding/nn-regridding-literature-review.md`): no operational pipeline uses NN, but our pipeline design makes the interpolation choice largely inconsequential.
- **External verification** — compare against other organizations' pipeline outputs. **LOCA2 and NEX-GDDP-CMIP6** are on the server under `Spatial_Downscaling\Downscaled_Products\`. A quantitative **product vs GridMET** benchmark for **MPI** is implemented locally in [`6-product-comparison/`](6-product-comparison/) (see **External product comparison** in this file).
- **Colorado data** now on server alongside Iowa — same structure (Raw, BC, BCPC, Geospatial, GridMET).

---

## Bilinear vs Nearest-Neighbor Comparison (Complete)

**Question:** Does bilinear interpolation in the 100km→4km regridding step produce better final downscaled output than nearest-neighbor?

**Setup:** Two parallel pipelines using identical test8 logic, differing only in regridding method. Both used the same physics-corrected OTBC source data (`source_bc/`) for a fair comparison. Validated on 1981–2014 period, Iowa domain, MPI-ESM1-2-HR.

**Original report (non-pr variables only):** `C:\drops-of-resilience\3-bilinear-vs-nn-regridding\regrid_comparison_report.html`

**Recommendation: Switch to NN for non-precipitation variables.** NN makes fewer assumptions than bilinear (no smoothing of GCM cell boundaries), matches or outperforms bilinear on the metrics that matter, and has a modest computational advantage. For precipitation, use conservative regridding (see pr 3-way comparison below).

**Literature review outcome:** No operational pipeline uses NN. Bilinear is the community default, but no one has quantitatively justified it — it is an unquestioned convention. ISIMIP3 is the only pipeline that questioned the interpolation method (bilinear vs conservative, qualitative only). Our experiment is the only quantitative comparison we've found. See `3-bilinear-vs-nn-regridding/nn-regridding-literature-review.md`.

**Precipitation 3-way comparison:** In the main NN vs bilinear pipeline, both paths used conservative regridding for pr. To answer Bhuwan's question about whether NN or bilinear could work for pr, we ran a separate 3-way test: conservative, bilinear, and NN regridding of pr only, each fed through test8's multiplicative downscaler.

**Result:** All three methods perform poorly on KGE (~0.03), Ext99 Bias% (−13% to −17%), and Lag1 Error (0.017–0.033) — all below "moderate" tier thresholds. Test8's stochastic downscaling overwhelms the regridding signal for precipitation. Bilinear shows ~3% lower RMSE, but this is a smoothing artifact: bilinear dampens variance (reducing squared error) while simultaneously worsening extreme underprediction (Ext99 −17.3% vs −13.3% for conservative/NN) and temporal autocorrelation (Lag1 error nearly 2x worse). The empirical metrics do not strongly differentiate the methods, but they offer no reason to deviate from the conventional practice of using conservative for pr, which is supported by physical reasoning (mass/flux conservation across grid cells).

**Report:** `C:\drops-of-resilience\3-bilinear-vs-nn-regridding\combined_regrid_report.html` (comprehensive report combining all metrics, charts, and qualitative plots for the full NN vs bilinear comparison and the pr 3-way comparison).

### Key findings by variable

| Variable | Verdict | Reasoning |
|----------|---------|-----------|
| tasmax | Toss-up → NN | No meaningful differences on any metric. NN preferred for fewer assumptions. |
| tasmin | Toss-up → NN | Same as tasmax. |
| rsds | Toss-up → NN | Same as tasmax. |
| huss | Toss-up → NN | Same as tasmax. |
| wind | NN | NN reduces Ext99 Bias% by 2.1pp (meaningful). Bilinear wins RMSE by 1.3% but Ext99 is more important for wind applications. |
| pr | Conservative (test8) / **Bilinear (test8_v2)** | 3-way comparison with test8 showed all methods perform poorly on KGE, Ext99, and Lag1. Conservative was recommended on physical grounds. **However**, Bhuwan reports that bilinear worked well for pr extremes when paired with test8_v2's parameters (wider noise clip, larger correlation length). The pr regridding question should be revisited with test8_v2. |

### Notes on interpretation
- **KGE and Ext99 are independent**: low KGE (poor day-to-day skill) does not invalidate an Ext99 result. Ext99 measures distributional properties across the full record; a model can fail at tracking specific days but still capture extremes reasonably.
- All "meaningful" differences are small (≤2pp absolute, ≤10% relative). Regridding method is not the dominant source of error in this pipeline.
- **RMSE can be misleading for pr**: bilinear's lower RMSE is a smoothing artifact — dampening variance reduces squared error but worsens extremes. For precipitation, Ext99 and Lag1 are more decision-relevant than RMSE.
- **Stochastic threshold instability**: Some variable–metric pairs sit very close to the meaningfulness thresholds (0.5% for RMSE, 5.0% for Lag1). Because test8 includes a stochastic component, small run-to-run variations can flip borderline cases (e.g. tasmin RMSE, rsds Lag1) across the threshold without any change in regridding. Any metric near the threshold is effectively negligible regardless of which side it falls on.

---

## External product comparison (`6-product-comparison/`)

**Purpose:** Compare **our** downscaled product to **published statistical downscaling archives** using a **common validation truth** (Iowa **GridMET** targets on the **216×192** crop), without claiming the external products were trained to GridMET.

**Scope:** Historical **validation-period** metrics only (config default **2006–2014**). This folder does **not** run the OTBC **regrid** pipeline; it consumes **already-built** DOR NPZs and **interpolates** LOCA2/NEX to the benchmark grid (see **Clarifications** table above). For **climate-change signal** (e.g. SSP minus historical), use or add tooling outside this benchmark (e.g. scripts that compare future stacks to historical means).

**Canonical DOR product in the benchmark:** Local **test8 PR-intensity** line (**`test8_v4`**) with **`PR_INTENSITY_BLEND=0.65`**, **`PR_USE_INTENSITY_RATIO=1`**, **`TEST8_SEED=42`**, default **`PR_WDF_THRESHOLD_FACTOR=1.65`**, outputs under [`pipeline/output/test8_v4/experiment_blend0p65/`](pipeline/output/test8_v4/experiment_blend0p65/) (see `run_manifest.json`). Historical copies of the same experiment may still exist under `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/experiment_blend0p65/`. **Blend scoring** (for documentation): `|pr Val_Ext99_Bias%| + 0.15 × pr Val_RMSE_pooled` across parity + sweep folders — **0.65 ranks first** (`6-product-comparison/scripts/verify_blend_choice.py`).

**Compared products (MPI-ESM1-2-HR, 2006–2014):**

| Product | Server path (under `Downscaled_Products\`) | Vars used in benchmark |
|---------|-------------------------------------------|-------------------------|
| **LOCA2** | `LOCA2\MPI-ESM1-2-HR\{historical}\{pr,tasmax,tasmin}\` (single `.nc` per var, 1950–2014) | **pr, tasmax, tasmin** only |
| **NEX-GDDP-CMIP6** | `NEX-GDDP-CMIP6_Files\MPI-ESM1-2-HR\historical\{var}\` (yearly `.nc`) | **All six** pipeline vars (`pr`, `tasmax`, `tasmin`, `rsds`, `sfcWind`, `huss`) |
| **DOR** | Local `Stochastic_V8_Hybrid_*.npz` | Same six |

**Alignment:** External fields are **linearly interpolated** in lon/lat (xarray) onto the **GridMET lat/lon** from `Data\Cropped_Iowa\GridMET\Cropped_pr_2006.npz`. **pr** from LOCA2/NEX converted **kg m⁻² s⁻¹ → mm/day** (×86400). Days aligned by **calendar date** (NEX timestamps normalized).

**Repo layout:** [`6-product-comparison/README.md`](6-product-comparison/README.md), [`WORKLOG.md`](6-product-comparison/WORKLOG.md) (audit trail + NEX-`rsds` diagnosis), [`LITERATURE.md`](6-product-comparison/LITERATURE.md). **Run:** `conda activate drops-of-resilience` then `python 6-product-comparison/scripts/run_benchmark.py` (long run if LOCA2 is read over the network). **Outputs:** [`6-product-comparison/output/benchmark_summary.csv`](6-product-comparison/output/benchmark_summary.csv), `6-product-comparison/output/figures/`.

### What observations LOCA2 and NEX were built to match (not GridMET)

Understanding this avoids mis-reading **mean offsets** in validation.

| Archive | Stated / documented observation target for bias correction or analog training |
|---------|-------------------------------------------------------------------------------|
| **NEX-GDDP-CMIP6** | **GMFD** — *Global Meteorological Forcing Dataset for land surface modeling* / **Princeton Global Meteorological Forcings** (Sheffield lineage). Pipeline uses **0.25° daily** fields for BC; **1960–2014** reference period for quantile mapping (*Scientific Data* 2022, [doi:10.1038/s41597-022-01393-4](https://doi.org/10.1038/s41597-022-01393-4)). NetCDF global attr `references` cites **Thrasher et al. 2012** (BCSD) and **Princeton Global Meteorological Forcings** + **Sheffield et al. 2006**. |
| **LOCA2** | **Livneh-family** gridded analyses: **unsplit Livneh** daily **precipitation** (Pierce et al. 2021); **Livneh et al. 2015** extended through **2018** for **Tmax/Tmin** (Lu Su, UCLA). Stated on [LOCA training data](https://loca.ucsd.edu/training-observed-data-sets/). LOCA2 NetCDFs include `fname_fine_obs` / `fname_coarse_obs` pointing at internal **preprocessed training** files (e.g. `LOCA2_training_*_preproc_obs.nc`, 1950–2014). |

**Takeaway:** **GridMET** is the **evaluation** reference in `6-product-comparison`, not the **training** reference for NEX or LOCA2. A large **mean bias** can still appear where the **external analysis** disagrees systematically with GridMET (especially **shortwave**).

### NEX `rsds` vs GridMET `srad` (pinned down, Apr 2026)

**Symptom:** Pooled mean **NEX − GridMET** ~**+37 W m⁻²** (~**21%** of mean observed SW) for 2006–2014 Iowa domain.

**Findings** (`scripts/diagnose_nex_rsds.py`, details in `WORKLOG.md`):

- **Not caused** by interpolating NEX onto the GridMET grid: same ~**37 W m⁻²** when **obs are interpolated onto the NEX Iowa subset grid** (native product resolution).
- **Positive every calendar month**; **largest** domain-mean bias in **spring**; **smallest** in mid-winter / mid-summer — not a single bad season.
- **Largest bias when observed domain-mean SW is low** (cloudier days); still positive on the brightest quartile — consistent with **cloud / radiation analysis** differences between **GMFD-family** training and **GridMET**.

**LOCA2 comparison:** For **pr** and **temperature**, LOCA2 vs GridMET in the same benchmark is **much closer** than NEX-`rsds` — **different variables and different training products**; “not trained on GridMET” does **not** imply NEX-`rsds`-level mean error for all vars.

### Benchmark results summary (Apr 2026)

Full metric table in [`output/benchmark_summary.csv`](6-product-comparison/output/benchmark_summary.csv). Detailed weakness inventory in [`6-product-comparison/dor-weaknesses.md`](6-product-comparison/dor-weaknesses.md).

**Where DOR wins:**
- **pr Ext99 Bias%: +0.13%** — essentially perfect. LOCA2 is -4.6%, NEX is -25.3%. This is the standout result.
- **tasmin**: best KGE (0.817), best RMSE (7.06), best Ext99 (+0.17%), best Lag1 (0.008) of all three products.
- **rsds, huss, wind** vs NEX (only comparison available): DOR leads on KGE, RMSE, Bias, and Ext99 for all three.
- **tasmax Ext99** (-0.24%) and **Lag1** (0.007): best of three, though KGE/RMSE trail slightly.

**Where DOR is weak:**
- **pr RMSE: 9.91** — worst of three (LOCA2 9.47, NEX 8.64). The PR-intensity blend traded RMSE for Ext99; parity had RMSE 9.51.
- **pr WDF overprediction: essentially eliminated** by raising `PR_WDF_THRESHOLD_FACTOR` from 1.15 to 1.65 (32.34% sim vs 32.32% obs, +0.02pp). Now better than LOCA2 (-1.5pp) and NEX (+4.6pp). See `8-WDF-overprediction-fix/`.
- **pr KGE ≈ 0.024** — no day-to-day skill. Per-cell correlation is 0.025. All products are near zero; fundamental GCM limitation.
- **tasmax KGE (0.801) and RMSE (8.12)** — worst of three, though gap is small (~1-2%). DOR trails LOCA2 (0.810, 7.94) and NEX (0.817, 7.73).
- **Consistent warm bias** in tasmax (+0.45 K) and tasmin (+0.58 K), larger than LOCA2 (+0.31, +0.44).
- **wind KGE ≈ 0.08** and **Ext99 -7.5%** — essentially no temporal skill, dampens extremes. Same multiplicative-pathway limitation as pr.
- **Stochastic noise slightly worsens Lag1** for rsds (0.005 vs NEX 0.001) and huss (0.0057 vs NEX 0.0055) — AR(1) noise adds tiny temporal disruption that NEX's noise-free BCSD avoids.

**Overall assessment:** DOR is competitive with established products and has a clear win on extreme precipitation — the metric that matters most for WEPP/SWAT+. Additive variables (temperature, radiation, humidity) are strong. Precipitation RMSE and WDF have room to improve. The product is publishable but not finished.

### Visual analysis: spatial maps (Apr 2026)

Spatial validation maps generated for all 6 vars: single-day snapshots (5 dates), time-mean (2006–2014), and seasonal-mean (DJF/MAM/JJA/SON). Located at `6-product-comparison/output/figures/dor side-by-side/`.

**Single-day maps** look alarming — DOR and GridMET spatial patterns often don't match on any given day, especially for pr and wind. This is expected: the GCM produces its own weather on its own timeline; it is not tracking observed storm events. All interpolation-based downscaling products (NEX, ISIMIP, etc.) share this property. Single-day maps should not be used to evaluate product quality.

**Time-mean and seasonal maps** show the pipeline working as designed:
- **tasmax, tasmin**: Broad north-south temperature gradient is well captured. DOR is slightly smoother than GridMET (terrain-driven microclimate features are averaged out). However, **DOR is systematically too warm at the northern edge** of the domain — the north-south gradient is weaker in DOR than in GridMET. This warm bias is not spatially uniform; it is concentrated in the north, suggesting MPI's temperature gradient over Iowa is weaker than observed. The delta-mapping preserves whatever gradient the GCM produces, so this is inherited from the GCM/BC, not introduced by the downscaler. The same pattern appears in **huss** (too humid in the north) because humidity is temperature-dependent.
- **pr**: The climatological pattern (wetter east, drier west) is captured, and magnitudes are correct. DOR pr fields can show **splotchiness** — irregular blobs in **time-mean** maps that look unlike smooth GridMET — especially on **short** averaging windows (e.g. 2006–2014 alone). On the **full historical** mean (e.g. 1981–2014), maps typically **resemble GridMET** much more closely; see **Time-mean PR maps** (below). Single-day maps remain GCM-timeline mismatched. Residual texture also reflects stochastic multiplicative noise (test8_v2 correlation length 35 px for pr) not averaging to zero; spatial autocorrelation tuning remains relevant.
- **rsds**: Strong match across all seasons. North-south gradient shifts with season and DOR tracks it.
- **wind**: Weakest spatial match. GridMET has fine-scale wind features (terrain channeling, land-use roughness) at 4km that have no representation in 100km GCM data. DOR captures the broad pattern (windier northwest, calmer southeast) but lacks fine-scale structure. Blockiness is most visible here. This is a resolution limitation of the source data.
- **huss**: Good match. Moisture gradient (dry northwest, humid southeast) well reproduced. Same northern warm/humid bias as temperature.

### Local disk note (PR-intensity sweeps)

To save space after the benchmark, **large `Stochastic_V8_Hybrid_*.npz`** (and any `Deterministic_*.npz`) were removed from intermediate blend folders (`experiment_blend0p25` … `experiment/`), keeping **CSVs + `run_manifest.json`**. **Full `npz` retained** for **`parity/`** and **`experiment_blend0p65/`** (under the old `test8_v2_pr_intensity` output tree and/or `pipeline/output/test8_v4/`). (~37 GiB freed; see `6-product-comparison/WORKLOG.md`.)

### Time-mean PR maps: pick the aggregation window to match the question

Side-by-side **time-mean** maps (GridMET vs DOR) are sensitive to **how many years** are averaged.

- The **2006–2014** span is only the **validation** split (~9 years). Mean maps for that window are **not** a good stand-in for “how does our downscaled precipitation look in long-run aggregate?” Prominent **dark wet patches** in DOR that stand out against GridMET on **short** windows often **ease or disappear** when the same style of plot is made for the **full historical** period on the standard memmaps (**1981–01–01–2014–12–31**, i.e. on the order of **three decades**—sometimes described informally as ~1982–2014 depending on slicing). On that longer average, the DOR field **typically looks much more like GridMET** spatially.

- **Lesson:** Do not conclude that the pipeline is systematically wrong from a **short-window** mean map alone. Align the plotted calendar range with the scientific question (short window for test-era behavior; full historical for climatological representativeness). Investigation notes and tooling: [`7-fix-pr-splotchiness/`](7-fix-pr-splotchiness/).

### Default styling for mean **pr** maps (GridMET vs model / DOR)

For **side-by-side** mean precipitation maps in this project, the **canonical** display convention is:

1. **`Blues`** colormap.
2. **Independent 2–98%** linear stretch **per panel**: each of the two fields gets its own `vmin`/`vmax` from the 2nd and 98th percentiles of finite values (`_vmin_vmax_one` in [`7-fix-pr-splotchiness/scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py`](7-fix-pr-splotchiness/scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py)). **Two colorbars** (one per panel) so the right-hand (GCM or DOR) panel is not washed out by GridMET’s amplitude range.
3. **Typical entry points:** `plot_gridmet_pipeline_side_by_side.py dor` (**default**; omit `--shared-scale`), [`plot_period_comparison.py`](7-fix-pr-splotchiness/scripts/plot_period_comparison.py) (multi-period figure sets under `7-fix-pr-splotchiness/figures/period-comparison/`), and `plot_validation_agg_mean_pr_obs_vs_gcm.py` for drivers-only checks.

Optional: pass **`--shared-scale`** to `dor` or use `_pair_vmin_vmax`-style plotting when you **intentionally** want **one** color scale for both panels (2–98% on the pooled finite values).

Full copy-paste examples and script list: [`7-fix-pr-splotchiness/PLOTTING.md`](7-fix-pr-splotchiness/PLOTTING.md).

---

## Open Questions / To Investigate

- **Literature review: NN regridding** — **Substantially complete.** See `3-bilinear-vs-nn-regridding/nn-regridding-literature-review.md`. Conclusion: no operational pipeline uses NN; bilinear is the community default but no one has quantitatively justified it. ISIMIP3 is the only pipeline that questioned the interpolation method at all — they compared bilinear vs conservative qualitatively (one visual example, no skill metrics) and assumed smoother input to their stochastic step would be better. Our bilinear vs NN comparison is the only quantitative test on this question we've found, and it shows the methods are equivalent after test8. Awaiting Bhuwan's review.
- **Bilinear vs NN comparison**: **Complete.** Recommendation: switch to NN (non-precip variables). PR 3-way comparison also complete — all methods perform poorly; conservative recommended on physical grounds. See combined report at `3-bilinear-vs-nn-regridding/combined_regrid_report.html`.
### Active work items (see [`Priorities.txt`](Priorities.txt) for the live list)

1. **Redo product benchmarks at native LOCA2 / NEX resolution** — **Active.** Compare DOR, LOCA2, and NEX against GridMET **without** forcing LOCA2/NEX onto the 216×192 GridMET grid first — i.e. evaluate at roughly **~6 km** (LOCA2) and **~0.25°** (NEX) over an Iowa-relevant domain (with Bhuwan’s buffer guidance for coarse-vs-fine bounds). The current benchmark ([`6-product-comparison/scripts/run_benchmark.py`](6-product-comparison/scripts/run_benchmark.py), [`benchmark_io.py`](6-product-comparison/scripts/benchmark_io.py)) **interpolates** LOCA2 and NEX to the GridMET target grid; native-resolution reruns require new alignment / aggregation logic (and likely upsampling **obs** or common-area masking). **Resolved elsewhere:** **pr WDF** tuning ([`8-WDF-overprediction-fix/`](8-WDF-overprediction-fix/)) — `PR_WDF_THRESHOLD_FACTOR` **1.65** default on **`test8_v4`**; see `output/wdf_216x192_confirmation.md`.

### On hold (per Priorities.txt)

- **Fix pr RMSE** ([`9-additional-pr-RMSE-fixes/`](9-additional-pr-RMSE-fixes/)) — Ideas: [`BRAINSTORMING.md`](9-additional-pr-RMSE-fixes/BRAINSTORMING.md). Downscaler-only fixes have limits; see "PR RMSE gap" under *Not actionable* below.
- **Improve wind** ([`10-improve-wind/`](10-improve-wind/)) — Noise-factor sweep and optional WindEffect modulation; plan [`PLAN.md`](10-improve-wind/PLAN.md). **Ask Bhuwan** before enabling `USE_GEO_STATIC`-style terrain injection.
- **BC-first vs downscale-first**, **spatial-uniformity assumptions**, **post-correction consistency** — deferred per Bhuwan / Priorities.

### Not actionable (documented)

- **PR splotchiness in time-aggregated maps**: Dark regions in **short-window** (e.g. **2006–2014**) time-mean DOR maps were alarming when compared to GridMET; investigation in [`7-fix-pr-splotchiness/`](7-fix-pr-splotchiness/) explored noise debiasing, ratio smoothing, and GCM-origin hypotheses. **Important clarification:** mean maps for the **full historical** period on the standard stack (**1981–2014**) look **much closer to GridMET**; a **short validation window** is a **poor** proxy for long-run aggregate appearance. Do not over-interpret a single short-period mean map. Mechanistic work in that folder (GCM pattern bleed-through, `spatial_ratio` train/test mismatch, stochastic texture) remains relevant for deep dives; see also **Time-mean PR maps** above. Set `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` (noise debias off) per that investigation’s outcome. **Note:** The `splotch_metric` scalar was an unreliable proxy — do not use it for future work.
- **PR and wind KGE near zero**: KGE ≈ 0.02 for pr, ≈ 0.08 for wind. Fundamental GCM limitation — can't track individual storm events at 100km. Stayed ~0.02 across test8, test8_v2, v9, and all three benchmark products (LOCA2 0.023, NEX 0.002). Won't improve until temporal downscaling is addressed (correcting *which days* it rains, not just *how much*). Not the current focus — Bhuwan said to work on spatial downscaling first.
- **PR RMSE gap vs NEX — fully understood (Apr 2026)** (see also [`9-additional-pr-RMSE-fixes/WHY-VARIANCE-DRIVES-RMSE.md`](9-additional-pr-RMSE-fixes/WHY-VARIANCE-DRIVES-RMSE.md) for an intuitive explanation): DOR's RMSE (9.91) vs NEX (8.64) is a 1.27 gap. The RMSE decomposition shows that with near-zero correlation (r ≈ 0.025) and variance-matched output (σ_sim ≈ σ_obs), RMSE² ≈ 2σ²(1−r). NEX achieves lower RMSE by *compressing variance* (Ext99 = −25.3%), not by having better correlation — NEX's KGE is 0.002, even worse than DOR. Tuning noise parameters (correlation length, amplitude, scaling) cannot close this gap: the entire noise RMSE budget is ~0.7 (stochastic 9.91 − deterministic 9.21), and a corr_len sweep confirmed only 0.013 improvement from the best value. The PR-intensity blend adds ~0.4 to RMSE but parity still doesn't beat NEX (9.51 vs 8.64). **The only mathematical path to beating NEX without sacrificing Ext99 is improving r from ~0.025 to ~0.26** — making the daily spatial pattern partially informed rather than random. A cross-variable noise conditioning approach (using the GCM's temperature/humidity fields, which have KGE ~0.8, to bias the precipitation noise field) is the current hypothesis. See `9-additional-pr-RMSE-fixes/BRAINSTORMING.md` and `PLAN-CROSS-VARIABLE-NOISE.md`.
- **Tasmax KGE/RMSE trailing LOCA2/NEX by 1-2%**: Likely inherited from MPI's weak north-south temperature gradient passed through OTBC. Spatial maps confirm the warm bias is concentrated in the north — a GCM/BC issue, not a downscaler issue. DOR already wins on tasmax Ext99 and Lag1. Would need BC investigation, which Bhuwan deferred.

### Completed / deferred

- **Literature review: NN regridding** — **Substantially complete.** See `3-bilinear-vs-nn-regridding/nn-regridding-literature-review.md`. Conclusion: no operational pipeline uses NN; bilinear is the community default but no one has quantitatively justified it. ISIMIP3 is the only pipeline that questioned the interpolation method at all — they compared bilinear vs conservative qualitatively (one visual example, no skill metrics) and assumed smoother input to their stochastic step would be better. Our bilinear vs NN comparison is the only quantitative test on this question we've found, and it shows the methods are equivalent after test8. Awaiting Bhuwan's review.
- **Bilinear vs NN comparison**: **Complete.** Recommendation: switch to NN (non-precip variables). PR 3-way comparison also complete — all methods perform poorly; conservative recommended on physical grounds. See combined report at `3-bilinear-vs-nn-regridding/combined_regrid_report.html`.
- **v9 script** — Not on server. Ask Bhuwan for it or for details on what structural changes it made vs test8_v2. The Ext99 improvement is dramatic; understanding why it wrecked Lag1 is the key to moving forward.
- **BC-first vs downscale-first (including fine-resolution BC at 4km)**: Deferred per Bhuwan — do this after spatial downscaling is nailed down. Elijah's hypothesis: bias correcting at 4km instead of 100km could capture terrain-dependent biases that coarse BC misses. Prediction: unlikely to improve pooled pr RMSE significantly because RMSE is dominated by stochastic noise variance (0.7 RMSE gap between deterministic and stochastic DOR), not by BC resolution. More likely to help spatial bias patterns, inter-variable consistency at local scale, and possibly KGE for temperature variables where terrain matters (northern warm bias in tasmax/tasmin). Test after noise-related RMSE improvements are explored.
- **Stochastic noise**: Has not been empirically tested for WEPP compatibility. test8_v2 added a 250 mm/day cap for SWAT+ stability.
- **Terrain-based BC**: Not yet explored; Bhuwan suggested looking into whether DEM/slope/aspect are used in any existing BC methods.
- **External pipeline verification**: **Done for MPI (local repo).** Benchmark + weakness inventory + visual spatial analysis complete. See "Benchmark results summary" and "Visual analysis: spatial maps" sections above. Key findings: DOR wins on pr extremes, competitive on temperature, but has highest pr RMSE, WDF overprediction, and visible pr splotchiness (GCM-origin; see "Not actionable" above). Northern warm bias in tasmax/tasmin/huss inherited from GCM/BC. Full details: [`benchmark_summary.csv`](6-product-comparison/output/benchmark_summary.csv), [`dor-weaknesses.md`](6-product-comparison/dor-weaknesses.md), [`LITERATURE.md`](6-product-comparison/LITERATURE.md), [`WORKLOG.md`](6-product-comparison/WORKLOG.md).
- **Bias correction validation**: **Complete.** All 8 methods validated over Iowa crop. Report at `5-bias-correction-validation/report.html`. Implementations are correct; OTBC confirmed as the production method. See BC validation section above for details.
