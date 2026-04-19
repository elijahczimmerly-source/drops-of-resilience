"""Run climate-signal stages for loca2_native and nex_native (gridmet often run separately)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PC_ROOT / "scripts"


def _run(args: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    print(f"\n>>> {' '.join(args)}")
    subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], cwd=str(PC_ROOT), env=env, check=True)


def main() -> int:
    for s in ("loca2_native", "nex_native"):
        _run(["run_climate_signal_stages.py", "--suite", s])
    print("\nrun_climate_native_suites: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
