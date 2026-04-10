"""
Pooled validation metrics aligned with pipeline/scripts/_test8_sd_impl.calculate_pooled_metrics.
"""
from __future__ import annotations

import numpy as np


def _spatial_bias(sim_3d: np.ndarray, obs_3d: np.ndarray) -> float:
    diff = np.nanmean(sim_3d, axis=0) - np.nanmean(obs_3d, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        v = np.nanmean(diff)
    return float(v) if np.isfinite(v) else float("nan")


def calculate_pooled_metrics(obs_3d: np.ndarray, sim_3d: np.ndarray, var_name: str, label: str = "Val") -> dict:
    obs, sim = obs_3d.flatten(), sim_3d.flatten()
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs_m, sim_m = obs[mask], sim[mask]
    if len(obs_m) == 0:
        return {}
    r = np.corrcoef(obs_m, sim_m)[0, 1] if np.std(obs_m) > 0 and np.std(sim_m) > 0 else 0.0
    alpha = np.std(sim_m) / (np.std(obs_m) + 1e-6)
    beta = np.mean(sim_m) / (np.mean(obs_m) + 1e-6)
    kge = 1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
    rmse_pooled = float(np.sqrt(np.mean((obs_m - sim_m) ** 2)))
    bias = float(np.mean(sim_m) - np.mean(obs_m))
    o99, s99 = np.percentile(obs_m, 99), np.percentile(sim_m, 99)
    ext99_bias = float(((s99 - o99) / (o99 + 1e-6) * 100) if o99 != 0 else 0.0)

    def lag1(a: np.ndarray) -> float:
        ts = np.nanmean(a, axis=(1, 2))
        if len(ts) < 2 or np.std(ts[:-1]) == 0 or np.std(ts[1:]) == 0:
            return 0.0
        return float(np.corrcoef(ts[:-1], ts[1:])[0, 1])

    obs_rho, sim_rho = lag1(obs_3d), lag1(sim_3d)
    out: dict = {
        "Variable": var_name,
        f"{label}_KGE": float(kge),
        f"{label}_RMSE_pooled": rmse_pooled,
        f"{label}_Bias": bias,
        f"{label}_Ext99_Bias%": ext99_bias,
        f"{label}_Lag1_Obs": obs_rho,
        f"{label}_Lag1_Sim": sim_rho,
        f"{label}_Lag1_Err": abs(obs_rho - sim_rho),
        f"{label}_Spatial_Bias": _spatial_bias(sim_3d, obs_3d),
    }
    if var_name == "pr":
        out[f"{label}_WDF_Obs%"] = float(np.mean(obs_m >= 0.1) * 100)
        out[f"{label}_WDF_Sim%"] = float(np.mean(sim_m >= 0.1) * 100)
    return out
