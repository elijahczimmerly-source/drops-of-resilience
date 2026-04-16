"""
Climate-change signal: slice driving memmaps (S3), DOR NPZs (S4), LOCA2/NEX.
Aligned with Bhuwan Compare_All_Signals_Iowa_Parallel metric definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import config as cfg

VARS_INTERNAL = list(cfg.VARS)

DATES_MAIN = pd.date_range(cfg.HIST_START, cfg.HIST_END, freq="D")
DATES_FUTURE = pd.date_range("2015-01-01", "2100-12-31", freq="D")
N_DAYS_FUTURE = len(DATES_FUTURE)


def load_cmip6_variable(
    memmap_path: Path,
    var: str,
    date_start: str,
    date_end: str,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """S3: slice (T,H,W) for one variable from 6-stack memmap (hist or future file).

    Slices the memmap to the requested date window only (avoids loading the full future timeline).
    Returns float32 to reduce peak RAM.
    """
    if not memmap_path.is_file():
        raise FileNotFoundError(memmap_path)
    vidx = VARS_INTERNAL.index(var)
    path_s = str(memmap_path).lower()
    is_future = "ssp585" in path_s or "20150101" in path_s
    if is_future:
        dates = DATES_FUTURE
        n = N_DAYS_FUTURE
    else:
        dates = DATES_MAIN
        n = cfg.N_DAYS_MAIN

    mm = np.memmap(
        str(memmap_path),
        dtype="float32",
        mode="r",
        shape=(n, len(VARS_INTERNAL), cfg.H, cfg.W),
    )
    ts0, ts1 = pd.Timestamp(date_start), pd.Timestamp(date_end)
    i0 = int(dates.searchsorted(ts0))
    i1 = int(dates.searchsorted(ts1, side="right")) - 1
    if i0 > i1 or i0 >= n:
        raise ValueError(f"No CMIP6 days in [{date_start}, {date_end}]")
    sl = np.asarray(mm[i0 : i1 + 1, vidx, :, :], dtype=np.float32)
    return sl, dates[i0 : i1 + 1]


def load_dor_main_npz(dor_dir: Path, var: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    p = dor_dir / f"Stochastic_V8_Hybrid_{var}.npz"
    if not p.is_file():
        raise FileNotFoundError(p)
    z = np.load(p)
    return np.asarray(z["data"], dtype=np.float64), pd.to_datetime(z["dates"])


def load_dor_future_npz(dor_dir: Path, var: str, *, shuffled: bool = True) -> tuple[np.ndarray, pd.DatetimeIndex]:
    tag = "SSP585_2015_2100_SHUFFLED" if shuffled else "SSP585_2015_2100"
    p = dor_dir / f"Stochastic_V8_Hybrid_{var}_{tag}.npz"
    if not p.is_file():
        raise FileNotFoundError(p)
    z = np.load(p)
    return np.asarray(z["data"], dtype=np.float64), pd.to_datetime(z["dates"])


def pooled_ext99(a: np.ndarray) -> float:
    v = np.asarray(a, dtype=np.float64).ravel()
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    return float(np.percentile(v, 99.0))


def domain_mean_and_signal(
    hist: np.ndarray,
    fut: np.ndarray,
    var: str,
) -> dict[str, float]:
    """Bhuwan-style domain-mean signal; pr uses relative % change."""
    mh, mf = float(np.nanmean(hist)), float(np.nanmean(fut))
    if var == "pr":
        sig = (mf / (mh + 1e-9) - 1.0) * 100.0
    else:
        sig = mf - mh
    eh, ef = pooled_ext99(hist), pooled_ext99(fut)
    if var == "pr":
        d99 = (ef / (eh + 1e-12) - 1.0) * 100.0
    else:
        d99 = ef - eh
    return {"mean_hist": mh, "mean_fut": mf, "signal": sig, "ext99_hist": eh, "ext99_fut": ef, "delta_ext99": d99}


def spatial_delta_maps(
    hist: np.ndarray,
    fut: np.ndarray,
    var: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Per-cell mean over time then delta. hist, fut: (Th,H,W) and (Tf,H,W) — use
    mean over each window separately (Bhuwan compares means of fut slice vs hist slice).
    """
    mh = np.nanmean(hist, axis=0)
    mf = np.nanmean(fut, axis=0)
    if var == "pr":
        delta = (mf / (mh + 1e-9) - 1.0) * 100.0
    else:
        delta = mf - mh
    return mh, delta


def preservation_metrics(delta_a: np.ndarray, delta_b: np.ndarray, mask_2d: np.ndarray) -> dict[str, float]:
    """Spatial r and RMSE between two delta fields (216x192)."""
    a = delta_a[mask_2d].ravel()
    b = delta_b[mask_2d].ravel()
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 10:
        return {"r": float("nan"), "rmse": float("nan")}
    r = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else float("nan")
    rmse = float(np.sqrt(np.nanmean((a - b) ** 2)))
    return {"r": r, "rmse": rmse}


@dataclass
class SignalSliceResult:
    stage: str
    product: str
    pipeline_id: str | None
    variable: str
    mean_hist: float
    mean_fut: float
    signal: float
    signal_kind: str  # "pct" or "abs"
    std_spatial_delta: float
    ext99_hist: float = float("nan")
    ext99_fut: float = float("nan")
    delta_ext99: float = float("nan")
    note: str = ""


def signal_row(
    stage: str,
    product: str,
    var: str,
    hist: np.ndarray,
    fut: np.ndarray,
    mask_2d: np.ndarray,
    pipeline_id: str | None = None,
) -> SignalSliceResult:
    _, dmap = spatial_delta_maps(hist, fut, var)
    std_sp = float(np.nanstd(dmap[mask_2d]))
    dm = domain_mean_and_signal(hist, fut, var)
    return SignalSliceResult(
        stage,
        product,
        pipeline_id,
        var,
        dm["mean_hist"],
        dm["mean_fut"],
        dm["signal"],
        "pct" if var == "pr" else "abs",
        std_sp,
        dm["ext99_hist"],
        dm["ext99_fut"],
        dm["delta_ext99"],
        "",
    )


def s1_raw_placeholder_row(var: str, note: str = "") -> SignalSliceResult:
    return SignalSliceResult(
        "S1_raw",
        "Cropped_Iowa_Raw",
        None,
        var,
        float("nan"),
        float("nan"),
        float("nan"),
        "abs",
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
        note or "S1 raw: set DOR_SCENARIO_RAW_ROOT or ensure config.S1_RAW_CROPPED_ROOT lists yearly Cropped_*_day_MPI-ESM1-2-HR_*.npz.",
    )


def results_to_dataframe(results: list[SignalSliceResult]) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in results])
