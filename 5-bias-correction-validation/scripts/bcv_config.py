"""Shared paths and constants for bias-correction-validation."""

from pathlib import Path

SERVER = r"\\abe-cylo\modelsdev\Projects\WRC_DOR"
DATA = Path(SERVER) / "Data" / "Cropped_Iowa"

BC_DIR = DATA / "BC"
BCPC_DIR = DATA / "BCPC"
RAW_DIR = DATA / "Raw"
OBS_DIR = DATA / "GridMET"

MODELS = ["CMCC", "EC", "GFDL", "MPI", "MRI"]
METHODS = [
    "qdm",
    "mv_bcca",
    "mv_ecc_schaake",
    "mv_gaussian_copula",
    "mv_mbcn_iterative",
    "mv_otbc",
    "mv_r2d2",
    "mv_spatial_mbc",
]

# Short name -> Raw NPZ filename token
MODEL_RAW_TOKEN = {
    "CMCC": "CMCC-ESM2",
    "EC": "EC-Earth3",
    "GFDL": "GFDL-CM4",
    "MPI": "MPI-ESM1-2-HR",
    "MRI": "MRI-ESM2-0",
}

VAR_MAP = {
    "pr": "pr",
    "tasmax": "tmmx",
    "tasmin": "tmmn",
    "rsds": "srad",
    "huss": "sph",
    "wind": "vs",
}

BC_VARS = ("pr", "tasmax", "tasmin", "rsds", "huss", "wind")

VAL_START = 2006
VAL_END = 2014

OUT_DIR = Path(__file__).resolve().parent / "output"
METRICS_DIR = OUT_DIR / "metrics"
PLOTS_DIR = OUT_DIR / "plots"
