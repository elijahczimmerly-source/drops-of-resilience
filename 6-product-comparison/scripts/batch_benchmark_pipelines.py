"""Run run_benchmark.py for test8_v2–v4 default output dirs and optional native suites."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PC_ROOT / "scripts"
sys.path.insert(0, str(PC_ROOT))
import config as cfg

_DEFAULT_SUITES = ("dor_native", "loca2_native", "nex_native")


def _runs() -> list[tuple[str, Path]]:
    """
    Distinct pipeline output dirs only (see pipeline/scripts/run_three_distinct_outputs.py).
    Optional legacy mirror: set DOR_BENCHMARK_SHARED_NPZ_ROOT **and** DOR_ALLOW_SHARED_BENCHMARK_MIRROR=1
    (metrics will be identical across IDs — not a three-way product comparison).
    """
    shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    allow = os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if shared and allow:
        root = Path(shared)
        if not root.is_dir():
            print(f"DOR_BENCHMARK_SHARED_NPZ_ROOT is not a directory: {root}")
            return []
        print("WARNING: using shared NPZ mirror for all pipeline IDs (not distinct products).")
        return [(pid, root) for pid, _ in cfg.DOR_DEFAULT_OUTPUTS.items()]
    return list(cfg.DOR_DEFAULT_OUTPUTS.items())


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch benchmark for test8_v2–v4")
    ap.add_argument(
        "--suites",
        type=str,
        default=",".join(_DEFAULT_SUITES),
        help=f"Comma-separated DOR_BENCHMARK_SUITE values (default: {','.join(_DEFAULT_SUITES)}).",
    )
    ap.add_argument(
        "--require-distinct-dor-roots",
        action="store_true",
        help="Fail if DOR_BENCHMARK_SHARED_NPZ_ROOT is set (same tree for all pipeline IDs).",
    )
    args = ap.parse_args()
    shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    if args.require_distinct_dor_roots and shared:
        print(
            "ERROR: --require-distinct-dor-roots but DOR_BENCHMARK_SHARED_NPZ_ROOT is set; "
            "unset it or run full pipeline outputs per test8_v*."
        )
        return 2

    suites = tuple(s.strip() for s in args.suites.split(",") if s.strip())

    for suite in suites:
        for pid, dor_root in _runs():
            if not dor_root.is_dir():
                print(f"Skip {pid}: missing {dor_root}")
                continue
            env = os.environ.copy()
            env["DOR_PIPELINE_ID"] = pid
            env["DOR_PRODUCT_ROOT"] = str(dor_root)
            env["DOR_BENCHMARK_SUITE"] = suite
            print(f"=== benchmark suite={suite} {pid} ===")
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_benchmark.py")],
                cwd=str(PC_ROOT),
                env=env,
            )
            if r.returncode != 0:
                return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
