"""
Time-mean validation (2006–2014): GridMET (target) | GCM input on the same 4 km grid.

Uses the **same** memmaps as `test8_v2_pr_intensity` (no downscaling): `gridmet_targets` and
`cmip6_inputs` (flat or `(n_days, 6, H, W)` float32); band 0 = pr (mm day⁻¹). Flat files are
reshaped using `geo_mask` dimensions.

Use this to see whether time-mean spatial texture (often called “splotchiness” in diagnostics)
is already present in the interpolated GCM field vs obs.

Default: **independent** 2–98% color stretch per panel (two colorbars) so the GCM panel is
not dominated by GridMET’s amplitude range. Use `--shared-scale` for strict comparable scaling
(old behavior; GCM often looks blurry/washed out).

Example:
  python plot_validation_agg_mean_pr_obs_vs_gcm.py \\
    --cmip6-hist \\\\abe-cylo\\...\\cmip6_inputs_19810101-20141231.dat \\
    --gridmet-targets \\\\abe-cylo\\...\\gridmet_targets_19810101-20141231.dat \\
    --geo-mask \\\\abe-cylo\\...\\geo_mask.npy \\
    --title-right "MPI-ESM1-2-HR (OTBC → 4 km)\\nmean 2006–2014" \\
    --out .../gcm_vs_gridmet_validation_agg_mean_pr.png
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd

VAR_YLABEL_PR = "Mean pr (mm day⁻¹)"


def _vmin_vmax_one(a: np.ndarray) -> tuple[float, float]:
    finite = a[np.isfinite(a)].ravel()
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, 2))
    vmax = float(np.percentile(finite, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    return max(0.0, vmin), vmax


def _save_obs_gcm_pair_independent(
    out_path: Path,
    o: np.ndarray,
    g: np.ndarray,
    title_left: str,
    title_right: str,
    suptitle: str,
    *,
    dpi: int = 200,
    figsize: tuple[float, float] = (10.5, 4.5),
) -> None:
    """Separate 2–98% stretch per panel so the GCM is not washed out by GridMET’s range."""
    import matplotlib.pyplot as plt

    vmin_o, vmax_o = _vmin_vmax_one(o)
    vmin_g, vmax_g = _vmin_vmax_one(g)
    cmap = "Blues"
    fig, axes = plt.subplots(1, 2, figsize=figsize, constrained_layout=True)
    im0 = axes[0].imshow(
        o, origin="upper", aspect="auto", vmin=vmin_o, vmax=vmax_o, cmap=cmap
    )
    axes[0].set_title(title_left)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)

    im1 = axes[1].imshow(
        g, origin="upper", aspect="auto", vmin=vmin_g, vmax=vmax_g, cmap=cmap
    )
    axes[1].set_title(title_right)
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)

    fig.suptitle(suptitle, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    print(f"Wrote {out_path}")


def _save_obs_gcm_pair_shared(
    out_path: Path,
    o: np.ndarray,
    g: np.ndarray,
    title_left: str,
    title_right: str,
    suptitle: str,
) -> None:
    """Same combined 2–98% scale on both panels (legacy; GCM often looks flat)."""
    from plot_validation_agg_mean_pr import _save_obs_dor_pair

    _save_obs_dor_pair(out_path, o, g, title_left, title_right, suptitle)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cmip6-hist",
        required=True,
        help="cmip6_inputs_19810101-20141231.dat memmap (same layout as test8)",
    )
    ap.add_argument(
        "--gridmet-targets",
        required=True,
        help="gridmet_targets_19810101-20141231.dat memmap",
    )
    ap.add_argument("--geo-mask", required=True, help="geo_mask.npy (216×192)")
    ap.add_argument(
        "--title-right",
        default="GCM input (OTBC → 4 km)\nmean 2006–2014",
        help="Right panel title (use \\n for newline)",
    )
    ap.add_argument("--out", required=True, help="Output PNG path")
    ap.add_argument(
        "--shared-scale",
        action="store_true",
        help="Use one color scale for both panels (old behavior; GCM often looks washed out)",
    )
    ap.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Figure DPI (default 200 for sharper maps)",
    )
    ap.add_argument(
        "--suptitle",
        default="",
        help="Figure suptitle (default depends on --shared-scale)",
    )
    args = ap.parse_args()

    mask = np.load(args.geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape

    # Memmaps on disk are often flat float32; infer n_days from size (same as test8 layout).
    el_per_day = 6 * H * W
    flat_g = np.memmap(args.gridmet_targets, dtype="float32", mode="r")
    flat_c = np.memmap(args.cmip6_hist, dtype="float32", mode="r")
    if flat_g.size != flat_c.size:
        print(
            f"ERROR: gridmet n_float={flat_g.size} != cmip6 n_float={flat_c.size}",
            file=sys.stderr,
        )
        return 1
    if flat_g.size % el_per_day != 0:
        print(
            f"ERROR: file size {flat_g.size} not divisible by 6*{H}*{W}",
            file=sys.stderr,
        )
        return 1
    n_days = flat_g.size // el_per_day
    mm_g = flat_g.reshape(n_days, 6, H, W)
    mm_c = flat_c.reshape(n_days, 6, H, W)

    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    val_mask = np.asarray(dates > pd.Timestamp("2005-12-31"), dtype=bool)

    obs_pr = np.asarray(mm_g[:, 0, :, :], dtype=np.float64)
    gcm_pr = np.asarray(mm_c[:, 0, :, :], dtype=np.float64)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        o = np.nanmean(obs_pr[val_mask], axis=0)
        g = np.nanmean(gcm_pr[val_mask], axis=0)

    title_right = args.title_right.replace("\\n", "\n")
    out = Path(args.out)
    if args.suptitle:
        suptitle = args.suptitle
    elif args.shared_scale:
        suptitle = (
            "pr — time-mean (obs vs GCM), same color scale 2–98% (combined); "
            "GCM contrast often poor"
        )
    else:
        suptitle = (
            "pr — time-mean (obs vs GCM), independent 2–98% scale per panel "
            "(fair contrast in each)"
        )

    if args.shared_scale:
        _save_obs_gcm_pair_shared(
            out,
            o,
            g,
            "GridMET (target)\nmean 2006–2014",
            title_right,
            suptitle,
        )
    else:
        _save_obs_gcm_pair_independent(
            out,
            o,
            g,
            "GridMET (target)\nmean 2006–2014",
            title_right,
            suptitle,
            dpi=args.dpi,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
