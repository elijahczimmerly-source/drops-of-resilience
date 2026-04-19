"""
Run product-comparison stack end-to-end: batch benchmarks, climate signal, extended diagnostics,
climatology maps, multi-product plot driver, validation-era DOR plots, NEX rsds diagnostic,
PR texture, provenance.

Requires local memmaps (see config DOR_LOCAL_WRC_CACHE) and **distinct** DOR outputs under
`pipeline/output/test8_v2|v3|v4/...` from `pipeline/scripts/run_three_distinct_outputs.py`
(with INVOCATION.json + run_manifest.json in each folder).

Optional legacy: set DOR_BENCHMARK_SHARED_NPZ_ROOT and DOR_ALLOW_SHARED_BENCHMARK_MIRROR=1
(same NPZs for all pipeline IDs — not a true three-way comparison).

Environment:
  DOR_E2E_SUITES — comma-separated list (default: dor_native,loca2_native,nex_native).
  Steps that are suite-specific set DOR_BENCHMARK_SUITE / `--suite` per iteration.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PC_ROOT / "scripts"
REPO_ROOT = PC_ROOT.parent

DEFAULT_SUITES = ("dor_native", "loca2_native", "nex_native")


def _require_distinct_dor() -> bool:
    import importlib.util

    spec = importlib.util.spec_from_file_location("cfg", PC_ROOT / "config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        p = root / "Stochastic_V8_Hybrid_pr.npz"
        if not p.is_file():
            print(
                f"Missing distinct DOR output for {pid}: {p}\n"
                "Run: python pipeline/scripts/run_three_distinct_outputs.py\n"
                "Or set DOR_ALLOW_SHARED_BENCHMARK_MIRROR=1 with DOR_BENCHMARK_SHARED_NPZ_ROOT."
            )
            return False
    return True


def _run(name: str, args: list[str]) -> int:
    print(f"\n{'='*60}\n>>> {name}\n{'='*60}")
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / args[0]), *args[1:]],
        cwd=str(PC_ROOT),
        env=env,
    )
    if r.returncode != 0:
        print(f"FAILED: {name} (exit {r.returncode})")
    return r.returncode


def _parse_suites() -> tuple[str, ...]:
    raw = os.environ.get("DOR_E2E_SUITES", ",".join(DEFAULT_SUITES)).strip()
    parts = tuple(s.strip().lower() for s in raw.split(",") if s.strip())
    return parts if parts else DEFAULT_SUITES


def main() -> int:
    shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    allow = os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if shared and allow:
        os.environ["DOR_BENCHMARK_SHARED_NPZ_ROOT"] = shared
        os.environ["DOR_PRODUCT_ROOT"] = shared
    elif not _require_distinct_dor():
        return 1
    else:
        v4 = REPO_ROOT / "pipeline" / "output" / "test8_v4" / "experiment_blend0p65"
        if v4.is_dir():
            os.environ.setdefault("DOR_PRODUCT_ROOT", str(v4.resolve()))

    suites = _parse_suites()
    code = 0

    rc = _run("batch_benchmark_pipelines (all suites)", ["batch_benchmark_pipelines.py"])
    if rc != 0:
        code = rc

    for suite in suites:
        os.environ["DOR_BENCHMARK_SUITE"] = suite
        for label, args in (
            (
                f"run_climate_signal_stages [{suite}]",
                ["run_climate_signal_stages.py", "--suite", suite],
            ),
            (
                f"extended_stage_diagnostics [{suite}]",
                ["extended_stage_diagnostics.py", "--suite", suite],
            ),
            (
                f"plot_comparison_driver [{suite}]",
                ["plot_comparison_driver.py", "--all", "--suite", suite],
            ),
        ):
            rc = _run(label, args)
            if rc != 0:
                code = rc

    rc = _run("multivariate_dor_signal.py", ["multivariate_dor_signal.py"])
    if rc != 0:
        code = rc

    for suite in suites:
        rc = _run(
            f"plot_climatology_comparisons [{suite}]",
            ["plot_climatology_comparisons.py", "--suite", suite],
        )
        if rc != 0:
            code = rc

    for suite in suites:
        rc = _run(
            f"plot_validation_period [{suite}]",
            ["plot_validation_period.py", "--suite", suite],
        )
        if rc != 0:
            code = rc

    for suite in ("dor_native", "nex_native"):
        if suite not in suites:
            continue
        rc = _run(
            f"diagnose_nex_rsds [{suite}]",
            ["diagnose_nex_rsds.py", "--suite", suite],
        )
        if rc != 0:
            code = rc

    for suite in suites:
        rc = _run(
            f"pr_texture_investigation [{suite}]",
            ["pr_texture_investigation.py", "--suite", suite],
        )
        if rc != 0:
            code = rc

    rc = _run("collect_benchmark_provenance.py", ["collect_benchmark_provenance.py"])
    if rc != 0:
        code = rc

    print(f"\nE2E suite finished (last non-zero exit: {code})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
