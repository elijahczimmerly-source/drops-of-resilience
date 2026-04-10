# Fix PR Splotchiness in Time-Aggregated Maps

## The Problem

When DOR precipitation output is averaged over the full validation period (2006-2014), the resulting spatial map shows irregular blobs ("splotches") of elevated and depressed mean precipitation that are not present in the smooth GridMET observed climatology. **Early plan text** tied artifact scale to the **~35 px** noise correlation length; **side-by-side maps** also show **broader** wet/dry structure (tens to 100+ pixels), so more than one spatial scale may matter. They are distinct from the GCM-cell blockiness visible in single-day maps.

This matters because:
- A **noise-driven** story says stochastic multiplicative noise introduces systematic spatial bias in the climatological mean; an **alternative** story says bias is dominated by **deterministic** `spatial_ratio` train/test mismatch (see **Competing hypotheses** below). The fix depends on which dominates.
- Any downstream application that uses multi-year mean precipitation fields (e.g., long-run average erosion rates in WEPP) will see these artificial spatial features.
- The splotches are visible in a simple eyeball check, which undermines confidence in the product even when scalar metrics (KGE, RMSE, Ext99) are strong.

## Where It Comes From

The splotchiness is produced by the interaction of three mechanisms in the multiplicative downscaler (`StochasticSpatialDisaggregatorMultiplicative` in `test8_v2_pr_intensity.py`). Each introduces a small asymmetry that prevents the noise from canceling to zero over many days. Together, they create a spatially varying mean bias — the splotches.

### Mechanism 1: Asymmetric clip on the noise multiplier

**Code** (`test8_v2_pr_intensity.py`, lines 534-535):
```python
noise_mult = 1.0 + cn.cpu().numpy().flatten()[valid] * cv_resid * nf
noise_mult = np.clip(noise_mult, 0.1, 8.5)
```

The noise multiplier is computed as `1.0 + (spatially correlated noise) * (residual CV) * 0.16`. Before clipping, this quantity is distributed roughly symmetrically around 1.0 (because the FFT-filtered noise `cn` is zero-mean and standardized — line 360). The clip bounds `[0.1, 8.5]` are then applied.

The problem: the clip is asymmetric around 1.0. The downside is capped at 0.1 (a 90% reduction), while the upside is capped at 8.5 (a 750% increase). For pixels where `cv_resid * nf` is large enough that the raw noise multiplier sometimes falls below 0.1, the clip truncates the left tail of the distribution more than the right tail. This makes `E[noise_mult] > 1.0` at those pixels.

How large is `cv_resid`? It's calibrated per pixel per semi-monthly period (line 499):
```python
self.resid_cv[p] = np.nanstd(resid, axis=0) / (np.nanmean(sim_base, axis=0) + 1e-4)
```
For pr, the residual CV can easily be 1.0-3.0+ at pixels with high variability relative to the mean (dry pixels with occasional storms). At `cv_resid = 2.0` and `nf = 0.16`, the noise term `cn * cv_resid * nf` has std ≈ 0.32 (since `cn` is standardized). The multiplier distribution spans roughly `1.0 +/- 3*0.32 = [0.04, 1.96]`. The lower bound 0.04 gets clipped to 0.1, truncating the left tail. At `cv_resid = 4.0`, the distribution spans `[−0.92, 2.92]`, meaning the raw multiplier goes negative — those get hard-clamped to 0.1, creating a substantial positive bias.

**Why this varies spatially:** `cv_resid` is different at every pixel. Pixels with high CV (typically drier pixels with occasional convective events) experience more clip truncation than pixels with low CV (consistently wet areas). The clip-induced bias is therefore spatially patterned, following the `cv_resid` field, which has structure at the scale of the semi-monthly calibration windows.

### Mechanism 2: Wet-day frequency (WDF) threshold censoring

**Code** (lines 540-543):
```python
if self.var_name == "pr":
    th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
    y_final = np.where(y_final <= th, 0, y_final)
    y_final = np.where(y_final < 0.1, 0, y_final)
```

After applying the noise multiplier, values at or below the WDF threshold are set to zero. This is a spatially varying censoring operation: `monthly_threshold[p]` is calibrated per pixel per semi-monthly period (lines 502-507) to match the observed wet-day frequency.

**How this creates asymmetry:** The threshold cuts from below — it removes small positive values but cannot remove large positive values. At pixels where the threshold is high relative to `y_base * noise_mult`, more of the distribution gets censored. But the large-multiplier tail survives. This creates a second spatially varying asymmetry:
- Pixels where the calibrated threshold is high (relatively dry pixels) lose more of their low-end distribution, shifting the surviving-day mean upward.
- Pixels where the threshold is low (consistently wet pixels) lose very little.

This interacts with Mechanism 1: both effects are strongest at high-CV, low-mean pixels — the same dry-but-sometimes-stormy pixels. The biases compound rather than offsetting.

**Subtlety about WDF interaction with noise:** Even if the noise multiplier were perfectly unbiased (mean exactly 1.0), the WDF threshold would still create a mean bias. Consider: on a day where `y_base = 1.0 mm` and the threshold is `0.5 mm`, the noise multiplier needs to drop below 0.5 to censor that day. Without noise, the day stays at 1.0 mm. With noise, some fraction of days get censored to 0 mm (those where the multiplier is < 0.5), while the rest are scaled up or down — but the zeros are hard, pulling the mean down. Meanwhile, on dry days where `y_base = 0.2 mm` and the threshold is `0.5 mm`, the day is always censored regardless of noise. So the WDF threshold creates a nonlinear interaction between `y_base`, the noise distribution, and the threshold level that is different at every pixel. Over many days, this doesn't average to the simple `y_base * ratio` that the deterministic model would produce.

### Mechanism 3: AR(1) temporal persistence amplifies the bias

**Code** (line 528):
```python
cn = ns if prev_noise is None else self.rho * prev_noise + np.sqrt(1 - self.rho**2) * ns
```

With `rho = 0.5` for multiplicative variables, today's noise field is 50% correlated with yesterday's. This is statistically correct for generating realistic temporal structure, but it means that the clip and WDF asymmetries don't get independent chances to cancel each day.

If a pixel gets a large positive noise draw on day 1, the AR(1) model carries ~50% of that forward to day 2, ~25% to day 3, etc. During these multi-day correlated episodes, the pixel consistently has `noise_mult > 1.0`, and the WDF threshold consistently does not censor. Then when the noise swings negative, the clip truncation at 0.1 and the WDF censoring at 0 kick in asymmetrically.

