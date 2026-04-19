"""Load LOCA2 slices: native Iowa crop or regridded to Iowa GridMET grid (Bhuwan crop_loca2_iowa_MPI patterns)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import config as cfg


def _glob_one(dir_path: Path) -> Path:
    fs = sorted(dir_path.glob("*.nc"))
    if not fs:
        raise FileNotFoundError(f"No .nc in {dir_path}")
    return fs[0]


def load_loca_native(
    var: str,
    lat_ref_1d: np.ndarray,
    lon_ref_1d: np.ndarray,
    *,
    scenario: str = "historical",
    time_start: str | None = None,
    time_end: str | None = None,
) -> tuple[np.ndarray, pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """
    LOCA2 on its native lat/lon slice over Iowa (+buffer bbox from reference GridMET grid).
    Returns (data_Tyx, times, LAT2, LON2) with LAT2/LON2 shape (nlat, nlon).
    """
    if time_start is None:
        time_start = cfg.VAL_START
    if time_end is None:
        time_end = cfg.VAL_END

    base = cfg.LOCA2_ROOT / cfg.GCM_FOLDER / scenario / var
    nc = _glob_one(base)
    with xr.open_dataset(nc) as ds:
        name = cfg.EXTERNAL_VAR[var]
        da = ds[name]

        lon_360 = (np.asarray(lon_ref_1d, dtype=float) + 360.0) % 360.0
        lon_lo = float(lon_360.min()) - 0.5
        lon_hi = float(lon_360.max()) + 0.5

        sub = da.sel(
            lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
            lon=slice(lon_lo, lon_hi),
        )
        sub = sub.sel(time=slice(time_start, time_end))
        if var == "pr":
            sub = sub * 86400.0  # kg m-2 s-1 -> mm/day

        lat1 = np.asarray(sub["lat"].values, dtype=float)
        lon1 = np.asarray(sub["lon"].values, dtype=float)
        LAT2, LON2 = np.meshgrid(lat1, lon1, indexing="ij")

        nt = sub.sizes.get("time", 1)
        chunk = max(16, int(os.environ.get("DOR_LOCA2_TIME_CHUNK", "48")))
        if nt <= chunk:
            arr = np.asarray(sub.values, dtype=np.float32)
            times = pd.to_datetime(sub["time"].values).normalize()
            return arr, pd.DatetimeIndex(times), LAT2, LON2

        parts: list[np.ndarray] = []
        time_parts: list[pd.Timestamp] = []
        for t0 in range(0, nt, chunk):
            t1 = min(t0 + chunk, nt)
            sub_c = sub.isel(time=slice(t0, t1))
            parts.append(np.asarray(sub_c.values, dtype=np.float32))
            time_parts.extend(pd.to_datetime(sub_c["time"].values).normalize().tolist())
        arr = np.concatenate(parts, axis=0)
        times = pd.DatetimeIndex(time_parts)
        return arr, times, LAT2, LON2


# Spatial mesh for Iowa LOCA2 crop is independent of variable (same lat/lon axes per scenario bbox).
_LOCA_MESH_CACHE: tuple[np.ndarray, np.ndarray] | None = None


def get_loca_validation_mesh(lat_ref_1d: np.ndarray, lon_ref_1d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (LAT2, LON2) for the Iowa-buffer crop using the pr historical validation window."""
    global _LOCA_MESH_CACHE
    if _LOCA_MESH_CACHE is not None:
        return _LOCA_MESH_CACHE
    _, _, LAT2, LON2 = load_loca_native(
        "pr",
        lat_ref_1d,
        lon_ref_1d,
        scenario="historical",
        time_start=cfg.VAL_START,
        time_end=cfg.VAL_END,
    )
    _LOCA_MESH_CACHE = (LAT2, LON2)
    return LAT2, LON2


def load_loca_on_grid(
    var: str,
    lat_tgt: np.ndarray,
    lon_tgt: np.ndarray,
    *,
    scenario: str = "historical",
    time_start: str | None = None,
    time_end: str | None = None,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """
    Default time window matches original benchmark: validation 2006–2014.
    Pass time_start/time_end for climate-signal or full-historical loads.
    """
    if time_start is None:
        time_start = cfg.VAL_START
    if time_end is None:
        time_end = cfg.VAL_END

    base = cfg.LOCA2_ROOT / cfg.GCM_FOLDER / scenario / var
    nc = _glob_one(base)
    with xr.open_dataset(nc) as ds:
        name = cfg.EXTERNAL_VAR[var]
        da = ds[name]

        lon_360 = (np.asarray(lon_tgt, dtype=float) + 360.0) % 360.0
        lon_lo = float(lon_360.min()) - 0.5
        lon_hi = float(lon_360.max()) + 0.5

        # Crop time and region *before* unit scaling so we never materialize the full CONUS grid.
        sub = da.sel(
            lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
            lon=slice(lon_lo, lon_hi),
        )
        sub = sub.sel(time=slice(time_start, time_end))
        if var == "pr":
            sub = sub * 86400.0  # kg m-2 s-1 -> mm/day

        lat_1d = np.asarray(lat_tgt, dtype=float)
        LAT2, LON2 = np.meshgrid(lat_1d, lon_360, indexing="ij")
        lat_da = xr.DataArray(LAT2, dims=("y", "x"))
        lon_da = xr.DataArray(LON2, dims=("y", "x"))

        nt = sub.sizes.get("time", 1)
        # Interp one time chunk at a time — full-historical LOCA2 × Iowa mask can exceed RAM otherwise.
        # Small default: full-historical LOCA2 interp is memory-heavy (216×192 × chunk × float64).
        chunk = max(16, int(os.environ.get("DOR_LOCA2_TIME_CHUNK", "48")))
        if nt <= chunk:
            out = sub.interp(lat=lat_da, lon=lon_da)
            times = pd.to_datetime(out["time"].values).normalize()
            arr = np.asarray(out.values, dtype=np.float32)
            return arr, times

        parts: list[np.ndarray] = []
        time_parts: list[pd.Timestamp] = []
        for t0 in range(0, nt, chunk):
            t1 = min(t0 + chunk, nt)
            sub_c = sub.isel(time=slice(t0, t1))
            out_c = sub_c.interp(lat=lat_da, lon=lon_da)
            parts.append(np.asarray(out_c.values, dtype=np.float32))
            time_parts.extend(
                pd.to_datetime(out_c["time"].values).normalize().tolist()
            )
        arr = np.concatenate(parts, axis=0)
        times = pd.DatetimeIndex(time_parts)
    return arr, times
