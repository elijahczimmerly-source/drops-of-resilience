# Cross-Variable Noise Conditioning — PR RMSE Improvement Plan

## The problem in plain language

Every day, it rains somewhere in Iowa and doesn't rain somewhere else. GridMET records exactly where. DOR's job is to produce a realistic precipitation map for each day — but right now, it has no idea *where* it rained on any given day. It gets the long-term averages right (some pixels are climatologically wetter than others) and it gets the overall variability right (the distribution of rain amounts matches observations), but the daily spatial pattern — which pixels are wet and which are dry today — is essentially a random guess.

This randomness is measured by **r**, the correlation between DOR's daily precipitation pattern and the actual observed pattern. Currently r ≈ 0.025 — essentially zero. Every day, DOR rolls the dice on where to put the rain. Sometimes it guesses right, usually it doesn't. Every wrong guess is a squared error that inflates RMSE.

## Why this is the only path to beating NEX

The RMSE formula (simplified for our case where bias ≈ 0 and variance is matched):

**RMSE² ≈ 2σ²(1 − r)**

Where σ ≈ 7.1 mm/day is the standard deviation of precipitation.

NEX achieves RMSE = 8.64 not by having better correlation (its r is also ~0), but by **compressing variance** — NEX underpredicts extreme precipitation by 25% (Ext99 = −25.3%). Less variance = less RMSE, but wrong extremes. DOR's nearly perfect Ext99 (−0.05%) means σ_sim ≈ σ_obs, which is correct but costs more RMSE when r ≈ 0.

There are only two ways to reduce RMSE:
1. **Compress variance** (what NEX does) — sacrifice Ext99 to lower σ_sim. Not acceptable.
2. **Improve correlation** — make the daily spatial pattern less random. This is the only option.

To match NEX's RMSE while keeping our Ext99:
- Need r ≈ 0.26 (currently 0.025)
- This is a modest correlation — it means "the spatial pattern is slightly better than random"

All noise-tuning approaches (correlation length, noise factor, intensity-dependent scaling, etc.) operate within a 0.7 RMSE budget (the difference between stochastic and deterministic DOR). A corr_len sweep confirmed only 0.013 improvement from the best value. These ideas cannot close a 1.27 gap because they don't improve r — they just rearrange the noise without making it less random.

## The idea: use temperature and humidity to inform where it rains

DOR downscales 6 variables: pr, tasmax, tasmin, rsds, wind, huss. Currently, each variable is downscaled independently — the precipitation noise field is a random spatial pattern that ignores what the temperature and humidity fields look like on that day.

But the GCM has **real daily spatial skill** for temperature and humidity:
- tasmax KGE = 0.80
- tasmin KGE = 0.82
- huss KGE = 0.78

These variables have r ≈ 0.9 at the pixel level — the GCM genuinely knows where it's warm and where it's cold on any given day. And precipitation is physically tied to these fields:
- **Fronts** occur where temperature gradients are strongest — precipitation concentrates along the warm/cold boundary
- **Convection** happens where humidity is high and surface temperatures are elevated
- **Orographic effects** interact with wind direction and moisture content

On a day where the downscaled temperature field shows a sharp cold-warm boundary cutting through central Iowa, precipitation is physically more likely along that boundary than 200 km away from it. DOR knows about this boundary (it downscales temperature well) but doesn't use this information for precipitation.

## What "cross-variable noise conditioning" means

Currently, the noise step works like this:

```
noise_field = random_spatial_pattern(corr_len=35)
y_final = y_base * (1 + noise_field * cv_resid * nf)
```

The `noise_field` is drawn from a spatially correlated random process. It has no information about the day's weather.

The proposed change:

```
weather_signal = f(tasmax_today, tasmin_today, huss_today, wind_today, rsds_today)
noise_field = alpha * weather_signal + (1 - alpha) * random_spatial_pattern
y_final = y_base * (1 + noise_field * cv_resid * nf)
```

Where:
- `weather_signal` is a spatial field derived from the GCM's other variables for today — it represents "where precipitation is more/less likely based on temperature gradients, humidity, etc."
- `alpha` controls the blend: 0 = fully random (current behavior), 1 = fully weather-driven (no randomness)
- `f()` is a function trained on historical data to predict precipitation spatial anomalies from the other variables

The output remains stochastic (the random component is still there) but has a spatial bias toward physically plausible patterns. On days with strong frontal forcing, the weather_signal would be strong and precipitation would concentrate in the right areas. On days with weak or ambiguous forcing, the signal would be weak and the noise would remain essentially random.

## Phase 0: Feasibility diagnostic (do this first)

Before building anything, test whether the GCM's other variables actually predict precipitation spatial patterns. This is a quick analysis on training data — no pipeline changes needed.

### What to compute

For each day in the training period (1981–2005):

1. Compute the **observed precipitation spatial anomaly**: for each pixel, how much does today's observed precipitation deviate from that pixel's climatological mean for this semi-monthly period?
   ```
   obs_anomaly[pixel] = obs_pr[pixel, today] / mean(obs_pr[pixel, this_period]) - 1
   ```

2. Compute the **GCM predictor fields**: the GCM's daily values for tasmax, tasmin, huss, wind, rsds at each pixel (already on the 4km grid after regridding).

