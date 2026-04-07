"""
test8_v2_pr_intensity.py — Local fork of Bhuwan's test8_v2.py + optional PR intensity-dependent ratio.

Fork provenance: copied from server test8_v2.py (see TEST8_V2_SERVER_SOURCE).

Env:
  PR_USE_INTENSITY_RATIO=0|1  — parity (flat PR ratio) vs experiment (p95-blended ratio for pr only)
  TEST8_MAIN_PERIOD_ONLY=1   — default: only 1981–2014 main stack + metrics (skip 1850–1980 / SSP585 I/O)
  TEST8_SEED=<int>           — optional; if set, fixes RNG for reproducibility vs published v2 may differ
  DOR_TEST8_V2_PR_INTENSITY_ROOT — optional absolute path to experiment root (folder with scripts/, data/, output/)
  DOR_TEST8_PR_DATA_DIR     — optional override for memmap directory (default: <root>/data)
  PR_INTENSITY_BLEND       — float in [0, 2], default 1.0; scales (ratio_ext - ratio) * weight when PR_USE_INTENSITY_RATIO=1
  PR_INTENSITY_OUT_TAG     — optional suffix for experiment output subdir (alphanumeric, _, -) to avoid overwriting during sweeps

Original docstring (test8_v2):
  Stochastic Spatial Disaggregation (Post-OTBC); spatial anomaly / ratio + AR(1) FFT noise; v2 Schaake.
"""

import os
import re

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import gc
import json
import hashlib
import random
import time
import warnings
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import torch
import torch.fft

warnings.filterwarnings('ignore')

# --- Fork provenance (recorded in run_manifest.json) ---
TEST8_V2_SERVER_SOURCE = r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Scripts\test8_v2.py"
TEST8_V2_SERVER_LASTWRITE_ISO = "2026-03-30T11:43:15-05:00"

_pr_env = os.environ.get("PR_USE_INTENSITY_RATIO", "0").strip().lower()
PR_USE_INTENSITY_RATIO = _pr_env in ("1", "true", "yes")

MAIN_PERIOD_ONLY = os.environ.get("TEST8_MAIN_PERIOD_ONLY", "1").strip().lower() in ("1", "true", "yes")


