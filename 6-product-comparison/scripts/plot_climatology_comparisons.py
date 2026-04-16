"""
Climatological mean maps (1981–2014): GridMET, S3 memmap, DOR (v2/v3/v4), LOCA2, NEX.
Uses independent 2–98% color scales per panel (see 7-fix-pr-splotchiness/PLOTTING.md).
"""
from __future__ import annotations

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
from grid_target import load_target_grid
from load_loca2 import load_loca_on_grid
from load_nex import load_nex_on_grid
from load_obs import load_obs_historical_full


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


def _mean_field_dor(var: str, dor_root: Path) -> np.ndarray:
    """Mean over 1981–2014 from Stochastic_V8_Hybrid_{var}.npz in dor_root."""
    p = dor_root / f"Stochastic_V8_Hybrid_{var}.npz"
    z = np.load(p)
    data = np.asarray(z["data"], dtype=np.float64)
    dates = pd.to_datetime(z["dates"])
    m = (dates >= pd.Timestamp(cfg.HIST_START)) & (dates <= pd.Timestamp(cfg.HIST_END))
    return np.nanmean(data[m], axis=0)


def _mean_s3_cmip6(var: str) -> np.ndarray:
    """Time-mean of driving memmap (historical 1981–2014) without materializing full time axis."""
    vidx = list(cfg.VARS).index(var)
    mm = np.memmap(
        str(cfg.CMIP6_HIST_DAT),
        dtype="float32",
        mode="r",
        shape=(cfg.N_DAYS_MAIN, len(cfg.VARS), cfg.H, cfg.W),
    )
    H, W = cfg.H, cfg.W
    T = cfg.N_DAYS_MAIN
    acc = np.zeros((H, W), dtype=np.float64)
    wgt = np.zeros((H, W), dtype=np.float64)
    step = 512
    for t0 in range(0, T, step):
        t1 = min(t0 + step, T)
        b = np.asarray(mm[t0:t1, vidx, :, :], dtype=np.float32)
        m = np.isfinite(b)
        acc += np.sum(np.where(m, b, 0.0), axis=0, dtype=np.float64)
        wgt += np.sum(m, axis=0, dtype=np.float64)
    mean = acc / np.maximum(wgt, 1.0)
    mean[wgt == 0] = np.nan
    return mean


def plot_var_climatology_row(var: str) -> None:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, _ = load_obs_historical_full(var)
    o_mean = np.nanmean(obs, axis=0)

    panels: list[tuple[str, np.ndarray]] = [("GridMET obs", o_mean)]

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            panels.append(("S3 cmip6_inputs", _mean_s3_cmip6(var)))
        except OSError as e:
            print(f"  S3 skip: {e}")

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        if root.is_dir() and (root / f"Stochastic_V8_Hybrid_{var}.npz").is_file():
            try:
                panels.append((f"DOR {pid}", _mean_field_dor(var, root)))
            except Exception as e:
                print(f"  DOR {pid} skip: {e}")

    if var in ("pr", "tasmax", "tasmin"):
        try:
            loca, _ = load_loca_on_grid(
                var,
                lat_tgt,
                lon_tgt,
                scenario="historical",
                time_start=cfg.HIST_START,
                time_end=cfg.HIST_END,
            )
            panels.append(("LOCA2", np.nanmean(loca, axis=0)))
        except (FileNotFoundError, OSError) as e:
            print(f"  LOCA2 skip: {e}")

    try:
        nex, _ = load_nex_on_grid(
            var,
            lat_tgt,
            lon_tgt,
            scenario="historical",
            year_start=int(cfg.HIST_START[:4]),
            year_end=int(cfg.HIST_END[:4]),
        )
        panels.append(("NEX", np.nanmean(nex, axis=0)))
    except (FileNotFoundError, OSError) as e:
        print(f"  NEX skip: {e}")

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
    fig.suptitle(f"{var} — climatological mean {cfg.HIST_START}..{cfg.HIST_END}", fontsize=11)
    out = cfg.FIG_4KM_PLOTS / f"clim_mean_{var}_1981_2014.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Wrote {out}")


def main() -> int:
    cfg.FIG_4KM_PLOTS.mkdir(parents=True, exist_ok=True)
    try:
        load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    except FileNotFoundError as e:
        print(f"Need GridMET reference NPZ on WRC_DOR (Cropped_pr_2006.npz): {e}")
        return 1
    for var in cfg.VARS:
        plot_var_climatology_row(var)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
