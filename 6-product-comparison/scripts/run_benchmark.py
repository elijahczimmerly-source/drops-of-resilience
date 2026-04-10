"""
Compare DOR (blend0.65), LOCA2, and NEX-GDDP vs GridMET on 2006–2014.
"""
from __future__ import annotations

import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd

import config as cfg
from benchmark_io import LOCA_VARS, load_aligned_stacks
from metrics import calculate_pooled_metrics

_METRIC_KEYS = [
    "KGE",
    "RMSE_pooled",
    "Bias",
    "Ext99_Bias%",
    "Lag1_Err",
    "WDF_Obs%",
    "WDF_Sim%",
]


def _flatten_metrics(prefix: str, m: dict, var: str) -> dict:
    out = {}
    for k in _METRIC_KEYS:
        if k.startswith("WDF") and var != "pr":
            out[f"{prefix}_{k}"] = np.nan
            continue
        key = f"Val_{k}"
        out[f"{prefix}_{k}"] = m.get(key, np.nan)
    return out


def run() -> pd.DataFrame:
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.FIG_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for var in cfg.VARS:
        st = load_aligned_stacks(var)
        obs_a, dor_a = st.obs, st.dor

        row: dict = {"variable": var}
        row.update(
            _flatten_metrics("DOR", calculate_pooled_metrics(obs_a, dor_a, var, label="Val"), var)
        )

        if st.loca2 is not None:
            row.update(
                _flatten_metrics(
                    "LOCA2", calculate_pooled_metrics(obs_a, st.loca2, var, label="Val"), var
                )
            )
        else:
            for k in _METRIC_KEYS:
                row[f"LOCA2_{k}"] = np.nan

        row.update(
            _flatten_metrics("NEX", calculate_pooled_metrics(obs_a, st.nex, var, label="Val"), var)
        )

        summary_rows.append(row)

    df = pd.DataFrame(summary_rows)
    out_csv = cfg.OUTPUT_DIR / "benchmark_summary.csv"
    df.to_csv(out_csv, index=False)
    print(df.to_string(index=False))
    print(f"\nWrote {out_csv}")

    _figures(df)
    return df


def _figures(df: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vars_ = df["variable"].tolist()
    x = np.arange(len(vars_))
    w = 0.25

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, name in enumerate(["DOR", "LOCA2", "NEX"]):
        col = f"{name}_KGE"
        vals = [float(df.loc[df["variable"] == v, col].iloc[0]) for v in vars_]
        ax.bar(x + (i - 1) * w, vals, width=w, label=name)

    ax.set_xticks(x)
    ax.set_xticklabels(vars_)
    ax.set_ylabel("KGE")
    ax.set_title("Pooled KGE vs GridMET (2006–2014), MPI-ESM1-2-HR products")
    ax.legend()
    ax.axhline(0, color="k", linewidth=0.5)
    fig.tight_layout()
    p = cfg.FIG_DIR / "kge_by_variable.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")

    pr = df[df["variable"] == "pr"]
    if not pr.empty:
        fig, ax = plt.subplots(figsize=(6, 4))
        labs = []
        vals = []
        for name in ["DOR", "LOCA2", "NEX"]:
            col = f"{name}_Ext99_Bias%"
            if col in pr.columns:
                labs.append(name)
                vals.append(float(pr[col].iloc[0]))
        ax.bar(labs, vals, color=["#2c7fb8", "#7fcdbb", "#fdae61"])
        ax.axhline(0, color="k", linewidth=0.6)
        ax.set_ylabel("Ext99 bias % (pr)")
        ax.set_title("Precipitation 99th percentile bias vs GridMET")
        fig.tight_layout()
        p2 = cfg.FIG_DIR / "pr_ext99_bias.png"
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        print(f"Wrote {p2}")


if __name__ == "__main__":
    run()
