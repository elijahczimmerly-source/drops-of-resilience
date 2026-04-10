"""
Compare V8_Table1_Pooled_Metrics_Stochastic.csv from a baseline run vs debiased run.
Prints merged table and per-column deltas (deb - base) for Val_* metrics.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", required=True, help="V8_Table1 CSV (e.g. pre-debias)")
    ap.add_argument("--debiased", required=True, help="V8_Table1 CSV (e.g. post-debias)")
    ap.add_argument("--out", default="", help="Optional: write merged comparison CSV")
    args = ap.parse_args()

    for p in (args.baseline, args.debiased):
        if not os.path.isfile(p):
            print(f"Missing file: {p}", file=sys.stderr)
            return 1

    b = pd.read_csv(args.baseline)
    d = pd.read_csv(args.debiased)
    merged = b.merge(d, on="Variable", suffixes=("_base", "_deb"))
    val_cols = [c for c in merged.columns if c.endswith("_deb") and c.startswith("Val_")]
    for cdeb in val_cols:
        cbase = cdeb.replace("_deb", "_base")
        if cbase in merged.columns:
            short = cdeb.replace("Val_", "").replace("_deb", "")
            merged[f"d_{short}"] = merged[cdeb] - merged[cbase]

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(merged.to_string(index=False))
    if args.out:
        ddir = os.path.dirname(os.path.abspath(args.out))
        if ddir:
            os.makedirs(ddir, exist_ok=True)
        merged.to_csv(args.out, index=False)
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
