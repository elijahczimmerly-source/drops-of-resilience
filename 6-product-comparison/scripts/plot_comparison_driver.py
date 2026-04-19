"""
Parameterized plot driver: full-historical (1981–2014) and validation (2006–2014) multi-panel
maps (GridMET, S3 cmip6_inputs, DOR test8_v2/v3/v4, LOCA2, NEX), domain-mean time series, and
climate-change Δ maps (future − historical). Independent 2–98% color scales per panel when
amplitudes differ (see 7-fix-pr-splotchiness/PLOTTING.md).

Outputs (under each suite's `figures/` — config.FIG_4KM_PLOTS for dor_native):
  hist_1981_2014/   — time-mean, seasonal, snapshots, domain-mean TS
  validation_2006_2014/ — same figure families for benchmark window
  For pr only: under each of the above, pr/ holds domain-mean TS + timemean; pr/seasonal/ and pr/snapshot/.
  For other variables, those PNGs sit directly under hist_1981_2014/ and validation_2006_2014/ (not in a subfolder).
  delta_future_minus_hist/ — S3, DOR×pipelines, LOCA2, NEX (future minus historical)
  index.html — links to generated PNGs
"""
from __future__ import annotations

import argparse
import gc
import html
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
import grid_suites as gs
from benchmark_io import MultiProductStacks, load_multi_product_historical, load_multi_product_validation
from climate_signal_io import load_cmip6_variable, load_dor_future_npz, load_dor_main_npz, spatial_delta_maps
from grid_target import load_target_grid
from interp_from_gridmet_stack import interp_curvilinear_stack_to_target, interp_gridmet_stack_to_target
from load_loca2 import get_loca_validation_mesh, load_loca_native, load_loca_on_grid
from load_nex import get_nex_validation_mesh, load_nex_native, load_nex_on_grid

DOR_PIDS = ("test8_v2", "test8_v3", "test8_v4")


def _cmap(var: str) -> str:
    return "Blues" if var == "pr" else "viridis"


def _vmin_vmax_one(a: np.ndarray, var: str) -> tuple[float, float]:
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, 2))
    vmax = float(np.percentile(finite, 98))
    if vmax <= vmin:
        vmax = vmin + 1e-6
    if var == "pr":
        vmin = max(0.0, vmin)
    return vmin, vmax


def _season_masks(dates: pd.DatetimeIndex) -> list[tuple[str, np.ndarray]]:
    m = pd.DatetimeIndex(dates).month.values
    return [
        ("DJF", np.isin(m, (12, 1, 2))),
        ("MAM", np.isin(m, (3, 4, 5))),
        ("JJA", np.isin(m, (6, 7, 8))),
        ("SON", np.isin(m, (9, 10, 11))),
    ]


def _panels_from_stack(st: MultiProductStacks, var: str) -> list[tuple[str, np.ndarray]]:
    out: list[tuple[str, np.ndarray]] = [("GridMET", st.obs)]
    if st.s3 is not None:
        out.append(("S3 cmip6_inputs", st.s3))
    for pid in DOR_PIDS:
        if pid in st.dor:
            out.append((f"DOR {pid}", st.dor[pid]))
    if st.loca2 is not None and np.any(np.isfinite(st.loca2)):
        out.append(("LOCA2", st.loca2))
    if st.nex is not None and np.any(np.isfinite(st.nex)):
        out.append(("NEX", st.nex))
    return out


def _figure_roots(suite: str) -> tuple[Path, Path, Path, Path]:
    """hist_dir, val_dir, delta_dir, plots_style_root (parent of hist/val/delta)."""
    r = gs.suite_fig_4km_style_root(suite)
    r.mkdir(parents=True, exist_ok=True)
    return (
        r / "hist_1981_2014",
        r / "validation_2006_2014",
        r / "delta_future_minus_hist",
        r,
    )


