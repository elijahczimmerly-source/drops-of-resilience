# Improve Wind Downscaling

## Prerequisites

The splotchiness fix (`7-fix-pr-splotchiness/`) applies to wind via the shared multiplicative pathway. Implement and validate that first. The WDF fix (`8-WDF-overprediction-fix/`) is pr-only (wind has no WDF censoring) and can be done in parallel with or before this work.

## Current State

Wind uses the multiplicative downscaler (same as pr), with:
- Correlation length: 50 px (vs 35 for pr, 100 for tasmax/rsds)
- Noise factor: 0.16 (shared `NOISE_FACTOR_MULTIPLICATIVE`)
- AR(1) rho: 0.5 (shared with pr)
- Clip: [0.1, 8.5] (shared with pr)
- No WDF censoring (wind is always >= 0, no wet/dry concept)
- `USE_GEO_STATIC = False` — elevation and wind effect covariates are available but disabled

### Benchmark metrics (DOR vs NEX, 2006-2014, MPI)

| Metric | DOR | NEX |
|--------|-----|-----|
| KGE | 0.081 | 0.061 |
| RMSE | 2.21 | 2.35 |
| Bias | -0.32 m/s | -0.93 m/s |
| Ext99 Bias% | **-7.5%** | -16.3% |
| Lag1 Err | 0.045 | 0.068 |

DOR beats NEX on every metric. No LOCA2 wind data available for comparison.

### Key weaknesses

1. **KGE ≈ 0.08** — essentially no day-to-day skill (same GCM timing limitation as pr). Not actionable at the spatial downscaling level.
2. **Ext99 -7.5%** — underpredicts wind extremes by 7.5%. This is actionable — the multiplicative noise parameters control the heavy tail.
3. **Spatial structure** — time-mean maps show GCM-scale blockiness and lack fine-scale terrain-driven features (channeling, roughness sheltering) visible in GridMET. The spatial ratio `m_obs / m_gcm` captures the climatological mean pattern but can't inject sub-GCM terrain features that aren't in the ratio field.
4. **Negative bias (-0.32 m/s)** — DOR systematically underestimates mean wind speed. Small but consistent.

## What's Available But Unused

### WindEffect monthly fields

**Location:** `Data/Cropped_Iowa/WindEffect/WindEffect_Mean_01.npz` through `..._12.npz`
**Also:** `Spatial_Downscaling/Data_WindEffect_Static/` (same files)

Each file contains:
- `mean`: shape (1681, 1921), float32 — a multiplicative wind speed modification factor
- `count`: shape (1681, 1921) — sample count
- `lat`: (1681,), `lon`: (1921,) — coordinates covering ~39.5-43.5°N, -92.5 to -88.5°W

The `mean` field ranges from ~0.74 to ~1.35, centered around 1.0. This is a **topographic wind speed multiplier** at very high resolution (~100m based on the grid dimensions). Values > 1.0 indicate terrain-accelerated locations (ridgelines, hilltops, open exposures); values < 1.0 indicate sheltered locations (valleys, lee slopes, forested areas).

**Monthly resolution:** 12 separate files means the wind effect varies by season — different prevailing wind directions interact with terrain differently throughout the year.

**This is exactly the kind of sub-GCM spatial information that could fix the blockiness.** The current downscaler applies `y = in_val * ratio` where `ratio = m_obs / m_gcm`. This captures the 4km climatological mean but only from the training period's average. The WindEffect field provides physically-derived terrain modulation that could sharpen the spatial structure beyond what the statistical ratio captures.

### Elevation data

**Location:** `Data/Regridded_Iowa/Regridded_Elevation_4km.npz`
- `data`: shape (216, 192), range 107-611 m — on the same grid as the downscaler output.

Iowa is relatively flat (max 611 m), so direct elevation-wind relationships are weak. But the WindEffect field already encodes the terrain effect at high resolution — elevation itself is less useful than the pre-computed wind effect multiplier.

### geo_static.npy

Contains elevation, slope, aspect, and monthly wind climatology. Currently disabled (`USE_GEO_STATIC = False`). On the server at `Data_Regrided_Gridmet/` (old layout, 84x96 grid — not the 216x192 grid used by test8_v2). Would need to be rebuilt for the new grid if used.

