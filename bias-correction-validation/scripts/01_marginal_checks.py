"""A1: Marginal distribution checks vs GridMET (2006–2014), obs interpolated to GCM grid."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from bcv_config import BC_VARS, METRICS_DIR, METHODS, MODELS, OUT_DIR, VAR_MAP
from bcv_io import (
    load_bc_historical,
    load_raw_concat,
    normalize_time_days,
    obs_values_in_bc_units,
    prepare_obs_for_bc_dates,
    slice_to_bc_validation,
)

OUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)


def _finite_pair(a: np.ndarray, b: np.ndarray, max_n: int = 500_000):
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if a.size > max_n:
        rng = np.random.default_rng(0)
        idx = rng.choice(a.size, size=max_n, replace=False)
        a, b = a[idx], b[idx]
    return a, b


def marginal_metrics(bc: np.ndarray, obs: np.ndarray, raw: np.ndarray | None):
    bc_f, obs_f = _finite_pair(bc.ravel(), obs.ravel())
    mean_bias = float(np.mean(bc_f - obs_f))
    mae = float(np.mean(np.abs(bc_f - obs_f)))
    qs = np.linspace(0.01, 0.99, 50)
    q_bc = np.quantile(bc_f, qs)
    q_obs = np.quantile(obs_f, qs)
    qq_rmse = float(np.sqrt(np.mean((q_bc - q_obs) ** 2)))
    ks = stats.ks_2samp(bc_f, obs_f)
    p1_bias = float(np.percentile(bc_f, 1) - np.percentile(obs_f, 1))
    p99_bias = float(np.percentile(bc_f, 99) - np.percentile(obs_f, 99))
    raw_mean_bias = raw_mae = np.nan
    if raw is not None:
        rw, ob = _finite_pair(raw.ravel(), obs.ravel())
        raw_mean_bias = float(np.mean(rw - ob))
        raw_mae = float(np.mean(np.abs(rw - ob)))
    return {
        "mean_bias": mean_bias,
        "mae": mae,
        "qq_rmse": qq_rmse,
        "ks_statistic": float(ks.statistic),
        "ks_pvalue": float(ks.pvalue),
        "p1_bias": p1_bias,
        "p99_bias": p99_bias,
        "raw_mean_bias": raw_mean_bias,
        "raw_mae": raw_mae,
    }


def main():
    rows = []
    for model in MODELS:
        for method in METHODS:
            for var in BC_VARS:
                obs_var = VAR_MAP[var]
                loaded = load_bc_historical(model, method, var)
                if loaded is None:
                    continue
                data, time, lat, lon = loaded
                dval, tval = slice_to_bc_validation(data, time)
                if dval.size == 0:
                    continue
                obs = prepare_obs_for_bc_dates(obs_var, tval, lat, lon)
                obs = obs_values_in_bc_units(obs_var, obs)
                raw = None
                r = load_raw_concat(model, var)
                if r is not None:
                    rd, rt, _, _ = r
                    rt_d = normalize_time_days(rt)
                    idx = []
                    ok = True
                    for d in tval:
                        w = np.where(rt_d == d)[0]
                        if w.size != 1:
                            ok = False
                            break
                        idx.append(int(w[0]))
                    if ok:
                        raw = rd[idx]
                met = marginal_metrics(dval, obs, raw)
                met.update(
                    {
                        "model": model,
                        "method": method,
                        "variable": var,
                        "n_days": len(tval),
                    }
                )
                rows.append(met)
    df = pd.DataFrame(rows)
    out = METRICS_DIR / "01_marginal_checks.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