The net effect: positive excursions persist and compound over multiple days; negative excursions are truncated by the clip and censored by the WDF threshold. The AR(1) memory extends the effective averaging window needed for the bias to wash out, making the splotches more visible in a 9-year mean than they would be with independent daily noise.

### Mechanism 4: The 35-pixel correlation length sets the splotch scale

**Code** (line 590):
```python
corr_len = 35.0  # Mesoscale moisture/storm structures
```

The FFT spatial filter (line 358) applies a Gaussian kernel with this correlation length. Each day's noise field consists of smooth blobs roughly 35 pixels across. The clip and WDF biases described above act on this spatially correlated field, so the resulting mean bias inherits the same spatial scale. That's why the splotches are ~35 px across — they are the spatial footprint of the noise kernel, made visible by the asymmetric biases that prevent cancellation.

Note: the correlation length itself is not the problem. You need spatially correlated noise to generate realistic storm structures. The problem is that the clip and WDF mechanisms turn the zero-mean noise into a nonzero-mean noise, and the correlation length determines the scale of the resulting artifacts.

## Summary of Causal Chain

```
FFT noise (zero mean, 35 px blobs)
    |
    v
noise_mult = 1.0 + noise * cv_resid * 0.16   (symmetric around 1.0)
    |
    v
clip to [0.1, 8.5]                             (truncates left tail more than right)
    |                                           --> E[noise_mult] > 1.0 at high-CV pixels
    v
y_final = y_base * noise_mult
    |
    v
WDF threshold censoring                        (removes small values, keeps large)
    |                                           --> further upward shift at dry/variable pixels
    v
AR(1) persistence                               (bias compounds over correlated multi-day episodes)
    |
    v
Time-averaged: splotchy mean field with ~35 px blob structure
```

**Scope of this chain:** The diagram is an accurate account of **how noise + clip + WDF + AR(1)** can create a **nonzero-mean** multiplier field. It does **not** by itself prove that this pathway explains **most** of the observed **~0.078** splotch metric — that requires measuring how much splotch remains **with noise turned off** (deterministic downscale). See **`opus-4.6-input.txt`** and the section below.

## Competing hypotheses and third-party review (`opus-4.6-input.txt`)

Full text: **[`opus-4.6-input.txt`](opus-4.6-input.txt)** (verbatim review). Summary integrated here so the plan stays self-contained.

### Verdict (Claude Opus 4.6, 2026)

Implementation work (RNG hygiene, calendar AR(1) debias calibration, reproducibility) is **sound**, but it may have solved the **wrong dominant problem**: refinements to **empirical noise debias** barely move **`splotch_metric`**, which is what you would expect if **noise bias is not the main contributor** to the scalar.

### Empirical splotch metric is flat across configurations

| Run / source | `splotch_metric` (≈) |
|----------------|----------------------|
| Bhuwan v8_2 (different weights/params) | 0.0771 |
| `experiment_plan_nodebias` | 0.0782 |
| Attempt 1 — legacy debias | 0.0786 |
| Attempt 2 — calendar-chain debias (N=6) | 0.0783 |
| Attempt 3 — N_PASSES=24 | 0.0786 |

If **Mechanisms 1–4** (noise path) were the **dominant** source of the ~0.078 value, **correcting** that path should have produced a **visible** drop; instead the scalar is flat within ~0.001 — consistent with **hitting a floor** set by something else (e.g. deterministic ratio field), not with noise MC tuning.

### Alternative hypothesis: `spatial_ratio` train/test mismatch

Per-pixel **`spatial_ratio[p]`** is calibrated from **1981–2005** (training) GCM vs GridMET means. Applied to **2006–2014** (validation), the GCM’s **spatial** precipitation pattern need not be stationary; ratios can be **wrong out-of-sample**, producing **large-scale** wet/dry structure in the time-mean ratio map that **does not** require multiplicative noise. This is **generalization error** in the ratio field, not clip/WDF noise bias. **Empirical debias** divides wet rain by **`noise_bias` ≈ 0.99** globally and can **amplify** wet bias (`mean_ratio` moved toward ~1.06 vs ~1.05 nodebias) — consistent with fighting the wrong lever.

### Missing experiment (highest priority)

**Deterministic downscale (`noise_mult` effectively 0 for pr/wind stochastic path):** `test8_v2_pr_intensity.py` already supports **`DETERMINISTIC = True`** (module constant today; produces **`Deterministic_V8_Hybrid_*.npz`**). **Before** more noise-debias iterations:

1. Run the pipeline with **`DETERMINISTIC=True`**. **Keep `STOCHASTIC=True`:** the main block builds `full_sim` from the **stochastic** stacks (`results_main`); turning stochastic off without a refactor will break the Schaake path. A full run therefore computes **both** branches; use **`Deterministic_V8_Hybrid_pr.npz`** for the splotch diagnostic (noise-off multiplicative path). *(Consider adding env toggles later to avoid double compute.)*
2. Run **`diagnose_splotchiness.py`** on **`Deterministic_V8_Hybrid_pr.npz`** for the same validation window.

**Interpretation:**

- If **deterministic splotch ≈ stochastic splotch (~0.078)** → the scalar is mostly **not** from stochastic noise; prioritize **ratio regularization** (spatial smoothing of `spatial_ratio`, LOO-CV, or accepting the floor) and **reassess** empirical debias for product goals.
- If **deterministic splotch ≪ stochastic** → noise path matters; **Alternative A** (log-space / mean-1 multiplicative noise) in the plan becomes a **first-class** candidate rather than “second choice,” because it fixes the multiplicative model at the source.

### Other diagnostic gaps called out in the review

- **Magnitude check:** The plan never quantified **expected** splotch contribution from each mechanism vs **0.078**.
- **Spatial frequency:** If dominant patterns are **much larger than 35 px**, the noise kernel is an incomplete explanation for what you see in maps.
- **Iteration discipline:** When attempt 1 moved metrics the wrong way, the response should have included **falsifying** the dominant-noise hypothesis via deterministic baseline **before** chain bugs and **N_PASSES** sweeps (those remain useful **after** the floor is known).

### Revised priority order (supersedes “noise debias first”)

1. **Measure deterministic splotch floor** (mandatory).
2. **If floor high:** spatial smoothing / CV of ratios, compare to **LOCA2/NEX** splotch if available, or **document** acceptable residual mismatch.
3. **If floor low:** return to **noise-model** fixes — **log-space multiplier** (Alternative A) preferred over endless empirical debias tuning.
4. Keep **empirical debias** + **calendar chain** as the current **best implementation** of the *original* hypothesis, not as proof the hypothesis is complete.

## Requirements for the Fix

