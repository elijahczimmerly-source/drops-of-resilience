# Fix PR Wet-Day Frequency Overprediction

## Prerequisites

- **Splotchiness investigation is closed.** The splotches come from the GCM, not the downscaler. No code changes resulted from it.
- **Noise debias is OFF.** `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` for all runs in this task. Do not turn it on.
- **Baseline is `experiment_attempt5_sigma0`** (or equivalently `experiment_plan_nodebias` — both have debias off, same seed, same blend). Use the sigma0 run as the reference since it's the most recent with debias off.

## The Problem

DOR overpredicts wet-day frequency by +3.4 percentage points (35.9% simulated vs 32.5% observed). LOCA2 is much closer, underpredicting by only 1.5pp (31.2%). NEX is worse than DOR (+4.6pp).

"Wet-day frequency" is defined as the fraction of pixel-days with precipitation >= 0.1 mm/day, pooled across the full validation domain and period (2006-2014).

This means DOR produces too many light-rain days. The implications:
- Downstream hydrological models (WEPP) will simulate more frequent runoff events and more total wet soil days than observed, biasing erosion rates upward.
- Dry spell statistics (consecutive dry days) will be too short, affecting drought and soil moisture modeling.
- The +3.4pp overprediction is a distributional error — it means the zero/non-zero precipitation threshold is miscalibrated, independent of how well the non-zero amounts are modeled.

**RMSE connection:** Fixing WDF should also improve pr RMSE. Each false wet day (DOR says light rain, GridMET says 0) contributes a squared error. DOR's pr RMSE (9.91 at blend 0.65, 9.51 at parity) is the worst of the three benchmark products. See `8-pr-RMSE-fix/BRAINSTORMING.md` for the full RMSE analysis.

## How WDF Censoring Currently Works

The WDF threshold system has two parts: calibration and application.

### Calibration

In `StochasticSpatialDisaggregatorMultiplicative.calibrate()`, inside the per-period loop, after computing `sim_base = in_m * spatial_ratio[p]`:

```python
if self.var_name == "pr":
    sim_m_sorted = np.sort(sim_base, axis=0)
    wdf = np.mean(tar_m >= 0.1, axis=0)
    ti = np.clip(np.round((1 - wdf) * (len(idx) - 1)).astype(int), 0, len(idx) - 1)
    Hi, Wi = np.indices((H, W))
    self.monthly_threshold[p] = sim_m_sorted[ti, Hi, Wi]
```

For each semi-monthly period `p` and each pixel:
1. Compute the observed wet-day fraction: `wdf = fraction of training days with obs >= 0.1 mm`.
2. Sort the `sim_base` values (= `in_val * ratio`) for training days in this period.
3. Set the threshold to the `(1 - wdf)` quantile of `sim_base`. This means: if observed WDF is 40%, the threshold is set to the 60th percentile of `sim_base`. Days with `sim_base` below this threshold would be censored to zero.

**The logic:** If the observed data has 40% wet days, then the bottom 60% of simulated days should be dry. By setting the threshold at the 60th percentile of the simulated distribution, you censor exactly the right fraction — *on the training data, without noise*.

### Application

In `StochasticSpatialDisaggregatorMultiplicative.downscale_day()`, after computing `y_final = y_base * noise_mult`:

```python
if self.var_name == "pr":
    th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
    y_final = np.where(y_final <= th, 0, y_final)
    y_final = np.where(y_final < 0.1, 0, y_final)
    y_final = np.clip(y_final, 0, 250.0)
```

During inference:
1. The calibrated threshold is scaled by `PR_WDF_THRESHOLD_FACTOR = 1.15`.
2. Any `y_final` (= `y_base * noise_mult`) at or below the scaled threshold is set to zero.
3. A second pass sets anything below 0.1 mm to zero (catch-all).
4. Physical cap at 250 mm.

## Why DOR Overpredicts WDF

The WDF calibration is designed to produce the correct WDF on the *deterministic* (noise-free) `sim_base` distribution. But during inference, multiplicative noise is applied *before* the threshold check. This disrupts the calibration in a way that systematically increases the wet-day count.

