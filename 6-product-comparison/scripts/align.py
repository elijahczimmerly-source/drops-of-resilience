"""Align simulator time axis to observation dates (inner join by calendar day)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def align_to_obs(
    sim: np.ndarray,
    sim_dates: pd.DatetimeIndex,
    obs: np.ndarray,
    obs_dates: pd.DatetimeIndex,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (sim_aligned, obs_aligned) with same length and matching days."""
    s_norm = pd.to_datetime(sim_dates).normalize()
    o_norm = pd.to_datetime(obs_dates).normalize()
    dsim = {d: i for i, d in enumerate(s_norm)}
    dobs = {d: i for i, d in enumerate(o_norm)}
    common = sorted(set(dsim) & set(dobs))
    if not common:
        raise ValueError("No overlapping dates between sim and obs")
    si = [dsim[d] for d in common]
    oi = [dobs[d] for d in common]
    return sim[si], obs[oi]


def align_to_obs_with_dates(
    sim: np.ndarray,
    sim_dates: pd.DatetimeIndex,
    obs: np.ndarray,
    obs_dates: pd.DatetimeIndex,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Same as align_to_obs plus the aligned calendar (normalized daily)."""
    s_norm = pd.to_datetime(sim_dates).normalize()
    o_norm = pd.to_datetime(obs_dates).normalize()
    dsim = {d: i for i, d in enumerate(s_norm)}
    dobs = {d: i for i, d in enumerate(o_norm)}
    common = sorted(set(dsim) & set(dobs))
    if not common:
        raise ValueError("No overlapping dates between sim and obs")
    si = [dsim[d] for d in common]
    oi = [dobs[d] for d in common]
    return sim[si], obs[oi], pd.DatetimeIndex(common)
