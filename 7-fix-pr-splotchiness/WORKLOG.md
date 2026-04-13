# PR splotchiness / multiplicative noise debias — decision & work log

This file records **what was tried**, **why choices were made**, and **how conclusions follow**. Numeric outcomes live in [`VALIDATION_RESULTS.md`](VALIDATION_RESULTS.md). Methodology lives in [`FIX-PR-SPLOTCHINESS-PLAN.md`](FIX-PR-SPLOTCHINESS-PLAN.md).

---

## 1. Problem statement (from plan)

Time-mean PR maps showed ~35 px “splotches” (areas of elevated/depressed precipitation visible in time-aggregated DOR maps but not in GridMET).

**Note on `splotch_metric`:** The scalar metric used throughout this investigation (spatial std of time-mean DOR/OBS ratio) was an unreliable proxy. It did not correspond to the visual splotchiness seen in the plots and could move in the wrong direction (e.g., “improve” when plots looked the same, or worsen when a fix was visually helpful in one region). Do not treat `splotch_metric` values in this file or `VALIDATION_RESULTS.md` as meaningful measures of the actual problem.

Root causes identified in the plan: asymmetric multiplicative noise clip, WDF censoring, AR(1) persistence, and FFT correlation length — together producing **non–zero-mean** effective multipliers per pixel/period.

**Chosen fix (plan):** After `calibrate()`, estimate per-pixel/period **mean effective multiplier** over training days using the **same** noise → clip → WDF chain as inference, then **divide** wet values at inference by that mean so long-run mean multiplier → 1.

**Why not alternatives first:** Log-space noise, symmetric clip-only, or lowering `NOISE_FACTOR_MULTIPLICATIVE` were deferred because they change tail behavior or trade extremes against splotches; the plan prioritized a **minimal** change that targets the net bias without redesigning the noise model.

---

## 2. Core implementation (`test8_v2_pr_intensity.py`)

### 2.1 Where the fix lives

- **Class:** `StochasticSpatialDisaggregatorMultiplicative` only (pr + wind). Additive variables already have approximately zero-mean additive noise; no clip asymmetry in the same form.

### 2.2 `calibrate_noise_bias()`

- **Accumulation (updated 2026-04-07):** Sum `y_final` and `y_base` over **training** days only, but drive AR(1) noise **in calendar order for every day** (train + test), matching `run_downscale_loop`. Earlier versions summed within each period with a **fresh** `prev_noise` per period, which **did not** match inference.
- **Legacy note:** For each semi-monthly period, training days were previously iterated with AR(1) noise **only within** that period (incorrect chain).
- **Bias field:** `noise_bias[p] = mean over passes of (clip(sum_yf/sum_yb))` per pixel, with the same clip as the plan (`[0.05, 20]` on the ratio field after the inner clip/WDF).

### 2.3 Multi-pass averaging (`DOR_NOISE_DEBIAS_N_PASSES`, default **6**)

**Tried:** Single-pass debias estimate. **Issue:** Monte Carlo noise between **different** `DOR_NOISE_DEBIAS_SEED` values produced **low** land-pixel correlation between two full `noise_bias` tensors (e.g. ~0.05–0.79 depending on passes), meaning the **point estimate** was seed-sensitive.

**Decision:** Average **N** independent debias simulations with seeds `debias_seed + k * 1_000_003`. **Rationale:** Reduces variance of the bias estimator toward a stable spatial field without changing the physics of inference (still one divide per pixel/period at run time).

**Tradeoff:** Calibration time scales ~linearly with N; 6 was a practical default for development; higher N may be needed if product metrics require stabler fields.

### 2.4 Split-half diagnostic (`_debias_split_half_corr`)

**Tried:** Use “two different seeds must correlate > 0.99” as the Step 5 gate. **Issue:** Even **adjacent** seeds gave poor correlation at moderate N — the estimator variance between **independent** runs is high.

**Decision:** Log **split-half correlation** (mean of first ⌊N/2⌋ pass tensors vs second half). **Rationale:** Tests **internal** consistency of the MC estimator on one calibration; does not require two separate jobs to agree to high precision.

