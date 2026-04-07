"""GridMET targets memmap (same file as test8 calibration targets)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg


def dates_main() -> pd.DatetimeIndex:
    return pd.date_range("1981-01-01", "2014-12-31", freq="D")


def load_obs_validation(var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    idx = cfg.VARS.index(var)
    mm = np.memmap(
        str(cfg.GRIDMET_TARGETS),
        dtype="float32",
        mode="r",
        shape=(cfg.N_DAYS_MAIN, len(cfg.VARS), cfg.H, cfg.W),
    )
    dates = dates_main()
    assert len(dates) == mm.shape[0]
    full = np.asarray(mm[:, idx, :, :], dtype=np.float64)
    mask = np.asarray(dates > pd.Timestamp("2005-12-31"), dtype=bool)
    return full[mask], dates[mask]
