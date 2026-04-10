"""
Shim: spatial downscaling lives under repo `pipeline/scripts/`.

Forwards to **`test8_v4.py`** (see repo `pipeline/README.md`).
"""
from __future__ import annotations

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_TARGET = os.path.join(_REPO, "pipeline", "scripts", "test8_v4.py")

if __name__ == "__main__":
    sys.stderr.write(
        "NOTE: use pipeline/scripts/test8_v4.py (or test8_v3.py). Forwarding to:\n"
        f"  {_TARGET}\n\n"
    )
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-u", _TARGET, *sys.argv[1:]],
            cwd=os.path.dirname(_TARGET),
            env={**os.environ, "DOR_PIPELINE_ROOT": os.environ.get("DOR_PIPELINE_ROOT", _REPO + os.sep + "pipeline")},
        )
    )
