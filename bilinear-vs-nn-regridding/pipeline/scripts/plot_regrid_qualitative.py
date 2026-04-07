"""
Qualitative maps: bilinear vs nearest-neighbor regridding vs GridMET (MPI OTBC, Iowa).

Reads from WRC_DOR Data share (no local copy required). Excludes precipitation
(local bilinear pr matches both paths; pr_3way is a separate comparison).

Usage (from repo root, with network path to \\\\abe-cylo\\... reachable):
  python bilinear-vs-nn-regridding/pipeline/scripts/plot_regrid_qualitative.py

Env:
  DOR_SERVER_DATA  — override root (default: \\\\abe-cylo\\modelsdev\\Projects\\WRC_DOR\\Data)
  DOR_PLOT_OUT     — output directory for PNG/HTML (default: bilinear-vs-nn-regridding/qualitative_plots)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import xarray_regrid  # noqa: F401 — registers .regrid accessor

# -----------------------------------------------------------------------------
# Paths & naming (match server layout March 2026)
# -----------------------------------------------------------------------------
DEFAULT_SERVER = r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Data"
HIST_SUFFIX = (
    "GROUP-huss-pr-rsds-tasmax-tasmin-wind_METHOD-mv_otbc_historical_18500101-20141231_physics_corrected"
)

# CMIP internal name -> GridMET cropped npz stem (Cropped_{stem}_{year}.npz)
CMIP_TO_GRIDMET = {
    "tasmax": "tmmx",
    "tasmin": "tmmn",
    "rsds": "srad",
    "wind": "vs",
    "huss": "sph",
}

# Bilinear pipeline uses bilinear pr too — we still skip pr here (focus on tas/wind/huss maps).
NON_PR_VARS = ("tasmax", "tasmin", "rsds", "wind", "huss")

CMIP_START = pd.Timestamp("1850-01-01")


def _server_root() -> Path:
    return Path(os.environ.get("DOR_SERVER_DATA", DEFAULT_SERVER))


def regridded_hist_path(root: Path, cmip_var: str) -> Path:
    return (
        root
        / "Regridded_Iowa"
        / "MPI"
        / "mv_otbc"
        / f"Regridded_Cropped_{cmip_var}_{HIST_SUFFIX}.npz"
    )


def coarse_bc_path(root: Path, cmip_var: str) -> Path:
    return (
        root
        / "Cropped_Iowa"
        / "BCPC"
        / "MPI"
        / "mv_otbc"
        / f"Cropped_{cmip_var}_{HIST_SUFFIX}.npz"
    )


def gridmet_path(root: Path, gridmet_stem: str, year: int) -> Path:
    return root / "Cropped_Iowa" / "GridMET" / f"Cropped_{gridmet_stem}_{year}.npz"


def geo_mask_path(root: Path) -> Path:
    return root / "Regridded_Iowa" / "geo_mask.npy"


def day_index_since_1850(date: pd.Timestamp) -> int:
    return int((date.normalize() - CMIP_START).days)


def day_of_year_index(date: pd.Timestamp) -> int:
    """0-based index into GridMET annual stack (len 365 or 366)."""
    return int(date.dayofyear - 1)


def load_npz_2d_field(path: Path, key: str = "data") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path) as z:
        data = np.asarray(z[key], dtype=np.float64)
        lat = np.asarray(z["lat"], dtype=np.float64)
        lon = np.asarray(z["lon"], dtype=np.float64)
    return data, lat, lon


def coarse_to_dataarray(
    cube: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    cmip_var: str,
    time_idx: int | None = None,
) -> xr.DataArray:
    """Build (lat,lon) or (time,lat,lon) DataArray; lon -> [-180, 180]."""
    lon = np.where(lon > 180, lon - 360, lon)
    if time_idx is not None:
        block = cube[time_idx : time_idx + 1]
        return xr.DataArray(
            block,
            dims=("time", "lat", "lon"),
            coords={
                "time": np.array([time_idx], dtype=np.int64),
                "lat": lat,
                "lon": lon,
            },
            name=cmip_var,
        )
    return xr.DataArray(
        cube,
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},
        name=cmip_var,
    )


def destination_grid(lat: np.ndarray, lon: np.ndarray) -> xr.Dataset:
    return xr.Dataset(coords={"lat": (("lat",), lat), "lon": (("lon",), lon)})


def regrid_slice(da: xr.DataArray, dst: xr.Dataset, method: str) -> np.ndarray:
    if method == "conservative":
        out = da.regrid.conservative(dst, latitude_coord="lat")
    elif method == "nearest":
        out = da.regrid.nearest(dst)
    else:
        out = da.regrid.linear(dst)
    return np.asarray(out.values.squeeze(), dtype=np.float64)


def nn_regrid_to_obs_grid(
    cube: np.ndarray,
    clat: np.ndarray,
    clon: np.ndarray,
    cmip_var: str,
    day_i: int,
    olat: np.ndarray,
    olon: np.ndarray,
) -> np.ndarray:
    """One time slice: coarse OTBC → 4 km nearest-neighbor on GridMET lat/lon."""
    da1 = coarse_to_dataarray(cube, clat, clon, cmip_var, time_idx=day_i)
    lat_r = (
        olat[::-1]
        if (olat.ndim == 1 and olat.size > 1 and olat[0] > olat[-1])
        else olat
    )
    dst = destination_grid(lat_r, olon)
    nn = regrid_slice(da1, dst, "nearest")
    if olat.ndim == 1 and olat.size > 1 and olat[0] > olat[-1]:
        nn = nn[::-1, :]
    return nn


def maybe_kelvin_align(obs: np.ndarray, sim_bilinear: np.ndarray) -> np.ndarray:
    """If obs looks like °C and sim like K, shift obs to K for shared color scale."""
    om = np.nanmedian(obs)
    sm = np.nanmedian(sim_bilinear)
    if np.isfinite(om) and np.isfinite(sm) and om < 100 and sm > 200:
        return obs + 273.15
    return obs


def pooled_vmin_vmax(*arrays: np.ndarray, lo: float = 2.0, hi: float = 98.0) -> tuple[float, float]:
    stacked = np.concatenate([a[np.isfinite(a)].ravel() for a in arrays if a.size])
    if stacked.size == 0:
        return 0.0, 1.0
    return float(np.nanpercentile(stacked, lo)), float(np.nanpercentile(stacked, hi))


def plot_one_date(
    root: Path,
    date: pd.Timestamp,
    mask: np.ndarray,
    out_dir: Path,
    dpi: int,
) -> list[Path]:
    """For each non-pr variable: 2x2 panel bilinear | NN | GridMET | (NN - bilinear)."""
    day_i = day_index_since_1850(date)
    doy = day_of_year_index(date)
    year = date.year
    saved: list[Path] = []

    bilinear_mmap: dict[str, np.memmap] = {}
    coarse_cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    try:
        for cmip_var in NON_PR_VARS:
            g_stem = CMIP_TO_GRIDMET[cmip_var]
            r_path = regridded_hist_path(root, cmip_var)
            c_path = coarse_bc_path(root, cmip_var)
            gm_path = gridmet_path(root, g_stem, year)

            if not r_path.is_file():
                print(f"Skip {cmip_var}: missing {r_path}", file=sys.stderr)
                continue
            if not c_path.is_file():
                print(f"Skip {cmip_var}: missing {c_path}", file=sys.stderr)
                continue
            if not gm_path.is_file():
                print(f"Skip {cmip_var}: missing {gm_path}", file=sys.stderr)
                continue

            if cmip_var not in bilinear_mmap:
                bilinear_mmap[cmip_var] = np.load(r_path, mmap_mode="r")["data"]
            bilinear_field = np.asarray(bilinear_mmap[cmip_var][day_i], dtype=np.float64)

            if cmip_var not in coarse_cache:
                cube, clat, clon = load_npz_2d_field(c_path)
                coarse_cache[cmip_var] = (cube, clat, clon)
            cube, clat, clon = coarse_cache[cmip_var]

            obs_cube, olat, olon = load_npz_2d_field(gm_path)
            if doy >= obs_cube.shape[0]:
                print(f"Skip {cmip_var}: DOY {doy} out of range for {gm_path.name}", file=sys.stderr)
                continue
            obs_raw = np.asarray(obs_cube[doy], dtype=np.float64)
            nn_field = nn_regrid_to_obs_grid(cube, clat, clon, cmip_var, day_i, olat, olon)

            if cmip_var in ("tasmax", "tasmin"):
                obs = maybe_kelvin_align(obs_raw, bilinear_field)
            else:
                obs = obs_raw

            diff = nn_field - bilinear_field
            vmin, vmax = pooled_vmin_vmax(
                bilinear_field[mask],
                nn_field[mask],
                obs[mask],
            )
            dmin, dmax = pooled_vmin_vmax(diff[mask], lo=5.0, hi=95.0)
            d_abs = max(abs(dmin), abs(dmax), 1e-6)

            fig, axes = plt.subplots(2, 2, figsize=(11, 10), constrained_layout=True)
            fig.suptitle(f"{cmip_var} — {date.date()}  (MPI OTBC, Iowa)", fontsize=13)

            titles = ("Bilinear (server)", "Nearest-neighbor", "GridMET", "NN − bilinear")
            fields = (bilinear_field, nn_field, obs, diff)
            cmaps = ("viridis", "viridis", "viridis", "coolwarm")

            for ax, fld, title, cmap in zip(axes.flat, fields, titles, cmaps):
                im = ax.imshow(
                    np.where(mask, fld, np.nan),
                    origin="upper",
                    cmap=cmap,
                    vmin=-d_abs if title == "NN − bilinear" else vmin,
                    vmax=d_abs if title == "NN − bilinear" else vmax,
                )
                ax.set_title(title)
                ax.set_xticks([])
                ax.set_yticks([])
                plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

            out_path = out_dir / f"qual_{cmip_var}_{date.strftime('%Y%m%d')}.png"
            fig.savefig(out_path, dpi=dpi)
            plt.close(fig)
            saved.append(out_path)
            print(f"Wrote {out_path}")
    finally:
        bilinear_mmap.clear()
        coarse_cache.clear()

    return saved


def seasonal_mean_maps(
    root: Path,
    years: range,
    months: tuple[int, ...],
    mask: np.ndarray,
    out_dir: Path,
    dpi: int,
) -> list[Path]:
    """Mean over all days in years where month in `months` (e.g. JJA)."""
    saved: list[Path] = []

    for cmip_var in NON_PR_VARS:
        g_stem = CMIP_TO_GRIDMET[cmip_var]
        r_path = regridded_hist_path(root, cmip_var)
        c_path = coarse_bc_path(root, cmip_var)
        if not r_path.is_file() or not c_path.is_file():
            print(f"Skip seasonal {cmip_var}: missing inputs", file=sys.stderr)
            continue

        bilinear_stack = np.load(r_path, mmap_mode="r")["data"]
        cube, clat, clon = load_npz_2d_field(c_path)
        sum_bi = sum_nn = sum_obs = None
        count = 0

        for year in years:
            gm_path = gridmet_path(root, g_stem, year)
            if not gm_path.is_file():
                continue
            obs_cube, olat, olon = load_npz_2d_field(gm_path)
            n_days = obs_cube.shape[0]
            for doy in range(n_days):
                d = pd.Timestamp(year, 1, 1) + pd.Timedelta(days=doy)
                if d.month not in months:
                    continue
                day_i = day_index_since_1850(d)
                if day_i < 0 or day_i >= cube.shape[0]:
                    continue

                bi = np.asarray(bilinear_stack[day_i], dtype=np.float64)
                nn = nn_regrid_to_obs_grid(cube, clat, clon, cmip_var, day_i, olat, olon)
                ob = np.asarray(obs_cube[doy], dtype=np.float64)
                if cmip_var in ("tasmax", "tasmin"):
                    ob = maybe_kelvin_align(ob, bi)

                if sum_bi is None:
                    sum_bi = np.zeros_like(bi)
                    sum_nn = np.zeros_like(nn)
                    sum_obs = np.zeros_like(ob)
                sum_bi += bi
                sum_nn += nn
                sum_obs += ob
                count += 1

        if count == 0:
            print(f"Skip seasonal {cmip_var}: no days accumulated", file=sys.stderr)
            continue

        mean_bi = sum_bi / count
        mean_nn = sum_nn / count
        mean_obs = sum_obs / count
        diff = mean_nn - mean_bi

        vmin, vmax = pooled_vmin_vmax(mean_bi[mask], mean_nn[mask], mean_obs[mask])
        dmin, dmax = pooled_vmin_vmax(diff[mask], lo=5.0, hi=95.0)
        d_abs = max(abs(dmin), abs(dmax), 1e-6)

        season = "".join({6: "JJA", 12: "DJF", 3: "MAM", 9: "SON"}.get(m, "") for m in sorted(months)) or "season"
        fig, axes = plt.subplots(2, 2, figsize=(11, 10), constrained_layout=True)
        fig.suptitle(
            f"{cmip_var} — mean ({season}, n={count} days)  {years.start}-{years.stop - 1}",
            fontsize=13,
        )
        for ax, fld, title, cmap in zip(
            axes.flat,
            (mean_bi, mean_nn, mean_obs, diff),
            ("Bilinear (server)", "Nearest-neighbor", "GridMET", "NN − bilinear"),
            ("viridis", "viridis", "viridis", "coolwarm"),
        ):
            im = ax.imshow(
                np.where(mask, fld, np.nan),
                origin="upper",
                cmap=cmap,
                vmin=-d_abs if title == "NN − bilinear" else vmin,
                vmax=d_abs if title == "NN − bilinear" else vmax,
            )
            ax.set_title(title)
            ax.set_xticks([])
            ax.set_yticks([])
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

        out_path = out_dir / f"qual_{cmip_var}_mean_{season}_{years.start}_{years.stop - 1}.png"
        fig.savefig(out_path, dpi=dpi)
        plt.close(fig)
        saved.append(out_path)
        print(f"Wrote {out_path}")

    return saved


def write_index_html(out_dir: Path, pngs: list[Path]) -> Path:
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Regrid qualitative</title>",
        "<style>body{font-family:sans-serif;max-width:1200px;margin:1rem auto;} img{max-width:100%;border:1px solid #ccc;margin:1rem 0;}</style>",
        "</head><body><h1>Bilinear vs NN vs GridMET</h1>",
    ]
    for p in sorted(pngs):
        rel = p.name
        lines.append(f"<h2>{p.stem}</h2><img src='{rel}' alt='{rel}'/>")
    lines.append("</body></html>")
    html_path = out_dir / "index.html"
    html_path.write_text("\n".join(lines), encoding="utf-8")
    return html_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Qualitative bilinear vs NN regrid maps.")
    parser.add_argument(
        "--server-root",
        type=Path,
        default=None,
        help=f"WRC_DOR Data root (default env DOR_SERVER_DATA or {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for PNGs and index.html",
    )
    parser.add_argument(
        "--dates",
        type=str,
        default="2011-07-15,2006-01-20,2013-08-01",
        help="Comma-separated YYYY-MM-DD (historical 1981-2014)",
    )
    parser.add_argument("--jja-mean", action="store_true", help="Also write JJA mean maps 2006-2013")
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()

    root = args.server_root or _server_root()
    out_dir = args.out_dir or Path(
        os.environ.get(
            "DOR_PLOT_OUT",
            str(
                Path(__file__).resolve().parents[2] / "qualitative_plots"
            ),
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"DOR_SERVER_DATA → {root}", flush=True)
    print(f"Output dir       → {out_dir}", flush=True)

    gmask_path = geo_mask_path(root)
    if not gmask_path.is_file():
        print(f"Missing geo_mask: {gmask_path}", file=sys.stderr)
        sys.exit(1)
    mask = np.load(gmask_path).astype(bool)

    all_pngs: list[Path] = []

    for ds in args.dates.split(","):
        ds = ds.strip()
        if not ds:
            continue
        date = pd.Timestamp(ds)
        all_pngs.extend(plot_one_date(root, date, mask, out_dir, args.dpi))

    if args.jja_mean:
        all_pngs.extend(
            seasonal_mean_maps(root, range(2006, 2014), (6, 7, 8), mask, out_dir, args.dpi)
        )

    if all_pngs:
        hp = write_index_html(out_dir, all_pngs)
        print(f"Index: {hp}")
    else:
        print("No figures written — check paths and dates.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
