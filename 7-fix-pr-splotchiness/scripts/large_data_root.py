"""Resolve root for large artifacts (memmaps, regrid cache, test8 NPZ).

Priority:
  1. Env `DROPS_LARGE_DATA_ROOT` (explicit path)
  2. `D:\\drops-resilience-data` if drive D: exists and is writable
  3. Fallback: `7-fix-pr-splotchiness/output` under the repo
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def large_data_root() -> Path:
    env = (os.environ.get("DROPS_LARGE_DATA_ROOT") or "").strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    d = Path(r"D:\drops-resilience-data")
    try:
        if d.drive and Path(d.drive + os.sep).exists():
            d.mkdir(parents=True, exist_ok=True)
            return d
    except OSError:
        pass
    return _REPO / "7-fix-pr-splotchiness" / "output"


def ec_cmip6_build_dir() -> Path:
    return large_data_root() / "ec_cmip6_build"
