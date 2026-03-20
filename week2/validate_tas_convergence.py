"""
Validate: average of (tasmax + tasmin)/2 converges to average of daily means (tas) over time.

In hydrology we often use only daily max and min. The claim is that over long periods,
  mean_over_days( (Tmax + Tmin)/2 )  ≈  mean_over_days( T_daily_mean ),
and that as you add more time, these converge.

This script loads tas (daily mean), tasmax, tasmin and:
  1. Compares the overall mean of midpoints vs mean of tas over the full period.
  2. Shows convergence: cumulative mean of (max+min)/2 vs cumulative mean of tas
     as we add more days (they should get closer with more data).
"""

import glob
import os
import numpy as np
import xarray as xr

xr.set_options(use_new_combine_kwarg_defaults=True)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = r"\\abe-cylo\public\CMIP\Download\km100"

# Single 30-day file (fallback)
FILE_SUFFIX = "day_EC-Earth3P_highresSST-present_r1i1p1f1_gr_20150401-20150430.nc"

# --- Long timeframe: EC-Earth3P highresSST-future r1i1p1f1, yearly files 2015–2049 (35 years) ---
# Set to a suffix string to use exactly 3 files (one year). Set to None to use the glob below.
LONG_TIMEFRAME_SINGLE_SUFFIX = None

# Glob for longest possible: 35 yearly files per variable (2015–2049), concatenated = 35 years of days.
LONG_TIMEFRAME_GLOB = "{var}_day_EC-Earth3P_highresSST-future_r1i1p1f1_gr_*.nc"
MAX_FILES = None  # no limit: use all 35 years


def nc_path(variable: str) -> str:
    return f"{DATA_DIR}\\{variable}_{FILE_SUFFIX}"


def _glob_paths(variable: str):
    pattern = os.path.join(DATA_DIR, LONG_TIMEFRAME_GLOB.format(var=variable))
    paths = sorted(glob.glob(pattern))
    if MAX_FILES is not None and len(paths) > MAX_FILES:
        paths = paths[:MAX_FILES]
    return paths


def load_tas_triple():
    """Load tas, tasmax, tasmin. Prefer one long file per variable (3 files total) when possible."""
    # 1) Explicit single long file per variable: exactly 3 files
    if LONG_TIMEFRAME_SINGLE_SUFFIX:
        paths = {
            v: os.path.join(DATA_DIR, f"{v}_{LONG_TIMEFRAME_SINGLE_SUFFIX}")
            for v in ("tas", "tasmax", "tasmin")
        }
        for v, p in paths.items():
            if not os.path.isfile(p):
                raise FileNotFoundError(f"Missing {v}: {p}")
        print("  Long timeframe: 1 tas, 1 tasmax, 1 tasmin file (3 files total)")
        ds_tas = xr.open_dataset(paths["tas"])
        ds_max = xr.open_dataset(paths["tasmax"])
        ds_min = xr.open_dataset(paths["tasmin"])
        return xr.merge([ds_tas, ds_max, ds_min], compat="override")

    # 2) Glob: if exactly one file per variable, still only 3 files; else concatenate many
    if LONG_TIMEFRAME_GLOB:
        tas_files = _glob_paths("tas")
        tmax_files = _glob_paths("tasmax")
        tmin_files = _glob_paths("tasmin")
        if tas_files and tmax_files and tmin_files:
            n_tas, n_max, n_min = len(tas_files), len(tmax_files), len(tmin_files)
            if n_tas == 1 and n_max == 1 and n_min == 1:
                print("  Long timeframe: 1 tas, 1 tasmax, 1 tasmin file (3 files total)")
                ds_tas = xr.open_dataset(tas_files[0])
                ds_max = xr.open_dataset(tmax_files[0])
                ds_min = xr.open_dataset(tmin_files[0])
                return xr.merge([ds_tas, ds_max, ds_min], compat="override")
            print(f"  Long timeframe: {n_tas} tas, {n_max} tasmax, {n_min} tasmin files (concatenating)")
            ds_tas = xr.open_mfdataset(
                tas_files, combine="by_coords", data_vars="minimal"
            )
            ds_max = xr.open_mfdataset(
                tmax_files, combine="by_coords", data_vars="minimal"
            )
            ds_min = xr.open_mfdataset(
                tmin_files, combine="by_coords", data_vars="minimal"
            )
            return xr.merge([ds_tas, ds_max, ds_min], compat="override")

    # 3) Fallback: single 30-day file
    paths = {v: nc_path(v) for v in ("tas", "tasmax", "tasmin")}
    for v, p in paths.items():
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Missing {v}: {p}")
    print("  Using single 30-day file per variable (3 files total)")
    ds_tas = xr.open_dataset(paths["tas"])
    ds_max = xr.open_dataset(paths["tasmax"])
    ds_min = xr.open_dataset(paths["tasmin"])
    return xr.merge([ds_tas, ds_max, ds_min], compat="override")