1. **Eliminate the splotchiness** — the time-mean pr field should be as smooth as GridMET's.
2. **Preserve Ext99 Bias% ≈ 0%** — DOR's standout metric. The fix must not dampen the heavy tail.
3. **Preserve or improve RMSE** — currently 9.91; should not get worse.
4. **Preserve or improve WDF** — currently +3.4pp overprediction; should not get worse.
5. **Preserve Lag1 error** — currently 0.056; the AR(1) temporal structure must not be disrupted.
6. **Preserve wind behavior** — wind uses the same multiplicative pathway; any fix applies to wind too unless explicitly scoped to pr only.
7. **Preserve the Schaake Shuffle** — the fix is upstream of the inter-variable rank correction; it should not interact with it.
8. **Minimal code change** — the fix should not restructure the downscaler. It should be a targeted modification to the noise application and/or calibration.

## The Fix: Empirical Per-Pixel Noise Debiasing

This section implements a **noise-path** correction (nonzero mean multiplier). It remains valid engineering **if** the deterministic splotch floor (noise off) is **materially lower** than stochastic — see **Competing hypotheses**. If deterministic splotch ≈ stochastic, prioritize **ratio / generalization** levers instead of further debias tuning.

### Approach

After calibration (which computes `spatial_ratio`, `resid_cv`, and `monthly_threshold`), run a **debiasing pass** that simulates the noise multiplier chain forward on the training period and records the per-pixel mean effective multiplier. Then divide by this mean during inference, forcing the long-run mean multiplier to be exactly 1.0 at every pixel.

This approach is chosen because:
- It fixes the root cause (nonzero mean multiplier) without changing the noise distribution's shape, variance, or correlation structure.
- It is agnostic to whether the bias comes from the clip, the WDF threshold, or their interaction — it corrects the net effect of all sources simultaneously.
- It preserves the heavy tail: the individual-day multipliers still reach 8.5; only the long-run mean is corrected. Extreme events are not dampened.
- It preserves the AR(1) structure: the temporal persistence is unchanged; only the mean is shifted.
- It is a calibration-time computation, not a per-day overhead during inference.

### Detailed Implementation Plan

#### Step 0: Diagnostic baseline

Before changing any code, quantify the current splotchiness so we can measure improvement. **Post-review prerequisite:** run **`Deterministic_V8_Hybrid_pr.npz`** through the same diagnostic once **`DETERMINISTIC=True`** (see **Competing hypotheses**) so noise vs ratio contributions are separated.

**Script:** `scripts/diagnose_splotchiness.py`

1. Load the existing blend 0.65 output (`Stochastic_V8_Hybrid_pr.npz`) from `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/experiment_blend0p65/`.
2. Load GridMET pr targets (same memmap as used in the downscaler).
3. Compute:
   - `dor_mean = np.nanmean(dor_pr[val_mask], axis=0)` — shape (H, W)
   - `obs_mean = np.nanmean(obs_pr[val_mask], axis=0)` — shape (H, W)
   - `ratio_field = dor_mean / (obs_mean + 1e-6)` — per-pixel mean ratio (should be ~1.0 everywhere if no splotchiness)
   - `splotch_metric = np.nanstd(ratio_field[geo_mask])` — scalar: the spatial standard deviation of the mean ratio field. This is the number we want to minimize.
4. Save `ratio_field` as a spatial map (PNG) and record `splotch_metric` to a CSV.

This gives us a quantitative target: reduce `splotch_metric` toward zero.

#### Step 1: Add a debiasing calibration pass to `StochasticSpatialDisaggregatorMultiplicative`

After `calibrate()` computes `spatial_ratio`, `resid_cv`, and `monthly_threshold`, add a method `calibrate_noise_bias()` that:

1. For each semi-monthly period `p`:
   a. Retrieve the training-day indices for period `p` (same selection logic as `calibrate()`).
   b. For each training day in period `p`:
      - Compute `y_base = in_val * ratio` (using the same ratio logic as `downscale_day`, including the intensity blend if enabled).
      - Draw a noise field from `generate_spatial_noise((H, W), self.corr_len)`.
      - Apply AR(1): `cn = rho * prev_cn + sqrt(1 - rho^2) * ns` (track `prev_cn` across days within the period).
      - Compute `noise_mult = 1.0 + cn * cv_resid * nf`, clip to `[0.1, 8.5]`.
      - Compute `y_final = y_base * noise_mult`.
      - Apply WDF threshold: `y_final = where(y_final <= th * 1.15, 0, y_final)` and `where(y_final < 0.1, 0, y_final)`.
      - Accumulate `y_final` and `y_base` into running sums per pixel.
   c. After all days in period `p`: `self.noise_bias[p] = sum(y_final) / (sum(y_base) + 1e-8)` — shape (H, W). This is the empirical mean effective multiplier at each pixel for this period, including the effects of clipping, WDF censoring, and AR(1) persistence.

2. **Important:** Use a fixed RNG seed for the debiasing pass that is different from the inference seed. The debiasing pass is a calibration step — it should use enough days to get a stable estimate of the mean, but it doesn't need to match the exact noise draws used during inference. The law of large numbers does the work: with ~300-600 training days per semi-monthly period (25 years × 12-24 days), the per-pixel mean will converge.

3. Store `self.noise_bias` as a `(N_PERIODS, H, W)` float32 array, same shape as `spatial_ratio`.

#### Step 2: Apply the debiasing correction in `downscale_day`

In `downscale_day`, after computing `y_final = y_base * noise_mult` and applying WDF censoring, divide by the precomputed bias:

```python
# Current code (lines 537-544):
y_final = y_base * noise_mult
if self.var_name == "pr":
    th = self.monthly_threshold[period_idx].flatten()[valid] * PR_WDF_THRESHOLD_FACTOR
    y_final = np.where(y_final <= th, 0, y_final)
    y_final = np.where(y_final < 0.1, 0, y_final)
    y_final = np.clip(y_final, 0, 250.0)

# New code — add after the existing WDF censoring block:
if hasattr(self, 'noise_bias'):
    bias = self.noise_bias[period_idx].flatten()[valid]
    # Only debias non-zero pixels (zeros are censored, not biased)
    nonzero = y_final > 0
    y_final[nonzero] = y_final[nonzero] / (bias[nonzero] + 1e-8)
    # Re-apply physical cap after debiasing
    if self.var_name == "pr":
        y_final = np.clip(y_final, 0, 250.0)
```

**Why divide only non-zero pixels:** Zeros come from WDF censoring — they represent "no rain" decisions, not biased rain amounts. Dividing a zero by the bias factor would still be zero, so this is a no-op for zeros, but the conditional avoids potential numerical issues and makes the intent clear.

