"""
Central paths for product-comparison. Override with environment variables when needed.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of product-comparison/
PC_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PC_ROOT.parent

WRC_DOR_SERVER = os.environ.get(
    "WRC_DOR_SERVER",
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR",
)
WRC_DOR = Path(WRC_DOR_SERVER)

DOWNSCALED = WRC_DOR / "Spatial_Downscaling" / "Downscaled_Products"
LOCA2_ROOT = DOWNSCALED / "LOCA2"
NEX_ROOT = DOWNSCALED / "NEX-GDDP-CMIP6_Files"

CROPPED_GRIDMET = WRC_DOR / "Data" / "Cropped_Iowa" / "GridMET"

GCM_FOLDER = "MPI-ESM1-2-HR"

# Iowa + buffer (matches pipeline crop scripts; GridMET files are 216 x 192)
LAT_MIN = 37.5
LAT_MAX = 46.5
LON_MIN = -97.5
LON_MAX = -89.5

# test8 Table1/2 validation mask: 2006-01-01 .. 2014-12-31
VAL_START = "2006-01-01"
VAL_END = "2014-12-31"

# DOR stochastic outputs (PR intensity blend 0.65 by default)
_DEFAULT_DOR = (
    REPO_ROOT
    / "test8-v2-pr-intensity"
    / "output"
    / "test8_v2_pr_intensity"
    / "experiment_blend0p65"
)
DOR_PRODUCT_DIR = Path(os.environ.get("DOR_PRODUCT_ROOT", str(_DEFAULT_DOR)))

GEO_MASK = (
    REPO_ROOT / "test8-v2-pr-intensity" / "data" / "geo_mask.npy"
)

GRIDMET_TARGETS = (
    REPO_ROOT
    / "test8-v2-pr-intensity"
    / "data"
    / "gridmet_targets_19810101-20141231.dat"
)

# Internal variable order (matches test8)
VARS = ("pr", "tasmax", "tasmin", "rsds", "wind", "huss")

# GridMET NPZ stem names on server
GRIDMET_NPZ_KEYS = {
    "pr": "pr",
    "tasmax": "tmmx",
    "tasmin": "tmmn",
    "rsds": "srad",
    "wind": "vs",
    "huss": "sph",
}

# LOCA2 / NEX netcdf variable names
EXTERNAL_VAR = {
    "pr": "pr",
    "tasmax": "tasmax",
    "tasmin": "tasmin",
    "rsds": "rsds",
    "wind": "sfcWind",
    "huss": "huss",
}

NEX_SUBDIR = {
    "pr": "pr",
    "tasmax": "tasmax",
    "tasmin": "tasmin",
    "rsds": "rsds",
    "wind": "sfcWind",
    "huss": "huss",
}

NEX_FILE_PATTERN = {
    "pr": "pr_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
    "tasmax": "tasmax_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
    "tasmin": "tasmin_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
    "rsds": "rsds_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
    "wind": "sfcWind_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
    "huss": "huss_day_MPI-ESM1-2-HR_historical_{year}_gn.nc",
}

OUTPUT_DIR = PC_ROOT / "output"
FIG_DIR = OUTPUT_DIR / "figures"

H, W = 216, 192
N_DAYS_MAIN = 12418  # 1981-01-01 .. 2014-12-31
