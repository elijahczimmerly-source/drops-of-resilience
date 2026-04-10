# DOR Weaknesses — Benchmark Inventory

Full inventory of every metric where DOR underperforms LOCA2 or NEX-GDDP-CMIP6, plus structural issues. Based on `output/benchmark_summary.csv` (MPI-ESM1-2-HR, 2006–2014, Iowa GridMET grid) and DOR internal metrics from the **`pipeline/`** PR-intensity line (**`test8_v4`**, blend **0.65**; older runs may be under `4-test8-v2-pr-intensity/output/test8_v2_pr_intensity/`).

---

## 1. Precipitation (`pr`) — the focus variable

| Metric | DOR | LOCA2 | NEX | DOR verdict |
|--------|-----|-------|-----|-------------|
| KGE | 0.024 | 0.023 | 0.002 | **Weak (absolute).** ~0.02 is essentially zero skill at day-to-day prediction. All products are bad, but DOR is no better than LOCA2. |
| RMSE | 9.91 | 9.47 | 8.64 | **Worst of three.** NEX is 13% lower, LOCA2 is 4% lower. |
| Bias | +0.11 | -0.12 | -0.15 | Fine — near zero for all. |
| Ext99 Bias% | **+0.13%** | -4.6% | -25.3% | **DOR's best metric.** Nearly perfect on extreme tail. |
| Lag1 Err | 0.056 | 0.066 | 0.043 | Middle of pack. NEX is best here. |
| WDF Obs% | 32.5% | 32.8% | 32.8% | (Reference — minor alignment diffs) |
| WDF Sim% | 32.3% (was 35.9% at factor 1.15) | 31.2% | 37.3% | **Essentially eliminated (+0.02pp)** after tuning `PR_WDF_THRESHOLD_FACTOR` to 1.65. Now best of all three products. LOCA2 -1.5pp, NEX +4.6pp. |
| Per-cell KGE mean | 0.013 | — | — | Essentially zero everywhere, not just pooled. |
| Per-cell r mean | 0.025 | — | — | Nearly zero correlation at cell level. |

