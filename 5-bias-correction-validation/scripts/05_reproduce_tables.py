"""A5: Aggregate rankings from 01–03 (Iowa) for cross-check vs publication ordering."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

from bcv_config import METRICS_DIR, METHODS, MODELS

M1 = METRICS_DIR / "01_marginal_checks.csv"
M2 = METRICS_DIR / "02_dependence_checks.csv"
M3 = METRICS_DIR / "03_temporal_checks.csv"


def rank_methods(df: pd.DataFrame, value_col: str, *, ascending: bool = True) -> pd.Series:
    g = df.groupby("method")[value_col].mean()
    return g.rank(ascending=ascending)


def main():
    d1 = pd.read_csv(M1)
    d2 = pd.read_csv(M2)
    d3 = pd.read_csv(M3)
    rows = []
    for method in METHODS:
        r = {"method": method}
        sub = d1[d1["method"] == method]
        r["mean_mae"] = float(sub["mae"].mean()) if len(sub) else np.nan
        r["mean_qq_rmse"] = float(sub["qq_rmse"].mean()) if len(sub) else np.nan
        s2 = d2[d2["method"] == method]
        r["mean_frobenius_dep"] = float(s2["frobenius_spearman_error"].mean()) if len(s2) else np.nan
        s3 = d3[d3["method"] == method]
        r["mean_lag1_err"] = float(s3["lag1_err"].mean()) if len(s3) else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    out["rank_mae"] = out["mean_mae"].rank(ascending=True)
    out["rank_frob"] = out["mean_frobenius_dep"].rank(ascending=True, na_option="keep")
    out["rank_lag1"] = out["mean_lag1_err"].rank(ascending=True)
    out_path = METRICS_DIR / "05_method_rankings_iowa.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
