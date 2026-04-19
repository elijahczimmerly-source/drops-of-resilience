"""
Central paths for product-comparison. Override with environment variables when needed.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of product-comparison/
PC_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PC_ROOT.parent

# Legacy task folder `data/` (memmaps, mask) — fallback if no local cache / env
_DATA_LEGACY = REPO_ROOT / "4-test8-v2-pr-intensity" / "data"

# Local mirror of UNC `\\abe-cylo\...\WRC_DOR` (e.g. robocopy Regridded_Iowa memmaps + Cropped_* NPZ to D:)
_LOCAL_WRC_CACHE = Path(os.environ.get("DOR_LOCAL_WRC_CACHE", r"D:\drops-resilience-data\WRC_DOR_cache"))
_LOCAL_REGRIDDED = _LOCAL_WRC_CACHE / "Spatial_Downscaling" / "test8_v2" / "Regridded_Iowa"
_LOCAL_MV_OTBC = _LOCAL_REGRIDDED / "MPI" / "mv_otbc"
_LOCAL_CROPPED_GRIDMET = _LOCAL_WRC_CACHE / "Data" / "Cropped_Iowa" / "GridMET"


def _memmap_default(env_key: str, local_file: Path, legacy_name: str) -> Path:
    if os.environ.get(env_key):
        return Path(os.environ[env_key])
    if local_file.is_file():
        return local_file
    return _DATA_LEGACY / legacy_name


WRC_DOR_SERVER = os.environ.get(
    "WRC_DOR_SERVER",
    r"\\abe-cylo\modelsdev\Projects\WRC_DOR",
)
WRC_DOR = Path(WRC_DOR_SERVER)

DOWNSCALED = WRC_DOR / "Spatial_Downscaling" / "Downscaled_Products"
LOCA2_ROOT = DOWNSCALED / "LOCA2"
NEX_ROOT = DOWNSCALED / "NEX-GDDP-CMIP6_Files"

if os.environ.get("DOR_CROPPED_GRIDMET_DIR"):
    CROPPED_GRIDMET = Path(os.environ["DOR_CROPPED_GRIDMET_DIR"])
elif (_LOCAL_CROPPED_GRIDMET / "Cropped_pr_2006.npz").is_file():
    CROPPED_GRIDMET = _LOCAL_CROPPED_GRIDMET
else:
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

# Full historical overlap with gridmet_targets / cmip6_inputs main stack
HIST_START = "1981-01-01"
HIST_END = "2014-12-31"

# Climate-signal windows (match Bhuwan Compare_All_Signals_Iowa_Parallel.py)
SIGNAL_HIST_START = os.environ.get("DOR_SIGNAL_HIST_START", "1981-01-01")
SIGNAL_HIST_END = os.environ.get("DOR_SIGNAL_HIST_END", "2014-12-31")
SIGNAL_FUT_START = os.environ.get("DOR_SIGNAL_FUT_START", "2015-01-01")
SIGNAL_FUT_END = os.environ.get("DOR_SIGNAL_FUT_END", "2044-12-31")

# Driving memmaps (S3) — same env names as pipeline _test8_sd_impl
CMIP6_HIST_DAT = _memmap_default(
    "DOR_TEST8_CMIP6_HIST_DAT",
    _LOCAL_MV_OTBC / "cmip6_inputs_19810101-20141231.dat",
    "cmip6_inputs_19810101-20141231.dat",
)
CMIP6_FUTURE_DAT = _memmap_default(
    "DOR_TEST8_CMIP6_FUTURE_DAT",
    _LOCAL_MV_OTBC / "cmip6_inputs_ssp585_20150101-21001231.dat",
    "cmip6_inputs_ssp585_20150101-21001231.dat",
)

# Optional coarse-stage roots (S1 raw / S2 BC); set when available
_LOCAL_RAW_IOWA = _LOCAL_WRC_CACHE / "Data" / "Cropped_Iowa" / "Raw"
if os.environ.get("DOR_SCENARIO_RAW_ROOT"):
    S1_RAW_CROPPED_ROOT = Path(os.environ["DOR_SCENARIO_RAW_ROOT"])
elif _LOCAL_RAW_IOWA.is_dir():
    S1_RAW_CROPPED_ROOT = _LOCAL_RAW_IOWA
else:
    S1_RAW_CROPPED_ROOT = WRC_DOR / "Data" / "Cropped_Iowa" / "Raw"

_LOCAL_BCPC_MV = _LOCAL_WRC_CACHE / "Data" / "Cropped_Iowa" / "BCPC" / "MPI" / "mv_otbc"
if os.environ.get("DOR_CROPPED_BC_ROOT"):
    DOR_CROPPED_BC_ROOT = Path(os.environ["DOR_CROPPED_BC_ROOT"])
elif _LOCAL_BCPC_MV.is_dir():
    DOR_CROPPED_BC_ROOT = _LOCAL_BCPC_MV
else:
    DOR_CROPPED_BC_ROOT = None

# Default DOR output dirs per pipeline id (override with DOR_PRODUCT_ROOT for active run)
def _dor_repo_out(pipeline_id: str, subdir: str) -> Path:
    return REPO_ROOT / "pipeline" / "output" / pipeline_id / subdir


def _build_dor_default_outputs() -> dict[str, Path]:
    """
    Prefer `DOR_PIPELINE_OUTPUT_ROOT` (parent of test8_v*/… NPZ trees), else repo `pipeline/output/`,
    else a local mirror on D: when present (see WORKLOG_NATIVE_RESOLUTION.md).
    """
    env_root = os.environ.get("DOR_PIPELINE_OUTPUT_ROOT", "").strip()
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(REPO_ROOT / "pipeline" / "output")
    # Common full-machine mirror (no repo-local pipeline outputs)
    candidates.append(Path(r"D:\drops-resilience-data\dor_pipeline_output"))

    chosen: Path | None = None
    for base in candidates:
        probe = base / "test8_v4" / "experiment_blend0p65" / "Stochastic_V8_Hybrid_pr.npz"
        if probe.is_file():
            chosen = base
            break
    if chosen is None:
        chosen = REPO_ROOT / "pipeline" / "output"

    return {
        "test8_v2": chosen / "test8_v2" / "parity",
        "test8_v3": chosen / "test8_v3" / "experiment_blend0p65",
        "test8_v4": chosen / "test8_v4" / "experiment_blend0p65",
    }


DOR_DEFAULT_OUTPUTS = _build_dor_default_outputs()

# DOR stochastic outputs (PR intensity blend 0.65; WDF default from test8_v4)
_DEFAULT_DOR = DOR_DEFAULT_OUTPUTS["test8_v4"]
DOR_PRODUCT_DIR = Path(os.environ.get("DOR_PRODUCT_ROOT", str(_DEFAULT_DOR)))

GEO_MASK = _memmap_default(
    "DOR_TEST8_GEO_MASK_NPY",
    _LOCAL_REGRIDDED / "geo_mask.npy",
    "geo_mask.npy",
)

GRIDMET_TARGETS = _memmap_default(
    "DOR_TEST8_GRIDMET_TARGETS_DAT",
    _LOCAL_REGRIDDED / "gridmet_targets_19810101-20141231.dat",
    "gridmet_targets_19810101-20141231.dat",
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

NEX_FILE_PATTERN_SSP585 = {
    "pr": "pr_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
    "tasmax": "tasmax_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
    "tasmin": "tasmin_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
    "rsds": "rsds_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
    "wind": "sfcWind_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
    "huss": "huss_day_MPI-ESM1-2-HR_ssp585_{year}_gn.nc",
}

OUTPUT_DIR = PC_ROOT / "output"
FIG_DIR = OUTPUT_DIR / "figures"

# Validation side-by-side maps (GridMET | DOR) — see plot_validation_period.py
FIG_VALIDATION_INDIVIDUAL_DAYS = FIG_DIR / "dor side-by-side" / "individual days"
FIG_VALIDATION_TIME_AGG = FIG_DIR / "dor side-by-side" / "time aggregated"

# Extended figure tree (multi-product / multi-pipeline)
FIG_BY_STAGE = FIG_DIR / "by_stage"
FIG_BY_PIPELINE = FIG_DIR / "by_pipeline"
FIG_4KM_PLOTS = FIG_DIR / "4km_plots"

# Calendar dates for validation_maps_* (side-by-side obs vs DOR); high-pr day added at runtime from obs.
VALIDATION_MAP_DATES_FIXED = (
    "2007-01-20",  # winter
    "2008-04-18",  # spring
    "2009-07-25",  # summer
    "2010-10-12",  # fall
)

# Y-axis labels for domain-mean time series
VAR_YLABEL = {
    "pr": "Domain mean (mm day⁻¹)",
    "tasmax": "Domain mean (K)",
    "tasmin": "Domain mean (K)",
    "rsds": "Domain mean (W m⁻²)",
    "wind": "Domain mean (m s⁻¹)",
    "huss": "Domain mean (kg kg⁻¹)",
}

H, W = 216, 192
N_DAYS_MAIN = 12418  # 1981-01-01 .. 2014-12-31
