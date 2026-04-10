"""
crop_gridmet_local.py
Crops GridMET CONUS .nc files from the server to the Iowa region and saves locally.

Input:  \\abe-cylo\modelsdev\Projects\WRC_DOR\CONUS\{var}_{year}.nc
Output: C:\drops-of-resilience\week3\pipeline\gridmet_cropped\Cropped_{var}_{year}.nc
"""

import xarray as xr
import os
from concurrent.futures import ProcessPoolExecutor

base_path = r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Gridmet-CONUS"
output_dir = r"C:\drops-of-resilience\bilinear-vs-nn-regridding\pipeline\gridmet_cropped"
os.makedirs(output_dir, exist_ok=True)

# Iowa + 3-degree buffer (must match server Cropped_Iowa domain: 216 lat × 192 lon)
LAT_BOUNDS = [37.5, 46.5]
LON_BOUNDS = [-97.5, -89.5]

gridmet_vars = ['vs', 'srad', 'sph', 'pr', 'tmmn', 'tmmx']
years = range(1981, 2015)  # 1981-2014 historical period

def process_single_gridmet(task):
    var, year = task
    file_name = f"{var}_{year}.nc"
    file_path = os.path.join(base_path, file_name)
    save_path = os.path.join(output_dir, f"Cropped_{file_name}")

    if os.path.exists(save_path):
        return f"Skip (exists): {file_name}"

    if not os.path.exists(file_path):
        return f"Missing: {file_name}"

    try:
        with xr.open_dataset(file_path) as ds:
            # GridMET lat is descending (North to South), so slice top -> bottom
            subset = ds.sel(
                lat=slice(LAT_BOUNDS[1], LAT_BOUNDS[0]),
                lon=slice(LON_BOUNDS[0], LON_BOUNDS[1])
            )
            encoding = {v: {'zlib': True, 'complevel': 4} for v in subset.data_vars}
            subset.to_netcdf(save_path, encoding=encoding)
        return f"OK: {file_name} -> {dict(subset.sizes)}"
    except Exception as e:
        return f"Error: {file_name}: {e}"

if __name__ == "__main__":
    tasks = [(v, y) for y in years for v in gridmet_vars]
    print(f"Cropping {len(tasks)} GridMET files to Iowa region...")
    with ProcessPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(process_single_gridmet, tasks))
    print("\n--- Summary ---")
    for r in results:
        print(r)