**Why this preserves Ext99:** The bias factor `noise_bias[p]` is the *mean* effective multiplier, typically something like 1.02-1.10 at high-CV pixels. Dividing by 1.05 scales down all non-zero values by ~5%. This is a uniform percentage reduction per pixel per period — it shifts the entire distribution, including the tails, by the same factor. An extreme event that produced 80 mm/day now produces 80/1.05 ≈ 76 mm/day. Since the bias factor is small (a few percent), the Ext99 impact is proportionally small. And since the current Ext99 Bias% is +0.13% (very slightly above zero), a small downward shift from the debiasing may actually improve it or leave it negligibly changed.

**Why this preserves Lag1:** The AR(1) noise structure is unchanged. The debiasing divides by a static per-pixel per-period field — it doesn't modify the temporal correlation between consecutive days' noise fields. Day-to-day transitions are preserved exactly.

#### Step 3: Scope the fix

The multiplicative pathway is shared between pr and wind. Both variables should get the debiasing because:
- Wind uses the same `noise_mult = 1.0 + cn * cv_resid * nf` and `clip(0.1, 8.5)` logic.
- Wind doesn't have WDF censoring, but the clip asymmetry still applies.
- Wind's time-mean maps showed blockiness/artifacts in the same analysis.

The additive pathway (tasmax, tasmin, rsds, huss) does NOT need this fix:
- Additive noise is `y_final = y_base + noise * resid_std * nf` — there is no clip that creates asymmetry.
- Additive noise is zero-mean by construction and stays zero-mean after addition.
- The `np.maximum(y_final, 0.0)` for rsds/huss (line 438) could theoretically create a small positive bias at pixels where the noise occasionally pushes values negative, but this is negligible for these variables in Iowa (rsds and huss are well above zero in all seasons).

#### Step 4: Validate

Run the full pipeline with debiasing enabled and compare against the baseline:

1. **Splotch metric:** Re-run `diagnose_splotchiness.py` on the new output. `splotch_metric` (spatial std of the mean ratio field) should be substantially reduced.
2. **Visual:** Generate time-mean and seasonal-mean pr maps. The splotches should be gone or greatly reduced.
3. **Scalar metrics from `V8_Table1`:**
   - Ext99 Bias%: should remain near 0% (within +/- 1%).
   - RMSE: should stay near 9.91 or improve (debiasing reduces the systematic component of error).
   - WDF: should stay near 35.9% or improve. Debiasing reduces the mean at high-bias pixels, which may push some marginal days below the 0.1 mm wet-day threshold — this could slightly reduce WDF overprediction.
   - Lag1: should be unchanged (0.056).
   - KGE: may improve slightly (the bias component of KGE benefits from reduced spatial bias).
4. **Wind metrics:** Check that wind Ext99 (-7.5%) and Lag1 (0.045) are preserved.

#### Step 5: Sensitivity check

The debiasing pass uses a finite sample of training days. Check sensitivity:
1. Run `calibrate_noise_bias()` with two different RNG seeds. Compare the resulting `noise_bias` fields. They should be very similar (pixel-wise correlation > 0.99) because each semi-monthly period has ~300-600 training days — enough for the mean to converge.
2. If they differ materially, increase the sample size by running multiple passes and averaging the bias estimates.

## Alternative Approaches Considered (and why they're second choice)

### A. Log-space noise model

Replace `noise_mult = 1.0 + cn * cv_resid * nf` with `noise_mult = exp(cn * cv_resid * nf - 0.5 * (cv_resid * nf)^2)`.

**Pros:** Eliminates the clip asymmetry at the source. The exp transform is naturally positive (no clip needed) and the `-0.5 * sigma^2` correction makes it exactly mean-1 in expectation.

**Cons:** Changes the noise distribution shape (lognormal vs shifted Gaussian). The heavy tail behavior would be different — extreme multipliers would follow a lognormal tail instead of a clipped Gaussian tail. This could affect Ext99 in unpredictable ways and would require re-tuning `nf` and the clip bounds. It also doesn't fix the WDF threshold asymmetry (Mechanism 2), which would still exist. More invasive than the empirical debiasing, and harder to validate that it doesn't break anything.

**When to consider:** If the empirical debiasing leaves residual splotchiness because the bias estimates don't converge well, a log-space model might be cleaner. But try the empirical approach first.

### B. Reducing NOISE_FACTOR_MULTIPLICATIVE

Simply lowering `nf` from 0.16 to something smaller reduces the amplitude of the noise, making fewer samples hit the clip bounds and reducing the asymmetry.

**Pros:** One-line change.

**Cons:** Directly trades splotchiness against Ext99. The noise is what generates realistic extreme events. Reducing it would dampen the heavy tail, degrading the metric DOR is best at. This is the tradeoff Bhuwan has been navigating between v9 (too aggressive) and v2 (current). Not recommended as a standalone fix.

### C. Symmetric clip bounds

Change `clip(0.1, 8.5)` to something symmetric in log-space, e.g., `clip(1/8.5, 8.5) = clip(0.118, 8.5)`.

**Pros:** Reduces the clip asymmetry.

**Cons:** Only fixes Mechanism 1 (clip asymmetry), not Mechanism 2 (WDF threshold). The improvement would be partial. Also, changing the lower clip from 0.1 to 0.118 is a tiny change that would barely affect the bias.

### D. Separate "is it raining?" from "how much?"

Split the multiplicative step into two: first decide whether the pixel is wet (using a stochastic occurrence model), then apply the noise multiplier only to wet pixels.

**Pros:** Eliminates Mechanism 2 entirely — the WDF decision is made independently of the noise amplitude.

**Cons:** Major structural change to the downscaler. Requires designing and calibrating a separate stochastic occurrence model. High risk of introducing new problems. Not appropriate as a targeted fix.

## File Organization

