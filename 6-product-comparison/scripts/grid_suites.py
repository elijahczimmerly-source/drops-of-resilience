"""
Benchmark evaluation-grid suites: GridMET 4 km (legacy), LOCA2 native, NEX native (0.25°).
Set DOR_BENCHMARK_SUITE=gridmet_4km|loca2_native|nex_native (default: gridmet_4km).
"""
from __future__ import annotations

import os
from pathlib import Path

import config as cfg

SUITE_GRIDMET_4KM = "gridmet_4km"
SUITE_LOCA2_NATIVE = "loca2_native"
SUITE_NEX_NATIVE = "nex_native"

VALID_SUITES = frozenset({SUITE_GRIDMET_4KM, SUITE_LOCA2_NATIVE, SUITE_NEX_NATIVE})


def benchmark_suite() -> str:
    s = os.environ.get("DOR_BENCHMARK_SUITE", SUITE_GRIDMET_4KM).strip().lower()
    if s not in VALID_SUITES:
        raise ValueError(
            f"DOR_BENCHMARK_SUITE must be one of {sorted(VALID_SUITES)}, got {s!r}"
        )
    return s


def suite_output_dir(suite: str | None = None) -> Path:
    s = suite if suite is not None else benchmark_suite()
    if s == SUITE_GRIDMET_4KM:
        return cfg.OUTPUT_DIR
    return cfg.OUTPUT_DIR / "suites" / s


def suite_fig_dir(suite: str | None = None) -> Path:
    s = suite if suite is not None else benchmark_suite()
    if s == SUITE_GRIDMET_4KM:
        return cfg.FIG_DIR
    return suite_output_dir(s) / "figures"


def suite_fig_4km_style_root(suite: str | None = None) -> Path:
    """Multi-panel plot tree (hist / validation / delta) — under FIG_4KM_PLOTS for 4 km, else suites/.../figures/plots."""
    s = suite if suite is not None else benchmark_suite()
    if s == SUITE_GRIDMET_4KM:
        return cfg.FIG_4KM_PLOTS
    return suite_output_dir(s) / "figures" / "plots"


def ensure_suite_dirs(suite: str | None = None) -> None:
    s = suite if suite is not None else benchmark_suite()
    suite_output_dir(s).mkdir(parents=True, exist_ok=True)
    if s != SUITE_GRIDMET_4KM:
        (suite_output_dir(s) / "figures").mkdir(parents=True, exist_ok=True)


def suite_label_for_titles(suite: str | None = None) -> str:
    s = suite if suite is not None else benchmark_suite()
    return {
        SUITE_GRIDMET_4KM: "GridMET 4 km",
        SUITE_LOCA2_NATIVE: "LOCA2 native grid",
        SUITE_NEX_NATIVE: "NEX 0.25° native grid",
    }[s]
