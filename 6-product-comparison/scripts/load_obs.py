"""GridMET targets memmap (same file as test8 calibration targets)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg


def dates_main() -> pd.DatetimeIndex:
    return pd.date_range("1981-01-01", "2014-12-31", freq="D")


def _index_range_inclusive(dates: pd.DatetimeIndex, date_start: str, date_end: str) -> tuple[int, int]:
    """Contiguous day indices in `dates` (daily, sorted). Avoids loading the full memmap time axis."""
    ts0, ts1 = pd.Timestamp(date_start), pd.Timestamp(date_end)
    i0 = int(dates.searchsorted(ts0))
    i1 = int(dates.searchsorted(ts1, side="right")) - 1
    if i0 > i1 or i0 >= len(dates):
        raise ValueError(f"No days in [{date_start}, {date_end}] on main calendar")
    return i0, i1


def load_obs_memmap_slice(var: str, date_start: str, date_end: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """GridMET targets for var on [date_start, date_end] inclusive (main 1981–2014 calendar).

    Slices the memmap to the needed day range only (does not materialize all ~12k days).
    Returns float32 stacks to halve RAM vs float64; metrics/plots accept float32.
    """
    idx = cfg.VARS.index(var)
    mm = np.memmap(
        str(cfg.GRIDMET_TARGETS),
        dtype="float32",
        mode="r",
        shape=(cfg.N_DAYS_MAIN, len(cfg.VARS), cfg.H, cfg.W),
    )
    dates = dates_main()
    assert len(dates) == mm.shape[0]
    i0, i1 = _index_range_inclusive(dates, date_start, date_end)
    # View then copy only [i0:i1+1] — typically ~3.3k days for validation vs 12.4k full
    sub = np.asarray(mm[i0 : i1 + 1, idx, :, :], dtype=np.float32)
    return sub, dates[i0 : i1 + 1]


def load_obs_validation(var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    return load_obs_memmap_slice(var, cfg.VAL_START, cfg.VAL_END)


def load_obs_historical_full(var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """Full historical 1981-01-01 .. 2014-12-31 (GridMET targets)."""
    return load_obs_memmap_slice(var, cfg.HIST_START, cfg.HIST_END)
