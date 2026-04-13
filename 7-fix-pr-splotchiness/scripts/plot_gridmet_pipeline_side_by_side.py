"""
GridMET | *field* side-by-side maps (mean 2006–2014 by default) at successive pipeline stages
**before / around** stochastic downscaling — same visual language as
`plot_validation_agg_mean_pr_obs_vs_gcm.py` (independent 2–98% Blues per panel, two colorbars).

Stages (subcommands):

  coarse-bc   — GridMET (bilinear sample onto **coarse** lat/lon) | **OTBC+physics** `pr` from
                coarse `.npz` (same grid). Needs `--gridmet-ref-npz` with 4 km `lat`/`lon` (e.g.
                `Cropped_pr_2006.npz`).

  regrid-gcm  — GridMET | **cmip6_inputs** on the **4 km** memmap grid (post-`regrid_to_gridmet`,
                pre-test8). Same as the standalone `plot_validation_agg_mean_pr_obs_vs_gcm.py`.

  dor         — GridMET | **DOR** `Stochastic_V8_Hybrid_pr.npz` (or any matching NPZ).

Examples:

  python plot_gridmet_pipeline_side_by_side.py regrid-gcm \\
    --cmip6-hist .../cmip6_inputs_19810101-20141231.dat \\
    --gridmet-targets .../gridmet_targets_19810101-20141231.dat \\
    --geo-mask .../geo_mask.npy \\
    --out .../stage_regrid_gcm.png

  python plot_gridmet_pipeline_side_by_side.py coarse-bc \\
    --coarse-npz .../pr_..._physics_corrected.npz \\
    --gridmet-targets .../gridmet_targets_19810101-20141231.dat \\
    --gridmet-ref-npz .../Cropped_pr_2006.npz \\
    --geo-mask .../geo_mask.npy \\
    --days-origin 1850-01-01 \\
    --out .../stage_coarse_bc.png

  python plot_gridmet_pipeline_side_by_side.py dor \\
    --dor-npz .../Stochastic_V8_Hybrid_pr.npz \\
    --gridmet-targets .../gridmet_targets_19810101-20141231.dat \\
    --geo-mask .../geo_mask.npy \\
    --out .../stage_dor.png
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
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from plot_coarse_gcm_mean_pr import _decode_times, _load_pr_lat_lon_time
from plot_validation_agg_mean_pr_obs_vs_gcm import (
    VAR_YLABEL_PR,
    _save_obs_gcm_pair_independent,
    _save_obs_gcm_pair_shared,
    _vmin_vmax_one,
)


def _mean_period_label(val_start: str, val_end: str) -> str:
    v0 = pd.Timestamp(val_start)
    v1 = pd.Timestamp(val_end)
    return f"{v0.year}–{v1.year}"


def _gridmet_mean_validation(
    gridmet_targets: str,
    H: int,
    W: int,
    n_days: int,
    val_start: str,
    val_end: str,
) -> np.ndarray:
    el_per_day = 6 * H * W
    flat_g = np.memmap(gridmet_targets, dtype="float32", mode="r")
    if flat_g.size != n_days * el_per_day:
        raise ValueError(
            f"gridmet size {flat_g.size} != n_days*{el_per_day} for n_days={n_days}"
        )
    mm_g = flat_g.reshape(n_days, 6, H, W)
    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    v0, v1 = pd.Timestamp(val_start), pd.Timestamp(val_end)
    mask = (dates >= v0) & (dates <= v1)
    obs_pr = np.asarray(mm_g[:, 0, :, :], dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(obs_pr[mask], axis=0)


def _align_lon_for_interp(
    lon_fine: np.ndarray,
    lon_coarse: np.ndarray,
) -> np.ndarray:
    """Map fine longitudes to 0–360° when the coarse grid uses that convention."""
    lon = np.asarray(lon_fine, dtype=np.float64).ravel()
    lc = np.asarray(lon_coarse, dtype=np.float64).ravel()
    if np.nanmax(lc) > 180.0 and np.nanmin(lon) < 0.0:
        lon = np.where(lon < 0.0, lon + 360.0, lon)
    return lon


def _fine_to_coarse_bilinear(
    fine_hw: np.ndarray,
    lat_fine: np.ndarray,
    lon_fine: np.ndarray,
    lat_coarse: np.ndarray,
    lon_coarse: np.ndarray,
) -> np.ndarray:
    """Sample fine field onto coarse lat/lon (for side-by-side on coarse grid)."""
    lat = np.asarray(lat_fine, dtype=np.float64).ravel()
    lon = _align_lon_for_interp(lon_fine, lon_coarse)
    fc = np.asarray(fine_hw, dtype=np.float64)
    if lat[0] > lat[-1]:
        lat = lat[::-1]
        fc = fc[::-1, :]
    if lon[0] > lon[-1]:
        lon = lon[::-1]
        fc = fc[:, ::-1]
    rgi = RegularGridInterpolator(
        (lat, lon),
        fc,
        bounds_error=False,
        fill_value=np.nan,
        method="linear",
    )
    la2, lo2 = np.meshgrid(
        np.asarray(lat_coarse, dtype=np.float64),
        np.asarray(lon_coarse, dtype=np.float64),
        indexing="ij",
    )
    pts = np.stack([la2, lo2], axis=-1)
    return rgi(pts)


def _save_pair_pcolormesh_same_grid(
    out_path: Path,
    lat1d: np.ndarray,
    lon1d: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    title_left: str,
    title_right: str,
    suptitle: str,
    *,
    dpi: int = 200,
) -> None:
    lon2d, lat2d = np.meshgrid(lon1d, lat1d)
    vmin_l, vmax_l = _vmin_vmax_one(left)
    vmin_r, vmax_r = _vmin_vmax_one(right)
    cmap = "Blues"
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    p0 = axes[0].pcolormesh(
        lon2d,
        lat2d,
        left,
        shading="auto",
        cmap=cmap,
        vmin=vmin_l,
        vmax=vmax_l,
    )
    axes[0].set_title(title_left)
    axes[0].set_xlabel("Longitude (°)")
    axes[0].set_ylabel("Latitude (°)")
    axes[0].set_aspect("auto")
    fig.colorbar(p0, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)

    p1 = axes[1].pcolormesh(
        lon2d,
        lat2d,
        right,
        shading="auto",
        cmap=cmap,
        vmin=vmin_r,
        vmax=vmax_r,
    )
    axes[1].set_title(title_right)
    axes[1].set_xlabel("Longitude (°)")
    axes[1].set_ylabel("Latitude (°)")
    axes[1].set_aspect("auto")
    fig.colorbar(p1, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
    fig.suptitle(suptitle, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    print(f"Wrote {out_path}")


def _memmap_days_shape(gridmet_path: str, geo_mask: str) -> tuple[int, int, int]:
    mask = np.load(geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape
    el = 6 * H * W
    flat = np.memmap(gridmet_path, dtype="float32", mode="r")
    if flat.size % el != 0:
        raise ValueError("gridmet file size incompatible with mask shape")
    n_days = flat.size // el
    return n_days, H, W


# --- subcommands ---

def cmd_coarse_bc(ns: argparse.Namespace) -> int:
    mask = np.load(ns.geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape
    n_days, H2, W2 = _memmap_days_shape(ns.gridmet_targets, ns.geo_mask)
    if (H2, W2) != (H, W):
        print("ERROR: geo_mask shape mismatch vs gridmet", file=sys.stderr)
        return 1

    zref = np.load(ns.gridmet_ref_npz)
    lat_f = np.asarray(zref["lat"], dtype=np.float64).ravel()
    lon_f = np.asarray(zref["lon"], dtype=np.float64).ravel()
    zref.close()

    o_fine = _gridmet_mean_validation(
        ns.gridmet_targets, H, W, n_days, ns.val_start, ns.val_end
    )

    pr, lat_c, lon_c, time_raw, _vkey = _load_pr_lat_lon_time(Path(ns.coarse_npz))
    dates = _decode_times(
        pr.shape[0],
        time_raw,
        days_origin=ns.days_origin,
        assume_daily_origin=(ns.assume_daily_origin or "").strip(),
    )
    v0, v1 = pd.Timestamp(ns.val_start), pd.Timestamp(ns.val_end)
    tmask = (dates >= v0) & (dates <= v1)
    if not np.any(tmask):
        print("ERROR: no coarse times in validation window", file=sys.stderr)
        return 1
    if len(dates) != pr.shape[0]:
        print(
            f"ERROR: time axis length {len(dates)} != pr.shape[0]={pr.shape[0]}",
            file=sys.stderr,
        )
        return 1
    # All-NaN coarse cells (e.g. ocean padding) trigger RuntimeWarning: Mean of empty slice
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gcm_coarse = np.nanmean(pr[tmask], axis=0)

    o_coarse = _fine_to_coarse_bilinear(o_fine, lat_f, lon_f, lat_c, lon_c)

    _mp = _mean_period_label(ns.val_start, ns.val_end)
    title_left = f"GridMET (to coarse grid)\nmean {_mp}"
    title_right = (ns.title_right or f"GCM OTBC+physics (coarse)\nmean {_mp}").replace(
        "\\n", "\n"
    )
    suptitle = ns.suptitle or (
        "pr — coarse BC stage (GridMET sampled to GCM lat/lon vs coarse pr)"
    )
    _save_pair_pcolormesh_same_grid(
        Path(ns.out),
        lat_c,
        lon_c,
        o_coarse,
        gcm_coarse,
        title_left,
        title_right,
        suptitle,
        dpi=ns.dpi,
    )
    return 0


def cmd_regrid_gcm(ns: argparse.Namespace) -> int:
    mask = np.load(ns.geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape
    el_per_day = 6 * H * W
    flat_g = np.memmap(ns.gridmet_targets, dtype="float32", mode="r")
    flat_c = np.memmap(ns.cmip6_hist, dtype="float32", mode="r")
    if flat_g.size != flat_c.size or flat_g.size % el_per_day != 0:
        print("ERROR: memmap size mismatch", file=sys.stderr)
        return 1
    n_days = flat_g.size // el_per_day
    mm_g = flat_g.reshape(n_days, 6, H, W)
    mm_c = flat_c.reshape(n_days, 6, H, W)
    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    v0, v1 = pd.Timestamp(ns.val_start), pd.Timestamp(ns.val_end)
    val_mask = (dates >= v0) & (dates <= v1)
    obs_pr = np.asarray(mm_g[:, 0, :, :], dtype=np.float64)
    gcm_pr = np.asarray(mm_c[:, 0, :, :], dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        o = np.nanmean(obs_pr[val_mask], axis=0)
        g = np.nanmean(gcm_pr[val_mask], axis=0)

    _mp = _mean_period_label(ns.val_start, ns.val_end)
    tl = f"GridMET (target)\nmean {_mp}"
    tr = (ns.title_right or f"GCM (OTBC → 4 km)\nmean {_mp}").replace("\\n", "\n")
    st = ns.suptitle or "pr — after regrid_to_gridmet (drivers on 4 km grid)"
    if ns.shared_scale:
        _save_obs_gcm_pair_shared(Path(ns.out), o, g, tl, tr, st)
    else:
        _save_obs_gcm_pair_independent(Path(ns.out), o, g, tl, tr, st, dpi=ns.dpi)
    return 0


def cmd_dor(ns: argparse.Namespace) -> int:
    mask = np.load(ns.geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    H, W = mask.shape
    z = np.load(ns.dor_npz)
    dor = np.asarray(z["data"], dtype=np.float64)
    z.close()
    if dor.shape[1:] != (H, W):
        print("ERROR: DOR grid mismatch", file=sys.stderr)
        return 1
    n_days = dor.shape[0]
    n_days_g, H2, W2 = _memmap_days_shape(ns.gridmet_targets, ns.geo_mask)
    if n_days_g != n_days:
        print(
            f"WARN: day count gridmet {n_days_g} vs DOR {n_days} — using min length",
            file=sys.stderr,
        )
    n_use = min(n_days, n_days_g)
    flat_g = np.memmap(ns.gridmet_targets, dtype="float32", mode="r")
    mm_g = flat_g.reshape(n_days_g, 6, H, W)
    dates = pd.date_range("1981-01-01", periods=n_use, freq="D")
    v0, v1 = pd.Timestamp(ns.val_start), pd.Timestamp(ns.val_end)
    val_mask = (dates >= v0) & (dates <= v1)
    obs_pr = np.asarray(mm_g[:n_use, 0, :, :], dtype=np.float64)
    dor_u = dor[:n_use]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        o = np.nanmean(obs_pr[val_mask], axis=0)
        d = np.nanmean(dor_u[val_mask], axis=0)

    _mp = _mean_period_label(ns.val_start, ns.val_end)
    tl = f"GridMET (target)\nmean {_mp}"
    tr = (ns.title_right or f"DOR\nmean {_mp}").replace("\\n", "\n")
    st = ns.suptitle or "pr — after test8 downscale + Schaake"
    if ns.shared_scale:
        from plot_validation_agg_mean_pr import _save_obs_dor_pair

        _save_obs_dor_pair(Path(ns.out), o, d, tl, tr, st)
    else:
        _save_obs_gcm_pair_independent(Path(ns.out), o, d, tl, tr, st, dpi=ns.dpi)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="stage", required=True)

    def add_common_val(p):
        p.add_argument("--gridmet-targets", required=True)
        p.add_argument("--geo-mask", required=True)
        p.add_argument("--out", required=True, type=Path)
        p.add_argument("--val-start", default="2006-01-01")
        p.add_argument("--val-end", default="2014-12-31")
        p.add_argument("--dpi", type=int, default=200)
        p.add_argument("--title-right", default="", help="Right panel title")
        p.add_argument("--suptitle", default="")

    p0 = sub.add_parser("coarse-bc", help="Coarse OTBC NPZ vs GridMET on coarse lat/lon")
    add_common_val(p0)
    p0.add_argument("--coarse-npz", required=True, help="Physics-corrected coarse pr .npz")
    p0.add_argument(
        "--gridmet-ref-npz",
        required=True,
        help="4 km reference with lat/lon (e.g. Cropped_pr_2006.npz)",
    )
    p0.add_argument("--days-origin", default="1850-01-01")
    p0.add_argument("--assume-daily-origin", default="")

    p1 = sub.add_parser("regrid-gcm", help="4 km cmip6_inputs vs GridMET memmaps")
    add_common_val(p1)
    p1.add_argument("--cmip6-hist", required=True)
    p1.add_argument(
        "--shared-scale",
        action="store_true",
        help="Single color scale (often washes out GCM)",
    )

    p2 = sub.add_parser("dor", help="DOR Stochastic_V8_Hybrid_pr.npz vs GridMET")
    add_common_val(p2)
    p2.add_argument("--dor-npz", required=True)
    p2.add_argument(
        "--shared-scale",
        action="store_true",
        help="One scale for both panels (like plot_validation_agg_mean_pr)",
    )

    ns = ap.parse_args()
    if ns.stage == "coarse-bc":
        return cmd_coarse_bc(ns)
    if ns.stage == "regrid-gcm":
        return cmd_regrid_gcm(ns)
    if ns.stage == "dor":
        return cmd_dor(ns)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
