# LOCA2 vs DOR precipitation — investigation and texture attempts

**Workspace:** [`9-fix-pr-splotchiness-attempt-2/`](.) (repo root)

---

## Part A — Investigation (done)

**Artifacts:** [`FINDINGS.md`](./FINDINGS.md), [`scripts/pr_texture_investigation.py`](../6-product-comparison/scripts/pr_texture_investigation.py)

**Summary:** LOCA2 is smoothed by **algorithm + `xarray.interp`** in [`load_loca2.py`](../6-product-comparison/scripts/load_loca2.py). DOR adds **stochastic noise + PR intensity (v3/v4)** in [`_test8_sd_impl.py`](../pipeline/scripts/_test8_sd_impl.py). [`plot_comparison_driver.py`](../6-product-comparison/scripts/plot_comparison_driver.py) uses **per-panel 2–98%** color limits. Domain–time means and map metrics are in the CSVs in this folder.

---

## Part B — Attempt 2: blend + ratio smooth (**closed — negative**)

**Hypothesis:** Lower **`PR_INTENSITY_BLEND`** (0.62 vs v4’s 0.65) and **`DOR_RATIO_SMOOTH_SIGMA=1`** would improve **texture** (less splotch) and nudge **domain–time mean pr** toward GridMET.

**What was run:** Archived script [`test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py) with **`DOR_PIPELINE_ID=test8_pr_tex_att2_b062_rs1`**. See **[`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md)**.

**Outcome:**

- **Human plot review:** Multipanel **pr** maps looked **indistinguishable from test8 v4** (no useful improvement).
- **Product wiring:** The archived Attempt 2 id is **not** in `config.DOR_DEFAULT_OUTPUTS`, `plot_comparison_driver.DOR_PIDS`, or batch/climate lists — this line is **not** part of the production downscaling evolution.
- **Artifacts:** Saved plots under [`plots_4km_pr_attempt2_blend062_ratio_smooth1/`](./plots_4km_pr_attempt2_blend062_ratio_smooth1/); archived benchmark CSV; output path notes in [`ARCHIVED_PIPELINE_OUTPUT_PATHS.md`](./ARCHIVED_PIPELINE_OUTPUT_PATHS.md).

### Original goals (historical)

1. Domain–time mean pr closer to GridMET than LOCA2’s offset — **small numeric move** occurred but **maps unchanged** to the eye.
2. Texture on time-mean maps — **failed** human gate.

### Documentation

- **[`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md)** — parameters, verdict, file locations.

---

## Part A phases (historical reference)

1. Lock definitions: aligned stacks; domain-time means.
2. Quantify map-level stats (done — see CSVs); texture **attribution** in FINDINGS.
3. Attribute: LOCA2 interp vs DOR stochastic vs plotting.

---

*Plan updated: Attempt 2 concluded negative; production stack remains test8_v2/v3/v4 only.*
