# Bias Correction Validation Plan

## Goal

Independently verify Bhuwan's bias correction implementations and reproduce/extend the publication plots. Bhuwan's request: "check if he implemented all the methods correctly and plot the results."

## What Bhuwan Has Already Done

### Scripts (on server at `Bias_Correction/Scripts/`)
| Script | Purpose |
|--------|---------|
| `generate_publication_metrics.py` | Computes MAE, KGE (daily/monthly), Lag-1, Frobenius norm across 5 GCMs × 8 BC methods. Outputs `all_models_metrics.json`. |
| `generate_publication_tables.py` | Reads the JSON and produces Tables 1-5 (method overview, marginal performance, dependence error, temporal persistence, KGE). |
| `plot_publication_figures_with_csv.py` | Main plotting engine: Figs 1-7 (marginal bias maps, dependence heatmaps, compound extremes, dry spells, spatial coherence, future deltas, future extreme shifts) + per-pixel CSVs. |
| `plot_fig1.py` | Conceptual Fig 1: tasmax vs huss scatter showing physics violations across Obs/Raw/QDM/R2D2. |
| `plot_ensemble_consensus.py` | Fig 10: Multi-model ensemble consensus maps (5 GCMs, stippling for agreement). |
| `plot_physics_analysis.py` | Figs 8-9, S5-S6: psychrometric scatter, spatial violation hotspots, impact bar chart. |
| `plot_metric_summary.py` | Fig 0: bar chart summary of all metrics. |
| `generate_physics_impact_table.py` | Physics correction impact table (violation rates, huss 99th diff, tmax consistency). |

### Outputs (on server at `Bias_Correction/Data/`)
- `all_models_metrics.json` — raw metric results
- `Publication_Tables/` — Tables 1-5 as CSV
- `Publication_Main_Figures_New/` — Figs 0-10 as PNG
- `Publication_Supplemental_Figures_New/` — Figs S1-S4
- `Publication_Physics_Analysis/` — Figs 8-9, S5-S6
- `Publication_Data_CSVs_New/` — per-pixel data for all figures
- `Pipeline_Impact_Analysis/` — Scott, IA site-level metrics + multi-city stage plots
- `Physics_Constraint_Impact_Table.csv`
- `Manuscript/Manuscript.tex` — draft paper

### Key Limitation
All of Bhuwan's scripts import `evaluate_multivariate_v2.py` from `E:\SpatialDownscaling` (his local machine). This module provides `load_series_multi_file()`, which handles loading yearly `.npz` files into aligned arrays. His scripts also point to `\\10.27.15.33\cylo-bshah\Bias-Correction\` for the CONUS-scale BC outputs — a path Elijah cannot access.

**However**, the cropped Iowa data at `Data/Cropped_Iowa/` contains all 8 BC methods × 5 GCMs × 6 vars, plus GridMET observations. This is what we can work with independently.

---

## What Needs to Be Done

The validation has two parts: (A) verify correctness of the BC implementations, and (B) produce plots.

### Part A: Verification of BC Method Correctness

The core question: did Bhuwan implement QDM, MBCn, ECC, R2D2, OTBC, Gaussian Copula, Spatial MBC, and BCCA correctly? We can't audit the BC code itself (it ran on Bhuwan's machine and is not on the server). What we *can* do is check that the outputs exhibit the expected statistical properties of each method.

#### A1. Marginal Distribution Sanity Checks
**Script:** `01_marginal_checks.py`
**Data:** `Cropped_Iowa/{BC,BCPC,Raw,GridMET}/` (all on server)

For each GCM × method × variable, during the validation period (2006-2014):
1. Load the BC output and the corresponding GridMET observations (using the variable name mapping: pr→pr, tasmax→tmmx, tasmin→tmmn, rsds→srad, huss→sph, wind→vs).
2. Load the Raw GCM output for comparison.
3. Compute:
   - Mean bias (BC - Obs)
   - MAE
   - QQ plot quantiles (1st through 99th percentile)
   - KS test p-value (does the BC distribution match Obs?)
   - P99 and P1 bias
