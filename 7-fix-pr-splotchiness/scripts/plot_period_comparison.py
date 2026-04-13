"""
Regenerate 12 PR time-mean comparison plots (3 periods x 4 stages).

Color scale: same convention as pipeline / `plot_validation_agg_mean_pr_obs_vs_gcm.py`:
**independent** 2–98% Blues stretch per panel (two colorbars per figure).

See PLAN-REDO-PERIOD-PLOTS.md. Server memmaps for 4 km; Cropped_Iowa Raw + BCPC coarse.
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
from scipy.interpolate import RegularGridInterpolator

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO = _SCRIPT_DIR.parents[1]
_BCV = _REPO / "5-bias-correction-validation" / "scripts"
if str(_BCV) not in sys.path:
    sys.path.insert(0, str(_BCV))

from bcv_io import (  # noqa: E402
    load_raw_concat_years,
    normalize_time_days,
    slice_to_date_range,
)

if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from plot_gridmet_pipeline_side_by_side import _fine_to_coarse_bilinear  # noqa: E402
from plot_validation_agg_mean_pr_obs_vs_gcm import (  # noqa: E402
    VAR_YLABEL_PR,
    _vmin_vmax_one,
)

SERVER = r"\\abe-cylo\modelsdev\Projects\WRC_DOR"
GRIDMET_TARGETS = (
    Path(SERVER)
    / "Spatial_Downscaling/test8_v2/Regridded_Iowa/gridmet_targets_19810101-20141231.dat"
)
CMIP6_INPUTS = (
    Path(SERVER)
    / "Spatial_Downscaling/test8_v2/Regridded_Iowa/MPI/mv_otbc/cmip6_inputs_19810101-20141231.dat"
)
GEO_MASK = Path(SERVER) / "Spatial_Downscaling/test8_v2/Regridded_Iowa/geo_mask.npy"
DOR_NPZ = (
    Path(SERVER)
    / "Spatial_Downscaling/test8_v2/Iowa_Downscaled/v8_2/Stochastic_V8_Hybrid_pr.npz"
)
BCPC_PR = (
    Path(SERVER)
    / "Data/Cropped_Iowa/BCPC/MPI/mv_otbc/"
    / "Cropped_pr_GROUP-huss-pr-rsds-tasmax-tasmin-wind_METHOD-mv_otbc_historical_18500101-20141231_physics_corrected.npz"
)
GRIDMET_REF = Path(SERVER) / "Data/Cropped_Iowa/GridMET/Cropped_pr_2006.npz"

PERIODS = (
    ("1981-2005", "1981-01-01", "2005-12-31", 9131),
    ("1981-2014", "1981-01-01", "2014-12-31", 12418),
    ("2006-2014", "2006-01-01", "2014-12-31", 3287),
)


def _gridmet_mean_from_memmap(
    gridmet_path: Path,
    H: int,
    W: int,
    n_days: int,
    val_start: str,
    val_end: str,
) -> np.ndarray:
    el = 6 * H * W
    flat = np.memmap(gridmet_path, dtype="float32", mode="r")
    mm = flat.reshape(n_days, 6, H, W)
    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    v0, v1 = pd.Timestamp(val_start), pd.Timestamp(val_end)
    tmask = (dates >= v0) & (dates <= v1)
    obs = np.asarray(mm[:, 0, :, :], dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(obs[tmask], axis=0)


def _cmip6_mean_from_memmap(
    cmip6_path: Path,
    H: int,
    W: int,
    n_days: int,
    val_start: str,
    val_end: str,
) -> np.ndarray:
    el = 6 * H * W
    flat = np.memmap(cmip6_path, dtype="float32", mode="r")
    mm = flat.reshape(n_days, 6, H, W)
    dates = pd.date_range("1981-01-01", periods=n_days, freq="D")
    v0, v1 = pd.Timestamp(val_start), pd.Timestamp(val_end)
    tmask = (dates >= v0) & (dates <= v1)
    gcm = np.asarray(mm[:, 0, :, :], dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(gcm[tmask], axis=0)


def _dor_mean_from_npz(
    dor_path: Path,
    n_expect: int,
    val_start: str,
    val_end: str,
) -> np.ndarray:
    z = np.load(dor_path)
    dor = np.asarray(z["data"], dtype=np.float64)
    z.close()
    n_days = dor.shape[0]
    n_use = min(n_days, n_expect)
    dates = pd.date_range("1981-01-01", periods=n_use, freq="D")
    v0, v1 = pd.Timestamp(val_start), pd.Timestamp(val_end)
    tmask = (dates >= v0) & (dates <= v1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(dor[tmask, :, :], axis=0)


def _apply_geo_mask(field: np.ndarray, geo: np.ndarray) -> np.ndarray:
    m = geo.astype(bool) if geo.dtype != bool else geo
    out = np.asarray(field, dtype=np.float64).copy()
    out[~m] = np.nan
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-root",
        type=Path,
        default=_SCRIPT_DIR.parent / "figures" / "period-comparison",
        help="Output root (creates 1981-2005/, 1981-2014/, 2006-2014/)",
    )
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    for p in (GRIDMET_TARGETS, CMIP6_INPUTS, GEO_MASK, DOR_NPZ, BCPC_PR, GRIDMET_REF):
        if not p.is_file():
            print(f"ERROR: missing {p}", file=sys.stderr)
            return 1

    geo = np.load(GEO_MASK)
    if geo.ndim != 2:
        geo = geo.reshape(geo.shape[-2], geo.shape[-1])
    H, W = geo.shape

    dates = pd.date_range("1981-01-01", periods=12418, freq="D")
    checks = (
        ((dates >= "1981-01-01") & (dates <= "2005-12-31"), 9131),
        ((dates >= "1981-01-01") & (dates <= "2014-12-31"), 12418),
        ((dates >= "2006-01-01") & (dates <= "2014-12-31"), 3287),
    )
    for msk, nexp in checks:
        n = int(msk.sum())
        print(f"Date mask count: {n} (expected {nexp})")
        if n != nexp:
            print("ERROR: day count mismatch — abort.", file=sys.stderr)
            return 1

    el = 6 * H * W
    flat_g = np.memmap(GRIDMET_TARGETS, dtype="float32", mode="r")
    if flat_g.size != 12418 * el:
        print("ERROR: gridmet memmap size", flat_g.size, file=sys.stderr)
        return 1

    # --- load BCPC (OTBC + physics) and Raw for coarse means ---
    zbc = np.load(BCPC_PR)
    bdata_full = np.asarray(zbc["data"], dtype=np.float64)
    btime_full = zbc["time"]
    zbc.close()

    Rfull = load_raw_concat_years("MPI", "pr", 1981, 2014)
    if Rfull is None:
        print("ERROR: raw concat 1981-2014 failed", file=sys.stderr)
        return 1
    rdata_full, rtime_full, lat_c, lon_c = Rfull
    rtime_full = normalize_time_days(rtime_full)

    with np.load(GRIDMET_REF) as zref:
        lat_f = np.asarray(zref["lat"], dtype=np.float64).ravel()
        lon_f = np.asarray(zref["lon"], dtype=np.float64).ravel()

    la_c = np.asarray(lat_c, dtype=np.float64).ravel()
    lo_c = np.asarray(lon_c, dtype=np.float64).ravel()
    lon2d, lat2d = np.meshgrid(lo_c, la_c)

    # --- 4 km means for scale + plot 2 / 3 ---
    gm_4k: dict[str, np.ndarray] = {}
    cm_4k: dict[str, np.ndarray] = {}
    dor_m: dict[str, np.ndarray] = {}

    for tag, vs, ve, _ in PERIODS:
        gm_4k[tag] = _apply_geo_mask(
            _gridmet_mean_from_memmap(GRIDMET_TARGETS, H, W, 12418, vs, ve),
            geo,
        )
        cm_4k[tag] = _apply_geo_mask(
            _cmip6_mean_from_memmap(CMIP6_INPUTS, H, W, 12418, vs, ve),
            geo,
        )
        dor_m[tag] = _apply_geo_mask(
            _dor_mean_from_npz(DOR_NPZ, 12418, vs, ve),
            geo,
        )

    # Coarse means per period
    coarse_gm: dict[str, np.ndarray] = {}
    coarse_raw: dict[str, np.ndarray] = {}
    coarse_bc: dict[str, np.ndarray] = {}

    for tag, vs, ve, _ in PERIODS:
        gm_f = _gridmet_mean_from_memmap(GRIDMET_TARGETS, H, W, 12418, vs, ve)
        coarse_gm[tag] = _fine_to_coarse_bilinear(gm_f, lat_f, lon_f, la_c, lo_c)

        rd, rt = slice_to_date_range(rdata_full, rtime_full, vs, ve)
        bd, _bt = slice_to_date_range(bdata_full, btime_full, vs, ve)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            coarse_raw[tag] = np.nanmean(rd, axis=0)
            coarse_bc[tag] = np.nanmean(bd, axis=0)

    # Domain means for verification (4 km GridMET + DOR)
    print("\nDomain-mean pr (4 km, masked land):")
    for tag, _, _, _ in PERIODS:
        g = gm_4k[tag]
        d = dor_m[tag]
        gm_dm = float(np.nanmean(g))
        dor_dm = float(np.nanmean(d))
        print(f"  {tag}  GridMET={gm_dm:.6f} mm/d   DOR={dor_dm:.6f} mm/d")

    dmeans = [float(np.nanmean(dor_m[t])) for t, _, _, _ in PERIODS]
    if max(dmeans) - min(dmeans) < 0.001:
        print(
            "ERROR: DOR domain means too close — check slicing.",
            file=sys.stderr,
        )
        return 1

    cmap = plt.get_cmap("Blues")

    out_root: Path = args.out_root
    out_root.mkdir(parents=True, exist_ok=True)

    for tag, vs, ve, _ in PERIODS:
        sub = out_root / tag
        sub.mkdir(parents=True, exist_ok=True)
        a, b = tag.split("-", 1)
        title_ym = f"{a}–{b}"

        # 0 coarse raw
        g0 = coarse_gm[tag]
        r0 = coarse_raw[tag]
        vl0, vh0 = _vmin_vmax_one(g0)
        vr0, vrh0 = _vmin_vmax_one(r0)
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
        p00 = axes[0].pcolormesh(
            lon2d,
            lat2d,
            g0,
            shading="auto",
            cmap=cmap,
            vmin=vl0,
            vmax=vh0,
        )
        axes[0].set_title(f"GridMET (target)\nmean {title_ym}")
        axes[0].set_xlabel("Longitude (°)")
        axes[0].set_ylabel("Latitude (°)")
        axes[0].set_aspect("auto")
        p01 = axes[1].pcolormesh(
            lon2d,
            lat2d,
            r0,
            shading="auto",
            cmap=cmap,
            vmin=vr0,
            vmax=vrh0,
        )
        axes[1].set_title(f"MPI-ESM1-2-HR (raw)\nmean {title_ym}")
        axes[1].set_xlabel("Longitude (°)")
        axes[1].set_ylabel("Latitude (°)")
        axes[1].set_aspect("auto")
        fig.suptitle(f"pr time-mean (2-98% per panel)\n{title_ym}")
        fig.colorbar(p00, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        fig.colorbar(p01, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        path_out = sub / "0_coarse_raw.png"
        fig.savefig(path_out, dpi=args.dpi)
        plt.close(fig)
        print(f"Wrote {path_out}")

        # 1 coarse OTBC+phys
        g1 = coarse_gm[tag]
        b1 = coarse_bc[tag]
        vl1, vh1 = _vmin_vmax_one(g1)
        vb1, vbh1 = _vmin_vmax_one(b1)
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
        p10 = axes[0].pcolormesh(
            lon2d,
            lat2d,
            g1,
            shading="auto",
            cmap=cmap,
            vmin=vl1,
            vmax=vh1,
        )
        axes[0].set_title(f"GridMET (target)\nmean {title_ym}")
        axes[0].set_xlabel("Longitude (°)")
        axes[0].set_ylabel("Latitude (°)")
        axes[0].set_aspect("auto")
        p11 = axes[1].pcolormesh(
            lon2d,
            lat2d,
            b1,
            shading="auto",
            cmap=cmap,
            vmin=vb1,
            vmax=vbh1,
        )
        axes[1].set_title(f"MPI-ESM1-2-HR (OTBC+phys)\nmean {title_ym}")
        axes[1].set_xlabel("Longitude (°)")
        axes[1].set_ylabel("Latitude (°)")
        axes[1].set_aspect("auto")
        fig.suptitle(f"pr time-mean (2-98% per panel)\n{title_ym}")
        fig.colorbar(p10, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        fig.colorbar(p11, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        p1 = sub / "1_coarse_otbc.png"
        fig.savefig(p1, dpi=args.dpi)
        plt.close(fig)
        print(f"Wrote {p1}")

        # 2 regridded 4km
        g2 = gm_4k[tag]
        c2 = cm_4k[tag]
        vl2, vh2 = _vmin_vmax_one(g2)
        vc2, vch2 = _vmin_vmax_one(c2)
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
        im20 = axes[0].imshow(
            g2,
            origin="upper",
            cmap=cmap,
            vmin=vl2,
            vmax=vh2,
            aspect="auto",
        )
        axes[0].set_title(f"GridMET (target)\nmean {title_ym}")
        axes[0].set_xticks([])
        axes[0].set_yticks([])
        im21 = axes[1].imshow(
            c2,
            origin="upper",
            cmap=cmap,
            vmin=vc2,
            vmax=vch2,
            aspect="auto",
        )
        axes[1].set_title(f"MPI-ESM1-2-HR (OTBC to 4km)\nmean {title_ym}")
        axes[1].set_xticks([])
        axes[1].set_yticks([])
        fig.suptitle(f"pr time-mean (2-98% per panel)\n{title_ym}")
        fig.colorbar(im20, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        fig.colorbar(im21, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        p2 = sub / "2_regridded_4km.png"
        fig.savefig(p2, dpi=args.dpi)
        plt.close(fig)
        print(f"Wrote {p2}")

        # 3 DOR
        g3 = gm_4k[tag]
        d3 = dor_m[tag]
        vl3, vh3 = _vmin_vmax_one(g3)
        vd3, vdh3 = _vmin_vmax_one(d3)
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
        im30 = axes[0].imshow(
            g3,
            origin="upper",
            cmap=cmap,
            vmin=vl3,
            vmax=vh3,
            aspect="auto",
        )
        axes[0].set_title(f"GridMET (target)\nmean {title_ym}")
        axes[0].set_xticks([])
        axes[0].set_yticks([])
        im31 = axes[1].imshow(
            d3,
            origin="upper",
            cmap=cmap,
            vmin=vd3,
            vmax=vdh3,
            aspect="auto",
        )
        axes[1].set_title(f"DOR (Bhuwan v8_2)\nmean {title_ym}")
        axes[1].set_xticks([])
        axes[1].set_yticks([])
        fig.suptitle(f"pr time-mean (2-98% per panel)\n{title_ym}")
        fig.colorbar(im30, ax=axes[0], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        fig.colorbar(im31, ax=axes[1], fraction=0.046, pad=0.04, label=VAR_YLABEL_PR)
        p3 = sub / "3_dor_output.png"
        fig.savefig(p3, dpi=args.dpi)
        plt.close(fig)
        print(f"Wrote {p3}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