def _day_index(dates: pd.DatetimeIndex, day_str: str) -> int | None:
    t = pd.Timestamp(day_str).normalize()
    dn = pd.DatetimeIndex(pd.to_datetime(dates).normalize())
    matches = np.where(dn == t)[0]
    return int(matches[0]) if len(matches) else None


def _plot_multipanel_row(
    panels: list[tuple[str, np.ndarray]],
    var: str,
    suptitle: str,
    out_path: Path,
    *,
    figsize_per: tuple[float, float] = (3.2, 3.6),
) -> None:
    n = len(panels)
    if n == 0:
        return
    fig, axes = plt.subplots(1, n, figsize=(figsize_per[0] * n, figsize_per[1]), constrained_layout=True)
    if n == 1:
        axes = np.array([axes])
    cmap = _cmap(var)
    cbl = cfg.VAR_YLABEL.get(var, var)
    for ax, (title, fld) in zip(axes, panels):
        vmin, vmax = _vmin_vmax_one(fld, var)
        im = ax.imshow(fld, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
        ax.set_title(title, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.72, label=cbl)
    fig.suptitle(suptitle, fontsize=10)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


def plot_domain_mean_ts(
    st: MultiProductStacks,
    var: str,
    label: str,
    out_dir: Path,
    fname_suffix: str,
) -> None:
    dm: list[tuple[str, np.ndarray]] = [("GridMET", np.nanmean(st.obs, axis=(1, 2)))]
    if st.s3 is not None:
        dm.append(("S3 cmip6_inputs", np.nanmean(st.s3, axis=(1, 2))))
    for pid in DOR_PIDS:
        if pid in st.dor:
            dm.append((f"DOR {pid}", np.nanmean(st.dor[pid], axis=(1, 2))))
    if st.loca2 is not None:
        dm.append(("LOCA2", np.nanmean(st.loca2, axis=(1, 2))))
    if st.nex is not None:
        dm.append(("NEX", np.nanmean(st.nex, axis=(1, 2))))

    fig, ax = plt.subplots(figsize=(12, 4))
    for name, ts in dm:
        ax.plot(st.dates, ts, lw=0.85, alpha=0.9, label=name)
    ax.set_ylabel(cfg.VAR_YLABEL.get(var, var))
    ax.set_xlabel("Date")
    ax.set_title(f"{var} — domain mean ({label})")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    out = out_dir / f"domain_mean_ts_{var}_{fname_suffix}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Wrote {out}")


def plot_time_mean_maps(st: MultiProductStacks, var: str, label: str, out_dir: Path, fname_suffix: str) -> None:
    panels = []
    for title, arr in _panels_from_stack(st, var):
        panels.append((title, np.nanmean(arr, axis=0)))
    _plot_multipanel_row(
        panels,
        var,
        f"{var} — time-mean ({label})",
        out_dir / f"timemean_{var}_{fname_suffix}.png",
    )


def plot_seasonal_grids(st: MultiProductStacks, var: str, label: str, out_dir: Path, fname_suffix: str) -> None:
    panels_src = _panels_from_stack(st, var)
    seasons = _season_masks(st.dates)
    for season, mask in seasons:
        if not np.any(mask):
            continue
        panels = []
        for title, arr in panels_src:
            panels.append((title, np.nanmean(arr[mask], axis=0)))
        _plot_multipanel_row(
            panels,
            var,
            f"{var} — {season} mean ({label})",
            out_dir / f"seasonal_{season}_{var}_{fname_suffix}.png",
            figsize_per=(2.9, 3.4),
        )