def _sanitize_pr_intensity_out_tag(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    out = re.sub(r"[^a-zA-Z0-9_-]+", "_", s).strip("_")
    return out[:80] if out else ""


def _parse_pr_intensity_blend() -> float:
    raw = os.environ.get("PR_INTENSITY_BLEND", "1").strip()
    try:
        v = float(raw)
    except ValueError:
        print(
            f"[WARN] PR_INTENSITY_BLEND={raw!r} invalid; using 1.0",
            file=sys.stderr,
            flush=True,
        )
        return 1.0
    if v < 0.0 or v > 2.0:
        print(
            f"[WARN] PR_INTENSITY_BLEND={v} outside [0, 2]; clamping",
            file=sys.stderr,
            flush=True,
        )
        v = max(0.0, min(2.0, v))
    return v


PR_INTENSITY_BLEND = _parse_pr_intensity_blend()
PR_INTENSITY_OUT_TAG = (
    _sanitize_pr_intensity_out_tag(os.environ.get("PR_INTENSITY_OUT_TAG", ""))
    if PR_USE_INTENSITY_RATIO
    else ""
)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_exp_root_env = os.environ.get("DOR_TEST8_V2_PR_INTENSITY_ROOT", "").strip()
_EXPERIMENT_ROOT = os.path.abspath(
    _exp_root_env if _exp_root_env else os.path.join(_SCRIPTS_DIR, "..")
)
_data_env = os.environ.get("DOR_TEST8_PR_DATA_DIR", "").strip()
BASE_DIR = os.path.abspath(_data_env if _data_env else os.path.join(_EXPERIMENT_ROOT, "data"))
F_INPUTS = os.path.join(BASE_DIR, "cmip6_inputs_19810101-20141231.dat")
F_TARGETS = os.path.join(BASE_DIR, "gridmet_targets_19810101-20141231.dat")
F_MASK = os.path.join(BASE_DIR, "geo_mask.npy")
F_GEO_STATIC = os.path.join(BASE_DIR, "geo_static.npy")
F_INPUTS_EARLY = os.path.join(BASE_DIR, "cmip6_inputs_18500101-19801231.dat")
F_INPUTS_FUTURE = os.path.join(BASE_DIR, "cmip6_inputs_ssp585_20150101-21001231.dat")

_OUTPUT_ROOT = os.path.join(_EXPERIMENT_ROOT, "output", "test8_v2_pr_intensity")
_run_base = "experiment" if PR_USE_INTENSITY_RATIO else "parity"
_RUN_SUBDIR = (
    f"{_run_base}_{PR_INTENSITY_OUT_TAG}" if PR_INTENSITY_OUT_TAG else _run_base
)
OUT_DIR = os.path.join(_OUTPUT_ROOT, _RUN_SUBDIR)
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
VARS_INTERNAL = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
MAX_WORKERS = 1  # 2 parallel variable-workers keeps peak RAM under ~12 GB

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TRAIN_MASK = (DATES_ALL <= "2005-12-31")
TEST_MASK  = (DATES_ALL >  "2005-12-31")
N_DAYS = len(DATES_ALL)

DATES_EARLY = pd.date_range("1850-01-01", "1980-12-31")
N_DAYS_EARLY = len(DATES_EARLY)
DATES_FUTURE = pd.date_range("2015-01-01", "2100-12-31")
N_DAYS_FUTURE = len(DATES_FUTURE)

# --- Method switches ---
USE_GEO_STATIC = False         # DEM + coastal from geo_static.npy (lapse-rate for temp)
MONTHLY_LAPSE_RATES = {
    1: -4.5, 2: -4.5, 3: -5.5, 4: -6.0, 5: -6.5, 6: -6.5,
    7: -6.5, 8: -6.5, 9: -6.0, 10: -5.5, 11: -5.0, 12: -4.5
}

USE_SEMIMONTHLY = True         # 24 semi-monthly windows instead of 12 monthly
STOCHASTIC    = True           # Run with noise (preserves extremes/variability)
DETERMINISTIC = False          # Run without noise (just spatial climatology delta)

# Noise factors (scales the daily residual variance)
NOISE_FACTOR_CONTINUOUS = 0.05      # (additive vars)
NOISE_FACTOR_MULTIPLICATIVE = 0.16  # (pr, wind)
PR_WDF_THRESHOLD_FACTOR = 1.15      # Reduced to ensure spatial texture continuity

try:
    _temp_mask = np.load(F_MASK)
    H, W = _temp_mask.shape
    del _temp_mask
except FileNotFoundError:
    H, W = 84, 96

# device moved inside worker functions to avoid CUDA deadlocks with ProcessPoolExecutor


# Geo static: elevation and coastal (loaded once, shape (H,W)); None if not available
ELEV_2D = None
COASTAL_2D = None
if USE_GEO_STATIC and os.path.exists(F_GEO_STATIC):
    _gs = np.load(F_GEO_STATIC)
    if _gs.shape[0] >= 2:
        ELEV_2D = np.asarray(_gs[0], dtype='float32').reshape(H, W)
        COASTAL_2D = np.asarray(_gs[1], dtype='float32').reshape(H, W)
    del _gs

# ---------------------------------------------------------
# LOGGING HELPER
# ---------------------------------------------------------
_T0 = time.time()

def _ram_gb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024**3
    except ImportError:
        return -1.0

def log(msg):
    elapsed = time.time() - _T0
    ram = _ram_gb()
    ram_str = f" | RAM {ram:.1f} GB" if ram >= 0 else ""
    print(f"[{elapsed:7.1f}s{ram_str}] {msg}", flush=True)

N_PERIODS = 24 if USE_SEMIMONTHLY else 12

def get_period_idx(month, day):
    """Month 1-12, day 1-31 -> period index 0..N_PERIODS-1."""
    if USE_SEMIMONTHLY:
        return (month - 1) * 2 + (0 if day <= 15 else 1)
    return month - 1


def _derive_worker_seed(base_seed: int, var_name: str) -> int:
    d = hashlib.sha256(f"{base_seed}:{var_name}".encode()).digest()
    return int.from_bytes(d[:4], "little") & 0x7FFFFFFF


def _set_deterministic_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _atomic_df_to_csv(df, path: str) -> None:
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_run_manifest(extra=None):
    seed_s = os.environ.get("TEST8_SEED", "").strip()
    manifest = {
        "PR_USE_INTENSITY_RATIO": PR_USE_INTENSITY_RATIO,
        "PR_INTENSITY_BLEND": PR_INTENSITY_BLEND if PR_USE_INTENSITY_RATIO else None,
        "PR_INTENSITY_OUT_TAG": PR_INTENSITY_OUT_TAG or None,
        "TEST8_MAIN_PERIOD_ONLY": MAIN_PERIOD_ONLY,
        "TEST8_SEED": seed_s if seed_s else None,
        "MAX_WORKERS": MAX_WORKERS,
        "EXPERIMENT_ROOT": os.path.abspath(_EXPERIMENT_ROOT),
        "BASE_DIR": os.path.abspath(BASE_DIR),
        "OUT_DIR": os.path.abspath(OUT_DIR),
        "H": H,
        "W": W,
        "N_DAYS": N_DAYS,
        "N_DAYS_EARLY": N_DAYS_EARLY,
        "N_DAYS_FUTURE": N_DAYS_FUTURE,
        "VARS_INTERNAL": VARS_INTERNAL,
        "server_source": TEST8_V2_SERVER_SOURCE,
        "server_lastwrite_iso": TEST8_V2_SERVER_LASTWRITE_ISO,
        "resid_cv_policy": (
            "resid_cv from flat sim_base = in_m * spatial_ratio[p]; "
            "PR y_base may use intensity-blended ratio when PR_USE_INTENSITY_RATIO=1."
        ),
    }
    if extra:
        manifest.update(extra)
    try:
        manifest["script_path"] = os.path.abspath(__file__)
        manifest["script_sha256"] = _sha256_file(__file__)
    except OSError:
        manifest["script_sha256"] = None
    mpath = os.path.join(OUT_DIR, "run_manifest.json")
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, mpath)


# ---------------------------------------------------------
# 2. METRIC ENGINES (unchanged)
# ---------------------------------------------------------
def calculate_pooled_metrics(obs_3d, sim_3d, var_name, label="Val"):
    obs, sim = obs_3d.flatten(), sim_3d.flatten()
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs_m, sim_m = obs[mask], sim[mask]
    if len(obs_m) == 0:
        return {}
    r = np.corrcoef(obs_m, sim_m)[0, 1] if np.std(obs_m) > 0 and np.std(sim_m) > 0 else 0
    alpha = np.std(sim_m) / (np.std(obs_m) + 1e-6)
    beta  = np.mean(sim_m) / (np.mean(obs_m) + 1e-6)
    kge = 1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)
    rmse_pooled = np.sqrt(np.mean((obs_m - sim_m)**2))
    bias = np.mean(sim_m) - np.mean(obs_m)
    o99, s99 = np.percentile(obs_m, 99), np.percentile(sim_m, 99)
    ext99_bias = ((s99 - o99) / (o99 + 1e-6) * 100) if o99 != 0 else 0

    def lag1(a):
        ts = np.nanmean(a, axis=(1, 2))
        return np.corrcoef(ts[:-1], ts[1:])[0, 1]

    obs_rho, sim_rho = lag1(obs_3d), lag1(sim_3d)
    out = {
        "Variable": var_name,
        f"{label}_KGE": kge, f"{label}_RMSE_pooled": rmse_pooled, f"{label}_Bias": bias,
        f"{label}_Ext99_Bias%": ext99_bias,
        f"{label}_Lag1_Obs": obs_rho, f"{label}_Lag1_Sim": sim_rho,
        f"{label}_Lag1_Err": abs(obs_rho - sim_rho),
        f"{label}_Spatial_Bias": np.nanmean(np.nanmean(sim_3d, 0) - np.nanmean(obs_3d, 0)),
    }
    if var_name == "pr":
        out[f"{label}_WDF_Obs%"] = np.mean(obs_m >= 0.1) * 100
        out[f"{label}_WDF_Sim%"] = np.mean(sim_m >= 0.1) * 100
    return out

