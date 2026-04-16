"""Load NEX-GDDP-CMIP6 yearly NetCDFs, concat, regrid to Iowa GridMET grid."""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

import config as cfg


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
            times_list.append(pd.to_datetime(out["time"].values).normalize())

    arr = np.concatenate(chunks, axis=0)
    times = pd.DatetimeIndex(np.concatenate(times_list))
    return arr, times
