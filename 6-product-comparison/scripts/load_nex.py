"""Load NEX-GDDP-CMIP6 yearly NetCDFs: native Iowa crop or regridded to Iowa GridMET grid."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

import config as cfg


def load_nex_native(
    var: str,
    lat_ref_1d: np.ndarray,
    lon_ref_1d: np.ndarray,
    *,
    scenario: str = "historical",
    year_start: int = 2006,
    year_end: int = 2014,
) -> tuple[np.ndarray, pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """
    NEX on native 0.25° slice over Iowa bbox (+buffer). Returns (T,y,x), times, LAT2, LON2.
    """
    name = cfg.EXTERNAL_VAR[var]
    subdir = cfg.NEX_SUBDIR[var]
    if scenario == "historical":
        pattern = cfg.NEX_FILE_PATTERN[var]
    elif scenario == "ssp585":
        pattern = cfg.NEX_FILE_PATTERN_SSP585[var]
    else:
        raise ValueError(f"Unknown NEX scenario: {scenario}")

    lon_360 = (np.asarray(lon_ref_1d, dtype=float) + 360.0) % 360.0
    lon_lo = float(lon_360.min()) - 0.5
    lon_hi = float(lon_360.max()) + 0.5

    chunks = []
    times_list = []
    lat2 = lon2 = None
    for year in range(year_start, year_end + 1):
        p = cfg.NEX_ROOT / cfg.GCM_FOLDER / scenario / subdir / pattern.format(year=year)
        if not p.is_file():
            raise FileNotFoundError(p)
        with xr.open_dataset(p) as ds:
            da = ds[name]
            if var == "pr":
                da = da * 86400.0
            sub = da.sel(
                lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
                lon=slice(lon_lo, lon_hi),
            )
            if lat2 is None:
                lat1 = np.asarray(sub["lat"].values, dtype=float)
                lon1 = np.asarray(sub["lon"].values, dtype=float)
                lat2, lon2 = np.meshgrid(lat1, lon1, indexing="ij")
            chunks.append(np.asarray(sub.values, dtype=np.float64))
            times_list.append(pd.to_datetime(sub["time"].values).normalize())

    arr = np.concatenate(chunks, axis=0)
    times = pd.DatetimeIndex(np.concatenate(times_list))
    assert lat2 is not None and lon2 is not None
    return arr, times, lat2, lon2


_NEX_MESH_CACHE: tuple[np.ndarray, np.ndarray] | None = None


def get_nex_validation_mesh(lat_ref_1d: np.ndarray, lon_ref_1d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(LAT2, LON2) for NEX Iowa crop on the validation-year range (uses pr)."""
    global _NEX_MESH_CACHE
    if _NEX_MESH_CACHE is not None:
        return _NEX_MESH_CACHE
    _, _, lat2, lon2 = load_nex_native(
        "pr",
        lat_ref_1d,
        lon_ref_1d,
        scenario="historical",
        year_start=int(cfg.VAL_START[:4]),
        year_end=int(cfg.VAL_END[:4]),
    )
    _NEX_MESH_CACHE = (lat2, lon2)
    return lat2, lon2


def load_nex_on_grid(
    var: str,
    lat_tgt: np.ndarray,
    lon_tgt: np.ndarray,
    *,
    scenario: str = "historical",
    year_start: int = 2006,
    year_end: int = 2014,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """
    Default years 2006–2014 match original benchmark.
    Use scenario='ssp585' and year range for future climate-signal windows.
    """
    name = cfg.EXTERNAL_VAR[var]
    subdir = cfg.NEX_SUBDIR[var]
    if scenario == "historical":
        pattern = cfg.NEX_FILE_PATTERN[var]
    elif scenario == "ssp585":
        pattern = cfg.NEX_FILE_PATTERN_SSP585[var]
    else:
        raise ValueError(f"Unknown NEX scenario: {scenario}")

    lon_360 = (np.asarray(lon_tgt, dtype=float) + 360.0) % 360.0
    lon_lo = float(lon_360.min()) - 0.5
    lon_hi = float(lon_360.max()) + 0.5
    lat_1d = np.asarray(lat_tgt, dtype=float)
    LAT2, LON2 = np.meshgrid(lat_1d, lon_360, indexing="ij")

    chunks = []
    times_list = []
    for year in range(year_start, year_end + 1):
        p = cfg.NEX_ROOT / cfg.GCM_FOLDER / scenario / subdir / pattern.format(year=year)
        if not p.is_file():
            raise FileNotFoundError(p)
        with xr.open_dataset(p) as ds:
            da = ds[name]
            if var == "pr":
                da = da * 86400.0
            sub = da.sel(
                lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
                lon=slice(lon_lo, lon_hi),
            )
            out = sub.interp(
                lat=xr.DataArray(LAT2, dims=("y", "x")),
                lon=xr.DataArray(LON2, dims=("y", "x")),
            )
            chunks.append(np.asarray(out.values, dtype=np.float64))
            times_list.append(pd.to_datetime(sub["time"].values).normalize())

    arr = np.concatenate(chunks, axis=0)
    times = pd.DatetimeIndex(np.concatenate(times_list))
    return arr, times
