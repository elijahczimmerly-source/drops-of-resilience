"""
Dump noise_bias tensor after calibrate + calibrate_noise_bias (Step 5 / debugging).

Requires the same memmaps as `pipeline/scripts/_test8_sd_impl.py` (set `DOR_PIPELINE_ROOT` or legacy
`DOR_TEST8_V2_PR_INTENSITY_ROOT` to the folder that contains `data/`).

Example:
  python dump_noise_bias.py --experiment-root C:/path/to/pipeline-or-task-folder --seed 111 --out noise_bias_a.npz

Set the same env as your pipeline run before invoking (e.g. PR_USE_INTENSITY_RATIO, PR_INTENSITY_BLEND,
PR_INTENSITY_OUT_TAG, TEST8_SEED, DOR_NOISE_DEBIAS_N_PASSES) — they are read when the impl module loads.

Output .npz keys: noise_bias, variable, seed, n_passes, H, W, N_PERIODS, split_half_corr.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--experiment-root",
        required=True,
        help="Folder containing data/ with cmip6_inputs_* and gridmet_targets_* .dat files",
    )
    ap.add_argument("--var", choices=["pr", "wind"], default="pr")
    ap.add_argument("--seed", type=int, required=True, help="DOR_NOISE_DEBIAS_SEED for this dump")
    ap.add_argument("--out", required=True, help="Output .npz with noise_bias array")
    ap.add_argument("--cmip-hist", default="", help="Absolute path to cmip6_inputs_19810101-20141231.dat")
    ap.add_argument("--gridmet-targets", default="", help="Absolute path to gridmet_targets .dat")
    ap.add_argument("--geo-mask", default="", help="Absolute path to geo_mask.npy")
    ap.add_argument("--geo-static", default="", help="Optional geo_static.npy")
    args = ap.parse_args()

    root = os.path.abspath(args.experiment_root)
    os.environ["DOR_PIPELINE_ROOT"] = root
    os.environ["DOR_TEST8_V2_PR_INTENSITY_ROOT"] = root
    os.environ.setdefault("DOR_PIPELINE_ID", "test8_v4")
    os.environ["DOR_NOISE_DEBIAS_SEED"] = str(args.seed)
    if args.cmip_hist:
        os.environ["DOR_TEST8_CMIP6_HIST_DAT"] = args.cmip_hist
    if args.gridmet_targets:
        os.environ["DOR_TEST8_GRIDMET_TARGETS_DAT"] = args.gridmet_targets
    if args.geo_mask:
        os.environ["DOR_TEST8_GEO_MASK_NPY"] = args.geo_mask
    if args.geo_static:
        os.environ["DOR_TEST8_GEO_STATIC_NPY"] = args.geo_static

    repo = Path(__file__).resolve().parents[2]
    impl = repo / "pipeline" / "scripts" / "_test8_sd_impl.py"
    spec = importlib.util.spec_from_file_location("dor_test8_sd_impl", impl)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot load {impl}", file=sys.stderr)
        return 1
    t8 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t8)

    import numpy as np
    import torch

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    vname = args.var
    v_idx = t8.VARS_INTERNAL.index(vname)
    if vname == "wind":
        corr_len = 50.0
    else:
        corr_len = 35.0

    inputs = np.memmap(
        t8.F_INPUTS, dtype="float32", mode="r", shape=(t8.N_DAYS, 6, t8.H, t8.W)
    )
    targets = np.memmap(
        t8.F_TARGETS, dtype="float32", mode="r", shape=(t8.N_DAYS, 6, t8.H, t8.W)
    )
    model = t8.StochasticSpatialDisaggregatorMultiplicative(
        v_idx, vname, correlation_length=corr_len, device=device
    )
    model.calibrate(inputs, targets, t8.DATES_ALL)
    model.calibrate_noise_bias(inputs, targets, t8.DATES_ALL)
    sh = getattr(model, "_debias_split_half_corr", None)
    try:
        n_passes_saved = int(os.environ.get("DOR_NOISE_DEBIAS_N_PASSES", "6").strip())
    except ValueError:
        n_passes_saved = 6
    np.savez_compressed(
        args.out,
        noise_bias=model.noise_bias,
        variable=vname,
        seed=args.seed,
        n_passes=np.int32(n_passes_saved),
        H=t8.H,
        W=t8.W,
        N_PERIODS=t8.N_PERIODS,
        split_half_corr=np.float64(sh) if sh is not None else np.float64(np.nan),
    )
    print(f"Wrote {os.path.abspath(args.out)} shape={model.noise_bias.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
