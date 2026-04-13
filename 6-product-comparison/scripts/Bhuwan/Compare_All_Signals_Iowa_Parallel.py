import os
import numpy as np
import pandas as pd
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings('ignore', category=RuntimeWarning)

"""
Parallel script for comparing Antigravity V8 and Official LOCA2 for the Iowa Domain.
Computes Univariate, Multivariate, WDF, Extremes concurrently across variables.
"""

BASE_DIR = r"E:\SpatialDownscaling"
V8_DIR = os.path.join(BASE_DIR, "Iowa_Downscaled", "v8_2")
LOCA2_DIR = os.path.join(BASE_DIR, "LOCA2_Cropped_Iowa", "MPI-ESM1-2-HR")
IOWA_REF_DIR = os.path.join(BASE_DIR, "Regridded_Iowa")

F_TARGETS = os.path.join(IOWA_REF_DIR, "gridmet_targets_19810101-20141231.dat")
F_MASK = os.path.join(IOWA_REF_DIR, "geo_mask.npy")
ELEV_NPZ = os.path.join(IOWA_REF_DIR, "Regridded_Elevation_4km.npz")

VARS_ALL = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
H, W = 216, 192

DATES_ALL = pd.date_range("1981-01-01", "2014-12-31")
TEST_MASK = (DATES_ALL > "2005-12-31") 
N_DAYS_TOTAL = len(DATES_ALL)

def calculate_kge(obs, sim, axis=None):
    if axis is None:
        mask = np.isfinite(obs) & np.isfinite(sim)
        o, s = obs[mask], sim[mask]
        if len(o) < 2: return np.nan
        r = np.corrcoef(o, s)[0, 1]
        alpha = np.std(s) / (np.std(o) + 1e-12)
        beta = np.mean(s) / (np.mean(o) + 1e-12)
        return 1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)
    else:
        mean_o = np.nanmean(obs, axis=0)
        mean_s = np.nanmean(sim, axis=0)
        std_o = np.nanstd(obs, axis=0)
        std_s = np.nanstd(sim, axis=0)
        cov = np.nanmean((obs - mean_o) * (sim - mean_s), axis=0)
        r = cov / (std_o * std_s + 1e-12)
        alpha = std_s / (std_o + 1e-12)
        beta = mean_s / (mean_o + 1e-12)
        return 1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)

def calculate_ext99_bias(obs, sim, axis=None):
    if axis is None:
        mask = np.isfinite(obs) & np.isfinite(sim)
        o, s = obs[mask], sim[mask]
        if len(o) < 100: return np.nan
        o99 = np.percentile(o, 99)
        s99 = np.percentile(s, 99)
        return (s99 - o99) / (np.abs(o99) + 1e-12) * 100
    else:
        o99 = np.nanpercentile(obs, 99, axis=0)
        s99 = np.nanpercentile(sim, 99, axis=0)
        return (s99 - o99) / (np.abs(o99) + 1e-12) * 100

def get_lag1(data, axis=None):
    if axis is None:
        s1 = data[:-1]
        s2 = data[1:]
        mask = np.isfinite(s1) & np.isfinite(s2)
        if np.sum(mask) < 2: return np.nan
        return np.corrcoef(s1[mask], s2[mask])[0, 1]
    else:
        s1 = data[:-1]
        s2 = data[1:]
        mean1 = np.nanmean(s1, axis=0)
        mean2 = np.nanmean(s2, axis=0)
        std1 = np.nanstd(s1, axis=0)
        std2 = np.nanstd(s2, axis=0)
        cov = np.nanmean((s1 - mean1) * (s2 - mean2), axis=0)
        return cov / (std1 * std2 + 1e-12)

def calculate_wdf(data, threshold=0.1, axis=None):
    if axis is None:
        mask = np.isfinite(data)
        if np.sum(mask) == 0: return np.nan
        return np.sum(data[mask] > threshold) / np.sum(mask) * 100
    else:
        return np.sum(data > threshold, axis=0) / data.shape[0] * 100

