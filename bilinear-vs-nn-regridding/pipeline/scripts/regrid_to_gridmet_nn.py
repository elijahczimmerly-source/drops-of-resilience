"""
regrid_to_gridmet_nn.py — Regrid bias-corrected MPI GCM from 100km -> 4km using NEAREST-NEIGHBOR.

Nearest-neighbor variant of regrid_to_gridmet.py. All variables (including pr) use nearest-neighbor
assignment instead of bilinear/conservative. Output .dat files go to:
  C:/drops-of-resilience/week3/pipeline/data/nearest_neighbor/

Source CMIP6 files expected in:
  C:/drops-of-resilience/week3/pipeline/source_bc/  (produced by crop_bc_mpi_local.py)

GridMET files (grid skeleton only) expected in:
  C:/drops-of-resilience/week3/pipeline/gridmet_cropped/  (produced by crop_gridmet_local.py)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import xarray as xr
import xarray_regrid  # registers .regrid accessor
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from PIL import Image
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = r"C:\drops-of-resilience\week3\pipeline\data\nearest_neighbor"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PATHS = {
    "CMIP6":   r"C:\drops-of-resilience\week3\pipeline\source_bc",
    "PRISM":   r"D:\Research\Projects\WRC\Cropped_PRISM_800m",
    "GridMET": r"C:\drops-of-resilience\week3\pipeline\gridmet_cropped",
    "Geo":     r"D:\Research\Projects\WRC\Cropped_Geospatial",
    "WindEffect": r"E:\SpatialDownscaling\Data_WindEffect_Static"
}

VAR_MAP = [
    ("pr",     "GridMET", "ppt"),
    ("tasmax", "GridMET", "tmax"),
    ("tasmin", "GridMET", "tmin"),
    ("rsds",   "GridMET", "srad"),
    ("wind",   "GridMET", "vs"),
    ("huss",   "GridMET", "sph")
]

GRIDMET_NAME_MAP = {
    "ppt":  "pr",
    "tmax": "tmmx",
    "tmin": "tmmn",
    "srad": "srad",
    "vs":   "vs",
    "sph":  "sph",
}

# All variables use nearest-neighbor
REGRID_METHOD = {
    "ppt":  "nearest",
    "tmax": "nearest",
    "tmin": "nearest",
    "srad": "nearest",
    "vs":   "nearest",
    "sph":  "nearest",
}

HIST_START, HIST_END = "1981-01-01", "2014-12-31"
FUT_START, FUT_END   = "2015-01-01", "2100-12-31"

def get_days_count(start, end):
    return (pd.Timestamp(end) - pd.Timestamp(start)).days + 1

# ==========================================
# ROBUST LOADING FUNCTIONS
# ==========================================
def robust_load_cmip6(var_name, scenario):
    pattern = "historical" if scenario == "historical" else "ssp585"
    prefix = f"Cropped_{var_name}_"
    files = [f for f in os.listdir(PATHS["CMIP6"])
             if f.startswith(prefix) and pattern in f and f.endswith('.npz')]
    if not files:
        print(f"   [Debug] No file found starting with '{prefix}' for {scenario}")
        return None
    fpath = os.path.join(PATHS["CMIP6"], files[0])
    try:
        with np.load(fpath) as npz:
            keys = list(npz.keys())
            candidates = [k for k in keys if k not in ['lat', 'lon', 'time', 'elevation', 'years']]
            if var_name in keys: key = var_name
            elif any(var_name in k for k in candidates):
                key = next(k for k in candidates if var_name in k)
            else: key = candidates[0]
            return npz[key]
    except Exception as e:
        print(f"   [Error] Failed to load CMIP6 {fpath}: {e}")
        return None

def robust_load_target(source, var, year, day_idx=None):
    file_var = GRIDMET_NAME_MAP.get(var, var) if source == "GridMET" else var
    fname = f"Cropped_prism_{file_var}_800m_{year}.npz" if source == "PRISM" else f"Cropped_{file_var}_{year}.nc"
    fpath = os.path.join(PATHS[source], fname)
    if not os.path.exists(fpath):
        return None
    try:
        if fpath.endswith('.npz'):
            with np.load(fpath) as npz:
                keys = list(npz.keys())
                k = next((k for k in keys if var in k), keys[0])
                data = npz[k]
                if day_idx is not None: return data[day_idx]
                return data
        elif fpath.endswith('.nc'):
            with xr.open_dataset(fpath) as ds:
                k = next((k for k in ds.data_vars if var in k), list(ds.data_vars)[0])
                time_dim = next((d for d in ds[k].dims if d in ('time', 'day')), ds[k].dims[0])
                if day_idx is not None: return ds[k].isel({time_dim: day_idx}).values
                return ds[k].values
    except Exception as e:
        print(f"   [Error] Found {fname} but failed to read: {e}")
        return None

def robust_load_geo(var_hint):
    if not os.path.exists(PATHS["Geo"]):
        return None
    files = [f for f in os.listdir(PATHS["Geo"]) if f.endswith('.tif') and var_hint in f]
    if not files: return None
    fpath = os.path.join(PATHS["Geo"], files[0])
    try:
        with rasterio.open(fpath) as src:
            data = src.read(1)
            if src.nodata is not None:
                data = np.where(data == src.nodata, np.nan, data)
            return data
    except Exception as e:
        print(f"Error reading Geo TIFF {fpath}: {e}")
        return None


def regrid_var(src_da, dst_grid_ds, method):
    """
    Regrid a DataArray onto the destination grid using xarray-regrid.
    method: 'conservative', 'nearest', or 'bilinear' (mapped to 'linear')
    """
    if method == "conservative":
        return src_da.regrid.conservative(dst_grid_ds, latitude_coord="lat")
    elif method == "nearest":
        return src_da.regrid.nearest(dst_grid_ds)
    else:
        return src_da.regrid.linear(dst_grid_ds)

def robust_load_cmip6_da(var_name, scenario):
    pattern = "historical" if scenario == "historical" else "ssp585"
    prefix = f"Cropped_{var_name}_"
    files = [f for f in os.listdir(PATHS["CMIP6"])
             if f.startswith(prefix) and pattern in f and f.endswith(".npz")]
    if not files:
        print(f"   [Debug] No CMIP6 file for {var_name} {scenario}")
        return None
    fpath = os.path.join(PATHS["CMIP6"], files[0])
    with np.load(fpath, allow_pickle=True) as npz:
        lat = npz["lat"]
        lon = npz["lon"]
        lon = np.where(lon > 180, lon - 360, lon)
        keys = [k for k in npz.keys() if k not in ["lat", "lon", "time", "years", "elevation"]]
        key = var_name if var_name in npz else (keys[0] if keys else None)
        if key is None:
            print(f"   [Error] No data key found in {fpath}")
            return None
        data = npz[key]
    if lat.ndim == 1 and lon.ndim == 1:
        da = xr.DataArray(data, dims=("time", "lat", "lon"),
                          coords={"time": np.arange(data.shape[0]), "lat": lat, "lon": lon},
                          name=var_name)
    else:
        da = xr.DataArray(data, dims=("time", "y", "x"),
                          coords={"time": np.arange(data.shape[0]), "lat": (("y","x"), lat), "lon": (("y","x"), lon)},
                          name=var_name)
    return da


def get_gridmet_template():
    sample_year = 2011
    ds = xr.open_dataset(os.path.join(PATHS["GridMET"], f"Cropped_pr_{sample_year}.nc"))
    return xr.Dataset(coords={"lat": ds["lat"], "lon": ds["lon"]})


# ==========================================
# PROCESSING LOGIC
# ==========================================
def resize_frame(frame, target_h, target_w):
    if np.isnan(frame).any():
        frame = np.nan_to_num(frame, nan=np.nanmean(frame))
    img = Image.fromarray(frame)
    return np.array(img.resize((target_w, target_h), resample=Image.Resampling.BILINEAR))

def create_geo_static(H, W, generate_static_array=False):
    mask_path = os.path.join(OUTPUT_DIR, "geo_mask.npy")
    if not os.path.exists(mask_path):
        print("Creating Geo Mask from GridMET PR...")
        gridmet_sample = robust_load_target("GridMET", "ppt", 2011, 0)
        if gridmet_sample is not None:
            if gridmet_sample.shape != (H, W):
                gridmet_sample = resize_frame(gridmet_sample, H, W)
            mask = ~np.isnan(gridmet_sample)
            np.save(mask_path, mask.astype('uint8'))
            print(f"   -> Mask Created. Valid Pixels: {np.sum(mask)}")
        else:
            mask = np.ones((H, W), dtype=bool)
            np.save(mask_path, mask.astype('uint8'))

def process_chunk(args):
    mode, start_idx, num_days, start_date, regridded_paths, in_path, tar_path, total_days, cmip_start_date_str, H, W = args
    fp_in = np.memmap(in_path, dtype='float32', mode='r+', shape=(total_days, 6, H, W))
    fp_tar = np.memmap(tar_path, dtype='float32', mode='r+', shape=(total_days, 6, H, W)) if mode == "hist" else None
    current_date = pd.Timestamp(start_date)
    cmip_start_date = pd.Timestamp(cmip_start_date_str)

    buf_in = np.zeros((num_days, 6, H, W), dtype='float32')
    buf_tar = np.zeros((num_days, 6, H, W), dtype='float32') if mode == "hist" else None

    chunk_dates = [current_date + pd.Timedelta(days=i) for i in range(num_days)]
    years = sorted(list(set(d.year for d in chunk_dates)))

    regridded_data = {}
    for cmip_var, (fpath, shape) in regridded_paths.items():
        if fpath is not None:
            regridded_data[cmip_var] = np.load(fpath, mmap_mode='r')

    target_cache = {}
    if mode == "hist":
        for y in years:
            target_cache[y] = {}
            for ch, (_, src, tar_var) in enumerate(VAR_MAP):
                d = robust_load_target(src, tar_var, y)
                if d is not None:
                    target_cache[y][ch] = d

    for day_idx in range(num_days):
        date = chunk_dates[day_idx]
        year = date.year
        doy = date.dayofyear - 1
        cmip_offset = (date - cmip_start_date).days
        for ch, (cmip_var, _, _) in enumerate(VAR_MAP):
            arr = regridded_data.get(cmip_var)
            if arr is not None and cmip_offset < arr.shape[0]:
                buf_in[day_idx, ch] = arr[cmip_offset]
        if mode == "hist":
            for ch in range(6):
                val = 0.0
                if year in target_cache and ch in target_cache[year]:
                    data_cube = target_cache[year][ch]
                    if doy < len(data_cube):
                        val = data_cube[doy]
                buf_tar[day_idx, ch] = np.nan_to_num(val, nan=0.0)

    idx_slice = slice(start_idx, start_idx + num_days)
    fp_in[idx_slice] = buf_in
    if mode == "hist":
        fp_tar[idx_slice] = buf_tar

    stats = {"count": num_days}
    return stats


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    sample = robust_load_target("GridMET", "ppt", 2011, 0)
    H, W = sample.shape
    create_geo_static(H, W)

    dst_grid = get_gridmet_template()

    EARLY_START, EARLY_END = "1850-01-01", "1980-12-31"

    hist_regridded_paths = {}
    fut_regridded_paths = {}
    all_hist_exist = True
    all_fut_exist = True

    for cmip_var, _, _ in VAR_MAP:
        h_path = os.path.join(OUTPUT_DIR, f"regridded_hist_{cmip_var}.npy")
        f_path = os.path.join(OUTPUT_DIR, f"regridded_fut_{cmip_var}.npy")
        if os.path.exists(h_path):
            arr = np.load(h_path, mmap_mode='r')
            hist_regridded_paths[cmip_var] = (h_path, arr.shape)
        else:
            all_hist_exist = False
        if os.path.exists(f_path):
            arr = np.load(f_path, mmap_mode='r')
            fut_regridded_paths[cmip_var] = (f_path, arr.shape)
        else:
            all_fut_exist = False

    if all_hist_exist and all_fut_exist:
        print("[SKIP] All regridded .npy files already exist.")
    else:
        print("Regridding CMIP6 Variables (nearest-neighbor)...")
        for cmip_var, _, tar_var in VAR_MAP:
            h_path = os.path.join(OUTPUT_DIR, f"regridded_hist_{cmip_var}.npy")
            if os.path.exists(h_path):
                print(f"  [SKIP] {cmip_var} historical already regridded.")
                arr = np.load(h_path, mmap_mode='r')
                hist_regridded_paths[cmip_var] = (h_path, arr.shape)
            else:
                da_h = robust_load_cmip6_da(cmip_var, "historical")
                if da_h is not None:
                    rg = regrid_var(da_h, dst_grid, REGRID_METHOD[tar_var])
                    np.save(h_path, rg.values.astype('float32'))
                    hist_regridded_paths[cmip_var] = (h_path, rg.shape)
                    print(f"  [OK] {cmip_var} historical regridded (nearest-neighbor).")
                else:
                    hist_regridded_paths[cmip_var] = (None, None)

            f_path = os.path.join(OUTPUT_DIR, f"regridded_fut_{cmip_var}.npy")
            if os.path.exists(f_path):
                print(f"  [SKIP] {cmip_var} future already regridded.")
                arr = np.load(f_path, mmap_mode='r')
                fut_regridded_paths[cmip_var] = (f_path, arr.shape)
            else:
                da_f = robust_load_cmip6_da(cmip_var, "ssp585")
                if da_f is not None:
                    rg = regrid_var(da_f, dst_grid, REGRID_METHOD[tar_var])
                    np.save(f_path, rg.values.astype('float32'))
                    fut_regridded_paths[cmip_var] = (f_path, arr.shape if 'arr' in dir() else rg.shape)
                    print(f"  [OK] {cmip_var} future regridded (nearest-neighbor).")
                else:
                    fut_regridded_paths[cmip_var] = (None, None)

    # ── PERIOD 1: EARLY HISTORICAL (1850-1980) ──
    days_early = get_days_count(EARLY_START, EARLY_END)
    f_in_early = os.path.join(OUTPUT_DIR, "cmip6_inputs_18500101-19801231.dat")
    np.memmap(f_in_early, dtype='float32', mode='w+', shape=(days_early, 6, H, W))
    tasks_early = []
    curr, c_date = 0, pd.Timestamp(EARLY_START)
    while curr < days_early:
        chunk = 366 if c_date.is_leap_year else 365
        if curr + chunk > days_early: chunk = days_early - curr
        tasks_early.append(("early_hist", curr, chunk, str(c_date.date()),
                            hist_regridded_paths, f_in_early, None,
                            days_early, "1850-01-01", H, W))
        curr += chunk; c_date += pd.Timedelta(days=chunk)
    print(f"Processing Early Historical ({EARLY_START} to {EARLY_END}, {days_early} days)...")
    with ProcessPoolExecutor(max_workers=4) as ex:
        list(tqdm(ex.map(process_chunk, tasks_early), total=len(tasks_early)))

    # ── PERIOD 2: HISTORICAL (1981-2014) ──
    days_h = get_days_count(HIST_START, HIST_END)
    f_in = os.path.join(OUTPUT_DIR, "cmip6_inputs_19810101-20141231.dat")
    f_tar = os.path.join(OUTPUT_DIR, "gridmet_targets_19810101-20141231.dat")
    np.memmap(f_in, dtype='float32', mode='w+', shape=(days_h, 6, H, W))
    np.memmap(f_tar, dtype='float32', mode='w+', shape=(days_h, 6, H, W))
    tasks_hist = []
    curr, c_date = 0, pd.Timestamp(HIST_START)
    while curr < days_h:
        chunk = 366 if c_date.is_leap_year else 365
        if curr + chunk > days_h: chunk = days_h - curr
        tasks_hist.append(("hist", curr, chunk, str(c_date.date()),
                           hist_regridded_paths, f_in, f_tar,
                           days_h, "1850-01-01", H, W))
        curr += chunk; c_date += pd.Timedelta(days=chunk)
    print(f"Processing Historical ({HIST_START} to {HIST_END}, {days_h} days)...")
    with ProcessPoolExecutor(max_workers=4) as ex:
        list(tqdm(ex.map(process_chunk, tasks_hist), total=len(tasks_hist)))

    # ── PERIOD 3: FUTURE (2015-2100) ──
    days_f = get_days_count(FUT_START, FUT_END)
    f_in_fut = os.path.join(OUTPUT_DIR, "cmip6_inputs_ssp585_20150101-21001231.dat")
    np.memmap(f_in_fut, dtype='float32', mode='w+', shape=(days_f, 6, H, W))
    tasks_fut = []
    curr, c_date = 0, pd.Timestamp(FUT_START)
    while curr < days_f:
        chunk = 366 if c_date.is_leap_year else 365
        if curr + chunk > days_f: chunk = days_f - curr
        tasks_fut.append(("fut", curr, chunk, str(c_date.date()),
                          fut_regridded_paths, f_in_fut, None,
                          days_f, "2015-01-01", H, W))
        curr += chunk; c_date += pd.Timedelta(days=chunk)
    print(f"Processing Future ({FUT_START} to {FUT_END}, {days_f} days)...")
    with ProcessPoolExecutor(max_workers=4) as ex:
        list(tqdm(ex.map(process_chunk, tasks_fut), total=len(tasks_fut)))

    print("\nSUCCESS. All three periods processed (nearest-neighbor).")
    print(f"  -> {f_in_early}")
    print(f"  -> {f_in}")
    print(f"  -> {f_tar}")
    print(f"  -> {f_in_fut}")
