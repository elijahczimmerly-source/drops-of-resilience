"""Extended per-product diagnostics on the validation window (2006–2014): variance, tails, WDF, lag-1, seasonality."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
import grid_suites as gs
from benchmark_io import LOCA_VARS, load_multi_product_validation
from metrics import calculate_pooled_metrics


def _lag1_domain(ts: np.ndarray) -> float:
    ts = np.asarray(ts, dtype=np.float64)
    if len(ts) < 3 or np.nanstd(ts[:-1]) == 0 or np.nanstd(ts[1:]) == 0:
        return float("nan")
    return float(np.corrcoef(ts[:-1], ts[1:])[0, 1])


def _seasonal_range_domain(ts: np.ndarray, dates: pd.DatetimeIndex) -> float:
    """Peak−trough of monthly mean domain-mean cycle."""
    df = pd.DataFrame({"y": ts, "m": pd.DatetimeIndex(dates).month})
    monthly = df.groupby("m", sort=True)["y"].mean()
    if monthly.size == 0:
        return float("nan")
    return float(monthly.max() - monthly.min())


def _pooled_p01_p99(a: np.ndarray) -> tuple[float, float]:
    v = a[np.isfinite(a)].ravel()
    if v.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(v, 1)), float(np.percentile(v, 99))


def _wdf_pr(a: np.ndarray) -> float:
    v = a[np.isfinite(a)].ravel()
    if v.size == 0:
        return float("nan")
    return float(np.mean(v >= 0.1) * 100.0)


def _wet_day_intensity_pr_mmday(a: np.ndarray) -> float:
    v = a[np.isfinite(a)].ravel()
    wet = v[v >= 0.1]
    if wet.size == 0:
        return float("nan")
    return float(np.mean(wet))


def _skew(a: np.ndarray) -> float:
    v = a[np.isfinite(a)].ravel()
    if v.size < 3:
        return float("nan")
    v = v - np.mean(v)
    s = np.std(v)
    if s == 0:
        return float("nan")
    return float(np.mean(v**3) / (s**3 + 1e-30))


def _cv(a: np.ndarray) -> float:
    v = a[np.isfinite(a)].ravel()
    if v.size == 0:
        return float("nan")
    m = float(np.mean(v))
    if abs(m) < 1e-30:
        return float("nan")
    return float(np.std(v) / abs(m))


def main() -> int:
    ap = argparse.ArgumentParser(description="Extended validation-window diagnostics per product")
    ap.add_argument("--suite", default=gs.SUITE_DOR_NATIVE, help="DOR_BENCHMARK_SUITE")
    args = ap.parse_args()
    os.environ["DOR_BENCHMARK_SUITE"] = str(args.suite).strip()
    suite = gs.benchmark_suite()
    out_root = gs.suite_output_dir(suite)
    out_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    window = "validation_2006_2014"

    for var in cfg.VARS:
        try:
            st = load_multi_product_validation(var, suite=suite)
        except Exception as e:
            rows.append(
                {
                    "variable": var,
                    "window": window,
                    "product": "_error",
                    "pipeline_id": "",
                    "metric": "load_error",
                    "value": float("nan"),
                    "note": str(e),
                }
            )
            continue

        dates = st.dates

        def add_row(product: str, pipeline_id: str, metric: str, value: float, note: str = "") -> None:
            rows.append(
                {
                    "variable": var,
                    "window": window,
                    "product": product,
                    "pipeline_id": pipeline_id,
                    "metric": metric,
                    "value": value,
                    "note": note,
                }
            )

        # GridMET
        obs = st.obs
        dm_o = np.nanmean(obs, axis=(1, 2))
        p1, p99 = _pooled_p01_p99(obs)
        add_row("GridMET", "", "pooled_variance", float(np.nanvar(obs)))
        add_row("GridMET", "", "p01_pooled", p1)
        add_row("GridMET", "", "p99_pooled", p99)
        add_row("GridMET", "", "lag1_domain_mean", _lag1_domain(dm_o))
        add_row("GridMET", "", "seasonal_range_domain_mean", _seasonal_range_domain(dm_o, dates))
        if var == "pr":
            add_row("GridMET", "", "wdf_pct", _wdf_pr(obs))
            add_row("GridMET", "", "wet_day_intensity_mmday", _wet_day_intensity_pr_mmday(obs))
        add_row("GridMET", "", "pooled_skew", _skew(obs))
        add_row("GridMET", "", "pooled_cv", _cv(obs))

        # S3
        if st.s3 is not None:
            s3 = st.s3
            dm = np.nanmean(s3, axis=(1, 2))
            p1, p99 = _pooled_p01_p99(s3)
            add_row("S3_cmip6_inputs", "", "pooled_variance", float(np.nanvar(s3)))
            add_row("S3_cmip6_inputs", "", "p01_pooled", p1)
            add_row("S3_cmip6_inputs", "", "p99_pooled", p99)
            add_row("S3_cmip6_inputs", "", "lag1_domain_mean", _lag1_domain(dm))
            add_row("S3_cmip6_inputs", "", "seasonal_range_domain_mean", _seasonal_range_domain(dm, dates))
            if var == "pr":
                add_row("S3_cmip6_inputs", "", "wdf_pct", _wdf_pr(s3))
                add_row("S3_cmip6_inputs", "", "wet_day_intensity_mmday", _wet_day_intensity_pr_mmday(s3))
            add_row("S3_cmip6_inputs", "", "pooled_skew", _skew(s3))
            add_row("S3_cmip6_inputs", "", "pooled_cv", _cv(s3))
            m = calculate_pooled_metrics(obs, s3, var, label="Val")
            add_row("S3_cmip6_inputs", "", "KGE_vs_GridMET", m.get("Val_KGE", float("nan")))
            add_row("S3_cmip6_inputs", "", "RMSE_vs_GridMET", m.get("Val_RMSE_pooled", float("nan")))
        else:
            add_row("S3_cmip6_inputs", "", "pooled_variance", float("nan"), st.missing.get("s3", "missing"))

        # DOR per pipeline
        for pid, darr in st.dor.items():
            dm = np.nanmean(darr, axis=(1, 2))
            p1, p99 = _pooled_p01_p99(darr)
            add_row("DOR", pid, "pooled_variance", float(np.nanvar(darr)))
            add_row("DOR", pid, "p01_pooled", p1)
            add_row("DOR", pid, "p99_pooled", p99)
            add_row("DOR", pid, "lag1_domain_mean", _lag1_domain(dm))
            add_row("DOR", pid, "seasonal_range_domain_mean", _seasonal_range_domain(dm, dates))
            if var == "pr":
                add_row("DOR", pid, "wdf_pct", _wdf_pr(darr))
                add_row("DOR", pid, "wet_day_intensity_mmday", _wet_day_intensity_pr_mmday(darr))
            add_row("DOR", pid, "pooled_skew", _skew(darr))
            add_row("DOR", pid, "pooled_cv", _cv(darr))
            m = calculate_pooled_metrics(obs, darr, var, label="Val")
            add_row("DOR", pid, "KGE_vs_GridMET", m.get("Val_KGE", float("nan")))

        # LOCA2
        if st.loca2 is not None and np.any(np.isfinite(st.loca2)):
            loca = st.loca2
            dm = np.nanmean(loca, axis=(1, 2))
            p1, p99 = _pooled_p01_p99(loca)
            add_row("LOCA2", "", "pooled_variance", float(np.nanvar(loca)))
            add_row("LOCA2", "", "p01_pooled", p1)
            add_row("LOCA2", "", "p99_pooled", p99)
            add_row("LOCA2", "", "lag1_domain_mean", _lag1_domain(dm))
            add_row("LOCA2", "", "seasonal_range_domain_mean", _seasonal_range_domain(dm, dates))
            if var == "pr":
                add_row("LOCA2", "", "wdf_pct", _wdf_pr(loca))
                add_row("LOCA2", "", "wet_day_intensity_mmday", _wet_day_intensity_pr_mmday(loca))
            add_row("LOCA2", "", "pooled_skew", _skew(loca))
            add_row("LOCA2", "", "pooled_cv", _cv(loca))
            m = calculate_pooled_metrics(obs, loca, var, label="Val")
            add_row("LOCA2", "", "KGE_vs_GridMET", m.get("Val_KGE", float("nan")))
        elif var not in LOCA_VARS:
            add_row("LOCA2", "", "pooled_variance", float("nan"), "not_applicable_external")
        else:
            add_row("LOCA2", "", "pooled_variance", float("nan"), st.missing.get("loca2", "missing"))

        # NEX
        if st.nex is not None and np.any(np.isfinite(st.nex)):
            nex = st.nex
            dm = np.nanmean(nex, axis=(1, 2))
            p1, p99 = _pooled_p01_p99(nex)
            add_row("NEX", "", "pooled_variance", float(np.nanvar(nex)))
            add_row("NEX", "", "p01_pooled", p1)
            add_row("NEX", "", "p99_pooled", p99)
            add_row("NEX", "", "lag1_domain_mean", _lag1_domain(dm))
            add_row("NEX", "", "seasonal_range_domain_mean", _seasonal_range_domain(dm, dates))
            if var == "pr":
                add_row("NEX", "", "wdf_pct", _wdf_pr(nex))
                add_row("NEX", "", "wet_day_intensity_mmday", _wet_day_intensity_pr_mmday(nex))
            add_row("NEX", "", "pooled_skew", _skew(nex))
            add_row("NEX", "", "pooled_cv", _cv(nex))
            m = calculate_pooled_metrics(obs, nex, var, label="Val")
            add_row("NEX", "", "KGE_vs_GridMET", m.get("Val_KGE", float("nan")))
        else:
            add_row("NEX", "", "pooled_variance", float("nan"), st.missing.get("nex", "missing"))

    df = pd.DataFrame(rows)
    suf = "" if gs.is_dor_native_suite(suite) else f"_{suite}"
    out = out_root / f"stage_diagnostics_extended{suf}.csv"
    df.to_csv(out, index=False)
    print(df.head(40).to_string(index=False))
    print(f"\nWrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
