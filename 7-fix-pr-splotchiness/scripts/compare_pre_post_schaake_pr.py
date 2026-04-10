"""
Phase 2 Step A.1 — same splotch diagnostic as `diagnose_splotchiness.py` on:
  * pre-Schaake PR stack (from `DOR_PHASE2_SAVE_PRE_SCHAAKE_PR=1` run → Phase2_pre_schaake_pr_main_stochastic.npz)
  * post-Schaake PR (`Stochastic_V8_Hybrid_pr.npz` in the same OUT_DIR)

If pre-Schaake splotch is much better than post-Schaake, Schaake reordering may be dominating the
spatial artifact; if both are similar, debias vs Schaake ordering is a weaker lever.

Example:
  python compare_pre_post_schaake_pr.py \\
    --pre  .../experiment_plan_debias/Phase2_pre_schaake_pr_main_stochastic.npz \\
    --post .../experiment_plan_debias/Stochastic_V8_Hybrid_pr.npz \\
    --targets \\\\...\\gridmet_targets_19810101-20141231.dat \\
    --mask \\\\...\\geo_mask.npy
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np
import pandas as pd

# Same calendar as diagnose_splotchiness / test8
DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TEST_MASK = np.asarray(DATES_ALL > "2005-12-31", dtype=bool)
_VAL_IDX = np.where(TEST_MASK)[0]


def _load_pr(path: str, n_days: int, H: int, W: int) -> np.ndarray:
    d = np.load(path)
    x = np.asarray(d["data"], dtype=np.float64)
    d.close()
    if x.shape[0] != n_days:
        raise ValueError(f"PR days {x.shape[0]} != expected {n_days}")
    if x.shape[1:] != (H, W):
        raise ValueError(f"PR shape {x.shape[1:]} != ({H},{W})")
    return x


def _metrics(
    dor: np.ndarray,
    obs_pr: np.ndarray,
    day_idx: np.ndarray,
    geo: np.ndarray,
) -> tuple[float, float]:
    dor_mean = np.nanmean(dor[day_idx], axis=0)
    obs_mean = np.nanmean(obs_pr[day_idx], axis=0)
    ratio_field = dor_mean / (obs_mean + 1e-6)
    flat = ratio_field[geo]
    flat = flat[np.isfinite(flat)]
    splotch = float(np.nanstd(flat)) if len(flat) else float("nan")
    rmean = float(np.nanmean(flat)) if len(flat) else float("nan")
    return splotch, rmean


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pre", required=True, help="Phase2_pre_schaake_pr_main_stochastic.npz")
    ap.add_argument("--post", required=True, help="Stochastic_V8_Hybrid_pr.npz (post-Schaake)")
    ap.add_argument("--targets", required=True, help="gridmet_targets .dat memmap")
    ap.add_argument("--mask", required=True, help="geo_mask.npy")
    ap.add_argument("--out-csv", default="", help="Optional single-row comparison CSV")
    args = ap.parse_args()

    mask_2d = np.load(args.mask)
    if mask_2d.ndim != 2:
        mask_2d = mask_2d.reshape(mask_2d.shape[-2], mask_2d.shape[-1])
    geo = mask_2d == 1
    H, W = geo.shape
    n_days = len(DATES_ALL)

    targets_mm = np.memmap(
        args.targets, dtype="float32", mode="r", shape=(n_days, 6, H, W)
    )
    obs_pr = np.asarray(targets_mm[:, 0], dtype=np.float64)

    pre = _load_pr(args.pre, n_days, H, W)
    post = _load_pr(args.post, n_days, H, W)

    sp_pre, mn_pre = _metrics(pre, obs_pr, _VAL_IDX, geo)
    sp_post, mn_post = _metrics(post, obs_pr, _VAL_IDX, geo)

    print("2006–2014 validation window (same as diagnose_splotchiness)")
    print(f"  pre-Schaake   splotch_metric={sp_pre:.6f}  mean_ratio={mn_pre:.6f}")
    print(f"  post-Schaake  splotch_metric={sp_post:.6f}  mean_ratio={mn_post:.6f}")
    print(f"  delta (post - pre) splotch = {sp_post - sp_pre:+.6f}")

    if args.out_csv:
        path = os.path.abspath(args.out_csv)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "label_pre",
                    "label_post",
                    "splotch_pre",
                    "splotch_post",
                    "mean_ratio_pre",
                    "mean_ratio_post",
                    "delta_splotch",
                ],
            )
            w.writeheader()
            w.writerow(
                {
                    "label_pre": os.path.basename(args.pre),
                    "label_post": os.path.basename(args.post),
                    "splotch_pre": sp_pre,
                    "splotch_post": sp_post,
                    "mean_ratio_pre": mn_pre,
                    "mean_ratio_post": mn_post,
                    "delta_splotch": sp_post - sp_pre,
                }
            )
        print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