def main():
    print("Loading tas, tasmax, tasmin...")
    ds = load_tas_triple()
    tas = ds["tas"]
    tasmax = ds["tasmax"]
    tasmin = ds["tasmin"]

    # Daily "midpoint" of max and min (what we get without daily mean)
    midpoint = (tasmax + tasmin) / 2.0

    ntime = tas.sizes["time"]
    time_min, time_max = tas.time.values.min(), tas.time.values.max()
    print(f"  Time steps: {ntime}  ({time_min} to {time_max})")

    # --- 1. Full-period comparison ---
    # Reduce time first, then space, to avoid MemoryError (never materialize full 4D array)
    mean_tas = tas.mean(dim="time")
    mean_midpoint = midpoint.mean(dim="time")
    overall_mean_of_means = float(mean_tas.mean())
    overall_mean_of_midpoints = float(mean_midpoint.mean())
    diff_overall = overall_mean_of_midpoints - overall_mean_of_means

    print("\n--- Full period ---")
    print(f"  Mean of daily means (tas):     {overall_mean_of_means:.4f} K")
    print(f"  Mean of (tasmax+tasmin)/2:     {overall_mean_of_midpoints:.4f} K")
    print(f"  Difference:                    {diff_overall:.4f} K")
    print(f"  Relative diff (vs mean tas):   {100 * diff_overall / overall_mean_of_means:.4f}%")

    # --- 2. Convergence as we add more time: cumulative means ---
    # cumulative mean up to day t: for each t, mean over days 0..t
    time_idx = tas.time
    n = xr.DataArray(
        np.arange(1, ntime + 1, dtype=float),
        dims=["time"],
        coords={"time": time_idx},
    )  # 1, 2, ..., ntime — broadcast across lat, lon

    # At one point (Ames, IA) to get a clean time series
    lat_ames, lon_ames = 42.03, 360 - 93.65
    tas_ames = tas.sel(lat=lat_ames, lon=lon_ames, method="nearest")
    mid_ames = midpoint.sel(lat=lat_ames, lon=lon_ames, method="nearest")
    cummean_tas_ames = tas_ames.cumsum(dim="time") / n
    cummean_mid_ames = mid_ames.cumsum(dim="time") / n
    diff_ames = cummean_mid_ames - cummean_tas_ames

    print("\n--- Cumulative difference at one point (Ames, IA) ---")
    i_quarter = max(1, ntime // 4)
    i_half = max(1, ntime // 2)
    print(f"  After 1 day:     diff = {float(diff_ames.isel(time=0)):.4f} K")
    if ntime > 1:
        print(f"  After ~25%:      diff = {float(diff_ames.isel(time=i_quarter - 1)):.4f} K  (day {i_quarter})")
    if ntime > 2:
        print(f"  After ~50%:      diff = {float(diff_ames.isel(time=i_half - 1)):.4f} K  (day {i_half})")
    print(f"  After full run:  diff = {float(diff_ames.isel(time=ntime - 1)):.4f} K  (day {ntime})")
    print("  (At a single point, sampling can make this vary; globally the full-period difference is tiny.)")

    # --- Plots ---
    # For very long runs, thin points so the plot stays readable (max ~2000 points)
    step = max(1, ntime // 2000)
    t_plot = time_idx.values[::step]
    tas_plot = cummean_tas_ames.values[::step]
    mid_plot = cummean_mid_ames.values[::step]
    diff_plot = diff_ames.values[::step]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Top: cumulative mean of tas vs cumulative mean of (max+min)/2 at Ames
    ax1 = axes[0]
    ax1.plot(t_plot, tas_plot, label="Mean of daily means (tas)", color="C0")
    ax1.plot(t_plot, mid_plot, label="Mean of (tasmax+tasmin)/2", color="C1", linestyle="--")
    ax1.set_ylabel("Cumulative mean temperature (K)")
    ax1.legend()
    ax1.set_title(f"Convergence at Ames, IA (n={ntime} days): as more days are included, the two averages get closer")
    ax1.grid(True, alpha=0.3)

    # Bottom: difference between the two cumulative means over time (should tend toward 0)
    ax2 = axes[1]
    ax2.plot(t_plot, diff_plot, color="C2")
    ax2.axhline(0, color="gray", linestyle=":")
    ax2.set_ylabel("Difference (midpoint avg − tas avg) [K]")
    ax2.set_xlabel("Time (last day in cumulative window)")
    ax2.set_title("Difference between the two cumulative means (converges toward 0 with more data)")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), "tas_convergence_validation.png")
    plt.savefig(out_path)
    plt.close()
    print(f"\nSaved plot: {out_path}")

    # Optional: spatial map of difference (full-period mean of midpoint minus mean of tas)
    fig2, ax = plt.subplots(figsize=(10, 5))
    (mean_midpoint - mean_tas).plot(ax=ax, cmap="RdBu_r", center=0)
    ax.set_title("Full period: (mean of (max+min)/2) − (mean of tas) [K]")
    map_path = os.path.join(os.path.dirname(__file__), "tas_midpoint_vs_mean_spatial_diff.png")
    plt.savefig(map_path)
    plt.close()
    print(f"Saved map: {map_path}")


if __name__ == "__main__":
    _log_path = os.path.join(os.path.dirname(__file__), "validate_tas_convergence_error.log")
    try:
        if not os.path.isdir(DATA_DIR):
            print(f"Data directory not found: {DATA_DIR}")
            raise SystemExit(1)
        main()
    except Exception as e:
        import traceback
        with open(_log_path, "w") as f:
            f.write(traceback.format_exc())
        print(f"Error logged to {_log_path}")
        raise
