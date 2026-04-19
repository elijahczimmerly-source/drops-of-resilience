"""
Benchmark evaluation-grid suites: dor_native (GridMET mesh), LOCA2 native, NEX native (0.25°).

Set DOR_BENCHMARK_SUITE=dor_native|gridmet_4km|loca2_native|nex_native
(default: dor_native). The token gridmet_4km is a deprecated alias for dor_native.
"""
from __future__ import annotations

import os
from pathlib import Path

import config as cfg

SUITE_DOR_NATIVE = "dor_native"
# Deprecated alias — normalized to SUITE_DOR_NATIVE by benchmark_suite() / normalize_suite()
SUITE_GRIDMET_4KM = "gridmet_4km"
SUITE_LOCA2_NATIVE = "loca2_native"
SUITE_NEX_NATIVE = "nex_native"

VALID_SUITES = frozenset(
    {SUITE_DOR_NATIVE, SUITE_GRIDMET_4KM, SUITE_LOCA2_NATIVE, SUITE_NEX_NATIVE}
)

# Canonical suite ids (no duplicate legacy alias)
CANONICAL_SUITES = frozenset({SUITE_DOR_NATIVE, SUITE_LOCA2_NATIVE, SUITE_NEX_NATIVE})


def normalize_suite(s: str) -> str:
    x = s.strip().lower()
    if x == SUITE_GRIDMET_4KM:
        return SUITE_DOR_NATIVE
    return x


def is_dor_native_suite(suite: str | None = None) -> bool:
    s = suite if suite is not None else benchmark_suite()
    return normalize_suite(s) == SUITE_DOR_NATIVE


def benchmark_suite() -> str:
    raw = os.environ.get("DOR_BENCHMARK_SUITE", SUITE_DOR_NATIVE).strip().lower()
    if raw not in VALID_SUITES:
        raise ValueError(
            f"DOR_BENCHMARK_SUITE must be one of {sorted(VALID_SUITES)}, got {raw!r}"
        )
    return normalize_suite(raw)


def suite_output_dir(suite: str | None = None) -> Path:
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    return {
        SUITE_DOR_NATIVE: cfg.DOR_NATIVE_ROOT,
        SUITE_LOCA2_NATIVE: cfg.LOCA2_NATIVE_ROOT,
        SUITE_NEX_NATIVE: cfg.NEX_NATIVE_ROOT,
    }[s]


def suite_fig_dir(suite: str | None = None) -> Path:
    return suite_output_dir(suite) / "figures"


def suite_multi_panel_fig_root(suite: str | None = None) -> Path:
    """Root for hist / validation / delta multi-panel trees (directly under figures/)."""
    return suite_fig_dir(suite)


def suite_fig_4km_style_root(suite: str | None = None) -> Path:
    """Deprecated name for suite_multi_panel_fig_root (same path for all suites)."""
    return suite_multi_panel_fig_root(suite)


def ensure_suite_dirs(suite: str | None = None) -> None:
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    suite_output_dir(s).mkdir(parents=True, exist_ok=True)
    suite_fig_dir(s).mkdir(parents=True, exist_ok=True)


def suite_label_for_titles(suite: str | None = None) -> str:
    s = normalize_suite(suite if suite is not None else benchmark_suite())
    return {
        SUITE_DOR_NATIVE: "GridMET 4 km",
        SUITE_LOCA2_NATIVE: "LOCA2 native grid",
        SUITE_NEX_NATIVE: "NEX 0.25° native grid",
    }[s]
