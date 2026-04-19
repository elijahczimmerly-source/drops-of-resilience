"""
Compare DOR (blend0.65), LOCA2, and NEX-GDDP vs GridMET on 2006–2014.
Set DOR_PIPELINE_ID when batching (e.g. test8_v2); else inferred from DOR_PRODUCT_ROOT.
Set DOR_BENCHMARK_SUITE=gridmet_4km|loca2_native|nex_native (default gridmet_4km).
"""
from __future__ import annotations

import os
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
import grid_suites as gs
from benchmark_io import load_aligned_stacks
from metrics import calculate_pooled_metrics


def _pipeline_id_for_run() -> str:
    e = os.environ.get("DOR_PIPELINE_ID", "").strip()
    if e:
        return e
    parts = cfg.DOR_PRODUCT_DIR.resolve().parts
    if "output" in parts:
        i = parts.index("output")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "unknown"


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
    suite = gs.benchmark_suite()
    out_dir = gs.suite_output_dir(suite)
    fig_dir = gs.suite_fig_dir(suite)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    pipeline_id = _pipeline_id_for_run()

    for var in cfg.VARS:
        st = load_aligned_stacks(var, suite=suite)
        obs_a, dor_a = st.obs, st.dor

        row: dict = {
            "pipeline_id": pipeline_id,
            "variable": var,
            "benchmark_suite": suite,
        }
        row.update(
            _flatten_metrics("DOR", calculate_pooled_metrics(obs_a, dor_a, var, label="Val"), var)
        )

        if st.loca2 is not None and np.any(np.isfinite(st.loca2)):
            row.update(
                _flatten_metrics(
                    "LOCA2", calculate_pooled_metrics(obs_a, st.loca2, var, label="Val"), var
                )
            )
        else:
            for k in _METRIC_KEYS:
                row[f"LOCA2_{k}"] = np.nan

        if st.nex is not None and np.any(np.isfinite(st.nex)):
            row.update(
                _flatten_metrics("NEX", calculate_pooled_metrics(obs_a, st.nex, var, label="Val"), var)
            )
        else:
            for k in _METRIC_KEYS:
                row[f"NEX_{k}"] = np.nan

        summary_rows.append(row)

    df = pd.DataFrame(summary_rows)
    suf = "" if suite == gs.SUITE_GRIDMET_4KM else f"_{suite}"
    out_csv = out_dir / f"benchmark_summary_{pipeline_id}{suf}.csv"
    df.to_csv(out_csv, index=False)
    print(df.to_string(index=False))
    print(f"\nWrote {out_csv}")

    _figures(df, pipeline_id, fig_dir, suite)
    return df


def _figures(df: pd.DataFrame, pipeline_id: str, fig_dir: Path, suite: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vars_ = df["variable"].tolist()
    x = np.arange(len(vars_))
    w = 0.25

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, name in enumerate(["DOR", "LOCA2", "NEX"]):
        col = f"{name}_KGE"
        vals = []
        for v in vars_:
            c = df.loc[df["variable"] == v, col]
            vals.append(float(c.iloc[0]) if not c.empty and np.isfinite(c.iloc[0]) else float("nan"))
        ax.bar(x + (i - 1) * w, vals, width=w, label=name)

    ax.set_xticks(x)
    ax.set_xticklabels(vars_)
    ax.set_ylabel("KGE")
    stitle = gs.suite_label_for_titles(suite)
    ax.set_title(f"Pooled KGE vs GridMET (2006–2014), MPI-ESM1-2-HR — {stitle}")
    ax.legend()
    ax.axhline(0, color="k", linewidth=0.5)
    fig.tight_layout()
    suf = "" if suite == gs.SUITE_GRIDMET_4KM else f"_{suite}"
    p = fig_dir / f"kge_by_variable_{pipeline_id}{suf}.png"
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
                vv = float(pr[col].iloc[0])
                if np.isfinite(vv):
                    labs.append(name)
                    vals.append(vv)
        if vals:
            ax.bar(labs, vals, color=["#2c7fb8", "#7fcdbb", "#fdae61"][: len(vals)])
        ax.axhline(0, color="k", linewidth=0.6)
        ax.set_ylabel("Ext99 bias % (pr)")
        ax.set_title(f"Precipitation 99th percentile bias vs GridMET — {stitle}")
        fig.tight_layout()
        p2 = fig_dir / f"pr_ext99_bias_{pipeline_id}{suf}.png"
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        print(f"Wrote {p2}")


if __name__ == "__main__":
    run()
