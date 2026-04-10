"""
Mean PR on the **coarse GCM grid** (OTBC + physics-corrected), **before** `regrid_to_gridmet.py`.

Expected layout (from `crop_bc_mpi_local.py` / server `Physics_Corrected_MPI`): a `.npz` with
`pr` shaped `(time, nlat, nlon)`, 1-D `lat`, `lon`, and `time` (or infer time from length).

Typical server file (adjust if your tree differs):
  \\\\abe-cylo\\modelsdev\\Projects\\WRC_DOR\\Bias_Correction\\Data\\Physics_Corrected_MPI\\
  mv_otbc_historical_GROUP-huss-pr-rsds-tasmax-tasmin-wind_METHOD-mv_otbc_historical_18500101-20141231\\
  pr_GROUP-huss-pr-rsds-tasmax-tasmin-wind_METHOD-mv_otbc_historical_18500101-20141231_physics_corrected.npz

Or a local `Cropped_*pr*_..._historical*.npz` from `crop_bc_mpi_local.py` output.

Example:
  python plot_coarse_gcm_mean_pr.py \\
    --npz "\\\\server\\...\\pr_..._physics_corrected.npz" \\
    --out figures/pr-splotch-side-by-side/MPI_OTBC_coarse_pr_mean_2006-2014.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

VAR_YLABEL = "Mean pr (mm day⁻¹)"


def _load_pr_lat_lon_time(path: Path):
    with np.load(path) as z:
        keys = set(z.files)
        if "pr" in keys:
            pr = np.asarray(z["pr"], dtype=np.float64)
            vkey = "pr"
        elif "data" in keys and "lat" in keys:
            pr = np.asarray(z["data"], dtype=np.float64)
            vkey = "data"
        else:
            skip = {"lat", "lon", "time", "years", "elevation"}
            cand = [k for k in keys if k not in skip]
            if not cand:
                raise ValueError(f"No data key in {path}; keys={keys}")
            vkey = cand[0]
            pr = np.asarray(z[vkey], dtype=np.float64)
        lat = np.asarray(z["lat"], dtype=np.float64)
        lon = np.asarray(z["lon"], dtype=np.float64)
        if "time" in keys:
            time_raw = z["time"]
        else:
            time_raw = None
    return pr, lat, lon, time_raw, vkey


def _decode_times(
    n_time: int,
    time_raw,
    *,
    days_origin: str,
    assume_daily_origin: str,
) -> pd.DatetimeIndex:
    if time_raw is not None:
        tr = np.asarray(time_raw)
        # datetime64[s] etc.: do not use np.issubdtype(..., np.datetime64) — unreliable across NumPy versions
        if getattr(tr.dtype, "kind", None) == "M" or tr.dtype == object:
            return pd.DatetimeIndex(pd.to_datetime(tr))
        if np.issubdtype(tr.dtype, np.floating) or np.issubdtype(tr.dtype, np.integer):
            origin = pd.Timestamp(days_origin)
            return pd.DatetimeIndex(
                origin + pd.to_timedelta(tr.ravel(), unit="D")
            )

    if assume_daily_origin:
        return pd.date_range(assume_daily_origin, periods=n_time, freq="D")

    # Heuristic: 1981–2014 daily only (test8 main period length)
    if n_time == 12418:
        return pd.date_range("1981-01-01", periods=n_time, freq="D")

    raise ValueError(
        f"Cannot infer dates for n_time={n_time}: missing `time` in npz — "
        f"pass --assume-daily-origin YYYY-MM-DD (file start date)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", required=True, type=Path, help="Coarse pr .npz (OTBC physics-corrected or Cropped_*)")
    ap.add_argument("--out", required=True, type=Path, help="Output PNG")
    ap.add_argument(
        "--val-start",
        default="2006-01-01",
        help="Validation window start (inclusive)",
    )
    ap.add_argument(
        "--val-end",
        default="2014-12-31",
        help="Validation window end (inclusive)",
    )
    ap.add_argument(
        "--assume-daily-origin",
        default="",
        help="If time axis is missing: assume n daily steps from this date (YYYY-MM-DD)",
    )
    ap.add_argument(
        "--days-origin",
        default="1850-01-01",
        help="If `time` is numeric days, day 0 = this date (default 1850-01-01)",
    )
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    pr, lat, lon, time_raw, vkey = _load_pr_lat_lon_time(args.npz)
    if pr.ndim != 3:
        print(f"ERROR: expected pr ndim 3, got {pr.shape}", file=sys.stderr)
        return 1

    n_time = pr.shape[0]
    try:
        dates = _decode_times(
            n_time,
            time_raw,
            days_origin=args.days_origin,
            assume_daily_origin=args.assume_daily_origin.strip(),
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(
            "  Fix: pass e.g. --assume-daily-origin 1850-01-01 if `time` is absent",
            file=sys.stderr,
        )
        return 1

    v0 = pd.Timestamp(args.val_start)
    v1 = pd.Timestamp(args.val_end)
    mask = (dates >= v0) & (dates <= v1)
    if not np.any(mask):
        print("ERROR: validation mask empty — check dates vs file coverage", file=sys.stderr)
        return 1

    with np.errstate(invalid="ignore"):
        mean_pr = np.nanmean(pr[mask], axis=0)

    finite = mean_pr[np.isfinite(mean_pr)]
    vmin = float(np.percentile(finite, 2)) if finite.size else 0.0
    vmax = float(np.percentile(finite, 98)) if finite.size else 1.0
    if vmax <= vmin:
        vmax = vmin + 1e-6
    vmin = max(0.0, vmin)

    lon2d, lat2d = np.meshgrid(lon, lat)

    fig, ax = plt.subplots(figsize=(7.5, 6), constrained_layout=True)
    pcm = ax.pcolormesh(
        lon2d,
        lat2d,
        mean_pr,
        shading="auto",
        cmap="Blues",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")
    ax.set_title(
        f"Coarse GCM pr (OTBC+physics), {vkey}\n"
        f"mean {args.val_start}–{args.val_end} (pre–regrid_to_gridmet)"
    )
    # Longitude degrees are not physical length; avoid 1:1 aspect for lat/lon.
    ax.set_aspect("auto")
    fig.colorbar(pcm, ax=ax, label=VAR_YLABEL, shrink=0.8)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi)
    plt.close(fig)
    print(f"Wrote {args.out}  (n_days averaged={int(mask.sum())}, grid {mean_pr.shape})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
