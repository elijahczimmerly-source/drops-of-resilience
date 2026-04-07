"""Run validation scripts in plan order (01–08). Expect ~30+ minutes over network NPZ I/O."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
scripts = [
    "01_marginal_checks.py",
    "02_dependence_checks.py",
    "03_temporal_checks.py",
    "04_physics_checks.py",
    "05_reproduce_tables.py",
    "06_iowa_validation_plots.py",
    "07_physics_plots.py",
    "08_summary_table.py",
]

for name in scripts:
    path = ROOT / name
    print("===", name, "===")
    r = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
    if r.returncode != 0:
        sys.exit(r.returncode)
print("All steps completed.")
