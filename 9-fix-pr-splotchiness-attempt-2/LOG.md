# Work log — PR splotchiness attempt 2

This file records **what changed**, **why**, and **non-CSV outcomes** (plot reviews, smoke-test verdicts, benchmark narrative). CSV outputs stay alongside this folder or under `pipeline/output/`.

---

## 2026-04-17 — Attempt 2 closed (negative)

**User verdict:** Multipanel **pr** plots for the blend **0.62** + **`DOR_RATIO_SMOOTH_SIGMA=1.0`** experiment looked **the same as test8 v4** — no useful texture change.

**Repo actions:** Entry script is [`test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py); pipeline id **`test8_pr_tex_att2_b062_rs1`** for reruns; Attempt 2 **removed** from default `config`, `plot_comparison_driver`, batch benchmarks, and climate pipeline lists. Saved figure trees + archived benchmark CSV under this folder ([`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md), [`plots_4km_pr_attempt2_blend062_ratio_smooth1/`](./plots_4km_pr_attempt2_blend062_ratio_smooth1/)). Investigation CSVs here list only **v2 / v3 / v4** DOR products.

---

## 2026-04-13 — Workspace move

**Action:** Moved all investigation artifacts from `6-product-comparison/docs/pr_texture_loca2_dor/` to `9-fix-pr-splotchiness-attempt-2/` at repo root.

**Rationale:** Centralize background, plans, CSVs, and tuning notes in a dedicated work area; keep `6-product-comparison/docs/` from growing ad-hoc.

**Code:** `pr_texture_investigation.py` now writes to this folder by default (`DOR_PR_SPLOTCH_WORKDIR` overrides).

**Follow-up:** Relative links in `PLAN.md` and `FINDINGS.md` were updated to `../6-product-comparison/scripts/...` and `../pipeline/scripts/...`. Stub `6-product-comparison/docs/pr_texture_loca2_dor/README.md` points here.

---

## 2026-04-13 — Part B implementation (Attempt 2, `test8_pr_tex_att2_b062_rs1`)

**Goal:** Ship [`PLAN.md`](./PLAN.md) Part B: new pipeline id, distinct output dir, product-comparison wiring, documentation.

**Code decisions (retrospective)**

- **`_test8_sd_impl.py`:** `_pipeline_id()` includes **`test8_pr_tex_att2_b062_rs1`**; WDF default **1.65** like v4/v2; v3 uses **1.15**.
- **Entry script** [`test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py): `PR_INTENSITY_BLEND=0.62`, `DOR_RATIO_SMOOTH_SIGMA=1.0`, `PR_INTENSITY_OUT_TAG=blend0p62_ratio_smooth1p0` → `OUT_DIR` under `pipeline/output/test8_pr_tex_att2_b062_rs1/experiment_blend0p62_ratio_smooth1p0/` (see [`ARCHIVED_PIPELINE_OUTPUT_PATHS.md`](./ARCHIVED_PIPELINE_OUTPUT_PATHS.md)).
- **Plot/batch/climate:** Attempt 2 was wired only until the negative result; default lists returned to **v2 / v3 / v4**.

**Tests run in this session**

- `python -m py_compile` on edited pipeline and 6-product-comparison modules — **pass**.
- Initial session did not run a full downscale until NPZ inputs were ready.

---

## 2026-04-16 / 2026-04-17 — Full plan execution (pipeline + benchmarks + plots + E2E)

**Entry script fix:** First run used `PR_USE_INTENSITY_RATIO` unset → parity mode and wrong `OUT_DIR`. Script now sets **`PR_USE_INTENSITY_RATIO=1`** and **`setdefault`** memmap paths under `D:\drops-resilience-data\WRC_DOR_cache\...\mv_otbc` when present so `pipeline/data/` is not required.

**Downscale:** `python pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py` with `DOR_LOCAL_WRC_CACHE` — completed in **~15.9 min**, wrote `Stochastic_V8_Hybrid_*.npz` under `pipeline/output/test8_pr_tex_att2_b062_rs1/experiment_blend0p62_ratio_smooth1p0/`.

**Product-comparison:** Ran `batch_benchmark_pipelines.py`, `pr_texture_investigation.py` (~10 min LOCA2 load), `plot_comparison_driver.py --all` (~90 min), `run_climate_signal_stages.py` (~65 min), `multivariate_dor_signal.py`, `run_e2e_suite.py` (~4 h including repeat plots/diagnostics). All exited **0**. Outputs: standard `6-product-comparison/output/*`; copies under this folder include **`benchmark_summary_archived_pr_blend062_ratio_sigma1.csv`**, `plot_driver_run.log`, `multivariate_dor_signal.log`. **`e2e_suite_run.log`** and **`climate_signal_stages.log`** are short UTF-8 stubs (original UTF-16 console captures were replaced when normalizing pipeline id strings).

**Results (high level):** Domain–time mean pr **2.488** (Attempt 2) vs **2.501** (v4) vs **2.396** (GridMET). Validation pr **KGE 0.0232** (Attempt 2) vs LOCA2 **0.0227**. Full-period map **r** vs GridMET in the same ballpark as v4 (Attempt 2 ≈ v4). **S4_dor** climate-signal rows for Attempt 2 skipped until future NPZs exist (`TEST8_MAIN_PERIOD_ONLY=1`).

**Human step (superseded by 2026-04-17):** Attempt 2 plots judged same as v4; see new log section above.

---

*(Append new dated sections below.)*