**PR weaknesses summary:**
- **RMSE is worst of all three products.** The PR-intensity blend improved extremes but at a cost to overall error.
- **WDF overprediction essentially eliminated** (+0.02pp, was +3.4pp at factor 1.15; now 1.65). Best of all three products.
- **KGE ~ 0** — no day-to-day skill. This is a known fundamental limitation (GCM can't track individual storms), but it means the product has zero temporal tracking ability for precipitation.
- **Per-cell correlation ~ 0.025** — the spatial average doesn't hide the problem; individual cells are equally bad.

## 2. Temperature (`tasmax`)

| Metric | DOR | LOCA2 | NEX | DOR verdict |
|--------|-----|-------|-----|-------------|
| KGE | 0.801 | **0.810** | **0.817** | **Worst of three.** Small gap (~1-2%), but DOR trails both. |
| RMSE | 8.12 | 7.94 | **7.73** | **Worst of three.** NEX is 5% better. |
| Bias | +0.45 | +0.31 | +0.81 | Middle. All have warm bias. LOCA2 is closest to zero. |
| Ext99 Bias% | **-0.24%** | -0.75% | -0.60% | **Best of three** — closest to zero. |
| Lag1 Err | **0.007** | 0.008 | 0.008 | **Best of three**, marginally. |

**Tasmax weaknesses:**
- **Lowest KGE and highest RMSE of the three.** The gap is small but consistent — DOR is the worst performer on the two most standard metrics.
- **Warm bias (+0.45 K)** is larger than LOCA2's (+0.31 K).

## 3. Temperature (`tasmin`)

| Metric | DOR | LOCA2 | NEX | DOR verdict |
|--------|-----|-------|-----|-------------|
| KGE | **0.817** | 0.802 | 0.790 | **Best of three.** |
| RMSE | **7.06** | 7.42 | 7.71 | **Best of three.** |
| Bias | +0.58 | +0.44 | +0.98 | Middle. All warm-biased. LOCA2 closest to zero. |
| Ext99 Bias% | **+0.17%** | +0.32% | +0.77% | **Best of three.** |
| Lag1 Err | **0.008** | 0.011 | 0.033 | **Best of three.** NEX notably worse. |

**Tasmin weaknesses:**
- **Warm bias (+0.58 K)** — not the worst (NEX is +0.98) but larger than LOCA2 (+0.44). Consistent warm bias across both tasmax and tasmin suggests a systematic offset, likely inherited from the GCM or BC step.

## 4. Shortwave radiation (`rsds`) — DOR vs NEX only

| Metric | DOR | NEX |
|--------|-----|-----|
| KGE | **0.763** | 0.682 |
| RMSE | **56.8** | 68.8 |
| Bias | **-0.46** | +36.7 |
| Ext99 Bias% | **+0.85%** | +14.6% |
| Lag1 Err | 0.005 | **0.001** |

**Rsds weaknesses:**
- **Lag1 error: NEX wins** (0.001 vs 0.005). DOR's stochastic noise slightly disrupts temporal persistence of radiation. This is a minor gap in absolute terms but a 5x relative difference.
- No LOCA2 comparison available — can't benchmark against the strongest analog method.

## 5. Wind (`wind`) — DOR vs NEX only

| Metric | DOR | NEX |
|--------|-----|-----|
| KGE | 0.081 | 0.061 |
| RMSE | **2.21** | 2.35 |
| Bias | **-0.32** | -0.93 |
| Ext99 Bias% | -7.5% | -16.3% |
| Lag1 Err | **0.045** | 0.068 |

**Wind weaknesses:**
- **KGE ~ 0.08** — essentially no skill, same fundamental problem as pr. The multiplicative pathway can't fix GCM timing.
- **Ext99 underprediction of -7.5%** — the stochastic downscaler dampens wind extremes. Not as bad as NEX (-16.3%), but still material.

## 6. Humidity (`huss`) — DOR vs NEX only

| Metric | DOR | NEX |
|--------|-----|-----|
| KGE | **0.774** | 0.599 |
| RMSE | **0.0029** | 0.0038 |
| Bias | **+0.0005** | +0.0015 |
| Ext99 Bias% | **+2.2%** | +16.7% |
| Lag1 Err | 0.0057 | **0.0055** |

**Huss weaknesses:**
- **Lag1 error marginally worse than NEX** — same pattern as rsds; the stochastic noise adds tiny temporal disruption.
- **Ext99 bias +2.2%** — small but the largest Ext99 overprediction among DOR's additive variables (tasmax/tasmin/rsds are all <1%).

---

## Structural / Cross-Variable Weaknesses

1. **Multiplicative variables (pr, wind) have near-zero KGE.** This is the single biggest weakness. Per-cell correlation for pr is 0.025 — the product has essentially no temporal tracking for precipitation or wind. This is a known GCM limitation, but LOCA2 achieves the same ~0.02 KGE with lower RMSE, meaning DOR's stochastic noise adds error without adding skill. (WDF gap has been fixed — now +0.9pp vs LOCA2's -1.5pp.)

2. **DOR has the highest pr RMSE of all three products.** The PR-intensity blend traded RMSE for Ext99 — the blend0.65 scoring rule (`|Ext99| + 0.15*RMSE`) explicitly deprioritized RMSE. Parity (no intensity weighting) had RMSE 9.51 vs 9.91 for blend0.65. The extremes improvement came at a ~4% RMSE cost.

3. **Consistent warm bias across tasmax and tasmin** (+0.45 K and +0.58 K). This is larger than LOCA2's bias for both. Could be inherited from OTBC or from the delta-mapping calibration means.

4. **WDF overprediction for pr: essentially eliminated** (+0.02pp, was +3.4pp). `PR_WDF_THRESHOLD_FACTOR` tuned from 1.15 to 1.65 (Apr 2026). Now best of all three products — LOCA2 underpredicts by 1.5pp, NEX overpredicts by 4.6pp. Zero cost to Ext99 (−0.05%). See `8-WDF-overprediction-fix/`.

5. **DOR loses to both LOCA2 and NEX on tasmax KGE and RMSE.** The gap is small (~1-2%) but it's notable that DOR is last place on the most common variable in climate downscaling.

6. **Stochastic noise slightly worsens Lag1 for additive variables** (rsds, huss). The AR(1) model preserves temporal structure well (errors are tiny: 0.005), but NEX's pure BCSD approach achieves even lower Lag1 error on these variables because it doesn't add noise at all.

7. **No LOCA2 data for rsds/wind/huss** — DOR can only be compared to NEX on 3 of 6 variables. The strongest analog-based competitor (LOCA2) is untested on half the variable set.
