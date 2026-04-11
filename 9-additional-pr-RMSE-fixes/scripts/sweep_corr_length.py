"""
PR noise correlation length sweep (PLAN-CORR-LENGTH-SWEEP.md).

For each `DOR_PR_CORR_LENGTH`, runs `pipeline/scripts/test8_v4.py` with fixed env and
`PR_INTENSITY_OUT_TAG=corr_len_<value>`.

`test8_v4.py` lives under **`pipeline/scripts/`** only; `--experiment-root` sets
`DOR_PIPELINE_ROOT` (output + default `data/` layout) but the subprocess always invokes
the repo pipeline script.

Example (server Regridded_Iowa data — the ONLY correct data for benchmark-comparable runs):
  conda activate drops-of-resilience
  python sweep_corr_length.py \\
    --experiment-root c:/drops-of-resilience/4-test8-v2-pr-intensity \\
    --out-csv c:/drops-of-resilience/9-additional-pr-RMSE-fixes/output/corr_length_sweep.csv \\
    --regridded-iowa-server

Do NOT use 3-bilinear-vs-nn-regridding/pipeline/data/bilinear/ — different regridding,
different border pixels, metrics won't match benchmarks. See dor-info.md.
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time

import pandas as pd


# Canonical 216×192 Regridded_Iowa (same as sweep_wdf_threshold.py).
_REGRIDDED_IOWA_ROOT = (
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa"
)
_REGRIDDED_IOWA_MV = os.path.join(_REGRIDDED_IOWA_ROOT, "MPI", "mv_otbc")
REGRIDDED_IOWA_CMIP_HIST = os.path.join(
    _REGRIDDED_IOWA_MV, "cmip6_inputs_19810101-20141231.dat"
)
REGRIDDED_IOWA_GRIDMET_TARGETS = os.path.join(
    _REGRIDDED_IOWA_ROOT, "gridmet_targets_19810101-20141231.dat"
)
REGRIDDED_IOWA_GEO_MASK = os.path.join(_REGRIDDED_IOWA_ROOT, "geo_mask.npy")


def _repo_root_from_script() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _pipeline_test8_v4_py() -> str:
    return os.path.join(_repo_root_from_script(), "pipeline", "scripts", "test8_v4.py")


def _corr_to_tag(cl: float, suffix: str = "") -> str:
    """15 -> corr_len_15; 45.5 -> corr_len_45p5."""
    if float(cl) == int(float(cl)):
        return f"corr_len_{int(float(cl))}{suffix}"
    s = str(cl).replace(".", "p")
    return f"corr_len_{s}{suffix}"


def _run(cmd: list[str], env: dict[str, str], cwd: str | None) -> int:
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, env=env, cwd=cwd)


def _table1_row(csv_path: str, variable: str) -> dict:
    df = pd.read_csv(csv_path)
    r = df[df["Variable"].str.lower() == variable.lower()]
    if r.empty:
        return {}
    return r.iloc[0].to_dict()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--experiment-root",
        default=os.path.join(_repo_root_from_script(), "4-test8-v2-pr-intensity"),
        help="DOR_PIPELINE_ROOT (output goes under <root>/output/test8_v4/…); "
        "default: repo/4-test8-v2-pr-intensity",
    )
    ap.add_argument(
        "--corr-lengths",
        default="15,25,35,45,55,70",
        help="Comma-separated DOR_PR_CORR_LENGTH values",
    )
    ap.add_argument(
        "--regridded-iowa-server",
        action="store_true",
        help="Use UNC paths under Spatial_Downscaling/test8_v2/Regridded_Iowa",
    )
    ap.add_argument("--cmip-hist", default="", help="DOR_TEST8_CMIP6_HIST_DAT")
    ap.add_argument("--gridmet-targets", default="", help="DOR_TEST8_GRIDMET_TARGETS_DAT")
    ap.add_argument("--geo-mask", default="", help="DOR_TEST8_GEO_MASK_NPY")
    ap.add_argument("--out-csv", required=True, help="One row per successful run")
    ap.add_argument(
        "--figures-dir",
        default="",
        help="If set, mean-pr validation maps (needs NPZ — do not combine with --skip-npz-save)",
    )
    ap.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Only read existing OUT_DIR Table1 + optional plot",
    )
    ap.add_argument(
        "--tag-suffix",
        default="",
        help="Append to folder name (e.g. '_216' → corr_len_35_216)",
    )
    ap.add_argument(
        "--skip-npz-save",
        action="store_true",
        help="Set TEST8_SKIP_NPZ_SAVE=1 (saves disk; cannot be used with --figures-dir)",
    )
    args = ap.parse_args()

    if args.regridded_iowa_server:
        cmip_hist = REGRIDDED_IOWA_CMIP_HIST
        gridmet_targets = REGRIDDED_IOWA_GRIDMET_TARGETS
        geo_mask = REGRIDDED_IOWA_GEO_MASK
    else:
        cmip_hist = (args.cmip_hist or "").strip()
        gridmet_targets = (args.gridmet_targets or "").strip()
        geo_mask = (args.geo_mask or "").strip()
        if not cmip_hist or not gridmet_targets or not geo_mask:
            print(
                "ERROR: specify --regridded-iowa-server OR all of "
                "--cmip-hist, --gridmet-targets, --geo-mask.",
                file=sys.stderr,
            )
            return 1

    if args.skip_npz_save and (args.figures_dir or "").strip():
        print(
            "ERROR: --skip-npz-save conflicts with --figures-dir (plots need Stochastic_V8_Hybrid_pr.npz).",
            file=sys.stderr,
        )
        return 1

    test8_py = _pipeline_test8_v4_py()
    if not os.path.isfile(test8_py):
        print(f"ERROR: missing {test8_py}", file=sys.stderr)
        return 1

    plot_py = os.path.abspath(
        os.path.join(
            _repo_root_from_script(),
            "7-fix-pr-splotchiness",
            "scripts",
            "plot_validation_agg_mean_pr.py",
        )
    )
    if args.figures_dir and not os.path.isfile(plot_py):
        print(f"ERROR: plot script missing {plot_py}", file=sys.stderr)
        return 1

    lengths: list[float] = []
    for part in args.corr_lengths.split(","):
        part = part.strip()
        if not part:
            continue
        lengths.append(float(part))
    if not lengths:
        print("ERROR: empty --corr-lengths", file=sys.stderr)
        return 1

    exp_root = os.path.abspath(args.experiment_root)
    test8_cwd = os.path.dirname(test8_py)

    fieldnames = [
        "DOR_PR_CORR_LENGTH",
        "pr_Val_KGE",
        "pr_Val_RMSE_pooled",
        "pr_Val_Bias",
        "pr_Val_Ext99_Bias%",
        "pr_Val_Lag1_Err",
        "pr_Val_WDF_Sim%",
        "pr_Val_WDF_Obs%",
        "pr_Val_Spatial_Bias",
        "wind_Val_Ext99_Bias%",
        "wall_s",
        "out_dir",
    ]

    out_csv = os.path.abspath(args.out_csv)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    new_file = not os.path.isfile(out_csv)
    f_out = open(out_csv, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f_out, fieldnames=fieldnames)
    if new_file:
        w.writeheader()

    tag_suffix = (args.tag_suffix or "").strip()

    for cl in lengths:
        tag = _corr_to_tag(cl, tag_suffix)
        out_dir = os.path.join(exp_root, "output", "test8_v4", f"experiment_{tag}")
        table1 = os.path.join(out_dir, "V8_Table1_Pooled_Metrics_Stochastic.csv")
        dor_npz = os.path.join(out_dir, "Stochastic_V8_Hybrid_pr.npz")

        env = os.environ.copy()
        env["DOR_PR_CORR_LENGTH"] = str(cl)
        env["PR_WDF_THRESHOLD_FACTOR"] = "1.65"
        env["DOR_MULTIPLICATIVE_NOISE_DEBIAS"] = "0"
        env["TEST8_SEED"] = "42"
        env["PR_USE_INTENSITY_RATIO"] = "1"
        env["PR_INTENSITY_BLEND"] = "0.65"
        env["TEST8_MAIN_PERIOD_ONLY"] = "1"
        env["DOR_RATIO_SMOOTH_SIGMA"] = "0"
        env["PR_INTENSITY_OUT_TAG"] = tag
        env["DOR_TEST8_CMIP6_HIST_DAT"] = cmip_hist
        env["DOR_TEST8_GRIDMET_TARGETS_DAT"] = gridmet_targets
        env["DOR_TEST8_GEO_MASK_NPY"] = geo_mask
        env["DOR_PIPELINE_ROOT"] = exp_root
        env["DOR_TEST8_V2_PR_INTENSITY_ROOT"] = exp_root
        env["DOR_PIPELINE_ID"] = "test8_v4"
        if args.skip_npz_save:
            env["TEST8_SKIP_NPZ_SAVE"] = "1"
        else:
            env.pop("TEST8_SKIP_NPZ_SAVE", None)

        t0 = time.perf_counter()
        if not args.skip_pipeline:
            rc = _run([sys.executable, test8_py], env, cwd=test8_cwd)
            if rc != 0:
                print(f"ERROR: pipeline failed DOR_PR_CORR_LENGTH={cl} rc={rc}", file=sys.stderr)
                f_out.close()
                return rc
        else:
            if not os.path.isfile(table1):
                print(
                    f"ERROR: --skip-pipeline but missing {table1}",
                    file=sys.stderr,
                )
                f_out.close()
                return 1

        wall_s = time.perf_counter() - t0
        pr = _table1_row(table1, "pr")
        wind = _table1_row(table1, "wind")

        row = {
            "DOR_PR_CORR_LENGTH": cl,
            "pr_Val_KGE": pr.get("Val_KGE", ""),
            "pr_Val_RMSE_pooled": pr.get("Val_RMSE_pooled", ""),
            "pr_Val_Bias": pr.get("Val_Bias", ""),
            "pr_Val_Ext99_Bias%": pr.get("Val_Ext99_Bias%", ""),
            "pr_Val_Lag1_Err": pr.get("Val_Lag1_Err", ""),
            "pr_Val_WDF_Sim%": pr.get("Val_WDF_Sim%", ""),
            "pr_Val_WDF_Obs%": pr.get("Val_WDF_Obs%", ""),
            "pr_Val_Spatial_Bias": pr.get("Val_Spatial_Bias", ""),
            "wind_Val_Ext99_Bias%": wind.get("Val_Ext99_Bias%", ""),
            "wall_s": round(wall_s, 1),
            "out_dir": out_dir,
        }
        w.writerow(row)
        f_out.flush()
        print(
            f"OK corr_len={cl} RMSE={row['pr_Val_RMSE_pooled']} Ext99={row['pr_Val_Ext99_Bias%']}",
            flush=True,
        )

        if args.figures_dir and os.path.isfile(plot_py):
            if not os.path.isfile(dor_npz):
                print(
                    f"WARN: missing {dor_npz} — skip figure (did you use TEST8_SKIP_NPZ_SAVE?)",
                    file=sys.stderr,
                )
            else:
                fig_dir = os.path.abspath(args.figures_dir)
                os.makedirs(fig_dir, exist_ok=True)
                png = os.path.join(fig_dir, f"dor_val_{tag}.png")
                title = (
                    f"DOR PR corr_len={cl} (blend 0.65, WDF 1.65, debias off)\nmean 2006–2014"
                )
                rc = _run(
                    [
                        sys.executable,
                        plot_py,
                        "--dor-npz",
                        dor_npz,
                        "--gridmet-targets",
                        gridmet_targets,
                        "--geo-mask",
                        geo_mask,
                        "--title-right",
                        title,
                        "--out",
                        png,
                    ],
                    env,
                    cwd=None,
                )
                if rc != 0:
                    print(f"WARN: plot failed corr_len={cl} rc={rc}", file=sys.stderr)

    f_out.close()
    print(f"Wrote {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
