# pr-splotch-side-by-side figures

Layout is **GridMET (left) | comparison (right)** unless noted. Mean period is set by each script’s `--val-start` / `--val-end` (many figures here use **2006–2014** for validation-era comparisons).

**Canonical PR mean-map styling (“pipeline default”):** independent **2–98%** linear stretch **per panel**, **two colorbars**, helper `_vmin_vmax_one` in `scripts/plot_validation_agg_mean_pr_obs_vs_gcm.py`. Do **not** use `--shared-scale` on `plot_gridmet_pipeline_side_by_side.py dor` unless you want one scale for both panels. Full instructions: `7-fix-pr-splotchiness/PLOTTING.md`.

**Interpreting means:** Short windows (e.g. 2006–2014) can look much rougher than **full historical** (1981–2014) means vs GridMET. See `dor-info.md` (*Time-mean PR maps*) and `7-fix-pr-splotchiness/WORKLOG.md` §12.

**vs `period-comparison/...`:** `plot_period_comparison.py` uses the same default as pipeline `dor`. See `7-fix-pr-splotchiness/DIAGNOSTIC_PERIOD_VS_PIPELINE_DOR.md` for scale history.

## Curated period folders (`1981-2005/`, `1981-2014/`, `2006-2014/`)

Each folder holds **four** MPI figures (mean over that calendar span; en dash in filenames, e.g. `1981–2005`):

| Prefix | File pattern | What it is |
|--------|----------------|------------|
| `0` | `0gridmet_coarse_vs_raw_pr_MPI_mean_<period>.png` | GridMET (to coarse GCM lat/lon) \| **raw** GCM pr |
| `1` | `1gridmet_coarse_vs_OTBC_pr_MPI_mean_<period>.png` | GridMET (coarse) \| **OTBC** pr |
| `2` | `2gridmet_4km_vs_OTBC_regridded_pr_MPI_mean_<period>.png` | GridMET (**4 km**) \| OTBC **bilinear** from coarse to 4 km |
| `3` | `3pipeline_dor_MPI.png` | GridMET \| DOR `Stochastic_V8_Hybrid_pr` (server `v8_2` NPZ) |

**Regenerate BC triple (0–2):** from repo root, with `--output-dir` pointing at the folder and matching `--val-start` / `--val-end`:

`python 7-fix-pr-splotchiness/scripts/plot_raw_vs_bc_mean_pr_gcm_grid.py --output-dir 7-fix-pr-splotchiness/figures/pr-splotch-side-by-side/1981-2005 --val-start 1981-01-01 --val-end 2005-12-31`

(defaults use server `test8_v2/Regridded_Iowa` memmaps + `Cropped_Iowa` via `bcv_config`.)

**Regenerate DOR (3):** `plot_gridmet_pipeline_side_by_side.py dor` with the same memmaps, `--dor-npz` to `Stochastic_V8_Hybrid_pr.npz`, matching `--val-start` / `--val-end`, and `--out` to `.../<folder>/3pipeline_dor_MPI.png`.

`2006-2014/` may also contain `dor_val_00_baseline_product_comparison.png` (6-product baseline).

Legacy **combined** two-panel BC figures (`raw | OTBC` coarse / regridded): pass `--legacy-combined` to `plot_raw_vs_bc_mean_pr_gcm_grid.py` if needed.

## DOR / validation attempts (`plot_validation_agg_mean_pr.py`)

| File | What it is |
|------|------------|
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

MPI **defaults** are the three **GridMET-paired** PNGs under `2006-2014/` (see above). Other models at repo root (e.g. EC-Earth3) may still use the older naming:

| File | What it is |
|------|------------|
| `bc_EC-Earth3_raw_vs_OTBC_coarse_gcm_mean_2006-2014.png` | EC-Earth3: raw vs OTBC on coarse grid. |
| `bc_EC-Earth3_raw_vs_OTBC_regridded_4km_mean_2006-2014.png` | EC-Earth3: bilinear to 4 km. |

## Regenerate

- Pipeline: `python 7-fix-pr-splotchiness/scripts/plot_gridmet_pipeline_side_by_side.py --help`
- DOR vs GridMET maps: `plot_validation_agg_mean_pr.py --help`
- MPI raw / OTBC / GridMET (2006–2014 curated): `python 7-fix-pr-splotchiness/scripts/plot_raw_vs_bc_mean_pr_gcm_grid.py --help`