```
7-fix-pr-splotchiness/
  FIX-PR-SPLOTCHINESS-PLAN.md        (this file)
  opus-4.6-input.txt                 third-party review (hypothesis check; incorporated into "Competing hypotheses" above)
  VALIDATION_RESULTS.md              measured Step 0/4/5 outcomes (separate from plan text)
  WORKLOG.md                         what was tried, why, and how conclusions were reached
  scripts/
    diagnose_splotchiness.py         Steps 0 & 4: splotch metric CSV; optional PNG + .npy; seasonal maps; --debiased-npz compare
    step4_validation.py              Step 4 driver: diagnose (baseline vs debiased) + validate_fix on two V8_Table1 CSVs
    validate_fix.py                  Merge two V8_Table1_Pooled_Metrics_Stochastic.csv and print deltas
    test8_v2_debiased.py             Launcher (delegates to 4-test8-v2-pr-intensity; forces debias on)
    dump_noise_bias.py               Step 5: save noise_bias tensor only (same env as pipeline for PR intensity / blend)
    sensitivity_compare_debias_seeds.py  Step 5: two seeds → two dumps → land pixel correlation (warn if < 0.99)
    audit_noise_bias.py              Phase 2 A.2: histogram-style stats on dump_noise_bias .npz (<1 vs >1 per period)
    sweep_debias_passes.py           Phase 2 A.3 / B1: sweep DOR_NOISE_DEBIAS_N_PASSES → split_half_corr CSV
    compare_pre_post_schaake_pr.py   Phase 2 A.1: splotch metric pre- vs post-Schaake PR stacks
    plot_validation_agg_mean_pr.py   time-mean validation GridMET|DOR PNGs (same style as 6-product-comparison `validation_agg_mean_pr.png`)
  figures/pr-splotch-side-by-side/   baseline + per-attempt side-by-side maps; see `README.txt`
  output/
    baseline/                        (optional: put diagnostic outputs from pre-debias NPZ here)
    debiased/                        (optional: diagnostic outputs after debias)
```

**Steps 1–3 (core downscaler):** implemented in `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py` — `calibrate_noise_bias()`, inference-time divide, env `DOR_MULTIPLICATIVE_NOISE_DEBIAS` (default on), `DOR_NOISE_DEBIAS_SEED`. Baseline parity: `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`.

**Calibration detail (important):** `calibrate_noise_bias()` advances AR(1) noise on **every calendar day** (train + test) and accumulates `sum_yb` / `sum_yf` only on **training** days — matching `run_downscale_loop` / `downscale_day`. Earlier drafts of the plan described resetting noise **within** each semi-monthly period; that was incorrect and has been fixed (`noise_debias_calibration: calendar_ar1_chain` in `run_manifest.json`).

## Completion checklist (repo-side)

| Step | Status |
|------|--------|
| 0 | **Done.** Baseline splotch measured: 0.0771 (Bhuwan v8_2), 0.0782 (our nodebias). |
| 1–3 | **Done (obsolete).** Noise debias implemented — proved ineffective. Set `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`. |
| 4 | **Done.** Attempt 4 (deterministic floor): proved noise is not the cause. |
| 5 | **Done.** Ratio smoothing sweep — failed (boundary contamination). |
| Diagnosis | **Done.** Pipeline stage plots + multi-GCM comparison confirmed splotches originate from GCM input. |
| **Overall** | **CLOSED.** Splotches are a GCM limitation, not fixable in the downscaler. |

**Measured results (all attempts):** see **[`VALIDATION_RESULTS.md`](VALIDATION_RESULTS.md)**.

Rationale and experiment history: **[`WORKLOG.md`](WORKLOG.md)**.

### Status as of 2026-04-09 — CLOSED

**Final conclusion:** The pr splotches in time-aggregated maps originate from the GCM's coarse spatial precipitation pattern, not from the spatial downscaler. Confirmed by examining pipeline stage plots across multiple GCMs — the splotch patterns are already present in the GCM input before the downscaler runs. The downscaler's spatial_ratio faithfully reproduces them. This is not fixable in the spatial downscaler.

| Item | Outcome |
|------|--------|
| **Root cause** | **GCM spatial pattern.** The GCM has ~3-4 cells across Iowa; their relative wetness doesn't match GridMET and varies between training and validation periods. The downscaler passes this through. |
| **Noise debias (Attempts 1-3)** | **Closed — ineffective.** Splotch metric flat across all attempts (0.078 ± 0.001). Set `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`. |
| **Attempt 4 (deterministic floor)** | Deterministic splotch 0.0709 ≈ stochastic 0.0710. Confirmed noise is not the cause. |
| **Attempt 5 (ratio smoothing)** | Failed — boundary contamination at moderate sigma, field destruction at large sigma. Moot anyway since the splotches are GCM-origin. |
| **Phase 3 (ratio generalization)** | **Not pursued.** Diagnosis showed the issue is upstream of the downscaler. |
| **Resolution** | Accept. The splotches are a GCM limitation. Move on to WDF and wind. |

---

## Third-party review and root cause diagnosis (2026-04-09, updated after Attempt 4)

### Summary of all attempts

| Attempt | What changed | splotch_metric | Ext99 Bias% | Outcome |
|---------|-------------|----------------|-------------|---------|
| Bhuwan v8_2 (reference) | Different autocorrelation weights | **0.0771** | −6.7% | — |
| 1 (legacy debias) | Empirical noise debias, N=6 | **0.0786** | +0.79% | No improvement; Ext99 worse |
| 2 (calendar-chain fix) | Fixed AR(1) chain bug in debias calibration | **0.0783** | +0.75% | Bug fix, no splotch improvement |
| 3 (N_PASSES=24) | More MC passes for noise_bias estimate | **0.0786** | +0.61% | Ext99 better, splotch slightly worse |
| **4 (deterministic floor)** | **noise=0, debias off** | **0.0709** | −11.6% | **Proved noise is not the cause** |
| 4 (stochastic, same run) | Standard noise, debias off | **0.0710** | −0.23% | Same splotch as deterministic |

### What Attempt 4 proved

The deterministic (noise=0) run has splotch_metric **0.0709**. The stochastic run from the same job has **0.0710**. The difference is **0.0001** — noise contributes essentially **nothing** to the splotch metric. The entire noise-debias approach (Attempts 1-3) was targeting a mechanism that accounts for ~0.1% of the observed splotchiness.

Note: the stochastic splotch from Attempt 4 (0.0710) is lower than the earlier `plan_nodebias` (0.0782), both with debias off. This drop came from code changes between Apr 8 and Apr 9 (calendar-chain fix and related refactoring), not from the deterministic test itself. The key comparison is **within** Attempt 4: deterministic vs stochastic from the same code revision, same seed, same run — and they are identical.

### Why Attempts 1-3 failed: the noise debias was solving the wrong problem

The plan's 4-mechanism theory (clip asymmetry → WDF censoring → AR(1) persistence → 35px correlation length) is **mathematically correct** — these mechanisms DO create a nonzero-mean effective multiplier. But the theory was never tested against the data before building a solution. The evidence always pointed away from noise as the dominant cause:

1. **The splotch metric never moved.** If noise bias were the dominant source of the 0.078 splotch, correcting it — even imperfectly — should produce a visible drop. Four attempts at correction produced zero improvement. This is the signature of targeting a small component while the dominant component is untouched.