def plot_snapshot_days(
    st: MultiProductStacks,
    var: str,
    label: str,
    out_dir: Path,
    fname_suffix: str,
    map_dates: list[str],
) -> None:
    for day in map_dates:
        idx = _day_index(st.dates, day)
        if idx is None:
            print(f"  skip snapshot {day}: not in aligned calendar")
            continue
        panels = []
        for title, arr in _panels_from_stack(st, var):
            panels.append((f"{title}\n{day}", arr[idx]))
        tag = pd.Timestamp(day).strftime("%Y%m%d")
        _plot_multipanel_row(
            panels,
            var,
            f"{var} — snapshot ({label})",
            out_dir / f"snapshot_{var}_{tag}_{fname_suffix}.png",
            figsize_per=(2.9, 3.4),
        )


def _high_pr_day(st: MultiProductStacks) -> str:
    dom = np.nanmean(st.obs, axis=(1, 2))
    i = int(np.nanargmax(dom))
    return pd.Timestamp(st.dates[i]).strftime("%Y-%m-%d")


def _hist_val_out_dirs(base: Path, var: str) -> tuple[Path, Path, Path]:
    """For pr: (base/pr, base/pr/seasonal, base/pr/snapshot). Else flat under base."""
    if var != "pr":
        return base, base, base
    root = base / "pr"
    return root, root / "seasonal", root / "snapshot"


def run_hist_plots(var: str, suite: str, fig_hist: Path) -> None:
    st = load_multi_product_historical(var, suite=suite)
    suf = "1981_2014"
    root, seasonal_dir, snapshot_dir = _hist_val_out_dirs(fig_hist, var)
    plot_domain_mean_ts(st, var, "1981–2014 full overlap", root, suf)
    plot_time_mean_maps(st, var, "1981–2014", root, suf)
    plot_seasonal_grids(st, var, "1981–2014", seasonal_dir, suf)
    fixed = list(cfg.VALIDATION_MAP_DATES_FIXED)
    if var == "pr":
        fixed = list(dict.fromkeys([*fixed, _high_pr_day(st)]))
    plot_snapshot_days(st, var, "1981–2014", snapshot_dir, suf, fixed)


def run_val_plots(var: str, suite: str, fig_val: Path) -> None:
    st = load_multi_product_validation(var, suite=suite)
    suf = "2006_2014"
    root, seasonal_dir, snapshot_dir = _hist_val_out_dirs(fig_val, var)
    plot_domain_mean_ts(st, var, "validation 2006–2014", root, suf)
    plot_time_mean_maps(st, var, "validation 2006–2014", root, suf)
    plot_seasonal_grids(st, var, "validation 2006–2014", seasonal_dir, suf)
    fixed = list(cfg.VALIDATION_MAP_DATES_FIXED)
    if var == "pr":
        fixed = list(dict.fromkeys([*fixed, _high_pr_day(st)]))
    plot_snapshot_days(st, var, "validation 2006–2014", snapshot_dir, suf, fixed)


def _delta_panels_dispatch(var: str, suite: str) -> list[tuple[str, np.ndarray]]:
    if gs.is_dor_native_suite(suite):
        return _delta_panels_gridmet(var)
    return _delta_panels_native(var, suite)


