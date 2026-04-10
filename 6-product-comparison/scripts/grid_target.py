"""Build target lat/lon (1D) for regridding from a reference GridMET NPZ."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def load_target_grid(gridmet_dir: Path, year: int = 2006) -> tuple[np.ndarray, np.ndarray]:
    """Return (lat_1d_desc, lon_1d_asc) from Cropped_* NPZ on server."""
    # Any year with full calendar — 2006 is leap; use file that exists
    ref = gridmet_dir / f"Cropped_pr_{year}.npz"
    if not ref.is_file():
        raise FileNotFoundError(f"Missing reference grid file: {ref}")
    z = np.load(ref)
    lat = np.asarray(z["lat"], dtype=float)
    lon = np.asarray(z["lon"], dtype=float)
    return lat, lon
