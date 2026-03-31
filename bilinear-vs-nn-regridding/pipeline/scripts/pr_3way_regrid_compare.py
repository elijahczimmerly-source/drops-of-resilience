"""
pr_3way_regrid_compare.py — 3-way regrid comparison for precipitation only.

Regrids pr with conservative (baseline), bilinear, and nearest-neighbor,
runs test8's multiplicative stochastic downscaler on each, and compares
metrics (Ext99_Bias%, KGE, RMSE, WDF, Lag1).

Output:
  pipeline/output/pr_3way/
    pr_3way_metrics.csv
    Stochastic_pr_{conservative,bilinear,nn}.npz
    pr_3way_console.log  (if run via batch redirect)

Env: TEST8_SEED (default 42), TEST8_MAX_WORKERS (default 2).
"""
from __future__ import annotations

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
import xarray as xr
import xarray_regrid  # noqa: F401 — registers .regrid accessor

warnings.filterwarnings("ignore")

# ─── seeds ───────────────────────────────────────────────────────────────────
RUN_SEED = int(os.environ.get("TEST8_SEED", "42"))


def _derive_worker_seed(base: int, label: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{base}:{label}".encode()).digest()[:4], "little") & 0x7FFFFFFF


def _set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ─── paths ───────────────────────────────────────────────────────────────────
PIPELINE = r"C:\drops-of-resilience\bilinear-vs-nn-regridding\pipeline"
SOURCE_BC = os.path.join(PIPELINE, "source_bc")
GRIDMET_DIR = os.path.join(PIPELINE, "gridmet_cropped")
BILINEAR_DATA = os.path.join(PIPELINE, "data", "bilinear")
OUT_DIR = os.path.join(PIPELINE, "output", "pr_3way")
os.makedirs(OUT_DIR, exist_ok=True)

F_MASK = os.path.join(BILINEAR_DATA, "geo_mask.npy")
F_TARGETS = os.path.join(BILINEAR_DATA, "gridmet_targets_19810101-20141231.dat")

# ─── grid / dates ────────────────────────────────────────────────────────────
_m = np.load(F_MASK)
H, W = _m.shape
del _m

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TRAIN_MASK = DATES_ALL <= "2005-12-31"
TEST_MASK = DATES_ALL > "2005-12-31"
N_DAYS = len(DATES_ALL)

USE_SEMIMONTHLY = True
N_PERIODS = 24
NOISE_FACTOR_MULT = 0.15
PR_WDF_THRESHOLD_FACTOR = 1.2

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_T0 = time.time()


def _ram_gb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024**3
    except ImportError:
        return -1.0


def log(msg: str) -> None:
    r = _ram_gb()
    rs = f" | RAM {r:.1f} GB" if r >= 0 else ""
    print(f"[{time.time() - _T0:7.1f}s{rs}] {msg}", flush=True)


def get_period_idx(month: int, day: int) -> int:
    return (month - 1) * 2 + (0 if day <= 15 else 1)


# ═════════════════════════════════════════════════════════════════════════════
# 1. REGRIDDING
# ═════════════════════════════════════════════════════════════════════════════
def _get_dst_grid() -> xr.Dataset:
    ds = xr.open_dataset(os.path.join(GRIDMET_DIR, "Cropped_pr_2011.nc"))
    return xr.Dataset(coords={"lat": ds["lat"], "lon": ds["lon"]})


def _load_cmip6_da(scenario: str) -> xr.DataArray | None:
    pattern = "historical" if scenario == "historical" else "ssp585"
    prefix = "Cropped_pr_"
    files = [f for f in os.listdir(SOURCE_BC)
             if f.startswith(prefix) and pattern in f and f.endswith(".npz")]
    if not files:
        return None
    fpath = os.path.join(SOURCE_BC, files[0])
    with np.load(fpath, allow_pickle=True) as npz:
        lat = np.asarray(npz["lat"])
        lon = np.asarray(npz["lon"])
        lon = np.where(lon > 180, lon - 360, lon)
        keys = [k for k in npz.keys() if k not in ("lat", "lon", "time", "years", "elevation")]
        key = "pr" if "pr" in npz else keys[0]
        data = np.asarray(npz[key], dtype=np.float32)
    nt = data.shape[0]
    if lat.ndim == 1:
        return xr.DataArray(data, dims=("time", "lat", "lon"),
                            coords={"time": np.arange(nt), "lat": lat, "lon": lon}, name="pr")
    return xr.DataArray(data, dims=("time", "y", "x"),
                        coords={"time": np.arange(nt),
                                "lat": (("y", "x"), lat), "lon": (("y", "x"), lon)}, name="pr")


def _regrid_da(da: xr.DataArray, dst: xr.Dataset, method: str) -> xr.DataArray:
    if method == "conservative":
        return da.regrid.conservative(dst, latitude_coord="lat")
    if method == "nearest":
        return da.regrid.nearest(dst)
    return da.regrid.linear(dst)


def regrid_pr_to_npy(method: str, dst_grid: xr.Dataset) -> str:
    """Regrid pr historical only with *method*. Returns hist_npy_path."""
    tag = {"conservative": "cons", "bilinear": "bil", "nearest": "nn"}[method]
    h_path = os.path.join(OUT_DIR, f"regridded_hist_pr_{tag}.npy")

    if os.path.isfile(h_path):
        log(f"  [SKIP] {os.path.basename(h_path)} already exists.")
        return h_path

    da = _load_cmip6_da("historical")
    if da is None:
        raise RuntimeError("No CMIP6 pr historical file found.")
    log(f"  Regridding pr historical with {method}...")
    chunk = 200
    nt = da.sizes["time"]
    probe = _regrid_da(da.isel(time=slice(0, 1)), dst_grid, method)
    _, ho, wo = probe.values.shape
    mm = np.lib.format.open_memmap(h_path, mode="w+", dtype=np.float32, shape=(nt, ho, wo))
    for s in range(0, nt, chunk):
        e = min(s + chunk, nt)
        rg = _regrid_da(da.isel(time=slice(s, e)), dst_grid, method)
        mm[s:e] = rg.values.astype(np.float32)
        del rg; gc.collect()
    mm.flush()
    del mm; gc.collect()
    log(f"  [OK] {os.path.basename(h_path)} ({nt} days)")
    return h_path


# ═════════════════════════════════════════════════════════════════════════════
# 2. EXTRACT PR INPUTS FROM REGRIDDED .NPY (no .dat needed)
# ═════════════════════════════════════════════════════════════════════════════
CMIP_START = pd.Timestamp("1850-01-01")


def extract_pr_inputs(hist_npy: str) -> np.ndarray:
    """Slice the 1981-2014 window out of the full historical regridded pr .npy."""
    regridded = np.load(hist_npy, mmap_mode="r")
    offset_start = (pd.Timestamp("1981-01-01") - CMIP_START).days
    offset_end = offset_start + N_DAYS
    return np.asarray(regridded[offset_start:offset_end], dtype=np.float32)


# ═════════════════════════════════════════════════════════════════════════════
# 3. TEST8 PR-ONLY (multiplicative downscaler + metrics)
# ═════════════════════════════════════════════════════════════════════════════
def generate_spatial_noise(shape, cl=5.0):
    h, w = shape
    n = torch.randn(h, w, device=device)
    kh = torch.fft.fftfreq(h, device=device).reshape(-1, 1)
    kw = torch.fft.fftfreq(w, device=device).reshape(1, -1)
    kernel = torch.exp(-0.5 * (torch.sqrt(kh**2 + kw**2) * cl) ** 2)
    f = torch.fft.ifftn(torch.fft.fftn(n) * kernel).real
    return (f - f.mean()) / (f.std() + 1e-8)


class PrDownscaler:
    def __init__(self):
        self.mask = np.load(F_MASK).flatten() == 1
        self.spatial_ratio = np.ones((N_PERIODS, H, W), dtype="float32")
        self.resid_cv = np.zeros((N_PERIODS, H, W), dtype="float32")
        self.monthly_threshold = np.zeros((N_PERIODS, H, W), dtype="float32")

    def calibrate(self, inputs_ch0, targets_ch0):
        log("  [PR] Calibrating...")
        for p in range(N_PERIODS):
            idx = [i for i in np.where(TRAIN_MASK)[0] if get_period_idx(DATES_ALL[i].month, DATES_ALL[i].day) == p]
            if len(idx) < 2:
                continue
            in_m = inputs_ch0[idx]
            tar_m = targets_ch0[idx]
            m_gcm = np.nanmean(in_m, axis=0)
            m_obs = np.nanmean(tar_m, axis=0)
            self.spatial_ratio[p] = np.clip(m_obs / (m_gcm + 1e-4), 0.05, 20.0)
            sim_base = in_m * self.spatial_ratio[p][None, :, :]
            resid = tar_m - sim_base
            self.resid_cv[p] = np.nanstd(resid, axis=0) / (np.nanmean(sim_base, axis=0) + 1e-4)
            sim_sorted = np.sort(sim_base, axis=0)
            wdf = np.mean(tar_m >= 0.1, axis=0)
            ti = np.clip(np.round((1 - wdf) * (len(idx) - 1)).astype(int), 0, len(idx) - 1)
            Hi, Wi = np.indices((H, W))
            self.monthly_threshold[p] = sim_sorted[ti, Hi, Wi]

    def downscale(self, inputs_ch0, stochastic=True):
        n = inputs_ch0.shape[0]
        out = np.empty((n, H, W), dtype="float32")
        prev_noise = None
        for d in range(n):
            dt = DATES_ALL[d]
            pi = get_period_idx(dt.month, dt.day)
            valid = self.mask & np.isfinite(inputs_ch0[d].flatten())
            if not np.any(valid):
                out[d] = np.nan
                continue
            iv = inputs_ch0[d].flatten()[valid]
            ratio = self.spatial_ratio[pi].flatten()[valid]
            y_base = iv * ratio
            with torch.no_grad():
                ns = generate_spatial_noise((H, W))
                cn = ns if prev_noise is None else 0.5 * prev_noise + np.sqrt(1 - 0.25) * ns
            if stochastic:
                cv = self.resid_cv[pi].flatten()[valid]
                nm = 1.0 + cn.cpu().numpy().flatten()[valid] * cv * NOISE_FACTOR_MULT
                nm = np.clip(nm, 0.1, 5.0)
                y_final = y_base * nm
            else:
                y_final = y_base
            th = self.monthly_threshold[pi].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
            y_final = np.where(y_final <= th, 0, y_final)
            y_final = np.where(y_final < 0.1, 0, y_final)
            frame = np.full((H, W), np.nan, dtype="float32")
            frame.reshape(-1)[valid] = y_final
            out[d] = frame
            prev_noise = cn
            if d % 2000 == 0:
                log(f"    pr stoch: day {d:>6d}/{n}")
        log(f"    pr stoch: done ({n} days)")
        return out


def schaake_shuffle_pr(sim_3d, targets_ch0):
    """Schaake shuffle for a single variable (pr)."""
    mask_2d = np.load(F_MASK) == 1
    sim_m = sim_3d[:, mask_2d]
    ref = targets_ch0[TRAIN_MASK][:, mask_2d]
    n_train = ref.shape[0]
    n_days = sim_m.shape[0]
    sim_sorted = np.sort(sim_m, axis=0)
    ref_ranks = np.argsort(np.argsort(ref, axis=0), axis=0)
    ref_q = ref_ranks / (n_train - 1 + 1e-6)
    idx_map = np.arange(n_days) % n_train
    target_q = ref_q[idx_map, :]
    final_idx = np.round(target_q * (n_days - 1)).astype(int)
    out = sim_3d.copy()
    out[:, mask_2d] = sim_sorted[final_idx, np.arange(sim_m.shape[1])]
    del sim_m, ref, sim_sorted, ref_ranks, ref_q, target_q, final_idx
    return out


def calc_metrics(obs_3d, sim_3d, label="Val"):
    obs, sim = obs_3d.flatten(), sim_3d.flatten()
    m = np.isfinite(obs) & np.isfinite(sim)
    o, s = obs[m], sim[m]
    if len(o) == 0:
        return {}
    r = np.corrcoef(o, s)[0, 1] if np.std(o) > 0 and np.std(s) > 0 else 0
    alpha = np.std(s) / (np.std(o) + 1e-6)
    beta = np.mean(s) / (np.mean(o) + 1e-6)
    kge = 1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
    rmse = np.sqrt(np.mean((o - s) ** 2))
    bias = np.mean(s) - np.mean(o)
    o99, s99 = np.percentile(o, 99), np.percentile(s, 99)
    ext99 = ((s99 - o99) / (o99 + 1e-6) * 100) if o99 != 0 else 0

    def lag1(a):
        ts = np.nanmean(a, axis=(1, 2))
        return np.corrcoef(ts[:-1], ts[1:])[0, 1]

    return {
        f"{label}_KGE": kge,
        f"{label}_RMSE_pooled": rmse,
        f"{label}_Bias": bias,
        f"{label}_Ext99_Bias%": ext99,
        f"{label}_Lag1_Obs": lag1(obs_3d),
        f"{label}_Lag1_Sim": lag1(sim_3d),
        f"{label}_Lag1_Err": abs(lag1(obs_3d) - lag1(sim_3d)),
        f"{label}_WDF_Obs%": np.mean(o >= 0.1) * 100,
        f"{label}_WDF_Sim%": np.mean(s >= 0.1) * 100,
    }


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
METHODS = ["conservative", "bilinear", "nearest"]
TAGS = {"conservative": "cons", "bilinear": "bil", "nearest": "nn"}

if __name__ == "__main__":
    _set_seeds(RUN_SEED)
    log("=" * 65)
    log("PR 3-WAY REGRID COMPARISON")
    log(f"  Grid: {H}x{W}  |  TEST8_SEED={RUN_SEED}")
    log("=" * 65)

    dst_grid = _get_dst_grid()

    # Step 1: regrid pr with all 3 methods (hist only — no ssp585 needed for comparison)
    hist_npys: dict[str, str] = {}
    for method in METHODS:
        log(f"\n--- Regridding pr ({method}) ---")
        hist_npys[method] = regrid_pr_to_npy(method, dst_grid)

    # Step 2: load targets once (channel 0 = pr from bilinear pipeline's targets .dat)
    log("\nLoading GridMET targets (pr)...")
    targets_mm = np.memmap(F_TARGETS, dtype="float32", mode="r", shape=(N_DAYS, 6, H, W))
    targets_pr = np.asarray(targets_mm[:, 0])
    del targets_mm; gc.collect()
    log(f"  targets_pr shape: {targets_pr.shape}")

    # Step 3: for each method → extract inputs, calibrate, downscale, metrics
    results = []
    for method in METHODS:
        tag = TAGS[method]
        log(f"\n{'=' * 65}")
        log(f"TEST8 PR — {method.upper()}")
        log("=" * 65)
        _set_seeds(_derive_worker_seed(RUN_SEED, f"pr_{tag}"))

        log(f"  Extracting pr inputs from {os.path.basename(hist_npys[method])}...")
        inputs_pr = extract_pr_inputs(hist_npys[method])
        log(f"  inputs_pr shape: {inputs_pr.shape}")

        model = PrDownscaler()
        model.calibrate(inputs_pr, targets_pr)
        sim = model.downscale(inputs_pr)

        sim = schaake_shuffle_pr(sim, targets_pr)

        m = calc_metrics(targets_pr[TEST_MASK], sim[TEST_MASK])
        m["Method"] = method
        results.append(m)
        log(f"  KGE={m['Val_KGE']:.4f}  RMSE={m['Val_RMSE_pooled']:.3f}  "
            f"Ext99={m['Val_Ext99_Bias%']:.2f}%  WDF_Obs={m['Val_WDF_Obs%']:.1f}%  WDF_Sim={m['Val_WDF_Sim%']:.1f}%")

        np.savez_compressed(os.path.join(OUT_DIR, f"Stochastic_pr_{tag}.npz"),
                            data=sim, dates=DATES_ALL.values)
        log(f"  Saved Stochastic_pr_{tag}.npz")
        del sim, inputs_pr, model; gc.collect()

    df = pd.DataFrame(results)
    cols = ["Method"] + [c for c in df.columns if c != "Method"]
    df = df[cols]
    csv_path = os.path.join(OUT_DIR, "pr_3way_metrics.csv")
    df.to_csv(csv_path, index=False)
    log(f"\n{'=' * 65}")
    log("PR 3-WAY COMPARISON — RESULTS")
    log("=" * 65)
    print(df.to_string(index=False), flush=True)
    log(f"\nSaved {csv_path}")
    log(f"Total time: {(time.time() - _T0) / 60:.1f} mins.")
