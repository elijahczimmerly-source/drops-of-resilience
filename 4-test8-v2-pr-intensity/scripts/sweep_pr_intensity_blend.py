"""
Sweep PR_INTENSITY_BLEND at fixed TEST8_SEED; append PR metrics to blend_sweep_results.csv.

Usage (from this directory, conda env drops-of-resilience):
  python sweep_pr_intensity_blend.py

Env overrides:
  SWEEP_BLEND_VALUES — comma-separated floats, default "0.25,0.35,0.45,0.55,0.65"
  TEST8_SEED         — default 42
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO = _SCRIPTS_DIR.parent.parent
_PIPELINE_SCRIPTS = _REPO / "pipeline" / "scripts"
_MAIN = _PIPELINE_SCRIPTS / "test8_v4.py"
_OUT_ROOT = _REPO / "pipeline" / "output" / "test8_v4"
_RESULTS = _OUT_ROOT / "blend_sweep_results.csv"

_DEFAULT_BLENDS = [0.25, 0.35, 0.45, 0.55, 0.65]


def _tag_for_blend(b: float) -> str:
    s = f"{b:.4f}".rstrip("0").rstrip(".")
    return "blend" + s.replace(".", "p")


def main() -> int:
    raw = os.environ.get("SWEEP_BLEND_VALUES", "").strip()
    if raw:
        blends = [float(x.strip()) for x in raw.split(",") if x.strip()]
    else:
        blends = _DEFAULT_BLENDS

    seed = os.environ.get("TEST8_SEED", "42").strip() or "42"
    py = sys.executable

    _OUT_ROOT.mkdir(parents=True, exist_ok=True)
    need_header = (not _RESULTS.is_file()) or _RESULTS.stat().st_size == 0
    with open(_RESULTS, "a", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        if need_header:
            w.writerow(
                [
                    "PR_INTENSITY_BLEND",
                    "PR_INTENSITY_OUT_TAG",
                    "TEST8_SEED",
                    "pr_Val_KGE",
                    "pr_Val_RMSE_pooled",
                    "pr_Val_Ext99_Bias_pct",
                    "pr_Val_Lag1_Err",
                    "exit_code",
                ]
            )

        for b in blends:
            tag = _tag_for_blend(b)
            env = os.environ.copy()
            env["PR_USE_INTENSITY_RATIO"] = "1"
            env["PR_INTENSITY_BLEND"] = str(b)
            env["PR_INTENSITY_OUT_TAG"] = tag
            env["TEST8_SEED"] = seed
            env["TEST8_MAIN_PERIOD_ONLY"] = "1"
            print(f"\n=== blend={b} tag={tag} ===", flush=True)
            env.setdefault("DOR_PIPELINE_ROOT", str(_REPO / "pipeline"))
            rc = subprocess.call([py, "-u", str(_MAIN)], cwd=str(_PIPELINE_SCRIPTS), env=env)
            t1 = _OUT_ROOT / f"experiment_{tag}" / "V8_Table1_Pooled_Metrics_Stochastic.csv"
            row = [b, tag, seed, "", "", "", "", rc]
            if t1.is_file() and rc == 0:
                import pandas as pd

                df = pd.read_csv(t1)
                pr = df[df["Variable"] == "pr"]
                if len(pr):
                    row[3] = pr.iloc[0].get("Val_KGE", "")
                    row[4] = pr.iloc[0].get("Val_RMSE_pooled", "")
                    row[5] = pr.iloc[0].get("Val_Ext99_Bias%", "")
                    row[6] = pr.iloc[0].get("Val_Lag1_Err", "")
            w.writerow(row)
            fp.flush()
            print(f"  wrote row ext99={row[5]!r} rmse={row[4]!r} kge={row[3]!r}", flush=True)

    print(f"\nDone. Results: {_RESULTS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