2. **Bhuwan's v8_2 has the same splotchiness.** Different spatial autocorrelation weights, different noise parameters → same splotch metric (0.0771 vs 0.0782). If the splotchiness came from the noise pathway, different noise parameters should yield meaningfully different splotch metrics.

3. **The splotch patterns are the wrong spatial scale.** The plan predicts ~35px blobs (the noise correlation length). The actual patterns in the time-mean maps are much larger — broad wet/dry regions spanning 50-100+ pixels. These are spatial ratio generalization errors, not noise artifacts.

4. **Attempt 4 confirmed it empirically.** Deterministic splotch (0.0709) ≈ stochastic splotch (0.0710). QED.

### What IS causing the splotchiness: spatial ratio train/test mismatch

The multiplicative downscaler calibrates per-pixel ratios on 1981-2005 training data:

```python
self.spatial_ratio[p] = np.clip(m_obs / (m_gcm + 1e-4), 0.05, 20.0)
```

These ratios encode where the GCM is too wet or too dry relative to GridMET during the training period. When applied to 2006-2014 validation data, they don't generalize perfectly — the GCM's spatial pattern of precipitation isn't stationary between training and test periods. The per-pixel ratio that was correct in training becomes a spatially-varying bias in validation.

This is a **train/test generalization error in the spatial ratios**, not a noise bias. The ratio field `m_obs / m_gcm` has pixel-scale noise from: (a) sampling variability in 25 years of GCM and observed means, (b) real climatological non-stationarity between 1981-2005 and 2006-2014, and (c) GridMET's own spatial noise at 4km. All of these create per-pixel ratio errors that show up as splotches when applied out-of-sample.

**The `mean_ratio` column confirms this.** The nodebias stochastic run has `mean_ratio = 1.050` — DOR is 5% wet-biased on average. This bias comes from `spatial_ratio` not perfectly predicting out-of-sample, not from noise. The debias made it worse (1.061) because `noise_bias ≈ 0.990`, so dividing by it scaled precipitation UP, amplifying the existing wet bias.

### Visual assessment of Attempt 4 (deterministic map)

Among the four attempts in `figures/pr-splotch-side-by-side/`, Attempt 4 shows the **largest visible change** from the baseline. Central-domain splotch-like patterns became less pronounced, which matches the goal. Southern splotch-scale structure also became less pronounced — but those features **are present in GridMET** (they are real observed features, so damping them in the simulation is ambiguous at best). The splotch_metric cannot distinguish helpful smoothing in one region from unhelpful smoothing in another.

### What the noise debias code DOES accomplish (not nothing — just not splotch reduction)

The empirical debias with higher N_PASSES (Attempt 3) improved **Ext99** (+0.61% vs −0.05% nodebias — both near zero, slight tradeoff) and **RMSE** (9.928 vs 9.905 — marginal). It also brings the mean effective multiplier closer to 1.0 in expectation. These are real but small effects on scalar metrics. They do not reduce the time-mean spatial pattern mismatch because that pattern is dominated by `spatial_ratio` generalization error.

**Decision:** Set `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` (off) as the default going forward. The debias code can be kept for reference but should not be used in production runs — it adds ~7-30 min calibration time, does not improve splotchiness, and slightly worsens Ext99 and mean bias.

---

## Phase 3 — Fixing the actual cause (spatial ratio generalization)

### Goals

| Goal | Target |
|------|--------|
| **Splotch** | Reduce spatial std of time-mean sim/obs ratio below **0.060** (vs current ~0.071 nodebias) |
| **Ext99** | Stay near **0%** bias on pr (within ±1%) |
| **RMSE / WDF / Lag1** | No large regression vs nodebias baseline |

### Approach A: Spatial smoothing of calibrated ratios (Attempt 5)

**Idea:** After calibrating `spatial_ratio[p]` per pixel, apply a Gaussian spatial filter to smooth it. This trades per-pixel precision for spatial coherence — the smoothed ratios suppress pixel-scale calibration noise that doesn't generalize to the validation period.

**Why this should work:**
- The splotch patterns are at scales of 50-100+ pixels. The pixel-scale ratio noise that creates them when applied out-of-sample will be suppressed by smoothing at sigma=5-15 pixels.
- Real large-scale climatological gradients (wetter east Iowa, drier west) are preserved because they have much longer wavelengths than the smoothing kernel.
- This is standard regularization — the same logic as ridge regression or Bayesian priors. Per-pixel ratios overfit; smoothed ratios generalize.

**Risks:**
- Over-smoothing (sigma too large) will erase real sub-GCM spatial structure that the ratios correctly capture, worsening RMSE and potentially Ext99.
- The right sigma probably depends on the variable and semi-monthly period. Start with one global value and refine if needed.
- WDF threshold calibration uses `sim_base = in_m * spatial_ratio`, so smoothing the ratio changes the threshold. This interacts with WDF tuning — do ratio smoothing BEFORE WDF threshold tuning (`8-WDF-overprediction-fix/`).

#### Attempt 5: Detailed implementation plan

##### 5.1 New env variable

Add to `test8_v2_pr_intensity.py` module-level config (near the other `DOR_*` env reads):

```python
# Spatial smoothing of multiplicative ratios (Phase 3 splotch fix)
# 0 = no smoothing (current behavior). Positive float = Gaussian sigma in pixels.
DOR_RATIO_SMOOTH_SIGMA = float(os.environ.get("DOR_RATIO_SMOOTH_SIGMA", "0").strip())
```

Document in the script docstring alongside the other env variables.

##### 5.2 New import

Add at the top of the file, with the other imports:

```python
from scipy.ndimage import gaussian_filter
```

`scipy` is already in `environment.yml` (dependency of `xarray` / `xesmf`), so no new install needed.

##### 5.3 Code change: smooth ratios inside `StochasticSpatialDisaggregatorMultiplicative.calibrate()`

The smoothing must happen **after** computing `spatial_ratio[p]` (and `spatial_ratio_ext[p]` if PR intensity is on) but **before** computing `resid_cv[p]` and `monthly_threshold[p]`, because those are derived from `sim_base = in_m * spatial_ratio[p]` and must be consistent with the smoothed ratio.

##### CRITICAL: Use normalized convolution, NOT naive fill-and-smooth

