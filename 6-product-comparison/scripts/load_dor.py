"""Load DOR stochastic npz stacks and validation slice (2006–2014)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg


def load_dor_variable(var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    path = cfg.DOR_PRODUCT_DIR / f"Stochastic_V8_Hybrid_{var}.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    z = np.load(path)
    data = np.asarray(z["data"], dtype=np.float64)
    dates = pd.to_datetime(z["dates"])
    if data.shape[1:] != (cfg.H, cfg.W):
        raise ValueError(f"{var} shape {data.shape} != (*,{cfg.H},{cfg.W})")
    return data, dates


def validation_mask(dates) -> np.ndarray:
    d = pd.DatetimeIndex(dates)
    return np.asarray(d > pd.Timestamp("2005-12-31"), dtype=bool)
