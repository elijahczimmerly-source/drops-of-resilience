"""
PR texture diagnostics: LOCA2 vs DOR vs GridMET on historical time-mean and seasonal means.

Reads aligned stacks via benchmark_io.load_multi_product_historical('pr').
Writes CSV + optional JSON summary to 9-fix-pr-splotchiness-attempt-2/ at repo root by default
(env DOR_PR_SPLOTCH_WORKDIR overrides). Filenames gain `_<suite>` when suite is not gridmet_4km.

Run from repo:  python 6-product-comparison/scripts/pr_texture_investigation.py
Or:  cd 6-product-comparison && python scripts/pr_texture_investigation.py --suite nex_native
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
import grid_suites as gs
from benchmark_io import load_multi_product_historical

DOCS_OUT = Path(os.environ.get("DOR_PR_SPLOTCH_WORKDIR", str(REPO_ROOT / "9-fix-pr-splotchiness-attempt-2")))


def _season_masks(dates: pd.DatetimeIndex) -> list[tuple[str, np.ndarray]]:
    m = pd.DatetimeIndex(dates).month.values
    return [
        ("full", np.ones(len(dates), dtype=bool)),
        ("DJF", np.isin(m, (12, 1, 2))),
        ("MAM", np.isin(m, (3, 4, 5))),
        ("JJA", np.isin(m, (6, 7, 8))),
        ("SON", np.isin(m, (9, 10, 11))),
    ]


def _finite_corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    m = np.isfinite(a) & np.isfinite(b)
    if np.sum(m) < 10:
        return float("nan")
    a, b = a[m], b[m]
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    return float(np.sqrt(np.nanmean(d**2)))


def _grad_mag(f: np.ndarray) -> np.ndarray:
    """Mean |gradient| using numpy gradient on 2D field."""
    gy, gx = np.gradient(np.asarray(f, dtype=np.float64))
    return np.hypot(gx, gy)


def _radial_power_2d(f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Azimuthally averaged 2D power spectrum (|FFT|^2), f from mean-subtracted field."""
    z = np.asarray(f, dtype=np.float64)
    z = z - np.nanmean(z)
    z = np.nan_to_num(z, nan=0.0)
    h, w = z.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    zw = z * win
    spec = np.abs(np.fft.fftshift(np.fft.fft2(zw))) ** 2
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2).astype(np.int32)
    rmax = int(r.max()) + 1
    radial = np.bincount(r.ravel(), weights=spec.ravel(), minlength=rmax)
    counts = np.bincount(r.ravel(), minlength=rmax)
    prof = radial / np.maximum(counts, 1)
    radii = np.arange(rmax)
    return radii, prof


def _high_freq_fraction(radii: np.ndarray, prof: np.ndarray, r_cut: float = 20.0) -> float:
    """Fraction of total power in radii >= r_cut (grid units)."""
    tot = float(np.sum(prof * (2 * np.pi * np.maximum(radii, 0.5))))
    if tot <= 0:
        return float("nan")
    hi = radii >= r_cut
    return float(np.sum(prof[hi] * (2 * np.pi * np.maximum(radii[hi], 0.5))) / tot)