### The noise-threshold interaction

Consider a pixel where:
- `sim_base` (deterministic) = 0.3 mm (below the threshold, would be censored)
- `threshold * 1.15` = 0.5 mm
- `noise_mult` is drawn from a distribution centered around 1.0

Without noise: `y_final = 0.3 mm < 0.5 mm` -> censored to 0. Correct.

With noise: `y_final = 0.3 * noise_mult`. If `noise_mult > 1.67`, then `y_final > 0.5 mm` and the day survives censoring. The probability of `noise_mult > 1.67` is nonzero -- maybe 10-20% depending on the local `cv_resid`. So a day that should be dry has a 10-20% chance of becoming wet.

Meanwhile, on genuinely wet days:
- `sim_base` = 5.0 mm (well above threshold)
- `noise_mult` would need to drop below 0.1 (i.e., `5.0 * noise_mult < 0.5`) to censor the day
- That requires `noise_mult < 0.1`, which is the hard clip floor -- probability is very small

**The asymmetry:** Noise can push dry days above the threshold (creating false wet days) much more easily than it can push wet days below the threshold (creating false dry days). The threshold sits in the middle of the distribution where the noise has the most leverage; genuinely wet days are far above the threshold where the noise can't reach the censoring boundary.

This is why `PR_WDF_THRESHOLD_FACTOR = 1.15` exists -- it was Bhuwan's attempt to compensate for this effect by raising the threshold by 15%. But 15% isn't enough: the current +3.4pp overprediction shows the threshold factor undercompensates.

---

## Phase 1: PR_WDF_THRESHOLD_FACTOR sweep (do this first)

Before implementing anything complex, sweep the existing `PR_WDF_THRESHOLD_FACTOR` to find a value that brings WDF close to observed. This is the quickest possible test and confirms the diagnosis.

### What to do

1. Write a script `8-WDF-overprediction-fix/scripts/sweep_wdf_threshold.py` that loops over threshold factor values, runs the full pipeline for each, and collects metrics into a single CSV.

2. Sweep these values: **{1.15, 1.20, 1.25, 1.30, 1.35, 1.40}**. The current value is 1.15.

3. For each value, set these env vars (same as all recent runs):
   ```
   PR_WDF_THRESHOLD_FACTOR=<value>      # <-- THIS IS THE VARIABLE BEING SWEPT
   DOR_MULTIPLICATIVE_NOISE_DEBIAS=0
   TEST8_SEED=42
   PR_USE_INTENSITY_RATIO=1
   PR_INTENSITY_BLEND=0.65
   TEST8_MAIN_PERIOD_ONLY=1
   DOR_RATIO_SMOOTH_SIGMA=0
   ```
   **IMPORTANT:** `PR_WDF_THRESHOLD_FACTOR` is currently a module-level constant (line 180 of `test8_v2_pr_intensity.py`):
   ```python
   PR_WDF_THRESHOLD_FACTOR = 1.15
   ```
   Before running the sweep, change this line to read from an env var:
   ```python
   PR_WDF_THRESHOLD_FACTOR = float(os.environ.get("PR_WDF_THRESHOLD_FACTOR", "1.15").strip())
   ```
   This is the **only code change needed** for Phase 1.

4. Use `PR_INTENSITY_OUT_TAG` to distinguish runs, e.g. `wdf_factor_1p20`, `wdf_factor_1p25`, etc.

5. For each run, record in the output CSV:
   - `PR_WDF_THRESHOLD_FACTOR` value
   - `Val_WDF_Sim%` (target: close to 32.5%)
   - `Val_WDF_Obs%` (should be ~32.5% in every run)
   - `Val_Ext99_Bias%` (must stay within +/- 1% of zero)
   - `Val_RMSE_pooled`
   - `Val_KGE`
   - `Val_Lag1_Err`
   - `Val_Bias`
   - `wind_Val_Ext99_Bias%` (wind uses the same code path but has no WDF censoring -- should be unaffected)
   - `out_dir` path

