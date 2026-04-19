"""Run extended diagnostics, plot driver, multivariate, clim/val plots, diagnose, pr_texture, provenance for all suites."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PC_ROOT / "scripts"
SUITES = ("dor_native", "loca2_native", "nex_native")


def _run(args: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    print(f"\n>>> {' '.join(args)}")
    subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], cwd=str(PC_ROOT), env=env, check=True)


def main() -> int:
    for s in SUITES:
        _run(["extended_stage_diagnostics.py", "--suite", s])
    for s in SUITES:
        _run(["plot_comparison_driver.py", "--all", "--suite", s])
    _run(["multivariate_dor_signal.py"])
    for s in SUITES:
        _run(["plot_climatology_comparisons.py", "--suite", s])
    for s in SUITES:
        _run(["plot_validation_period.py", "--suite", s])
    _run(["diagnose_nex_rsds.py", "--suite", "dor_native"])
    _run(["diagnose_nex_rsds.py", "--suite", "nex_native"])
    for s in SUITES:
        _run(["pr_texture_investigation.py", "--suite", s])
    _run(["collect_benchmark_provenance.py"])
    print("\nrun_native_suite_outputs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
