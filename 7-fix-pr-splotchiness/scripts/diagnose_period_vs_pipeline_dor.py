"""
Compare period-comparison vs pipeline DOR plots: inputs, mean fields, and color scales.

Uses the same paths and loaders as plot_period_comparison.py and the pipeline `dor`
path in plot_gridmet_pipeline_side_by_side.cmd_dor.

Run from repo root:
  python 7-fix-pr-splotchiness/scripts/diagnose_period_vs_pipeline_dor.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from plot_period_comparison import (  # noqa: E402
    DOR_NPZ,
    GEO_MASK,
    GRIDMET_TARGETS,
    PERIODS,
    _apply_geo_mask,
    _dor_mean_from_npz,
    _gridmet_mean_from_memmap,
)


def _legacy_global_vmin_vmax(stack: list[np.ndarray]) -> tuple[float, float]:
    """Old period-comparison stage-3 policy (min/max over six arrays); for diagnostics only."""
    vals = np.concatenate([a[np.isfinite(a)].ravel() for a in stack if a.size])
    if vals.size == 0:
        return 0.0, 1.0
    g_min = float(np.nanmin(vals))
    g_max = float(np.nanmax(vals))
    vmin = np.floor(g_min * 10.0) / 10.0
    vmax = np.ceil(g_max * 10.0) / 10.0
    if vmax <= vmin:
        vmax = vmin + 0.1
    return max(0.0, vmin), vmax
from plot_gridmet_pipeline_side_by_side import _memmap_days_shape  # noqa: E402
from plot_validation_agg_mean_pr import _pair_vmin_vmax  # noqa: E402
from plot_validation_agg_mean_pr_obs_vs_gcm import _vmin_vmax_one  # noqa: E402


def _pipeline_dor_means_unmasked(
    gridmet_targets: Path,
    geo_mask: Path,
    dor_npz: Path,
    val_start: str,
    val_end: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Mirror plot_gridmet_pipeline_side_by_side.cmd_dor (no geo_mask on fields)."""
    mask = np.load(geo_mask)
    if mask.ndim != 2:
        mask = mask.reshape(mask.shape[-2], mask.shape[-1])
    h, w = mask.shape
    z = np.load(dor_npz)
    dor = np.asarray(z["data"], dtype=np.float64)
    z.close()
    if dor.shape[1:] != (h, w):
        raise ValueError("DOR grid mismatch")
    n_days = dor.shape[0]
    n_days_g, h2, w2 = _memmap_days_shape(str(gridmet_targets), str(geo_mask))
    if (h2, w2) != (h, w):
        raise ValueError("geo vs gridmet shape mismatch")
    n_use = min(n_days, n_days_g)
    flat_g = np.memmap(gridmet_targets, dtype="float32", mode="r")
    mm_g = flat_g.reshape(n_days_g, 6, h, w)
    dates = pd.date_range("1981-01-01", periods=n_use, freq="D")
    v0, v1 = pd.Timestamp(val_start), pd.Timestamp(val_end)
    val_mask = (dates >= v0) & (dates <= v1)
    obs_pr = np.asarray(mm_g[:n_use, 0, :, :], dtype=np.float64)
    dor_u = dor[:n_use]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        o = np.nanmean(obs_pr[val_mask], axis=0)
        d = np.nanmean(dor_u[val_mask], axis=0)
    return o, d