6. Also generate a side-by-side GridMET|DOR plot for each run using the same style as the plots in `7-fix-pr-splotchiness/figures/pr-splotch-side-by-side/`. Save them to `8-WDF-overprediction-fix/figures/`.

### How to structure the sweep script

Model it after `7-fix-pr-splotchiness/scripts/sweep_ratio_smooth.py` -- that script already does exactly this pattern (loop over env var values, subprocess the pipeline, collect Table1 metrics into a CSV). The key differences:
- The env var being swept is `PR_WDF_THRESHOLD_FACTOR` instead of `DOR_RATIO_SMOOTH_SIGMA`
- The out tags should be `wdf_factor_1p15`, `wdf_factor_1p20`, etc.
- Collect WDF columns in addition to the standard Table1 metrics

### Success criteria for Phase 1

| Metric | Requirement |
|--------|-------------|
| WDF Sim% | Within 1pp of WDF Obs% (~32.5%). Target: 31.5-33.5%. |
| Ext99 Bias% | Within +/- 1% of zero |
| RMSE | No worse than 9.91 (current blend 0.65). Should improve. |
| Lag1 Err | No worse than 0.060 (current ~0.056) |
| Wind Ext99 | Unchanged from current (~-7.5%) -- wind has no WDF censoring |

### Interpreting Phase 1 results

- **If a factor value hits all criteria:** Lock that value, update the default in `test8_v2_pr_intensity.py`, and move on. The simple fix is sufficient.
- **If no single factor hits WDF < 1pp without regressing Ext99:** The blunt-instrument approach isn't precise enough. Proceed to Phase 2 (noise-aware calibration).
- **If WDF improves but RMSE doesn't:** The false-wet-day hypothesis about RMSE was wrong. RMSE improvement would need to come from the ideas in `8-pr-RMSE-fix/BRAINSTORMING.md` instead.

---

## Phase 2: Noise-aware WDF threshold calibration (only if Phase 1 fails)

Only implement this if the threshold factor sweep in Phase 1 does not find a value that satisfies all success criteria.

### Approach

Replace the current deterministic threshold calibration with one that accounts for the multiplicative noise distribution. Instead of asking "what sim_base quantile matches the observed WDF?", ask "what threshold, when applied to the noisy output `sim_base * noise_mult`, matches the observed WDF?"

### Implementation

In `calibrate()`, replace the WDF threshold block with:

```python
if self.var_name == "pr":
    # Noise-aware WDF threshold calibration.
    # Simulate noisy output on training data to find the threshold that
    # produces the correct WDF when noise is applied.
    n_noise_samples = 50  # MC samples per training day
    wdf_obs = np.mean(tar_m >= 0.1, axis=0)  # (H, W) target WDF

    n_days_period = len(idx)
    noisy_values = []

    for _ in range(n_noise_samples):
        # Independent noise draws (no AR(1) -- marginal distribution is the same)
        cn = generate_spatial_noise((H, W), self.corr_len, device=self.device)
        cn_np = cn.cpu().numpy()
        noise_mult = 1.0 + cn_np * self.resid_cv[p] * self.noise_factor
        noise_mult = np.clip(noise_mult, 0.1, 8.5)
        noisy_sim = sim_base * noise_mult  # (n_days_period, H, W)
        noisy_values.append(noisy_sim)

    # Stack: (n_days * n_samples, H, W)
    all_noisy = np.concatenate(noisy_values, axis=0)

    # Threshold = (1 - wdf_obs) quantile of the noisy distribution
    n_total = all_noisy.shape[0]
    all_noisy_sorted = np.sort(all_noisy, axis=0)
    ti = np.clip(np.round((1 - wdf_obs) * (n_total - 1)).astype(int), 0, n_total - 1)
    Hi, Wi = np.indices((H, W))
    self.monthly_threshold[p] = all_noisy_sorted[ti, Hi, Wi]
```

Also change `downscale_day` to NOT multiply the threshold by `PR_WDF_THRESHOLD_FACTOR` (set `PR_WDF_THRESHOLD_FACTOR = 1.0` or remove the multiplication). The noise-aware threshold already accounts for the noise effect.

