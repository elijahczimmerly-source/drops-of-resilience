"""
regrid_to_gridmet_bilinear.py — Regrid bias-corrected MPI GCM from 100km -> 4km (local pipeline).

**Bilinear** for all variables including precipitation (ppt → pr), matching Bhuwan’s test8_v2 Iowa protocol.
Other stacks may use conservative PR on the server; this local pipeline uses linear regrid for pr as well.
GridMET provides target lat/lon only (no observational interpolation in this step).

Paths default under ``pipeline/data/``; override with environment variables (see ``README.md`` in this folder).

Memory: regridding runs in time chunks and streams to regridded_*.npy via memmap.
  DOR_REGRID_TIME_CHUNK — days per chunk (default tuned for ~32GB RAM; lower if OOM).
  DOR_MEMMAP_POOL_WORKERS — worker processes for .dat fill phase (default 4).
  DOR_REGRID_OVERWRITE_PR=1 — delete regridded_hist_pr.npy / regridded_fut_pr.npy before the
    existence check so PR is rebuilt (use after switching PR method or fixing a bad run).
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import gc
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

from regrid_paths import output_dir_bilinear, paths_for_regrid

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = output_dir_bilinear()
os.makedirs(OUTPUT_DIR, exist_ok=True)
PATHS = paths_for_regrid()

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

# All vars bilinear (xarray-regrid `.linear`), including pr — Iowa test8_v2 parity
REGRID_METHOD = {
    "ppt":  "bilinear",
    "tmax": "bilinear",
    "tmin": "bilinear",
    "srad": "bilinear",
    "vs":   "bilinear",
    "sph":  "bilinear",
}

HIST_START, HIST_END = "1981-01-01", "2014-12-31"
FUT_START, FUT_END   = "2015-01-01", "2100-12-31"

# ~32GB RAM: default 200 days/chunk ≈2.2× fewer iterations than 90.
# If memory spikes, set DOR_REGRID_TIME_CHUNK=120 (or 90).
REGRID_TIME_CHUNK = int(os.environ.get("DOR_REGRID_TIME_CHUNK", "200"))
MEMMAP_POOL_WORKERS = int(os.environ.get("DOR_MEMMAP_POOL_WORKERS", "4"))

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
    method: 'conservative' | 'nearest' | 'linear' | 'bilinear' (bilinear → .linear)
    """
    if method == "conservative":
        return src_da.regrid.conservative(dst_grid_ds, latitude_coord="lat")
    if method == "nearest":
        return src_da.regrid.nearest(dst_grid_ds)
    # 'linear', 'bilinear', or legacy aliases
    return src_da.regrid.linear(dst_grid_ds)


def _method_label(tar_var):
    m = REGRID_METHOD.get(tar_var, "bilinear")
    return "conservative" if m == "conservative" else "bilinear"


def _chunk_to_da(block, lat, lon, var_name, time_start, latlon_1d):
    """block: (time, lat, lon) or (time, y, x); time coords = absolute indices into full series."""
    nt = block.shape[0]
    time_coord = np.arange(time_start, time_start + nt, dtype=np.int64)
    if latlon_1d:
        return xr.DataArray(
            block,
            dims=("time", "lat", "lon"),
            coords={"time": time_coord, "lat": lat, "lon": lon},
            name=var_name,
        )
    return xr.DataArray(
        block,
        dims=("time", "y", "x"),
        coords={
            "time": time_coord,
            "lat": (("y", "x"), lat),
            "lon": (("y", "x"), lon),
        },
        name=var_name,
    )


def regrid_cmip6_file_to_npy(fpath, out_npy_path, var_name, tar_var, dst_grid, method, chunk_days=None):
    """
    Stream regridded (time, dest_lat, dest_lon) to disk: one time-chunk at a time to cap peak RAM.
    Returns output shape tuple.
    """
    if chunk_days is None:
        chunk_days = max(1, REGRID_TIME_CHUNK)

    with np.load(fpath, allow_pickle=True, mmap_mode="r") as npz:
        lat = np.asarray(npz["lat"])
        lon = np.asarray(npz["lon"])
        lon = np.where(lon > 180, lon - 360, lon)
        keys = [k for k in npz.keys() if k not in ["lat", "lon", "time", "years", "elevation"]]
        key = var_name if var_name in npz else (keys[0] if keys else None)
        if key is None:
            raise ValueError(f"No data key in {fpath}")

        data = npz[key]
        if data.ndim != 3:
            raise ValueError(f"Expected 3D (time, lat, lon) data in {fpath}, got shape {data.shape}")

        latlon_1d = lat.ndim == 1 and lon.ndim == 1
        if not latlon_1d and not (lat.ndim == 2 and lon.ndim == 2):
            raise ValueError(f"Unexpected lat/lon shapes in {fpath}")

        n_time = int(data.shape[0])
        probe = np.asarray(data[0:1], dtype=np.float32)
        da0 = _chunk_to_da(probe, lat, lon, var_name, 0, latlon_1d)
        rg0 = regrid_var(da0, dst_grid, method)
        _, h_out, w_out = rg0.values.shape
        del da0, rg0
        gc.collect()

        mm = np.lib.format.open_memmap(
            out_npy_path, mode="w+", dtype=np.float32, shape=(n_time, h_out, w_out)
        )
        try:
            for start in range(0, n_time, chunk_days):
                end = min(start + chunk_days, n_time)
                block = np.asarray(data[start:end], dtype=np.float32)
                da = _chunk_to_da(block, lat, lon, var_name, start, latlon_1d)
                rg = regrid_var(da, dst_grid, method)
                mm[start:end] = np.asarray(rg.values, dtype=np.float32)
                del block, da, rg
                gc.collect()
            mm.flush()
        finally:
            del mm
            gc.collect()

    return (n_time, h_out, w_out)


