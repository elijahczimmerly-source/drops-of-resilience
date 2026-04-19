"""
Validation-period plots (2006–2014): domain-mean time series (Obs vs DOR, LOCA2, NEX) and
side-by-side maps (GridMET vs DOR): snapshot days, full-window mean, and seasonal means.

For **multi-product** climatological (1981–2014) and validation (2006–2014) panels — domain-mean time
series, time-mean and seasonal maps, snapshot days, and climate delta maps — use
`plot_comparison_driver.py` (under `output/figures/4km_plots/`). This script can delegate validation
panels to that driver with **`python plot_validation_period.py --via-comparison-driver`**. For a **single row** of
1981–2014 climatological means only, use `plot_climatology_comparisons.py` (independent 2–98% per panel).

Outputs (gridmet_4km; native suites mirror under output/suites/<suite>/figures/):
  figures/validation_ts_<var>.png
  figures/dor side-by-side/individual days/validation_maps_<var>_<YYYYMMDD>.png
  figures/dor side-by-side/time aggregated/validation_agg_mean_<var>.png
  figures/dor side-by-side/time aggregated/validation_agg_seasonal_<var>.png

Use `--suite` or DOR_BENCHMARK_SUITE. For full multi-product validation panels see
`plot_comparison_driver.py --val`.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import time
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as cfg
import grid_suites as gs
from benchmark_io import load_aligned_stacks, high_pr_obs_date


def _day_index(dates: pd.DatetimeIndex, day_str: str) -> int | None:
    t = pd.Timestamp(day_str).normalize()
    dn = pd.DatetimeIndex(pd.to_datetime(dates).normalize())
    matches = np.where(dn == t)[0]
    if len(matches) == 0:
        return None
    return int(matches[0])


def _pair_vmin_vmax(o: np.ndarray, d: np.ndarray, var: str) -> tuple[float, float]:
    finite = np.concatenate([o[np.isfinite(o)].ravel(), d[np.isfinite(d)].ravel()])
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, 2))
    vmax = float(np.percentile(finite, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    if var == "pr":
        vmin = max(0.0, vmin)
    return vmin, vmax


def _cmap_for_var(var: str) -> str:
    return "Blues" if var == "pr" else "viridis"


def _save_obs_dor_pair(
    out_path: Path,
    o: np.ndarray,
    d: np.ndarray,
    var: str,
    title_left: str,
    title_right: str,
    suptitle: str,
    *,
    figsize: tuple[float, float] = (10, 4.2),
) -> None:
    vmin, vmax = _pair_vmin_vmax(o, d, var)
    cmap = _cmap_for_var(var)
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
    fig.colorbar(im1, ax=axes, shrink=0.85, label=cfg.VAR_YLABEL.get(var, var))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    data = buf.getvalue()
    fd, tmp = tempfile.mkstemp(suffix=".png", dir=str(out_path.parent))
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    dest = str(out_path.resolve())
    last_err: OSError | None = None
    try:
        for attempt in range(12):
            try:
                if out_path.is_file():
                    os.remove(out_path)
                os.replace(tmp, dest)
                print(f"Wrote {out_path}")
                return
            except OSError as e:
                last_err = e
                time.sleep(0.12 * (attempt + 1))
        raise last_err if last_err else OSError(f"failed to write {out_path}")
    finally:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _season_masks(dates: pd.DatetimeIndex) -> list[tuple[str, np.ndarray]]:
    m = pd.DatetimeIndex(dates).month.values
    return [
        ("DJF", np.isin(m, (12, 1, 2))),
        ("MAM", np.isin(m, (3, 4, 5))),
        ("JJA", np.isin(m, (6, 7, 8))),
        ("SON", np.isin(m, (9, 10, 11))),
    ]


def _domain_means(st) -> dict[str, np.ndarray]:
    out = {
        "GridMET": np.nanmean(st.obs, axis=(1, 2)),
        "DOR": np.nanmean(st.dor, axis=(1, 2)),
        "NEX": np.nanmean(st.nex, axis=(1, 2)),
    }
    if st.loca2 is not None:
        out["LOCA2"] = np.nanmean(st.loca2, axis=(1, 2))
    return out


def _fig_paths(suite: str):
    base = gs.suite_fig_dir(suite)
    ind = base / "dor side-by-side" / "individual days"
    agg = base / "dor side-by-side" / "time aggregated"
    return base, ind, agg


def plot_domain_mean_timeseries(var: str, st, *, fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    dm = _domain_means(st)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(st.dates, dm["GridMET"], label="GridMET (target)", color="0.15", lw=0.9, alpha=0.95)
    ax.plot(st.dates, dm["DOR"], label="DOR (blend 0.65)", color="#2c7fb8", lw=0.8, alpha=0.85)
    if "LOCA2" in dm:
        ax.plot(st.dates, dm["LOCA2"], label="LOCA2", color="#7fcdbb", lw=0.8, alpha=0.85)
    ax.plot(st.dates, dm["NEX"], label="NEX-GDDP", color="#fdae61", lw=0.8, alpha=0.85)
    ax.set_ylabel(cfg.VAR_YLABEL.get(var, var))
    ax.set_xlabel("Date")
    ax.set_title(f"{var} - domain mean (MPI-ESM1-2-HR, validation 2006-2014)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    p = fig_dir / f"validation_ts_{var}.png"
    fig.savefig(str(p.resolve()), dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")


def plot_obs_vs_dor_maps(var: str, st, day_str: str, *, fig_individual: Path) -> None:
    idx = _day_index(st.dates, day_str)
    if idx is None:
        print(f"  skip maps {var} {day_str}: date not in aligned series")
        return
    o = st.obs[idx]
    d = st.dor[idx]
    if not np.any(np.isfinite(o)) and not np.any(np.isfinite(d)):
        return
    tag = pd.Timestamp(day_str).strftime("%Y%m%d")
    p = fig_individual / f"validation_maps_{var}_{tag}.png"
    _save_obs_dor_pair(
        p,
        o,
        d,
        var,
        f"GridMET (target)\n{day_str}",
        f"DOR blend 0.65\n{day_str}",
        f"{var} - Iowa crop (216x192), shared color scale (2-98%)",
    )


def plot_obs_vs_dor_mean_maps(var: str, st, *, fig_agg: Path) -> None:
    o = np.nanmean(st.obs, axis=0)
    d = np.nanmean(st.dor, axis=0)
    p = fig_agg / f"validation_agg_mean_{var}.png"
    _save_obs_dor_pair(
        p,
        o,
        d,
        var,
        "GridMET (target)\nmean 2006-2014",
        "DOR blend 0.65\nmean 2006-2014",
        f"{var} - time-mean fields, shared color scale (2-98%)",
    )


def plot_obs_vs_dor_seasonal_maps(var: str, st, *, fig_agg: Path) -> None:
    cmap = _cmap_for_var(var)
    fig, axes = plt.subplots(4, 2, figsize=(10, 12), constrained_layout=True)
    cbar_label = cfg.VAR_YLABEL.get(var, var)

    for i, (season, mask) in enumerate(_season_masks(st.dates)):
        if not np.any(mask):
            axes[i, 0].set_visible(False)
            axes[i, 1].set_visible(False)
            continue
        o_m = np.nanmean(st.obs[mask], axis=0)
        d_m = np.nanmean(st.dor[mask], axis=0)
        vmin, vmax = _pair_vmin_vmax(o_m, d_m, var)
        axes[i, 0].imshow(o_m, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
        axes[i, 0].set_title(f"GridMET (target)\n{season} mean")
        axes[i, 0].set_xticks([])
        axes[i, 0].set_yticks([])
        im1 = axes[i, 1].imshow(d_m, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
        axes[i, 1].set_title(f"DOR blend 0.65\n{season} mean")
        axes[i, 1].set_xticks([])
        axes[i, 1].set_yticks([])
        fig.colorbar(im1, ax=[axes[i, 0], axes[i, 1]], shrink=0.72, label=cbar_label)

    fig.suptitle(
        f"{var} - seasonal mean (2006-2014), per-row 2-98% on GridMET+DOR",
        fontsize=11,
    )
    p = fig_agg / f"validation_agg_seasonal_{var}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(p.resolve()), dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")


def main() -> int:
    if "--via-comparison-driver" in sys.argv:
        import plot_comparison_driver as pcd

        suite = gs.SUITE_GRIDMET_4KM
        if "--suite" in sys.argv:
            i = sys.argv.index("--suite")
            if i + 1 < len(sys.argv):
                suite = sys.argv[i + 1].strip().lower()
        extra = ["--val", "--vars", ",".join(cfg.VARS), "--suite", suite]
        sys.argv = [sys.argv[0], *extra]
        return pcd.main()

    ap = argparse.ArgumentParser(description="Validation-era GridMET vs DOR side-by-side maps")
    ap.add_argument(
        "--suite",
        default=os.environ.get("DOR_BENCHMARK_SUITE", gs.SUITE_GRIDMET_4KM),
        help=f"DOR_BENCHMARK_SUITE ({', '.join(sorted(gs.VALID_SUITES))})",
    )
    args, _unknown = ap.parse_known_args()
    suite = args.suite.strip().lower()
    if suite not in gs.VALID_SUITES:
        print(f"Invalid suite {suite!r}; expected one of {sorted(gs.VALID_SUITES)}")
        return 1
    os.environ["DOR_BENCHMARK_SUITE"] = suite

    fig_dir, fig_individual, fig_agg = _fig_paths(suite)
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig_individual.mkdir(parents=True, exist_ok=True)
    fig_agg.mkdir(parents=True, exist_ok=True)

    pr_st = load_aligned_stacks("pr", suite=suite)
    high_day = high_pr_obs_date(pr_st).strftime("%Y-%m-%d")
    map_dates = list(dict.fromkeys([*cfg.VALIDATION_MAP_DATES_FIXED, high_day]))
    print(f"Map snapshot dates: {map_dates} (includes max domain-mean pr day: {high_day})")

    for var in cfg.VARS:
        st = load_aligned_stacks(var, suite=suite)
        plot_domain_mean_timeseries(var, st, fig_dir=fig_dir)
        for day in map_dates:
            plot_obs_vs_dor_maps(var, st, day, fig_individual=fig_individual)
        plot_obs_vs_dor_mean_maps(var, st, fig_agg=fig_agg)
        plot_obs_vs_dor_seasonal_maps(var, st, fig_agg=fig_agg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