**Attempt 5 (first try) used a naive approach** that filled non-land pixels with 1.0 before smoothing. This caused **boundary contamination**: edge land pixels got averaged with the 1.0 fill values, pulling their ratios toward 1.0. For Iowa pr ratios (typically 1.0-1.5), this depressed edges systematically, creating a NEW spatial pattern that **increased** the splotch metric at sigma=5-15 and destroyed the field at sigma=20. See `attempt5_ratio_smooth_sweep.csv` — splotch went from 0.078 to 0.082-0.090 before collapsing to 0.044 at sigma=20 (field obliterated).

**The fix is normalized convolution.** This standard technique smooths only over valid (land) neighbors at each pixel. Near domain edges, the kernel footprint that falls outside land is simply excluded from the average rather than being filled with an arbitrary value.

Replace the smoothing helper with:

```python
def _smooth_ratio_field(field_2d, land_2d, sigma):
    """Gaussian-smooth a 2D ratio field using normalized convolution (land-only).

    At boundary pixels where the kernel extends past the land mask, only the
    land portion contributes to the weighted average.  This avoids the boundary
    contamination that occurs when non-land is filled with a constant (1.0).
    """
    field = np.asarray(field_2d, dtype=np.float64).copy()
    field[~land_2d] = 0.0                         # zero out non-land
    weight = land_2d.astype(np.float64)            # 1 on land, 0 off

    numerator   = gaussian_filter(field,  sigma=sigma)
    denominator = gaussian_filter(weight, sigma=sigma)

    out = np.where(denominator > 1e-8, numerator / denominator, 1.0)
    out[~land_2d] = 1.0                            # restore non-land to neutral
    return np.clip(out, 0.05, 20.0).astype(np.float32)
```

In `calibrate()`, after `spatial_ratio[p]` and `spatial_ratio_ext[p]` are computed but **before** `resid_cv`:

```python
            # Phase 3: Spatial smoothing of calibrated ratios (normalized convolution)
            if DOR_RATIO_SMOOTH_SIGMA > 0:
                self.spatial_ratio[p] = _smooth_ratio_field(
                    self.spatial_ratio[p], land_2d, DOR_RATIO_SMOOTH_SIGMA
                )
                if self.use_intensity_ratio and self.var_name == "pr":
                    self.spatial_ratio_ext[p] = _smooth_ratio_field(
                        self.spatial_ratio_ext[p], land_2d, DOR_RATIO_SMOOTH_SIGMA
                    )
```

**Why normalized convolution works here:** A pixel at the domain edge might have 40% of its Gaussian kernel footprint over land and 60% over ocean/non-land. With fill-and-smooth, those 60% contribute 1.0 each, contaminating the result. With normalized convolution, those 60% contribute nothing — the average is taken only over the 40% that are on land. The pixel gets the weighted mean of its land neighbors, which is the correct spatial average.

**What this does NOT smooth:** `resid_cv` and `monthly_threshold`. These are computed downstream from the already-smoothed `spatial_ratio`, so they automatically inherit the smoothed structure via `sim_base = in_m * self.spatial_ratio[p]`. Do NOT separately smooth them — their per-pixel values are physically meaningful (local residual variability, local wet-day threshold) and should respond to the smoothed ratio naturally.

**What this does NOT touch:** The additive class (`StochasticSpatialDisaggregatorAdditive`) uses `spatial_delta = m_obs - m_gcm`, which is an additive correction. The splotchiness problem is specific to the multiplicative pathway. Do not smooth `spatial_delta` in this attempt — if additive variables also show splotchiness after this fix, that can be a follow-up.

##### 5.4 Log the smoothing

Add a log line at the start of `calibrate()` if smoothing is active:

```python
    def calibrate(self, inputs, targets, dates):
        log(f"  [{self.var_name.upper()}] Calibrating Spatial Ratios ({N_PERIODS} periods)"
            + (f" with Gaussian smooth sigma={DOR_RATIO_SMOOTH_SIGMA}" if DOR_RATIO_SMOOTH_SIGMA > 0 else "")
            + "...")
```

##### 5.5 Record in run manifest

In the manifest-writing section (wherever `run_manifest.json` is assembled), add:

```python
"ratio_smooth_sigma": DOR_RATIO_SMOOTH_SIGMA,
```

##### 5.6 Validation runs

**Attempt 5a (failed — naive fill-and-smooth):** Used `raw[~land_2d] = 1.0` then `gaussian_filter`. Results in `attempt5_ratio_smooth_sweep.csv`: splotch INCREASED at sigma=5-15 due to boundary contamination, then collapsed at sigma=20 (field destroyed). Maps confirm progressive blurring and domain shrinkage. **Do not reuse these runs.**

**Attempt 5b (re-sweep with normalized convolution):** Replace the smoothing code per §5.3 above, then re-run the full sweep.

Run the pipeline for **each** sigma value below, all with the same settings:
- `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` (noise debias off)
- `TEST8_SEED=42`
- `PR_USE_INTENSITY_RATIO=1`, `PR_INTENSITY_BLEND=0.65`
- `TEST8_MAIN_PERIOD_ONLY=1`
- Same UNC memmaps as all prior attempts

| Run | `DOR_RATIO_SMOOTH_SIGMA` | `PR_INTENSITY_OUT_TAG` |
|-----|--------------------------|------------------------|
| Baseline (reuse attempt5a sigma=0 — unaffected by smoothing bug) | 0 | `attempt5b_sigma0` |
| Sweep | 5 | `attempt5b_sigma5` |
| Sweep | 10 | `attempt5b_sigma10` |
| Sweep | 15 | `attempt5b_sigma15` |
| Sweep | 20 | `attempt5b_sigma20` |

For each run, after the pipeline completes:

1. Run `diagnose_splotchiness.py` on `Stochastic_V8_Hybrid_pr.npz` → record `splotch_metric`
2. Read `V8_Table1_Pooled_Metrics_Stochastic.csv` → record pr `Val_Ext99_Bias%`, `Val_RMSE_pooled`, `Val_KGE`, `Val_Lag1_Err`, `Val_WDF_Sim%`
3. Also check wind row from the same Table1 — wind uses the same multiplicative pathway and same smoothing
4. Generate side-by-side figure: `plot_validation_agg_mean_pr.py` → `figures/pr-splotch-side-by-side/dor_val_05_attempt5_ratio_smooth_sigma{NN}.png` (or run `sweep_ratio_smooth.py --figures-dir` to emit those names automatically)

**Automation option:** Write a `sweep_ratio_smooth.py` script that loops over sigma values, sets the env, calls the pipeline, and collects splotch + Table1 pr row into a single CSV. This avoids manual repetition. Each run takes ~27 min on CPU, so the full sweep is ~2 hours.

##### 5.7 Success criteria

