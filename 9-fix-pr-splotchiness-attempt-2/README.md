# PR texture: LOCA2 vs DOR investigation

| File | Purpose |
|------|---------|
| [PLAN.md](./PLAN.md) | Investigation + **Attempt 2** (closed negative) |
| [FINDINGS.md](./FINDINGS.md) | Quantitative results and conclusions |
| [NEGATIVE_RESULT_ATTEMPT2.md](./NEGATIVE_RESULT_ATTEMPT2.md) | Archived blend+ratio-smooth experiment — **plots matched v4**; not in production wiring |
| [ARCHIVED_PIPELINE_OUTPUT_PATHS.md](./ARCHIVED_PIPELINE_OUTPUT_PATHS.md) | Canonical `pipeline/output/...` layout for Attempt 2 (`test8_pr_tex_att2_b062_rs1`) |
| [plots_4km_pr_attempt2_blend062_ratio_smooth1/](./plots_4km_pr_attempt2_blend062_ratio_smooth1/) | **Saved** multipanel **pr** figure trees (hist + validation) from the run that included the extra DOR column |
| [benchmark_summary_archived_pr_blend062_ratio_sigma1.csv](./benchmark_summary_archived_pr_blend062_ratio_sigma1.csv) | Benchmark CSV from that run (`pipeline_id` = `test8_pr_tex_att2_b062_rs1`) |
| [domain_time_means_pr.csv](./domain_time_means_pr.csv) | Domain–time mean pr + wet-day fraction (v2–v4 + refs) |
| [time_mean_map_metrics_pr.csv](./time_mean_map_metrics_pr.csv) | Per-season r, RMSE, gradients, HF power proxy |
| [correlation_vs_gridmet_pivot.csv](./correlation_vs_gridmet_pivot.csv) | Correlation pivot |
| [run_summary.json](./run_summary.json) | Run metadata |
| [LOG.md](./LOG.md) | Work log |

**Regenerate metrics** (several minutes; loads full-historical LOCA2):

```bash
cd 6-product-comparison
python scripts/pr_texture_investigation.py
```

Default output directory is this folder (override with env `DOR_PR_SPLOTCH_WORKDIR`).

**Archived downscale entry (not production):** [`pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py)