def calculate_per_cell_summary_metrics(obs_3d, sim_3d, var_name, mask_2d, label="Val"):
    valid = np.isfinite(obs_3d) & np.isfinite(sim_3d)
    obs_w = np.where(valid, obs_3d, np.nan)
    sim_w = np.where(valid, sim_3d, np.nan)

    sq_err = (obs_w - sim_w)**2
    n_valid = np.nansum(valid, axis=0).astype(float)
    n_valid[n_valid < 2] = np.nan
    rmse_pc = np.sqrt(np.nansum(sq_err, axis=0) / n_valid)
    del sq_err

    bias_pc = np.nanmean(sim_w - obs_w, axis=0)
    mean_o = np.nanmean(obs_w, axis=0);  mean_s = np.nanmean(sim_w, axis=0)
    std_o  = np.nanstd(obs_w, axis=0) + 1e-12
    std_s  = np.nanstd(sim_w, axis=0) + 1e-12
    cov = np.nanmean((obs_w - mean_o[None]) * (sim_w - mean_s[None]), axis=0)
    r_pc = cov / (std_o * std_s)
    kge_pc = 1 - np.sqrt((r_pc - 1)**2 + (std_s / std_o - 1)**2 + (mean_s / (mean_o + 1e-12) - 1)**2)
    del obs_w, sim_w

    ts_obs = np.nanmean(obs_3d, axis=(1, 2))
    ts_sim = np.nanmean(sim_3d, axis=(1, 2))
    rmse_dm = np.sqrt(np.nanmean((ts_obs - ts_sim)**2))

    fm = mask_2d.flatten()
    def _stat(arr):
        v = arr.flatten()[fm]; v = v[np.isfinite(v)]
        return (np.mean(v), np.median(v), np.std(v)) if len(v) else (np.nan,)*3

    rm, rmed, rstd = _stat(rmse_pc)
    km, kmed, _ = _stat(kge_pc)
    cm, cmed, _ = _stat(r_pc)
    bm, bmed, _ = _stat(bias_pc)

    return {
        "Variable": var_name,
        f"{label}_RMSE_per_cell_mean": rm, f"{label}_RMSE_per_cell_median": rmed,
        f"{label}_RMSE_per_cell_std": rstd,
        f"{label}_RMSE_domain_mean_ts": rmse_dm,
        f"{label}_KGE_per_cell_mean": km, f"{label}_KGE_per_cell_median": kmed,
        f"{label}_r_per_cell_mean": cm, f"{label}_r_per_cell_median": cmed,
        f"{label}_Bias_per_cell_mean": bm, f"{label}_Bias_per_cell_median": bmed,
        f"{label}_n_cells": int(np.sum(fm)),
    }

def calculate_climatology_summary(data_3d, var_name, period_name, mask_2d):
    flat = data_3d[:, mask_2d]
    flat = flat[np.isfinite(flat)]
    if len(flat) == 0:
        return {"Variable": var_name, "Period": period_name}
    return {
        "Variable": var_name, "Period": period_name,
        "mean": float(np.nanmean(flat)), "std": float(np.nanstd(flat)),
        "p01": float(np.nanpercentile(flat, 1)), "p99": float(np.nanpercentile(flat, 99)),
        "n_days": data_3d.shape[0],
    }

# ---------------------------------------------------------
# 3. HYBRID ENGINES (GPU noise)
# ---------------------------------------------------------
def generate_spatial_noise(shape, correlation_length=4.0, device=None):
    h, w = shape
    noise = torch.randn(h, w, device=device)
    kh = torch.fft.fftfreq(h, device=device).reshape(-1, 1)
    kw = torch.fft.fftfreq(w, device=device).reshape(1, -1)
    kernel = torch.exp(-0.5 * (torch.sqrt(kh**2 + kw**2) * correlation_length)**2)
    filtered = torch.fft.ifftn(torch.fft.fftn(noise) * kernel).real
    return (filtered - filtered.mean()) / (filtered.std() + 1e-8)

