"""
Shared loaders: align DOR, LOCA2, NEX, and GridMET obs on the validation calendar (2006–2014).
Used by run_benchmark.py and plot_validation_period.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config as cfg
from align import align_to_obs_with_dates
from grid_target import load_target_grid
from load_dor import load_dor_variable, validation_mask
from load_loca2 import load_loca_on_grid
from load_nex import load_nex_on_grid
from load_obs import load_obs_validation

LOCA_VARS = frozenset({"pr", "tasmax", "tasmin"})


@dataclass
class AlignedStacks:
    """All arrays (T, H, W); same T and dates."""

    obs: np.ndarray
    dor: np.ndarray
    loca2: np.ndarray | None
    nex: np.ndarray
    dates: pd.DatetimeIndex


def load_aligned_stacks(var: str) -> AlignedStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, obs_dates = load_obs_validation(var)
    dor_full, dor_dates = load_dor_variable(var)
    m = validation_mask(dor_dates)
    dor_a, obs_a, dates = align_to_obs_with_dates(
        dor_full[m], dor_dates[m], obs, obs_dates
    )

    loca_a: np.ndarray | None
    if var in LOCA_VARS:
        loca, lt = load_loca_on_grid(var, lat_tgt, lon_tgt)
        loca_a, _, dates_l = align_to_obs_with_dates(loca, lt, obs, obs_dates)
        if not dates_l.equals(dates):
            raise ValueError(f"LOCA2 date alignment mismatch for {var}")
        if loca_a.shape != obs_a.shape:
            raise ValueError(f"LOCA2 shape mismatch for {var}")
    else:
        loca_a = None

    nex, nt = load_nex_on_grid(var, lat_tgt, lon_tgt)
    nex_a, _, dates_n = align_to_obs_with_dates(nex, nt, obs, obs_dates)
    if not dates_n.equals(dates):
        raise ValueError(f"NEX date alignment mismatch for {var}")
    if nex_a.shape != obs_a.shape:
        raise ValueError(f"NEX shape mismatch for {var}")

    return AlignedStacks(
        obs=obs_a, dor=dor_a, loca2=loca_a, nex=nex_a, dates=dates
    )


def high_pr_obs_date(st: AlignedStacks) -> pd.Timestamp:
    """Calendar day with maximum domain-mean observed pr (for map snapshots)."""
    dom = np.nanmean(st.obs, axis=(1, 2))
    i = int(np.nanargmax(dom))
    return pd.Timestamp(st.dates[i]).normalize()
