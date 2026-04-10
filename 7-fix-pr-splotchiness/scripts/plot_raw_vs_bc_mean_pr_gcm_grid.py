"""Raw MPI pr | OTBC pr on the **coarse GCM grid**, time-mean 2006–2014 (before BC vs after BC).

Also writes a second figure: same means **bilinearly regridded** to the 4 km GridMET lat/lon
(like `regrid_to_gridmet` sampling), for side-by-side comparison on the fine grid.
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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RegularGridInterpolator

VAR_YLABEL = "Mean pr (mm day⁻¹)"


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
        "--out",
        type=Path,
        default=_SCRIPT_DIR.parent
        / "figures"
        / "pr-splotch-side-by-side"
        / "bc_MPI_raw_vs_OTBC_coarse_gcm_mean_2006-2014.png",
    )
    ap.add_argument(
        "--out-regridded",
        type=Path,
        default=_SCRIPT_DIR.parent
        / "figures"
        / "pr-splotch-side-by-side"
        / "bc_MPI_raw_vs_OTBC_regridded_4km_mean_2006-2014.png",
        help="Second PNG: coarse means bilinearly sampled to GridMET lat/lon",
    )
    ap.add_argument(
        "--gridmet-ref-npz",
        type=Path,
        default=None,
        help="4 km reference lat/lon (default: Cropped_pr_2006.npz under GridMET)",
    )
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    _patch_cropped_iowa_root(args.data_root)

    import bcv_config as cfg

    gcm_label = cfg.MODEL_RAW_TOKEN.get(args.model, args.model)

    from bcv_io import (
        load_bc_historical,
        load_raw_concat,
        normalize_time_days,
        slice_to_bc_validation,
    )

    Lb = load_bc_historical(args.model, args.method, "pr")
    if Lb is None:
        print("ERROR: BC load failed (path / method / var)", file=sys.stderr)
        return 1
    bdata, btime, lat, lon = Lb
    bd, bt = slice_to_bc_validation(bdata, btime)
    if bd.size == 0:
        print("ERROR: empty BC validation slice", file=sys.stderr)
        return 1

    R = load_raw_concat(args.model, "pr")
    if R is None:
        print("ERROR: raw load failed (missing yearly Raw npz?)", file=sys.stderr)
        return 1
    rdata, rtime, lat2, lon2 = R
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
        lon2d, lat2d = np.meshgrid(lo, la)
    else:
        lon2d, lat2d = np.asarray(lon, float), np.asarray(lat, float)

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
            f"Before BC (raw)\n{gcm_label}\nmean 2006–2014",
        ),
        (
            axes[1],
            m_bc,
            vmin_r,
            vmax_r,
            f"After BC ({args.method})\n{gcm_label}\nmean 2006–2014",
        ),
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

    fig.suptitle(
        f"{gcm_label} pr — GCM grid (Iowa crop), independent 2–98% scale per panel",
        fontsize=11,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi)
    plt.close(fig)
    print(f"Wrote {args.out}  (n_days={bd.shape[0]})")

    ref_npz = args.gridmet_ref_npz or (cfg.OBS_DIR / "Cropped_pr_2006.npz")
    if not ref_npz.is_file():
        print(f"WARN: skip regridded figure — missing {ref_npz}", file=sys.stderr)
        return 0

    with np.load(ref_npz) as zref:
        lat_f = np.asarray(zref["lat"], dtype=np.float64).ravel()
        lon_f = np.asarray(zref["lon"], dtype=np.float64).ravel()

    la1 = np.asarray(lat, dtype=np.float64).ravel()
    lo1 = np.asarray(lon, dtype=np.float64).ravel()
    rg_raw = _coarse_to_fine_bilinear(m_raw, la1, lo1, lat_f, lon_f)
    rg_bc = _coarse_to_fine_bilinear(m_bc, la1, lo1, lat_f, lon_f)

    lon2df, lat2df = np.meshgrid(lon_f, lat_f)
    vmin_lr, vmax_lr = _vmin_vmax(rg_raw)
    vmin_rr, vmax_rr = _vmin_vmax(rg_bc)

    fig2, axes2 = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    for ax, field, vmin, vmax, title in (
        (
            axes2[0],
            rg_raw,
            vmin_lr,
            vmax_lr,
            f"Before BC (raw)\n{gcm_label}\n4 km grid (bilinear)",
        ),
        (
            axes2[1],
            rg_bc,
            vmin_rr,
            vmax_rr,
            f"After BC ({args.method})\n{gcm_label}\n4 km grid (bilinear)",
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
        f"{gcm_label} pr — time-mean 2006–2014, coarse field sampled to GridMET lat/lon",
        fontsize=11,
    )
    args.out_regridded.parent.mkdir(parents=True, exist_ok=True)
    fig2.savefig(args.out_regridded, dpi=args.dpi)
    plt.close(fig2)
    print(f"Wrote {args.out_regridded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