class StochasticSpatialDisaggregatorAdditive:
    """For continuous variables: tasmax, tasmin, rsds, huss"""
    def __init__(self, var_idx, var_name, rho=0.8, noise_factor=None, elev_2d=None, correlation_length=5.0, device=None):
        self.var_idx, self.var_name, self.rho = var_idx, var_name, rho
        self.noise_factor = noise_factor if noise_factor is not None else NOISE_FACTOR_CONTINUOUS
        self.elev_2d = elev_2d  # (H,W) for lapse correction on tasmax/tasmin
        self.corr_len = correlation_length
        self.device = device
        self.mask = np.load(F_MASK).flatten() == 1
        
        # Spatial Anomaly Fields
        self.spatial_delta = np.zeros((N_PERIODS, H, W), dtype='float32')
        self.resid_std = np.zeros((N_PERIODS, H, W), dtype='float32')
        self._elev_ref = None

    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating Spatial Anomalies ({N_PERIODS} periods)...")
        for p in range(N_PERIODS):
            if USE_SEMIMONTHLY:
                idx = [i for i in np.where(TRAIN_MASK)[0] if get_period_idx(dates[i].month, dates[i].day) == p]
            else:
                idx = [i for i in np.where(TRAIN_MASK)[0] if dates[i].month == p + 1]
            if len(idx) < 2:
                continue
            
            # inputs = 100km OTBC bilinearly interpolated to 4km
            # targets = 4km GridMET
            in_m  = inputs[idx, self.var_idx].copy()
            tar_m = targets[idx, self.var_idx].copy()
            
            if self.var_name in ["tasmax", "tasmin"] and np.nanmean(in_m) < 150:
                in_m = in_m + 273.15
                
            m_gcm = np.nanmean(in_m, axis=0)
            m_obs = np.nanmean(tar_m, axis=0)
            
            # 1. Calculate Spatial Anomaly (Delta)
            # This preserves the domain mean of the OTBC input while injecting 4km texture
            self.spatial_delta[p] = m_obs - m_gcm
            
            # 2. Calculate Daily Residual Variance (for stochastic noise)
            sim_base = in_m + self.spatial_delta[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_std[p] = np.nanstd(resid, axis=0) + 1e-6

        if self.elev_2d is not None and self.var_name in ["tasmax", "tasmin"]:
            mask_2d = np.load(F_MASK) == 1
            self._elev_ref = float(np.nanmean(self.elev_2d[mask_2d]))

    def downscale_day(self, full_in_data, date_obj, period_idx, prev_noise):
        valid = self.mask & np.isfinite(full_in_data[self.var_idx].flatten())
        if not np.any(valid):
            return np.full((H, W), np.nan, 'f'), None
            
        in_val = full_in_data[self.var_idx].flatten()[valid].copy()
        if self.var_name in ["tasmax", "tasmin"] and np.nanmean(in_val) < 150:
            in_val += 273.15
            
        # 1. Apply Spatial Climatology Delta
        delta = self.spatial_delta[period_idx].flatten()[valid]
        y_base = in_val + delta
        
        # 2. Generate AR(1) Spatial Noise
        with torch.no_grad():
            ns = generate_spatial_noise((H, W), self.corr_len, device=self.device)
            cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
            
        nf = 0.0 if (getattr(self, "_noise_override", None) is not None) else self.noise_factor
        
        # 3. Scale noise by historical daily residual variance
        std_resid = self.resid_std[period_idx].flatten()[valid]
        noise_scaled = cn.cpu().numpy().flatten()[valid] * std_resid * nf
        
        y_final = y_base + noise_scaled
        
        if self.var_name in ["rsds", "huss"]:
            y_final = np.maximum(y_final, 0.0)
            
        out = np.full((H, W), np.nan, 'f')
        out.reshape(-1)[valid] = y_final
        
        # Lapse-rate correction for temperature (elevation covariate)
        if self.elev_2d is not None and self._elev_ref is not None and self.var_name in ["tasmax", "tasmin"]:
            lapse_rate = MONTHLY_LAPSE_RATES[date_obj.month]
            out += (lapse_rate / 1000.0) * (self.elev_2d - self._elev_ref)
            
        return out, cn

class StochasticSpatialDisaggregatorMultiplicative:
    """For zero-bounded variables: pr, wind. Optional PR-only intensity blend (test6-style) when global PR_USE_INTENSITY_RATIO."""
    def __init__(self, var_idx, var_name, rho=0.5, noise_factor=None, elev_2d=None, correlation_length=5.0, device=None):
        self.var_idx, self.var_name, self.rho = var_idx, var_name, rho
        self.noise_factor = noise_factor if noise_factor is not None else NOISE_FACTOR_MULTIPLICATIVE
        self.corr_len = correlation_length
        self.device = device
        self.use_intensity_ratio = PR_USE_INTENSITY_RATIO
        self.mask = np.load(F_MASK).flatten() == 1

        self.spatial_ratio = np.ones((N_PERIODS, H, W), dtype='float32')
        self.resid_cv = np.zeros((N_PERIODS, H, W), dtype='float32')
        self.monthly_threshold = np.zeros((N_PERIODS, H, W), dtype='float32')
        self.hist_temp_mean = 288.15  # Baseline global historical temp proxy
        if self.use_intensity_ratio and var_name == "pr":
            self.spatial_ratio_ext = np.ones((N_PERIODS, H, W), dtype='float32')
            self.gcm_95th = np.zeros((N_PERIODS, H, W), dtype='float32')
        else:
            self.spatial_ratio_ext = None
            self.gcm_95th = None

    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating Spatial Ratios ({N_PERIODS} periods)...")
        for p in range(N_PERIODS):
            if USE_SEMIMONTHLY:
                idx = [i for i in np.where(TRAIN_MASK)[0] if get_period_idx(dates[i].month, dates[i].day) == p]
            else:
                idx = [i for i in np.where(TRAIN_MASK)[0] if dates[i].month == p + 1]
            if len(idx) < 2:
                continue
                
            in_m, tar_m = inputs[idx, self.var_idx], targets[idx, self.var_idx]
            m_gcm = np.nanmean(in_m, axis=0)
            m_obs = np.nanmean(tar_m, axis=0)
            
            # 1. Calculate Spatial Ratio (flat r_base)
            self.spatial_ratio[p] = np.clip(m_obs / (m_gcm + 1e-4), 0.05, 20.0)

            if self.use_intensity_ratio and self.var_name == "pr":
                p95_gcm = np.nanpercentile(in_m, 95, axis=0)
                p95_obs = np.nanpercentile(tar_m, 95, axis=0)
                self.spatial_ratio_ext[p] = np.clip(
                    p95_obs / (p95_gcm + 1e-4), 0.05, 20.0
                )
                self.gcm_95th[p] = np.maximum(p95_gcm.astype("float32"), 0.1)

            # 2. Daily residual CV from flat-ratio sim_base (same as test8_v2 when intensity off)
            sim_base = in_m * self.spatial_ratio[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_cv[p] = np.nanstd(resid, axis=0) / (np.nanmean(sim_base, axis=0) + 1e-4)
            
            # 3. Calculate Wet-Day Threshold for PR
            if self.var_name == "pr":
                sim_m_sorted = np.sort(sim_base, axis=0)
                wdf = np.mean(tar_m >= 0.1, axis=0)
                ti = np.clip(np.round((1 - wdf) * (len(idx) - 1)).astype(int), 0, len(idx) - 1)
                Hi, Wi = np.indices((H, W))
                self.monthly_threshold[p] = sim_m_sorted[ti, Hi, Wi]

    def downscale_day(self, full_in_data, date_obj, period_idx, prev_noise):
        valid = self.mask & np.isfinite(full_in_data[self.var_idx].flatten())
        if not np.any(valid):
            return np.full((H, W), np.nan, 'f'), None
            
        iv = full_in_data[self.var_idx].flatten()[valid].copy()

        # 1. Spatial ratio (PR: optional blend toward r_ext by GCM intensity)
        ratio = self.spatial_ratio[period_idx].flatten()[valid]
        if self.use_intensity_ratio and self.var_name == "pr":
            ratio_ext = self.spatial_ratio_ext[period_idx].flatten()[valid]
            gcm_95 = self.gcm_95th[period_idx].flatten()[valid]
            weight = np.clip(iv / (gcm_95 + 1e-4), 0.0, 1.0)
            ratio = ratio + PR_INTENSITY_BLEND * (ratio_ext - ratio) * weight
        y_base = iv * ratio

        # 2. Generate AR(1) Spatial Noise
        with torch.no_grad():
            ns = generate_spatial_noise((H, W), self.corr_len, device=self.device)
            cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
            
        nf = 0.0 if (getattr(self, "_noise_override", None) is not None) else self.noise_factor
        
        # 3. Apply Multiplicative Noise
        cv_resid = self.resid_cv[period_idx].flatten()[valid]
        noise_mult = 1.0 + cn.cpu().numpy().flatten()[valid] * cv_resid * nf
        noise_mult = np.clip(noise_mult, 0.1, 8.5) # Prevent extreme blowups, but allow high storms
        
        y_final = y_base * noise_mult
        
        # 4. Wet-day censoring
        if self.var_name == "pr":
            th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
            y_final = np.where(y_final <= th, 0, y_final)
            y_final = np.where(y_final < 0.1, 0, y_final)
            y_final = np.clip(y_final, 0, 250.0) # Absolute physical cap for SWAT+ stability
            
        out = np.full((H, W), np.nan, 'f')
        out.reshape(-1)[valid] = y_final
        return out, cn

# ---------------------------------------------------------
# 4. DOWNSCALE LOOP (pre-allocated, with progress)
# ---------------------------------------------------------
LOG_INTERVAL = 2000

def run_downscale_loop(model, input_data, dates_arr, var_name, period_label, noise_override=None):
    """noise_override=0 for deterministic (best RMSE); None for stochastic."""
    if noise_override is not None:
        model._noise_override = noise_override
    n = input_data.shape[0]
    out = np.empty((n, H, W), dtype='float32')
    prev_noise = None
    for d in range(n):
        dt = dates_arr[d]
        period_idx = get_period_idx(dt.month, dt.day)
        out[d], prev_noise = model.downscale_day(input_data[d], dt, period_idx, prev_noise)
        if d % LOG_INTERVAL == 0:
            log(f"  [{var_name}] {period_label}: day {d:>6d}/{n}")
    if hasattr(model, "_noise_override"):
        del model._noise_override
    log(f"  [{var_name}] {period_label}: done ({n} days)")
    return out

# ---------------------------------------------------------
# 5. WORKER: returns only main stack; saves early/future to disk
# ---------------------------------------------------------
def process_variable(var_name):
    seed_str = os.environ.get("TEST8_SEED", "").strip()
    if seed_str:
        _set_deterministic_seeds(_derive_worker_seed(int(seed_str), var_name))
    # Device must be initialized inside the worker to avoid CUDA deadlocks in sub-processes
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    v_idx = VARS_INTERNAL.index(var_name)
    
    # GridMET Verified Synoptic Correlation Lengths (in Pixels)
    if var_name in ["tasmax", "rsds"]:
        corr_len = 100.0 # Synoptic scale air-masses / cloud systems
    elif var_name in ["wind"]:
        corr_len = 50.0  # Large-scale wind fields
    elif var_name in ["tasmin", "huss", "pr"]:
        corr_len = 35.0  # Mesoscale moisture/storm/temp structures
    else:
        corr_len = 35.0
        
    inputs  = np.memmap(F_INPUTS,  dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    targets = np.memmap(F_TARGETS, dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    elev_2d = ELEV_2D

    if var_name in ["pr", "wind"]:
        model = StochasticSpatialDisaggregatorMultiplicative(v_idx, var_name, elev_2d=elev_2d, correlation_length=corr_len, device=device)
    else:
        model = StochasticSpatialDisaggregatorAdditive(v_idx, var_name, elev_2d=elev_2d, correlation_length=corr_len, device=device)
        
    model.calibrate(inputs, targets, DATES_ALL)

    stack_main_det = None
    if DETERMINISTIC:
        log(f"  [{var_name}] Running deterministic (noise=0)...")
        stack_main_det = run_downscale_loop(model, inputs, DATES_ALL, var_name, "1981-2014 (det)", noise_override=0)

    stack_main_stoch = None
    if STOCHASTIC:
        log(f"  [{var_name}] Running stochastic...")
        stack_main_stoch = run_downscale_loop(model, inputs, DATES_ALL, var_name, "1981-2014 (stoch)")

    # --- Early historical: process -> save -> free ---
    if (not MAIN_PERIOD_ONLY) and os.path.exists(F_INPUTS_EARLY):
        log(f"  [{var_name}] Starting early-historical 1850-1980...")
        inp_e = np.memmap(F_INPUTS_EARLY, dtype='float32', mode='r', shape=(N_DAYS_EARLY, 6, H, W))
        stack_e = run_downscale_loop(model, inp_e, DATES_EARLY, var_name, "1850-1980")
        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var_name}_1850_1980.npz"),
                            data=stack_e, dates=DATES_EARLY.values)
        log(f"  [{var_name}] Saved early-historical. Freeing memory...")
        del stack_e, inp_e; gc.collect()

    # --- Future: process -> save -> free ---
    if (not MAIN_PERIOD_ONLY) and os.path.exists(F_INPUTS_FUTURE):
        log(f"  [{var_name}] Starting future SSP585 2015-2100...")
        inp_f = np.memmap(F_INPUTS_FUTURE, dtype='float32', mode='r', shape=(N_DAYS_FUTURE, 6, H, W))
        stack_f = run_downscale_loop(model, inp_f, DATES_FUTURE, var_name, "2015-2100")
        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var_name}_SSP585_2015_2100.npz"),
                            data=stack_f, dates=DATES_FUTURE.values)
        log(f"  [{var_name}] Saved future. Freeing memory...")
        del stack_f, inp_f; gc.collect()

    # Explicitly clear large arrays and collect garbage
    del inputs, targets, model
    gc.collect()
    return var_name, stack_main_det, stack_main_stoch