| Metric | Requirement |
|--------|-------------|
| splotch_metric | Meaningfully below 0.071 (Attempt 4 stochastic baseline). Target < 0.060. |
| Ext99 Bias% | Within ±1% of zero |
| RMSE | No worse than 10.0 (current ~9.9) |
| Lag1 Err | No worse than 0.060 (current ~0.055) |
| WDF | No worse than 36.5% (current ~35.7%) |
| Wind Ext99 | No worse than −8% (current −7.5%) |

**Pick the smallest sigma that meets the splotch target** without violating any of the other constraints. If no sigma meets all constraints, pick the best tradeoff and document it.

##### 5.8 Expected outcome

Smoothing at sigma=5-10 should reduce splotchiness noticeably while preserving large-scale gradients. The Ext99 impact should be small because the PR intensity blend uses `spatial_ratio_ext` (extreme ratio), which is also smoothed — the ratio of the smoothed extreme ratio to the smoothed base ratio will be similar to the unsmoothed version. RMSE may slightly improve (removing systematic spatial bias reduces squared error) or slightly worsen (smoothing removes real local corrections).

If the sweep shows splotch_metric monotonically decreasing with sigma while Ext99 stays stable, this confirms the ratio-overfitting hypothesis and we have a simple, clean fix. If splotch_metric plateaus early (say at sigma=5) and doesn't improve further, the residual is from real non-stationarity and we should accept it.

##### 5.9 After the sweep

- Record all results in `VALIDATION_RESULTS.md` under "Attempt 5 — ratio smoothing sweep"
- Update `WORKLOG.md` with one paragraph: hypothesis, what ran, outcome, next step
- If a good sigma is found: lock it, update `DOR_RATIO_SMOOTH_SIGMA` default in the script, unblock `8-WDF-overprediction-fix/`
- If no sigma works: proceed to Approach B (cross-validated regularization) or Approach C (accept)

##### 5.10 Optional: Measure LOCA2/NEX splotchiness for context

Use the already-interpolated external products from `6-product-comparison/` to compute the same splotch metric. This tells us what "good" looks like for competing products and whether 0.071 is actually a problem worth solving.

**Script:** Adapt `diagnose_splotchiness.py` or write a thin wrapper that loads the LOCA2/NEX interpolated fields (from `6-product-comparison/scripts/run_benchmark.py`'s alignment step) and computes `splotch_metric = std(sim_mean / obs_mean)` over the same 2006-2014 validation window and Iowa land mask.

**If LOCA2 splotch ≈ 0.07:** Our 0.071 is already competitive. Accept and move to WDF/wind.
**If LOCA2 splotch ≪ 0.07:** The smoothing sweep is worth pursuing. LOCA2 uses analog-based downscaling which inherits observed spatial patterns directly — it should have lower splotchiness than a ratio-based method.

### Approach B: Cross-validated ratio regularization

**Idea:** Use leave-one-year-out on the 25 training years to estimate the variance of the per-pixel ratio. Pixels where the ratio is unstable across years get shrunk toward the domain mean. This is more principled than a fixed Gaussian filter because it adapts to the local signal-to-noise ratio.

**Implementation sketch:**
```python
for p in range(N_PERIODS):
    ratios_by_year = []  # list of per-pixel ratios from each training year
    for year in training_years:
        idx_year = [i for i in period_indices if dates[i].year == year]
        m_gcm_y = np.nanmean(inputs[idx_year, v_idx], axis=0)
        m_obs_y = np.nanmean(targets[idx_year, v_idx], axis=0)
        ratios_by_year.append(m_obs_y / (m_gcm_y + 1e-4))
    ratio_stack = np.stack(ratios_by_year)
    ratio_mean = np.nanmean(ratio_stack, axis=0)
    ratio_var = np.nanvar(ratio_stack, axis=0)
    domain_mean = np.nanmean(ratio_mean[land])
    # James-Stein-style shrinkage: high-variance pixels → domain mean
    shrinkage = ratio_var / (ratio_var + tau**2)
    self.spatial_ratio[p] = (1 - shrinkage) * ratio_mean + shrinkage * domain_mean
```

**Pros:** Adaptive — doesn't over-smooth areas with strong, stable signals. More principled.

**Cons:** More complex. The 25 training years give noisy per-year ratio estimates for semi-monthly periods (~12-15 days per year per period). May need to pool across periods or use monthly instead of semi-monthly for the variance estimate. Try Approach A first.

### Approach C: Accept the current splotchiness

**Rationale:** The splotch metric of 0.071 may be the natural floor for a per-pixel ratio-based downscaler evaluated out-of-sample on a different 9-year period. GridMET itself has spatial noise at 4km. The GCM's spatial climatology is not expected to be stationary at the pixel level across decades. LOCA2 and NEX likely have comparable or worse spatial pattern accuracy (never measured for them).

**When to choose this:** If Approach A at moderate sigma (5-10 px) doesn't meaningfully improve the splotch metric, the residual splotchiness is probably from real non-stationarity, not overfitting. At that point, accept 0.071, document it, and move on to WDF and wind.

### Recommended sprint order

1. **Approach A sweep:** Implement `DOR_RATIO_SMOOTH_SIGMA`, run sigma = {0, 5, 10, 15, 20} with `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`. Record splotch_metric + Table1 pr for each. Pick the sigma that minimizes splotch without regressing Ext99 below ±1%.
2. **If sigma sweep succeeds:** Lock the best sigma, proceed to `8-WDF-overprediction-fix/` (WDF threshold tuning on the smoothed-ratio baseline).
3. **If sigma sweep fails** (splotch doesn't improve or Ext99 degrades at all sigma values): Try Approach B or go to Approach C (accept).
4. **Measure LOCA2/NEX splotchiness** using the same `diagnose_splotchiness.py` diagnostic (already have the interpolated products from `6-product-comparison/`). This gives context for what “good” looks like. If LOCA2 has splotch ≈ 0.07, our 0.071 is already competitive.

### Coordination with other priorities

- **`8-WDF-overprediction-fix/`:** WDF tuning MUST wait until ratio smoothing is decided. Smoothing changes `sim_base = in_val * ratio`, which changes the WDF threshold calibration. Do not tune WDF on an unsmoothed baseline if you plan to smooth later.
- **`10-improve-wind/`:** Wind uses the same `spatial_ratio` → same smoothing would apply. Run wind metrics alongside pr in the sigma sweep. Wind is likely to benefit (blockiness in wind time-mean maps is also a ratio generalization issue).
- **Noise debias code:** Keep in the codebase behind `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` default. Do not delete — the calibration infrastructure may be useful for future diagnostics. But do not use it in production runs.



