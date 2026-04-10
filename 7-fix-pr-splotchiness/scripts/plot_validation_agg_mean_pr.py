"""
Time-mean validation (2006–2014) side-by-side maps: GridMET | DOR — same layout and
color scaling as `6-product-comparison/scripts/plot_validation_period.py`
(`validation_agg_mean_pr.png`).

Uses the full 1981–2014 memmap for obs and `Stochastic_V8_Hybrid_pr.npz` from a test8 run.

Example:
  python plot_validation_agg_mean_pr.py \\
    --dor-npz .../experiment_plan_debias/Stochastic_V8_Hybrid_pr.npz \\
    --gridmet-targets \\\\abe-cylo\\...\\gridmet_targets_19810101-20141231.dat \\
    --geo-mask \\\\abe-cylo\\...\\geo_mask.npy \\
    --title-right "DOR debias (legacy chain)\\nmean 2006–2014" \\
    --out .../dor_val_01_plan_debias.png
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

VAR_YLABEL_PR = "Domain mean (mm day⁻¹)"


def _pair_vmin_vmax(o: np.ndarray, d: np.ndarray) -> tuple[float, float]:
    finite = np.concatenate([o[np.isfinite(o)].ravel(), d[np.isfinite(d)].ravel()])
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, 2))
    vmax = float(np.percentile(finite, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    vmin = max(0.0, vmin)
    return vmin, vmax


def _save_obs_dor_pair(
    out_path: Path,
    o: np.ndarray,
    d: np.ndarray,
    title_left: str,
    title_right: str,
    suptitle: str,
    *,
    figsize: tuple[float, float] = (10, 4.2),
) -> None:
    vmin, vmax = _pair_vmin_vmax(o, d)
    cmap = "Blues"
    fig, axes = plt.subplots(1, 2, figsize=figsize, constrained_layout=True)
    axes[0].imshow(o, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
    axes[0].set_title(title_left)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    im1 = axes[1].imshow(d, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
    axes[1].set_title(title_right)
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    fig.suptitle(suptitle, fontsize=11)
    fig.colorbar(im1, ax=axes, shrink=0.85, label=VAR_YLABEL_PR)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dor-npz", required=True, help="Stochastic_V8_Hybrid_pr.npz from a run")
    ap.add_argument(
        "--gridmet-targets",
        required=True,
        help="gridmet_targets_19810101-20141231.dat memmap",
    )
    ap.add_argument("--geo-mask", required=True, help="geo_mask.npy (216×192)")
    ap.add_argument(
        "--title-right",
        default="DOR\nmean 2006–2014",
        help="Right panel title (use \\n for newline)",
    )
    ap.add_argument("--out", required=True, help="Output PNG path")
    args = ap.parse_args()

    mask = np.load(args.geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape

    z = np.load(args.dor_npz)
    dor = np.asarray(z["data"], dtype=np.float64)
    z.close()
    n_days = dor.shape[0]
    if dor.shape[1:] != (H, W):
        print(
            f"ERROR: DOR spatial {dor.shape[1:]} != ({H},{W})",
            file=sys.stderr,
        )
        return 1

    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    val_mask = np.asarray(dates > pd.Timestamp("2005-12-31"), dtype=bool)

    mm = np.memmap(
        args.gridmet_targets,
        dtype="float32",
        mode="r",
        shape=(n_days, 6, H, W),
    )
    obs_pr = np.asarray(mm[:, 0, :, :], dtype=np.float64)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        o = np.nanmean(obs_pr[val_mask], axis=0)
        d = np.nanmean(dor[val_mask], axis=0)

    title_right = args.title_right.replace("\\n", "\n")
    _save_obs_dor_pair(
        Path(args.out),
        o,
        d,
        "GridMET (target)\nmean 2006–2014",
        title_right,
        "pr — time-mean fields, shared color scale (2–98%)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