## Plan

### Phase 1: Wind Ext99 improvement via noise tuning (low risk)

The -7.5% Ext99 underprediction means the multiplicative noise doesn't generate strong enough extreme wind events. This can be addressed by tuning wind-specific noise parameters without changing the spatial structure.

**Approach:** Give wind its own noise factor, separate from pr's shared `NOISE_FACTOR_MULTIPLICATIVE = 0.16`.

Currently both pr and wind use 0.16. But pr's Ext99 is nearly perfect (+0.13%) while wind's is -7.5%. This suggests wind needs a higher noise factor to generate stronger tail events.

**Implementation:**

1. Add `NOISE_FACTOR_WIND` as a separate constant (default: 0.16, same as current behavior).
2. In `process_variable()`, pass `noise_factor=NOISE_FACTOR_WIND` when constructing the wind model instead of relying on the shared default.
3. Sweep `NOISE_FACTOR_WIND` from 0.16 to 0.30 in increments of 0.02 and record Ext99, RMSE, Lag1 for each.
4. Select the value that brings Ext99 closest to 0% without degrading Lag1 by more than 0.01 or RMSE by more than 5%.

**Why this is safe:** Wind has no WDF censoring, so the noise-threshold interaction that complicates pr doesn't exist. The noise factor directly controls the tail width. Increasing it will:
- Improve Ext99 (heavier tail → more extreme events)
- Slightly increase RMSE (more variance → more squared error on non-extreme days)
- Slightly increase Lag1 error (more noise amplitude → AR(1) structure has more to track)

The tradeoff should be favorable because -7.5% Ext99 is a clear underprediction, suggesting the current noise amplitude is too conservative for wind.

**Validation:**
- Ext99 Bias%: target within +/- 3%
- RMSE: should not increase more than 5% from current 2.21
- Lag1: should not increase more than 0.01 from current 0.045
- KGE: may improve slightly (better variability ratio component)

### Phase 2: WindEffect terrain modulation (moderate risk, high potential)

Apply the monthly WindEffect multiplicative field as a post-processing step to inject sub-GCM terrain structure into the downscaled wind field.

**Concept:** After the standard multiplicative downscaling produces `y_final = in_val * ratio * noise_mult`, apply the terrain modulation:

```python
y_terrain = y_final * wind_effect_field[month]
```

where `wind_effect_field[month]` is the WindEffect_Mean field for the current month, regridded from its native (1681, 1921) resolution to the downscaler's (216, 192) grid.

**Why multiplicative:** The WindEffect field is already a multiplicative factor centered on 1.0. Multiplying preserves the mean (since the field averages ~1.0) while redistributing wind speed within the domain — exposed locations get amplified, sheltered locations get dampened. This is physically correct: terrain modifies wind speed as a fraction of the ambient flow, not as an additive offset.

**Implementation:**

1. **Regrid WindEffect to 216x192:** Use conservative or bilinear interpolation to go from (1681, 1921) to (216, 192). The WindEffect grid covers a slightly smaller domain than the full downscaler grid (39.5-43.5°N vs 37.5-46.5°N) — need to handle the mismatch. Options:
   - Crop the downscaler output to the WindEffect domain and apply only there (leaves edges unmodified).
   - Extrapolate WindEffect to 1.0 outside its domain (neutral, no terrain modification at edges).
   The second option is cleaner — pixels outside the WindEffect domain get no terrain modulation, which is the same as what currently happens.

2. **Load monthly fields at calibration time:** Read all 12 `WindEffect_Mean_*.npz` files, regrid each to (216, 192), store as `self.wind_effect[0..11]` shape (12, H, W).

3. **Apply in `downscale_day`:** After computing `y_final` (and after noise debiasing if present):
   ```python
   if self.var_name == "wind" and hasattr(self, 'wind_effect'):
       month_idx = date_obj.month - 1
       we = self.wind_effect[month_idx].flatten()[valid]
       y_final = y_final * we
   ```

