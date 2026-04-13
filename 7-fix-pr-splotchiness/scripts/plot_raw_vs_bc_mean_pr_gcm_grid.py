"""MPI (or other GCM) pr time-mean fields on the **coarse GCM grid** and **4 km GridMET grid**.

``--val-start`` / ``--val-end`` define the averaging window (default 2006–2014 validation).
Outputs pair **GridMET** (left) with **raw GCM**, **OTBC**, or **OTBC bilinear to 4 km** (right),
matching `plot_gridmet_pipeline_side_by_side.py` coarse-bc / regrid sampling.

Optional ``--legacy-combined`` also writes the old two-panel figures: raw | OTBC (coarse) and
raw regridded | OTBC regridded (4 km).
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO = _SCRIPT_DIR.parents[1]  # drops-of-resilience
_BCV = _REPO / "5-bias-correction-validation" / "scripts"
if str(_BCV) not in sys.path:
    sys.path.insert(0, str(_BCV))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_gridmet_pipeline_side_by_side import (
    _fine_to_coarse_bilinear,
    _gridmet_mean_validation,
    _memmap_days_shape,
)

VAR_YLABEL = "Mean pr (mm day⁻¹)"

# Canonical server paths (test8_v2 Regridded_Iowa layout; see dor-info.md)
_DEFAULT_GRIDMET_TARGETS = Path(
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2"
    r"\Regridded_Iowa\gridmet_targets_19810101-20141231.dat"
)
_DEFAULT_GEO_MASK = Path(
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2"
    r"\Regridded_Iowa\geo_mask.npy"
)


def _align_lon_for_interp(
    lon_fine: np.ndarray,
    lon_coarse: np.ndarray,
) -> np.ndarray:
    lon = np.asarray(lon_fine, dtype=np.float64)
    lc = np.asarray(lon_coarse, dtype=np.float64).ravel()
    if np.nanmax(lc) > 180.0 and np.nanmin(lon) < 0.0:
        lon = np.where(lon < 0.0, lon + 360.0, lon)
    return lon


def _coarse_to_fine_bilinear(
    coarse_hw: np.ndarray,
    lat_coarse_1d: np.ndarray,
    lon_coarse_1d: np.ndarray,
    lat_fine_1d: np.ndarray,
    lon_fine_1d: np.ndarray,
) -> np.ndarray:
    """Sample coarse GCM mean field onto fine GridMET lat/lon (bilinear)."""
    from scipy.interpolate import RegularGridInterpolator

    lat = np.asarray(lat_coarse_1d, dtype=np.float64).ravel()
    lon = np.asarray(lon_coarse_1d, dtype=np.float64).ravel()
    fc = np.asarray(coarse_hw, dtype=np.float64)
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
    lf = np.asarray(lat_fine_1d, dtype=np.float64).ravel()
    lof = np.asarray(lon_fine_1d, dtype=np.float64).ravel()
    lon_use = _align_lon_for_interp(lof, lon)
    la2, lo2 = np.meshgrid(lf, lon_use, indexing="ij")
    pts = np.stack([la2, lo2], axis=-1)
    return rgi(pts)


def _patch_cropped_iowa_root(root: Path | None) -> None:
    if root is None:
        return
    import bcv_config as cfg

    cfg.DATA = root
    cfg.BC_DIR = root / "BC"
    cfg.BCPC_DIR = root / "BCPC"
    cfg.RAW_DIR = root / "Raw"
    cfg.OBS_DIR = root / "GridMET"


def _vmin_vmax(a: np.ndarray) -> tuple[float, float]:
    finite = a[np.isfinite(a)].ravel()
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, 2))
    vmax = float(np.percentile(finite, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    return max(0.0, vmin), vmax


def _save_pair_pcolormesh(
    out_path: Path,
    lon2d: np.ndarray,
    lat2d: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    title_left: str,
    title_right: str,
    suptitle: str,
    *,
    dpi: int,
) -> None:
    vmin_l, vmax_l = _vmin_vmax(left)
    vmin_r, vmax_r = _vmin_vmax(right)
    cmap = "Blues"
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    for ax, field, vmin, vmax, title in (
        (axes[0], left, vmin_l, vmax_l, title_left),
        (axes[1], right, vmin_r, vmax_r, title_right),
    ):
        pcm = ax.pcolormesh(
            lon2d,
            lat2d,
            field,
            shading="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(title)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        ax.set_aspect("auto")
        fig.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04, label=VAR_YLABEL)
    fig.suptitle(suptitle, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Cropped_Iowa root (default: bcv_config UNC path)",
    )
    ap.add_argument("--model", default="MPI", help="Short model key (default MPI)")
    ap.add_argument(
        "--method",
        default="mv_otbc",
        help="BC method folder (default mv_otbc — production OTBC)",
    )
    ap.add_argument(
        "--gridmet-targets",
        type=Path,
        default=_DEFAULT_GRIDMET_TARGETS,
        help="gridmet_targets_19810101-20141231.dat memmap",
    )
    ap.add_argument(
        "--geo-mask",
        type=Path,
        default=_DEFAULT_GEO_MASK,
        help="geo_mask.npy (216×192)",
    )
    ap.add_argument("--val-start", default="2006-01-01")
    ap.add_argument("--val-end", default="2014-12-31")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="If set, write 0/1/2 prefixed PNGs here (see README). Overrides default out paths.",
    )
    ap.add_argument(
        "--gridmet-ref-npz",
        type=Path,
        default=None,
        help="4 km reference lat/lon (default: Cropped_pr_2006.npz under GridMET)",
    )
    ap.add_argument(
        "--out-gridmet-coarse-vs-raw",
        type=Path,
        default=None,
        help="Output: GridMET coarse vs raw",
    )
    ap.add_argument(
        "--out-gridmet-coarse-vs-bc",
        type=Path,
        default=None,
        help="Output: GridMET coarse vs OTBC",
    )
    ap.add_argument(
        "--out-gridmet-4km-vs-bc-regridded",
        type=Path,
        default=None,
        help="Output: GridMET 4 km vs OTBC regridded",
    )
    ap.add_argument(
        "--legacy-combined",
        action="store_true",
        help="Also write legacy raw|OTBC coarse and raw|OTBC regridded two-panel PNGs",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Legacy: coarse raw|OTBC (only if --legacy-combined)",
    )
    ap.add_argument(
        "--out-regridded",
        type=Path,
        default=None,
        help="Legacy: regridded raw|OTBC (only if --legacy-combined)",
    )
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    v0 = pd.Timestamp(args.val_start)
    v1 = pd.Timestamp(args.val_end)
    period_tag = f"{v0.year}–{v1.year}"
    _fig_base = (
        _SCRIPT_DIR.parent / "figures" / "pr-splotch-side-by-side" / period_tag
    )
    if args.output_dir is not None:
        od = args.output_dir
        args.out_gridmet_coarse_vs_raw = od / (
            f"0gridmet_coarse_vs_raw_pr_MPI_mean_{period_tag}.png"
        )
        args.out_gridmet_coarse_vs_bc = od / (
            f"1gridmet_coarse_vs_OTBC_pr_MPI_mean_{period_tag}.png"
        )
        args.out_gridmet_4km_vs_bc_regridded = od / (
            f"2gridmet_4km_vs_OTBC_regridded_pr_MPI_mean_{period_tag}.png"
        )
    else:
        if args.out_gridmet_coarse_vs_raw is None:
            args.out_gridmet_coarse_vs_raw = _fig_base / (
                f"0gridmet_coarse_vs_raw_pr_MPI_mean_{period_tag}.png"
            )
        if args.out_gridmet_coarse_vs_bc is None:
            args.out_gridmet_coarse_vs_bc = _fig_base / (
                f"1gridmet_coarse_vs_OTBC_pr_MPI_mean_{period_tag}.png"
            )
        if args.out_gridmet_4km_vs_bc_regridded is None:
            args.out_gridmet_4km_vs_bc_regridded = _fig_base / (
                f"2gridmet_4km_vs_OTBC_regridded_pr_MPI_mean_{period_tag}.png"
            )
    if args.out is None:
        args.out = (
            _SCRIPT_DIR.parent
            / "figures"
            / "pr-splotch-side-by-side"
            / f"bc_MPI_raw_vs_OTBC_coarse_gcm_mean_{period_tag}.png"
        )
    if args.out_regridded is None:
        args.out_regridded = (
            _SCRIPT_DIR.parent
            / "figures"
            / "pr-splotch-side-by-side"
            / f"bc_MPI_raw_vs_OTBC_regridded_4km_mean_{period_tag}.png"
        )

    _patch_cropped_iowa_root(args.data_root)

    import bcv_config as cfg

    gcm_label = cfg.MODEL_RAW_TOKEN.get(args.model, args.model)

    from bcv_io import (
        load_bc_historical,
        load_raw_concat_years,
        normalize_time_days,
        slice_to_date_range,
    )

    Lb = load_bc_historical(args.model, args.method, "pr")
    if Lb is None:
        print("ERROR: BC load failed (path / method / var)", file=sys.stderr)
        return 1
    bdata, btime, lat, lon = Lb
    bd, bt = slice_to_date_range(bdata, btime, args.val_start, args.val_end)
    if bd.size == 0:
        print("ERROR: empty slice for date range", file=sys.stderr)
        return 1

    y0, y1 = v0.year, v1.year
    R = load_raw_concat_years(args.model, "pr", y0, y1)
    if R is None:
        print("ERROR: raw load failed (missing yearly Raw npz?)", file=sys.stderr)
        return 1
    rdata, rtime, _lat2, _lon2 = R
    rt = normalize_time_days(rtime)
    idx = []
    for d in bt:
        w = np.where(rt == d)[0]
        if w.size != 1:
            print(
                f"ERROR: raw time alignment failed for {d} (need 1 match, got {w.size})",
                file=sys.stderr,
            )
            return 1
        idx.append(int(w[0]))
    rd = rdata[idx]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m_raw = np.nanmean(rd, axis=0)
        m_bc = np.nanmean(bd, axis=0)

    la = np.asarray(lat, dtype=float)
    lo = np.asarray(lon, dtype=float)
    if la.ndim == 1 and lo.ndim == 1:
        lon2d_c, lat2d_c = np.meshgrid(lo, la)
    else:
        lon2d_c, lat2d_c = np.asarray(lon, float), np.asarray(lat, float)

    if not args.gridmet_targets.is_file():
        print(f"ERROR: --gridmet-targets not found: {args.gridmet_targets}", file=sys.stderr)
        return 1
    if not args.geo_mask.is_file():
        print(f"ERROR: --geo-mask not found: {args.geo_mask}", file=sys.stderr)
        return 1

    n_days, H, W = _memmap_days_shape(str(args.gridmet_targets), str(args.geo_mask))
    o_fine = _gridmet_mean_validation(
        str(args.gridmet_targets),
        H,
        W,
        n_days,
        args.val_start,
        args.val_end,
    )
    lat_f = None
    lon_f = None
    ref_npz = args.gridmet_ref_npz or (cfg.OBS_DIR / "Cropped_pr_2006.npz")
    if ref_npz.is_file():
        with np.load(ref_npz) as zref:
            lat_f = np.asarray(zref["lat"], dtype=np.float64).ravel()
            lon_f = np.asarray(zref["lon"], dtype=np.float64).ravel()
    else:
        # Infer 1-D lat/lon from mean field shape (fallback)
        print(f"WARN: missing {ref_npz}, using grid shape only for fine mesh", file=sys.stderr)
        # Cannot build mesh without coords — require ref npz
        print("ERROR: need --gridmet-ref-npz or Cropped_pr_2006.npz under GridMET", file=sys.stderr)
        return 1

    la1 = np.asarray(lat, dtype=np.float64).ravel()
    lo1 = np.asarray(lon, dtype=np.float64).ravel()
    o_coarse = _fine_to_coarse_bilinear(o_fine, lat_f, lon_f, la1, lo1)
    rg_bc = _coarse_to_fine_bilinear(m_bc, la1, lo1, lat_f, lon_f)

    lon2df, lat2df = np.meshgrid(lon_f, lat_f)

    _save_pair_pcolormesh(
        args.out_gridmet_coarse_vs_raw,
        lon2d_c,
        lat2d_c,
        o_coarse,
        m_raw,
        f"GridMET (to coarse grid)\nmean {period_tag}",
        f"Before BC (raw)\n{gcm_label}\nmean {period_tag}",
        f"{gcm_label} pr — GridMET vs raw GCM (coarse), independent 2–98% per panel",
        dpi=args.dpi,
    )
    _save_pair_pcolormesh(
        args.out_gridmet_coarse_vs_bc,
        lon2d_c,
        lat2d_c,
        o_coarse,
        m_bc,
        f"GridMET (to coarse grid)\nmean {period_tag}",
        f"After BC ({args.method})\n{gcm_label}\nmean {period_tag}",
        f"{gcm_label} pr — GridMET vs OTBC (coarse), independent 2–98% per panel",
        dpi=args.dpi,
    )
    _save_pair_pcolormesh(
        args.out_gridmet_4km_vs_bc_regridded,
        lon2df,
        lat2df,
        o_fine,
        rg_bc,
        f"GridMET (target)\nmean {period_tag}",
        f"After BC ({args.method})\n{gcm_label}\n4 km grid (bilinear from coarse)",
        f"{gcm_label} pr — GridMET vs OTBC regridded to 4 km, independent 2–98% per panel",
        dpi=args.dpi,
    )

    print(f"  (n_days validation={bd.shape[0]})")

    if not args.legacy_combined:
        return 0

    # --- legacy combined figures ---
    vmin_l, vmax_l = _vmin_vmax(m_raw)
    vmin_r, vmax_r = _vmin_vmax(m_bc)
    cmap = "Blues"
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    for ax, field, vmin, vmax, title in (
        (
            axes[0],
            m_raw,
            vmin_l,
            vmax_l,
            f"Before BC (raw)\n{gcm_label}\nmean {period_tag}",
        ),
        (
            axes[1],
            m_bc,
            vmin_r,
            vmax_r,
            f"After BC ({args.method})\n{gcm_label}\nmean {period_tag}",
        ),
    ):
        pcm = ax.pcolormesh(
            lon2d_c,
            lat2d_c,
            field,
            shading="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(title)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        ax.set_aspect("auto")
        fig.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04, label=VAR_YLABEL)
    fig.suptitle(
        f"{gcm_label} pr — GCM grid (Iowa crop), independent 2–98% scale per panel",
        fontsize=11,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi)
    plt.close(fig)
    print(f"Wrote {args.out}  (legacy combined coarse)")

    rg_raw = _coarse_to_fine_bilinear(m_raw, la1, lo1, lat_f, lon_f)
    vmin_lr, vmax_lr = _vmin_vmax(rg_raw)
    vmin_rr, vmax_rr = _vmin_vmax(rg_bc)
    fig2, axes2 = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    for ax, field, vmin, vmax, title in (
        (
            axes2[0],
            rg_raw,
            vmin_lr,
            vmax_lr,
            f"Before BC (raw)\n{gcm_label}\nmean {period_tag}\n4 km grid (bilinear)",
        ),
        (
            axes2[1],
            rg_bc,
            vmin_rr,
            vmax_rr,
            f"After BC ({args.method})\n{gcm_label}\nmean {period_tag}\n4 km grid (bilinear)",
        ),
    ):
        pcm = ax.pcolormesh(
            lon2df,
            lat2df,
            field,
            shading="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(title)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        ax.set_aspect("auto")
        fig2.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04, label=VAR_YLABEL)
    fig2.suptitle(
        f"{gcm_label} pr — time-mean {period_tag}, coarse field sampled to GridMET lat/lon",
        fontsize=11,
    )
    args.out_regridded.parent.mkdir(parents=True, exist_ok=True)
    fig2.savefig(args.out_regridded, dpi=args.dpi)
    plt.close(fig2)
    print(f"Wrote {args.out_regridded}  (legacy combined regridded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