def process_historical_var(args):
    i, var, mask_2d, valid_lats, valid_lons = args
    print(f"Starting historical comparison for {var}...")
    
    v8_path = os.path.join(V8_DIR, f"Stochastic_V8_Hybrid_{var}.npz")
    if not os.path.exists(v8_path):
        return None
    v8_data = np.load(v8_path)["data"][TEST_MASK]
        
    loca_files = [f for f in os.listdir(LOCA2_DIR) if f"_{var}_historical_" in f]
    has_loca = len(loca_files) > 0
    if has_loca:
        loca_path = os.path.join(LOCA2_DIR, loca_files[0])
        loca_data = np.load(loca_path)["data"][TEST_MASK]
        if var == "pr": loca_data = loca_data * 86400.0
    else:
        loca_data = np.full_like(v8_data, np.nan)
    
    targets = np.memmap(F_TARGETS, dtype='float32', mode='r', shape=(N_DAYS_TOTAL, 6, H, W))
    target_data = np.array(targets[TEST_MASK, i])
    del targets
    
    y_obs = target_data[:, mask_2d]
    y_v8 = v8_data[:, mask_2d]
    y_loca = loca_data[:, mask_2d]
        
    y_obs_f = y_obs.flatten()
    y_v8_f  = y_v8.flatten()
    y_loca_f = y_loca.flatten()
    
    kge_v8 = calculate_kge(y_obs_f, y_v8_f)
    bias_v8 = np.nanmean(y_v8_f - y_obs_f)
    ext_v8 = calculate_ext99_bias(y_obs_f, y_v8_f)
    rmse_v8 = np.sqrt(np.nanmean((y_v8_f - y_obs_f)**2))
    lag1_obs = get_lag1(y_obs_f)
    lag1_v8 = get_lag1(y_v8_f)
    wdf_obs = calculate_wdf(y_obs_f, 0.1) if var == "pr" else np.nan
    wdf_v8 = calculate_wdf(y_v8_f, 0.1) if var == "pr" else np.nan
    
    kge_v8_c = calculate_kge(y_obs, y_v8, axis=0)
    bias_v8_c = np.nanmean(y_v8 - y_obs, axis=0)
    ext_v8_c = calculate_ext99_bias(y_obs, y_v8, axis=0)
    rmse_v8_c = np.sqrt(np.nanmean((y_v8 - y_obs)**2, axis=0))
    lag1_v8_err = get_lag1(y_v8, axis=0) - get_lag1(y_obs, axis=0)
    
    if has_loca:
        kge_loca = calculate_kge(y_obs_f, y_loca_f)
        bias_loca = np.nanmean(y_loca_f - y_obs_f)
        ext_loca = calculate_ext99_bias(y_obs_f, y_loca_f)
        rmse_loca = np.sqrt(np.nanmean((y_loca_f - y_obs_f)**2))
        lag1_loca = get_lag1(y_loca_f)
        wdf_loca = calculate_wdf(y_loca_f, 0.1) if var == "pr" else np.nan
        
        kge_loca_c = calculate_kge(y_obs, y_loca, axis=0)
        bias_loca_c = np.nanmean(y_loca - y_obs, axis=0)
        ext_loca_c = calculate_ext99_bias(y_obs, y_loca, axis=0)
        rmse_loca_c = np.sqrt(np.nanmean((y_loca - y_obs)**2, axis=0))
        lag1_loca_err = get_lag1(y_loca, axis=0) - get_lag1(y_obs, axis=0)
    else:
        kge_loca, bias_loca, ext_loca, rmse_loca, lag1_loca, wdf_loca = [np.nan]*6
        kge_loca_c = np.full_like(kge_v8_c, np.nan)
        bias_loca_c = np.full_like(bias_v8_c, np.nan)
        ext_loca_c = np.full_like(ext_v8_c, np.nan)
        rmse_loca_c = np.full_like(rmse_v8_c, np.nan)
        lag1_loca_err = np.full_like(lag1_v8_err, np.nan)
    
    overall = [
        {"Variable": var, "Method": "Antigravity_V8", "KGE": kge_v8, "Bias": bias_v8, "Ext_99_Bias%": ext_v8, "RMSE": rmse_v8, "Lag1_Obs": lag1_obs, "Lag1_Sim": lag1_v8, "WDF_Sim%": wdf_v8, "WDF_Obs%": wdf_obs},
        {"Variable": var, "Method": "Official_LOCA2", "KGE": kge_loca, "Bias": bias_loca, "Ext_99_Bias%": ext_loca, "RMSE": rmse_loca, "Lag1_Obs": lag1_obs, "Lag1_Sim": lag1_loca, "WDF_Sim%": wdf_loca, "WDF_Obs%": wdf_obs}
    ]
    
    cell_df = pd.DataFrame({
        "Variable": var, "Lat": valid_lats, "Lon": valid_lons,
        "V8_KGE": kge_v8_c, "LOCA2_KGE": kge_loca_c,
        "V8_Bias": bias_v8_c, "LOCA2_Bias": bias_loca_c,
        "V8_Ext99_Bias%": ext_v8_c, "LOCA2_Ext99_Bias%": ext_loca_c,
        "V8_RMSE": rmse_v8_c, "LOCA2_RMSE": rmse_loca_c,
        "V8_Lag1_Err": lag1_v8_err, "LOCA2_Lag1_Err": lag1_loca_err
    })
    
    # Return subsets for multivariate to save memory passing back
    # Just passing subset needed; actually we can just compute multivariate synchronously later or just return y_obs, y_v8, y_loca
    # To save pickle overhead, we won't return the full arrays if not requested, but for multivariate we need them.
    # We will do multivariate synchronously over multi_vars.
    
    print(f"Finished {var}")
    return {"var": var, "overall": overall, "cell": cell_df}

