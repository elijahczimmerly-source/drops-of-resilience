"""
Deprecated entry point — spatial downscaling now lives in `pipeline/scripts/`.

- **`pipeline/scripts/test8_v4.py`** — current line (PR intensity + WDF default 1.65)
- **`pipeline/scripts/test8_v3.py`** — PR intensity with legacy WDF default 1.15

This file delegates to **test8 v4** and keeps outputs under `4-test8-v2-pr-intensity/`
when `DOR_PIPELINE_ROOT` is unset (same as running from the old task folder).

PR noise correlation length is controlled by `DOR_PR_CORR_LENGTH` in `pipeline/scripts/_test8_sd_impl.py`
(see `9-additional-pr-RMSE-fixes/PLAN-CORR-LENGTH-SWEEP.md`).
"""
from __future__ import annotations

import os
import runpy

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_IMPL = os.path.join(_REPO, "pipeline", "scripts", "_test8_sd_impl.py")
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DOR_PIPELINE_ROOT", _ROOT)
os.environ["DOR_PIPELINE_ID"] = "test8_v4"
os.environ.setdefault("PR_INTENSITY_BLEND", "0.65")
runpy.run_path(_IMPL, run_name="__main__")
