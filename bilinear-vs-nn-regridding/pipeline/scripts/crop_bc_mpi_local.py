"""
crop_bc_mpi_local.py
Crops physics-corrected OTBC bias-corrected MPI data from the server to Iowa region.

Input:  \\abe-cylo\modelsdev\Projects\WRC_DOR\Bias_Correction\Data\Physics_Corrected_MPI\
            mv_otbc_{scenario}_{startdate}\
            {var}_GROUP-huss-pr-rsds-tasmax-tasmin-wind_METHOD-mv_otbc_{scenario}_{daterange}_physics_corrected.npz
Output: C:\drops-of-resilience\week3\pipeline\source_bc\
            Cropped_{var}_GROUP-..._METHOD-mv_otbc_{scenario}_{daterange}.npz
        (saved without _physics_corrected suffix so regrid_to_gridmet_nn.py can find them)
"""

import numpy as np
import os
from concurrent.futures import ProcessPoolExecutor

BASE_BC = r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Bias_Correction\Data\Physics_Corrected_MPI"
output_dir = r"C:\drops-of-resilience\week3\pipeline\source_bc"
os.makedirs(output_dir, exist_ok=True)

method = "mv_otbc"
group  = "huss-pr-rsds-tasmax-tasmin-wind"

# Iowa bounds + 3-degree buffer (matching original crop_2_scott_bc_mpi.py)
LAT_BOUNDS = [37.5, 46.5]
LON_BOUNDS = [260.0, 273.0]  # 0-360 convention (GCM native)

SCENARIOS = {
    "historical": ("18500101", "20141231"),
    "ssp585":     ("20150101", "21001231"),
}

variables = ['huss', 'pr', 'rsds', 'tasmax', 'tasmin', 'wind']

def get_paths(var, scenario):
    start, end = SCENARIOS[scenario]
    folder = f"{method}_{scenario}_{start}"
    base_name = f"{var}_GROUP-{group}_METHOD-{method}_{scenario}_{start}-{end}"
    src_file  = base_name + "_physics_corrected.npz"
    src_path  = os.path.join(BASE_BC, folder, src_file)
    save_path = os.path.join(output_dir, f"Cropped_{base_name}.npz")
    return src_path, save_path

def process_file(task):
    var, scenario = task
    src_path, save_path = get_paths(var, scenario)

    if os.path.exists(save_path):
        return f"Skip (exists): {var} {scenario}"

    if not os.path.exists(src_path):
        return f"Missing: {src_path}"

    try:
        with np.load(src_path) as data:
            lats = data['lat']
            lons = data['lon']

            lat_idx = np.where((lats >= LAT_BOUNDS[0]) & (lats <= LAT_BOUNDS[1]))[0]
            lon_idx = np.where((lons >= LON_BOUNDS[0]) & (lons <= LON_BOUNDS[1]))[0]

            if len(lat_idx) == 0 or len(lon_idx) == 0:
                return f"Error: region out of bounds for {var} {scenario}"

            cropped = data[var][:, lat_idx[:, None], lon_idx]

            np.savez_compressed(
                save_path,
                **{var: cropped},
                lat=lats[lat_idx],
                lon=lons[lon_idx],
                time=data['time']
            )

        return f"OK: {var} {scenario} -> shape {cropped.shape}"
    except Exception as e:
        return f"Failed {var} {scenario}: {e}"

if __name__ == "__main__":
    tasks = [(v, s) for s in SCENARIOS for v in variables]
    print(f"Cropping {len(tasks)} BC files to Iowa region...")
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_file, tasks))
    print("\n--- Summary ---")
    for r in results:
        print(r)