**Bug fixed:** Land mask for correlation used `(self.mask == 1)[None,:,:]` but `self.mask` is **1D** `(H*W,)`. Replaced with `self.mask.reshape(1,H,W)` for broadcast. Without this, split-half logging crashed.

### 2.5 Inference

- Apply divide **after** PR WDF/cap, only where `y_final > 0` (zeros unchanged).
- **RNG:** Save/restore NumPy, Python, torch, and CUDA RNG state around debias calibration so **`TEST8_SEED` inference sequence is unchanged** vs a no-debias code path.

### 2.6 Flags and reproducibility

- `DOR_MULTIPLICATIVE_NOISE_DEBIAS` — default **on**; set **0** for A/B parity with pre-debias behavior.
- `DOR_NOISE_DEBIAS_SEED` — optional; else derived from `TEST8_SEED` and variable name (stable hash, not Python `hash()`).
- Manifest records debias-related env for traceability.

---

## 3. Data paths (UNC, no local 12 GB copies)

**Tried:** `mklink` file symlinks from repo `data/` to UNC memmaps. **Failed:** insufficient privilege on the machine.

**Decision:** Optional env **absolute paths**: `DOR_TEST8_CMIP6_HIST_DAT`, `DOR_TEST8_GRIDMET_TARGETS_DAT`, `DOR_TEST8_GEO_MASK_NPY`, `DOR_TEST8_GEO_STATIC_NPY` so `BASE_DIR/data/` is not required when server layout splits **cmip6** under `MPI/mv_otbc/` and **gridmet/mask** under `Regridded_Iowa/`.

**Why:** ~12 GB × 2 files cannot be duplicated locally; symlinks are the usual fix but were blocked; explicit paths are explicit and auditable.

---

## 4. Step 5 tooling evolution

| Tried | Outcome | Decision |
|-------|---------|----------|
| Two-seed land correlation, threshold 0.99 | Poor at 6–48 passes | Not used as primary gate; documented as high-variance |
| Split-half only, threshold 0.99 | Often &lt; 0.99 at N=6–32 | Kept as **logged diagnostic**, not hard fail for shipping |
| **Determinism:** two dumps, **same** seed | **max abs diff = 0** | **`sensitivity_compare_debias_seeds.py --mode determinism`** is the **primary** Step 5 pass — proves reproducibility |

**Rationale:** The plan’s “two seeds must agree” is **too strict** for a finite-MC bias estimate without very large N; reproducibility under fixed seed **is** the engineering requirement for a deterministic pipeline.

---

## 5. Scripts and repo layout

- **`diagnose_splotchiness.py`:** Step 0/4 splotch scalar + optional seasonal PNGs + `--debiased-npz` compare. **Fix:** `TEST_MASK` as `np.asarray(..., bool)` — pandas vs numpy inconsistency broke `.values`.
- **`step4_validation.py`:** Orchestrates diagnose + `validate_fix.py` when both run dirs exist.
- **`dump_noise_bias.py`:** Calibration-only artifact for debugging; accepts same path overrides as main; saves `n_passes` in the .npz.
- **`audit_noise_bias.py` / `sweep_debias_passes.py` / `compare_pre_post_schaake_pr.py`:** Phase 2 diagnostics (see §9).
- **`test8_v2_debiased.py`:** Thin launcher (plan filename); behavior = main script + debias on.
- **`VALIDATION_RESULTS.md`:** Holds **numbers only** so the plan stays methodological.
- **`WORKLOG.md` (this file):** Narrative + rationale; **not** a duplicate of raw CSVs.

---

## 6. Full pipeline validation (2026-04-08)

**Runs:**

- **A:** `experiment_plan_nodebias` — `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`
- **B:** `experiment_plan_debias` — `=1`

Same `TEST8_SEED=42`, `PR_INTENSITY_BLEND=0.65`, UNC memmaps, **216×192** grid (server `Regridded_Iowa`, not the older 84×96 note in some docs).

**Outcome (see VALIDATION_RESULTS.md):**

