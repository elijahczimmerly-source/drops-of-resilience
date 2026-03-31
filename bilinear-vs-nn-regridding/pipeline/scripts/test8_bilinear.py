"""
test8_bilinear.py  —  Stochastic Spatial Disaggregation (Post-OTBC)
Regrid path: pr via conservative (mass-preserving); other vars bilinear — same as server regrid_to_gridmet.py.
Output goes to: C:/drops-of-resilience/week3/pipeline/output/bilinear/
  (Run regrid_to_gridmet_bilinear.py first to populate week3/pipeline/data/bilinear/.)

Env: TEST8_SEED (default 42), TEST8_MAX_WORKERS (default 4). Use the same TEST8_SEED as test8_nn.py
  to pair identical stochastic draws across regrid methods (inputs still differ).
Run lock: output/bilinear/.test8_bilinear.lock (removed on clean exit or Ctrl+C). Delete manually if a run
  was killed and the next start falsely thinks another job is alive.
"""

import os

# Intel OpenMP + PyTorch on Windows: avoid abort on duplicate libiomp5 (see Intel OMP note).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import gc
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

warnings.filterwarnings("ignore")

RUN_SEED = int(os.environ.get("TEST8_SEED", "42"))


def _derive_worker_seed(base_seed: int, var_name: str) -> int:
    d = hashlib.sha256(f"{base_seed}:{var_name}".encode()).digest()
    return int.from_bytes(d[:4], "little") & 0x7FFFFFFF


def _set_deterministic_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
VARS_INTERNAL = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
MAX_WORKERS = int(os.environ.get("TEST8_MAX_WORKERS", "4"))

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TRAIN_MASK = (DATES_ALL <= "2005-12-31")
TEST_MASK  = (DATES_ALL >  "2005-12-31")
N_DAYS = len(DATES_ALL)

DATES_EARLY = pd.date_range("1850-01-01", "1980-12-31")
N_DAYS_EARLY = len(DATES_EARLY)
DATES_FUTURE = pd.date_range("2015-01-01", "2100-12-31")
N_DAYS_FUTURE = len(DATES_FUTURE)

BASE_DIR       = r"C:\drops-of-resilience\bilinear-vs-nn-regridding\pipeline\data\bilinear"
F_INPUTS       = os.path.join(BASE_DIR, "cmip6_inputs_19810101-20141231.dat")
F_TARGETS      = os.path.join(BASE_DIR, "gridmet_targets_19810101-20141231.dat")
F_MASK         = os.path.join(BASE_DIR, "geo_mask.npy")
F_GEO_STATIC   = os.path.join(BASE_DIR, "geo_static.npy")
F_INPUTS_EARLY = os.path.join(BASE_DIR, "cmip6_inputs_18500101-19801231.dat")
F_INPUTS_FUTURE= os.path.join(BASE_DIR, "cmip6_inputs_ssp585_20150101-21001231.dat")

USE_GEO_STATIC = False
LAPSE_RATE_PER_KM = -6.5
USE_SEMIMONTHLY = True
STOCHASTIC    = True
DETERMINISTIC = False

NOISE_FACTOR_CONTINUOUS = 0.06
NOISE_FACTOR_MULTIPLICATIVE = 0.15
PR_WDF_THRESHOLD_FACTOR = 1.2

try:
    _temp_mask = np.load(F_MASK); H, W = _temp_mask.shape; del _temp_mask
except FileNotFoundError:
    H, W = 84, 96