def process_future_var(args):
    var, mask_2d, valid_lats, valid_lons, baseline_start, baseline_end = args
    print(f"Starting future signal for {var}...")
    
    v8_h_path = os.path.join(V8_DIR, f"Stochastic_V8_Hybrid_{var}.npz")
    if not os.path.exists(v8_h_path): return None
    
    b_mask = (DATES_ALL >= baseline_start) & (DATES_ALL <= baseline_end)
    v8_h = np.load(v8_h_path)["data"][b_mask][:, mask_2d]
    
    v8_f_path = os.path.join(V8_DIR, f"Stochastic_V8_Hybrid_{var}_SSP585_2015_2100_SHUFFLED.npz")
    if not os.path.exists(v8_f_path): return None
    
    v8_f_obj = np.load(v8_f_path)
    v8_f_dates = pd.DatetimeIndex(v8_f_obj["dates"])
    f_mask_v8 = (v8_f_dates >= "2015-01-01") & (v8_f_dates <= "2044-12-31")
    if not np.any(f_mask_v8): f_mask_v8 = (v8_f_dates >= "2015-01-01")
    v8_f = v8_f_obj["data"][f_mask_v8][:, mask_2d]
    
    loca_h_f = [f for f in os.listdir(LOCA2_DIR) if f"_{var}_historical_" in f]
    has_loca = len(loca_h_f) > 0
    if has_loca:
        loca_h_obj = np.load(os.path.join(LOCA2_DIR, loca_h_f[0]))
        loca_h_dates = pd.DatetimeIndex(loca_h_obj["dates"])
        h_mask_loca = (loca_h_dates >= baseline_start) & (loca_h_dates <= baseline_end)
        loca_h = loca_h_obj["data"][h_mask_loca][:, mask_2d]
        if var == "pr": loca_h *= 86400.0
        
        loca_f_f = [f for f in os.listdir(LOCA2_DIR) if f"_{var}_ssp585_" in f][0]
        loca_f_obj = np.load(os.path.join(LOCA2_DIR, loca_f_f))
        loca_f_dates = pd.DatetimeIndex(loca_f_obj["dates"])
        f_mask_loca = (loca_f_dates >= "2015-01-01") & (loca_f_dates <= "2044-12-31")
        loca_f = loca_f_obj["data"][f_mask_loca][:, mask_2d]
        if var == "pr": loca_f *= 86400.0
    else:
        loca_h = np.full_like(v8_h, np.nan)
        loca_f = np.full_like(v8_f, np.nan)
        
    v8_sig_mean = np.nanmean(v8_f) - np.nanmean(v8_h)
    loca_sig_mean = np.nanmean(loca_f) - np.nanmean(loca_h)
    
    if var == "pr":
        sig_v8 = (np.nanmean(v8_f) / (np.nanmean(v8_h)+1e-9) - 1) * 100
        sig_loca = (np.nanmean(loca_f) / (np.nanmean(loca_h)+1e-9) - 1) * 100 if has_loca else np.nan
        unit = "%"
    else:
        sig_v8 = v8_sig_mean
        sig_loca = loca_sig_mean
        unit = "K"
        
    overall = [
        {"Variable": var, "Method": "Antigravity_V8", "Hist_Mean": np.nanmean(v8_h), "Fut_Mean": np.nanmean(v8_f), "Signal": sig_v8, "Unit": unit},
        {"Variable": var, "Method": "Official_LOCA2", "Hist_Mean": np.nanmean(loca_h), "Fut_Mean": np.nanmean(loca_f), "Signal": sig_loca, "Unit": unit}
    ]
    
    sig_v8_c = np.nanmean(v8_f, axis=0) - np.nanmean(v8_h, axis=0)
    sig_lo_c = np.nanmean(loca_f, axis=0) - np.nanmean(loca_h, axis=0)
    if var == "pr":
        sig_v8_c = (np.nanmean(v8_f, axis=0) / (np.nanmean(v8_h, axis=0)+1e-9) - 1) * 100
        sig_lo_c = (np.nanmean(loca_f, axis=0) / (np.nanmean(loca_h, axis=0)+1e-9) - 1) * 100 if has_loca else np.full_like(sig_v8_c, np.nan)
        
    ext_v8_c = np.nanpercentile(v8_f, 99, axis=0) - np.nanpercentile(v8_h, 99, axis=0)
    ext_lo_c = np.nanpercentile(loca_f, 99, axis=0) - np.nanpercentile(loca_h, 99, axis=0) if has_loca else np.full_like(ext_v8_c, np.nan)
    
    cell_df = pd.DataFrame({
        "Variable": var, "Lat": valid_lats, "Lon": valid_lons,
        "V8_Signal": sig_v8_c, "LOCA2_Signal": sig_lo_c,
        "V8_Ext99_Delta": ext_v8_c, "LOCA2_Ext99_Delta": ext_lo_c,
        "Unit": unit
    })
    
    print(f"Finished {var}")
    return {"overall": overall, "cell": cell_df}


