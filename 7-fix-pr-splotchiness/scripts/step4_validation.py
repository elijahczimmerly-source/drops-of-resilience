"""
Step 4 checklist driver: splotch diagnostics + Table1 diff (when paths exist).

Usage (after you have two full pipeline output folders and shared memmaps):

  python step4_validation.py \\
    --baseline-dir .../experiment_blend0p65 \\
    --debiased-dir .../experiment_blend0p65_debiased \\
    --targets .../data/gridmet_targets_19810101-20141231.dat \\
    --mask .../data/geo_mask.npy \\
    --out-dir 7-fix-pr-splotchiness/output/validation_run

Requires: diagnose_splotchiness.py, validate_fix.py on the path (same directory).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline-dir", required=True, help="Folder with Stochastic_V8_Hybrid_pr.npz + V8_Table1*.csv")
    ap.add_argument("--debiased-dir", required=True, help="Debiased run output folder")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--baseline-label", default="baseline")
    ap.add_argument("--debiased-label", default="debiased")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    diag = os.path.join(here, "diagnose_splotchiness.py")
    val = os.path.join(here, "validate_fix.py")

    b_npz = os.path.join(args.baseline_dir, "Stochastic_V8_Hybrid_pr.npz")
    d_npz = os.path.join(args.debiased_dir, "Stochastic_V8_Hybrid_pr.npz")
    b_t1 = os.path.join(args.baseline_dir, "V8_Table1_Pooled_Metrics_Stochastic.csv")
    d_t1 = os.path.join(args.debiased_dir, "V8_Table1_Pooled_Metrics_Stochastic.csv")

    for p in (b_npz, d_npz, b_t1, d_t1, args.targets, args.mask):
        if not os.path.isfile(p):
            print(f"Missing required file: {p}", file=sys.stderr)
            return 1

    os.makedirs(args.out_dir, exist_ok=True)

    cmd_diag = [
        sys.executable,
        diag,
        "--dor-npz",
        b_npz,
        "--debiased-npz",
        d_npz,
        "--targets",
        args.targets,
        "--mask",
        args.mask,
        "--out-dir",
        args.out_dir,
        "--label",
        args.baseline_label,
        "--debiased-label",
        args.debiased_label,
        "--seasonal",
        "--save-npy",
    ]
    print("Running:", " ".join(cmd_diag))
    r = subprocess.call(cmd_diag)
    if r != 0:
        return r

    out_csv = os.path.join(args.out_dir, "step4_table1_diff.csv")
    cmd_val = [
        sys.executable,
        val,
        "--baseline",
        b_t1,
        "--debiased",
        d_t1,
        "--out",
        out_csv,
    ]
    print("Running:", " ".join(cmd_val))
    return subprocess.call(cmd_val)


if __name__ == "__main__":
    raise SystemExit(main())
