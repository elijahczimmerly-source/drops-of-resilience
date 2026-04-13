# Local 100 km → 4 km regridding (OTBC → GridMET skeleton)

These scripts build the memmaps / `.dat` stacks used by the stochastic downscaler inputs. They are **not** the same file as Bhuwan’s production script on the server.

## Scripts

| File | Role |
|------|------|
| [`regrid_to_gridmet_bilinear.py`](regrid_to_gridmet_bilinear.py) | **Bilinear** for all six variables (including `pr`), streamed in time chunks. |
| [`regrid_to_gridmet_nn.py`](regrid_to_gridmet_nn.py) | **Nearest-neighbor** for non-`pr` variables; **bilinear** for `pr`. Loads full arrays (higher RAM than bilinear path). |
| [`regrid_paths.py`](regrid_paths.py) | Resolves default directories under `pipeline/data/`. |

## Server production script (not in this repo)

Canonical OTBC regridding for the WRC_DOR project lives on the lab share:

`\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Scripts\regrid_to_gridmet.py`

That version uses **`gridmet_paths.py`** (imports `GRIDMET_DATA_DIR`) and typically **conservative** remapping for precipitation and **bilinear** for other variables. `gridmet_paths.py` is local to Bhuwan’s machine layout and is **not** vendored here; use env-based paths below instead.

## Environment variables

Defaults resolve to subfolders of **`pipeline/data/`** next to the repo `pipeline/` root (see [`regrid_paths.py`](regrid_paths.py)).

| Variable | Purpose |
|----------|---------|
| `DOR_REGRID_OUTPUT_DIR` | Output root for **bilinear** script (`.dat`, `regridded_*.npy`, `geo_mask.npy`). Default: `pipeline/data/regrid_bilinear`. |
| `DOR_NN_DATA_DIR` | Output root for **NN** script (takes precedence over `DOR_REGRID_OUTPUT_DIR` for that script). Default: `pipeline/data/regrid_nearest_neighbor`. |
| `DOR_REGRID_CMIP6_DIR` | Cropped OTBC MPI `.npz` inputs (`Cropped_*`). Default: `pipeline/data/source_bc`. |
| `DOR_REGRID_GRIDMET_DIR` | Cropped GridMET `.nc` skeleton. Default: `pipeline/data/gridmet_cropped`. |
| `DOR_REGRID_GEO_DIR` | Optional GeoTIFFs (elevation/coastal). Default: `pipeline/data/geospatial`. |
| `DOR_REGRID_PRISM_DIR` | Optional PRISM crop. Default: `pipeline/data/prism_800m`. |
| `DOR_REGRID_WINDEFFECT_DIR` | Optional wind-effect static. Default: `pipeline/data/wind_effect_static`. |
| `DOR_REGRID_TIME_CHUNK` | Bilinear streaming chunk size in days (default 200). |
| `DOR_MEMMAP_POOL_WORKERS` | Worker processes for filling `.dat` memmaps (default 4). |
| `DOR_REGRID_OVERWRITE_PR` | Set to `1` to delete `regridded_hist_pr.npy` / `regridded_fut_pr.npy` before a rerun. |

## Dependencies

Install the repo conda env [`../../../environment.yml`](../../../environment.yml). Regridding needs **`xarray-regrid`** and **`rasterio`** (listed under `pip:`).

## How to run

From the repo root (Windows example):

```powershell
conda activate drops-of-resilience
cd c:\drops-of-resilience
python pipeline\scripts\regrid\regrid_to_gridmet_bilinear.py
```

Ensure `DOR_REGRID_GRIDMET_DIR` contains e.g. `Cropped_pr_2011.nc` and `DOR_REGRID_CMIP6_DIR` contains the cropped OTBC files (see `3-bilinear-vs-nn-regridding` crop scripts).