3. Fit a simple linear regression: `obs_anomaly ~ GCM_tasmax + GCM_tasmin + GCM_huss + GCM_wind + GCM_rsds` (pixel-wise values, pooled across days).

4. Measure R² — the fraction of variance in the observed precipitation spatial anomaly that the GCM's other variables explain.

### How to interpret

- **R² > 0.05:** There's signal. Worth pursuing. Even R² = 0.05 could improve r from 0.025 to ~0.07, which would reduce RMSE by ~0.2.
- **R² > 0.10:** Strong signal. Could meaningfully close the gap to NEX.
- **R² ≈ 0:** The GCM's other variables carry no useful information about precipitation placement at 4km. The idea is dead. Move on.

### Important details for the diagnostic

- Run on the **training period only** (1981–2005). The validation period (2006–2014) must be held out.
- Use **the server `Regridded_Iowa` data** — not the local bilinear data. See `dor-info.md` § "CRITICAL: Only one correct input dataset."
- Pool across days within each semi-monthly period (to avoid seasonality confounds), then average R² across periods.
- Also compute R² separately for "wet days" (domain-mean obs pr > 1 mm) and "dry days" to see if the signal is concentrated in certain weather regimes.
- Normalize predictor variables to zero mean, unit variance before regression.
- Try both: (a) regression on raw GCM fields, (b) regression on **spatial gradients** of GCM fields (e.g. ∂tasmax/∂x, ∂tasmax/∂y) since fronts are gradient features.

### Script location

`9-additional-pr-RMSE-fixes/scripts/diagnostic_cross_variable_signal.py`

### Output

- `9-additional-pr-RMSE-fixes/output/cross_variable_diagnostic.md` — R² values, interpretation, go/no-go recommendation
- `9-additional-pr-RMSE-fixes/output/cross_variable_r2_by_period.csv` — R² per semi-monthly period

## Phase 1: Build the weather signal model (only if Phase 0 shows signal)

Only proceed here if R² > 0.05 in the diagnostic.

### Training

For each semi-monthly period, train a model (start with ridge regression, not anything fancy) that predicts the observed precipitation spatial anomaly from the GCM's multi-variable fields:

```
X = [tasmax, tasmin, huss, wind, rsds, grad_tasmax_x, grad_tasmax_y, grad_huss_x, ...]  # per pixel
y = obs_pr_anomaly  # per pixel
```

Train on 1981–2005. The model produces a spatial field `weather_signal(H, W)` for each day.

### Normalization

The `weather_signal` must be normalized to have similar statistics to the random noise field it's blending with — zero mean, comparable variance. Otherwise it would shift the precipitation distribution.

### Blend parameter α

Start with α = 0.3 (30% weather-driven, 70% random). Sweep α ∈ {0.1, 0.2, 0.3, 0.4, 0.5} and measure RMSE, Ext99, WDF, Lag1 on the validation period.

### WDF interaction

The WDF threshold (1.65) was calibrated on fully random noise. The weather signal changes the noise distribution — some pixels will systematically get more noise, some less. **PR_WDF_THRESHOLD_FACTOR will need to be re-tuned after implementing this.** Budget one extra sweep for that.

## Phase 2: Validate (only if Phase 1 produces a working model)

Run the full pipeline with cross-variable noise conditioning on the 216×192 server data. Compare all metrics for all variables against the current baseline.

### Success criteria

| Metric | Requirement |
|--------|-------------|
| pr RMSE | Must improve by at least 0.3 (to ≤ 9.6) to justify the complexity. Target: < 8.64 (beat NEX). |
| pr Ext99 Bias% | Must stay within ±1% of zero |
| pr WDF | Must stay within 2pp of observed (after re-tuning threshold) |
| pr Lag1 Err | Must not increase by more than 0.02 |
| All other variables | Must be unchanged (this only modifies the pr noise field) |

### If it works

This would be a genuinely novel contribution — no existing operational downscaler uses cross-variable spatial information to condition stochastic noise. It would be worth highlighting in the paper.

### If it doesn't work (R² ≈ 0 in Phase 0)

Then the GCM simply doesn't carry usable spatial information about precipitation placement at the 4km scale after regridding. This is a fundamental limitation of ~100km GCMs with only 3–4 cells across Iowa. The RMSE gap to NEX would be documented as a structural consequence of preserving realistic variance — a deliberate tradeoff, not a failure. DOR already beats LOCA2's RMSE in the deterministic case (9.21 vs 9.47), and LOCA2 is the fair comparison since it also preserves extremes.

## File organization

```
9-additional-pr-RMSE-fixes/
  BRAINSTORMING.md                          Ideas + why noise-tuning can't work
  PLAN-CORR-LENGTH-SWEEP.md                 Completed — 0.013 improvement, not enough
  PLAN-CROSS-VARIABLE-NOISE.md              This file
  scripts/
    sweep_corr_length.py                    Completed
    diagnostic_cross_variable_signal.py     Phase 0 diagnostic
  output/
    corr_length_sweep.csv                   Completed
    corr_length_findings.md                 Completed — corr_len not the answer
    cross_variable_diagnostic.md            Phase 0 results (TBD)
    cross_variable_r2_by_period.csv         Phase 0 data (TBD)
```
