"""
Attempt 5 — sweep `DOR_RATIO_SMOOTH_SIGMA` (Phase 3 Approach A, FIX-PR-SPLOTCHINESS-PLAN.md).

For each sigma: run `pipeline/scripts/test8_v4.py`, then `diagnose_splotchiness.py` on
`Stochastic_V8_Hybrid_pr.npz`, merge key Table1 pr/wind rows, append to CSV.
Optionally writes `plot_validation_agg_mean_pr.py` figures under `--figures-dir`.

Shared env per run (override via `--extra-env` not implemented; edit script if needed):
  DOR_MULTIPLICATIVE_NOISE_DEBIAS=0, TEST8_SEED=42, PR_USE_INTENSITY_RATIO=1,
  PR_INTENSITY_BLEND=0.65, TEST8_MAIN_PERIOD_ONLY=1, TEST8_DETERMINISTIC=0,
  DOR_PHASE2_SAVE_PRE_SCHAAKE_PR=0

Example:
  python sweep_ratio_smooth.py \\
    --experiment-root c:/drops-of-resilience/pipeline \\
    --sigmas 0,5,10,15,20 \\
    --cmip-hist \\\\abe-cylo\\...\\cmip6_inputs_19810101-20141231.dat \\
    --gridmet-targets \\\\abe-cylo\\...\\gridmet_targets_19810101-20141231.dat \\
    --geo-mask \\\\abe-cylo\\...\\geo_mask.npy \\
    --geo-static \\\\abe-cylo\\...\\geo_static.npy \\
    --out-csv c:/drops-of-resilience/7-fix-pr-splotchiness/output/attempt5_ratio_smooth_sweep.csv \\
    --figures-dir c:/drops-of-resilience/7-fix-pr-splotchiness/figures/pr-splotch-side-by-side
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time

import pandas as pd


def _run(cmd: list[str], env: dict[str, str], cwd: str | None) -> int:
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, env=env, cwd=cwd)


def _table1_row(csv_path: str, variable: str) -> dict[str, float]:
    df = pd.read_csv(csv_path)
    r = df[df["Variable"].str.lower() == variable.lower()]
    if r.empty:
        return {}
    return r.iloc[0].to_dict()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--experiment-root",
        required=True,
        help="Pipeline root with scripts/ and output/ (e.g. .../pipeline, or a copy with data/)",
    )
    ap.add_argument(
        "--sigmas",
        default="0,5,10,15,20",
        help="Comma-separated DOR_RATIO_SMOOTH_SIGMA values",
    )
    ap.add_argument("--cmip-hist", default="", help="DOR_TEST8_CMIP6_HIST_DAT")
    ap.add_argument("--gridmet-targets", default="", help="DOR_TEST8_GRIDMET_TARGETS_DAT")
    ap.add_argument("--geo-mask", default="", help="DOR_TEST8_GEO_MASK_NPY")
    ap.add_argument("--geo-static", default="", help="DOR_TEST8_GEO_STATIC_NPY")
    ap.add_argument(
        "--out-csv",
        required=True,
        help="Append one row per successful sigma",
    )
    ap.add_argument(
        "--figures-dir",
        default="",
        help="If set, write dor_val_05_attempt5_ratio_smooth_sigma{NN}.png per sigma",
    )
    ap.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Only post-process: expect OUT_DIR already populated (diagnose + table1 + optional plot)",
    )
    args = ap.parse_args()

    if not args.skip_pipeline and (
        not args.gridmet_targets or not args.geo_mask
    ):
        print(
            "ERROR: --gridmet-targets and --geo-mask required "
            "(needed for post-run diagnose_splotchiness).",
            file=sys.stderr,
        )
        return 1

    root = os.path.abspath(args.experiment_root)
    test8_py = os.path.join(root, "scripts", "test8_v4.py")
    if not os.path.isfile(test8_py):
        print(f"ERROR: missing {test8_py}", file=sys.stderr)
        return 1

    diag_py = os.path.join(
        os.path.dirname(__file__), "diagnose_splotchiness.py"
    )
    plot_py = os.path.join(
        os.path.dirname(__file__), "plot_validation_agg_mean_pr.py"
    )

    sigmas: list[float] = []
    for part in args.sigmas.split(","):
        part = part.strip()
        if not part:
            continue
        sigmas.append(float(part))
    if not sigmas:
        print("ERROR: empty --sigmas", file=sys.stderr)
        return 1

    fieldnames = [
        "sigma",
        "pr_intensity_out_tag",
        "wall_s",
        "splotch_metric",
        "mean_ratio_field",
        "pr_Val_Ext99_Bias%",
        "pr_Val_RMSE_pooled",
        "pr_Val_KGE",
        "pr_Val_Lag1_Err",
        "pr_Val_WDF_Sim%",
        "wind_Val_Ext99_Bias%",
        "out_dir",
        "dor_npz",
    ]

    out_csv = os.path.abspath(args.out_csv)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    new_file = not os.path.isfile(out_csv)
    f_out = open(out_csv, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f_out, fieldnames=fieldnames)
    if new_file:
        w.writeheader()

    for sigma in sigmas:
        if sigma == int(sigma):
            tag = f"attempt5_sigma{int(sigma)}"
        else:
            tag = "attempt5_sigma" + str(sigma).replace(".", "p")

        out_dir = os.path.join(
            root, "output", "test8_v4", f"experiment_{tag}"
        )
        dor_npz = os.path.join(out_dir, "Stochastic_V8_Hybrid_pr.npz")
        table1 = os.path.join(out_dir, "V8_Table1_Pooled_Metrics_Stochastic.csv")

        env = os.environ.copy()
        env.setdefault("DOR_PIPELINE_ROOT", root)
        env["DOR_RATIO_SMOOTH_SIGMA"] = str(sigma)
        env["PR_INTENSITY_OUT_TAG"] = tag
        env["DOR_MULTIPLICATIVE_NOISE_DEBIAS"] = "0"
        env["TEST8_SEED"] = "42"
        env["PR_USE_INTENSITY_RATIO"] = "1"
        env["PR_INTENSITY_BLEND"] = "0.65"
        env["TEST8_MAIN_PERIOD_ONLY"] = "1"
        env["TEST8_DETERMINISTIC"] = "0"
        env["DOR_PHASE2_SAVE_PRE_SCHAAKE_PR"] = "0"
        if args.cmip_hist:
            env["DOR_TEST8_CMIP6_HIST_DAT"] = args.cmip_hist
        if args.gridmet_targets:
            env["DOR_TEST8_GRIDMET_TARGETS_DAT"] = args.gridmet_targets
        if args.geo_mask:
            env["DOR_TEST8_GEO_MASK_NPY"] = args.geo_mask
        if args.geo_static:
            env["DOR_TEST8_GEO_STATIC_NPY"] = args.geo_static

        t0 = time.perf_counter()
        if not args.skip_pipeline:
            rc = _run(
                [sys.executable, test8_py], env, cwd=os.path.dirname(test8_py)
            )
            if rc != 0:
                print(f"ERROR: pipeline failed sigma={sigma} rc={rc}", file=sys.stderr)
                f_out.close()
                return rc
        else:
            if not os.path.isfile(dor_npz) or not os.path.isfile(table1):
                print(
                    f"ERROR: --skip-pipeline but missing outputs for sigma={sigma}",
                    file=sys.stderr,
                )
                f_out.close()
                return 1

        wall_s = time.perf_counter() - t0

        with tempfile.TemporaryDirectory() as td:
            rc = _run(
                [
                    sys.executable,
                    diag_py,
                    "--dor-npz",
                    dor_npz,
                    "--targets",
                    args.gridmet_targets,
                    "--mask",
                    args.geo_mask,
                    "--out-dir",
                    td,
                    "--label",
                    f"s{sigma}",
                ],
                env,
                cwd=None,
            )
            if rc != 0:
                print(f"ERROR: diagnose_splotchiness failed sigma={sigma}", file=sys.stderr)
                f_out.close()
                return rc
            spl_path = os.path.join(td, "splotch_diagnostic.csv")
            sp_df = pd.read_csv(spl_path)
            sp_row = sp_df[sp_df["window"] == "val_2006_2014_full"].iloc[0]
            splotch_m = float(sp_row["splotch_metric_std_ratio"])
            mean_r = float(sp_row["mean_ratio_field"])

        pr = _table1_row(table1, "pr")
        wind = _table1_row(table1, "wind")

        row = {
            "sigma": sigma,
            "pr_intensity_out_tag": tag,
            "wall_s": round(wall_s, 1),
            "splotch_metric": round(splotch_m, 6),
            "mean_ratio_field": round(mean_r, 6),
            "pr_Val_Ext99_Bias%": pr.get("Val_Ext99_Bias%", ""),
            "pr_Val_RMSE_pooled": pr.get("Val_RMSE_pooled", ""),
            "pr_Val_KGE": pr.get("Val_KGE", ""),
            "pr_Val_Lag1_Err": pr.get("Val_Lag1_Err", ""),
            "pr_Val_WDF_Sim%": pr.get("Val_WDF_Sim%", ""),
            "wind_Val_Ext99_Bias%": wind.get("Val_Ext99_Bias%", ""),
            "out_dir": out_dir,
            "dor_npz": dor_npz,
        }
        w.writerow(row)
        f_out.flush()
        print(f"OK sigma={sigma} splotch={splotch_m:.6f} pr Ext99={row['pr_Val_Ext99_Bias%']}", flush=True)

        if args.figures_dir and args.gridmet_targets and args.geo_mask:
            fig_dir = os.path.abspath(args.figures_dir)
            os.makedirs(fig_dir, exist_ok=True)
            if sigma == int(sigma):
                sigma_key = f"{int(sigma):02d}"
            else:
                sigma_key = str(sigma).replace(".", "p")
            png = os.path.join(
                fig_dir,
                f"dor_val_05_attempt5_ratio_smooth_sigma{sigma_key}.png",
            )
            title = f"DOR ratio smooth sigma={sigma} (stoch)\nmean 2006-2014"
            rc = _run(
                [
                    sys.executable,
                    plot_py,
                    "--dor-npz",
                    dor_npz,
                    "--gridmet-targets",
                    args.gridmet_targets,
                    "--geo-mask",
                    args.geo_mask,
                    "--title-right",
                    title,
                    "--out",
                    png,
                ],
                env,
                cwd=None,
            )
            if rc != 0:
                print(f"WARN: plot failed sigma={sigma} rc={rc}", file=sys.stderr)

    f_out.close()
    print(f"Wrote {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
