import os
import numpy as np
import xarray as xr
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

"""
Crop LOCA2 North America files to the Iowa 4km grid (216x192).
Target variables: pr, tasmax, tasmin
Periods: 
  - historical: matching 1981-01-01 to 2014-12-31
  - ssp585: matching 2015-01-01 to 2044-12-31 (based on local file existence)
"""

LOCA2_ROOT = r"\\abe-cylo\Cylo-bshah\Spatial_Downscaling\LOCA2\MPI-ESM1-2-HR"
IOWA_REF_DIR = r"E:\SpatialDownscaling\Regridded_Iowa"
OUTPUT_DIR = r"E:\SpatialDownscaling\LOCA2_Cropped_Iowa\MPI-ESM1-2-HR"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Load target grid metadata
ref_npz = np.load(os.path.join(IOWA_REF_DIR, "Regridded_Elevation_4km.npz"))
target_lat = ref_npz['lat'] # (216,) North to South?
target_lon = ref_npz['lon'] # (192,) West to East?
H, W = len(target_lat), len(target_lon)

# Define the bounding box + buffer to ensure overlap
# We use the -180 to 180 scale initially
LAT_BOUNDS = (target_lat.min() - 0.2, target_lat.max() + 0.2)
LON_BOUNDS = (target_lon.min() - 0.2, target_lon.max() + 0.2)

def crop_and_regrid_loca2(var, scenario, period_start, period_end):
    # Find the local NetCDF file
    var_dir = os.path.join(LOCA2_ROOT, scenario, var)
    if not os.path.exists(var_dir):
        print(f"Skipping {var} {scenario}: Directory not found.")
        return
    
    files = [f for f in os.listdir(var_dir) if f.endswith(".nc") and not any(b in f for b in [".monthly", ".yearly", ".DJF", ".JJA", ".MAM", ".SON"])]
    if not files:
        print(f"No daily files in {var_dir}")
        return
        
    # Find file that covers the requested period start
    f_path = None
    for f in files:
        if scenario == "historical" or period_start.split("-")[0] in f:
            f_path = os.path.join(var_dir, f)
            break
            
    if not f_path:
        f_path = os.path.join(var_dir, files[0])
        
    print(f"\nProcessing {var} {scenario} from {f_path}...")
    
    # Open dataset
    ds = xr.open_dataset(f_path, chunks={'time': 100})
    
    # Coordinates in LOCA2 are usually 'lat', 'lon' or 'latitude', 'longitude'
    lat_name = 'lat' if 'lat' in ds.coords else 'latitude'
    lon_name = 'lon' if 'lon' in ds.coords else 'longitude'
    
    # Handle longitude scale (LOCA2 is often 0-360)
    ds_lon = ds[lon_name].values
    if ds_lon.max() > 180:
        print("  Detected 0-360 longitude scale in LOCA2. Converting bounds...")
        lon_min = LON_BOUNDS[0] + 360 if LON_BOUNDS[0] < 0 else LON_BOUNDS[0]
        lon_max = LON_BOUNDS[1] + 360 if LON_BOUNDS[1] < 0 else LON_BOUNDS[1]
        # Ensure min < max
        actual_lon_bounds = (min(lon_min, lon_max), max(lon_min, lon_max))
    else:
        actual_lon_bounds = LON_BOUNDS

    # Slice space (with buffer)
    ds_sel = ds.sel({
        lat_name: slice(LAT_BOUNDS[0], LAT_BOUNDS[1]),
        lon_name: slice(actual_lon_bounds[0], actual_lon_bounds[1])
    })
    
    # Slice time
    ds_sel = ds_sel.sel(time=slice(period_start, period_end))
    
    if len(ds_sel.time) == 0:
        print(f"  Empty time slice for {period_start} to {period_end} in {f_path}")
        return

    print(f"  Input size: {ds_sel.time.shape[0]} days, Grid: {ds_sel[lat_name].shape[0]}x{ds_sel[lon_name].shape[0]}")
    
    # Load into memory (cropped size is much smaller now)
    data_stack = ds_sel[var].values # (time, lat, lon)
    loca_lat = ds_sel[lat_name].values
    loca_lon = ds_sel[lon_name].values
    
    # Convert loca_lon back to -180 if needed for interpolation matching target_lon
    if loca_lon.max() > 180:
        loca_lon = loca_lon - 360
        
    # Ensure input coords for RegularGridInterpolator are strictly increasing
    lat_sort = np.argsort(loca_lat)
    lon_sort = np.argsort(loca_lon)
    loca_lat = loca_lat[lat_sort]
    loca_lon = loca_lon[lon_sort]
    data_stack = data_stack[:, lat_sort, :][:, :, lon_sort]

    # Regrid (Interp) to the EXACT target grid
    print(f"  Interpolating to target {H}x{W} Iowa grid...")
    # data_stack is (time, lat, lon) -> RegularGridInterpolator needs (x, y, z) where x is lat, y is lon, z the values at those points
    # Wait, the data should be (lat, lon, time) for interp_func(points) if points are (lat, lon)
    interp_func = RegularGridInterpolator((loca_lat, loca_lon), data_stack.transpose(1, 2, 0), bounds_error=False, fill_value=None)
    
    # Create target mesh (target_lon is -180..180 already)
    # Note: meshgrid order XY -> grid_lon corresponds to columns, grid_lat to rows
    grid_lon, grid_lat = np.meshgrid(target_lon, target_lat)
    target_points = np.stack([grid_lat.flatten(), grid_lon.flatten()], axis=1)
    
    # Perform interpolation
    regridded_flat = interp_func(target_points) # (H*W, time)
    regridded = regridded_flat.reshape(H, W, -1).transpose(2, 0, 1) # (time, H, W)
    
    # Save as .npz (simpler to compare with user's .npz)
    out_name = f"LOCA2_Iowa_{var}_{scenario}_{period_start.replace('-','')}_{period_end.replace('-','')}.npz"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    np.savez_compressed(out_path, data=regridded.astype('float32'), dates=ds_sel.time.values.astype('datetime64[ns]'))
    print(f"  SUCCESS: Saved {out_name}")
    
    del data_stack, ds_sel, ds, regridded, regridded_flat; import gc; gc.collect()


if __name__ == "__main__":
    # Historical Match
    for v in ["pr", "tasmax", "tasmin"]:
        crop_and_regrid_loca2(v, "historical", "1981-01-01", "2014-12-31")
        
    # Future Match (First block)
    for v in ["pr", "tasmax", "tasmin"]:
        crop_and_regrid_loca2(v, "ssp585", "2015-01-01", "2044-12-31")