# ---------------------------------------------------------
# 6. SCHAAKE SHUFFLE
# ---------------------------------------------------------
def apply_schaake_shuffle_single_var(output_data, target_stack, v_idx, output_dates):
    log(f"  Schaake var {VARS_INTERNAL[v_idx]}")
    mask_2d = np.load(F_MASK) == 1
    
    sim_slice = output_data[:, mask_2d]
    ref_slice = target_stack[TRAIN_MASK, v_idx][:, mask_2d]
    ref_dates = DATES_ALL[TRAIN_MASK]
    unique_ref_years = np.unique(ref_dates.year)
    
    for year in np.unique(output_dates.year):
        hist_y = unique_ref_years[year % len(unique_ref_years)]
        for month in range(1, 13):
            out_idx = np.where((output_dates.year == year) & (output_dates.month == month))[0]
            if len(out_idx) == 0: continue
            
            r_idx_year = np.where((ref_dates.year == hist_y) & (ref_dates.month == month))[0]
            
            N = len(out_idx)
            if len(r_idx_year) == 0:
                continue
            if len(r_idx_year) >= N:
                r_idx_used = r_idx_year[:N]
            else:
                r_idx_used = np.pad(r_idx_year, (0, N - len(r_idx_year)), mode='edge')
                
            sim_m = sim_slice[out_idx, :]
            ref_m = ref_slice[r_idx_used, :]
            
            sim_sorted = np.sort(sim_m, axis=0)
            ref_ranks = np.argsort(np.argsort(ref_m, axis=0), axis=0)
            
            sim_slice[out_idx, :] = np.take_along_axis(sim_sorted, ref_ranks, axis=0)
            
    output_data[:, mask_2d] = sim_slice
    del sim_slice, ref_slice
    return output_data

