"""A4: Physics correction — BC vs BCPC violation rates and huss P99 shift."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

from bcv_config import METRICS_DIR, METHODS, MODELS, OUT_DIR
from bcv_io import load_bc_historical, qsat_kgkg, slice_to_bc_validation

OUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)


def violation_stats(
    huss: np.ndarray,
    tasmax: np.ndarray,
    tasmin: np.ndarray,
) -> dict:
    qs = qsat_kgkg(tasmax)
    v_huss = huss > qs
    v_t = tasmax < tasmin
    n = huss.size
    return {
        "frac_huss_gt_qsat": float(np.mean(v_huss)),
        "frac_tmax_lt_tmin": float(np.mean(v_t)),
        "n_points": int(n),
    }


def load_triplet(
    model: str,
    method: str,
    *,
    bcpc: bool,
    physics_corrected: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    out = {}
    for var in ("huss", "tasmax", "tasmin"):
        loaded = load_bc_historical(
            model, method, var, bcpc=bcpc, physics_corrected=physics_corrected
        )
        if loaded is None:
            return None
        data, time, _, _ = loaded
        dval, _ = slice_to_bc_validation(data, time)
        out[var] = dval
    return out["huss"], out["tasmax"], out["tasmin"]


def main():
    rows = []
    for model in MODELS:
        for method in METHODS:
            pre = load_triplet(model, method, bcpc=False, physics_corrected=False)
            post = load_triplet(model, method, bcpc=True, physics_corrected=True)
            if pre is None or post is None:
                continue
            h0, tx0, tn0 = pre
            h1, tx1, tn1 = post
            st_pre = violation_stats(h0, tx0, tn0)
            st_post = violation_stats(h1, tx1, tn1)
            rows.append(
                {
                    "model": model,
                    "method": method,
                    **{f"pre_{k}": v for k, v in st_pre.items()},
                    **{f"post_{k}": v for k, v in st_post.items()},
                    "huss_p99_pre": float(np.nanpercentile(h0, 99)),
                    "huss_p99_post": float(np.nanpercentile(h1, 99)),
                }
            )
    df = pd.DataFrame(rows)
    out = METRICS_DIR / "04_physics_checks.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
