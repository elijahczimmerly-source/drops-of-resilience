"""Load LOCA2 historical slice, regrid to Iowa GridMET grid."""
from __future__ import annotations

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


def load_loca_on_grid(
    var: str,
    lat_tgt: np.ndarray,
    lon_tgt: np.ndarray,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    base = cfg.LOCA2_ROOT / cfg.GCM_FOLDER / "historical" / var
    nc = _glob_one(base)
    with xr.open_dataset(nc) as ds:
        name = cfg.EXTERNAL_VAR[var]
        da = ds[name]
        if var == "pr":
            da = da * 86400.0  # kg m-2 s-1 -> mm/day

        lon_360 = (np.asarray(lon_tgt, dtype=float) + 360.0) % 360.0
        lon_lo = float(lon_360.min()) - 0.5
        lon_hi = float(lon_360.max()) + 0.5

        sub = da.sel(
            lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
            lon=slice(lon_lo, lon_hi),
        )
        sub = sub.sel(time=slice(cfg.VAL_START, cfg.VAL_END))

        lat_1d = np.asarray(lat_tgt, dtype=float)
        LAT2, LON2 = np.meshgrid(lat_1d, lon_360, indexing="ij")
        out = sub.interp(
            lat=xr.DataArray(LAT2, dims=("y", "x")),
            lon=xr.DataArray(LON2, dims=("y", "x")),
        )

        times = pd.to_datetime(out["time"].values).normalize()
        arr = np.asarray(out.values, dtype=np.float64)
    return arr, times
