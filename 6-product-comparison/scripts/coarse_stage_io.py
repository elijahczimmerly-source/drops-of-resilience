"""
S2_bc: OTBC + physics-corrected Iowa crop stacks (~100 km) under BCPC/MPI/mv_otbc.
S1_raw: yearly `Cropped_*_day_MPI-ESM1-2-HR_*.npz` under Data/Cropped_Iowa/Raw (Iowa crop ~10×9).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

import config as cfg

VAR_FILES = ("pr", "tasmax", "tasmin", "rsds", "wind", "huss")

# CMIP table stem in Cropped_Iowa/Raw filenames (matches server layout)
_VAR_TABLE = {
    "pr": "pr_day",
    "tasmax": "tasmax_day",
    "tasmin": "tasmin_day",
    "rsds": "rsds_day",
    "wind": "wind_day",
    "huss": "huss_day",
}

_NPZ_DATE_TAIL = re.compile(r"_gn_(\d{8})-(\d{8})\.npz$", re.I)


def bc_pc_otbc_root() -> Path | None:
    if cfg.DOR_CROPPED_BC_ROOT is not None:
        return cfg.DOR_CROPPED_BC_ROOT
    p = cfg.WRC_DOR / "Data" / "Cropped_Iowa" / "BCPC" / "MPI" / "mv_otbc"
    return p if p.is_dir() else None


def _npz_paths(var: str, root: Path) -> tuple[Path, Path]:
    g = "GROUP-huss-pr-rsds-tasmax-tasmin-wind"
    hist = root / (
        f"Cropped_{var}_{g}_METHOD-mv_otbc_historical_18500101-20141231_physics_corrected.npz"
    )
    fut = root / (
        f"Cropped_{var}_{g}_METHOD-mv_otbc_ssp585_20150101-21001231_physics_corrected.npz"
    )
    return hist, fut


def load_s2_bc_otbc_slices(
    var: str,
    hist_start: str,
    hist_end: str,
    fut_start: str,
    fut_end: str,
    *,
    root: Path | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (hist_THW, fut_THW) for BCPC mv_otbc, or None if files missing."""
    r = root or bc_pc_otbc_root()
    if r is None:
        return None
    hp, fp = _npz_paths(var, r)
    if not hp.is_file() or not fp.is_file():
        return None
    zh, zf = np.load(hp), np.load(fp)
    th = pd.to_datetime(zh["time"])
    tf = pd.to_datetime(zf["time"])
    h0, h1 = pd.Timestamp(hist_start), pd.Timestamp(hist_end)
    f0, f1 = pd.Timestamp(fut_start), pd.Timestamp(fut_end)
    mh = (th >= h0) & (th <= h1)
    mf = (tf >= f0) & (tf <= f1)
    if not np.any(mh) or not np.any(mf):
        return None
    return np.asarray(zh["data"], dtype=np.float64)[mh], np.asarray(zf["data"], dtype=np.float64)[mf]


def coarse_mask_from_shape(h: int, w: int) -> np.ndarray:
    return np.ones((h, w), dtype=bool)


def s1_raw_cropped_root() -> Path | None:
    r = cfg.S1_RAW_CROPPED_ROOT
    return r if r.is_dir() else None


def load_s1_raw_cropped_slices(
    var: str,
    hist_start: str,
    hist_end: str,
    fut_start: str,
    fut_end: str,
    *,
    root: Path | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (hist_THW, fut_THW) from raw GCM Iowa-crop yearly NPZs, or None if missing."""
    if var not in _VAR_TABLE:
        return None
    r = root or s1_raw_cropped_root()
    if r is None:
        return None
    table = _VAR_TABLE[var]
    pat = f"Cropped_{table}_MPI-ESM1-2-HR_*_r1i1p1f1_gn_*.npz"
    files = sorted(r.glob(pat))
    if not files:
        return None

    def load_window(scenario: str, t0s: str, t1s: str) -> np.ndarray | None:
        t0, t1 = pd.Timestamp(t0s), pd.Timestamp(t1s)
        chunks: list[np.ndarray] = []
        t_chunks: list[pd.DatetimeIndex] = []
        for fp in files:
            if scenario not in fp.name:
                continue
            m = _NPZ_DATE_TAIL.search(fp.name)
            if not m:
                continue
            f0 = pd.Timestamp(m.group(1))
            f1 = pd.Timestamp(m.group(2))
            if f1 < t0 or f0 > t1:
                continue
            z = np.load(fp)
            arr = np.asarray(z["data"], dtype=np.float64)
            tt = pd.to_datetime(z["time"])
            sel = (tt >= t0) & (tt <= t1)
            if not np.any(sel):
                continue
            chunks.append(arr[sel])
            t_chunks.append(tt[sel])
        if not chunks:
            return None
        data = np.concatenate(chunks, axis=0)
        times = pd.to_datetime(np.concatenate([np.asarray(t, dtype="datetime64[ns]") for t in t_chunks]))
        order = np.argsort(times)
        return data[order]

    h = load_window("historical", hist_start, hist_end)
    f = load_window("ssp585", fut_start, fut_end)
    if h is None or f is None:
        return None
    return h, f
