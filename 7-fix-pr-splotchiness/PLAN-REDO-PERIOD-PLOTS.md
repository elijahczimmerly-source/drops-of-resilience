# Plan: Regenerate PR Time-Mean Plots Across Time Periods

## Status (supersedes earlier color-scale section)

The implementation [`scripts/plot_period_comparison.py`](scripts/plot_period_comparison.py) now uses the **canonical pipeline default** for mean maps: **independent 2–98% per panel**, **two colorbars** (see [`PLOTTING.md`](PLOTTING.md)). Sections below that demand a **single global vmin/vmax across all 12 plots** are **obsolete**; multi-period folders remain useful to compare the **same pipeline stage** over different calendar spans.

## Goal

Generate side-by-side GridMET vs pipeline-output plots of time-mean precipitation for THREE time periods: **1981-2005**, **1981-2014**, and **2006-2014**. Same data sources per plot type; **interpretation:** short windows (especially **2006–2014**) are **not** a substitute for full-historical climatology when judging long-run aggregate appearance vs GridMET (see [`WORKLOG.md`](WORKLOG.md) §12, [`../dor-info.md`](../dor-info.md)).

## Output location

All output goes to `7-fix-pr-splotchiness/figures/period-comparison/`. Create this directory.

Inside it, create three subdirectories: `1981-2005/`, `1981-2014/`, `2006-2014/`.

Each subdirectory gets four plots (same four pipeline stages):
1. `0_coarse_raw.png` — GridMET (regridded to coarse GCM grid) vs raw GCM (before BC), coarse grid
2. `1_coarse_otbc.png` — GridMET (regridded to coarse GCM grid) vs OTBC physics-corrected GCM, coarse grid
3. `2_regridded_4km.png` — GridMET (4km) vs OTBC regridded to 4km (post-`regrid_to_gridmet`, pre-downscaler)
4. `3_dor_output.png` — GridMET (4km) vs DOR stochastic downscaled output

That is 12 plots total.

## CRITICAL: Data sources

### For plots 2 and 3 (4km grid): use the SERVER memmaps

These are the ONLY correct data files. Do NOT use any local data under `3-bilinear-vs-nn-regridding/` or `4-test8-v2-pr-intensity/`.

- **CMIP6 inputs (for plot 2):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat`
  - Format: float32 memmap, shape `(12418, 6, 216, 192)`. Variable index 0 = pr.
  - Day 0 = 1981-01-01. Day 12417 = 2014-12-31.

- **GridMET targets (for plots 2, 3):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat`
  - Same format as CMIP6: float32 memmap, shape `(12418, 6, 216, 192)`. Variable index 0 = pr.
  - Day 0 = 1981-01-01. Day 12417 = 2014-12-31.

- **Geo mask:** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy`
  - Shape: `(216, 192)`. Use this to mask invalid border pixels (set to NaN).

- **DOR output (for plot 3):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\Stochastic_V8_Hybrid_pr.npz`
  - Key: `data`. Shape: `(12418, 216, 192)`. Float32 or float64.
  - Day 0 = 1981-01-01. Day 12417 = 2014-12-31.

### For plots 0 and 1 (coarse GCM grid): use the server cropped Iowa data

- **Raw GCM pr (for plot 0):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\Raw\` — yearly `.npz` files per GCM. Use **MPI-ESM1-2-HR** (look for files containing "MPI" in the name). Each NPZ has keys including `pr` (or similar), `lat`, `lon`, and a time axis. Load all years in the target range and concatenate.

- **OTBC physics-corrected pr (for plot 1):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\BCPC\MPI-ESM1-2-HR\mv_otbc\` — yearly `.npz` files. Same structure.

- **GridMET coarse reference (for plots 0, 1):** `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\GridMET\` — yearly `.npz` files (e.g. `Cropped_pr_2006.npz`). These are at 4km. To compare against the coarse GCM grid, you need to regrid the 4km GridMET onto the coarse GCM lat/lon using bilinear interpolation (`scipy.interpolate.RegularGridInterpolator`). Get the coarse lat/lon from the raw GCM NPZ files.

## CRITICAL: Date slicing

Create a date index using `pd.date_range("1981-01-01", periods=12418, freq="D")`.

For each period:
- **1981-2005:** `dates >= "1981-01-01"` AND `dates <= "2005-12-31"` — this is 9131 days
- **1981-2014:** `dates >= "1981-01-01"` AND `dates <= "2014-12-31"` — this is 12418 days (all data)
- **2006-2014:** `dates >= "2006-01-01"` AND `dates <= "2014-12-31"` — this is 3287 days

**Verification step (MANDATORY):** Before generating any plots, print the number of days selected for each period and assert they match the counts above. If they don't, stop and fix the bug.

For the coarse data (plots 0, 1), the NPZ files are per-year. Load only the years in the target range. For example, for 1981-2005, load years 1981 through 2005.

Compute the time-mean by taking `np.nanmean(data[mask], axis=0)` along the time axis.

## Color scale (UPDATED — was “single global scale”)

**Current behavior:** Each figure uses **independent 2–98%** scaling per panel and **two** colorbars — see [`PLOTTING.md`](PLOTTING.md) and [`scripts/plot_period_comparison.py`](scripts/plot_period_comparison.py).

*(Earlier plan revisions required one global vmin/vmax across all 12 PNGs; that approach is obsolete.)*

## Plot layout

Each plot has two panels side by side:
- Left panel: GridMET (observed truth)
- Right panel: pipeline output at that stage

Title format:
- Left: `GridMET (target)\nmean YYYY-YYYY`
- Right: `[stage description]\nmean YYYY-YYYY`

Right-panel descriptions:
- Plot 0: `MPI-ESM1-2-HR (raw)\nmean YYYY-YYYY`
- Plot 1: `MPI-ESM1-2-HR (OTBC+phys)\nmean YYYY-YYYY`
- Plot 2: `MPI-ESM1-2-HR (OTBC to 4km)\nmean YYYY-YYYY`
- Plot 3: `DOR (Bhuwan v8_2)\nmean YYYY-YYYY`

Suptitle: `pr time-mean (2-98% per panel)` plus period label (see `plot_period_comparison.py`).

Figure size: `(10.5, 4.8)`. DPI: 200. Use `constrained_layout=True`.

For the 4km plots (2, 3): use `imshow` with the data array directly (no lat/lon axes needed — just pixel coordinates). Apply the geo_mask by setting masked pixels to NaN before plotting.

For the coarse plots (0, 1): use `pcolormesh` with the coarse lat/lon coordinates.

## Script location

Write the script to `7-fix-pr-splotchiness/scripts/plot_period_comparison.py`. It should be a single self-contained script that generates all 12 plots in one run.

## Verification

After generating the plots:
1. Print the vmin and vmax used.
2. Print the domain-mean precipitation for each period for both GridMET and DOR at 4km, so we can verify the periods are actually different:
   ```
   GridMET domain mean (1981-2005): X.XXX mm/d
   GridMET domain mean (1981-2014): X.XXX mm/d
   GridMET domain mean (2006-2014): X.XXX mm/d
   DOR domain mean (1981-2005): X.XXX mm/d
   DOR domain mean (1981-2014): X.XXX mm/d
   DOR domain mean (2006-2014): X.XXX mm/d
   ```
3. Assert that the three DOR domain means are NOT identical (they should differ by at least 0.001). If they are identical, there is a bug in the date slicing.
