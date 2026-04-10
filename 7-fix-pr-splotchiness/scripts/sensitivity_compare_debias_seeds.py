"""
Step 5 (plan): statistical checks on empirical noise_bias.

1. **determinism** (default): two dumps with the *same* DOR_NOISE_DEBIAS_SEED must yield identical
   `noise_bias` (validates RNG save/restore and reproducibility).

2. **split-half** (optional): one dump; `split_half_corr` in the NPZ compares mean bias from first vs
   second half of Monte Carlo passes (raise DOR_NOISE_DEBIAS_N_PASSES if this is low — diagnostic only).

3. **two-seed**: legacy comparison of two different seeds (high variance unless N_PASSES is large).

Example:
  python sensitivity_compare_debias_seeds.py --experiment-root ... --mask ... --cmip-hist ... --gridmet-targets ...
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experiment-root", required=True)
    ap.add_argument("--mask", required=True, help="geo_mask.npy")
    ap.add_argument("--cmip-hist", default="", help="cmip6_inputs_19810101-20141231.dat")
    ap.add_argument("--gridmet-targets", default="", help="gridmet_targets .dat")
    ap.add_argument("--geo-static", default="", help="optional geo_static.npy")
    ap.add_argument("--var", choices=["pr", "wind"], default="pr")
    ap.add_argument(
        "--mode",
        choices=["determinism", "split-half", "two-seed"],
        default="determinism",
    )
    ap.add_argument("--seed-a", type=int, default=111111)
    ap.add_argument("--seed-b", type=int, default=918273645)
    ap.add_argument(
        "--min-split-half",
        type=float,
        default=0.99,
        help="split-half mode only: fail if split_half_corr below this",
    )
    ap.add_argument(
        "--min-correlation",
        type=float,
        default=0.80,
        help="two-seed mode only",
    )
    args = ap.parse_args()

    if args.cmip_hist:
        os.environ["DOR_TEST8_CMIP6_HIST_DAT"] = args.cmip_hist
    if args.gridmet_targets:
        os.environ["DOR_TEST8_GRIDMET_TARGETS_DAT"] = args.gridmet_targets
    if args.geo_static:
        os.environ["DOR_TEST8_GEO_STATIC_NPY"] = args.geo_static
    os.environ["DOR_TEST8_GEO_MASK_NPY"] = args.mask

    dump_py = os.path.join(os.path.dirname(__file__), "dump_noise_bias.py")

    def _dump_cmd(seed: int, outp: str) -> list:
        cmd = [
            sys.executable,
            dump_py,
            "--experiment-root",
            args.experiment_root,
            "--var",
            args.var,
            "--seed",
            str(seed),
            "--out",
            outp,
        ]
        if args.cmip_hist:
            cmd.extend(["--cmip-hist", args.cmip_hist])
        if args.gridmet_targets:
            cmd.extend(["--gridmet-targets", args.gridmet_targets])
        if args.mask:
            cmd.extend(["--geo-mask", args.mask])
        if args.geo_static:
            cmd.extend(["--geo-static", args.geo_static])
        return cmd

    env = os.environ.copy()

    if args.mode == "determinism":
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "a.npz")
            p2 = os.path.join(td, "b.npz")
            for outp in (p1, p2):
                r = subprocess.call(_dump_cmd(args.seed_a, outp), env=env)
                if r != 0:
                    return r
            z1 = np.load(p1)
            z2 = np.load(p2)
            a, b = z1["noise_bias"], z2["noise_bias"]
            sh = float(z1["split_half_corr"])
            z1.close()
            z2.close()
            mad = float(np.max(np.abs(a - b)))
            print(f"Determinism: max_abs_diff(noise_bias) = {mad:.3e} (same seed {args.seed_a})")
            print(f"split_half_corr (informational): {sh:.6f}")
            if mad > 0:
                print("FAIL: noise_bias differs between two runs with identical seed", file=sys.stderr)
                return 1
        return 0

    if args.mode == "split-half":
        with tempfile.TemporaryDirectory() as td:
            outp = os.path.join(td, "debias.npz")
            r = subprocess.call(_dump_cmd(args.seed_a, outp), env=env)
            if r != 0:
                return r
            z = np.load(outp)
            sh = float(z["split_half_corr"])
            z.close()
            print(f"split_half_corr: {sh:.6f}")
            if sh < args.min_split_half or not np.isfinite(sh):
                print(
                    f"FAIL: split_half_corr {sh:.6f} < {args.min_split_half} "
                    f"(increase DOR_NOISE_DEBIAS_N_PASSES; now {env.get('DOR_NOISE_DEBIAS_N_PASSES', '6')})",
                    file=sys.stderr,
                )
                return 2
        return 0

    # two-seed
    with tempfile.TemporaryDirectory() as td:
        a_npz = os.path.join(td, "a.npz")
        b_npz = os.path.join(td, "b.npz")
        for seed, outp in [(args.seed_a, a_npz), (args.seed_b, b_npz)]:
            r = subprocess.call(_dump_cmd(seed, outp), env=env)
            if r != 0:
                print(f"dump_noise_bias failed (exit {r})", file=sys.stderr)
                return r

        nb1 = np.load(a_npz)["noise_bias"].astype(np.float64)
        nb2 = np.load(b_npz)["noise_bias"].astype(np.float64)
        mask = np.load(args.mask)
        if mask.ndim != 2:
            mask = mask.reshape(mask.shape[-2], mask.shape[-1])
        land = (mask == 1)[None, :, :]
        mflat = np.broadcast_to(land, nb1.shape).ravel()
        nb1 = nb1.ravel()
        nb2 = nb2.ravel()
        ok = mflat & np.isfinite(nb1) & np.isfinite(nb2)
        r = float(np.corrcoef(nb1[ok], nb2[ok])[0, 1])
        mad = float(np.nanmean(np.abs(nb1[ok] - nb2[ok])))
        print(f"Pixel-wise correlation (land, two seeds): {r:.6f}")
        print(f"Mean abs diff (land): {mad:.6f}")
        if r < args.min_correlation:
            print(
                f"WARN: correlation {r:.6f} < {args.min_correlation}. "
                "Use --mode determinism or raise DOR_NOISE_DEBIAS_N_PASSES.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
