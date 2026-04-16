"""
CLI: climate-change signal summaries (S1 raw Iowa crop, S2 BCPC coarse, S3 memmap, S4 DOR, LOCA2, NEX).
Emits supplementary CSVs: BC effect (S2−S1), Tier B (coarse Δ upsampled vs S3), physics (tasmax<tasmin).
Requires CMIP6 future memmap + DOR future NPZs for full S4 output.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PC_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for _p in (SCRIPTS, PC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config as cfg
from climate_signal_io import (
    VARS_INTERNAL,
    SignalSliceResult,
    load_cmip6_variable,
    load_dor_future_npz,
    load_dor_main_npz,
    preservation_metrics,
    results_to_dataframe,
    s1_raw_placeholder_row,
    signal_row,
    spatial_delta_maps,
)
from coarse_stage_io import coarse_mask_from_shape, load_s1_raw_cropped_slices, load_s2_bc_otbc_slices
from grid_target import load_target_grid
from load_loca2 import load_loca_on_grid
from load_nex import load_nex_on_grid
from tier_b_alignment import upsample_coarse_delta_bilinear


def _slice_by_dates(
    data: np.ndarray,
    dates: pd.DatetimeIndex,
    start: str,
    end: str,
) -> np.ndarray:
    m = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    return data[m]


def _bc_delta_row(
    var: str,
    h1: np.ndarray,
    f1: np.ndarray,
    h2: np.ndarray,
    f2: np.ndarray,
) -> dict:
    m1h, m1f = float(np.nanmean(h1)), float(np.nanmean(f1))
    m2h, m2f = float(np.nanmean(h2)), float(np.nanmean(f2))
    if var == "pr":
        dh = (m2h / (m1h + 1e-12) - 1.0) * 100.0
        df = (m2f / (m1f + 1e-12) - 1.0) * 100.0
        kind = "pct_domain_mean"
    else:
        dh, df = m2h - m1h, m2f - m1f
        kind = "abs_domain_mean"
    return {
        "variable": var,
        "mean_hist_s1": m1h,
        "mean_hist_s2": m2h,
        "mean_fut_s1": m1f,
        "mean_fut_s2": m2f,
        "delta_mean_hist_s2_minus_s1": dh,
        "delta_mean_fut_s2_minus_s1": df,
        "kind": kind,
    }


def _physics_tas_frac(
    h_tx: np.ndarray,
    f_tx: np.ndarray,
    h_tn: np.ndarray,
    f_tn: np.ndarray,
) -> tuple[float, float]:
    if h_tx.shape != h_tn.shape or f_tx.shape != f_tn.shape:
        return float("nan"), float("nan")
    return float(np.mean(h_tx < h_tn)), float(np.mean(f_tx < f_tn))


def run_signal_analysis(
    *,
    skip_dor: bool = False,
    include_unshuffled_s4: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not cfg.CMIP6_HIST_DAT.is_file() or not cfg.CMIP6_FUTURE_DAT.is_file():
        print(
            "Missing CMIP6 memmaps. Set DOR_TEST8_CMIP6_HIST_DAT and DOR_TEST8_CMIP6_FUTURE_DAT "
            "(e.g. UNC paths under Spatial_Downscaling/test8_v2/Regridded_Iowa/MPI/mv_otbc/)."
        )
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    pipeline_ids = ["test8_v2", "test8_v3", "test8_v4"]
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    if cfg.GEO_MASK.is_file():
        mask_2d = np.load(cfg.GEO_MASK) == 1
    else:
        mask_2d = np.ones((cfg.H, cfg.W), dtype=bool)

    hist_s, hist_e = cfg.SIGNAL_HIST_START, cfg.SIGNAL_HIST_END
    fut_s, fut_e = cfg.SIGNAL_FUT_START, cfg.SIGNAL_FUT_END

    all_rows: list = []
    pres_rows: list = []
    bc_rows: list = []
    tier_b_rows: list = []
    phys_rows: list = []

    for var in VARS_INTERNAL:
        s1_pair = load_s1_raw_cropped_slices(var, hist_s, hist_e, fut_s, fut_e)
        if s1_pair is not None:
            h1, f1 = s1_pair
            m1 = coarse_mask_from_shape(h1.shape[1], h1.shape[2])
            all_rows.append(signal_row("S1_raw", "Cropped_Iowa_Raw", var, h1, f1, m1, None))
        else:
            all_rows.append(s1_raw_placeholder_row(var))

        s2_pair = load_s2_bc_otbc_slices(var, hist_s, hist_e, fut_s, fut_e)
        if s2_pair is not None:
            h2, f2 = s2_pair
            m2 = coarse_mask_from_shape(h2.shape[1], h2.shape[2])
            all_rows.append(
                signal_row(
                    "S2_bc",
                    "BCPC_mv_otbc_physics_corrected",
                    var,
                    h2,
                    f2,
                    m2,
                    None,
                )
            )
        else:
            all_rows.append(
                SignalSliceResult(
                    "S2_bc",
                    "BCPC_mv_otbc",
                    None,
                    var,
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    "abs",
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    float("nan"),
                    "BCPC coarse npz missing or empty date slice (set DOR_CROPPED_BC_ROOT or open WRC_DOR UNC).",
                )
            )

        if s1_pair is not None and s2_pair is not None:
            h1, f1 = s1_pair
            h2, f2 = s2_pair
            bc_rows.append(_bc_delta_row(var, h1, f1, h2, f2))

        s3_hist, _ = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, hist_s, hist_e)
        s3_fut, _ = load_cmip6_variable(cfg.CMIP6_FUTURE_DAT, var, fut_s, fut_e)
        _, ds3 = spatial_delta_maps(s3_hist, s3_fut, var)

        all_rows.append(signal_row("S3_regrid", "cmip6_inputs", var, s3_hist, s3_fut, mask_2d, None))

        if s2_pair is not None:
            h2, f2 = s2_pair
            _, d_s2 = spatial_delta_maps(h2, f2, var)
            try:
                d_up = upsample_coarse_delta_bilinear(d_s2, cfg.H, cfg.W)
                pm = preservation_metrics(d_up, ds3, mask_2d)
                diff = d_up - ds3
                mae = float(np.nanmean(np.abs(diff[mask_2d])))
                tier_b_rows.append(
                    {
                        "variable": var,
                        "tier": "B_bilinear_upsample_S2_delta_vs_S3_delta",
                        "r_delta_maps": pm["r"],
                        "rmse_delta_maps": pm["rmse"],
                        "mean_abs_delta_diff": mae,
                        "note": "",
                    }
                )
            except Exception as e:
                tier_b_rows.append(
                    {
                        "variable": var,
                        "tier": "B_bilinear_upsample_S2_delta_vs_S3_delta",
                        "r_delta_maps": float("nan"),
                        "rmse_delta_maps": float("nan"),
                        "mean_abs_delta_diff": float("nan"),
                        "note": str(e),
                    }
                )

        loca_h = loca_f = None
        if var in ("pr", "tasmax", "tasmin"):
            try:
                loca_h, _ = load_loca_on_grid(
                    var, lat_tgt, lon_tgt, scenario="historical", time_start=hist_s, time_end=hist_e
                )
                loca_f, _ = load_loca_on_grid(
                    var, lat_tgt, lon_tgt, scenario="ssp585", time_start=fut_s, time_end=fut_e
                )
                all_rows.append(signal_row("external", "LOCA2", var, loca_h, loca_f, mask_2d, None))
            except (FileNotFoundError, OSError, ValueError) as e:
                print(f"  LOCA2 skip {var}: {e}")

        try:
            y0, y1 = int(hist_s[:4]), int(hist_e[:4])
            nex_h, _ = load_nex_on_grid(
                var, lat_tgt, lon_tgt, scenario="historical", year_start=y0, year_end=y1
            )
            y2, y3 = int(fut_s[:4]), int(fut_e[:4])
            nex_f, _ = load_nex_on_grid(
                var, lat_tgt, lon_tgt, scenario="ssp585", year_start=y2, year_end=y3
            )
            all_rows.append(signal_row("external", "NEX", var, nex_h, nex_f, mask_2d, None))
        except (FileNotFoundError, OSError) as e:
            print(f"  NEX skip {var}: {e}")

        if skip_dor:
            continue

        _dor_shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
        use_shared = os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        for pid in pipeline_ids:
            dor_dir = (
                Path(_dor_shared)
                if (_dor_shared and use_shared)
                else cfg.DOR_DEFAULT_OUTPUTS.get(pid)
            )
            if dor_dir is None:
                continue
            try:
                dh, dd = load_dor_main_npz(dor_dir, var)
                dfu, ddf = load_dor_future_npz(dor_dir, var, shuffled=True)
                dor_h = _slice_by_dates(dh, dd, hist_s, hist_e)
                dor_f = _slice_by_dates(dfu, ddf, fut_s, fut_e)
            except FileNotFoundError as e:
                print(f"  DOR skip {pid} {var}: {e}")
                continue

            all_rows.append(signal_row("S4_dor", "DOR", var, dor_h, dor_f, mask_2d, pid))
            _, ddor = spatial_delta_maps(dor_h, dor_f, var)
            pr = preservation_metrics(ds3, ddor, mask_2d)
            pres_rows.append(
                {
                    "from_stage": "S3_regrid",
                    "to_stage": "S4_dor",
                    "pipeline_id": pid,
                    "variable": var,
                    "r_delta_maps": pr["r"],
                    "rmse_delta_maps": pr["rmse"],
                }
            )

            if include_unshuffled_s4:
                try:
                    dfu_u, ddf_u = load_dor_future_npz(dor_dir, var, shuffled=False)
                    dor_f_u = _slice_by_dates(dfu_u, ddf_u, fut_s, fut_e)
                    all_rows.append(
                        signal_row(
                            "S4_dor",
                            "DOR_SSP585_unshuffled",
                            var,
                            dor_h,
                            dor_f_u,
                            mask_2d,
                            pid,
                        )
                    )
                except FileNotFoundError:
                    pass

    # Physics: tasmax < tasmin fraction (coarse stages)
    for stage, loader in (
        ("S1_raw", load_s1_raw_cropped_slices),
        ("S2_bc", load_s2_bc_otbc_slices),
    ):
        p_tx = loader("tasmax", hist_s, hist_e, fut_s, fut_e)
        p_tn = loader("tasmin", hist_s, hist_e, fut_s, fut_e)
        if p_tx is None or p_tn is None:
            phys_rows.append(
                {
                    "stage": stage,
                    "frac_hist_tasmax_lt_tasmin": float("nan"),
                    "frac_fut_tasmax_lt_tasmin": float("nan"),
                    "note": "missing tasmax or tasmin stacks",
                }
            )
            continue
        h_tx, f_tx = p_tx
        h_tn, f_tn = p_tn
        fh, ff = _physics_tas_frac(h_tx, f_tx, h_tn, f_tn)
        phys_rows.append(
            {
                "stage": stage,
                "frac_hist_tasmax_lt_tasmin": fh,
                "frac_fut_tasmax_lt_tasmin": ff,
                "note": "",
            }
        )

    df_sig = results_to_dataframe(all_rows)
    df_pres = pd.DataFrame(pres_rows)
    df_bc = pd.DataFrame(bc_rows)
    df_tier = pd.DataFrame(tier_b_rows)
    df_phys = pd.DataFrame(phys_rows)
    return df_sig, df_pres, df_bc, df_tier, df_phys


def main() -> int:
    p = argparse.ArgumentParser(description="Climate signal by stage (S1–S4, LOCA2, NEX)")
    p.add_argument("--skip-dor", action="store_true", help="Only S3 + externals (no DOR NPZs)")
    p.add_argument(
        "--include-unshuffled-s4",
        action="store_true",
        help="Add S4 rows using unshuffled future NPZ when present (alongside default shuffled).",
    )
    args = p.parse_args()

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_sig, df_pres, df_bc, df_tier, df_phys = run_signal_analysis(
        skip_dor=args.skip_dor,
        include_unshuffled_s4=args.include_unshuffled_s4,
    )

    out1 = cfg.OUTPUT_DIR / "climate_signal_by_stage.csv"
    out2 = cfg.OUTPUT_DIR / "climate_signal_preservation.csv"
    df_sig.to_csv(out1, index=False)
    df_pres.to_csv(out2, index=False)
    print(df_sig.to_string(index=False))
    print(f"\nWrote {out1}\nWrote {out2}")

    p_bc = cfg.OUTPUT_DIR / "climate_signal_bc_delta.csv"
    p_tb = cfg.OUTPUT_DIR / "climate_signal_tier_b.csv"
    p_ph = cfg.OUTPUT_DIR / "climate_signal_physics_coarse.csv"
    df_bc.to_csv(p_bc, index=False)
    df_tier.to_csv(p_tb, index=False)
    df_phys.to_csv(p_ph, index=False)
    print(f"Wrote {p_bc} ({len(df_bc)} rows)")
    print(f"Wrote {p_tb} ({len(df_tier)} rows)")
    print(f"Wrote {p_ph} ({len(df_phys)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
