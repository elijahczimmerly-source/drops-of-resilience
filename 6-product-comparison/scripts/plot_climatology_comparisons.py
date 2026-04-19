"""
Climatological mean maps (1981–2014): GridMET, S3 memmap, DOR (v2/v3/v4 only), LOCA2, NEX.
Uses independent 2–98% color scales per panel (see 7-fix-pr-splotchiness/PLOTTING.md).

Writes `clim_mean_{var}_1981_2014.png` under each suite's `figures/` (same root as the multi-panel driver).
Rerun after DOR output / config changes.

Use `--suite dor_native|gridmet_4km|loca2_native|nex_native` (or set DOR_BENCHMARK_SUITE).
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

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
import grid_suites as gs
from benchmark_io import MultiProductStacks, load_multi_product_historical
from grid_target import load_target_grid
from plot_comparison_driver import DOR_PIDS


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


def _cmap(var: str) -> str:
    return "Blues" if var == "pr" else "viridis"


def _clim_panels_from_stack(st: MultiProductStacks) -> list[tuple[str, np.ndarray]]:
    out: list[tuple[str, np.ndarray]] = [("GridMET obs", np.nanmean(st.obs, axis=0))]
    if st.s3 is not None:
        out.append(("S3 cmip6_inputs", np.nanmean(st.s3, axis=0)))
    for pid in DOR_PIDS:
        if pid in st.dor:
            out.append((f"DOR {pid}", np.nanmean(st.dor[pid], axis=0)))
    if st.loca2 is not None and np.any(np.isfinite(st.loca2)):
        out.append(("LOCA2", np.nanmean(st.loca2, axis=0)))
    if st.nex is not None and np.any(np.isfinite(st.nex)):
        out.append(("NEX", np.nanmean(st.nex, axis=0)))
    return out


def plot_var_climatology_row(var: str, suite: str) -> None:
    st = load_multi_product_historical(var, suite=suite)
    panels = _clim_panels_from_stack(st)
    if not panels:
        print(f"  skip {var}: no panels")
        return

    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.8), constrained_layout=True)
    if n == 1:
        axes = [axes]
    cmap = _cmap(var)
    for ax, (title, fld) in zip(axes, panels):
        vmin, vmax = _vmin_vmax_one(fld, var)
        im = ax.imshow(fld, origin="upper", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
        ax.set_title(title, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.72, label=cfg.VAR_YLABEL.get(var, var))
    label = gs.suite_label_for_titles(suite)
    fig.suptitle(
        f"{var} — climatological mean {cfg.HIST_START}..{cfg.HIST_END} ({label})",
        fontsize=11,
    )
    out_root = gs.suite_fig_4km_style_root(suite)
    out_root.mkdir(parents=True, exist_ok=True)
    out = out_root / f"clim_mean_{var}_1981_2014.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Wrote {out}")
    if st.missing:
        print(f"  note missing sources: {st.missing}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Climatological mean maps per benchmark suite")
    ap.add_argument(
        "--suite",
        default=os.environ.get("DOR_BENCHMARK_SUITE", gs.SUITE_DOR_NATIVE),
        help=f"DOR_BENCHMARK_SUITE ({', '.join(sorted(gs.VALID_SUITES))})",
    )
    args = ap.parse_args()
    suite = args.suite.strip().lower()
    if suite not in gs.VALID_SUITES:
        print(f"Invalid suite {suite!r}; expected one of {sorted(gs.VALID_SUITES)}")
        return 1
    os.environ["DOR_BENCHMARK_SUITE"] = suite

    gs.suite_fig_4km_style_root(suite).mkdir(parents=True, exist_ok=True)
    try:
        load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    except FileNotFoundError as e:
        print(f"Need GridMET reference NPZ on WRC_DOR (Cropped_pr_2006.npz): {e}")
        return 1
    for var in cfg.VARS:
        plot_var_climatology_row(var, suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