- **Splotch metric** ~flat (did **not** improve).
- **pr Ext99 Bias%** moved from ~**−0.05%** to **+0.79%** (worse vs near-zero target).
- **RMSE** slightly worse; **WDF** essentially unchanged.

**Interpretation recorded:**

- Debiasing operates **before** Schaake; saved NPZ and metrics are **after** Schaake — spatial mean patterns in sim can still differ from obs for reasons unrelated to the raw multiplicative bias.
- Empirical `noise_bias` may be **< 1** or **> 1** in a way that, combined with Schaake and validation masking, **does not** monotonically improve the chosen splotch scalar or Ext99.
- **Not ruled out:** Higher `DOR_NOISE_DEBIAS_N_PASSES`, debias applied at a different stage, or a different scalar than mean ratio for “splotch.”

**Decision (Apr 2026):** Record debiased run B numbers for traceability, but **do not** assume they are the long-term WDF baseline until Phase 2 stabilizes pr — see `FIX-PR-SPLOTCHINESS-PLAN.md` “Relationship to WDF Fix” and `VALIDATION_RESULTS.md` “Next steps.”

---

## 7. Items explicitly not done here

- Retuning `PR_WDF_THRESHOLD_FACTOR` (blocked until splotch/debias story stabilizes per plan).
- Changing Schaake order or debias-after-Schaake (would be a larger experiment).
- GPU vs CPU: validation used **CPU** torch; runtime differs, determinism with same seed should still hold for the same build.

---

## 8. Quick reference — files to read next

| Question | Where |
|----------|--------|
| What numbers did we get? | `VALIDATION_RESULTS.md` |
| How was the fix supposed to work? | `FIX-PR-SPLOTCHINESS-PLAN.md` |
| What did we change in code? | `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py` |
| Raw CSV outputs | `output/step4_validation_apr2026/` |

---

## 9. Phase 2 — tooling + calendar-chain debias fix (2026-04-07)

### 9.1 Diagnostics scripts

- **`scripts/audit_noise_bias.py`** — summarizes `noise_bias` .npz: per-period and global `frac_lt_1`, `frac_gt_1`, moments; optional `--mask` for land-only.
- **`scripts/sweep_debias_passes.py`** — loops `DOR_NOISE_DEBIAS_N_PASSES`, subprocesses `dump_noise_bias.py`, records `split_half_corr` and `n_passes` (requires same memmaps as calibration).
- **`scripts/compare_pre_post_schaake_pr.py`** — pairs `Phase2_pre_schaake_pr_main_stochastic.npz` with `Stochastic_V8_Hybrid_pr.npz` for the same splotch diagnostic as `diagnose_splotchiness.py`.
- **`dump_noise_bias.py`** — saves **`n_passes`** in the .npz for traceability.
- **`test8_v2_pr_intensity.py`** — env **`DOR_PHASE2_SAVE_PRE_SCHAAKE_PR`**: writes pre-Schaake PR stack before `apply_schaake_shuffle_stack`; recorded in `run_manifest.json`.

### 9.2 Calendar AR(1) alignment (`calibrate_noise_bias`)

**Issue:** Debias MC previously reset **`prev_noise`** at the start of **each** semi-monthly period while **inference** carries AR(1) noise **continuously** across the full calendar. The estimated `noise_bias` field could not match the effective multipliers used in `downscale_day`.

**Change:** Single chronological loop over all days; advance `prev_noise` on every day; accumulate `sum_yb`/`sum_yf` only on training days. Manifest key: **`noise_debias_calibration`: `calendar_ar1_chain`**.

**UNC check:** `dump_noise_bias.py` on `Regridded_Iowa` with **`PR_INTENSITY_BLEND=0.65`**, **`DOR_NOISE_DEBIAS_N_PASSES=6`**, **`TEST8_SEED=42`** completed successfully; **`audit_noise_bias`** global land mean **`noise_bias` ≈ 0.990** (see `VALIDATION_RESULTS.md`).

