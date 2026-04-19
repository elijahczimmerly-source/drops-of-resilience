# PR noise correlation length sweep — findings

**Plan:** [`PLAN-CORR-LENGTH-SWEEP.md`](../PLAN-CORR-LENGTH-SWEEP.md)  
**Sweep CSV:** [`corr_length_sweep.csv`](corr_length_sweep.csv)  
**Runs:** Local 216×192 memmaps under `3-bilinear-vs-nn-regridding/pipeline/data/bilinear/`; outputs under `4-test8-v2-pr-intensity/output/test8_v4/experiment_corr_len_*`.  
**DATA WARNING:** These runs used the local bilinear data, NOT the canonical server `Regridded_Iowa` data. The bilinear data has 3,999 NaN border pixels vs 6,147 in `Regridded_Iowa`, so absolute metrics (WDF Obs%=32.547 here vs 32.317 on server data) are not directly comparable to published benchmarks. **Relative comparisons across corr_len values within this sweep are valid.**  
**Env (all runs):** `PR_WDF_THRESHOLD_FACTOR=1.65`, `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`, `TEST8_SEED=42`, `PR_USE_INTENSITY_RATIO=1`, `PR_INTENSITY_BLEND=0.65`, `TEST8_MAIN_PERIOD_ONLY=1`, `DOR_RATIO_SMOOTH_SIGMA=0`.

## Results summary

| DOR_PR_CORR_LENGTH | pr RMSE | pr Ext99 Bias% | pr WDF Sim% | pr WDF Obs% | pr Lag1 Err | pr KGE |
|-------------------:|--------:|---------------:|------------:|------------:|------------:|-------:|
| 15 | **9.903** | −0.145 | 32.489 | 32.547 | 0.0543 | 0.0240 |
| 25 | 9.909 | 0.094 | 32.486 | 32.547 | 0.0547 | 0.0239 |
| 35 | 9.916 | 0.128 | 32.495 | 32.547 | 0.0547 | 0.0238 |
| 45 | 9.923 | 0.178 | 32.492 | 32.547 | 0.0544 | 0.0238 |
| 55 | 9.929 | 0.196 | 32.486 | 32.547 | 0.0540 | 0.0238 |
| 70 | 9.937 | 0.216 | 32.478 | 32.547 | 0.0535 | 0.0238 |

**Pattern:** RMSE **increases monotonically** with longer correlation length (9.903 at 15 px → 9.937 at 70 px). Shorter correlation produces more localized multiplicative noise; in this pipeline that **reduces pooled RMSE** without violating the plan’s guardrails.

## Success criteria (plan § Success criteria)

Reference “baseline” row in the plan table used RMSE **9.910**, Ext99 **−0.054%**, WDF Sim **32.34%**, Lag1 **0.055**, KGE **0.024**, wind Ext99 **−7.38%**. Those came from an earlier benchmark run; numbers differ slightly from our **corr_len=35** control in this sweep (e.g. RMSE 9.916 vs 9.910) due to code/manifest drift vs the old `test8_v2_pr_intensity` output folder on `D:\`. Within this single sweep, comparisons are apples-to-apples.

| Criterion | corr_len = **15** |
|-----------|-------------------|
| RMSE improves vs other tested values | **Yes** — best in sweep |
| Ext99 within ±1% of zero | **Yes** (−0.145%) |
| WDF Sim within 2 pp of WDF Obs | **Yes** (32.489 vs 32.547) |
| Lag1 not worse than baseline +0.01 | **Yes** (0.0543; also slightly better than corr_len 35) |
| KGE not worse | **Yes** — vs corr_len 35 in this sweep, KGE is **higher** at 15 |
| Wind Ext99 unchanged across runs | **Yes** — **−7.530304** on every Table1 (all six folders) |
| Non-`pr` variables unchanged when only `pr` corr changes | **Yes** — Table1 rows for tasmax, tasmin, rsds, wind, huss are **identical** between `experiment_corr_len_15` and `experiment_corr_len_35` (verified by file diff) |

## Recommendation

**Adopt `DOR_PR_CORR_LENGTH` default **15** px** for precipitation (when the env var is unset): implemented in `pipeline/scripts/_test8_sd_impl.py` (`process_variable`). Override remains via `DOR_PR_CORR_LENGTH` for experiments.

**Caveat:** Shorter correlation length implies **more pixel-scale** structure in the noise field. RMSE improved; physical realism of spatial noise scale should stay on Bhuwan’s radar if maps look too “speckled” vs coarser mesoscale storms.

## Artifacts

- **Figures:** `../figures/dor_val_corr_len_{15,25,35,45,55,70}.png` — GridMET vs DOR validation mean PR (2006–2014).

## Control vs archived baseline

If you need bit-for-bit match to `experiment_wdf_factor_1p65_216` on `D:\WRC_DOR_runs`, re-run that tag with the **current** `test8_v4` binary; the sweep’s corr_len=35 row is the correct internal control for **this** code revision.
