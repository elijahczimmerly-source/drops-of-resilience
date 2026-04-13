"""
test8 v2 — Bhuwan-parity-oriented preset (no PR-intensity blend default; noise debias off; pr corr 35).

This entry point runs the **same fork** as v3/v4: [`_test8_sd_impl.py`](_test8_sd_impl.py), not a byte-for-byte
copy of Bhuwan's server `test8_v2.py`. Defaults below align with documented Bhuwan test8_v2 Iowa behavior
(WDF 1.65, pr spatial noise correlation length 35 px). Results may still differ if Bhuwan changed spatial
autocorrelation weights locally after upload (see repo `dor-info.md`).

For PR-intensity sweeps and legacy WDF 1.15, use **`test8_v3.py`**. For tuned production with blend 0.65,
use **`test8_v4.py`**.

See [`../README.md`](../README.md).
"""
from __future__ import annotations

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))

os.environ["DOR_PIPELINE_ID"] = "test8_v2"
# Closer to Bhuwan's server script (Elijah's debias remains available via DOR_MULTIPLICATIVE_NOISE_DEBIAS=1).
os.environ.setdefault("DOR_MULTIPLICATIVE_NOISE_DEBIAS", "0")
# Documented test8_v2 pr noise scale vs fork default 15 px when unset in `_test8_sd_impl.process_variable`.
os.environ.setdefault("DOR_PR_CORR_LENGTH", "35")
# Do not set PR_INTENSITY_BLEND here (v3 sets 0.65); leave impl default 1.0 when PR_USE_INTENSITY_RATIO=0.

runpy.run_path(os.path.join(_HERE, "_test8_sd_impl.py"), run_name="__main__")
