"""B3: Master CSV — merge marginal, dependence, temporal, physics summaries."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd

from bcv_config import METHODS, METRICS_DIR, OUT_DIR

OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    d1 = pd.read_csv(METRICS_DIR / "01_marginal_checks.csv")
    d2 = pd.read_csv(METRICS_DIR / "02_dependence_checks.csv")
    d3 = pd.read_csv(METRICS_DIR / "03_temporal_checks.csv")
    d4 = pd.read_csv(METRICS_DIR / "04_physics_checks.csv")

    g1 = d1.groupby(["method", "variable"]).agg(
        mae_mean=("mae", "mean"),
        qq_rmse_mean=("qq_rmse", "mean"),
        p99_bias_mean=("p99_bias", "mean"),
    )
    g1p = g1.unstack("variable")
    g1p.columns = [f"{a}_{b}" for a, b in g1p.columns]

    g2 = d2.groupby("method")["frobenius_spearman_error"].mean().rename("frobenius_spearman_error_mean")

    g3 = d3.groupby(["method", "variable"])["lag1_err"].mean().unstack("variable")
    g3.columns = [f"lag1_err_{c}" for c in g3.columns]

    g4 = d4.groupby("method").agg(
        pre_huss_violation=("pre_frac_huss_gt_qsat", "mean"),
        post_huss_violation=("post_frac_huss_gt_qsat", "mean"),
        pre_tmin_violation=("pre_frac_tmax_lt_tmin", "mean"),
        post_tmin_violation=("post_frac_tmax_lt_tmin", "mean"),
    )

    out = pd.DataFrame(index=METHODS)
    out = out.join(g1p, how="left")
    out = out.join(g2, how="left")
    out = out.join(g3, how="left")
    out = out.join(g4, how="left")
    out.insert(0, "method", out.index)
    out_path = OUT_DIR / "summary_table.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
