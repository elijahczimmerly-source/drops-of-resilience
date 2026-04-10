"""
Validation-period plots: domain-mean time series (Obs vs DOR, LOCA2, NEX) and
side-by-side maps (GridMET vs DOR): snapshot days, full-window mean, and seasonal means.

Outputs:
  output/figures/validation_ts_<var>.png
  output/figures/dor side-by-side/individual days/validation_maps_<var>_<YYYYMMDD>.png
  output/figures/dor side-by-side/time aggregated/validation_agg_mean_<var>.png
  output/figures/dor side-by-side/time aggregated/validation_agg_seasonal_<var>.png
"""
from __future__ import annotations

import sys
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
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


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


def plot_domain_mean_timeseries(var: str, st) -> None:
    cfg.FIG_DIR.mkdir(parents=True, exist_ok=True)
    dm = _domain_means(st)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(st.dates, dm["GridMET"], label="GridMET (target)", color="0.15", lw=0.9, alpha=0.95)
    ax.plot(st.dates, dm["DOR"], label="DOR (blend 0.65)", color="#2c7fb8", lw=0.8, alpha=0.85)
    if "LOCA2" in dm:
        ax.plot(st.dates, dm["LOCA2"], label="LOCA2", color="#7fcdbb", lw=0.8, alpha=0.85)
    ax.plot(st.dates, dm["NEX"], label="NEX-GDDP", color="#fdae61", lw=0.8, alpha=0.85)
    ax.set_ylabel(cfg.VAR_YLABEL.get(var, var))
    ax.set_xlabel("Date")
    ax.set_title(f"{var} — domain mean (MPI-ESM1-2-HR, validation 2006–2014)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    p = cfg.FIG_DIR / f"validation_ts_{var}.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")


def plot_obs_vs_dor_maps(var: str, st, day_str: str) -> None:
    idx = _day_index(st.dates, day_str)
    if idx is None:
        print(f"  skip maps {var} {day_str}: date not in aligned series")
        return
    o = st.obs[idx]
    d = st.dor[idx]
    if not np.any(np.isfinite(o)) and not np.any(np.isfinite(d)):
        return
    tag = pd.Timestamp(day_str).strftime("%Y%m%d")
    p = cfg.FIG_VALIDATION_INDIVIDUAL_DAYS / f"validation_maps_{var}_{tag}.png"
    _save_obs_dor_pair(
        p,
        o,
        d,
        var,
        f"GridMET (target)\n{day_str}",
        f"DOR blend 0.65\n{day_str}",
        f"{var} — Iowa crop (216×192), shared color scale (2–98%)",
    )


def plot_obs_vs_dor_mean_maps(var: str, st) -> None:
    o = np.nanmean(st.obs, axis=0)
    d = np.nanmean(st.dor, axis=0)
    p = cfg.FIG_VALIDATION_TIME_AGG / f"validation_agg_mean_{var}.png"
    _save_obs_dor_pair(
        p,
        o,
        d,
        var,
        "GridMET (target)\nmean 2006–2014",
        "DOR blend 0.65\nmean 2006–2014",
        f"{var} — time-mean fields, shared color scale (2–98%)",
    )


def plot_obs_vs_dor_seasonal_maps(var: str, st) -> None:
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
        f"{var} — seasonal mean (2006–2014), per-row 2–98% on GridMET+DOR",
        fontsize=11,
    )
    p = cfg.FIG_VALIDATION_TIME_AGG / f"validation_agg_seasonal_{var}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")


def main() -> int:
    cfg.FIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg.FIG_VALIDATION_INDIVIDUAL_DAYS.mkdir(parents=True, exist_ok=True)
    cfg.FIG_VALIDATION_TIME_AGG.mkdir(parents=True, exist_ok=True)

    pr_st = load_aligned_stacks("pr")
    high_day = high_pr_obs_date(pr_st).strftime("%Y-%m-%d")
    map_dates = list(dict.fromkeys([*cfg.VALIDATION_MAP_DATES_FIXED, high_day]))
    print(f"Map snapshot dates: {map_dates} (includes max domain-mean pr day: {high_day})")

    for var in cfg.VARS:
        st = load_aligned_stacks(var)
        plot_domain_mean_timeseries(var, st)
        for day in map_dates:
            plot_obs_vs_dor_maps(var, st, day)
        plot_obs_vs_dor_mean_maps(var, st)
        plot_obs_vs_dor_seasonal_maps(var, st)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
