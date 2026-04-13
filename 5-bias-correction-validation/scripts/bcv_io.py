"""Load Cropped_Iowa NPZ data: BC, BCPC, Raw, GridMET; align validation period; interp obs to GCM grid."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from bcv_config import (
    BC_DIR,
    BCPC_DIR,
    MODEL_RAW_TOKEN,
    OBS_DIR,
    RAW_DIR,
    VAL_END,
    VAL_START,
    VAR_MAP,
)


def historical_bc_path(
    root: Path,
    model: str,
    method: str,
    var: str,
    *,
    physics_corrected: bool = False,
) -> Path | None:
    """Return path to historical NPZ or None if missing (e.g. qdm has no wind)."""
    d = root / model / method
    if not d.is_dir():
        return None
    if method == "qdm":
        base = f"Cropped_{var}_historical_qdm_1850-01-01_2014-12-31"
        name = f"{base}_physics_corrected.npz" if physics_corrected else f"{base}.npz"
        p = d / name
        return p if p.is_file() else None
    if physics_corrected:
        pat = f"Cropped_{var}_GROUP-*_METHOD-{method}_historical_*_physics_corrected.npz"
        matches = sorted(d.glob(pat))
    else:
        pat = f"Cropped_{var}_GROUP-*_METHOD-{method}_historical_*.npz"
        matches = sorted(m for m in d.glob(pat) if "_physics_corrected" not in m.name)
    if not matches:
        return None
    pref = [m for m in matches if "18500101" in m.name]
    return pref[0] if pref else matches[0]


def raw_year_path(model: str, var: str, year: int) -> Path:
    tok = MODEL_RAW_TOKEN[model]
    y0 = f"{year}0101"
    y1 = f"{year}1231"
    if var == "wind":
        stem = f"Cropped_wind_day_{tok}_historical_r1i1p1f1_gn_{y0}-{y1}.npz"
    else:
        stem = f"Cropped_{var}_day_{tok}_historical_r1i1p1f1_gn_{y0}-{y1}.npz"
    p = RAW_DIR / stem
    if not p.is_file():
        # grid token may be 'gr' for EC
        alt = stem.replace("_gn_", "_gr_")
        p2 = RAW_DIR / alt
        if p2.is_file():
            return p2
    return p


def normalize_time_days(t: np.ndarray) -> np.ndarray:
    """Cast to datetime64[D] for comparisons."""
    return t.astype("datetime64[D]")


def validation_mask(time: np.ndarray) -> np.ndarray:
    t = normalize_time_days(time)
    t0 = np.datetime64(f"{VAL_START}-01-01", "D")
    t1 = np.datetime64(f"{VAL_END}-12-31", "D")
    return (t >= t0) & (t <= t1)


def interp_obs_to_gcm(
    obs_day: np.ndarray,
    lat_obs: np.ndarray,
    lon_obs: np.ndarray,
    lat_gcm: np.ndarray,
    lon_gcm: np.ndarray,
) -> np.ndarray:
    """Bilinear-like linear interpolation of one fine-grid day to GCM centers."""
    lat_obs = np.asarray(lat_obs, dtype=np.float64)
    lon_obs = np.asarray(lon_obs, dtype=np.float64)
    if np.all(np.diff(lat_obs) < 0):
        lat_asc = lat_obs[::-1]
        z = np.asarray(obs_day, dtype=np.float64)[::-1, :]
    else:
        lat_asc = lat_obs
        z = np.asarray(obs_day, dtype=np.float64)
    lon_use = np.where(lon_obs < 0, lon_obs + 360.0, lon_obs)
    lon_gcm = np.asarray(lon_gcm, dtype=np.float64)
    rgi = RegularGridInterpolator(
        (lat_asc, lon_use),
        z,
        bounds_error=False,
        fill_value=np.nan,
    )
    lat_m, lon_m = np.meshgrid(lat_gcm, lon_gcm, indexing="ij")
    pts = np.column_stack([lat_m.ravel(), lon_m.ravel()])
    out = rgi(pts).reshape(lat_gcm.size, lon_gcm.size)
    return out.astype(np.float32)


def load_bc_historical(
    model: str,
    method: str,
    var: str,
    *,
    bcpc: bool = False,
    physics_corrected: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    root = BCPC_DIR if bcpc else BC_DIR
    p = historical_bc_path(root, model, method, var, physics_corrected=physics_corrected)
    if p is None:
        return None
    z = np.load(p, allow_pickle=True)
    return z["data"], z["time"], z["lat"], z["lon"]


def load_raw_concat(model: str, var: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    return load_raw_concat_years(model, var, VAL_START, VAL_END)


def load_raw_concat_years(
    model: str,
    var: str,
    year_start: int,
    year_end: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """Concatenate yearly Raw NPZ files for ``year_start``..``year_end`` (inclusive)."""
    parts = []
    times = []
    lat = lon = None
    for y in range(year_start, year_end + 1):
        p = raw_year_path(model, var, y)
        if not p.is_file():
            return None
        z = np.load(p, allow_pickle=True)
        parts.append(z["data"])
        times.append(normalize_time_days(z["time"]))
        if lat is None:
            lat, lon = z["lat"], z["lon"]
    data = np.concatenate(parts, axis=0)
    time = np.concatenate(times, axis=0)
    return data, time, lat, lon


def prepare_obs_for_bc_dates(
    obs_var: str,
    dates: np.ndarray,
    lat_gcm: np.ndarray,
    lon_gcm: np.ndarray,
) -> np.ndarray:
    """For each calendar day in `dates`, load GridMET and interpolate to GCM grid."""
    dates = normalize_time_days(np.asarray(dates))
    out = np.empty((len(dates), lat_gcm.size, lon_gcm.size), dtype=np.float32)
    year_cache: dict[int, tuple] = {}
    for i, d in enumerate(dates):
        y = int(str(d)[:4])
        if y not in year_cache:
            p = OBS_DIR / f"Cropped_{obs_var}_{y}.npz"
            if not p.is_file():
                raise FileNotFoundError(p)
            z = np.load(p, allow_pickle=True)
            year_cache[y] = (z["data"], z["time"], z["lat"], z["lon"])
        data, time, lat, lon = year_cache[y]
        td = normalize_time_days(time)
        idx = int(np.where(td == d)[0][0])
        out[i] = interp_obs_to_gcm(data[idx], lat, lon, lat_gcm, lon_gcm)
    return out


def obs_values_in_bc_units(obs_var: str, arr: np.ndarray) -> np.ndarray:
    """GridMET temperatures are K; BC/Raw use °C for tasmax/tasmin."""
    if obs_var in ("tmmx", "tmmn"):
        return arr - 273.15
    return arr


def slice_to_bc_validation(
    data: np.ndarray,
    time: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    m = validation_mask(time)
    return data[m], normalize_time_days(time[m])


def slice_to_date_range(
    data: np.ndarray,
    time: np.ndarray,
    start: str,
    end: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Restrict ``data`` to calendar days in ``[start, end]`` (inclusive)."""
    import pandas as pd

    t = normalize_time_days(time)
    t0 = np.datetime64(pd.Timestamp(start), "D")
    t1 = np.datetime64(pd.Timestamp(end), "D")
    m = (t >= t0) & (t <= t1)
    return data[m], normalize_time_days(t[m])