def _delta_panels_gridmet(var: str) -> list[tuple[str, np.ndarray]]:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    hist_s, hist_e = cfg.SIGNAL_HIST_START, cfg.SIGNAL_HIST_END
    fut_s, fut_e = cfg.SIGNAL_FUT_START, cfg.SIGNAL_FUT_END
    panels: list[tuple[str, np.ndarray]] = []

    if not cfg.CMIP6_HIST_DAT.is_file() or not cfg.CMIP6_FUTURE_DAT.is_file():
        print("  Δ maps: skip S3 (missing CMIP6 memmaps)")
    else:
        h, _ = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, hist_s, hist_e)
        f, _ = load_cmip6_variable(cfg.CMIP6_FUTURE_DAT, var, fut_s, fut_e)
        _, dmap = spatial_delta_maps(h, f, var)
        panels.append(("S3 cmip6_inputs Δ", dmap))

    for pid in DOR_PIDS:
        root = cfg.DOR_DEFAULT_OUTPUTS.get(pid)
        if root is None:
            continue
        try:
            dh, dd = load_dor_main_npz(root, var)
            dfu, ddf = load_dor_future_npz(root, var, shuffled=True)
            m0 = (dd >= pd.Timestamp(hist_s)) & (dd <= pd.Timestamp(hist_e))
            m1 = (ddf >= pd.Timestamp(fut_s)) & (ddf <= pd.Timestamp(fut_e))
            _, dmap = spatial_delta_maps(dh[m0], dfu[m1], var)
            panels.append((f"DOR {pid} Δ", dmap))
        except FileNotFoundError as e:
            print(f"  DOR Δ skip {pid}: {e}")

    if var in ("pr", "tasmax", "tasmin"):
        try:
            loca_h, _ = load_loca_on_grid(
                var, lat_tgt, lon_tgt, scenario="historical", time_start=hist_s, time_end=hist_e
            )
            loca_f, _ = load_loca_on_grid(
                var, lat_tgt, lon_tgt, scenario="ssp585", time_start=fut_s, time_end=fut_e
            )
            _, dmap = spatial_delta_maps(loca_h, loca_f, var)
            panels.append(("LOCA2 Δ", dmap))
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"  LOCA2 Δ skip: {e}")

    try:
        y0, y1 = int(hist_s[:4]), int(hist_e[:4])
        nex_h, _ = load_nex_on_grid(
            var, lat_tgt, lon_tgt, scenario="historical", year_start=y0, year_end=y1
        )
        y2, y3 = int(fut_s[:4]), int(fut_e[:4])
        nex_f, _ = load_nex_on_grid(
            var, lat_tgt, lon_tgt, scenario="ssp585", year_start=y2, year_end=y3
        )
        _, dmap = spatial_delta_maps(nex_h, nex_f, var)
        panels.append(("NEX Δ", dmap))
    except (FileNotFoundError, OSError) as e:
        print(f"  NEX Δ skip: {e}")

    return panels


