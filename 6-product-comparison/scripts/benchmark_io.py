"""
Shared loaders: align DOR, LOCA2, NEX, and GridMET obs on the validation calendar (2006–2014).
Also: multi-pipeline DOR + S3 (cmip6_inputs) on validation or full-historical windows for plotting.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import config as cfg
from align import align_to_obs_with_dates
from climate_signal_io import load_cmip6_variable
from grid_suites import (
    SUITE_DOR_NATIVE,
    SUITE_LOCA2_NATIVE,
    SUITE_NEX_NATIVE,
    benchmark_suite,
    normalize_suite,
)
from grid_target import load_target_grid
from interp_from_gridmet_stack import (
    interp_curvilinear_stack_to_target,
    interp_gridmet_stack_to_target,
)
from load_dor import load_dor_variable, validation_mask
from load_loca2 import get_loca_validation_mesh, load_loca_native, load_loca_on_grid
from load_nex import get_nex_validation_mesh, load_nex_native, load_nex_on_grid
from load_obs import load_obs_historical_full, load_obs_validation

LOCA_VARS = frozenset({"pr", "tasmax", "tasmin"})


def _dor_root_with_shared_fallback(canonical: Path) -> Path:
    """Use per-pipeline output dir; optional shared mirror only with DOR_ALLOW_SHARED_BENCHMARK_MIRROR=1."""
    probe = canonical / "Stochastic_V8_Hybrid_pr.npz"
    if probe.is_file():
        return canonical
    if os.environ.get("DOR_ALLOW_SHARED_BENCHMARK_MIRROR", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return canonical
    shared = os.environ.get("DOR_BENCHMARK_SHARED_NPZ_ROOT", "").strip()
    if shared:
        p = Path(shared)
        if (p / "Stochastic_V8_Hybrid_pr.npz").is_file():
            return p
    return canonical


@dataclass
class AlignedStacks:
    """All arrays (T, H, W); same T and dates."""

    obs: np.ndarray
    dor: np.ndarray
    loca2: np.ndarray | None
    nex: np.ndarray
    dates: pd.DatetimeIndex


@dataclass
class MultiProductStacks:
    """GridMET + optional S3 + DOR per pipeline + LOCA2 + NEX; one shared calendar."""

    obs: np.ndarray
    s3: np.ndarray | None
    dor: dict[str, np.ndarray]
    loca2: np.ndarray | None
    nex: np.ndarray | None
    dates: pd.DatetimeIndex
    missing: dict[str, str] = field(default_factory=dict)


def load_aligned_stacks(var: str, suite: str | None = None) -> AlignedStacks:
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    if s == SUITE_DOR_NATIVE:
        return _load_aligned_stacks_gridmet_4km(var)
    if s == SUITE_LOCA2_NATIVE:
        return _load_aligned_stacks_loca2_native(var)
    if s == SUITE_NEX_NATIVE:
        return _load_aligned_stacks_nex_native(var)
    raise ValueError(f"Unknown suite: {s}")


def _load_aligned_stacks_gridmet_4km(var: str) -> AlignedStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, obs_dates = load_obs_validation(var)
    dor_full, dor_dates = load_dor_variable(var)
    m = validation_mask(dor_dates)
    dor_a, obs_a, dates = align_to_obs_with_dates(
        dor_full[m], dor_dates[m], obs, obs_dates
    )

    loca_a: np.ndarray | None
    if var in LOCA_VARS:
        loca, lt = load_loca_on_grid(var, lat_tgt, lon_tgt)
        loca_a, _, dates_l = align_to_obs_with_dates(loca, lt, obs, obs_dates)
        if not dates_l.equals(dates):
            raise ValueError(f"LOCA2 date alignment mismatch for {var}")
        if loca_a.shape != obs_a.shape:
            raise ValueError(f"LOCA2 shape mismatch for {var}")
    else:
        loca_a = None

    nex, nt = load_nex_on_grid(var, lat_tgt, lon_tgt)
    nex_a, _, dates_n = align_to_obs_with_dates(nex, nt, obs, obs_dates)
    if not dates_n.equals(dates):
        raise ValueError(f"NEX date alignment mismatch for {var}")
    if nex_a.shape != obs_a.shape:
        raise ValueError(f"NEX shape mismatch for {var}")

    return AlignedStacks(
        obs=obs_a, dor=dor_a, loca2=loca_a, nex=nex_a, dates=dates
    )


def _load_aligned_stacks_loca2_native(var: str) -> AlignedStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    LAT2, LON2 = get_loca_validation_mesh(lat_tgt, lon_tgt)
    obs, obs_dates = load_obs_validation(var)
    dor_full, dor_dates = load_dor_variable(var)
    m = validation_mask(dor_dates)
    dor_v, obs_v, dates_od = align_to_obs_with_dates(
        dor_full[m], dor_dates[m], obs, obs_dates
    )
    if var in LOCA_VARS:
        loca_tot, lt, _, _ = load_loca_native(
            var, lat_tgt, lon_tgt, scenario="historical", time_start=cfg.VAL_START, time_end=cfg.VAL_END
        )
        parts = [
            ("obs", obs_v, dates_od),
            ("dor", dor_v, dates_od),
            ("loca2", loca_tot, lt),
        ]
        aligned, dates = _align_on_common(parts)
        obs_i = interp_gridmet_stack_to_target(aligned["obs"], lat_tgt, lon_tgt, LAT2, LON2)
        dor_i = interp_gridmet_stack_to_target(aligned["dor"], lat_tgt, lon_tgt, LAT2, LON2)
        loca_a = aligned["loca2"].astype(np.float32, copy=False)
    else:
        aligned, dates = _align_on_common([("obs", obs_v, dates_od), ("dor", dor_v, dates_od)])
        obs_i = interp_gridmet_stack_to_target(aligned["obs"], lat_tgt, lon_tgt, LAT2, LON2)
        dor_i = interp_gridmet_stack_to_target(aligned["dor"], lat_tgt, lon_tgt, LAT2, LON2)
        loca_a = np.full(obs_i.shape, np.nan, dtype=np.float32)
    return AlignedStacks(
        obs=obs_i,
        dor=dor_i,
        loca2=loca_a,
        nex=np.full(obs_i.shape, np.nan, dtype=np.float32),
        dates=dates,
    )


def _load_aligned_stacks_nex_native(var: str) -> AlignedStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    obs, obs_dates = load_obs_validation(var)
    dor_full, dor_dates = load_dor_variable(var)
    m = validation_mask(dor_dates)
    dor_v, obs_v, dates_od = align_to_obs_with_dates(
        dor_full[m], dor_dates[m], obs, obs_dates
    )
    nex_tot, nt, LATn, LONn = load_nex_native(
        var,
        lat_tgt,
        lon_tgt,
        scenario="historical",
        year_start=int(cfg.VAL_START[:4]),
        year_end=int(cfg.VAL_END[:4]),
    )
    parts: list = [
        ("obs", obs_v, dates_od),
        ("dor", dor_v, dates_od),
        ("nex", nex_tot, nt),
    ]
    loca_LAT = loca_LON = None
    if var in LOCA_VARS:
        loca_tot, lt, loca_LAT, loca_LON = load_loca_native(
            var, lat_tgt, lon_tgt, scenario="historical", time_start=cfg.VAL_START, time_end=cfg.VAL_END
        )
        parts.append(("loca2", loca_tot, lt))
    aligned, dates = _align_on_common(parts)
    obs_i = interp_gridmet_stack_to_target(aligned["obs"], lat_tgt, lon_tgt, LATn, LONn)
    dor_i = interp_gridmet_stack_to_target(aligned["dor"], lat_tgt, lon_tgt, LATn, LONn)
    nex_a = aligned["nex"].astype(np.float32, copy=False)
    loca2_a: np.ndarray | None = None
    if "loca2" in aligned and loca_LAT is not None:
        loca2_a = interp_curvilinear_stack_to_target(
            aligned["loca2"], loca_LAT, loca_LON, LATn, LONn
        )
    if nex_a.shape != obs_i.shape:
        raise ValueError(f"NEX native shape {nex_a.shape} vs interp obs {obs_i.shape}")
    return AlignedStacks(
        obs=obs_i,
        dor=dor_i,
        loca2=loca2_a,
        nex=nex_a,
        dates=dates,
    )


def high_pr_obs_date(st: AlignedStacks) -> pd.Timestamp:
    """Calendar day with maximum domain-mean observed pr (for map snapshots)."""
    dom = np.nanmean(st.obs, axis=(1, 2))
    i = int(np.nanargmax(dom))
    return pd.Timestamp(st.dates[i]).normalize()


def _date_index_map(dates: pd.DatetimeIndex) -> dict[pd.Timestamp, int]:
    dn = pd.DatetimeIndex(dates).normalize()
    return {pd.Timestamp(t).normalize(): i for i, t in enumerate(dn)}


def _align_on_common(
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]],
) -> tuple[dict[str, np.ndarray], pd.DatetimeIndex]:
    """Inner-join all series on normalized calendar days."""
    if not parts:
        raise ValueError("No sources to align")
    sets: list[set] = []
    for _, _, ds in parts:
        s = {pd.Timestamp(t).normalize() for t in pd.DatetimeIndex(ds)}
        sets.append(s)
    common = set.intersection(*sets)
    common_sorted = sorted(common)
    if not common_sorted:
        raise ValueError("No overlapping dates between sources")
    out: dict[str, np.ndarray] = {}
    for name, arr, ds in parts:
        idx = _date_index_map(ds)
        ix = [idx[c] for c in common_sorted]
        out[name] = arr[ix]
    return out, pd.DatetimeIndex(common_sorted)


def _load_dor_hist_slice(var: str, root: Path) -> tuple[np.ndarray | None, pd.DatetimeIndex | None, str]:
    p = root / f"Stochastic_V8_Hybrid_{var}.npz"
    if not p.is_file():
        return None, None, f"missing {p.name}"
    z = np.load(p)
    data = np.asarray(z["data"], dtype=np.float64)
    dates = pd.to_datetime(z["dates"])
    m = (dates >= pd.Timestamp(cfg.HIST_START)) & (dates <= pd.Timestamp(cfg.HIST_END))
    if not np.any(m):
        return None, None, "no days in HIST range"
    return data[m], dates[m], ""


def _load_dor_val_slice(var: str, root: Path) -> tuple[np.ndarray | None, pd.DatetimeIndex | None, str]:
    p = root / f"Stochastic_V8_Hybrid_{var}.npz"
    if not p.is_file():
        return None, None, f"missing {p.name}"
    z = np.load(p)
    data = np.asarray(z["data"], dtype=np.float64)
    dates = pd.to_datetime(z["dates"])
    m = validation_mask(dates)
    if not np.any(m):
        return None, None, "no validation days"
    return data[m], dates[m], ""


def load_multi_product_validation(
    var: str, suite: str | None = None
) -> MultiProductStacks:
    """2006–2014: GridMET, S3 cmip6_inputs, DOR for each default pipeline, LOCA2, NEX."""
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    if s == SUITE_DOR_NATIVE:
        return _load_multi_product_validation_gridmet(var)
    if s == SUITE_LOCA2_NATIVE:
        return _load_multi_product_validation_loca2_native(var)
    if s == SUITE_NEX_NATIVE:
        return _load_multi_product_validation_nex_native(var)
    raise ValueError(f"Unknown suite: {s}")


def _load_multi_product_validation_gridmet(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_validation(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.VAL_START, cfg.VAL_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_val_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    if var in LOCA_VARS:
        try:
            loca, lt = load_loca_on_grid(var, lat_tgt, lon_tgt)
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    try:
        nex, nt = load_nex_on_grid(
            var, lat_tgt, lon_tgt, scenario="historical", year_start=2006, year_end=2014
        )
        parts.append(("nex", nex, nt))
    except (FileNotFoundError, OSError) as e:
        missing["nex"] = str(e)

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    nex_arr = aligned.pop("nex", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )


def _load_multi_product_validation_loca2_native(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    LAT2, LON2 = get_loca_validation_mesh(lat_tgt, lon_tgt)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_validation(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.VAL_START, cfg.VAL_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_val_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    if var in LOCA_VARS:
        try:
            loca, lt, _, _ = load_loca_native(
                var, lat_tgt, lon_tgt, scenario="historical", time_start=cfg.VAL_START, time_end=cfg.VAL_END
            )
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v

    obs_a = interp_gridmet_stack_to_target(obs_a, lat_tgt, lon_tgt, LAT2, LON2)
    if s3_arr is not None:
        s3_arr = interp_gridmet_stack_to_target(s3_arr, lat_tgt, lon_tgt, LAT2, LON2)
    for k in list(dor_out.keys()):
        dor_out[k] = interp_gridmet_stack_to_target(dor_out[k], lat_tgt, lon_tgt, LAT2, LON2)
    if loca_arr is not None:
        loca_arr = loca_arr.astype(np.float32, copy=False)
    else:
        loca_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    nex_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )


def _load_multi_product_validation_nex_native(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    LATn, LONn = get_nex_validation_mesh(lat_tgt, lon_tgt)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_validation(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.VAL_START, cfg.VAL_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_val_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    loca_LAT = loca_LON = None
    if var in LOCA_VARS:
        try:
            loca, lt, loca_LAT, loca_LON = load_loca_native(
                var, lat_tgt, lon_tgt, scenario="historical", time_start=cfg.VAL_START, time_end=cfg.VAL_END
            )
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    try:
        nex, nt, _, _ = load_nex_native(
            var,
            lat_tgt,
            lon_tgt,
            scenario="historical",
            year_start=int(cfg.VAL_START[:4]),
            year_end=int(cfg.VAL_END[:4]),
        )
        parts.append(("nex", nex, nt))
    except (FileNotFoundError, OSError) as e:
        missing["nex"] = str(e)

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    nex_arr = aligned.pop("nex", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v

    obs_a = interp_gridmet_stack_to_target(obs_a, lat_tgt, lon_tgt, LATn, LONn)
    if s3_arr is not None:
        s3_arr = interp_gridmet_stack_to_target(s3_arr, lat_tgt, lon_tgt, LATn, LONn)
    for k in list(dor_out.keys()):
        dor_out[k] = interp_gridmet_stack_to_target(dor_out[k], lat_tgt, lon_tgt, LATn, LONn)
    if loca_arr is not None and loca_LAT is not None:
        loca_arr = interp_curvilinear_stack_to_target(loca_arr, loca_LAT, loca_LON, LATn, LONn)
    else:
        loca_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    if nex_arr is None:
        nex_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    else:
        nex_arr = nex_arr.astype(np.float32, copy=False)
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )


def load_multi_product_historical(
    var: str, suite: str | None = None
) -> MultiProductStacks:
    """1981–2014: GridMET, S3, DOR per default pipeline, LOCA2, NEX (inner-join calendars)."""
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    if s == SUITE_DOR_NATIVE:
        return _load_multi_product_historical_gridmet(var)
    if s == SUITE_LOCA2_NATIVE:
        return _load_multi_product_historical_loca2_native(var)
    if s == SUITE_NEX_NATIVE:
        return _load_multi_product_historical_nex_native(var)
    raise ValueError(f"Unknown suite: {s}")


def _load_multi_product_historical_gridmet(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_historical_full(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.HIST_START, cfg.HIST_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_hist_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    if var in LOCA_VARS:
        try:
            loca, lt = load_loca_on_grid(
                var,
                lat_tgt,
                lon_tgt,
                scenario="historical",
                time_start=cfg.HIST_START,
                time_end=cfg.HIST_END,
            )
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    try:
        nex, nt = load_nex_on_grid(
            var,
            lat_tgt,
            lon_tgt,
            scenario="historical",
            year_start=int(cfg.HIST_START[:4]),
            year_end=int(cfg.HIST_END[:4]),
        )
        parts.append(("nex", nex, nt))
    except (FileNotFoundError, OSError) as e:
        missing["nex"] = str(e)

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    nex_arr = aligned.pop("nex", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )


def _load_multi_product_historical_loca2_native(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    LAT2, LON2 = get_loca_validation_mesh(lat_tgt, lon_tgt)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_historical_full(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.HIST_START, cfg.HIST_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_hist_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    if var in LOCA_VARS:
        try:
            loca, lt, _, _ = load_loca_native(
                var,
                lat_tgt,
                lon_tgt,
                scenario="historical",
                time_start=cfg.HIST_START,
                time_end=cfg.HIST_END,
            )
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v

    obs_a = interp_gridmet_stack_to_target(obs_a, lat_tgt, lon_tgt, LAT2, LON2)
    if s3_arr is not None:
        s3_arr = interp_gridmet_stack_to_target(s3_arr, lat_tgt, lon_tgt, LAT2, LON2)
    for k in list(dor_out.keys()):
        dor_out[k] = interp_gridmet_stack_to_target(dor_out[k], lat_tgt, lon_tgt, LAT2, LON2)
    if loca_arr is not None:
        loca_arr = loca_arr.astype(np.float32, copy=False)
    else:
        loca_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    nex_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )


def _load_multi_product_historical_nex_native(var: str) -> MultiProductStacks:
    lat_tgt, lon_tgt = load_target_grid(cfg.CROPPED_GRIDMET, year=2006)
    LATn, LONn = get_nex_validation_mesh(lat_tgt, lon_tgt)
    missing: dict[str, str] = {}
    parts: list[tuple[str, np.ndarray, pd.DatetimeIndex]] = []

    obs, od = load_obs_historical_full(var)
    parts.append(("obs", obs, od))

    if cfg.CMIP6_HIST_DAT.is_file():
        try:
            s3, sd = load_cmip6_variable(cfg.CMIP6_HIST_DAT, var, cfg.HIST_START, cfg.HIST_END)
            parts.append(("s3", s3, sd))
        except OSError as e:
            missing["s3"] = str(e)
    else:
        missing["s3"] = "CMIP6_HIST_DAT not found"

    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        root_eff = _dor_root_with_shared_fallback(root)
        dslice, dd, err = _load_dor_hist_slice(var, root_eff)
        if dslice is None:
            missing[f"dor_{pid}"] = err
            continue
        parts.append((f"dor_{pid}", dslice, dd))

    loca_LAT = loca_LON = None
    if var in LOCA_VARS:
        try:
            loca, lt, loca_LAT, loca_LON = load_loca_native(
                var,
                lat_tgt,
                lon_tgt,
                scenario="historical",
                time_start=cfg.HIST_START,
                time_end=cfg.HIST_END,
            )
            parts.append(("loca2", loca, lt))
        except (FileNotFoundError, OSError, ValueError) as e:
            missing["loca2"] = str(e)
    else:
        missing["loca2"] = "not_applicable_external"

    try:
        nex, nt, _, _ = load_nex_native(
            var,
            lat_tgt,
            lon_tgt,
            scenario="historical",
            year_start=int(cfg.HIST_START[:4]),
            year_end=int(cfg.HIST_END[:4]),
        )
        parts.append(("nex", nex, nt))
    except (FileNotFoundError, OSError) as e:
        missing["nex"] = str(e)

    aligned, dates = _align_on_common(parts)
    s3_arr = aligned.pop("s3", None)
    loca_arr = aligned.pop("loca2", None)
    nex_arr = aligned.pop("nex", None)
    obs_a = aligned.pop("obs")
    dor_out: dict[str, np.ndarray] = {}
    for k, v in list(aligned.items()):
        if k.startswith("dor_"):
            dor_out[k.replace("dor_", "", 1)] = v

    obs_a = interp_gridmet_stack_to_target(obs_a, lat_tgt, lon_tgt, LATn, LONn)
    if s3_arr is not None:
        s3_arr = interp_gridmet_stack_to_target(s3_arr, lat_tgt, lon_tgt, LATn, LONn)
    for k in list(dor_out.keys()):
        dor_out[k] = interp_gridmet_stack_to_target(dor_out[k], lat_tgt, lon_tgt, LATn, LONn)
    if loca_arr is not None and loca_LAT is not None:
        loca_arr = interp_curvilinear_stack_to_target(loca_arr, loca_LAT, loca_LON, LATn, LONn)
    else:
        loca_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    if nex_arr is None:
        nex_arr = np.full_like(obs_a, np.nan, dtype=np.float32)
    else:
        nex_arr = nex_arr.astype(np.float32, copy=False)
    return MultiProductStacks(
        obs=obs_a,
        s3=s3_arr,
        dor=dor_out,
        loca2=loca_arr,
        nex=nex_arr,
        dates=dates,
        missing=missing,
    )