def main() -> int:
    for p in (GRIDMET_TARGETS, GEO_MASK, DOR_NPZ):
        if not p.is_file():
            print(f"ERROR: missing {p}", file=sys.stderr)
            return 1

    geo = np.load(GEO_MASK)
    if geo.ndim != 2:
        geo = geo.reshape(geo.shape[-2], geo.shape[-1])
    h, w = geo.shape
    land = geo.astype(bool) if geo.dtype != bool else geo

    tags = [t for t, _, _, _ in PERIODS]
    gm_4k: dict[str, np.ndarray] = {}
    dor_m: dict[str, np.ndarray] = {}

    for tag, vs, ve, _ in PERIODS:
        gm_4k[tag] = _apply_geo_mask(
            _gridmet_mean_from_memmap(GRIDMET_TARGETS, h, w, 12418, vs, ve),
            geo,
        )
        dor_m[tag] = _apply_geo_mask(
            _dor_mean_from_npz(DOR_NPZ, 12418, vs, ve),
            geo,
        )

    s3 = [gm_4k[t] for t in tags] + [dor_m[t] for t in tags]
    legacy_s3_scale = _legacy_global_vmin_vmax(s3)

    tag_0614 = "2006-2014"
    vs, ve = "2006-01-01", "2014-12-31"
    g_mask = gm_4k[tag_0614]
    d_mask = dor_m[tag_0614]

    o_pipe, d_pipe = _pipeline_dor_means_unmasked(
        GRIDMET_TARGETS, GEO_MASK, DOR_NPZ, vs, ve
    )

    # Same means as period script but without geo mask (for diff)
    g_raw = _gridmet_mean_from_memmap(GRIDMET_TARGETS, h, w, 12418, vs, ve)
    d_raw = _dor_mean_from_npz(DOR_NPZ, 12418, vs, ve)

    print("=== verify-inputs (paths used by both workflows) ===")
    print(f"  GRIDMET_TARGETS: {GRIDMET_TARGETS}")
    print(f"  GEO_MASK:        {GEO_MASK}")
    print(f"  DOR_NPZ:         {DOR_NPZ}")
    print(f"  Period 2006-2014: val_start={vs!r} val_end={ve!r}")

    print("\n=== optional-array-diff (2006-2014 means) ===")
    for name, a, b in (
        ("GridMET masked vs raw", g_mask, g_raw),
        ("DOR masked vs raw", d_mask, d_raw),
    ):
        delta = np.abs(a - b)
        finite = np.isfinite(delta)
        print(f"  {name}: max abs diff = {float(np.nanmax(delta[finite])):.6e}")

    land3 = land & np.isfinite(g_mask) & np.isfinite(d_mask)
    for name, a, b in (
        ("GridMET pipeline vs raw (expect 0)", o_pipe, g_raw),
        ("DOR pipeline vs raw (expect 0)", d_pipe, d_raw),
    ):
        delta = np.abs(a - b)
        print(f"  {name}: max abs diff = {float(np.nanmax(delta)):.6e}")

    g_land = g_mask[land3]
    d_land = d_mask[land3]
    o_land = o_pipe[land3]
    d_land_pipe = d_pipe[land3]
    print(
        "  GridMET period(masked land) vs pipeline(land): "
        f"max abs diff = {float(np.max(np.abs(g_land - o_land))):.6e}"
    )
    print(
        "  DOR period(masked land) vs pipeline(land): "
        f"max abs diff = {float(np.max(np.abs(d_land - d_land_pipe))):.6e}"
    )

    print("\n=== print-scales (2006-2014) ===")
    print(
        "  Current period-comparison `3_dor_output.png`: independent 2-98% per panel "
        "(`_vmin_vmax_one` on masked fields), same helper as pipeline default."
    )
    vgm_l, vgm_h = _vmin_vmax_one(g_mask)
    vdm_l, vdm_h = _vmin_vmax_one(d_mask)
    print(f"    _vmin_vmax_one(GridMET masked): {vgm_l:.6f}, {vgm_h:.6f}")
    print(f"    _vmin_vmax_one(DOR masked):     {vdm_l:.6f}, {vdm_h:.6f}")
    print("  Pipeline cmd_dor (unmasked fields, same helper):")
    vo_l, vo_h = _vmin_vmax_one(o_pipe)
    vd_l, vd_h = _vmin_vmax_one(d_pipe)
    print(f"    _vmin_vmax_one(GridMET): {vo_l:.6f}, {vo_h:.6f}")
    print(f"    _vmin_vmax_one(DOR):     {vd_l:.6f}, {vd_h:.6f}")
    ps_l, ps_h = _pair_vmin_vmax(o_pipe, d_pipe)
    print(f"  Pipeline --shared-scale (_pair_vmin_vmax): {ps_l:.6f}, {ps_h:.6f}")
    leg_lo, leg_hi = float(legacy_s3_scale[0]), float(legacy_s3_scale[1])
    print(
        f"  Legacy removed policy (six-array min/max for stage 3): ({leg_lo:.4f}, {leg_hi:.4f})"
    )
    only_0614 = _legacy_global_vmin_vmax([g_mask, d_mask])
    o_lo, o_hi = float(only_0614[0]), float(only_0614[1])
    print(f"  Legacy min/max 2006-2014 masked pair only: ({o_lo:.4f}, {o_hi:.4f})")

    print("\n=== summary ===")
    print(
        "Period-comparison plots now use pipeline-style 2-98% per panel. "
        "Masked vs unmasked fields can shift percentiles slightly at edges; "
        "mean fields match on land."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