def _delta_panels_native(var: str, suite: str) -> list[tuple[str, np.ndarray]]:
    """Δ maps on LOCA2 or NEX native evaluation grid (S3/DOR interpolated; externals native or cross-interp)."""
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    hist_s, hist_e = cfg.SIGNAL_HIST_START, cfg.SIGNAL_HIST_END
    fut_s, fut_e = cfg.SIGNAL_FUT_START, cfg.SIGNAL_FUT_END
    panels: list[tuple[str, np.ndarray]] = []

    if suite == gs.SUITE_LOCA2_NATIVE:
        LAT2, LON2 = get_loca_validation_mesh(lat_tgt, lon_tgt)
    elif suite == gs.SUITE_NEX_NATIVE:
        LAT2, LON2 = get_nex_validation_mesh(lat_tgt, lon_tgt)
    else:
        return panels

    if not cfg.CMIP6_HIST_DAT.is_file() or not cfg.CMIP6_FUTURE_DAT.is_file():
        print("  Δ maps: skip S3 (missing CMIP6 memmaps)")
    else:
        h, _ = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, hist_s, hist_e)
        f, _ = load_cmip6_variable(cfg.CMIP6_FUTURE_DAT, var, fut_s, fut_e)
        hi = interp_gridmet_stack_to_target(h, lat_tgt, lon_tgt, LAT2, LON2)
        fi = interp_gridmet_stack_to_target(f, lat_tgt, lon_tgt, LAT2, LON2)
        _, dmap = spatial_delta_maps(hi, fi, var)
        panels.append(("S3 cmip6_inputs Δ", dmap))

    for pid in DOR_PIDS:
        root = cfg.DOR_DEFAULT_OUTPUTS.get(pid)
        if root is None:
            continue
        try:
            dh, dd = load_dor_main_npz(root, var)
            dfu, ddf = load_dor_future_npz(root, var, shuffled=True)
            m0 = (dd >= pd.Timestamp(hist_s)) & (dd <= pd.Timestamp(hist_e))
            m1 = (ddf >= pd.Timestamp(fut_s)) & (ddf <= pd.Timestamp(fut_e))
            hi = interp_gridmet_stack_to_target(dh[m0], lat_tgt, lon_tgt, LAT2, LON2)
            fi = interp_gridmet_stack_to_target(dfu[m1], lat_tgt, lon_tgt, LAT2, LON2)
            _, dmap = spatial_delta_maps(hi, fi, var)
            panels.append((f"DOR {pid} Δ", dmap))
        except FileNotFoundError as e:
            print(f"  DOR Δ skip {pid}: {e}")

    if var in ("pr", "tasmax", "tasmin"):
        try:
            if suite == gs.SUITE_LOCA2_NATIVE:
                loca_h, _, _, _ = load_loca_native(
                    var, lat_tgt, lon_tgt, scenario="historical", time_start=hist_s, time_end=hist_e
                )
                loca_f, _, _, _ = load_loca_native(
                    var, lat_tgt, lon_tgt, scenario="ssp585", time_start=fut_s, time_end=fut_e
                )
                _, dmap = spatial_delta_maps(loca_h, loca_f, var)
                panels.append(("LOCA2 Δ", dmap))
            else:
                y0, y1 = int(hist_s[:4]), int(hist_e[:4])
                loca_h, _, la_h, lo_h = load_loca_native(
                    var, lat_tgt, lon_tgt, scenario="historical", time_start=hist_s, time_end=hist_e
                )
                y2, y3 = int(fut_s[:4]), int(fut_e[:4])
                loca_f, _, la_f, lo_f = load_loca_native(
                    var, lat_tgt, lon_tgt, scenario="ssp585", time_start=fut_s, time_end=fut_e
                )
                # align spatial grids if needed
                if la_h.shape == la_f.shape and np.allclose(la_h, la_f):
                    _, dmap = spatial_delta_maps(loca_h, loca_f, var)
                    dloc = interp_curvilinear_stack_to_target(
                        dmap[np.newaxis, ...], la_h, lo_h, LAT2, LON2
                    )[0]
                    panels.append(("LOCA2 Δ (on NEX grid)", dloc))
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"  LOCA2 Δ skip: {e}")

    try:
        y0, y1 = int(hist_s[:4]), int(hist_e[:4])
        nex_h, _, _, _ = load_nex_native(
            var, lat_tgt, lon_tgt, scenario="historical", year_start=y0, year_end=y1
        )
        y2, y3 = int(fut_s[:4]), int(fut_e[:4])
        nex_f, _, _, _ = load_nex_native(
            var, lat_tgt, lon_tgt, scenario="ssp585", year_start=y2, year_end=y3
        )
        if suite == gs.SUITE_NEX_NATIVE:
            _, dmap = spatial_delta_maps(nex_h, nex_f, var)
            panels.append(("NEX Δ", dmap))
        else:
            _, dm = spatial_delta_maps(nex_h, nex_f, var)
            LATn, LONn = get_nex_validation_mesh(lat_tgt, lon_tgt)
            d_on_loca = interp_curvilinear_stack_to_target(
                dm[np.newaxis, ...], LATn, LONn, LAT2, LON2
            )[0]
            panels.append(("NEX Δ (on LOCA grid)", d_on_loca))
    except (FileNotFoundError, OSError) as e:
        print(f"  NEX Δ skip: {e}")

    return panels


