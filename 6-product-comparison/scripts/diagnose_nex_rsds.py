"""
Pin down NEX-GDDP rsds vs GridMET srad mean bias (Iowa, 2006-2014).

Writes under product-comparison/output/:
  - nex_rsds_metadata.txt
  - nex_rsds_bias_monthly.csv
  - nex_rsds_bias_by_obs_quartile.csv
  - nex_rsds_bias_native_vs_targetgrid.csv
  - figures/nex_rsds_bias_map_targetgrid.png
  - figures/nex_rsds_monthly_bias.png
  - figures/nex_rsds_domain_mean_timeseries.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
from align import align_to_obs_with_dates
from grid_target import load_target_grid
from load_nex import load_nex_on_grid
from load_obs import load_obs_validation


def _nex_rsds_paths() -> list[str]:
    subdir = cfg.NEX_SUBDIR["rsds"]
    pat = cfg.NEX_FILE_PATTERN["rsds"]
    paths = []
    for year in range(2006, 2015):
        p = cfg.NEX_ROOT / cfg.GCM_FOLDER / "historical" / subdir / pat.format(year=year)
        if not p.is_file():
            raise FileNotFoundError(p)
        paths.append(str(p))
    return paths


def _write_metadata(out_dir: Path) -> None:
    lines = []
    p_nex = _nex_rsds_paths()[0]
    with xr.open_dataset(p_nex) as ds:
        lines.append(f"NEX file: {p_nex}\n")
        lines.append(f"rsds attrs: {dict(ds.rsds.attrs)}\n")
        lines.append(f"global attrs (subset): { {k: ds.attrs.get(k) for k in list(ds.attrs)[:12]} }\n")

    z = np.load(cfg.CROPPED_GRIDMET / "Cropped_srad_2006.npz")
    lines.append(f"\nGridMET NPZ: Cropped_srad_2006.npz keys {z.files}\n")
    if "data" in z.files:
        lines.append(f"GridMET srad sample mean (2006 daily): {float(np.nanmean(z['data']))}\n")
    out = out_dir / "nex_rsds_metadata.txt"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {out}")


def _bias_on_target_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex]:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, obs_dates = load_obs_validation("rsds")
    nex, nt = load_nex_on_grid("rsds", lat_tgt, lon_tgt)
    n_a, o_a, dates = align_to_obs_with_dates(nex, nt, obs, obs_dates)
    diff = n_a - o_a
    return diff, o_a, n_a, dates


def _bias_native_grid() -> float:
    """
    Interpolate GridMET obs onto NEX Iowa subset grid each day; mean(NEX_native - obs_interp_native).
    If this ~ target-grid pooled bias, interpolation is not the main story.
    """
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, obs_dates = load_obs_validation("rsds")

    lon_obs = np.asarray(lon_tgt, dtype=float)
    lat_obs = np.asarray(lat_tgt, dtype=float)

    diffs = []
    for year in range(2006, 2015):
        p = cfg.NEX_ROOT / cfg.GCM_FOLDER / "historical" / "rsds" / cfg.NEX_FILE_PATTERN["rsds"].format(
            year=year
        )
        with xr.open_dataset(p) as ds:
            da = ds["rsds"]
            lon_360 = (lon_obs + 360.0) % 360.0
            lon_lo = float(lon_360.min()) - 1.0
            lon_hi = float(lon_360.max()) + 1.0
            sub = da.sel(
                lat=slice(cfg.LAT_MIN, cfg.LAT_MAX),
                lon=slice(lon_lo, lon_hi),
            )
            lat_n = np.asarray(sub.lat.values, dtype=float)
            lon_n = np.asarray(sub.lon.values, dtype=float)
            LATN, LONN = np.meshgrid(lat_n, lon_n, indexing="ij")
            LONN_W = np.where(LONN > 180.0, LONN - 360.0, LONN)

            times = pd.to_datetime(sub.time.values).normalize()
            d_obs = {pd.Timestamp(t).normalize(): i for i, t in enumerate(obs_dates)}
            for ti, t in enumerate(times):
                tn = pd.Timestamp(t).normalize()
                if tn not in d_obs:
                    continue
                oi = d_obs[tn]
                o2 = obs[oi]
                da_o = xr.DataArray(
                    o2,
                    dims=("lat", "lon"),
                    coords={"lat": lat_obs, "lon": lon_obs},
                )
                o_on_nex = da_o.interp(
                    lat=xr.DataArray(LATN, dims=("yn", "xn")),
                    lon=xr.DataArray(LONN_W, dims=("yn", "xn")),
                    method="linear",
                )
                nex_native = np.asarray(sub.isel(time=ti).values, dtype=np.float64)
                dnative = nex_native - np.asarray(o_on_nex.values, dtype=np.float64)
                diffs.append(dnative.reshape(-1))

    if not diffs:
        return float("nan")
    all_d = np.concatenate(diffs)
    return float(np.nanmean(all_d))


def main() -> int:
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_dir = cfg.OUTPUT_DIR / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    _write_metadata(cfg.OUTPUT_DIR)

    diff, obs_a, nex_a, dates = _bias_on_target_grid()
    pooled_bias = float(np.nanmean(diff))
    pooled_rmse = float(np.sqrt(np.nanmean(diff**2)))
    obs_mean = float(np.nanmean(obs_a))
    nex_mean = float(np.nanmean(nex_a))

    # Monthly domain-mean bias
    dfm = pd.DataFrame(
        {
            "date": dates,
            "domain_mean_obs": np.nanmean(obs_a, axis=(1, 2)),
            "domain_mean_nex": np.nanmean(nex_a, axis=(1, 2)),
            "domain_mean_diff": np.nanmean(diff, axis=(1, 2)),
        }
    )
    dfm["month"] = dfm["date"].dt.month
    monthly = dfm.groupby("month").agg(
        bias_mean=("domain_mean_diff", "mean"),
        bias_std=("domain_mean_diff", "std"),
        n_days=("domain_mean_diff", "count"),
    ).reset_index()
    mp = cfg.OUTPUT_DIR / "nex_rsds_bias_monthly.csv"
    monthly.to_csv(mp, index=False)
    print(f"Wrote {mp}")

    # Quartiles of domain-mean observed srad
    dom_obs = dfm["domain_mean_obs"].to_numpy()
    qs = np.nanpercentile(dom_obs, [25, 50, 75])
    bins = [
        ("q1_dullest", dom_obs <= qs[0]),
        ("q2", (dom_obs > qs[0]) & (dom_obs <= qs[1])),
        ("q3", (dom_obs > qs[1]) & (dom_obs <= qs[2])),
        ("q4_brightest", dom_obs > qs[2]),
    ]
    rows = []
    for name, m in bins:
        if not np.any(m):
            continue
        dsub = diff[m]
        rows.append(
            {
                "regime": name,
                "pooled_bias": float(np.nanmean(dsub)),
                "pooled_rmse": float(np.sqrt(np.nanmean(dsub**2))),
                "n_days": int(np.sum(m)),
            }
        )
    qdf = pd.DataFrame(rows)
    qp = cfg.OUTPUT_DIR / "nex_rsds_bias_by_obs_quartile.csv"
    qdf.to_csv(qp, index=False)
    print(f"Wrote {qp}")

    native_bias = _bias_native_grid()
    summary = {
        "pooled_mean_bias_Wm2_target_grid": pooled_bias,
        "pooled_rmse_Wm2_target_grid": pooled_rmse,
        "mean_obs_Wm2": obs_mean,
        "mean_nex_Wm2": nex_mean,
        "relative_bias_pct_of_obs_mean": 100.0 * pooled_bias / (obs_mean + 1e-9),
        "pooled_mean_bias_Wm2_native_nex_grid": native_bias,
    }
    sp = cfg.OUTPUT_DIR / "nex_rsds_bias_native_vs_targetgrid.json"
    sp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {sp}")
    print(json.dumps(summary, indent=2))

    # Figures
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with np.errstate(invalid="ignore", divide="ignore"):
        bias_map = np.nanmean(diff, axis=0)
    vmax = np.nanpercentile(np.abs(bias_map), 98)
    vmax = max(vmax, 1.0)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(bias_map, origin="upper", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_title("Mean NEX − GridMET srad (W m⁻²), 2006–2014")
    plt.colorbar(im, ax=ax, label="W m⁻²")
    fp = fig_dir / "nex_rsds_bias_map_targetgrid.png"
    fig.savefig(fp, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {fp}")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(monthly["month"], monthly["bias_mean"], yerr=monthly["bias_std"], capsize=3, color="#4c72b0")
    ax.axhline(0, color="k", linewidth=0.8)
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Month")
    ax.set_ylabel("Mean domain (NEX − obs) W m⁻²")
    ax.set_title("Monthly mean bias (target grid)")
    fig.tight_layout()
    fp2 = fig_dir / "nex_rsds_monthly_bias.png"
    fig.savefig(fp2, dpi=150)
    plt.close(fig)
    print(f"Wrote {fp2}")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dfm["date"], dfm["domain_mean_obs"], label="GridMET domain mean", alpha=0.7, lw=0.8)
    ax.plot(dfm["date"], dfm["domain_mean_nex"], label="NEX domain mean", alpha=0.7, lw=0.8)
    ax.set_ylabel("W m⁻²")
    ax.legend()
    ax.set_title("Domain-mean daily shortwave: GridMET vs NEX (Iowa crop)")
    fig.tight_layout()
    fp3 = fig_dir / "nex_rsds_domain_mean_timeseries.png"
    fig.savefig(fp3, dpi=150)
    plt.close(fig)
    print(f"Wrote {fp3}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
