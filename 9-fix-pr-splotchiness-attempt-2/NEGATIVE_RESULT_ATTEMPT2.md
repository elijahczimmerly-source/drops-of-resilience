# Attempt 2 — negative result (PR “splotch” / mean tweak)

## What we tried

| Setting | Value (vs test8 v4) |
|---------|---------------------|
| Script (archived) | [`pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py) |
| `DOR_PIPELINE_ID` | `test8_pr_tex_att2_b062_rs1` |
| `PR_INTENSITY_BLEND` | **0.62** (v4: 0.65) |
| `DOR_RATIO_SMOOTH_SIGMA` | **1.0** px on calibrated spatial ratios (v4: 0) |
| `PR_WDF_THRESHOLD_FACTOR` | **1.65** (same family as v4) |

## Verdict

- **Plots:** Time-mean and seasonal **pr** multipanel figures looked **the same as v4** to visual inspection (no useful texture / splotch improvement).
- **Science / product line:** This experiment is **not** carried forward; default product-comparison wiring remains **test8_v2 / v3 / v4** only.

## Where artifacts live

- **Figures (copy of multipanel pr set):** [`plots_4km_pr_attempt2_blend062_ratio_smooth1/`](./plots_4km_pr_attempt2_blend062_ratio_smooth1/) — snapshots of `6-product-comparison/output/figures/4km_plots/` **hist + validation** `pr/` trees from the archived Attempt 2 run (same PNGs show all products in one image; titles used the pipeline short label for that column).
- **Benchmark CSV (archived run):** [`benchmark_summary_archived_pr_blend062_ratio_sigma1.csv`](./benchmark_summary_archived_pr_blend062_ratio_sigma1.csv) — `pipeline_id` = `test8_pr_tex_att2_b062_rs1`.
- **NPZ output path:** `pipeline/output/test8_pr_tex_att2_b062_rs1/experiment_blend0p62_ratio_smooth1p0/` — see [`ARCHIVED_PIPELINE_OUTPUT_PATHS.md`](./ARCHIVED_PIPELINE_OUTPUT_PATHS.md).

## Numeric reminder (why we abandoned “metrics-only” gating)

Small shifts in domain-mean pr and KGE were **not** accompanied by a visible map improvement; the plan’s **human texture** gate failed. See [`FINDINGS.md`](./FINDINGS.md).