def qsat_kgkg(t_celsius: np.ndarray, pressure_pa: float = 100_000.0) -> np.ndarray:
    """Saturation specific humidity (kg/kg) from Magnus; T in °C."""
    T = np.asarray(t_celsius, dtype=np.float64)
    es = 611.2 * np.exp(17.67 * T / (T + 243.5))
    return (0.622 * es / (pressure_pa - es)).astype(np.float64)


def diagnostic_print_sample() -> None:
    """Plan.md: first step — print keys/shapes for one file per source."""
    print("=== BC mv_otbc pr MPI ===")
    p = historical_bc_path(BC_DIR, "MPI", "mv_otbc", "pr")
    if p:
        z = np.load(p, allow_pickle=True)
        for k in z.files:
            a = z[k]
            print(k, getattr(a, "shape", None), getattr(a, "dtype", None))
    print("=== BC qdm pr MPI ===")
    p2 = historical_bc_path(BC_DIR, "MPI", "qdm", "pr")
    if p2:
        z = np.load(p2, allow_pickle=True)
        for k in z.files:
            a = z[k]
            print(k, getattr(a, "shape", None), getattr(a, "dtype", None))
    print("=== GridMET pr 2006 ===")
    z = np.load(OBS_DIR / "Cropped_pr_2006.npz")
    for k in z.files:
        a = z[k]
        print(k, getattr(a, "shape", None), getattr(a, "dtype", None))
    print("=== Raw pr MPI 2006 ===")
    z = np.load(raw_year_path("MPI", "pr", 2006))
    for k in z.files:
        a = z[k]
        print(k, getattr(a, "shape", None), getattr(a, "dtype", None))
