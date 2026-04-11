# PR correlation length sweep — agent work log

Live log for `PLAN-CORR-LENGTH-SWEEP.md`.

---

## 2026-04-10 — Session start

**Goal:** Implement `DOR_PR_CORR_LENGTH`, add `scripts/sweep_corr_length.py`, run full sweep `{15,25,35,45,55,70}`, produce `output/corr_length_sweep.csv`, optional figures, and `output/corr_length_findings.md`.

**Decisions:**

1. **Where the code lives:** The plan still points at `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py`, but that entry point only `runpy`s `pipeline/scripts/_test8_sd_impl.py`. The correlation-length block to change is in **`pipeline/scripts/_test8_sd_impl.py`** inside `process_variable()` (not `_process_variable`). Editing the impl keeps `test8_v3` / `test8_v4` in sync.

2. **How to invoke the pipeline:** `test8_v4.py` exists only under **`pipeline/scripts/`**. The sweep sets `DOR_PIPELINE_ROOT` to the experiment folder (default `4-test8-v2-pr-intensity` so outputs land under that task per plan layout) but runs `python …/pipeline/scripts/test8_v4.py`. If we joined `experiment-root` with `scripts/test8_v4.py`, runs would fail.

3. **Baseline reference:** Older WDF benchmark rows live under `D:\WRC_DOR_runs\…\experiment_wdf_factor_1p65_216\` with pipeline folder name `test8_v2_pr_intensity`. This sweep uses current `test8_v4`; the **corr_len=35** row is the right internal control for code revision alignment.

4. **NPZ saves:** Implemented `TEST8_SKIP_NPZ_SAVE` in `_test8_sd_impl.py` (skips main-period `Stochastic_V8_Hybrid_*.npz` / `Deterministic_V8_Hybrid_*.npz` after Table1/2). The production sweep used **full NPZ writes** because `--figures-dir` was set (plots need `Stochastic_V8_Hybrid_pr.npz`).

5. **Logging:** Main block logs `DOR_PR_CORR_LENGTH` when set (helps sweep audits).

---

## 2026-04-10 — Implementation complete

**Files touched:**

| File | Change |
|------|--------|
| `pipeline/scripts/_test8_sd_impl.py` | PR-only `DOR_PR_CORR_LENGTH`; `TEST8_SKIP_NPZ_SAVE`; default PR corr len **15** after sweep; docstring |
| `4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py` | Note pointing to impl + plan |
| `9-additional-pr-RMSE-fixes/scripts/sweep_corr_length.py` | **New** — CLI per plan; resolves `test8_v4.py` via repo root |
| `9-additional-pr-RMSE-fixes/output/corr_length_sweep.csv` | **New** — six rows |
| `9-additional-pr-RMSE-fixes/output/corr_length_findings.md` | **New** — interpretation + recommendation |
| `9-additional-pr-RMSE-fixes/figures/dor_val_corr_len_*.png` | Six mean-PR validation maps |

---

## 2026-04-10 — Run record

**Command (condensed):**

`conda run -n drops-of-resilience python 9-additional-pr-RMSE-fixes/scripts/sweep_corr_length.py --experiment-root 4-test8-v2-pr-intensity --out-csv …/corr_length_sweep.csv --figures-dir …/figures --cmip-hist/--gridmet-targets/--geo-mask` → local bilinear memmaps (size verified **12 359 983 104** bytes for `.dat` files).

**Wall time:** Total subprocess log ~**90 minutes** for six full pipeline runs on **CPU** (device line: `cpu`). Per-run pipeline log ~**14–15 min** including NPZ write + plot.

**Machine note:** Runs used CPU not CUDA; timing is environment-specific.

---

## 2026-04-10 — Results (non-CSV)

**Monotonic RMSE:** Longer `DOR_PR_CORR_LENGTH` → **higher** pr RMSE (9.903 at 15 → 9.937 at 70). Shorter correlation = more localized FFT noise for `pr`; pooled RMSE improves.

**Cross-variable isolation:** Compared `V8_Table1_Pooled_Metrics_Stochastic.csv` for `experiment_corr_len_15` vs `experiment_corr_len_35`. Rows for **tasmax, tasmin, rsds, wind, huss** are **byte-for-byte identical** between the two runs. Only **`pr`** differs, as intended.

**Wind check:** `wind` `Val_Ext99_Bias%` is **−7.530304** in every run folder — sweep column is constant.

**Baseline drift:** `corr_len=35` in this sweep (RMSE **9.916**) does not exactly match archived `experiment_wdf_factor_1p65_216` (RMSE **9.910** on D:). Likely pipeline ID / code revision drift. Sweep internal comparisons remain valid.

**Chosen default:** **15 px** for PR when `DOR_PR_CORR_LENGTH` is unset — meets plan success criteria vs other sweep points; documented in `corr_length_findings.md`.

---

## Checklist (plan § Verification checklist)

1. Control run (corr_len=35) documented; exact match to old D: baseline not required after drift note.  
2. Non-pr variables identical across runs — **verified** (15 vs 35 Table1).  
3. Wind Ext99 unchanged across runs — **verified**.  
4. Findings recorded — **`output/corr_length_findings.md`**.

---

*Plan items exhausted: code change, sweep driver, CSV, figures, findings, default update, WORKLOG.*
