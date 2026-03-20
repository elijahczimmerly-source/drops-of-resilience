"""
Compare long-run average of (tasmax + tasmin)/2 vs average of daily mean tas.

Hydrology often only has daily extrema. This script checks whether, over many
days, mean((Tmax+Tmin)/2) approaches mean(tas) at a single Iowa location.

Memory: does not load the global grid. Opens each NetCDF once per variable,
selects the nearest grid point to (LAT_IOWA, LON_IOWA), and concatenates 1D
series — RAM ~ O(n_days), not O(n_days * n_lat * n_lon).
"""

import glob
import os
from typing import Iterator

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

matplotlib.use("Agg")

xr.set_options(use_new_combine_kwarg_defaults=True)

DATA_DIR = r"\\abe-cylo\public\CMIP\Download\km100"

# Nearest grid cell to this location (Ames, IA); lon in 0–360° east
LAT_IOWA, LON_IOWA = 42.03, 360.0 - 93.65

# Single 30-day file (fallback)
FILE_SUFFIX = "day_EC-Earth3P_highresSST-present_r1i1p1f1_gr_20150401-20150430.nc"

LONG_TIMEFRAME_SINGLE_SUFFIX = None
LONG_TIMEFRAME_GLOB = "{var}_day_EC-Earth3P_highresSST-future_r1i1p1f1_gr_*.nc"
MAX_FILES = None


def nc_path(variable: str) -> str:
    return os.path.join(DATA_DIR, f"{variable}_{FILE_SUFFIX}")


def _glob_paths(variable: str) -> list[str]:
    pattern = os.path.join(DATA_DIR, LONG_TIMEFRAME_GLOB.format(var=variable))
    paths = sorted(glob.glob(pattern))
    if MAX_FILES is not None and len(paths) > MAX_FILES:
        paths = paths[:MAX_FILES]
    return paths


def iter_tas_path_triplets() -> Iterator[tuple[str, str, str]]:
    """Yield (tas_path, tasmax_path, tasmin_path) in time order."""
    if LONG_TIMEFRAME_SINGLE_SUFFIX:
        triple = tuple(
            os.path.join(DATA_DIR, f"{v}_{LONG_TIMEFRAME_SINGLE_SUFFIX}")
            for v in ("tas", "tasmax", "tasmin")
        )
        for v, p in zip(("tas", "tasmax", "tasmin"), triple):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"Missing {v}: {p}")
        yield triple  # type: ignore[misc]
        return

    if LONG_TIMEFRAME_GLOB:
        tas_files = _glob_paths("tas")
        tmax_files = _glob_paths("tasmax")
        tmin_files = _glob_paths("tasmin")
        if tas_files and tmax_files and tmin_files:
            if not (len(tas_files) == len(tmax_files) == len(tmin_files)):
                raise ValueError(
                    f"Mismatched file counts: tas={len(tas_files)}, "
                    f"tasmax={len(tmax_files)}, tasmin={len(tmin_files)}"
                )
            for a, b, c in zip(tas_files, tmax_files, tmin_files):
                yield (a, b, c)
            return

    paths = {v: nc_path(v) for v in ("tas", "tasmax", "tasmin")}
    for v, p in paths.items():
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Missing {v}: {p}")
    yield (paths["tas"], paths["tasmax"], paths["tasmin"])