**Full pipeline (2026-04-09):** `PR_INTENSITY_OUT_TAG=calchain_apr2026full`, **`DOR_PHASE2_SAVE_PRE_SCHAAKE_PR=1`**, ~26.6 min on CPU. **Table1 pr:** Ext99 bias **+0.75%** vs **+0.79%** on Apr 2026 `experiment_plan_debias` (legacy debias chain); RMSE slightly lower; **splotch** ~**0.0783** vs **0.0786**. Empirically, **Schaake did not change** the validation-window **time-mean** PR field (splotch pre/post identical); daily fields still differ — time-mean splotch cannot isolate Schaake effects.

**Attempt 3 (same day):** `PR_INTENSITY_OUT_TAG=attempt3_pass24`, **`DOR_NOISE_DEBIAS_N_PASSES=24`**, ~33 min CPU. **Table1 pr:** Ext99 **+0.61%**, RMSE **9.928** (better than N=6 calchain); **splotch_metric** **0.07861** (slightly **worse** than 0.07833 at N=6). PR debias **split-half 0.46** vs ~0.19 at N=6. Conclusion: more MC passes stabilize the bias estimator and help tails/system metrics but do **not** improve the time-mean splotch scalar — possible tradeoff to document when choosing N for production.

---

## 10. Attempt 5 — Gaussian spatial smoothing of `spatial_ratio` (2026-04-09)

**Hypothesis:** After Attempt 4 showed splotch is dominated by calibrated **ratio** mismatch (not multiplicative noise), Phase 3 Approach A applies **`gaussian_filter`** to `spatial_ratio` (and PR `spatial_ratio_ext` when intensity is on) per period, controlled by **`DOR_RATIO_SMOOTH_SIGMA`** (pixels), before **`resid_cv`** / WDF calibration so `sim_base` stays consistent.

**What ran:** `sweep_ratio_smooth.py` loops σ ∈ {0, 5, 10, 15, 20} with **`DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`**, writes **`output/attempt5_ratio_smooth_sweep.csv`** and **`dor_val_05_attempt5_ratio_smooth_sigma*.png`** (under `--figures-dir`). **Next:** Pick σ from plan success criteria; then unblock WDF work (`8-WDF-overprediction-fix/`) on the chosen baseline.

---

---

## 11. Final diagnosis — splotches originate from GCM (2026-04-09)

After Attempt 5 (ratio smoothing) also failed to improve the splotch metric, generated pipeline-stage diagnostic plots comparing GridMET vs GCM input vs DOR output at each stage, and compared across GCMs. The splotch patterns visible in time-aggregated DOR maps are already present in the GCM's coarse precipitation field before the downscaler runs. The GCM cells' relative wetness doesn't match GridMET. The downscaler's spatial_ratio faithfully transmits this pattern.

**Conclusion:** The pr splotches are a GCM limitation, not a downscaler artifact. Not fixable in the spatial downscaler. Task closed. `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0` (off) going forward.

---

## 12. Interpretation — aggregation window and “the mystery” (2026)

**What happened:** Validation used **side-by-side time-mean** maps (DOR vs GridMET) for **2006–2014** (the short held-out window). Those maps showed **large dark wet patches** in the interior that were **not** visible in GridMET — alarming for pipeline quality.

**Resolution:** The same style of plot for the **full historical** period on the standard memmaps (**1981–2014**, sometimes described informally as ~1982–2014) looks **much more like GridMET**; the dramatic splotches seen on the **short** window are **not** representative of long-run time-aggregate behavior. A **short** average emphasizes interannual noise and validation-era mismatch; a **long** climatological mean answers a different question.

**Takeaway:** Always **match the plotted years to the question**. For “how does the product look in climatological mean?”, use a **long** historical span. For “how does the test era look?”, a short window is appropriate but **easy to over-read** in isolation.

**Plotting:** Canonical **mean-map** styling (2–98% **per panel**, two colorbars) is documented in [`PLOTTING.md`](PLOTTING.md) and [`../dor-info.md`](../dor-info.md). Older drafts of [`PLAN-REDO-PERIOD-PLOTS.md`](PLAN-REDO-PERIOD-PLOTS.md) required a single global color scale; **`plot_period_comparison.py` now follows the pipeline default** instead.

*Last updated: 2026-04-12 (§12: aggregation window + plotting canon).*
