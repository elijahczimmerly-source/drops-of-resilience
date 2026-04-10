"""
test8 v4 — Same as test8 v3, plus tuned **PR_WDF_THRESHOLD_FACTOR** default **1.65**
(Regridded_Iowa 216×192, blend 0.65, debias off; see `8-WDF-overprediction-fix/`).

This is the recommended production entry point unless you need legacy WDF scaling (v3).
"""
from __future__ import annotations

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["DOR_PIPELINE_ID"] = "test8_v4"
os.environ.setdefault("PR_INTENSITY_BLEND", "0.65")
runpy.run_path(os.path.join(_HERE, "_test8_sd_impl.py"), run_name="__main__")