def _find_cmip6_npz(var_name, scenario):
    pattern = "historical" if scenario == "historical" else "ssp585"
    prefix = f"Cropped_{var_name}_"
    files = [
        f
        for f in os.listdir(PATHS["CMIP6"])
        if f.startswith(prefix) and pattern in f and f.endswith(".npz")
    ]
    if not files:
        return None
    return os.path.join(PATHS["CMIP6"], files[0])


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


def _overwrite_pr_memmaps_if_requested():
    flag = os.environ.get("DOR_REGRID_OVERWRITE_PR", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return
    for name in ("regridded_hist_pr.npy", "regridded_fut_pr.npy"):
        p = os.path.join(OUTPUT_DIR, name)
        if os.path.isfile(p):
            os.remove(p)
            print(f"[DOR_REGRID_OVERWRITE_PR] Removed {p}")


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print(f"[regrid bilinear] OUTPUT_DIR={OUTPUT_DIR}")
    print(f"[regrid bilinear] CMIP6={PATHS['CMIP6']}")
    print(f"[regrid bilinear] GridMET={PATHS['GridMET']}")
    _overwrite_pr_memmaps_if_requested()
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
        print(
            f"Regridding CMIP6 (all vars bilinear; time_chunk={REGRID_TIME_CHUNK} days)..."
        )
        for cmip_var, _, tar_var in VAR_MAP:
            h_path = os.path.join(OUTPUT_DIR, f"regridded_hist_{cmip_var}.npy")
            if os.path.exists(h_path):
                print(f"  [SKIP] {cmip_var} historical already regridded.")
                arr = np.load(h_path, mmap_mode='r')
                hist_regridded_paths[cmip_var] = (h_path, arr.shape)
            else:
                f_npz = _find_cmip6_npz(cmip_var, "historical")
                if f_npz is not None:
                    try:
                        shp = regrid_cmip6_file_to_npy(
                            f_npz,
                            h_path,
                            cmip_var,
                            tar_var,
                            dst_grid,
                            REGRID_METHOD[tar_var],
                        )
                        hist_regridded_paths[cmip_var] = (h_path, shp)
                        print(
                            f"  [OK] {cmip_var} historical regridded ({_method_label(tar_var)}) -> {shp}."
                        )
                    except Exception as e:
                        print(f"  [Error] {cmip_var} historical regrid failed: {e}")
                        hist_regridded_paths[cmip_var] = (None, None)
                else:
                    hist_regridded_paths[cmip_var] = (None, None)

            f_path = os.path.join(OUTPUT_DIR, f"regridded_fut_{cmip_var}.npy")
            if os.path.exists(f_path):
                print(f"  [SKIP] {cmip_var} future already regridded.")
                arr = np.load(f_path, mmap_mode='r')
                fut_regridded_paths[cmip_var] = (f_path, arr.shape)
            else:
                f_npz = _find_cmip6_npz(cmip_var, "ssp585")
                if f_npz is not None:
                    try:
                        shp = regrid_cmip6_file_to_npy(
                            f_npz,
                            f_path,
                            cmip_var,
                            tar_var,
                            dst_grid,
                            REGRID_METHOD[tar_var],
                        )
                        fut_regridded_paths[cmip_var] = (f_path, shp)
                        print(
                            f"  [OK] {cmip_var} future regridded ({_method_label(tar_var)}) -> {shp}."
                        )
                    except Exception as e:
                        print(f"  [Error] {cmip_var} future regrid failed: {e}")
                        fut_regridded_paths[cmip_var] = (None, None)
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
    with ProcessPoolExecutor(max_workers=MEMMAP_POOL_WORKERS) as ex:
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
    with ProcessPoolExecutor(max_workers=MEMMAP_POOL_WORKERS) as ex:
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
    with ProcessPoolExecutor(max_workers=MEMMAP_POOL_WORKERS) as ex:
        list(tqdm(ex.map(process_chunk, tasks_fut), total=len(tasks_fut)))

    print("\nSUCCESS. All three periods processed (all variables bilinear, including pr).")
    print(f"  -> {f_in_early}")
    print(f"  -> {f_in}")
    print(f"  -> {f_tar}")
    print(f"  -> {f_in_fut}")
