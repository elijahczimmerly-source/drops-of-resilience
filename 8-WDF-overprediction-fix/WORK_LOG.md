# WDF overprediction fix — agent work log

Live log for autonomous execution of `FIX-WDF-OVERPREDICTION-PLAN.md`. Updated as steps complete.

---

## 2026-04-09 — Start

**Goal:** Phase 1 — sweep `PR_WDF_THRESHOLD_FACTOR` ∈ {1.15, 1.20, 1.25, 1.30, 1.35, 1.40} with fixed env (debias off, seed 42, blend 0.65), collect metrics + side-by-side pr mean maps. Phase 2 only if no row meets success criteria.

**Decisions:**

- **Data paths:** Local `4-test8-v2-pr-intensity/data` has no `.dat` memmaps in this workspace; runs use UNC inputs under `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\Data_Regrided_Gridmet\` (same layout as prior `experiment_attempt5_sigma0` / benchmark runs).
- **`PR_WDF_THRESHOLD_FACTOR`:** Implemented as `float(os.environ.get("PR_WDF_THRESHOLD_FACTOR", "1.15"))` at import time (plan’s only required code change for Phase 1), and recorded in `run_manifest.json` for traceability.
- **Output tags:** `PR_INTENSITY_OUT_TAG=wdf_factor_1p15` … `wdf_factor_1p40` via `1pXX` hundredths encoding to avoid ambiguous folder names.
- **Plots:** Reuse `7-fix-pr-splotchiness/scripts/plot_validation_agg_mean_pr.py` (same GridMET | DOR style as product-comparison / splotch figures).

**Status:** Implementing scripts + pipeline patch; then sequential full pipeline runs (expect ~20–25 min each × 6).

---

## 2026-04-09 — Phase 1 complete

**Script:** `scripts/sweep_wdf_threshold.py`  
**CSV:** `output/wdf_threshold_sweep.csv`  
**Figures:** `figures/dor_val_wdf_wdf_factor_1p15.png` … `1p40.png` (6 panels)

**Runtime:** ~19 min first factor, ~10 min × 5 subsequent (Schaake/cache effects); ~51 min for the batch of 5.

**Grid / data note:** Runs use UNC memmaps under `Spatial_Downscaling\Data_Regrided_Gridmet\` (**120×192**, 23040 cells). Published benchmark numbers in `dor-info.md` / `6-product-comparison` use a **216×192** Iowa crop elsewhere — so absolute RMSE / Ext99 here are **not** numerically comparable to the +0.13% Ext99 / 9.91 RMSE benchmark; only **relative** comparisons across this sweep are valid.

**Findings:**

- Raising `PR_WDF_THRESHOLD_FACTOR` monotonically **lowers** `Val_WDF_Sim%` (more aggressive censoring), as intended.
- **`PR_WDF_THRESHOLD_FACTOR = 1.30`:** `Val_WDF_Sim%` = **32.69%** vs `Val_WDF_Obs%` = **32.68%** (~0.01pp gap) — essentially nails wet-day frequency on this stack.
- **1.35** also sits within the plan’s ±1pp band (Sim 31.95 vs Obs 32.68 → 0.73pp low).
- **Ext99 Bias%** is **unchanged** at **4.207545** for every factor — wet-day thresholding is acting on light rain; pooled 99th percentile is insensitive in practice.
- **Wind `Val_Ext99_Bias%`** is **−8.808012** for every run (identical) — confirms no cross-talk from PR WDF tuning.
- **Lag1 Err** improves slightly as factor increases (0.020 → 0.013) — fewer marginal wet days → slightly different temporal structure.

**Plan success criteria:** WDF target met at **1.30** (and nearby). **Ext99 ±1%** criterion **not** met for any factor (stuck at +4.2%). Per plan, proceed to Phase 2.

---

## 2026-04-09 — Phase 2 (noise-aware calibration)

**Implementation:** In `test8_v2_pr_intensity.py`:

- `DOR_PR_WDF_NOISE_AWARE_CALIBRATION=1` enables MC calibration of `monthly_threshold` from `y_base * noise_mult` with **independent** `generate_spatial_noise` draws per (MC replicate × training day), matching the plan’s pseudo-code structure.
- `DOR_WDF_NOISE_AWARE_N_SAMPLES` (default **30** in code; run used **15** for faster iteration).
- `_effective_pr_wdf_factor()` returns **1.0** when noise-aware is on (no extra `PR_WDF_THRESHOLD_FACTOR` multiply at inference), else `PR_WDF_THRESHOLD_FACTOR`.

**Run:** `experiment_wdf_noise_aware_n15` (~13 min).

**Results:** **WDF degraded:** `Val_WDF_Sim%` = **38.04%** vs Obs **32.68%** (+5.4pp vs Phase 1 baseline 35% at 1.15). Ext99 moved slightly (4.21 → 3.61%) but not to the ±1% band.

**Interpretation (why Phase 2 failed):**

- MC calibration uses **i.i.d.** spatial noise each step; **inference** uses **AR(1)** temporal noise for `noise_mult`. Marginals differ — thresholds calibrated on the wrong distribution.
- Independent replication × day inflates the synthetic pool variance vs AR(1)-chained days; quantile thresholds can land **too low** after sorting, so at inference (with AR(1)) too many values stay above threshold → **too many wet days**.

**Figure:** `figures/dor_val_wdf_noise_aware_n15.png`

**Conclusion:** Keep Phase 2 code behind env flag for future **AR(1)-matched** calibration experiments. The **120×192** Phase 1 optimum (~1.30) is **not** portable to the benchmark grid — see **2026-04-10** below.

---

## 2026-04-10 — Plan “Next Steps” (correct 216×192 data)

Per updated **`FIX-WDF-OVERPREDICTION-PLAN.md`** (wrong-path correction + Regridded_Iowa instructions):

1. **`sweep_wdf_threshold.py` fixed:** Removed silent defaults to `Data_Regrided_Gridmet`. Added **`--regridded-iowa-server`** (canonical UNC tree) and **`--tag-suffix`** (e.g. `_216`) so sweeps do not clobber other grids.

2. **Confirmation run** `PR_WDF_THRESHOLD_FACTOR=1.30`, `PR_INTENSITY_OUT_TAG=wdf_factor_1p30_216x192`, paths from plan → **Grid 216×192** ✓. **WDF still off:** Sim **34.59%** vs Obs **32.32%** (+2.27pp). So **1.30 is not** the answer on benchmark memmaps.

3. **Follow-up sweep** on Regridded_Iowa (`--tag-suffix _216`, factors 1.40–1.55): **`wdf_threshold_sweep_216x192.csv`**
   - **1.50:** WDF Sim **33.23%** vs Obs **32.32%** → **+0.92pp** (within ±1pp). Ext99 **−0.05%**, RMSE **9.909**, Lag1 **~0.055**, wind Ext99 **−7.38%** — **meets plan success table on correct data.**

4. **Default updated:** `PR_WDF_THRESHOLD_FACTOR` default in `test8_v2_pr_intensity.py` first **1.50** then **1.65** after extended sweep 1.55–1.70 on **D:** (see `output/wdf_threshold_sweep_216_1p55plus.csv`). **1.65** matches Obs WDF to ~0.02pp; **1.70** goes slightly dry.

5. **Disk failure:** Run **1.55** ended with **`No space left on device`** during NPZ save; some experiment folders may lack full `Stochastic_*.npz`. **Free disk** before re-running sweeps or generating side-by-side figures that need NPZ.

6. **Docs:** `output/wdf_216x192_confirmation.md` — full metrics table and interpretation.

---

## Artifacts checklist

| Artifact | Path |
|----------|------|
| Phase 1 CSV (120 grid, relative only) | `output/wdf_threshold_sweep.csv` |
| Phase 1 criteria note | `output/phase1_success_criteria.md` |
| Phase 2 row | `output/wdf_phase2_noise_aware_n15.csv` |
| **216×192 sweep + summary** | `output/wdf_threshold_sweep_216x192.csv`, `output/wdf_216x192_confirmation.md` |
| Sweep + plot driver | `scripts/sweep_wdf_threshold.py` |
| Pipeline `PR_WDF_THRESHOLD_FACTOR` (default **1.65**) | `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py` |

---