4. **Recalibrate the spatial ratio:** With the terrain modulation in place, the spatial ratio (`m_obs / m_gcm`) needs to be recalibrated because the WindEffect already captures some of the spatial structure that the ratio was compensating for. Without recalibration, you'd double-count the terrain effect.

   Two options:
   - **Option A (simple):** Apply the fix as post-processing only, after the full downscale loop. Don't touch calibration. The ratio still does its job (matching obs mean), and the WindEffect adds sub-ratio-scale texture. Risk: the ratio already partially captures terrain effects in the 4km obs mean, so the WindEffect may over-correct at some pixels.
   - **Option B (clean):** Recalibrate the ratio with the WindEffect pre-applied: `sim_base = in_m * ratio * wind_effect`, then recompute ratio to minimize residuals. This avoids double-counting but requires modifying the calibration loop.

   **Recommendation:** Start with Option A. Measure the spatial bias after applying WindEffect. If certain pixels show systematic over/underprediction (from double-counting), switch to Option B.

**Validation:**
- Time-mean and seasonal spatial maps: visual comparison to GridMET. The terrain-driven fine-scale features should appear.
- RMSE: should improve (better spatial structure → less pixel-level error).
- Ext99: should be roughly unchanged (WindEffect is ~0.74-1.35, not extreme enough to create or destroy wind extremes).
- Lag1: unchanged (WindEffect is a static field, doesn't affect temporal structure).
- Bias: should stay near -0.32 m/s (WindEffect averages ~1.0, so domain-mean is preserved).

### Phase 3: Evaluate and decide (after Phases 1-2)

After implementing both phases:
1. Re-run the full benchmark (`product-comparison/scripts/run_benchmark.py`) with the new wind output.
2. Generate time-mean and seasonal spatial maps.
3. Compare to NEX on all metrics.
4. Discuss with Bhuwan whether the improvement is sufficient or if further work is needed (e.g., directional wind effects, stability-dependent terrain modulation).

## What This Fix Cannot Do

- **Fix KGE ≈ 0.08.** This is a GCM timing limitation, same as pr. The GCM produces its own wind variability on its own timeline; the downscaler can't fix which days are windy. This requires temporal downscaling.
- **Inject terrain features smaller than 4km.** The downscaler grid is 4km (216x192). The WindEffect data is much higher resolution (~100m) but gets averaged to 4km during regridding. Sub-4km features are lost.
- **Fix the negative bias (-0.32 m/s) if it's from the GCM/BC.** If MPI systematically underestimates Iowa wind speed and OTBC doesn't fully correct it, the bias propagates through the ratio (which is `m_obs / m_gcm` — this *should* correct the mean, but only over the training period's statistics).

## Risks

- **Phase 1 (noise tuning):** Low risk. Worst case: no value in the sweep produces acceptable Ext99 without degrading RMSE/Lag1 beyond thresholds. In that case, keep the current 0.16.
- **Phase 2 (WindEffect):** Moderate risk. The WindEffect data was provided by Bhuwan but hasn't been used in the pipeline before (`USE_GEO_STATIC = False`). Need to verify:
  - That the WindEffect domain covers our full Iowa crop (it covers ~39.5-43.5°N — may not reach the full 37.5-46.5°N extent of the downscaler grid).
  - That the WindEffect values are physically reasonable in all months (no NaNs, no extreme outliers).
  - That regridding from (1681, 1921) to (216, 192) preserves the terrain features adequately.
  - Whether Bhuwan has a reason for leaving `USE_GEO_STATIC = False` — ask before implementing Phase 2.

## File Organization

```
10-improve-wind/
  PLAN.md                            (this file)
  scripts/
    sweep_wind_noise.py              (Phase 1: noise factor sweep)
    apply_wind_effect.py             (Phase 2: WindEffect terrain modulation)
    validate_wind.py                 (metric comparison + spatial maps)
    inspect_wind_effect.py           (preliminary: examine WindEffect data, coverage, regrid)
  output/
    noise_sweep/                     (Phase 1: metrics per noise factor value)
    wind_effect/                     (Phase 2: pipeline output with terrain modulation)
```
