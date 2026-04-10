"""
test8 v3 — Stochastic spatial downscaling with PR intensity–dependent ratio (incl. blend 0.65).

Default `PR_WDF_THRESHOLD_FACTOR` is **1.15** (Bhuwan test8_v2 scale). For tuned wet-day
frequency on Iowa 216×192, use **`test8_v4.py`** (default factor 1.65).

See `../README.md` and repo `4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md`.
"""
from __future__ import annotations

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["DOR_PIPELINE_ID"] = "test8_v3"
os.environ.setdefault("PR_INTENSITY_BLEND", "0.65")
runpy.run_path(os.path.join(_HERE, "_test8_sd_impl.py"), run_name="__main__")
