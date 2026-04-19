# Archived Attempt 2 — output paths

The archived entry script [`test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py`](../pipeline/scripts/test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py) sets **`DOR_PIPELINE_ID=test8_pr_tex_att2_b062_rs1`** and **`PR_INTENSITY_OUT_TAG=blend0p62_ratio_smooth1p0`**, so stochastic outputs live under:

`pipeline/output/test8_pr_tex_att2_b062_rs1/experiment_blend0p62_ratio_smooth1p0/`

Use that path for reruns and for wiring product-comparison tools when you intentionally point at this experiment. If you still have NPZ files under a different directory layout from an older checkout, copy or symlink them into the path above so scripts resolve them consistently.
