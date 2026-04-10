"""
Diagnose where the pr splotches come from.

Plots four panels for a chosen time window (default: JJA 2006-2014):
  1. GridMET observed mean pr (the "truth")
  2. GCM input mean pr (bilinearly interpolated to 4km, before any ratio)
  3. spatial_ratio mean (the calibrated correction field, averaged over the window's semi-monthly periods)
  4. DOR output mean pr (= GCM * ratio * noise, but noise ≈ 1 in the mean)

If the splotches appear in panel 2 (GCM), the downscaler can't fix them.
If the splotches appear in panel 3 (ratio) but not panel 2, the ratio calibration is the source.
If neither panel 2 nor 3 has them, the noise/WDF interaction is the source (unlikely given Attempt 4).

Usage:
  python diagnose_splotch_source.py

Requires env vars pointing to UNC memmaps (same as test8_v2_pr_intensity.py):
  DOR_TEST8_CMIP6_HIST_DAT, DOR_TEST8_GRIDMET_TARGETS_DAT, DOR_TEST8_GEO_MASK_NPY
Or a DOR_TEST8_PR_DATA_DIR / DOR_TEST8_V2_PR_INTENSITY_ROOT with data/ subfolder.

Also needs a DOR output NPZ:
  --dor-npz path/to/Stochastic_V8_Hybrid_pr.npz
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --- dates and masks (same as test8_v2_pr_intensity.py) ---
DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TRAIN_MASK = np.asarray(DATES_ALL <= "2005-12-31", dtype=bool)
TEST_MASK = np.asarray(DATES_ALL > "2005-12-31", dtype=bool)

JJA_MONTHS = {6, 7, 8}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dor-npz", required=True,
                    help="Stochastic_V8_Hybrid_pr.npz from a pipeline run")
    ap.add_argument("--out-dir", default=".",
                    help="Where to write the output PNG")
    ap.add_argument("--season", default="JJA",
                    help="Season to analyze: DJF, MAM, JJA, SON, or ALL (annual)")
    args = ap.parse_args()

    season_months = {
        "DJF": {12, 1, 2}, "MAM": {3, 4, 5},
        "JJA": {6, 7, 8}, "SON": {9, 10, 11},
        "ALL": set(range(1, 13)),
    }
    months = season_months.get(args.season.upper())
    if months is None:
        print(f"Unknown season: {args.season}", file=sys.stderr)
        return 1

    # --- resolve data paths (same logic as test8_v2_pr_intensity.py) ---
    _root = os.environ.get("DOR_TEST8_V2_PR_INTENSITY_ROOT", "").strip()
    _data = os.environ.get("DOR_TEST8_PR_DATA_DIR", "").strip()
    if not _root:
        _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    base_dir = os.path.abspath(_data if _data else os.path.join(_root, "4-test8-v2-pr-intensity", "data"))

    f_inputs = os.environ.get("DOR_TEST8_CMIP6_HIST_DAT", "").strip() or \
               os.path.join(base_dir, "cmip6_inputs_19810101-20141231.dat")
    f_targets = os.environ.get("DOR_TEST8_GRIDMET_TARGETS_DAT", "").strip() or \
                os.path.join(base_dir, "gridmet_targets_19810101-20141231.dat")
    f_mask = os.environ.get("DOR_TEST8_GEO_MASK_NPY", "").strip() or \
             os.path.join(base_dir, "geo_mask.npy")

    for p, name in [(f_inputs, "cmip6_inputs"), (f_targets, "gridmet_targets"), (f_mask, "geo_mask")]:
        if not os.path.exists(p):
            print(f"Cannot find {name}: {p}", file=sys.stderr)
            return 1

    # --- load mask and determine grid size ---
    mask_2d = np.load(f_mask)
    if mask_2d.ndim != 2:
        mask_2d = mask_2d.reshape(mask_2d.shape[-2], mask_2d.shape[-1])
    land = mask_2d == 1
    H, W = land.shape
    N = len(DATES_ALL)

    print(f"Grid: {H}x{W}, {N} days, season={args.season} months={sorted(months)}")

    # --- load memmaps ---
    inputs = np.memmap(f_inputs, dtype='float32', mode='r', shape=(N, 6, H, W))
    targets = np.memmap(f_targets, dtype='float32', mode='r', shape=(N, 6, H, W))

    # pr is variable index 0
    gcm_pr = np.asarray(inputs[:, 0, :, :], dtype=np.float64)
    obs_pr = np.asarray(targets[:, 0, :, :], dtype=np.float64)

    # --- build day masks ---
    val_month_mask = np.array([TEST_MASK[i] and DATES_ALL[i].month in months
                               for i in range(N)], dtype=bool)
    train_month_mask = np.array([TRAIN_MASK[i] and DATES_ALL[i].month in months
                                 for i in range(N)], dtype=bool)

    print(f"  Validation days in {args.season}: {val_month_mask.sum()}")
    print(f"  Training days in {args.season}: {train_month_mask.sum()}")

    # --- compute means ---
    gcm_val_mean = np.nanmean(gcm_pr[val_month_mask], axis=0)
    obs_val_mean = np.nanmean(obs_pr[val_month_mask], axis=0)
    gcm_train_mean = np.nanmean(gcm_pr[train_month_mask], axis=0)
    obs_train_mean = np.nanmean(obs_pr[train_month_mask], axis=0)

    # spatial_ratio as the downscaler would compute it (training period)
    ratio_train = obs_train_mean / (gcm_train_mean + 1e-4)
    ratio_train = np.clip(ratio_train, 0.05, 20.0)

    # what the downscaler produces (deterministic, no noise): GCM_val * ratio_train
    dor_deterministic = gcm_val_mean * ratio_train

    # load actual DOR output
    d = np.load(args.dor_npz)
    dor_full = np.asarray(d["data"], dtype=np.float64)
    d.close()
    dor_stoch_mean = np.nanmean(dor_full[val_month_mask], axis=0)

    # mask non-land
    for arr in [gcm_val_mean, obs_val_mean, ratio_train, dor_deterministic, dor_stoch_mean,
                gcm_train_mean, obs_train_mean]:
        arr[~land] = np.nan

    # --- also compute the GCM shift: how did the GCM's spatial pattern change? ---
    gcm_shift = gcm_val_mean / (gcm_train_mean + 1e-4)
    gcm_shift[~land] = np.nan

    os.makedirs(args.out_dir, exist_ok=True)

    # --- PLOT 1: Four-panel decomposition ---
    # Use same color scale (2nd-98th percentile of obs) for panels 1,2,4,5
    obs_flat = obs_val_mean[land]
    vmin, vmax = np.nanpercentile(obs_flat, [2, 98])

    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    fig.suptitle(f"PR splotch source decomposition — {args.season} mean 2006–2014", fontsize=14)

    # Panel 1: GridMET observed
    im = axes[0, 0].imshow(obs_val_mean, vmin=vmin, vmax=vmax, cmap="Blues")
    axes[0, 0].set_title("GridMET observed (truth)")
    plt.colorbar(im, ax=axes[0, 0], label="mm/day", shrink=0.8)

    # Panel 2: GCM input (bilinear-interpolated, before ratio)
    im = axes[0, 1].imshow(gcm_val_mean, vmin=vmin, vmax=vmax, cmap="Blues")
    axes[0, 1].set_title("GCM input (4km bilinear, before ratio)")
    plt.colorbar(im, ax=axes[0, 1], label="mm/day", shrink=0.8)

    # Panel 3: spatial_ratio (training period)
    r_flat = ratio_train[land]
    rvmin, rvmax = np.nanpercentile(r_flat, [2, 98])
    im = axes[0, 2].imshow(ratio_train, vmin=rvmin, vmax=rvmax, cmap="RdBu_r")
    axes[0, 2].set_title("spatial_ratio (obs_train / gcm_train)")
    plt.colorbar(im, ax=axes[0, 2], label="ratio", shrink=0.8)

    # Panel 4: DOR deterministic (gcm_val * ratio_train, no noise)
    im = axes[1, 0].imshow(dor_deterministic, vmin=vmin, vmax=vmax, cmap="Blues")
    axes[1, 0].set_title("GCM_val × ratio_train (deterministic)")
    plt.colorbar(im, ax=axes[1, 0], label="mm/day", shrink=0.8)

    # Panel 5: Actual DOR stochastic output
    im = axes[1, 1].imshow(dor_stoch_mean, vmin=vmin, vmax=vmax, cmap="Blues")
    axes[1, 1].set_title("DOR stochastic output (actual)")
    plt.colorbar(im, ax=axes[1, 1], label="mm/day", shrink=0.8)

    # Panel 6: GCM spatial shift (val_mean / train_mean)
    gs_flat = gcm_shift[land]
    gs_vmin, gs_vmax = np.nanpercentile(gs_flat, [2, 98])
    # center on 1.0
    gs_ext = max(abs(gs_vmin - 1.0), abs(gs_vmax - 1.0))
    im = axes[1, 2].imshow(gcm_shift, vmin=1.0 - gs_ext, vmax=1.0 + gs_ext, cmap="RdBu_r")
    axes[1, 2].set_title("GCM shift (gcm_val_mean / gcm_train_mean)")
    plt.colorbar(im, ax=axes[1, 2], label="ratio", shrink=0.8)

    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])

    fig.tight_layout()
    out_path = os.path.join(args.out_dir, f"splotch_source_{args.season}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Wrote {out_path}")

    # --- Print summary stats ---
    print(f"\n--- {args.season} summary (land pixels) ---")
    print(f"  GridMET val mean:       {np.nanmean(obs_flat):.3f} mm/day")
    print(f"  GCM val mean:           {np.nanmean(gcm_val_mean[land]):.3f} mm/day")
    print(f"  DOR deterministic mean: {np.nanmean(dor_deterministic[land]):.3f} mm/day")
    print(f"  DOR stochastic mean:    {np.nanmean(dor_stoch_mean[land]):.3f} mm/day")
    print(f"  spatial_ratio mean:     {np.nanmean(ratio_train[land]):.3f}")
    print(f"  GCM shift mean:         {np.nanmean(gcm_shift[land]):.3f}")
    print(f"  GCM shift std:          {np.nanstd(gcm_shift[land]):.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