def _plot_delta_row(panels: list[tuple[str, np.ndarray]], var: str, out_path: Path) -> None:
    n = len(panels)
    if n == 0:
        return
    fig, axes = plt.subplots(1, n, figsize=(3.0 * n, 3.5), constrained_layout=True)
    if n == 1:
        axes = np.array([axes])
    # diverging-friendly: use RdBu_r for signed Δ (temps) or different for pr %
    for ax, (title, fld) in zip(axes, panels):
        finite = fld[np.isfinite(fld)]
        if finite.size == 0:
            continue
        vmin, vmax = float(np.percentile(finite, 2)), float(np.percentile(finite, 98))
        if vmax <= vmin:
            vmax = vmin + 1e-6
        cmap = "RdBu_r" if var != "pr" else "BrBG"
        im = ax.imshow(fld, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
        ax.set_title(title, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.72)
    unit = "% Δ mean" if var == "pr" else "Δ (native units)"
    fig.suptitle(f"{var} — future−historical signal ({unit})", fontsize=10)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")


def run_delta_maps(var: str, suite: str, fig_delta: Path) -> None:
    panels = _delta_panels_dispatch(var, suite)
    suf = f"{cfg.SIGNAL_HIST_START[:4]}_{cfg.SIGNAL_FUT_END[:4]}"
    _plot_delta_row(panels, var, fig_delta / f"delta_maps_{var}_{suf}.png")


def write_html_index(plots_root: Path, suite: str) -> None:
    paths: list[Path] = []
    for base in (
        plots_root / "hist_1981_2014",
        plots_root / "validation_2006_2014",
        plots_root / "delta_future_minus_hist",
    ):
        if base.is_dir():
            paths.extend(sorted(base.rglob("*.png")))
    if not paths:
        return
    title = f"6-product-comparison — {gs.suite_label_for_titles(suite)}"
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Climate signal figures</title></head><body>",
        f"<h1>{html.escape(title)}</h1><ul>",
    ]
    for p in paths:
        rel = p.relative_to(plots_root)
        lines.append(f"<li><a href='{html.escape(str(rel.as_posix()))}'>{html.escape(rel.name)}</a></li>")
    lines.append("</ul></body></html>")
    idx = plots_root / "index.html"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {idx}")


def main() -> int:
    p = argparse.ArgumentParser(description="Multi-product comparison plots (hist / val / delta)")
    p.add_argument("--vars", default=",".join(cfg.VARS), help="Comma-separated variables")
    p.add_argument(
        "--suite",
        default=gs.SUITE_DOR_NATIVE,
        help=f"DOR_BENCHMARK_SUITE ({', '.join(sorted(gs.VALID_SUITES))})",
    )
    p.add_argument("--hist", action="store_true", help="1981-2014 figure family")
    p.add_argument("--val", action="store_true", help="2006-2014 figure family")
    p.add_argument("--delta", action="store_true", help="climate-change delta maps (future minus historical)")
    p.add_argument("--all", action="store_true", help="hist + val + delta + index")
    args = p.parse_args()
    do_hist = args.all or args.hist
    do_val = args.all or args.val
    do_delta = args.all or args.delta
    if not (do_hist or do_val or do_delta):
        do_hist = do_val = do_delta = True

    os.environ["DOR_BENCHMARK_SUITE"] = args.suite.strip()
    suite = gs.benchmark_suite()
    fig_hist, fig_val, fig_delta, plots_root = _figure_roots(suite)

    try:
        load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    except FileNotFoundError as e:
        print(f"Need GridMET reference NPZ (CROPPED_GRIDMET): {e}")
        return 1

    plots_root.mkdir(parents=True, exist_ok=True)
    for var in [x.strip() for x in args.vars.split(",") if x.strip()]:
        if do_hist:
            try:
                run_hist_plots(var, suite, fig_hist)
            except Exception as e:
                print(f"hist {var}: {e}")
        if do_val:
            try:
                run_val_plots(var, suite, fig_val)
            except Exception as e:
                print(f"val {var}: {e}")
        if do_delta:
            try:
                run_delta_maps(var, suite, fig_delta)
            except Exception as e:
                print(f"delta {var}: {e}")
        gc.collect()

    if args.all or do_hist or do_val or do_delta:
        write_html_index(plots_root, suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
