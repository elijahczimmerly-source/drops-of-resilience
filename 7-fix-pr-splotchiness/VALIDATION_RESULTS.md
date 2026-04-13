# PR splotchiness / noise debias — validation results

**Note on `splotch_metric`:** The scalar metric used throughout this investigation (spatial std of time-mean DOR/OBS ratio) was an unreliable proxy. It did not correspond to the visual splotchiness seen in the plots and should not be treated as a meaningful measure of the actual problem. It is retained in this file for completeness but should not inform future decisions.

**Note on time windows:** Many tables below use **2006–2014** (validation split). **Short-window** time-mean maps can look much worse than **full historical** (1981–2014) means for eyeball comparison to GridMET. See [`WORKLOG.md`](WORKLOG.md) §12 and [`../dor-info.md`](../dor-info.md) (*Time-mean PR maps*).

Narrative of **decisions and experiments** (why things were tried): [`WORKLOG.md`](WORKLOG.md).

Standalone record of runs executed against UNC data (`\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa`, **216×192** grid). See `FIX-PR-SPLOTCHINESS-PLAN.md` for methodology.

## Configuration (shared across A/B pipeline runs)

| Setting | Value |
|---------|--------|
| `TEST8_SEED` | 42 |
| `PR_USE_INTENSITY_RATIO` | 1 |
| `PR_INTENSITY_BLEND` | 0.65 |
| `TEST8_MAIN_PERIOD_ONLY` | 1 |
| `DOR_NOISE_DEBIAS_N_PASSES` | 6 (when debias calibration runs) |
| Memmaps | `DOR_TEST8_CMIP6_HIST_DAT` → `...\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat`; `DOR_TEST8_GRIDMET_TARGETS_DAT` / `DOR_TEST8_GEO_MASK_NPY` → `Regridded_Iowa\` |

## Step 0 — reference splotch metric (Bhuwan v8_2 product)

| Item | Value |
|------|--------|
| Source NPZ | `...\Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\Stochastic_V8_Hybrid_pr.npz` |
| Output folder | `7-fix-pr-splotchiness/output/step0_bhuwan_v82/` |
| **splotch_metric** (spatial std of time-mean DOR/OBS ratio, 2006–2014) | **≈ 0.0771** |

## Step 4 — full pipeline A vs B

| Run | Output directory under `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/` | `DOR_MULTIPLICATIVE_NOISE_DEBIAS` |
|-----|------------------------------------------------------------------|-----------------------------------|
| A (nodebias) | `experiment_plan_nodebias/` | 0 |
| B (debiased) | `experiment_plan_debias/` | 1 |

Aggregated analysis (CSV + figures): **`7-fix-pr-splotchiness/output/step4_validation_apr2026/`**

- `splotch_compare.csv` — per-label splotch metrics and seasonal rows where computed  
- `step4_table1_diff.csv` — merged Table1 + deltas (`validate_fix.py`)

### PR — pooled validation metrics (2006–2014)

| Metric | A (nodebias) | B (debiased) | Δ (B − A) |
|--------|----------------|--------------|-----------|
| Val_Ext99_Bias% | −0.0539 | +0.7912 | +0.845 |
| Val_RMSE_pooled | 9.905 | 9.942 | +0.037 |
| Val_KGE | 0.0240 | 0.0232 | −0.0008 |
| Val_Lag1_Err | 0.0558 | 0.0570 | +0.0012 |
| Val_WDF_Sim% | 35.746 | 35.740 | −0.007 |
| Val_Bias | 0.1128 | 0.1385 | +0.0257 |

Non-PR variables matched between A and B (debias does not target additive pathway).

### Splotch scalar (same diagnostic as Step 0)

| Label | splotch_metric | mean_ratio (DOR_mean/OBS_mean) |
|-------|----------------|--------------------------------|
| plan_nodebias | **0.0782** | ~1.050 |
| plan_debias | **0.0786** | ~1.061 |

**Interpretation:** On this run, debias did **not** lower the splotch metric; Ext99 bias moved **away** from ~0%. Follow-up may require more `DOR_NOISE_DEBIAS_N_PASSES`, re-checking debias vs **Schaake** ordering, or a revised correction.

## Step 5 — reproducibility

| Check | Result |
|-------|--------|
| `sensitivity_compare_debias_seeds.py --mode determinism` | Same `DOR_NOISE_DEBIAS_SEED` → **identical** `noise_bias` (**max abs diff = 0**) |

## Phase 2 — calendar AR(1) chain fix (2026-04-07)

**Bug:** `calibrate_noise_bias` advanced AR(1) noise **separately within each semi-monthly period** (`prev_noise = None` at each period), while **`run_downscale_day` / `run_downscale_loop`** use **one continuous** `prev_noise` across **all** calendar days (train + test). The debias field was therefore misaligned with the noise actually used at inference.

**Fix:** One pass over `i = 0 .. N_DAYS-1` in calendar order: update `prev_noise` every day; add to `sum_yb` / `sum_yf` only when `TRAIN_MASK[i]`. `run_manifest.json` records `"noise_debias_calibration": "calendar_ar1_chain"`.

### Post-fix calibration on UNC (not a full Table1 pipeline)

Same memmaps as § “Configuration”: `\\abe-cylo\...\test8_v2\Regridded_Iowa\`. `dump_noise_bias.py` + `audit_noise_bias.py` (land mask).

| Run | Env highlights | `noise_bias` GLOBAL land: mean | median | frac &lt; 1 | frac &gt; 1 | split_half (6 passes) |
|-----|----------------|-------------------------------|--------|------------|------------|-------------------------|
| Quick | `PR_USE_INTENSITY_RATIO=0`, `DOR_NOISE_DEBIAS_N_PASSES=2` | **0.99014** | 1.00000 | 0.498 | 0.354 | — |
| Validation parity | `PR_USE_INTENSITY_RATIO=1`, `PR_INTENSITY_BLEND=0.65`, `TEST8_SEED=42`, `DOR_NOISE_DEBIAS_N_PASSES=6` | **0.99009** | 0.99606 | 0.534 | 0.318 | **0.1957** (diagnostic) |

Artifacts (local `7-fix-pr-splotchiness/output/`, gitignored): `noise_bias_after_calendar_chain.npz`, `noise_bias_intensity_blend065_calchain.npz`, matching `noise_bias_audit_*.csv`.

**Interpretation:** The **global mean** of `noise_bias` is ~**0.99** on land — consistent with a debias tensor targeting long-run mean multiplier ≈ 1. **Split-half** remains modest at `N_PASSES=6` (known high estimator variance; see `WORKLOG.md`).

## Full pipeline after calendar-chain fix (`experiment_calchain_apr2026full`, 2026-04-09)

| Item | Value |
|------|--------|
| `PR_INTENSITY_OUT_TAG` | `calchain_apr2026full` |
| `OUT_DIR` | `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/experiment_calchain_apr2026full/` |
| Wall time | **~26.6 min** (CPU); `run_manifest.json` records `noise_debias_calibration: calendar_ar1_chain` |
| `DOR_PHASE2_SAVE_PRE_SCHAAKE_PR` | 1 → `Phase2_pre_schaake_pr_main_stochastic.npz` written |
| Log | `7-fix-pr-splotchiness/output/pipeline_calchain_apr2026full.log` |

### PR — pooled metrics (2006–2014) vs Apr 2026 `experiment_plan_debias`

| Metric | B (Apr 2026 debias, legacy chain) | **calchain_apr2026full** | Δ (new − old) |
|--------|-----------------------------------|-------------------------|----------------|
| Val_Ext99_Bias% | +0.7912 | **+0.7515** | **−0.04** (closer to 0) |
| Val_RMSE_pooled | 9.942 | **9.937** | −0.005 |
| Val_KGE | 0.0232 | **0.0232** | ~0 |
| Val_Lag1_Err | 0.0570 | **0.0570** | ~0 |
| Val_WDF_Sim% | 35.740 | **35.740** | 0 |
| Val_Bias | 0.1385 | **0.1378** | −0.0007 |

**Splotch** (`diagnose_splotchiness.py`, post-Schaake `Stochastic_V8_Hybrid_pr.npz`): **0.07833** vs **0.0786** (Apr B) — essentially unchanged; **mean_ratio** ~1.060 vs ~1.061.

**Pre- vs post-Schaake** (`compare_pre_post_schaake_pr.py`): **identical** splotch / mean_ratio to machine precision. On this run, the **validation-window time-mean PR field** (hence the time-mean ratio map) is **unchanged** by Schaake at float64; daily values still differ (e.g. mean abs diff ~4 mm on val days). So the time-mean splotch diagnostic **cannot** attribute artifacts to Schaake reordering — use diagnostics that use daily fields if testing that hypothesis.

## Attempt 3 — `DOR_NOISE_DEBIAS_N_PASSES=24` (`experiment_attempt3_pass24`, 2026-04-09)

Phase 2 **B1**: same calendar-chain debias as attempt 2 (`calchain_apr2026full`), but **24** averaged Monte Carlo passes for `noise_bias` (vs 6). `TEST8_SEED=42`, `PR_INTENSITY_BLEND=0.65`.

| Item | Value |
|------|--------|
| `OUT_DIR` | `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/experiment_attempt3_pass24/` |
| Wall time | **~33 min** (CPU) |
| Log | `7-fix-pr-splotchiness/output/pipeline_attempt3_pass24.log` |
| PR debias split-half (passes 0..11 vs 12..23) | **0.4600** (vs ~0.19 at N=6 — estimator more self-consistent) |

### PR — pooled metrics vs `experiment_calchain_apr2026full` (N=6)

| Metric | calchain (N=6) | **attempt3 (N=24)** | Δ |
|--------|----------------|----------------------|---|
| Val_Ext99_Bias% | +0.751 | **+0.613** | toward 0 |
| Val_RMSE_pooled | 9.937 | **9.928** | −0.009 |
| Val_KGE | 0.0232 | **0.0234** | +0.0002 |
| Val_Lag1_Err | 0.0570 | **0.0571** | +0.0001 |
| Val_WDF_Sim% | 35.740 | **35.742** | +0.002 |
| Val_Bias | 0.1378 | **0.1355** | −0.002 |

**Splotch** (`diagnose_splotchiness.py`): **0.07861** vs **0.07833** (N=6) — **slightly higher** (worse) spatial std of time-mean ratio; **mean_ratio** ~1.059.

**Interpretation:** Raising **N_PASSES** improves **Ext99** and **RMSE** vs N=6 with little change to WDF/Lag1, but the **time-mean splotch scalar does not improve** — it moves slightly the wrong way. Tradeoff: better tails / RMSE vs slightly worse time-mean spatial pattern by this diagnostic.

**Figure:** `7-fix-pr-splotchiness/figures/pr-splotch-side-by-side/dor_val_03_attempt3_pass24.png`

## Attempt 4 — deterministic floor (`experiment_attempt4_det_floor`, 2026-04-09)

**Hypothesis (plan):** Measure how much time-mean “splotch” comes from **multiplicative stochastic noise** vs **ratio / WDF / Schaake** by running the downscaler with **`noise_override=0`** (deterministic branch) while still writing the usual stochastic stack. **`DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`** (no empirical noise debias divide on wet PR).

| Item | Value |
|------|--------|
| `PR_INTENSITY_OUT_TAG` | `attempt4_det_floor` |
| Env | `TEST8_DETERMINISTIC=1`, `TEST8_STOCHASTIC=1` (default), `TEST8_SEED=42`, `PR_INTENSITY_BLEND=0.65` |
| `OUT_DIR` | `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/experiment_attempt4_det_floor/` |
| Wall time | **~42.7 min** (CPU); `run_manifest.json` records `STOCHASTIC` / `DETERMINISTIC`, `noise_debias_calibration`: null |
| Side-by-side figure | `7-fix-pr-splotchiness/figures/pr-splotch-side-by-side/dor_val_04_attempt4_det_floor.png` — **right panel** = `Deterministic_V8_Hybrid_pr.npz` (not `Stochastic_*`) |

**Qualitative description (plot vs other side-by-side attempts):** Among the four attempts in `figures/pr-splotch-side-by-side/`, this one shows the **largest visible change** from the baseline. Whether that is **better or worse overall** is **not** obvious from the map alone. **Central-domain** splotch-like patterns became **less pronounced**, which matches the original goal. **Southern** splotch-scale structure also became **less pronounced**; that was **not** desired for that region because those features are **present on GridMET** (they are plausibly “right” on the obs side, so damping them in the sim is ambiguous). The global **splotch_metric** cannot distinguish helpful smoothing in one region from unhelpful smoothing in another.

### PR — pooled metrics (2006–2014), same run

**Deterministic** (`V8_Table1_Pooled_Metrics_Deterministic.csv`) — matches the Attempt 4 figure:

| Metric | Value |
|--------|--------|
| Val_KGE | 0.0258 |
| Val_RMSE_pooled | 9.212 |
| Val_Bias | 0.075 |
| Val_Ext99_Bias% | −11.64 |
| Val_Lag1_Err | 0.0886 |
| Val_WDF_Obs% / Val_WDF_Sim% | 32.32 / 37.20 |

**Stochastic** (`V8_Table1_Pooled_Metrics_Stochastic.csv`) — same configuration, standard product path:

| Metric | Value |
|--------|--------|
| Val_KGE | 0.0240 |
| Val_RMSE_pooled | 9.915 |
| Val_Bias | 0.112 |
| Val_Ext99_Bias% | −0.23 |
| Val_Lag1_Err | 0.0553 |
| Val_WDF_Sim% | 35.75 |

**Interpretation:** Deterministic noise-off improves **RMSE** and **KGE** and lowers **domain bias**, but **hurts extremes** (Ext99), **lag-1** agreement, and **WDF** vs obs compared to the stochastic stack from the same job. Stochastic Table1 is **near** `experiment_plan_nodebias` (same debias-off regime); Attempts **1–3** in the figure series mostly used **debias on**, so **direct** splotch-number comparison to those panels mixes **regime** with **deterministic vs stochastic**.

### Splotch scalar (`diagnose_splotchiness.py`, 2006–2014)

| NPZ | splotch_metric | mean_ratio |
|-----|----------------|------------|
| `Deterministic_V8_Hybrid_pr.npz` | **0.0709** | ~1.034 |
| `Stochastic_V8_Hybrid_pr.npz` (same run) | **0.0710** | ~1.049 |

On this run, deterministic vs stochastic barely moves the **global** splotch number; the drop vs **~0.078** on debias-on attempts is largely **no debias calibration** here, not the deterministic branch alone.

## Attempt 5 — spatial ratio Gaussian smoothing (Phase 3 Approach A)

**Hypothesis (`FIX-PR-SPLOTCHINESS-PLAN.md`):** Pixel-scale **spatial_ratio** overfits training climatology; Gaussian smoothing of calibrated ratios (per semi-monthly period, land-only) should reduce time-mean splotch without destroying large-scale gradients.

### Implementation

| Item | Detail |
|------|--------|
| Code | `DOR_RATIO_SMOOTH_SIGMA` env (default **0**) in `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py` — applied in `StochasticSpatialDisaggregatorMultiplicative.calibrate()` **after** `spatial_ratio` / `spatial_ratio_ext` (PR intensity) and **before** `resid_cv` and WDF threshold; `run_manifest.json` key **`ratio_smooth_sigma`** |
| Sweep driver | `7-fix-pr-splotchiness/scripts/sweep_ratio_smooth.py` |
| Shared sweep settings | `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`, `TEST8_SEED=42`, `PR_INTENSITY_BLEND=0.65`, `TEST8_DETERMINISTIC=0`, `DOR_PHASE2_SAVE_PRE_SCHAAKE_PR=0` |

### Sweep σ ∈ {0, 5, 10, 15, 20}

**Aggregated metrics** (one row per σ): `7-fix-pr-splotchiness/output/attempt5_ratio_smooth_sweep.csv` — **`splotch_metric`**, **Table1 pr** (Ext99, RMSE, KGE, Lag1, WDF Sim), **wind Ext99**, paths.

**Run log:** `7-fix-pr-splotchiness/output/attempt5_sweep_run.log`

**Side-by-side maps** (stochastic PR, same style as earlier attempts): `figures/pr-splotch-side-by-side/dor_val_05_attempt5_ratio_smooth_sigma{00,05,10,15,20}.png` for each σ.

**Status:** Full sweep **started 2026-04-09** on UNC memmaps (same layout as Attempt 4). **~40+ min × 5 runs** CPU — when the CSV is complete, fill the summary table below from its rows and pick σ against plan §5.7 gates (splotch below ~0.071, target toward 0.060, Ext99 ±1%, no large RMSE/Lag1/WDF regression).

| σ | splotch_metric | pr Ext99 Bias% | pr RMSE | pr WDF Sim% | Notes |
|---|----------------|----------------|---------|-------------|--------|
| *Pending* | *see CSV* | *see CSV* | *see CSV* | *see CSV* | Refresh after sweep finishes |

## Phase 2 — supporting scripts

| Artifact / script | Purpose |
|-------------------|---------|
| `audit_noise_bias.py` | Land-mask or global stats on `noise_bias` from `dump_noise_bias.py` — fraction **< 1** vs **> 1** per period |
| `sweep_debias_passes.py` | Sweep `DOR_NOISE_DEBIAS_N_PASSES` → `split_half_corr` + timing (needs memmaps) |
| `compare_pre_post_schaake_pr.py` | Same splotch scalar on pre- vs post-Schaake PR (needs `Phase2_pre_schaake_pr_main_stochastic.npz`) |
| `DOR_PHASE2_SAVE_PRE_SCHAAKE_PR=1` | Main pipeline writes `Phase2_pre_schaake_pr_main_stochastic.npz` before multivariate Schaake |

**Still optional on UNC:** `sweep_debias_passes` for **N=48** (or full **nodebias** run on current code) for a strict A/B; Apr 2026 A/B mixed pre-calendar-chain debias.

## Final conclusion (2026-04-09)

**Task closed.** After 5 attempts at fixing pr splotchiness and diagnostic decomposition across pipeline stages and GCMs, determined that the splotches originate from the GCM's coarse spatial precipitation pattern, not from the downscaler. The GCM cells' relative wetness doesn't match GridMET. This is not fixable in the spatial downscaler.

- Set `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` (noise debias off) going forward.
- WDF fix (`8-WDF-overprediction-fix/`) and wind improvement (`10-improve-wind/`) are no longer blocked by this task.
