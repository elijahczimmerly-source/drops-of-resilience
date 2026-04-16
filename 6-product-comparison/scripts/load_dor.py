"""Load DOR stochastic npz stacks and validation slice (2006–2014)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

import config as cfg


def _dor_product_root() -> Path:
    """Prefer DOR_PRODUCT_DIR; optional shared mirror only with DOR_ALLOW_SHARED_BENCHMARK_MIRROR=1."""
    root = cfg.DOR_PRODUCT_DIR
    if (root / "Stochastic_V8_Hybrid_pr.npz").is_file():
        return root
    if os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return root
    shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    if shared:
        sr = Path(shared)
        if (sr / "Stochastic_V8_Hybrid_pr.npz").is_file():
            return sr
    return root


def load_dor_variable(var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    path = _dor_product_root() / f"Stochastic_V8_Hybrid_{var}.npz"
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