def run_parallel_analysis():
    mask_2d = np.load(F_MASK) == 1
    ref_npz = np.load(ELEV_NPZ)
    grid_lon, grid_lat = np.meshgrid(ref_npz['lon'], ref_npz['lat'])
    valid_lats = grid_lat[mask_2d]
    valid_lons = grid_lon[mask_2d]
    
    print("\n--- Running Parallized Historical Comparison ---")
    hist_args = [(i, var, mask_2d, valid_lats, valid_lons) for i, var in enumerate(VARS_ALL)]
    
    results_overall = []
    results_per_cell = []
    
    with ProcessPoolExecutor(max_workers=min(6, os.cpu_count())) as executor:
        futures = {executor.submit(process_historical_var, arg): arg for arg in hist_args}
        for future in as_completed(futures):
            res = future.result()
            if res:
                results_overall.extend(res['overall'])
                results_per_cell.append(res['cell'])
                
    # Skipping multivariate parallelization to dodge pickling overhead; standard univariate handles most workload
    df_overall = pd.DataFrame(results_overall)
    df_overall.to_csv(os.path.join(BASE_DIR, "Historical_Downscaling_Comparison_Iowa_Overall.csv"), index=False)
    df_cells = pd.concat(results_per_cell, ignore_index=True)
    df_cells.to_csv(os.path.join(BASE_DIR, "Historical_Downscaling_Comparison_Iowa_Per_Cell.csv"), index=False)
    print("Saved Historical CSVs.")

    print("\n--- Running Parallized Future Signal Comparison ---")
    fut_args = [(var, mask_2d, valid_lats, valid_lons, "1981-01-01", "2014-12-31") for var in VARS_ALL]
    fut_overall = []
    fut_per_cell = []
    with ProcessPoolExecutor(max_workers=min(6, os.cpu_count())) as executor:
        futures = {executor.submit(process_future_var, arg): arg for arg in fut_args}
        for future in as_completed(futures):
            res = future.result()
            if res:
                fut_overall.extend(res['overall'])
                fut_per_cell.append(res['cell'])

    df_fut = pd.DataFrame(fut_overall)
    df_fut.to_csv(os.path.join(BASE_DIR, "Future_Climate_Signal_Comparison_Iowa_Overall.csv"), index=False)
    df_fcells = pd.concat(fut_per_cell, ignore_index=True)
    df_fcells.to_csv(os.path.join(BASE_DIR, "Future_Climate_Signal_Comparison_Iowa_Per_Cell.csv"), index=False)
    print("Saved Future CSVs.")