def load_iowa_point_series(
    lat: float = LAT_IOWA,
    lon: float = LON_IOWA,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Stream all file triplets; return (time, tas, tasmax, tasmin) as 1D float arrays
    at the nearest grid point to (lat, lon).
    """
    time_parts: list[np.ndarray] = []
    tas_parts: list[np.ndarray] = []
    tmax_parts: list[np.ndarray] = []
    tmin_parts: list[np.ndarray] = []

    sel = {"lat": lat, "lon": lon, "method": "nearest"}
    n_files = 0
    for p_tas, p_max, p_min in iter_tas_path_triplets():
        n_files += 1
        with xr.open_dataset(p_tas) as ds_t:
            t_var = ds_t["tas"].sel(**sel)
            time_parts.append(np.asarray(t_var["time"].values))
            tas_parts.append(np.asarray(t_var.values, dtype=np.float64).ravel())
        with xr.open_dataset(p_max) as ds_mx:
            mx = ds_mx["tasmax"].sel(**sel)
            tmax_parts.append(np.asarray(mx.values, dtype=np.float64).ravel())
        with xr.open_dataset(p_min) as ds_mn:
            mn = ds_mn["tasmin"].sel(**sel)
            tmin_parts.append(np.asarray(mn.values, dtype=np.float64).ravel())

    if n_files == 0:
        raise OSError("No input files found for tas / tasmax / tasmin")

    time_all = np.concatenate(time_parts)
    tas_all = np.concatenate(tas_parts)
    tmax_all = np.concatenate(tmax_parts)
    tmin_all = np.concatenate(tmin_parts)

    n = tas_all.size
    if not (tmax_all.size == n and tmin_all.size == n):
        raise ValueError(
            f"Length mismatch after concat: tas={tas_all.size}, "
            f"tasmax={tmax_all.size}, tasmin={tmin_all.size}"
        )

    return time_all, tas_all, tmax_all, tmin_all


def main() -> None:
    print(
        f"Streaming Iowa point (lat={LAT_IOWA}, lon={LON_IOWA}°): "
        "one grid cell, year-by-year files..."
    )
    time_idx, tas, tasmax, tasmin = load_iowa_point_series()
    midpoint = (tasmax + tasmin) / 2.0
    ntime = tas.size
    print(f"  Days loaded: {ntime}  (time[0]={time_idx[0]}, time[-1]={time_idx[-1]})")

    mean_tas = float(tas.mean())
    mean_mid = float(midpoint.mean())
    diff_overall = mean_mid - mean_tas

    print("\n--- Full period (Iowa grid cell) ---")
    print(f"  Mean of daily means (tas):     {mean_tas:.4f} K")
    print(f"  Mean of (tasmax+tasmin)/2:     {mean_mid:.4f} K")
    print(f"  Difference:                    {diff_overall:.4f} K")
    print(f"  Relative diff (vs mean tas):   {100 * diff_overall / mean_tas:.4f}%")

    # Cumulative means (pure numpy; one pass)
    n = np.arange(1, ntime + 1, dtype=np.float64)
    csum_tas = np.cumsum(tas)
    csum_mid = np.cumsum(midpoint)
    cummean_tas = csum_tas / n
    cummean_mid = csum_mid / n
    diff_cum = cummean_mid - cummean_tas

    print("\n--- Cumulative difference (same Iowa cell) ---")
    i_quarter = max(1, ntime // 4)
    i_half = max(1, ntime // 2)
    print(f"  After 1 day:     diff = {diff_cum[0]:.4f} K")
    if ntime > 1:
        print(f"  After ~25%:      diff = {diff_cum[i_quarter - 1]:.4f} K  (day {i_quarter})")
    if ntime > 2:
        print(f"  After ~50%:      diff = {diff_cum[i_half - 1]:.4f} K  (day {i_half})")
    print(f"  After full run:  diff = {diff_cum[-1]:.4f} K  (day {ntime})")

    step = max(1, ntime // 2000)
    t_plot = time_idx[::step]
    tas_plot = cummean_tas[::step]
    mid_plot = cummean_mid[::step]
    diff_plot = diff_cum[::step]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    ax1 = axes[0]
    ax1.plot(t_plot, tas_plot, label="Cumulative mean tas", color="C0")
    ax1.plot(t_plot, mid_plot, label="Cumulative mean (tasmax+tasmin)/2", color="C1", linestyle="--")
    ax1.set_ylabel("Cumulative mean temperature (K)")
    ax1.legend()
    ax1.set_title(f"Iowa grid cell (n={ntime} days): cumulative means vs sample length")
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.plot(t_plot, diff_plot, color="C2")
    ax2.axhline(0, color="gray", linestyle=":")
    ax2.set_ylabel("Difference (midpoint − tas) [K]")
    ax2.set_xlabel("Time (last day in cumulative window)")
    ax2.set_title("Cumulative mean difference (→ 0 would mean extrema-midpoint matches tas mean)")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), "tas_convergence_validation.png")
    plt.savefig(out_path)
    plt.close()
    print(f"\nSaved plot: {out_path}")


if __name__ == "__main__":
    _log_path = os.path.join(os.path.dirname(__file__), "validate_tas_convergence_error.log")
    try:
        if not os.path.isdir(DATA_DIR):
            print(f"Data directory not found: {DATA_DIR}")
            raise SystemExit(1)
        main()
    except Exception:
        import traceback

        with open(_log_path, "w") as f:
            f.write(traceback.format_exc())
        print(f"Error logged to {_log_path}")
        raise
