"""
Quantify PR time-mean splotchiness: spatial std of (sim_mean / obs_mean) on validation days.
Uses 2006–2014 test mask aligned with test8_v2_pr_intensity.

Step 0 / Step 4 of FIX-PR-SPLOTCHINESS-PLAN: CSV + optional PNG; optional seasonal maps;
optional second NPZ for before/after debias comparison.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np
import pandas as pd

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TEST_MASK = np.asarray(DATES_ALL > "2005-12-31", dtype=bool)

# Validation-day indices and calendar months (for seasonal splits)
_VAL_IDX = np.where(TEST_MASK)[0]
_VAL_MONTHS = DATES_ALL[_VAL_IDX].month.values

_SEASONS = (
    ("DJF", (12, 1, 2)),
    ("MAM", (3, 4, 5)),
    ("JJA", (6, 7, 8)),
    ("SON", (9, 10, 11)),
)


def _load_dor_pr(path: str, n_days: int, H: int, W: int) -> np.ndarray:
    d = np.load(path)
    dor = np.asarray(d["data"], dtype=np.float64)
    d.close()
    if dor.shape[0] != n_days:
        raise ValueError(f"DOR days {dor.shape[0]} != expected {n_days}")
    if dor.shape[1:] != (H, W):
        raise ValueError(f"DOR shape {dor.shape[1:]} != ({H},{W})")
    return dor


def _metrics_for_subset(
    dor: np.ndarray,
    obs_pr: np.ndarray,
    day_idx: np.ndarray,
    geo: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    dor_mean = np.nanmean(dor[day_idx], axis=0)
    obs_mean = np.nanmean(obs_pr[day_idx], axis=0)
    ratio_field = dor_mean / (obs_mean + 1e-6)
    flat = ratio_field[geo]
    flat = flat[np.isfinite(flat)]
    splotch = float(np.nanstd(flat)) if len(flat) else float("nan")
    rmean = float(np.nanmean(flat)) if len(flat) else float("nan")
    return splotch, rmean, ratio_field


def _write_plots(ratio_field: np.ndarray, title: str, png_path: str) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(ratio_field, vmin=0.85, vmax=1.15, cmap="RdBu_r")
    plt.colorbar(im, ax=ax, label="DOR_mean / OBS_mean")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


def run_one(
    label: str,
    dor_npz: str,
    targets: str,
    mask_path: str,
    out_dir: str,
    seasonal: bool,
    save_npy: bool,
) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    mask_2d = np.load(mask_path)
    if mask_2d.ndim != 2:
        mask_2d = mask_2d.reshape(mask_2d.shape[-2], mask_2d.shape[-1])
    geo = mask_2d == 1
    H, W = geo.shape
    n_days = len(DATES_ALL)
    targets_mm = np.memmap(targets, dtype="float32", mode="r", shape=(n_days, 6, H, W))
    obs_pr = np.asarray(targets_mm[:, 0], dtype=np.float64)

    dor = _load_dor_pr(dor_npz, n_days, H, W)
    splotch, ratio_mean, ratio_field = _metrics_for_subset(dor, obs_pr, _VAL_IDX, geo)

    rows = [
        {
            "label": label,
            "window": "val_2006_2014_full",
            "splotch_metric_std_ratio": splotch,
            "mean_ratio_field": ratio_mean,
            "n_days": len(_VAL_IDX),
            "dor_npz": os.path.abspath(dor_npz),
        }
    ]

    try:
        _write_plots(
            ratio_field,
            f"Time-mean PR ratio — {label} (2006–2014)",
            os.path.join(out_dir, f"ratio_field_mean_pr_{label}.png"),
        )
        print(f"Wrote ratio map for {label}")
    except Exception as e:
        print(f"(Skipping main PNG for {label}: {e})", file=sys.stderr)

    if save_npy:
        npy_path = os.path.join(out_dir, f"ratio_field_mean_pr_{label}.npy")
        np.save(npy_path, ratio_field.astype(np.float32))
        print(f"Wrote {npy_path}")

    if seasonal:
        for sname, months in _SEASONS:
            sm = np.isin(_VAL_MONTHS, np.array(months, dtype=np.int32))
            day_idx = _VAL_IDX[sm]
            if len(day_idx) < 5:
                continue
            sub = dor[day_idx]
            if not np.any(np.isfinite(sub)):
                continue
            sp, rm, rf = _metrics_for_subset(dor, obs_pr, day_idx, geo)
            rows.append(
                {
                    "label": label,
                    "window": f"val_{sname}",
                    "splotch_metric_std_ratio": sp,
                    "mean_ratio_field": rm,
                    "n_days": len(day_idx),
                    "dor_npz": os.path.abspath(dor_npz),
                }
            )
            try:
                _write_plots(
                    rf,
                    f"Mean PR ratio — {label} {sname} (val days)",
                    os.path.join(out_dir, f"ratio_field_{label}_{sname}.png"),
                )
            except Exception as e:
                print(f"(Skipping seasonal PNG {sname}: {e})", file=sys.stderr)

    return {"rows": rows, "splotch": splotch, "ratio_mean": ratio_mean}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dor-npz", required=True, help="Stochastic_V8_Hybrid_pr.npz")
    ap.add_argument("--targets", required=True, help="gridmet_targets memmap .dat")
    ap.add_argument("--mask", required=True, help="geo_mask.npy")
    ap.add_argument("--out-dir", default=".", help="Output directory")
    ap.add_argument("--label", default="run_a", help="Tag for filenames / CSV label column")
    ap.add_argument("--seasonal", action="store_true", help="DJF/MAM/JJA/SON maps + metrics")
    ap.add_argument("--save-npy", action="store_true", help="Save ratio_field as .npy")
    ap.add_argument(
        "--debiased-npz",
        default="",
        help="Optional second NPZ (e.g. debiased run); writes splotch_compare.csv",
    )
    ap.add_argument(
        "--debiased-label",
        default="debiased",
        help="Label for second run when --debiased-npz is set",
    )
    args = ap.parse_args()

    try:
        r1 = run_one(
            args.label,
            args.dor_npz,
            args.targets,
            args.mask,
            args.out_dir,
            args.seasonal,
            args.save_npy,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    all_rows = list(r1["rows"])
    csv_path = os.path.join(args.out_dir, "splotch_diagnostic.csv")
    if args.debiased_npz:
        try:
            r2 = run_one(
                args.debiased_label,
                args.debiased_npz,
                args.targets,
                args.mask,
                args.out_dir,
                args.seasonal,
                save_npy=False,
            )
            all_rows.extend(r2["rows"])
            cmp_path = os.path.join(args.out_dir, "splotch_compare.csv")
            with open(cmp_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
                w.writeheader()
                w.writerows(all_rows)
            print(f"Wrote {cmp_path}")
            for row in all_rows:
                if row["window"] == "val_2006_2014_full":
                    print(
                        f"  {row['label']}: splotch_metric={row['splotch_metric_std_ratio']:.6f} "
                        f"mean_ratio={row['mean_ratio_field']:.6f}"
                    )
        except Exception as e:
            print(f"ERROR (debiased run): {e}", file=sys.stderr)
            return 1
    else:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"Wrote {csv_path}")
        print(f"  splotch_metric: {r1['splotch']:.6f}")
        print(f"  mean_ratio: {r1['ratio_mean']:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