4. **Expected behavior by method:**
   - **QDM**: Should nearly perfectly match observed marginal quantiles (that's what QDM does). QQ plots should lie on the 1:1 line. If they don't, QDM is wrong.
   - **All MV methods** (MBCn, R2D2, etc.): Marginals should be close to QDM's but with some drift from the multivariate rotation. Slight MAE increase vs QDM is expected.
   - **BCCA**: Known to inflate P99 for precipitation. Verify we see this (~18 mm/d P99 error per Bhuwan's tables).
   - **ECC**: Should perfectly preserve temporal sequencing from the GCM (Lag-1 should match Raw GCM closely). Marginals may be slightly worse than QDM.
5. **Red flags:** QDM not matching observed quantiles; MV methods with dramatically worse marginals than QDM; negative KGE for temperature variables.

#### A2. Inter-Variable Dependence Verification
**Script:** `02_dependence_checks.py`

1. For each method, compute the 6×6 Spearman rank correlation matrix (across all 6 vars) and compare to the observed matrix.
2. Compute Frobenius norm of the error matrix.
3. **Expected behavior:**
   - **Raw GCM**: Highest Frobenius norm (~0.87 per Bhuwan's Table 3).
   - **QDM (univariate)**: Should *not* improve dependence much — it corrects each variable independently, so inter-variable correlations come from the GCM. Frobenius norm should be similar to Raw or slightly better.
   - **MBCn, Gaussian Copula, OTBC**: Should substantially reduce Frobenius norm vs Raw/QDM (~0.17-0.20).
   - **ECC**: Should have one of the lowest Frobenius norms (~0.24) — ECC explicitly reorders to match observed rank structure.
   - **Spatial MBC, BCCA**: These are spatial methods. Frobenius norm may be *worse* than point-wise MV methods (~0.46 for Spatial MBC, ~0.72 for BCCA per Table 3). This is expected — they prioritize spatial coherence over point-wise inter-variable dependence.
4. **Red flags:** QDM dramatically improving dependence (shouldn't); MV methods not improving over Raw; BCCA having better inter-variable dependence than MBCn (would be surprising).

#### A3. Temporal Persistence Check
**Script:** `03_temporal_checks.py`

1. Compute Lag-1 autocorrelation for each variable per pixel (subsample for speed), compare BC vs Obs.
2. Compute dry spell length distributions for PR.
3. **Expected behavior:**
   - **QDM**: Should preserve GCM temporal structure. Lag-1 error should be close to Raw GCM.
   - **ECC (Schaake)**: Should have very low Lag-1 error for temperature (it reorders to match observed sequencing). However, PR Lag-1 error will be *high* (~0.21 per Table 4) because rank reordering of a zero-inflated variable is disruptive.
   - **R2D2**: Known to badly disrupt temporal structure (~0.16-0.21 Lag-1 error across most vars per Table 4). This is expected — R2D2 resamples sub-dimensions.
   - **MBCn**: Iterative rotation destroys temporal ordering. Lag-1 error should be moderate.
   - **Spatial MBC**: Should have elevated Lag-1 errors across most vars (~0.10-0.22 per Table 4).
4. **Red flags:** R2D2 preserving temporal structure well (it shouldn't); QDM having much worse Lag-1 than Raw.

#### A4. Physics Correction Verification
**Script:** `04_physics_checks.py`

Using `Cropped_Iowa/BC/` (pre-physics) vs `Cropped_Iowa/BCPC/` (post-physics):
1. For each method, compare BC and BCPC huss outputs.
   - Count how many space-time points were adjusted (violation rate).
   - Compute saturation specific humidity from tasmax and check if any BCPC huss values still exceed it.
   - Compare 99th percentile of huss before/after correction.
2. Compare tasmax and tasmin:
   - Count how many points have tasmax < tasmin in BC (should be fixed in BCPC).
3. **Expected behavior:**
   - Univariate QDM should have the highest violation rate (~17%) — it doesn't preserve T-q dependence.
   - MV methods should have lower violation rates (~14-16%).
   - Spatial MBC should have the lowest point-wise violation rate (~6%) — it directly accounts for spatial covariance.
   - After physics correction, there should be zero violations (huss ≤ q_sat, tasmax ≥ tasmin everywhere).
4. **Red flags:** BCPC still having violations; violation rates dramatically different from Bhuwan's Table (Physics_Constraint_Impact_Table.csv); physics correction changing more than ~5% of the 99th percentile.

**Note:** The cropped Iowa data only has 5 of the 8 BC methods in BC/BCPC (mv_bcca, mv_ecc_schaake, mv_gaussian_copula, mv_mbcn_iterative, mv_otbc, mv_r2d2, mv_spatial_mbc, qdm). All 8 are present. Physics checks should be done on all available methods.

#### A5. Cross-Check Against Bhuwan's Published Metrics
**Script:** `05_reproduce_tables.py`

Reproduce Bhuwan's Table 2 (Marginal MAE) and Table 3 (Frobenius Norm) using only the cropped Iowa data and compare. The numbers won't match exactly (Bhuwan used CONUS-scale data, we're using Iowa only), but the *ranking* of methods should be consistent. If method X beats method Y at CONUS scale, it should generally beat it over Iowa too.

---

### Part B: Plotting

#### B1. Reproduce Key Publication Figures for Iowa
**Script:** `06_iowa_validation_plots.py`

Since we can't run Bhuwan's plotting scripts (they need `evaluate_multivariate_v2.py` and CONUS data from cylo-bshah), we produce equivalent plots over the Iowa domain:

1. **Marginal bias maps** (equivalent to Bhuwan's Fig 1): For each BC method, plot the spatial mean bias (BC - Obs) over Iowa for pr and tasmax. Use pcolormesh with the Iowa lat/lon grid.

2. **QQ plots per method**: For a representative pixel (or domain-averaged), plot observed vs BC quantiles for each method. Helps visually confirm marginal fidelity.

3. **Spearman correlation error heatmaps** (equivalent to Fig 2): 6×6 heatmap per method, showing the difference from observed Spearman matrix.

4. **Compound extreme density plots** (equivalent to Fig 3): Joint KDE of tasmax vs pr for Obs, Raw, QDM, and a few MV methods.

5. **Dry spell distribution** (equivalent to Fig 4): KDE of dry spell lengths by method.

6. **Summary bar chart** (equivalent to Fig 0): MAE, Lag-1 error, monthly KGE, Frobenius norm — one grouped bar chart comparing all methods.

#### B2. Physics Correction Before/After Plots
**Script:** `07_physics_plots.py`

1. **Psychrometric scatter**: For each method, scatter huss vs tasmax (or tasmin) with the saturation curve overlaid. Show pre-correction (BC) and post-correction (BCPC) side by side.

2. **Violation rate bar chart**: Bar chart of violation % by method, comparing our Iowa numbers to Bhuwan's CONUS-CMCC numbers.

3. **Spatial violation frequency map**: For Iowa, map the fraction of time steps where huss > q_sat before physics correction.

#### B3. Method Comparison Summary Table
**Script:** `08_summary_table.py`

Produce a single CSV ranking all methods across:
- Marginal MAE (per variable)
- P99 bias (per variable)
- Frobenius norm (dependence)
- Lag-1 error (per variable)
- Monthly KGE (per variable)
- Physics violation rate

Color-code or rank to make it easy to see which method wins on which dimension. This is the "at a glance" deliverable for Bhuwan.

---

## Execution Order

1. **`01_marginal_checks.py`** — runs first, outputs per-method per-variable metric CSVs
2. **`02_dependence_checks.py`** — needs only raw data, independent of step 1
3. **`03_temporal_checks.py`** — independent
4. **`04_physics_checks.py`** — independent (uses BC vs BCPC)
5. **`05_reproduce_tables.py`** — reads outputs from steps 1-3 to build the comparison table
6. **`06_iowa_validation_plots.py`** — reads raw data + metrics from steps 1-3
7. **`07_physics_plots.py`** — reads raw data from step 4
8. **`08_summary_table.py`** — aggregates everything

Steps 1-4 can run in parallel. Steps 5-8 depend on 1-4.

## Data Paths

All scripts should use these paths:

```python
SERVER = r"\\abe-cylo\modelsdev\Projects\WRC_DOR"
DATA   = f"{SERVER}\\Data\\Cropped_Iowa"

BC_DIR    = f"{DATA}\\BC"        # Pre-physics correction
BCPC_DIR  = f"{DATA}\\BCPC"      # Post-physics correction
RAW_DIR   = f"{DATA}\\Raw"       # Raw GCM
OBS_DIR   = f"{DATA}\\GridMET"   # Observed GridMET

MODELS = ["CMCC", "EC", "GFDL", "MPI", "MRI"]
METHODS = ["qdm", "mv_bcca", "mv_ecc_schaake", "mv_gaussian_copula",
           "mv_mbcn_iterative", "mv_otbc", "mv_r2d2", "mv_spatial_mbc"]

# Variable name mapping (BC/Raw → GridMET)
VAR_MAP = {
    "pr": "pr", "tasmax": "tmmx", "tasmin": "tmmn",
    "rsds": "srad", "huss": "sph", "wind": "vs"
}

# Validation period
VAL_START = 2006
VAL_END   = 2014

# Output
OUT_DIR = r"C:\drops-of-resilience\bias-correction-validation\output"
```

## Key Risks and Unknowns

1. **NPZ file format**: We need to discover the array keys and shapes inside the `.npz` files. The first thing each script does should be a diagnostic print of the keys and shapes of a sample file from each data source (BC, BCPC, Raw, GridMET).

2. **Date alignment**: BC files span 1850-2014 (historical) or 2015-2100 (SSP585) in a single file. GridMET has yearly files (1981-2014). We need to extract the 2006-2014 slice from the BC data. The BC filenames contain date ranges (e.g., `18500101-20141231`); we'll need to compute the correct array index for 2006-01-01 using day counts from 1850-01-01 (accounting for leap years).

3. **Grid alignment**: BC data is on the ~100km GCM grid cropped to Iowa. GridMET is on a 4km grid cropped to Iowa. These grids are *different*. Bhuwan's CONUS-scale scripts use `Gridmet-4km-Regrided-to-100km` — GridMET already regridded to the GCM grid. The cropped Iowa GridMET in `Data/Cropped_Iowa/GridMET/` might be at 4km or 100km. We must check the shapes. If they differ, we need to regrid one to match (likely aggregate GridMET to 100km, or use the 100km-regridded GridMET if available on server).

4. **Wind variable**: Raw GCM has `uas` and `vas` (components). BC outputs have `wind` (speed). GridMET has `vs` (speed). For Raw comparisons, wind = sqrt(uas^2 + vas^2).

5. **Temperature units**: Some GCM data may be in Kelvin (check if mean > 200, then subtract 273.15).

## Deliverables

When complete, the `bias-correction-validation/output/` folder should contain:
- `metrics/` — CSVs from steps 1-5
- `plots/` — PNGs from steps 6-7
- `summary_table.csv` — the master comparison table from step 8
- A brief `findings.md` summarizing what looks correct and what (if anything) looks suspicious
