# pr-splotch-side-by-side figures

Layout is **GridMET (left) | comparison (right)** unless noted. Mean **2006–2014** where applicable.
Blues scaling follows each script (often independent 2–98% per panel).

## DOR / validation attempts (`plot_validation_agg_mean_pr.py`)

| File | What it is |
|------|------------|
| `dor_val_00_baseline_product_comparison.png` | Baseline from 6-product-comparison (DOR blend 0.65). |
| `dor_val_01_plan_debias.png` | `experiment_plan_debias` — legacy debias calibration chain. |
| `dor_val_02_calchain_apr2026full.png` | `experiment_calchain_apr2026full` — calendar AR(1) debias chain. |
| `dor_val_03_attempt3_pass24.png` | `experiment_attempt3_pass24` — `DOR_NOISE_DEBIAS_N_PASSES=24`. |
| `dor_val_04_attempt4_det_floor.png` | `experiment_attempt4_det_floor` — deterministic PR (`Deterministic_V8_Hybrid_pr`). |
| `dor_val_05_attempt5_ratio_smooth_sigma{00,05,10,15,20}.png` | Attempt 5 sweep: `DOR_RATIO_SMOOTH_SIGMA` = 0, 5, 10, 15, 20; debias off. |

## Pipeline stages (`plot_gridmet_pipeline_side_by_side.py`)

| File | What it is |
|------|------------|
| `pipeline_MPI_memmap_regrid_gcm_stage.png` | **regrid-gcm:** GridMET vs `cmip6_inputs` (MPI OTBC) on 4 km memmap grid. |
| `pipeline_MPI_memmap_coarse_bc_stage.png` | **coarse-bc:** GridMET (sampled to GCM grid) vs coarse OTBC+physics NPZ. |
| `pipeline_dor_MPI.png` | **dor:** GridMET vs DOR `Stochastic_V8_Hybrid_pr` (MPI path; default naming). |
| `pipeline_dor_MPI_blend065_experiment.png` | Same style; MPI **blend 0.65** run from `experiment_blend0p65` (explicit regenerate). |
| `pipeline_dor_EC-Earth3.png` | **dor:** GridMET vs EC-Earth3 downscaled PR (`experiment_EC_Earth3` on D: drive). |

## Drivers only (no DOR)

| File | What it is |
|------|------------|
| `drivers_MPI_OTBC_4km_memmap_vs_gridmet_mean_2006-2014.png` | `plot_validation_agg_mean_pr_obs_vs_gcm.py` — OTBC→4 km vs GridMET (not DOR). |

## Raw vs bias-corrected GCM (`plot_raw_vs_bc_mean_pr_gcm_grid.py`)

| File | What it is |
|------|------------|
| `bc_MPI_raw_vs_OTBC_coarse_gcm_mean_2006-2014.png` | MPI: raw vs `mv_otbc` on **coarse** GCM grid. |
| `bc_MPI_raw_vs_OTBC_regridded_4km_mean_2006-2014.png` | MPI: same means **bilinear** to GridMET 4 km lat/lon. |
| `bc_EC-Earth3_raw_vs_OTBC_coarse_gcm_mean_2006-2014.png` | EC-Earth3: raw vs OTBC on coarse grid. |
| `bc_EC-Earth3_raw_vs_OTBC_regridded_4km_mean_2006-2014.png` | EC-Earth3: bilinear to 4 km. |

## Regenerate

- Pipeline: `python 7-fix-pr-splotchiness/scripts/plot_gridmet_pipeline_side_by_side.py --help`
- DOR vs GridMET maps: `plot_validation_agg_mean_pr.py --help`
- Raw vs BC: `plot_raw_vs_bc_mean_pr_gcm_grid.py`
