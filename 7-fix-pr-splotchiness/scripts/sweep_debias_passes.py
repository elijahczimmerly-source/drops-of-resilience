"""
Phase 2 Step A.3 / B1 — sweep `DOR_NOISE_DEBIAS_N_PASSES` and record `split_half_corr` from
`dump_noise_bias.py` (cheap vs full Table1; needs same memmaps as test8).

Example:
  python sweep_debias_passes.py --experiment-root R:/.../4-test8-v2-pr-intensity \\
    --seed 42 --passes 6,12,24,48 --out-csv sweep_passes.csv \\
    --cmip-hist ... --gridmet-targets ... --geo-mask ...
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experiment-root", required=True)
    ap.add_argument("--seed", type=int, required=True, help="DOR_NOISE_DEBIAS_SEED")
    ap.add_argument(
        "--passes",
        default="6,12,24,32,48",
        help="Comma-separated integers for DOR_NOISE_DEBIAS_N_PASSES",
    )
    ap.add_argument("--var", choices=["pr", "wind"], default="pr")
    ap.add_argument("--out-csv", default="", help="Append one row per pass count")
    ap.add_argument("--cmip-hist", default="")
    ap.add_argument("--gridmet-targets", default="")
    ap.add_argument("--geo-mask", default="")
    ap.add_argument("--geo-static", default="")
    args = ap.parse_args()

    dump_py = os.path.join(os.path.dirname(__file__), "dump_noise_bias.py")
    pass_list = []
    for part in args.passes.split(","):
        part = part.strip()
        if not part:
            continue
        pass_list.append(int(part))
    if not pass_list:
        print("ERROR: empty --passes", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for n_pass in pass_list:
        env = os.environ.copy()
        env["DOR_NOISE_DEBIAS_N_PASSES"] = str(n_pass)
        if args.cmip_hist:
            env["DOR_TEST8_CMIP6_HIST_DAT"] = args.cmip_hist
        if args.gridmet_targets:
            env["DOR_TEST8_GRIDMET_TARGETS_DAT"] = args.gridmet_targets
        if args.geo_mask:
            env["DOR_TEST8_GEO_MASK_NPY"] = args.geo_mask
        if args.geo_static:
            env["DOR_TEST8_GEO_STATIC_NPY"] = args.geo_static

        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            outp = os.path.join(td, f"bias_{n_pass}.npz")
            cmd = [
                sys.executable,
                dump_py,
                "--experiment-root",
                args.experiment_root,
                "--var",
                args.var,
                "--seed",
                str(args.seed),
                "--out",
                outp,
            ]
            if args.cmip_hist:
                cmd.extend(["--cmip-hist", args.cmip_hist])
            if args.gridmet_targets:
                cmd.extend(["--gridmet-targets", args.gridmet_targets])
            if args.geo_mask:
                cmd.extend(["--geo-mask", args.geo_mask])
            if args.geo_static:
                cmd.extend(["--geo-static", args.geo_static])

            r = subprocess.call(cmd, env=env)
            if r != 0:
                return r
            elapsed = time.perf_counter() - t0
            z = np.load(outp)
            sh = float(z["split_half_corr"]) if "split_half_corr" in z.files else float("nan")
            n_saved = int(z["n_passes"]) if "n_passes" in z.files else n_pass
            z.close()

        row = {
            "n_passes": n_pass,
            "n_passes_saved": n_saved,
            "split_half_corr": sh,
            "elapsed_sec": round(elapsed, 3),
            "seed": args.seed,
            "variable": args.var,
        }
        rows.append(row)
        print(
            f"N_PASSES={n_pass:3d}  split_half_corr={sh:.6g}  elapsed={elapsed:.1f}s",
            flush=True,
        )

    if args.out_csv:
        path = os.path.abspath(args.out_csv)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        new_file = not os.path.isfile(path)
        with open(path, "a" if not new_file else "w", newline="", encoding="utf-8") as f:
            fieldnames = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if new_file:
                w.writeheader()
            for row in rows:
                w.writerow(row)
        print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
