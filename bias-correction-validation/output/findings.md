# Bias correction validation — findings (Iowa crop, 2006–2014)

## What ran

Scripts `01`–`08` in `bias-correction-validation/` produced:

- `output/metrics/` — CSVs from steps 1–5  
- `output/plots/` — PNGs from steps 6–7  
- `output/summary_table.csv` — merged metrics (step 8)

Re-run everything with: `python run_all.py` from `bias-correction-validation/` (long-running; heavy reads from `\\abe-cylo\...\Cropped_Iowa`).

## Grid and alignment

- **BC / Raw** outputs sit on the **~100 km cropped GCM grid** (e.g. 10×9 for MPI).  
- **GridMET** is **4 km** (216×192). Following `plan.md`, GridMET was **linearly interpolated** to GCM lat/lon with `scipy.interpolate.RegularGridInterpolator`, after shifting observation longitude to **0–360°** to match BC.  
- Marginal and map metrics are therefore comparable **in spirit** to a regrid-to-GCM observation product, but **not** identical to Bhuwan’s CONUS pipeline or conservative area averages.

## File naming (multivariate historical)

- Most models use multivariate historical files starting **1850-01-01**. **MRI** uses **1900-01-01** (`..._historical_19000101-20141231.npz`).  
- `bcv_io.historical_bc_path` resolves multivariate files with a **glob** and prefers the 1850 stem when both exist.

## QDM and `wind`

- Under `BC/MPI/qdm/` (and other models), there is **no** yearly `wind` NPZ — only `huss`, `pr`, `rsds`, `tasmax`, `tasmin`.  
- **01** and **03** therefore have **no row** for `method=qdm, variable=wind`.  
- **02** needs all six variables in one stack, so **qdm is omitted** from dependence / Frobenius summaries.

## Marginal behaviour (sanity)

- **Pooled** `mean_mae` / `mean_qq_rmse` in `05_method_rankings_iowa.csv` mix all variables and models; **qdm does not have the lowest pooled MAE** here (radiation and temperature contribute heavily).  
- **Per-variable** checks in `01_marginal_checks.csv` are more informative: for **qdm**, **huss** has very small `**qq_rmse`** (~0.001), while **pr**, **tasmax**, **tasmin**, and **rsds** show larger QQ gaps — partly expected under **validation-period** evaluation and partly from **observation interpolation** onto the coarse grid (smoothing / mismatch vs native BC grid).  
- **mv_bcca** has the **lowest pooled MAE** but the **largest pooled `qq_rmse`**, consistent with tail distortion (e.g. precipitation) noted in the plan.

## Dependence and temporal structure

- **Frobenius error** (domain-mean daily Spearman vs observations) is **lowest for mv_gaussian_copula** and **next for mv_otbc / mv_mbcn_iterative** in the Iowa aggregate (`05_method_rankings_iowa.csv`). **mv_r2d2** and **mv_bcca** sit at the high-error end, in line with the plan’s expectations.  
- **Lag-1 error** (domain-mean daily) is **lowest for qdm** here; **mv_spatial_mbc** and **mv_r2d2** are high, consistent with known temporal mixing from those families of methods.

## Physics correction

- **Pre-physics** (`BC/`): non-zero fractions of **huss > q_sat(tasmax)** and **tasmax < tasmin** appear for several methods (notably **mv_spatial_mbc** on Iowa).  
- **Post-physics** (`BCPC/` with `_physics_corrected` multivariate files): **tasmax < tasmin → 0** everywhere in the table. **huss > q_sat** drops sharply but a **small residual** remains for some methods (order **1e-4–1e-3** fraction of points), likely from numerical tolerance, time-step vs instantaneous pairing, or the simple Magnus `q_sat` used here vs the production physics routine.

## Caveats

- **KS *p*-values** on huge pooled samples are **not** interpretable as “good model fit” (almost always significant); use QQ / quantile errors and maps instead.  
- **06** bias maps can emit **Mean of empty slice** if interpolation returns all-NaN for a panel; check that GCM lon/lat stay inside the GridMET hull for every model.

## Next steps (optional)

- Add **area-conservative** aggregation from 4 km → GCM cells (e.g. precomputed weights) and compare to linear interpolation.  
- Pull **Bhuwan’s** `Physics_Constraint_Impact_Table.csv` from the server and join on method for a direct CONUS vs Iowa physics comparison.  
- Extend **02** with a **five-variable** mode so **qdm** can enter dependence metrics (excluding wind).