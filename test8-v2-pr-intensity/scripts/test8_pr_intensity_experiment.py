"""
test8_pr_intensity_experiment.py — PR-only stochastic spatial disaggregation with test8_v2-style
parameters and optional test6-style intensity-dependent spatial ratios.

**Not v2-comparable:** For apples-to-apples vs Bhuwan's test8_v2 metrics (6 variables + v2 Schaake), use
`test8_v2_pr_intensity.py` (same folder) instead. This script omits Schaake and other variables by design.

Live in: C:\\drops-of-resilience\\test8-v2-pr-intensity\\scripts\\ (data via ..\\data junction).

Env:
  DOR_TEST8_V2_PR_INTENSITY_ROOT — optional experiment root override
  DOR_TEST8_PR_DATA_DIR — optional memmap directory override

Toggle via environment variable:
  PR_USE_INTENSITY_RATIO=0  →  flat ratio baseline (output: pr_intensity_baseline/)
  PR_USE_INTENSITY_RATIO=1  →  intensity-dependent ratio (output: pr_intensity_experiment/)

Other env: TEST8_SEED (default 42). Single-process (no worker pool) for PR only.
No Schaake shuffle (single variable; measures raw stochastic downscaler).
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import gc
import hashlib
import random
import time
import warnings

import numpy as np
import pandas as pd
import torch
import torch.fft

warnings.filterwarnings("ignore")

RUN_SEED = int(os.environ.get("TEST8_SEED", "42"))

# Controlled toggle: set True/False here, or override with PR_USE_INTENSITY_RATIO=1|0 in the environment.
USE_INTENSITY_RATIO = False
_pr_ir = os.environ.get("PR_USE_INTENSITY_RATIO")
if _pr_ir is not None and str(_pr_ir).strip() != "":
    USE_INTENSITY_RATIO = str(_pr_ir).strip().lower() in ("1", "true", "yes")

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_exp_root_env = os.environ.get("DOR_TEST8_V2_PR_INTENSITY_ROOT", "").strip()
_EXPERIMENT_ROOT = os.path.abspath(
    _exp_root_env if _exp_root_env else os.path.join(_scripts_dir, "..")
)
_data_env = os.environ.get("DOR_TEST8_PR_DATA_DIR", "").strip()
BASE_DIR = os.path.abspath(_data_env if _data_env else os.path.join(_EXPERIMENT_ROOT, "data"))
F_INPUTS = os.path.join(BASE_DIR, "cmip6_inputs_19810101-20141231.dat")
F_TARGETS = os.path.join(BASE_DIR, "gridmet_targets_19810101-20141231.dat")
F_MASK = os.path.join(BASE_DIR, "geo_mask.npy")

USE_SEMIMONTHLY = True
STOCHASTIC = True

# test8_v2 multiplicative / PR settings (vs original test8_bilinear)
NOISE_FACTOR_MULTIPLICATIVE = 0.16
PR_WDF_THRESHOLD_FACTOR = 1.15
PR_NOISE_CORRELATION_LENGTH = 35.0
NOISE_MULT_CLIP = (0.1, 8.5)
PR_CAP_MM_DAY = 250.0

try:
    _temp_mask = np.load(F_MASK)
    H, W = _temp_mask.shape
    del _temp_mask
except FileNotFoundError:
    H, W = 84, 96

_output_root = os.path.join(_EXPERIMENT_ROOT, "output")
OUT_DIR = os.path.join(
    _output_root,
    "pr_intensity_experiment" if USE_INTENSITY_RATIO else "pr_intensity_baseline",
)
os.makedirs(OUT_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TRAIN_MASK = DATES_ALL <= "2005-12-31"
TEST_MASK = DATES_ALL > "2005-12-31"
N_DAYS = len(DATES_ALL)

N_PERIODS = 24 if USE_SEMIMONTHLY else 12
VAR_NAME = "pr"
VAR_IDX = 0  # pr first in VARS_INTERNAL order

_T0 = time.time()


def _derive_worker_seed(base_seed: int, name: str) -> int:
    d = hashlib.sha256(f"{base_seed}:{name}".encode()).digest()
    return int.from_bytes(d[:4], "little") & 0x7FFFFFFF


def _set_deterministic_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_period_idx(month, day):
    if USE_SEMIMONTHLY:
        return (month - 1) * 2 + (0 if day <= 15 else 1)
    return month - 1


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


def calculate_pooled_metrics(obs_3d, sim_3d, var_name, label="Val"):
    obs, sim = obs_3d.flatten(), sim_3d.flatten()
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs_m, sim_m = obs[mask], sim[mask]
    if len(obs_m) == 0:
        return {}
    r = np.corrcoef(obs_m, sim_m)[0, 1] if np.std(obs_m) > 0 and np.std(sim_m) > 0 else 0
    alpha = np.std(sim_m) / (np.std(obs_m) + 1e-6)
    beta = np.mean(sim_m) / (np.mean(obs_m) + 1e-6)
    kge = 1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
    rmse_pooled = np.sqrt(np.mean((obs_m - sim_m) ** 2))
    bias = np.mean(sim_m) - np.mean(obs_m)
    o99, s99 = np.percentile(obs_m, 99), np.percentile(sim_m, 99)
    ext99_bias = ((s99 - o99) / (o99 + 1e-6) * 100) if o99 != 0 else 0

    def lag1(a):
        ts = np.nanmean(a, axis=(1, 2))
        return np.corrcoef(ts[:-1], ts[1:])[0, 1]

    obs_rho, sim_rho = lag1(obs_3d), lag1(sim_3d)
    out = {
        "Variable": var_name,
        f"{label}_KGE": kge,
        f"{label}_RMSE_pooled": rmse_pooled,
        f"{label}_Bias": bias,
        f"{label}_Ext99_Bias%": ext99_bias,
        f"{label}_Lag1_Obs": obs_rho,
        f"{label}_Lag1_Sim": sim_rho,
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

    sq_err = (obs_w - sim_w) ** 2
    n_valid = np.nansum(valid, axis=0).astype(float)
    n_valid[n_valid < 2] = np.nan
    rmse_pc = np.sqrt(np.nansum(sq_err, axis=0) / n_valid)
    del sq_err

    bias_pc = np.nanmean(sim_w - obs_w, axis=0)
    mean_o = np.nanmean(obs_w, axis=0)
    mean_s = np.nanmean(sim_w, axis=0)
    std_o = np.nanstd(obs_w, axis=0) + 1e-12
    std_s = np.nanstd(sim_w, axis=0) + 1e-12
    cov = np.nanmean((obs_w - mean_o[None]) * (sim_w - mean_s[None]), axis=0)
    r_pc = cov / (std_o * std_s)
    kge_pc = 1 - np.sqrt(
        (r_pc - 1) ** 2 + (std_s / std_o - 1) ** 2 + (mean_s / (mean_o + 1e-12) - 1) ** 2
    )
    del obs_w, sim_w

    ts_obs = np.nanmean(obs_3d, axis=(1, 2))
    ts_sim = np.nanmean(sim_3d, axis=(1, 2))
    rmse_dm = np.sqrt(np.nanmean((ts_obs - ts_sim) ** 2))

    fm = mask_2d.flatten()

    def _stat(arr):
        v = arr.flatten()[fm]
        v = v[np.isfinite(v)]
        return (np.mean(v), np.median(v), np.std(v)) if len(v) else (np.nan,) * 3

    rm, rmed, rstd = _stat(rmse_pc)
    km, kmed, _ = _stat(kge_pc)
    cm, cmed, _ = _stat(r_pc)
    bm, bmed, _ = _stat(bias_pc)

    return {
        "Variable": var_name,
        f"{label}_RMSE_per_cell_mean": rm,
        f"{label}_RMSE_per_cell_median": rmed,
        f"{label}_RMSE_per_cell_std": rstd,
        f"{label}_RMSE_domain_mean_ts": rmse_dm,
        f"{label}_KGE_per_cell_mean": km,
        f"{label}_KGE_per_cell_median": kmed,
        f"{label}_r_per_cell_mean": cm,
        f"{label}_r_per_cell_median": cmed,
        f"{label}_Bias_per_cell_mean": bm,
        f"{label}_Bias_per_cell_median": bmed,
        f"{label}_n_cells": int(np.sum(fm)),
    }


def generate_spatial_noise(shape, correlation_length=4.0):
    h, w = shape
    noise = torch.randn(h, w, device=device)
    kh = torch.fft.fftfreq(h, device=device).reshape(-1, 1)
    kw = torch.fft.fftfreq(w, device=device).reshape(1, -1)
    kernel = torch.exp(-0.5 * (torch.sqrt(kh**2 + kw**2) * correlation_length) ** 2)
    filtered = torch.fft.ifftn(torch.fft.fftn(noise) * kernel).real
    return (filtered - filtered.mean()) / (filtered.std() + 1e-8)


class StochasticSpatialDisaggregatorMultiplicative:
    def __init__(self, var_idx, var_name, rho=0.5, noise_factor=None, use_intensity_ratio=False):
        self.var_idx = var_idx
        self.var_name = var_name
        self.rho = rho
        self.noise_factor = noise_factor if noise_factor is not None else NOISE_FACTOR_MULTIPLICATIVE
        self.use_intensity_ratio = use_intensity_ratio
        self.mask = np.load(F_MASK).flatten() == 1
        self.spatial_ratio = np.ones((N_PERIODS, H, W), dtype="float32")
        self.resid_cv = np.zeros((N_PERIODS, H, W), dtype="float32")
        self.monthly_threshold = np.zeros((N_PERIODS, H, W), dtype="float32")
        if use_intensity_ratio and var_name == "pr":
            self.spatial_ratio_ext = np.ones((N_PERIODS, H, W), dtype="float32")
            self.gcm_95th = np.zeros((N_PERIODS, H, W), dtype="float32")
        else:
            self.spatial_ratio_ext = None
            self.gcm_95th = None

    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating ({N_PERIODS} periods)...")
        for p in range(N_PERIODS):
            if USE_SEMIMONTHLY:
                idx = [
                    i
                    for i in np.where(TRAIN_MASK)[0]
                    if get_period_idx(dates[i].month, dates[i].day) == p
                ]
            else:
                idx = [i for i in np.where(TRAIN_MASK)[0] if dates[i].month == p + 1]
            if len(idx) < 2:
                continue
            in_m, tar_m = inputs[idx, self.var_idx], targets[idx, self.var_idx]
            m_gcm = np.nanmean(in_m, axis=0)
            m_obs = np.nanmean(tar_m, axis=0)
            self.spatial_ratio[p] = np.clip(m_obs / (m_gcm + 1e-4), 0.05, 20.0)
            if self.use_intensity_ratio and self.var_name == "pr":
                p95_gcm = np.nanpercentile(in_m, 95, axis=0)
                p95_obs = np.nanpercentile(tar_m, 95, axis=0)
                self.spatial_ratio_ext[p] = np.clip(
                    p95_obs / (p95_gcm + 1e-4), 0.05, 20.0
                )
                self.gcm_95th[p] = np.maximum(p95_gcm.astype("float32"), 0.1)
            sim_base = in_m * self.spatial_ratio[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_cv[p] = np.nanstd(resid, axis=0) / (np.nanmean(sim_base, axis=0) + 1e-4)
            if self.var_name == "pr":
                sim_m_sorted = np.sort(sim_base, axis=0)
                wdf = np.mean(tar_m >= 0.1, axis=0)
                ti = np.clip(
                    np.round((1 - wdf) * (len(idx) - 1)).astype(int), 0, len(idx) - 1
                )
                Hi, Wi = np.indices((H, W))
                self.monthly_threshold[p] = sim_m_sorted[ti, Hi, Wi]

    def downscale_day(self, in_data, period_idx, prev_noise):
        valid = self.mask & np.isfinite(in_data.flatten())
        if not np.any(valid):
            return np.full((H, W), np.nan, "f"), None
        iv = in_data.flatten()[valid].copy()
        ratio = self.spatial_ratio[period_idx].flatten()[valid]
        if self.use_intensity_ratio and self.var_name == "pr":
            ratio_ext = self.spatial_ratio_ext[period_idx].flatten()[valid]
            gcm_95 = self.gcm_95th[period_idx].flatten()[valid]
            weight = np.clip(iv / (gcm_95 + 1e-4), 0.0, 1.0)
            ratio = ratio + (ratio_ext - ratio) * weight
        y_base = iv * ratio
        with torch.no_grad():
            ns = generate_spatial_noise((H, W), PR_NOISE_CORRELATION_LENGTH)
            cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
        nf = 0.0 if (getattr(self, "_noise_override", None) is not None) else self.noise_factor
        cv_resid = self.resid_cv[period_idx].flatten()[valid]
        noise_mult = 1.0 + cn.cpu().numpy().flatten()[valid] * cv_resid * nf
        noise_mult = np.clip(noise_mult, NOISE_MULT_CLIP[0], NOISE_MULT_CLIP[1])
        y_final = y_base * noise_mult
        if self.var_name == "pr":
            th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
            y_final = np.where(y_final <= th, 0, y_final)
            y_final = np.where(y_final < 0.1, 0, y_final)
            y_final = np.minimum(y_final, PR_CAP_MM_DAY)
        out = np.full((H, W), np.nan, "f")
        out.reshape(-1)[valid] = y_final
        return out, cn


LOG_INTERVAL = 2000


def run_downscale_loop(model, input_data, dates_arr, var_name, period_label, noise_override=None):
    if noise_override is not None:
        model._noise_override = noise_override
    n = input_data.shape[0]
    out = np.empty((n, H, W), dtype="float32")
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


def main():
    from dor_test8_lock import acquire_run_lock

    lock_name = "pr_intensity_experiment" if USE_INTENSITY_RATIO else "pr_intensity_baseline"
    acquire_run_lock(os.path.join(OUT_DIR, f".test8_{lock_name}.lock"), lock_name)

    global _T0
    _T0 = time.time()
    _set_deterministic_seeds(_derive_worker_seed(RUN_SEED, VAR_NAME))

    log("=" * 65)
    log(
        f"PR intensity experiment | intensity_ratio={USE_INTENSITY_RATIO} | "
        f"device={device} | seed={RUN_SEED}"
    )
    log(f"  Input:  {BASE_DIR}")
    log(f"  Output: {OUT_DIR}")
    log("=" * 65)

    inputs = np.memmap(F_INPUTS, dtype="float32", mode="r", shape=(N_DAYS, 6, H, W))
    targets = np.memmap(F_TARGETS, dtype="float32", mode="r", shape=(N_DAYS, 6, H, W))

    model = StochasticSpatialDisaggregatorMultiplicative(
        VAR_IDX, VAR_NAME, use_intensity_ratio=USE_INTENSITY_RATIO
    )
    model.calibrate(inputs, targets, DATES_ALL)

    stack = None
    if STOCHASTIC:
        stack = run_downscale_loop(
            model, inputs[:, VAR_IDX], DATES_ALL, VAR_NAME, "1981-2014 (stoch)"
        )

    mask_2d = np.load(F_MASK) == 1

    log("\n" + "=" * 65)
    log("TABLE 1 — DOMAIN-POOLED METRICS (2006-2014), PR")
    log("=" * 65)
    t1 = calculate_pooled_metrics(targets[TEST_MASK, VAR_IDX], stack[TEST_MASK], VAR_NAME, label="Val")
    df1 = pd.DataFrame([t1])
    print(df1.to_string(index=False), flush=True)
    prefix = "PR_IntensityExp" if USE_INTENSITY_RATIO else "PR_IntensityBaseline"
    df1.to_csv(os.path.join(OUT_DIR, f"{prefix}_Table1_Pooled_Metrics.csv"), index=False)

    log("\n" + "=" * 65)
    log("TABLE 2 — PER-CELL METRICS (2006-2014), PR")
    log("=" * 65)
    t2 = calculate_per_cell_summary_metrics(
        targets[TEST_MASK, VAR_IDX], stack[TEST_MASK], VAR_NAME, mask_2d
    )
    df2 = pd.DataFrame([t2])
    print(df2.to_string(index=False), flush=True)
    df2.to_csv(os.path.join(OUT_DIR, f"{prefix}_Table2_PerCell_Metrics.csv"), index=False)

    log("Saving PR stack...")
    np.savez_compressed(
        os.path.join(OUT_DIR, f"{prefix}_pr_1981_2014.npz"),
        data=stack,
        dates=DATES_ALL.values,
    )
    del stack, model, inputs, targets
    gc.collect()
    log(f"\nDone. Total time: {(time.time() - _T0) / 60:.2f} mins.")


if __name__ == "__main__":
    main()