def apply_schaake_shuffle_stack(output_stack, target_stack, output_dates):
    log("Applying Schaake Shuffle...")
    n_days, v_count, h, w = output_stack.shape
    for v in range(v_count):
        output_stack[:, v] = apply_schaake_shuffle_single_var(output_stack[:, v], target_stack, v, output_dates)
    log("Schaake Shuffle done.")
    return output_stack

# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    from dor_test8_lock import acquire_run_lock

    acquire_run_lock(os.path.join(OUT_DIR, ".test8_v2_pr_intensity.lock"), "test8_v2_pr_intensity")

    _T0 = time.time()
    seed_str = os.environ.get("TEST8_SEED", "").strip()
    if seed_str:
        _set_deterministic_seeds(int(seed_str))

    _device_str = "cuda" if torch.cuda.is_available() else "cpu"
    log("=" * 65)
    log("test8_v2_pr_intensity (local fork + optional PR intensity ratio)")
    log(f"  EXPERIMENT_ROOT: {_EXPERIMENT_ROOT}")
    log(f"  BASE_DIR: {BASE_DIR}")
    log(f"  OUT_DIR: {OUT_DIR}")
    log(
        f"  PR_USE_INTENSITY_RATIO={PR_USE_INTENSITY_RATIO}  |  PR_INTENSITY_BLEND={PR_INTENSITY_BLEND}"
        + (f"  |  OUT_TAG={PR_INTENSITY_OUT_TAG}" if PR_INTENSITY_OUT_TAG else "")
        + f"  |  TEST8_MAIN_PERIOD_ONLY={MAIN_PERIOD_ONLY}"
    )
    log(f"  TEST8_SEED={seed_str or '(unset)'}")
    log("V8: STOCHASTIC SPATIAL DISAGGREGATION (OTBC PRESERVING)")
    log(f"  Device: {_device_str}  |  Workers: {MAX_WORKERS}  |  Grid: {H}x{W}")
    log(f"  Geo (DEM/coastal): {USE_GEO_STATIC}  |  Semi-monthly: {USE_SEMIMONTHLY}")
    log(f"  Noise: cont={NOISE_FACTOR_CONTINUOUS} mult={NOISE_FACTOR_MULTIPLICATIVE}  |  PR WDF factor: {PR_WDF_THRESHOLD_FACTOR}")
    log(f"  Stochastic: {STOCHASTIC}  |  Deterministic: {DETERMINISTIC}")
    log("=" * 65)

    # ---- Phase 1: downscale all variables (2 at a time) ----
    results_main = {}
    results_main_det = {}
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(process_variable, v): v for v in VARS_INTERNAL}
        for f in concurrent.futures.as_completed(futs):
            vn, sm_det, sm_stoch = f.result()
            results_main[vn] = sm_stoch
            if sm_det is not None:
                results_main_det[vn] = sm_det
            sz = (sm_stoch.nbytes/1e6 if sm_stoch is not None else 0) + (sm_det.nbytes/1e6 if sm_det is not None else 0)
            log(f"[MAIN] {vn.upper()} received ({sz:.0f} MB total)")

    # Build combined stack for Schaake shuffle and metrics (~2.3 GB)
    log("Building combined stack for Schaake...")
    full_sim = np.stack([results_main[v] for v in VARS_INTERNAL], axis=1) if len(results_main) > 0 else None
    full_sim_det = np.stack([results_main_det[v] for v in VARS_INTERNAL], axis=1) if len(results_main_det) > 0 else None
    del results_main, results_main_det; gc.collect()

    targets = np.memmap(F_TARGETS, dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    if full_sim is not None:
        full_sim = apply_schaake_shuffle_stack(full_sim, targets, DATES_ALL)
    if full_sim_det is not None:
        full_sim_det = apply_schaake_shuffle_stack(full_sim_det, targets, DATES_ALL)

    mask_2d  = np.load(F_MASK) == 1
    mask_flat = mask_2d.flatten()

    # ---- TABLE 1 & 2: Stochastic (realistic variability) ----
    if STOCHASTIC and full_sim is not None:
        log("\n" + "=" * 65)
        log("TABLE 1 — DOMAIN-POOLED METRICS — STOCHASTIC (2006-2014)")
        log("=" * 65)
        t1 = []
        for i, var in enumerate(VARS_INTERNAL):
            t1.append(calculate_pooled_metrics(targets[TEST_MASK, i], full_sim[TEST_MASK, i], var, label="Val"))
            log(f"  Table1 {var} done")
        df1 = pd.DataFrame(t1)
        print(df1.to_string(index=False), flush=True)
        _atomic_df_to_csv(df1, os.path.join(OUT_DIR, "V8_Table1_Pooled_Metrics_Stochastic.csv"))

        log("\n" + "=" * 65)
        log("TABLE 2 — PER-GRID-CELL SUMMARIZED METRICS — STOCHASTIC (2006-2014)")
        log("=" * 65)
        t2 = []
        for i, var in enumerate(VARS_INTERNAL):
            t2.append(calculate_per_cell_summary_metrics(targets[TEST_MASK, i], full_sim[TEST_MASK, i], var, mask_2d))
            log(f"  Table2 {var} done")
        df2 = pd.DataFrame(t2)
        print(df2.to_string(index=False), flush=True)
        _atomic_df_to_csv(df2, os.path.join(OUT_DIR, "V8_Table2_PerCell_Summary_Metrics_Stochastic.csv"))

    # ---- TABLE 1 & 2: Deterministic (best RMSE/KGE, noise=0) ----
    if DETERMINISTIC and full_sim_det is not None:
        log("\n" + "=" * 65)
        log("TABLE 1 — DOMAIN-POOLED METRICS — DETERMINISTIC (2006-2014)")
        log("=" * 65)
        t1d = []
        for i, var in enumerate(VARS_INTERNAL):
            t1d.append(calculate_pooled_metrics(targets[TEST_MASK, i], full_sim_det[TEST_MASK, i], var, label="Val"))
        df1d = pd.DataFrame(t1d)
        print(df1d.to_string(index=False), flush=True)
        _atomic_df_to_csv(df1d, os.path.join(OUT_DIR, "V8_Table1_Pooled_Metrics_Deterministic.csv"))
        log("\n" + "=" * 65)
        log("TABLE 2 — PER-GRID-CELL SUMMARIZED METRICS — DETERMINISTIC (2006-2014)")
        log("=" * 65)
        t2d = []
        for i, var in enumerate(VARS_INTERNAL):
            t2d.append(calculate_per_cell_summary_metrics(targets[TEST_MASK, i], full_sim_det[TEST_MASK, i], var, mask_2d))
        df2d = pd.DataFrame(t2d)
        print(df2d.to_string(index=False), flush=True)
        _atomic_df_to_csv(df2d, os.path.join(OUT_DIR, "V8_Table2_PerCell_Summary_Metrics_Deterministic.csv"))

    # Multivariate Frobenius norm (subsample test days; build masked rows day-by-day to avoid OOM)
    if STOCHASTIC and full_sim is not None:
        test_day_idx = np.where(TEST_MASK)[0]
        max_frob_days = int(os.environ.get("TEST8_FROBENIUS_MAX_DAYS", "400"))
        if len(test_day_idx) > max_frob_days:
            seed_f = os.environ.get("TEST8_SEED", "").strip()
            rng = np.random.default_rng(int(seed_f) if seed_f else 42)
            test_day_idx = np.sort(rng.choice(test_day_idx, size=max_frob_days, replace=False))
        obs_rows, sim_rows = [], []
        for d in test_day_idx:
            o = targets[d].transpose(1, 2, 0).reshape(-1, 6)[mask_flat]
            s = full_sim[d].transpose(1, 2, 0).reshape(-1, 6)[mask_flat]
            obs_rows.append(o)
            sim_rows.append(s)
        obs_f = np.vstack(obs_rows)
        sim_f = np.vstack(sim_rows)
        f_err = np.linalg.norm(
            np.nan_to_num(np.corrcoef(obs_f.T)) - np.nan_to_num(np.corrcoef(sim_f.T)), ord="fro"
        )
        log(
            f"Multivariate Frobenius Norm Error: {f_err:.4f} "
            f"(n_test_days_used={len(test_day_idx)}/{int(np.sum(TEST_MASK))})"
        )
        del obs_f, sim_f, obs_rows, sim_rows
        gc.collect()

    # Save main period
    if STOCHASTIC and full_sim is not None:
        log("Saving main-period outputs (Stochastic)...")
        for i, var in enumerate(VARS_INTERNAL):
            np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}.npz"),
                                data=full_sim[:, i], dates=DATES_ALL.values)
            log(f"  Saved {var}")
    if DETERMINISTIC and full_sim_det is not None:
        log("Saving main-period outputs (Deterministic)...")
        for i, var in enumerate(VARS_INTERNAL):
            np.savez_compressed(os.path.join(OUT_DIR, f"Deterministic_V8_Hybrid_{var}.npz"),
                                data=full_sim_det[:, i], dates=DATES_ALL.values)
            log(f"  Saved {var}")
    
    del full_sim, full_sim_det
    gc.collect()

    if not MAIN_PERIOD_ONLY:
        # ---- Climatology for early historical (load from saved npz one at a time) ----
        log("\n" + "=" * 65)
        log("EARLY HISTORICAL CLIMATOLOGY (loaded from disk one-by-one)")
        log("=" * 65)
        early_clim = []
        for var in VARS_INTERNAL:
            fpath = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_1850_1980.npz")
            if not os.path.exists(fpath):
                log(f"  [{var}] no early file — skipped")
                continue
            d = np.load(fpath)
            row = calculate_climatology_summary(d["data"], var, "1850-1980", mask_2d)
            early_clim.append(row)
            del d
            gc.collect()
            log(f"  [{var}] done")
        if early_clim:
            df_ec = pd.DataFrame(early_clim)
            print(df_ec.to_string(index=False), flush=True)
            _atomic_df_to_csv(df_ec, os.path.join(OUT_DIR, "V8_Early_Historical_Climatology.csv"))

        # ---- Climatology for future (load from saved npz one at a time) ----
        log("\n" + "=" * 65)
        log("FUTURE CLIMATOLOGY (loaded from disk one-by-one)")
        log("=" * 65)
        future_clim = []
        SUB_PERIODS = [
            ("2015-01-01", "2040-12-31", "2015-2040"),
            ("2041-01-01", "2070-12-31", "2041-2070"),
            ("2071-01-01", "2100-12-31", "2071-2100"),
        ]
        for var in VARS_INTERNAL:
            fpath = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_SSP585_2015_2100.npz")
            if not os.path.exists(fpath):
                log(f"  [{var}] no future file — skipped")
                continue
            d = np.load(fpath)
            data, dates = d["data"], pd.DatetimeIndex(d["dates"])
            future_clim.append(calculate_climatology_summary(data, var, "2015-2100", mask_2d))
            for s, e, name in SUB_PERIODS:
                m = (dates >= s) & (dates <= e)
                if np.any(m):
                    future_clim.append(calculate_climatology_summary(data[m], var, name, mask_2d))
            del d, data, dates
            gc.collect()
            log(f"  [{var}] done")
        if future_clim:
            df_fc = pd.DataFrame(future_clim)
            print(df_fc.to_string(index=False), flush=True)
            _atomic_df_to_csv(df_fc, os.path.join(OUT_DIR, "V8_Future_Climatology.csv"))

        # ---- Phase 7: MULTIVARIATE SCHAAKE SHUFFLE (FUTURE SSP585) ----
        log("\n" + "=" * 65)
        log("PHASE 7: MULTIVARIATE SCHAAKE SHUFFLE (FUTURE SSP585)")
        log("=" * 65)
        for i, var in enumerate(VARS_INTERNAL):
            fpath = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_SSP585_2015_2100.npz")
            if os.path.exists(fpath):
                log(f"Loading {var} for Schaake Shuffle...")
                d = np.load(fpath)
                single_stack = d["data"].copy()
                del d
                gc.collect()

                single_stack_shuffled = apply_schaake_shuffle_single_var(
                    single_stack, targets, i, DATES_FUTURE
                )

                out_path = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_SSP585_2015_2100_SHUFFLED.npz")
                np.savez_compressed(out_path, data=single_stack_shuffled, dates=DATES_FUTURE.values)
                log(f"Saved {var} (Shuffled)")
                del single_stack, single_stack_shuffled
                gc.collect()

        # ---- Phase 8: MULTIVARIATE SCHAAKE SHUFFLE (EARLY HISTORICAL) ----
        log("\n" + "=" * 65)
        log("PHASE 8: MULTIVARIATE SCHAAKE SHUFFLE (EARLY HISTORICAL 1850-1980)")
        log("=" * 65)
        for i, var in enumerate(VARS_INTERNAL):
            fpath = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_1850_1980.npz")
            if os.path.exists(fpath):
                log(f"Loading {var} for Schaake Shuffle...")
                d = np.load(fpath)
                single_stack = d["data"].copy()
                del d
                gc.collect()

                single_stack_shuffled = apply_schaake_shuffle_single_var(
                    single_stack, targets, i, DATES_EARLY
                )

                out_path = os.path.join(OUT_DIR, f"Stochastic_V8_Hybrid_{var}_1850_1980_SHUFFLED.npz")
                np.savez_compressed(out_path, data=single_stack_shuffled, dates=DATES_EARLY.values)
                log(f"Saved {var} (Shuffled)")
                del single_stack, single_stack_shuffled
                gc.collect()
    else:
        log("Skipping early/future NPZ climatology and Phases 7–8 (TEST8_MAIN_PERIOD_ONLY=1).")

    elapsed_min = (time.time() - _T0) / 60.0
    write_run_manifest({"elapsed_minutes": elapsed_min})
    log(f"\nV8 pipeline complete. Total time: {elapsed_min:.2f} mins.")