### Why no AR(1) in the calibration noise

The AR(1) creates temporal persistence, but the *marginal* distribution of `noise_mult` on any single day is the same whether or not there's AR(1) (the AR(1) process is stationary with the same marginal variance). The threshold needs to match the marginal distribution, not the temporal sequence. Using independent samples is simpler and avoids needing to simulate long AR(1) chains during calibration.

### Memory consideration

`all_noisy` has shape `(n_days * 50, H, W)`. With `n_days ~ 400` and `H, W = 216, 192`, that's `400 * 50 * 216 * 192 * 4 bytes ~ 3.3 GB`. This fits in 32 GB RAM but is not trivial. If memory is tight, reduce `n_noise_samples` to 20 (still ~8,000-12,000 samples per pixel -- sufficient) or process in chunks.

### Validation

Same success criteria as Phase 1. Run the full pipeline with noise-aware threshold and measure WDF, Ext99, RMSE, Lag1.

---

## Alternative approaches (for reference, do not implement unless Phases 1 and 2 both fail)

### B. Two-stage censoring: censor before noise, then re-censor after

Apply the WDF threshold to `y_base` (before noise) to decide if the day is wet or dry. Only apply noise to wet days. Eliminates the noise-threshold interaction entirely but changes the physical meaning of the stochastic step.

### C. Stochastic occurrence model

Replace the threshold with a probabilistic wet/dry decision. Most physically principled but major structural change. Out of scope for a targeted fix.

---

---

## Phase 1 Results (2026-04-09) — WRONG DATA, relative results valid

### What happened

The Phase 1 sweep was executed by Cursor using `scripts/sweep_wdf_threshold.py`. However, the sweep script hardcoded the **wrong default data paths** (lines 27-31):

```python
_DEFAULT_GRIDMET = r"\\abe-cylo\...\Data_Regrided_Gridmet"  # WRONG — old 84×96 / 120×192 grid
```

This should have been `Regridded_Iowa` (216×192). As a result, all 6 runs used a **120×192 grid (23,040 cells)** instead of the **216×192 grid (41,472 cells)** used by all published benchmarks. Absolute metrics (RMSE ~10.81, Ext99 ~4.21%) are **not comparable** to benchmark numbers (RMSE 9.91, Ext99 +0.13%).

### Relative findings (valid)

Relative comparisons across the 6 factors are valid because all used the same (wrong) data:

| Factor | WDF Sim% | Δ vs Obs (32.68%) | Ext99 Bias% | RMSE | Lag1 Err |
|--------|----------|-------------------|-------------|------|----------|
| 1.15 | 35.01 | +2.33pp | 4.21 | 10.80 | 0.020 |
| 1.20 | 34.22 | +1.54pp | 4.21 | 10.80 | 0.019 |
| 1.25 | 33.45 | +0.76pp | 4.21 | 10.81 | 0.018 |
| **1.30** | **32.69** | **+0.01pp** | 4.21 | 10.81 | 0.016 |
| 1.35 | 31.95 | −0.73pp | 4.21 | 10.81 | 0.015 |
| 1.40 | 31.23 | −1.45pp | 4.21 | 10.81 | 0.013 |

Key takeaways:
- **Factor 1.30 essentially nails WDF** (Sim 32.69% vs Obs 32.68%).
- **Ext99 is completely unchanged** across all factors — the threshold only affects light rain.
- **Factors 1.25–1.35** all satisfy the ±1pp WDF criterion.
- Wind Ext99 is identical across all factors (no cross-talk).

### Phase 2 result (also on wrong data)

Noise-aware calibration (`DOR_PR_WDF_NOISE_AWARE_CALIBRATION=1`, 15 MC samples) **degraded WDF** to 38.04% (+5.4pp vs obs). Root cause: MC calibration uses i.i.d. noise per day, but inference uses AR(1) temporally correlated noise. The marginal distributions don't match, so thresholds calibrated on i.i.d. are too low for AR(1) inference → more false wet days. Phase 2 is not needed since Phase 1 works.