def main() -> int:
    ap = argparse.ArgumentParser(description="PR texture metrics vs GridMET")
    ap.add_argument(
        "--suite",
        default=os.environ.get("DOR_BENCHMARK_SUITE", gs.SUITE_GRIDMET_4KM),
        help=f"DOR_BENCHMARK_SUITE ({', '.join(sorted(gs.VALID_SUITES))})",
    )
    args = ap.parse_args()
    suite = args.suite.strip().lower()
    if suite not in gs.VALID_SUITES:
        print(f"Invalid suite {suite!r}; expected one of {sorted(gs.VALID_SUITES)}")
        return 1
    os.environ["DOR_BENCHMARK_SUITE"] = suite
    suf = "" if suite == gs.SUITE_GRIDMET_4KM else f"_{suite}"

    warnings.filterwarnings("ignore", category=RuntimeWarning, message="Mean of empty slice")
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    print(f"Loading historical pr stacks (1981–2014 aligned), suite={suite}...")
    st = load_multi_product_historical("pr", suite=suite)
    dates = st.dates
    obs = st.obs
    loca = st.loca2
    s3 = st.s3
    nex = st.nex

    rows_means = []
    rows_maps = []

    wdf_thr = 0.1  # mm/day, matches benchmark WDF convention

    def add_mean_wdf(label: str, arr: np.ndarray | None) -> None:
        if arr is None:
            return
        flat = np.asarray(arr, dtype=np.float64).ravel()
        m = np.isfinite(flat)
        wdf = float(np.mean(flat[m] > wdf_thr) * 100.0) if np.any(m) else float("nan")
        rows_means.append(
            {
                "product": label,
                "domain_time_mean_mm_day": float(np.nanmean(arr)),
                "wet_day_frac_pct_gt_0p1mm": wdf,
                "n_days": int(arr.shape[0]),
                "shape": f"{arr.shape[1]}x{arr.shape[2]}",
            }
        )

    add_mean_wdf("GridMET", obs)
    if s3 is not None:
        add_mean_wdf("S3_cmip6_inputs", s3)
    for pid, arr in st.dor.items():
        add_mean_wdf(f"DOR_{pid}", arr)
    if loca is not None:
        add_mean_wdf("LOCA2", loca)
    if nex is not None:
        add_mean_wdf("NEX", nex)

    df_means = pd.DataFrame(rows_means)
    df_means.to_csv(DOCS_OUT / f"domain_time_means_pr{suf}.csv", index=False)
    print(df_means.to_string(index=False))

    masks = _season_masks(dates)
    products: list[tuple[str, np.ndarray | None]] = [("GridMET", obs)]
    if s3 is not None:
        products.append(("S3_cmip6_inputs", s3))
    for pid, arr in st.dor.items():
        products.append((f"DOR_{pid}", arr))
    if loca is not None:
        products.append(("LOCA2", loca))
    if nex is not None:
        products.append(("NEX", nex))

    for season_name, mask in masks:
        if int(np.sum(mask)) == 0:
            continue
        ref = np.nanmean(obs[mask], axis=0)

        for prod_name, arr in products:
            if arr is None:
                continue
            sl = arr[mask]
            if sl.shape[0] == 0:
                continue
            fld = np.nanmean(sl, axis=0)
            gm = _grad_mag(fld)
            ref_gm = _grad_mag(ref)
            radii, prof = _radial_power_2d(fld)
            hf = _high_freq_fraction(radii, prof, r_cut=20.0)
            radii_r, prof_r = _radial_power_2d(ref)
            hf_ref = _high_freq_fraction(radii_r, prof_r, r_cut=20.0)

            row = {
                "season": season_name,
                "product": prod_name,
                "r_vs_gridmet": _finite_corr(fld, ref),
                "rmse_vs_gridmet_mm_day": _rmse(fld, ref),
                "mean_grad_mag": float(np.nanmean(gm)),
                "p95_grad_mag": float(np.nanpercentile(gm, 95)),
                "mean_grad_mag_gridmet": float(np.nanmean(ref_gm)),
                "high_freq_power_frac_r_ge_20": hf,
                "gridmet_high_freq_power_frac_r_ge_20": hf_ref,
            }
            rows_maps.append(row)

    df_maps = pd.DataFrame(rows_maps)
    df_maps.to_csv(DOCS_OUT / f"time_mean_map_metrics_pr{suf}.csv", index=False)
    print("\nSaved:", DOCS_OUT / f"domain_time_means_pr{suf}.csv")
    print("Saved:", DOCS_OUT / f"time_mean_map_metrics_pr{suf}.csv")

    summary = {
        "benchmark_suite": suite,
        "hist_window": {"start": cfg.HIST_START, "end": cfg.HIST_END},
        "n_calendar_days_aligned": int(len(dates)),
        "missing": st.missing,
        "interpretation_notes": [
            "LOCA2 is bilinearly interpolated to 216x192 in load_loca2.py (smooths fine scales).",
            "DOR uses stochastic multiplicative noise + OTBC (injects fine-scale variance).",
            "plot_comparison_driver uses independent 2-98% color scales per panel.",
        ],
    }
    (DOCS_OUT / f"run_summary{suf}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Short narrative for FINDINGS
    pivot = df_maps.pivot_table(
        index="season",
        columns="product",
        values="r_vs_gridmet",
        aggfunc="first",
    )
    pivot.to_csv(DOCS_OUT / f"correlation_vs_gridmet_pivot{suf}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