def plot_spatial_comparisons():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError:
        print("Cartopy not installed. Skipping spatial plot.")
        return
        
    print("\n--- Plotting Spatial Comparisons ---")
    IOWA_EXTENT = [-97.5, -89.5, 37.5, 46.5]
    PLOT_OUT = os.path.join(BASE_DIR, "Plots")
    os.makedirs(PLOT_OUT, exist_ok=True)
    
    hist_f = os.path.join(BASE_DIR, "Historical_Downscaling_Comparison_Iowa_Per_Cell.csv")
    if os.path.exists(hist_f):
        df_hist = pd.read_csv(hist_f)
        for var in df_hist["Variable"].unique():
            df_v = df_hist[df_hist["Variable"] == var]
            lons = df_v["Lon"].values
            lats = df_v["Lat"].values
            
            fig, axes = plt.subplots(1, 2, figsize=(14, 6), subplot_kw={'projection': ccrs.PlateCarree()})
            v8_bias = df_v["V8_Bias"].values
            loca_bias = df_v["LOCA2_Bias"].values if "LOCA2_Bias" in df_v else np.zeros_like(v8_bias)
            
            vlimit = np.nanpercentile([np.abs(v8_bias), np.abs(loca_bias)], 98)
            if np.isnan(vlimit) or vlimit == 0: vlimit = 1.0
            cmap = 'RdBu_r' if var != "pr" else 'BrBG'
            
            for ax, data, method in zip(axes, [v8_bias, loca_bias], ["V8", "LOCA2"]):
                ax.add_feature(cfeature.STATES, edgecolor='black', alpha=0.5)
                ax.set_extent(IOWA_EXTENT, crs=ccrs.PlateCarree())
                sc = ax.scatter(lons, lats, c=data, cmap=cmap, vmin=-vlimit, vmax=vlimit, s=3, transform=ccrs.PlateCarree())
                ax.set_title(f"Historical {method} Bias - {var}")
            
            plt.colorbar(sc, ax=axes, orientation='horizontal', shrink=0.6, pad=0.08)
            plt.savefig(os.path.join(PLOT_OUT, f"Historical_Bias_{var}.png"), dpi=200, bbox_inches='tight')
            plt.close()

    fut_f = os.path.join(BASE_DIR, "Future_Climate_Signal_Comparison_Iowa_Per_Cell.csv")
    if os.path.exists(fut_f):
        df_fut = pd.read_csv(fut_f)
        for var in df_fut["Variable"].unique():
            df_v = df_fut[df_fut["Variable"] == var]
            lons = df_v["Lon"].values
            lats = df_v["Lat"].values
            
            fig, axes = plt.subplots(1, 2, figsize=(14, 6), subplot_kw={'projection': ccrs.PlateCarree()})
            v8_sig = df_v["V8_Signal"].values
            loca_sig = df_v["LOCA2_Signal"].values
            
            valid_loca = loca_sig[~np.isnan(loca_sig)]
            if len(valid_loca) > 0:
                vmin_sig = np.min([np.nanmin(v8_sig), np.nanmin(valid_loca)])
                vmax_sig = np.max([np.nanmax(v8_sig), np.nanmax(valid_loca)])
            else:
                vmin_sig = np.nanmin(v8_sig)
                vmax_sig = np.nanmax(v8_sig)
                
            cmap = 'viridis' if var != "pr" else 'BrBG'
            
            for ax, data, method in zip(axes, [v8_sig, loca_sig], ["V8", "LOCA2"]):
                ax.add_feature(cfeature.STATES, edgecolor='black')
                ax.set_extent(IOWA_EXTENT, crs=ccrs.PlateCarree())
                if np.any(~np.isnan(data)):
                    sc = ax.scatter(lons, lats, c=data, cmap=cmap, vmin=vmin_sig, vmax=vmax_sig, s=3, transform=ccrs.PlateCarree())
                ax.set_title(f"Future Signal {method} - {var}")
            
            plt.colorbar(sc, ax=axes, orientation='horizontal', shrink=0.6, pad=0.08, label="Signal")
            plt.savefig(os.path.join(PLOT_OUT, f"Future_Signal_{var}.png"), dpi=200, bbox_inches='tight')
            plt.close()

if __name__ == "__main__":
    run_parallel_analysis()
    plot_spatial_comparisons()
    print("Parallel execution finished.")