---

## Next Steps: Re-run Phase 1 on correct data

The relative results show **factor 1.30 is the answer**. But we need one confirmation run on the correct 216×192 grid to produce benchmark-comparable absolute metrics.

### What to do

Run a single pipeline execution with `PR_WDF_THRESHOLD_FACTOR=1.30` on the correct `Regridded_Iowa` data:

```bash
conda activate drops-of-resilience

# Set correct data paths (Regridded_Iowa, 216×192)
export DOR_TEST8_CMIP6_HIST_DAT='\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat'
export DOR_TEST8_GRIDMET_TARGETS_DAT='\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat'
export DOR_TEST8_GEO_MASK_NPY='\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy'

# Pipeline settings (match benchmark config)
export PR_WDF_THRESHOLD_FACTOR=1.30
export DOR_MULTIPLICATIVE_NOISE_DEBIAS=0
export TEST8_SEED=42
export PR_USE_INTENSITY_RATIO=1
export PR_INTENSITY_BLEND=0.65
export TEST8_MAIN_PERIOD_ONLY=1
export DOR_RATIO_SMOOTH_SIGMA=0
export PR_INTENSITY_OUT_TAG=wdf_factor_1p30_216x192

python c:/drops-of-resilience/4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py
```

### Expected outcome

- **WDF:** Sim% ≈ Obs% (within ~0.5pp), matching the relative finding.
- **Ext99:** Should be close to +0.13% (benchmark value), since threshold factor does not affect Ext99.
- **RMSE:** Should be close to 9.91 or slightly better (fewer false wet days = fewer squared errors).
- **Grid:** 216×192 = 41,472 cells — confirm from `run_manifest.json` that `H=216, W=192`.

### Success criteria (on correct data)

| Metric | Requirement |
|--------|-------------|
| WDF Sim% | Within 1pp of WDF Obs% |
| Ext99 Bias% | Within ±1% of zero (expect ~+0.13%) |
| RMSE | ≤ 9.91 |
| Grid | 216×192 (check run_manifest.json) |

If these are met, update the default `PR_WDF_THRESHOLD_FACTOR` in `test8_v2_pr_intensity.py` from 1.15 to 1.30.

### Also fix the sweep script defaults

Update `scripts/sweep_wdf_threshold.py` lines 27-31 to point to the correct data, or better yet, remove the hardcoded defaults and require explicit `--cmip-hist`, `--gridmet-targets`, `--geo-mask` arguments so the wrong data can never be silently used again.

---

## File Organization

```
8-WDF-overprediction-fix/
  FIX-WDF-OVERPREDICTION-PLAN.md     (this file)
  scripts/
    sweep_wdf_threshold.py           Phase 1: sweep PR_WDF_THRESHOLD_FACTOR
  figures/                            side-by-side plots per sweep value
  output/
    wdf_threshold_sweep.csv          Phase 1 results (120×192 — wrong grid)
    wdf_phase2_noise_aware_n15.csv   Phase 2 result (120×192 — wrong grid)
    phase1_success_criteria.md       Summary table of Phase 1 vs criteria
```

The actual pipeline code is in `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py`. The only code change for Phase 1 is making `PR_WDF_THRESHOLD_FACTOR` read from an env var instead of being hardcoded.

---

## Completion (2026-04-10)

- **216×192 confirmation + sweep:** See `output/wdf_216x192_confirmation.md`, `output/wdf_threshold_sweep_216x192.csv`, and extended **`output/wdf_threshold_sweep_216_1p55plus.csv`** (factors 1.55–1.70, outputs on **D:**). **Default `PR_WDF_THRESHOLD_FACTOR` updated to 1.65** (best WDF vs obs on benchmark grid; 1.50 was only a first pass on 216×192).
- **`sweep_wdf_threshold.py`:** Use `--regridded-iowa-server` or explicit paths — no silent wrong defaults.
- **Disk:** A later sweep hit `No space left on device` during NPZ write; free space before large reruns.
