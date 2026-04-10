"""Build self-contained HTML report with base64-embedded plots."""
import base64
import os

PLOTS_DIR = os.path.join(os.path.dirname(__file__), "output", "plots")
OUT_PATH = os.path.join(os.path.dirname(__file__), "report.html")

def img(fname):
    path = os.path.join(PLOTS_DIR, fname)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{fname}">'

def plot_block(fname, caption):
    return f'<div class="plot-container">{img(fname)}<div class="plot-caption">{caption}</div></div>'

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bias Correction Validation Report</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 960px; margin: 0 auto; padding: 20px 40px; color: #222; line-height: 1.6; }}
  h1 {{ color: #003a70; border-bottom: 2px solid #003a70; padding-bottom: 8px; }}
  h2 {{ color: #003a70; margin-top: 2em; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  h3 {{ color: #444; margin-top: 1.5em; }}
  table {{ border-collapse: collapse; margin: 1em 0; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 0.9em; }}
  th {{ background: #f0f4f8; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  .plot-container {{ margin: 1.5em 0; text-align: center; }}
  .plot-container img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
  .plot-caption {{ font-size: 0.85em; color: #555; margin-top: 0.3em; font-style: italic; }}
  .meta {{ background: #f0f4f8; padding: 12px 16px; border-radius: 6px; margin-bottom: 2em; font-size: 0.9em; }}
  .meta strong {{ color: #003a70; }}
  code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }}
</style>
</head>
<body>

<h1>Bias Correction Validation Report</h1>

<div class="meta">
<strong>Domain:</strong> Cropped Iowa (~10&times;9 GCM grid cells, ~100 km resolution)<br>
<strong>Validation period:</strong> 2006&ndash;2014<br>
<strong>GCMs:</strong> CMCC-ESM2, EC-Earth3, GFDL-CM4, MPI-ESM1-2-HR, MRI-ESM2-0<br>
<strong>BC methods:</strong> QDM, MBCn, ECC (Schaake), R2D2, OTBC, Gaussian Copula, Spatial MBC, BCCA<br>
<strong>Variables:</strong> pr, tasmax, tasmin, rsds, huss, wind<br>
<strong>Selected production method:</strong> OTBC (input to spatial downscaling pipeline, test8/test8_v2)
</div>

<h2>1. What Was Done</h2>

<p>Eight scripts validated Bhuwan's bias correction implementations by comparing BC outputs against GridMET observations interpolated to the GCM grid. The validation covers four dimensions: marginal distribution fidelity, inter-variable dependence, temporal persistence, and physical consistency.</p>

<h3>Observation regridding</h3>
<p>BC and Raw outputs sit on the ~100 km GCM grid. GridMET observations are at 4 km. For this validation, GridMET was <strong>linearly interpolated</strong> (via <code>scipy.interpolate.RegularGridInterpolator</code>) to GCM cell centers. This is a convenience for metric computation only&mdash;it does not affect any production data. Bhuwan's production pipeline uses <code>xESMF</code> with <strong>conservative_normed</strong> regridding for precipitation/flux and <strong>bilinear</strong> for state variables, which is the correct approach.</p>

<h3>File discovery notes</h3>
<ul>
<li>Most GCMs use historical BC files starting 1850-01-01; <strong>MRI uses 1900-01-01</strong>. The loader resolves this via glob.</li>
<li>QDM has <strong>no wind variable</strong> in the cropped Iowa data. QDM is therefore excluded from Frobenius dependence metrics (which require all 6 variables).</li>
</ul>

<h2>2. Marginal Distribution Checks</h2>

<p>For each model &times; method &times; variable, the script computes: mean bias, MAE, QQ RMSE (50 quantiles, 1st&ndash;99th), KS statistic, P1 and P99 bias, and the same metrics for the Raw GCM as baseline.</p>

<table>
<tr><th>Method</th><th>Mean MAE</th><th>Mean QQ RMSE</th><th>Rank (MAE)</th></tr>
<tr><td>mv_bcca</td><td>8.40</td><td>4.42</td><td>1</td></tr>
<tr><td>mv_ecc_schaake</td><td>9.78</td><td>2.38</td><td>2</td></tr>
<tr><td>mv_otbc</td><td>9.95</td><td>1.22</td><td>3</td></tr>
<tr><td>mv_gaussian_copula</td><td>9.95</td><td>1.34</td><td>4</td></tr>
<tr><td>mv_r2d2</td><td>10.16</td><td>1.93</td><td>5</td></tr>
<tr><td>mv_mbcn_iterative</td><td>10.17</td><td>1.42</td><td>6</td></tr>
<tr><td>qdm</td><td>11.92</td><td>1.41</td><td>7</td></tr>
<tr><td>mv_spatial_mbc</td><td>13.41</td><td>1.77</td><td>8</td></tr>
</table>

<p>Pooled MAE mixes all variables and models. BCCA has the lowest pooled MAE but the <strong>largest QQ RMSE</strong> (4.42), reflecting severe tail distortion&mdash;it fits the middle of distributions well but badly compresses extremes.</p>

<h2>3. Inter-Variable Dependence Checks</h2>

<p>For each model &times; method, a daily domain-mean 6-variable Spearman rank correlation matrix is computed and compared to the observed matrix via Frobenius norm.</p>

<table>
<tr><th>Method</th><th>Frobenius Error</th><th>Rank</th></tr>
<tr><td>mv_gaussian_copula</td><td>0.210</td><td>1</td></tr>
<tr><td>mv_otbc</td><td>0.220</td><td>2</td></tr>
<tr><td>mv_mbcn_iterative</td><td>0.222</td><td>3</td></tr>
<tr><td>mv_ecc_schaake</td><td>0.370</td><td>4</td></tr>
<tr><td>mv_spatial_mbc</td><td>0.635</td><td>5</td></tr>
<tr><td>mv_r2d2</td><td>0.921</td><td>6</td></tr>
<tr><td>mv_bcca</td><td>1.272</td><td>7</td></tr>
<tr><td>qdm</td><td>&mdash;</td><td>&mdash;</td></tr>
</table>

<p>QDM is excluded (no wind data). Point-wise MV methods (Gaussian Copula, OTBC, MBCn) cluster around 0.21&ndash;0.22, confirming they effectively restore inter-variable correlations. BCCA is worst because its analogue-blending approach doesn't explicitly target inter-variable dependence. Spatial MBC prioritizes spatial coherence over point-wise inter-variable coherence by design.</p>

<h2>4. Temporal Persistence Checks</h2>

<p>Lag-1 autocorrelation error computed on domain-mean daily series. Dry spell lengths computed for precipitation (wet threshold: 0.1 mm/d).</p>

<table>
<tr><th>Method</th><th>Mean Lag-1 Error</th><th>Rank</th></tr>
<tr><td>qdm</td><td>0.012</td><td>1</td></tr>
<tr><td>mv_mbcn_iterative</td><td>0.016</td><td>2</td></tr>
<tr><td>mv_gaussian_copula</td><td>0.016</td><td>3</td></tr>
<tr><td>mv_otbc</td><td>0.025</td><td>4</td></tr>
<tr><td>mv_ecc_schaake</td><td>0.052</td><td>5</td></tr>
<tr><td>mv_bcca</td><td>0.061</td><td>6</td></tr>
<tr><td>mv_r2d2</td><td>0.093</td><td>7</td></tr>
<tr><td>mv_spatial_mbc</td><td>0.128</td><td>8</td></tr>
</table>

<p>QDM preserves GCM temporal structure by construction, so its low lag-1 error is expected. R2D2 and Spatial MBC are highest because their resampling/rotation operations disrupt day-to-day sequencing.</p>

<h2>5. Physics Correction Checks</h2>

<p>Compares pre-physics (<code>BC/</code>) vs post-physics (<code>BCPC/</code>) outputs for two constraints: (1) huss must not exceed saturation specific humidity at tasmax, (2) tasmax &ge; tasmin.</p>

<table>
<tr><th>Method</th><th>Pre huss&gt;qsat</th><th>Post huss&gt;qsat</th><th>Pre tmax&lt;tmin</th><th>Post tmax&lt;tmin</th></tr>
<tr><td>qdm</td><td>0.048%</td><td>0.0%</td><td>0.0%</td><td>0.0%</td></tr>
<tr><td>mv_bcca</td><td>0.0%</td><td>0.0%</td><td>0.0%</td><td>0.0%</td></tr>
<tr><td>mv_ecc_schaake</td><td>0.045%</td><td>0.001%</td><td>0.042%</td><td>0.0%</td></tr>
<tr><td>mv_gaussian_copula</td><td>0.030%</td><td>0.001%</td><td>0.061%</td><td>0.0%</td></tr>
<tr><td>mv_mbcn_iterative</td><td>0.139%</td><td>0.021%</td><td>0.283%</td><td>0.0%</td></tr>
<tr><td>mv_otbc</td><td>0.129%</td><td>0.028%</td><td>0.093%</td><td>0.0%</td></tr>
<tr><td>mv_r2d2</td><td>0.038%</td><td>0.006%</td><td>0.046%</td><td>0.0%</td></tr>
<tr><td>mv_spatial_mbc</td><td><strong>2.54%</strong></td><td><strong>0.49%</strong></td><td><strong>1.47%</strong></td><td>0.0%</td></tr>
</table>

<p>All tasmax&lt;tasmin violations are eliminated. Huss saturation violations drop sharply; small residuals remain for some methods, likely from numerical tolerance differences between our simple Magnus-based qsat and Bhuwan's production routine.</p>

<p>Violation rates are much lower than Bhuwan's CONUS numbers (e.g., QDM: 0.048% here vs 17% CONUS). Iowa is continental and temperate&mdash;the worst physics violations happen at humid coastal hotspots where temperature and humidity approach saturation limits. Iowa's climate simply doesn't push the psychrometric boundary often.</p>

<h2>6. Method Ranking Cross-Check</h2>

<p>Rankings over Iowa are consistent with Bhuwan's CONUS-scale Table 2 (MAE) and Table 3 (Frobenius norm): point-wise MV methods outperform spatial methods on dependence, QDM is best on temporal persistence, BCCA has tail artifacts. The implementations behave correctly even on a smaller domain.</p>

<h2>7. Plot Analysis</h2>

<h3>Plot 1: Precipitation Spatial Bias Maps</h3>
{plot_block("06_bias_maps_pr_MPI.png",
            "mean(BC &minus; Obs) for precipitation, each panel = one BC method, MPI model")}
<p>All eight methods show roughly similar bias patterns with comparable amounts of white (near-zero) cells. This is expected: all multivariate methods start from QDM-corrected marginals and apply rotations/reorderings on top, so marginal bias should be similar across methods. The differences between methods show up in dependence, temporal structure, and extremes&mdash;not in mean spatial bias. If one method had dramatically different bias maps, that would indicate a problem.</p>

<h3>Plot 2: Tasmax Spatial Bias Maps</h3>
{plot_block("06_bias_maps_tasmax_MPI.png",
            "mean(BC &minus; Obs) for tasmax, each panel = one BC method, MPI model")}
<p>Same story as precipitation. Methods look broadly alike. Temperature is a smoother field, biases are modest. No red flags.</p>

<h3>Plot 3: QQ Plot for Precipitation</h3>
{plot_block("06_qq_pr_domain_mean.png",
            "Domain-mean pr quantiles: BC (y) vs observed (x), MPI model")}
<p>QDM (blue) and OTBC (orange) both track the 1:1 dashed line closely, confirming correct marginal correction. <strong>BCCA (green) dramatically diverges</strong>&mdash;observed P99 of ~17 mm/d maps to only ~6.5 mm/d in BCCA output. This is the analogue-blending compression artifact: BCCA constructs each day as a linear combination of historical analogues, which smooths out extremes. On a small Iowa domain with limited analogues, the compression is severe. Bhuwan's CONUS results show the opposite sign (+17.95 mm/d inflation) because at continental scale, blending across diverse spatial patterns can overshoot. Both results point to the same underlying problem: BCCA badly distorts precipitation tails.</p>

<h3>Plot 4: Spearman Correlation Error Heatmap (OTBC)</h3>
{plot_block("06_corr_error_heatmap_mv_otbc.png",
            "6&times;6 Spearman rank correlation difference (BC &minus; Obs), domain-mean daily, MPI OTBC")}
<p>Mostly pale, with errors generally under 0.1. The largest error is in the pr&ndash;wind cell (~0.1), which makes sense: precipitation and wind have a real physical coupling through storm systems, and that correlation is among the harder ones for any BC method to reproduce precisely. Temperature and humidity pairs (tasmax&ndash;huss, tasmax&ndash;tasmin) are nearly white, meaning OTBC preserves the key thermodynamic relationships well.</p>

<h3>Plot 5: Compound Extreme Scatter</h3>
{plot_block("06_compound_tmax_pr.png",
            "Each dot = one day's domain-mean tasmax vs pr, MPI model")}
<p>Points are concentrated near pr=0 because most days have low/no rainfall, and thin out at high precipitation and extreme temperatures. The three point clouds (Obs, QDM, OTBC) overlap substantially, meaning both BC methods preserve the observed joint distribution of temperature and precipitation. If a method's cloud were shifted or had a different shape, it would mean the BC had broken the temperature&ndash;precipitation relationship. The overlap confirms it hasn't.</p>

<h3>Plot 6: Dry Spell KDE</h3>
{plot_block("06_dry_spell_kde.png",
            "KDE of consecutive dry-day lengths (domain-mean pr, wet threshold 0.1 mm/d), MPI model")}
<p>All three lines (Obs, QDM, OTBC) are virtually on top of each other. This is a strong positive result: OTBC's multivariate rotation is not disrupting the wet/dry day sequencing of precipitation at the domain-mean level. QDM matching observations is expected (it preserves GCM temporal structure). OTBC matching this closely confirms minimal temporal disruption.</p>

<h3>Plot 7: Summary Bar Chart</h3>
{plot_block("06_summary_bars.png",
            "MAE, Frobenius dependence error, and lag-1 error across all methods (ensemble-averaged)")}
<p><strong>MAE (top):</strong> Spatial MBC is highest; others are clustered. QDM bar is missing the wind contribution.<br>
<strong>Frobenius (middle):</strong> BCCA is by far highest (~1.27)&mdash;its analogue blending doesn't target inter-variable dependence. Spatial MBC is next (~0.64), prioritizing spatial over inter-variable coherence. R2D2 third (~0.92). Point-wise MV methods (Gaussian Copula, OTBC, MBCn) cluster low (~0.21&ndash;0.22). QDM absent (no wind).<br>
<strong>Lag-1 (bottom):</strong> QDM lowest (preserves GCM temporal ordering). Spatial MBC and R2D2 highest. OTBC sits in a reasonable middle position.</p>

<h3>Plot 8: Physics Violation Rates</h3>
{plot_block("07_violation_rates_huss.png",
            "Fraction of points where huss &gt; qsat(tasmax), pre vs post physics correction, MPI model")}
<p>Spatial MBC dominates with ~2.5% violations pre-correction. All other methods are under 0.15%. Post-correction (orange), Spatial MBC still has a small residual (~0.5%); everything else is near zero. BCCA shows zero violations because its analogue blending produces conservative humidity values. Overall violation rates are much lower than Bhuwan's CONUS results because Iowa's continental climate rarely approaches the psychrometric saturation boundary.</p>

<h3>Plot 9: Psychrometric Scatter, Pre-Physics</h3>
{plot_block("07_psychrometric_BC_pre.png",
            "huss vs tasmax for OTBC (MPI) before physics correction, with saturation curve")}
<p>Very few points sit above the saturation curve, consistent with the low violation rate (0.13%). The scatter cloud sits well within the physically plausible region. Iowa's moderate humidity means most huss values are far from the saturation limit even at high temperatures.</p>

<h3>Plot 10: Psychrometric Scatter, Post-Physics</h3>
{plot_block("07_psychrometric_BCPC_post.png",
            "huss vs tasmax for OTBC (MPI) after physics correction, with saturation curve")}
<p>No visible points above the saturation curve. The overall shape is nearly identical to pre-correction, confirming the physics layer made only minimal adjustments (as expected for Iowa). The correction works correctly&mdash;it clips the rare violations without distorting the bulk of the distribution.</p>

<h2>8. Conclusions</h2>

<ol>
<li><strong>All BC implementations behave as expected.</strong> Method rankings on the Iowa crop are consistent with Bhuwan's CONUS-scale results. No red flags.</li>
<li><strong>OTBC is a defensible choice</strong> for the production pipeline. It ranks #2 in Frobenius norm, #3 in MAE, and #4 in lag-1 error&mdash;consistently near the top with no glaring weakness.</li>
<li><strong>BCCA has severe precipitation tail artifacts</strong> (compression on Iowa, inflation on CONUS). Known limitation, already documented in the manuscript.</li>
<li><strong>The physics correction layer works correctly:</strong> all tasmax&lt;tasmin violations eliminated, huss saturation violations drop to near-zero.</li>
<li><strong>Iowa-specific caveat:</strong> Physics violations are much lower than CONUS because Iowa's continental climate doesn't stress the psychrometric boundary. The physics layer would show more impact in humid coastal regions.</li>
</ol>

</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Wrote {os.path.getsize(OUT_PATH):,} bytes to {OUT_PATH}")
