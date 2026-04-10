"""A2: Inter-variable Spearman correlation (domain-mean daily) vs observations."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from bcv_config import BC_VARS, METRICS_DIR, METHODS, MODELS, OUT_DIR, VAR_MAP
from bcv_io import (
    load_bc_historical,
    obs_values_in_bc_units,
    prepare_obs_for_bc_dates,
    slice_to_bc_validation,
)

OUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)


def daily_domain_mean(x: np.ndarray) -> np.ndarray:
    """(T, lat, lon) -> (T,)"""
    return np.nanmean(x, axis=(1, 2))


def spearman_corr_matrix(y: np.ndarray) -> np.ndarray:
    """y shape (T, 6) -> (6,6) Spearman rho."""
    n = y.shape[1]
    out = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            a = y[:, i]
            b = y[:, j]
            m = np.isfinite(a) & np.isfinite(b)
            if m.sum() < 30:
                out[i, j] = out[j, i] = np.nan
            else:
                r, _ = spearmanr(a[m], b[m])
                out[i, j] = out[j, i] = r
    return out


def frobenius_diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b, ord="fro"))


def stack_method(model: str, method: str) -> np.ndarray | None:
    """Return (T, 6) domain-mean BC series aligned in BC_VARS order."""
    series = []
    tref = None
    lat = lon = None
    for var in BC_VARS:
        obs_var = VAR_MAP[var]
        loaded = load_bc_historical(model, method, var)
        if loaded is None:
            return None
        data, time, lat, lon = loaded
        dval, tval = slice_to_bc_validation(data, time)
        if tref is None:
            tref = tval
        elif not np.array_equal(tval, tref):
            return None
        series.append(daily_domain_mean(dval))
    return np.column_stack(series)


def stack_obs(model: str) -> np.ndarray | None:
    """Obs on GCM grid, domain mean; timeline from mv_otbc pr (or qdm pr)."""
    tref = None
    lat = lon = None
    for method_try in ("mv_otbc", "qdm"):
        loaded = load_bc_historical(model, method_try, "pr")
        if loaded is not None:
            _, time, lat, lon = loaded
            _, tref = slice_to_bc_validation(loaded[0], time)
            break
    if tref is None:
        return None
    series = []
    for var in BC_VARS:
        obs_var = VAR_MAP[var]
        obs = prepare_obs_for_bc_dates(obs_var, tref, lat, lon)
        obs = obs_values_in_bc_units(obs_var, obs)
        series.append(daily_domain_mean(obs))
    return np.column_stack(series)


def main():
    rows = []
    for model in MODELS:
        obs_mat = stack_obs(model)
        if obs_mat is None:
            print(f"skip model {model}: obs stack failed")
            continue
        c_obs = spearman_corr_matrix(obs_mat)
        for method in METHODS:
            bc_mat = stack_method(model, method)
            if bc_mat is None:
                continue
            c_bc = spearman_corr_matrix(bc_mat)
            frob = frobenius_diff(c_bc, c_obs)
            rows.append(
                {
                    "model": model,
                    "method": method,
                    "frobenius_spearman_error": frob,
                }
            )
    df = pd.DataFrame(rows)
    out = METRICS_DIR / "02_dependence_checks.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