OUT_DIR = r"C:\drops-of-resilience\bilinear-vs-nn-regridding\pipeline\output\bilinear"
os.makedirs(OUT_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ELEV_2D = None
COASTAL_2D = None
if USE_GEO_STATIC and os.path.exists(F_GEO_STATIC):
    _gs = np.load(F_GEO_STATIC)
    if _gs.shape[0] >= 2:
        ELEV_2D = np.asarray(_gs[0], dtype='float32').reshape(H, W)
        COASTAL_2D = np.asarray(_gs[1], dtype='float32').reshape(H, W)
    del _gs

_T0 = time.time()

def _ram_gb():
    try:
        import psutil  # optional; pip/conda package "psutil"

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
    if USE_SEMIMONTHLY:
        return (month - 1) * 2 + (0 if day <= 15 else 1)
    return month - 1

# ---------------------------------------------------------
# 2. METRIC ENGINES
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


# ---------------------------------------------------------
# 3. NOISE + DOWNSCALERS
# ---------------------------------------------------------
def generate_spatial_noise(shape, correlation_length=4.0):
    h, w = shape
    noise = torch.randn(h, w, device=device)
    kh = torch.fft.fftfreq(h, device=device).reshape(-1, 1)
    kw = torch.fft.fftfreq(w, device=device).reshape(1, -1)
    kernel = torch.exp(-0.5 * (torch.sqrt(kh**2 + kw**2) * correlation_length)**2)
    filtered = torch.fft.ifftn(torch.fft.fftn(noise) * kernel).real
    return (filtered - filtered.mean()) / (filtered.std() + 1e-8)


class StochasticSpatialDisaggregatorAdditive:
    def __init__(self, var_idx, var_name, rho=0.8, noise_factor=None, elev_2d=None):
        self.var_idx, self.var_name, self.rho = var_idx, var_name, rho
        self.noise_factor = noise_factor if noise_factor is not None else NOISE_FACTOR_CONTINUOUS
        self.elev_2d = elev_2d
        self.mask = np.load(F_MASK).flatten() == 1
        self.spatial_delta = np.zeros((N_PERIODS, H, W), dtype='float32')
        self.resid_std = np.zeros((N_PERIODS, H, W), dtype='float32')
        self._elev_ref = None

    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating ({N_PERIODS} periods)...")
        for p in range(N_PERIODS):
            if USE_SEMIMONTHLY:
                idx = [i for i in np.where(TRAIN_MASK)[0] if get_period_idx(dates[i].month, dates[i].day) == p]
            else:
                idx = [i for i in np.where(TRAIN_MASK)[0] if dates[i].month == p + 1]
            if len(idx) < 2:
                continue
            in_m  = inputs[idx, self.var_idx].copy()
            tar_m = targets[idx, self.var_idx].copy()
            if self.var_name in ["tasmax", "tasmin"] and np.nanmean(in_m) < 150:
                in_m = in_m + 273.15
            m_gcm = np.nanmean(in_m, axis=0)
            m_obs = np.nanmean(tar_m, axis=0)
            self.spatial_delta[p] = m_obs - m_gcm
            sim_base = in_m + self.spatial_delta[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_std[p] = np.nanstd(resid, axis=0) + 1e-6
        if self.elev_2d is not None and self.var_name in ["tasmax", "tasmin"]:
            mask_2d = np.load(F_MASK) == 1
            self._elev_ref = float(np.nanmean(self.elev_2d[mask_2d]))

    def downscale_day(self, in_data, period_idx, prev_noise):
        valid = self.mask & np.isfinite(in_data.flatten())
        if not np.any(valid):
            return np.full((H, W), np.nan, 'f'), None
        in_val = in_data.flatten()[valid].copy()
        if self.var_name in ["tasmax", "tasmin"] and np.nanmean(in_val) < 150:
            in_val += 273.15
        delta = self.spatial_delta[period_idx].flatten()[valid]
        y_base = in_val + delta
        with torch.no_grad():
            ns = generate_spatial_noise((H, W), 5.0)
            cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
        nf = 0.0 if (getattr(self, "_noise_override", None) is not None) else self.noise_factor
        std_resid = self.resid_std[period_idx].flatten()[valid]
        noise_scaled = cn.cpu().numpy().flatten()[valid] * std_resid * nf
        y_final = y_base + noise_scaled
        if self.var_name in ["rsds", "huss"]:
            y_final = np.maximum(y_final, 0.0)
        out = np.full((H, W), np.nan, 'f')
        out.reshape(-1)[valid] = y_final
        if self.elev_2d is not None and self._elev_ref is not None and self.var_name in ["tasmax", "tasmin"]:
            out += LAPSE_RATE_PER_KM * (self.elev_2d - self._elev_ref) / 1000.0
        return out, cn


class StochasticSpatialDisaggregatorMultiplicative:
    def __init__(self, var_idx, var_name, rho=0.5, noise_factor=None, elev_2d=None):
        self.var_idx, self.var_name, self.rho = var_idx, var_name, rho
        self.noise_factor = noise_factor if noise_factor is not None else NOISE_FACTOR_MULTIPLICATIVE
        self.mask = np.load(F_MASK).flatten() == 1
        self.spatial_ratio = np.ones((N_PERIODS, H, W), dtype='float32')
        self.resid_cv = np.zeros((N_PERIODS, H, W), dtype='float32')
        self.monthly_threshold = np.zeros((N_PERIODS, H, W), dtype='float32')

    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating ({N_PERIODS} periods)...")
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
            self.spatial_ratio[p] = np.clip(m_obs / (m_gcm + 1e-4), 0.05, 20.0)
            sim_base = in_m * self.spatial_ratio[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_cv[p] = np.nanstd(resid, axis=0) / (np.nanmean(sim_base, axis=0) + 1e-4)
            if self.var_name == "pr":
                sim_m_sorted = np.sort(sim_base, axis=0)
                wdf = np.mean(tar_m >= 0.1, axis=0)
                ti = np.clip(np.round((1 - wdf) * (len(idx) - 1)).astype(int), 0, len(idx) - 1)
                Hi, Wi = np.indices((H, W))
                self.monthly_threshold[p] = sim_m_sorted[ti, Hi, Wi]

    def downscale_day(self, in_data, period_idx, prev_noise):
        valid = self.mask & np.isfinite(in_data.flatten())
        if not np.any(valid):
            return np.full((H, W), np.nan, 'f'), None
        iv = in_data.flatten()[valid].copy()
        ratio = self.spatial_ratio[period_idx].flatten()[valid]
        y_base = iv * ratio
        with torch.no_grad():
            ns = generate_spatial_noise((H, W), 5.0)
            cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
        nf = 0.0 if (getattr(self, "_noise_override", None) is not None) else self.noise_factor
        cv_resid = self.resid_cv[period_idx].flatten()[valid]
        noise_mult = 1.0 + cn.cpu().numpy().flatten()[valid] * cv_resid * nf
        noise_mult = np.clip(noise_mult, 0.1, 5.0)
        y_final = y_base * noise_mult
        if self.var_name == "pr":
            th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
            y_final = np.where(y_final <= th, 0, y_final)
            y_final = np.where(y_final < 0.1, 0, y_final)
        out = np.full((H, W), np.nan, 'f')
        out.reshape(-1)[valid] = y_final
        return out, cn


# ---------------------------------------------------------
# 4. DOWNSCALE LOOP
# ---------------------------------------------------------
LOG_INTERVAL = 2000

def run_downscale_loop(model, input_data, dates_arr, var_name, period_label, noise_override=None):
    if noise_override is not None:
        model._noise_override = noise_override
    n = input_data.shape[0]
    out = np.empty((n, H, W), dtype='float32')
    prev_noise = None
    for d in range(n):
        dt = dates_arr[d]
        period_idx = get_period_idx(dt.month, dt.day)
        out[d], prev_noise = model.downscale_day(input_data[d], period_idx, prev_noise)
        if d % LOG_INTERVAL == 0:
            log(f"  [{var_name}] {period_label}: day {d:>6d}/{n}")
    if hasattr(model, "_noise_override"):
        del model._noise_override
    log(f"  [{var_name}] {period_label}: done ({n} days)")
    return out


def process_variable(var_name):
    _set_deterministic_seeds(_derive_worker_seed(RUN_SEED, var_name))
    v_idx = VARS_INTERNAL.index(var_name)
    inputs  = np.memmap(F_INPUTS,  dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    targets = np.memmap(F_TARGETS, dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    elev_2d = ELEV_2D

    if var_name in ["pr", "wind"]:
        model = StochasticSpatialDisaggregatorMultiplicative(v_idx, var_name, elev_2d=elev_2d)
    else:
        model = StochasticSpatialDisaggregatorAdditive(v_idx, var_name, elev_2d=elev_2d)

    model.calibrate(inputs, targets, DATES_ALL)

    stack_main_stoch = None
    if STOCHASTIC:
        stack_main_stoch = run_downscale_loop(model, inputs[:, v_idx], DATES_ALL, var_name, "1981-2014 (stoch)")

    if os.path.exists(F_INPUTS_EARLY):
        inp_e = np.memmap(F_INPUTS_EARLY, dtype='float32', mode='r', shape=(N_DAYS_EARLY, 6, H, W))
        stack_e = run_downscale_loop(model, inp_e[:, v_idx], DATES_EARLY, var_name, "1850-1980")
        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_Bilinear_{var_name}_1850_1980.npz"),
                            data=stack_e, dates=DATES_EARLY.values)
        del stack_e, inp_e; gc.collect()

    if os.path.exists(F_INPUTS_FUTURE):
        inp_f = np.memmap(F_INPUTS_FUTURE, dtype='float32', mode='r', shape=(N_DAYS_FUTURE, 6, H, W))
        stack_f = run_downscale_loop(model, inp_f[:, v_idx], DATES_FUTURE, var_name, "2015-2100")
        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_Bilinear_{var_name}_SSP585_2015_2100.npz"),
                            data=stack_f, dates=DATES_FUTURE.values)
        del stack_f, inp_f; gc.collect()

    return var_name, stack_main_stoch


# ---------------------------------------------------------
# 5. SCHAAKE SHUFFLE
# ---------------------------------------------------------
def apply_schaake_shuffle_stack(output_stack, target_stack):
    log("Applying Schaake Shuffle...")
    n_days, v_count, h, w = output_stack.shape
    mask_2d = np.load(F_MASK) == 1
    for v in range(v_count):
        log(f"  Schaake var {v+1}/{v_count} ({VARS_INTERNAL[v]})")
        sim_slice = output_stack[:, v][:, mask_2d]
        ref_slice = target_stack[TRAIN_MASK, v][:, mask_2d]
        n_train = ref_slice.shape[0]
        sim_sorted = np.sort(sim_slice, axis=0)
        ref_ranks = np.argsort(np.argsort(ref_slice, axis=0), axis=0)
        ref_q = ref_ranks / (n_train - 1 + 1e-6)
        idx_map = np.arange(n_days) % n_train
        target_q = ref_q[idx_map, :]
        final_idx = np.round(target_q * (n_days - 1)).astype(int)
        output_stack[:, v, mask_2d] = sim_sorted[final_idx, np.arange(sim_slice.shape[1])]
        del sim_slice, ref_slice, sim_sorted, ref_ranks, ref_q, target_q, final_idx
    log("Schaake Shuffle done.")
    return output_stack


# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    from dor_test8_lock import acquire_run_lock

    acquire_run_lock(os.path.join(OUT_DIR, ".test8_bilinear.lock"), "bilinear test8")
    _set_deterministic_seeds(RUN_SEED)
    _T0 = time.time()
    log("=" * 65)
    log("BILINEAR PATH: Stochastic Spatial Disaggregation")
    log(
        f"  Device: {device}  |  Workers: {MAX_WORKERS}  |  Grid: {H}x{W}  |  TEST8_SEED={RUN_SEED}"
    )
    log(f"  Input dir:  {BASE_DIR}")
    log(f"  Output dir: {OUT_DIR}")
    log("=" * 65)

    results_main = {}
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(process_variable, v): v for v in VARS_INTERNAL}
        for f in concurrent.futures.as_completed(futs):
            vn, sm_stoch = f.result()
            results_main[vn] = sm_stoch
            log(f"[MAIN] {vn.upper()} received")

    log("Building combined stack for Schaake...")
    full_sim = np.stack([results_main[v] for v in VARS_INTERNAL], axis=1)
    del results_main; gc.collect()

    targets = np.memmap(F_TARGETS, dtype='float32', mode='r', shape=(N_DAYS, 6, H, W))
    full_sim = apply_schaake_shuffle_stack(full_sim, targets)

    mask_2d  = np.load(F_MASK) == 1
    mask_flat = mask_2d.flatten()

    log("\n" + "=" * 65)
    log("TABLE 1 — DOMAIN-POOLED METRICS (2006-2014)")
    log("=" * 65)
    t1 = []
    for i, var in enumerate(VARS_INTERNAL):
        t1.append(calculate_pooled_metrics(targets[TEST_MASK, i], full_sim[TEST_MASK, i], var, label="Val"))
        log(f"  {var} done")
    df1 = pd.DataFrame(t1)
    print(df1.to_string(index=False), flush=True)
    df1.to_csv(os.path.join(OUT_DIR, "Bilinear_Table1_Pooled_Metrics.csv"), index=False)

    log("\n" + "=" * 65)
    log("TABLE 2 — PER-CELL METRICS (2006-2014)")
    log("=" * 65)
    t2 = []
    for i, var in enumerate(VARS_INTERNAL):
        t2.append(calculate_per_cell_summary_metrics(targets[TEST_MASK, i], full_sim[TEST_MASK, i], var, mask_2d))
        log(f"  {var} done")
    df2 = pd.DataFrame(t2)
    print(df2.to_string(index=False), flush=True)
    df2.to_csv(os.path.join(OUT_DIR, "Bilinear_Table2_PerCell_Metrics.csv"), index=False)

    # Save outputs
    log("Saving main-period outputs...")
    for i, var in enumerate(VARS_INTERNAL):
        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_Bilinear_{var}.npz"),
                            data=full_sim[:, i], dates=DATES_ALL.values)
        log(f"  Saved {var}")

    del full_sim; gc.collect()
    log(f"\nBilinear path complete. Total time: {(time.time() - _T0) / 60:.2f} mins.")
