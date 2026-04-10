"""
Phase 2 Step A.2 — summarize `noise_bias` from `dump_noise_bias.py` output (.npz).

Reports per-period and global (land) fractions with bias < 1 vs > 1, and basic moments.
Dividing wet PR by values < 1 increases rain; > 1 decreases it.

Examples:
  python audit_noise_bias.py --npz noise_bias_run.npz
  python audit_noise_bias.py --npz noise_bias_run.npz --mask "\\\\server\\...\\geo_mask.npy" --out-csv audit.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np


def _land_mask(mask_path: str, H: int, W: int) -> np.ndarray:
    m = np.load(mask_path)
    if m.ndim != 2:
        m = m.reshape(m.shape[-2], m.shape[-1])
    if m.shape != (H, W):
        raise ValueError(f"mask shape {m.shape} != ({H},{W})")
    return m == 1


def audit_array(
    noise_bias: np.ndarray,
    land: np.ndarray | None,
) -> tuple[list[dict], dict]:
    """noise_bias: (P, H, W). land: (H,W) bool or None = all finite pixels."""
    P, H, W = noise_bias.shape
    rows: list[dict] = []
    all_vals: list[np.ndarray] = []

    for p in range(P):
        b = noise_bias[p]
        ok = np.isfinite(b)
        if land is not None:
            ok = ok & land
        v = b[ok].astype(np.float64).ravel()
        all_vals.append(v)
        if v.size == 0:
            rows.append(
                {
                    "period": p,
                    "n_pix": 0,
                    "frac_lt_1": float("nan"),
                    "frac_gt_1": float("nan"),
                    "frac_eq_1": float("nan"),
                    "min": float("nan"),
                    "max": float("nan"),
                    "mean": float("nan"),
                    "median": float("nan"),
                }
            )
            continue
        lt = np.sum(v < 1.0)
        gt = np.sum(v > 1.0)
        eq = np.sum(v == 1.0)
        n = float(v.size)
        rows.append(
            {
                "period": p,
                "n_pix": int(v.size),
                "frac_lt_1": lt / n,
                "frac_gt_1": gt / n,
                "frac_eq_1": eq / n,
                "min": float(np.min(v)),
                "max": float(np.max(v)),
                "mean": float(np.mean(v)),
                "median": float(np.median(v)),
            }
        )

    cat = np.concatenate(all_vals) if all_vals else np.array([], dtype=np.float64)
    if cat.size == 0:
        glob = {
            "n_pix": 0,
            "frac_lt_1": float("nan"),
            "frac_gt_1": float("nan"),
            "frac_eq_1": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "mean": float("nan"),
            "median": float("nan"),
        }
    else:
        lt = np.sum(cat < 1.0)
        gt = np.sum(cat > 1.0)
        eq = np.sum(cat == 1.0)
        n = float(cat.size)
        glob = {
            "n_pix": int(cat.size),
            "frac_lt_1": lt / n,
            "frac_gt_1": gt / n,
            "frac_eq_1": eq / n,
            "min": float(np.min(cat)),
            "max": float(np.max(cat)),
            "mean": float(np.mean(cat)),
            "median": float(np.median(cat)),
        }
    return rows, glob


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", required=True, help="Output from dump_noise_bias.py")
    ap.add_argument("--mask", default="", help="geo_mask.npy (optional land-only stats)")
    ap.add_argument("--out-csv", default="", help="Write per-period rows + global summary")
    args = ap.parse_args()

    z = np.load(args.npz)
    if "noise_bias" not in z.files:
        print("ERROR: npz must contain 'noise_bias'", file=sys.stderr)
        return 1
    nb = np.asarray(z["noise_bias"], dtype=np.float64)
    z.close()

    if nb.ndim != 3:
        print(f"ERROR: expected noise_bias (P,H,W), got {nb.shape}", file=sys.stderr)
        return 1

    P, H, W = nb.shape
    land = _land_mask(args.mask, H, W) if args.mask.strip() else None

    rows, glob = audit_array(nb, land)

    print(f"noise_bias shape = {nb.shape}  (P,H,W)")
    if land is not None:
        print("stats: land mask pixels only")
    else:
        print("stats: all finite pixels (no --mask)")
    print()
    print(
        f"{'p':>4} {'n':>8} {'<1':>8} {'>1':>8} {'mean':>10} {'min':>8} {'max':>8}"
    )
    for r in rows:
        print(
            f"{r['period']:4d} {r['n_pix']:8d} {r['frac_lt_1']:8.4f} {r['frac_gt_1']:8.4f} "
            f"{r['mean']:10.5f} {r['min']:8.4f} {r['max']:8.4f}"
        )
    print()
    print(
        "GLOBAL (all periods, stacked):",
        f"n={glob['n_pix']}",
        f"frac<1={glob['frac_lt_1']:.4f}",
        f"frac>1={glob['frac_gt_1']:.4f}",
        f"mean={glob['mean']:.5f}",
        f"median={glob['median']:.5f}",
    )

    if args.out_csv:
        out_path = os.path.abspath(args.out_csv)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "period",
                    "n_pix",
                    "frac_lt_1",
                    "frac_gt_1",
                    "frac_eq_1",
                    "min",
                    "max",
                    "mean",
                    "median",
                ],
            )
            w.writeheader()
            for r in rows:
                w.writerow(r)
            w.writerow({**{"period": "GLOBAL"}, **{k: glob[k] for k in glob}})
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
