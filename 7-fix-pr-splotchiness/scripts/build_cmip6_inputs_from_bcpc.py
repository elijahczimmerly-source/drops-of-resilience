"""
Build `cmip6_inputs_19810101-20141231.dat` (test8 driver memmap) from BCPC physics-corrected
OTBC NPZs for any Cropped_Iowa model (e.g. EC = EC-Earth3).

Regridding matches `regrid_to_gridmet_bilinear.py` (xarray-regrid linear / bilinear).

Outputs:
  --out-dat   float32 memmap (12418, 6, H, W) for 1981–01–01 .. 2014–12–31
  --work-dir  regridded_hist_*.npy intermediates (large)

Defaults use `D:\\drops-resilience-data\\ec_cmip6_build\\` when drive D: exists (override with
`DROPS_LARGE_DATA_ROOT`). Keeps huge files off `C:`.

Example:
  python build_cmip6_inputs_from_bcpc.py --model EC
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import xarray_regrid  # noqa: F401 — registers .regrid accessor

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT_DIR = Path(__file__).resolve().parent
_BCV = _REPO / "5-bias-correction-validation" / "scripts"
if str(_BCV) not in sys.path:
    sys.path.insert(0, str(_BCV))

from large_data_root import ec_cmip6_build_dir  # noqa: E402

from bcv_config import BCPC_DIR  # noqa: E402
from bcv_io import historical_bc_path  # noqa: E402

# --- mirror regrid_to_gridmet_bilinear VAR_MAP / methods ---
VAR_MAP = [
    ("pr", "GridMET", "ppt"),
    ("tasmax", "GridMET", "tmax"),
    ("tasmin", "GridMET", "tmin"),
    ("rsds", "GridMET", "srad"),
    ("wind", "GridMET", "vs"),
    ("huss", "GridMET", "sph"),
]

REGRID_METHOD = {
    "ppt": "bilinear",
    "tmax": "bilinear",
    "tmin": "bilinear",
    "srad": "bilinear",
    "vs": "bilinear",
    "sph": "bilinear",
}

REGRID_TIME_CHUNK = int(os.environ.get("DOR_REGRID_TIME_CHUNK", "200"))


def regrid_var(src_da: xr.DataArray, dst_grid_ds: xr.Dataset, method: str) -> xr.DataArray:
    if method == "conservative":
        return src_da.regrid.conservative(dst_grid_ds, latitude_coord="lat")
    if method == "nearest":
        return src_da.regrid.nearest(dst_grid_ds)
    return src_da.regrid.linear(dst_grid_ds)


def _chunk_to_da(block, lat, lon, var_name, time_start, latlon_1d):
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
            raise ValueError(f"Expected 3D data in {fpath}, got {data.shape}")

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


def _dst_grid_from_pr_npz(npz_path: Path) -> xr.Dataset:
    with np.load(npz_path) as z:
        lat = np.asarray(z["lat"], dtype=np.float64)
        lon = np.asarray(z["lon"], dtype=np.float64)
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError(f"Expected 1-D lat/lon in {npz_path}")
    return xr.Dataset(coords={"lat": lat, "lon": lon})


def _fill_cmip6_1981_2014(
    regridded_paths: dict[str, str],
    out_dat: Path,
    h: int,
    w: int,
) -> None:
    t0 = pd.Timestamp("1981-01-01")
    t1 = pd.Timestamp("2014-12-31")
    days_h = (t1 - t0).days + 1
    t1850 = pd.Timestamp("1850-01-01")

    mm = np.memmap(out_dat, dtype=np.float32, mode="w+", shape=(days_h, 6, h, w))
    rdr: dict[str, np.ndarray] = {}
    try:
        for cmip_var, pth in regridded_paths.items():
            rdr[cmip_var] = np.load(pth, mmap_mode="r")

        for day in range(days_h):
            date = t0 + pd.Timedelta(days=day)
            off = (date - t1850).days
            for ch, (cmip_var, _, _) in enumerate(VAR_MAP):
                arr = rdr[cmip_var]
                if off >= arr.shape[0]:
                    mm[day, ch] = np.nan
                else:
                    mm[day, ch] = np.asarray(arr[off], dtype=np.float32)
            if (day + 1) % 2000 == 0:
                mm.flush()
                print(f"  ... wrote day {day + 1}/{days_h}")
        mm.flush()
    finally:
        del mm
        rdr.clear()
        gc.collect()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="EC", help="Short key: EC, GFDL, CMCC, MRI, MPI")
    ap.add_argument("--method", default="mv_otbc")
    ap.add_argument(
        "--gridmet-pr-npz",
        type=Path,
        default=None,
        help="Reference 4 km lat/lon (default: Cropped_pr_2006.npz under GridMET)",
    )
    ap.add_argument(
        "--work-dir",
        type=Path,
        default=ec_cmip6_build_dir() / "regridded_npy",
    )
    ap.add_argument(
        "--out-dat",
        type=Path,
        default=ec_cmip6_build_dir() / "cmip6_inputs_19810101-20141231.dat",
    )
    args = ap.parse_args()

    import bcv_config as cfg

    ref = args.gridmet_pr_npz or (cfg.OBS_DIR / "Cropped_pr_2006.npz")
    if not ref.is_file():
        print(f"ERROR: missing GridMET ref {ref}", file=sys.stderr)
        return 1

    dst = _dst_grid_from_pr_npz(ref)
    h_out, w_out = int(dst.sizes["lat"]), int(dst.sizes["lon"])
    print(f"Destination grid: {h_out} x {w_out}")

    args.work_dir.mkdir(parents=True, exist_ok=True)
    regridded: dict[str, str] = {}

    for cmip_var, _, tar_var in VAR_MAP:
        src = historical_bc_path(
            BCPC_DIR,
            args.model,
            args.method,
            cmip_var,
            physics_corrected=True,
        )
        if src is None:
            print(f"ERROR: missing BCPC for {cmip_var}", file=sys.stderr)
            return 1
        out_npy = args.work_dir / f"regridded_hist_{cmip_var}.npy"
        method = REGRID_METHOD.get(tar_var, "bilinear")
        print(f"Regridding {cmip_var} <- {src.name} ({method}) ...")
        try:
            shp = regrid_cmip6_file_to_npy(
                str(src),
                str(out_npy),
                cmip_var,
                tar_var,
                dst,
                method,
            )
        except Exception as e:
            print(f"ERROR regridding {cmip_var}: {e}", file=sys.stderr)
            return 1
        print(f"  -> {shp}")
        regridded[cmip_var] = str(out_npy)

    args.out_dat.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {args.out_dat} ...")
    _fill_cmip6_1981_2014(regridded, args.out_dat, h_out, w_out)
    print(f"Done: {args.out_dat}")
    print(
        "Point test8 at this file: DOR_TEST8_CMIP6_HIST_DAT=<path>; use the same "
        "gridmet_targets + geo_mask as the MPI run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
