"""
Week 1 – Drops of Resilience: File Loading & Variable Extraction
Load the sample NetCDF (huss) and the other key variables from the CYLO directory.
"""

from typing import Any


import os
import xarray as xr
import matplotlib
matplotlib.use("Agg")  # non-interactive backend so script exits without waiting for plot window
import matplotlib.pyplot as plt

# Use the server path when connected, or set to a local folder if you've copied the file
DATA_DIR = r"\\abe-cylo\public\CMIP\Download\km100"
# DATA_DIR = r"C:\path\to\local\copy"  # Uncomment and set if using a local copy

# All 7 variables from the doc: huss (sample) + pr, tasmax, tasmin, rsds, uas, vas
# CMIP naming: {variable}_day_{model}_{experiment}_{run}_{grid}_{timerange}.nc
VARIABLES = [
    "huss",   # specific humidity (sample file)
    "pr",     # precipitation
    "tasmax", # maximum temperature
    "tasmin", # minimum temperature
    "rsds",   # surface downwelling shortwave (solar) radiation
    "uas",    # eastward wind
    "vas",    # northward wind
]

# Same model, run, grid, and time range as the sample file — only the variable prefix changes
FILE_SUFFIX = "day_EC-Earth3P_highresSST-present_r1i1p1f1_gr_20150401-20150430.nc"

# rsds not available in that scenario; use control-1950 file instead
RSDS_FILENAME = "rsds_day_EC-Earth3P_control-1950_r2i1p2f1_gr_19500101-19501231.nc"


def nc_path(variable: str) -> str:
    """Build the full path for a variable's NetCDF file."""
    if variable == "rsds":
        filename = RSDS_FILENAME
    else:
        filename = f"{variable}_{FILE_SUFFIX}"
    return f"{DATA_DIR}\\{filename}"


def load_netcdf(path: str) -> xr.Dataset:
    """Load a NetCDF file and return an xarray Dataset."""
    return xr.open_dataset(path)


def load_all_variables(data_dir: str = DATA_DIR) -> xr.Dataset:
    """
    Load all 7 key variables from the directory and merge into one Dataset.

    How it works:
    1. Each variable lives in its own file with the same naming convention:
       {variable}_day_EC-Earth3P_highresSST-present_r1i1p1f1_gr_20150401-20150430.nc
    2. We open each file with xarray (lazy by default — data read when needed).
    3. xr.merge() combines them on shared dimensions (time, lat, lon). Each file
       has one data variable and the same coordinates, so we get one dataset
       with 7 data variables and one set of coordinates.
    Missing files are skipped with a warning so the script still runs with available data.
    """
    datasets = []
    for var in VARIABLES:
        path = nc_path(var)
        if not os.path.isfile(path):
            print(f"  Skip (not found): {var}")
            continue
        try:
            ds = load_netcdf(path)
            datasets.append(ds)
        except OSError as e:
            print(f"  Skip ({var}): {e}")
            continue

    if not datasets:
        raise FileNotFoundError("No variable files could be loaded from " + data_dir)
    # compat='override': some variables (e.g. height) differ per file; keep first
    return xr.merge(datasets, compat="override")

def crop_dataset(ds: xr.Dataset, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> xr.Dataset:
    """Crop a dataset to a given latitude and longitude range."""
    return ds.sel(lat=slice(min_lat, max_lat), lon=slice(min_lon, max_lon))

if __name__ == "__main__":
    print("Loading all variables from directory...")
    print(f"  Dir: {DATA_DIR}\n")

    if not os.path.isdir(DATA_DIR):
        print(
            f"Data directory not found or not accessible.\n"
            f"Connect to the network (e.g. map \\abe-cylo) or set DATA_DIR to a local copy."
        )
        raise SystemExit(1)

    try:
        ds = load_all_variables()
        print("Loaded successfully.")
        print("\nDataset structure (all variables):")
        print(ds)
        ds.huss.sel(lat=42.026175, lon=360-93.64843183333333, method="nearest").plot()
        plt.title("Specific Humidity at Ames, IA")
        plt.savefig("huss_ames_ia.png")
        plt.close()
        ds.huss.sel(time="2015-04-01", method="nearest").plot()
        plt.title("Specific Humidity on April 1, 2015")
        plt.savefig("huss_april_1_2015.png")
        plt.close()
        print("\nSaved plots: huss_ames_ia.png, huss_april_1_2015.png")
        croppsed_ds = crop_dataset(ds, 40.6, 43.5, 263.5, 270.9)
        croppsed_ds.huss.sel(time="2015-04-01", method="nearest").plot()
        plt.title("Specific Humidity on April 1, 2015 in Iowa")
        plt.savefig("huss_april_1_2015_iowa.png")
        plt.close()
        print("\nSaved plots: huss_ames_ia.png, huss_april_1_2015.png, huss_april_1_2015_iowa.png")
    except FileNotFoundError as e:
        print(
            "File not found. If you're not on the network, copy the files locally "
            "and set DATA_DIR in this script to that folder."
        )
        raise
    except OSError as e:
        print(f"Could not open file (e.g. network drive not mounted): {e}")
        raise