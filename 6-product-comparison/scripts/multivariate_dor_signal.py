"""
Optional plan §7: Frobenius distance between historical and future 6×6 daily correlation matrices
(domain-mean daily time series per variable) for DOR S4 per pipeline.
"""
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
from climate_signal_io import VARS_INTERNAL, load_dor_future_npz, load_dor_main_npz


def _slice_by_dates(
    data: np.ndarray,
    dates: pd.DatetimeIndex,
    start: str,
    end: str,
) -> np.ndarray:
    m = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    return data[m]


def frob_corr_diff_hist_fut(h_mat: np.ndarray, f_mat: np.ndarray) -> float:
    """h_mat (Th,6), f_mat (Tf,6) — upper-triangle Frobenius norm of Corr_fut - Corr_hist."""
    if h_mat.shape[1] != 6 or f_mat.shape[1] != 6:
        return float("nan")
    if h_mat.shape[0] < 30 or f_mat.shape[0] < 30:
        return float("nan")
    c0 = np.corrcoef(h_mat.T)
    c1 = np.corrcoef(f_mat.T)
    tri = np.triu_indices(6, k=1)
    return float(np.linalg.norm(c1[tri] - c0[tri]))


def main() -> int:
    p = argparse.ArgumentParser(description="DOR multivariate correlation-matrix distance (optional plan metric)")
    p.add_argument(
        "--unshuffled",
        action="store_true",
        help="Use unshuffled future NPZ instead of default SHUFFLED",
    )
    args = p.parse_args()
    shuf = not args.unshuffled

    hist_s, hist_e = cfg.SIGNAL_HIST_START, cfg.SIGNAL_HIST_END
    fut_s, fut_e = cfg.SIGNAL_FUT_START, cfg.SIGNAL_FUT_END
    pipeline_ids = ["test8_v2", "test8_v3", "test8_v4"]
    _dor_shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    use_shared = os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    rows: list[dict] = []
    for pid in pipeline_ids:
        dor_dir = (
            Path(_dor_shared)
            if (_dor_shared and use_shared)
            else cfg.DOR_DEFAULT_OUTPUTS.get(pid)
        )
        if dor_dir is None or not dor_dir.is_dir():
            continue
        dm_hs: list[np.ndarray] = []
        dm_fs: list[np.ndarray] = []
        ok = True
        for var in VARS_INTERNAL:
            try:
                dh, dd = load_dor_main_npz(dor_dir, var)
                dfu, ddf = load_dor_future_npz(dor_dir, var, shuffled=shuf)
                h = _slice_by_dates(dh, dd, hist_s, hist_e)
                f = _slice_by_dates(dfu, ddf, fut_s, fut_e)
                dm_hs.append(np.nanmean(h, axis=(1, 2)))
                dm_fs.append(np.nanmean(f, axis=(1, 2)))
            except FileNotFoundError:
                ok = False
                break
        if not ok:
            continue
        th = min(len(x) for x in dm_hs)
        tf = min(len(x) for x in dm_fs)
        h_mat = np.stack([x[:th] for x in dm_hs], axis=1)
        f_mat = np.stack([x[:tf] for x in dm_fs], axis=1)
        fr = frob_corr_diff_hist_fut(h_mat, f_mat)
        rows.append(
            {
                "pipeline_id": pid,
                "frobenius_corr_diff_hist_vs_fut": fr,
                "n_days_hist": th,
                "n_days_fut": tf,
                "future_npz": "shuffled" if shuf else "unshuffled",
            }
        )

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = cfg.OUTPUT_DIR / "climate_signal_multivariate_dor.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
