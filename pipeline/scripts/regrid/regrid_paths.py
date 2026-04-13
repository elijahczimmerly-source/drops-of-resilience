"""
Path resolution for local 100 km→4 km regridding (bilinear / NN harness).

Defaults are under the repo `pipeline/` folder so a fresh clone is not tied to a fixed drive letter.
Override any path with environment variables (see `README.md` in this directory).
"""
from __future__ import annotations

import os
from pathlib import Path


def pipeline_root() -> Path:
    """`.../pipeline` (parent of `scripts/regrid`)."""
    return Path(__file__).resolve().parents[2]


def _abspath(key: str, default: str) -> str:
    raw = os.environ.get(key, "").strip()
    return os.path.abspath(raw) if raw else os.path.abspath(default)


def paths_for_regrid() -> dict[str, str]:
    """CMIP6 crop, GridMET crop, optional PRISM/Geo/WindEffect roots."""
    root = pipeline_root()
    return {
        "CMIP6": _abspath(
            "DOR_REGRID_CMIP6_DIR", str(root / "data" / "source_bc")
        ),
        "PRISM": _abspath(
            "DOR_REGRID_PRISM_DIR", str(root / "data" / "prism_800m")
        ),
        "GridMET": _abspath(
            "DOR_REGRID_GRIDMET_DIR", str(root / "data" / "gridmet_cropped")
        ),
        "Geo": _abspath(
            "DOR_REGRID_GEO_DIR", str(root / "data" / "geospatial")
        ),
        "WindEffect": _abspath(
            "DOR_REGRID_WINDEFFECT_DIR",
            str(root / "data" / "wind_effect_static"),
        ),
    }


def output_dir_bilinear() -> str:
    """Prefer `DOR_REGRID_OUTPUT_DIR`; default `pipeline/data/regrid_bilinear`."""
    root = pipeline_root()
    return _abspath(
        "DOR_REGRID_OUTPUT_DIR", str(root / "data" / "regrid_bilinear")
    )


def output_dir_nn() -> str:
    """NN harness: honors legacy `DOR_NN_DATA_DIR`, then `DOR_REGRID_OUTPUT_DIR`, then default."""
    raw = os.environ.get("DOR_NN_DATA_DIR", "").strip()
    if raw:
        return os.path.abspath(raw)
    raw2 = os.environ.get("DOR_REGRID_OUTPUT_DIR", "").strip()
    if raw2:
        return os.path.abspath(raw2)
    root = pipeline_root()
    return os.path.abspath(str(root / "data" / "regrid_nearest_neighbor"))
