# PR Texture Analysis: Domain Mean, Spatial Texture, and Fixability

## 1. Why is DOR's domain-time mean higher than GridMET and LOCA2?

**Numbers:** DOR v4 = 2.50, GridMET = 2.40, LOCA2 = 2.35, S3 (raw GCM input) = 2.53 mm/day.

The answer is straightforward: **the GCM (MPI) is too wet over Iowa** (2.53 vs GridMET's 2.40). DOR's `spatial_ratio` calibration corrects this *on average over the training period* (1981-2005), but:

- The correction doesn't perfectly generalize to the full 1981-2014 period
- The PR intensity blend (v3/v4) amplifies extremes, which skews the mean upward (test8_v2 without the blend is 2.32 — actually *too dry*)
- The stochastic noise has a slight positive mean bias from clip asymmetry (noise_mult clipped [0.1, 8.5] around 1.0), though Attempt 4 proved this contributes almost nothing to spatial pattern

LOCA2 is drier than GridMET (2.35 vs 2.40) because LOCA2 was trained to Livneh observations, not GridMET, and Livneh is systematically drier than GridMET over Iowa.

**Bottom line:** The domain-mean wet bias comes from the GCM being too wet + the PR intensity blend amplifying that. It's a ~4% overestimate (2.50 vs 2.40). This is a separate issue from the spatial texture.

## 2. Why do the time-mean plots look how Elijah described (DOR spottier, LOCA2 smoother/more gradient-like)?

This is caused by **three compounding factors**, and they are *not* the same as the large-splotch issue from folder 7:

**Factor A: LOCA2 is smoothed by design.** LOCA2 uses constructed analogs — it picks real observed spatial patterns from history and composites them. The result is inherently smooth because observed patterns are smooth. Then in the benchmark, LOCA2 is *additionally* smoothed by `xarray.interp` from its ~6km native grid to the 4km GridMET grid. This acts as a low-pass filter. LOCA2's `high_freq_power_frac` is 0.005 — below GridMET's 0.008. LOCA2 is actually *smoother than reality*.

**Factor B: DOR injects fine-scale variance by design.** The multiplicative stochastic noise (corr_len=35 px for pr, noise factor 0.16, clip up to 8.5x) + the PR intensity blend create pixel-scale variability that doesn't perfectly cancel in time-mean maps. DOR's `high_freq_power_frac` is 0.014 — almost 2x GridMET's 0.008. DOR is *rougher than reality*. This isn't a bug per se — it's the stochastic machinery doing its job of generating realistic daily variability — but the residual texture in time-means is a cosmetic artifact.

**Factor C: Independent per-panel color scaling amplifies perceived differences.** Each panel gets its own 2-98% stretch, so DOR's slightly higher mean and local maxima fill the color range differently than GridMET.

**Why this is different from folder 7:** Folder 7 investigated *large* splotches (50-100+ px dark wet regions in 2006-2014 maps). Those turned out to originate from GCM spatial pattern non-stationarity between training and validation — a `spatial_ratio` generalization problem, not fixable in the downscaler. They mostly disappear on the full 1981-2014 average.

What Elijah is seeing now against LOCA2 is **smaller-scale texture** (the "tiny spots" described in `Elijah_notices.txt`) that persists even over the full historical period. This is fundamentally about DOR's stochastic noise leaving residual fine-scale variance in time-means, versus LOCA2 being inherently smooth. The quantitative data confirms it: DOR's `mean_grad_mag` is 0.025 vs LOCA2's 0.015 vs GridMET's 0.017.

## 3. Are the mean bias and the texture the same issue?

**Partially related but mostly separate.**

- The **mean bias** (DOR 2.50 vs GridMET 2.40) comes from GCM wet bias + PR intensity blend. It would exist even if the spatial texture matched GridMET perfectly.
- The **texture** (DOR rougher than LOCA2/GridMET in time-means) comes from stochastic noise not fully canceling. It would exist even if the domain mean were perfect.

They interact a little: the noise's slight positive mean bias (from the asymmetric clip) contributes a fraction to both the mean and the texture. But Attempt 4 proved noise bias accounts for essentially none of the spatial pattern mismatch. The two problems are essentially independent.

## 4. Is this fixable?

**Honest assessment: not really, and probably not worth fixing.**

Here's what was tried and why it failed:

| Approach | What happened | Why it failed |
|----------|--------------|---------------|
| Noise debiasing (folder 7, Attempts 1-3) | No improvement across all attempts | Noise isn't the cause — deterministic and stochastic maps look the same |
| Ratio smoothing (folder 7, Attempt 5) | Boundary contamination; even with normalized convolution, didn't help | The texture is GCM-origin pattern, not ratio overfitting |
| Blend 0.62 + ratio smooth sigma=1 (folder 9-attempt-2) | Maps identical to v4 | sigma=1 is too small to matter; blend 0.62 vs 0.65 is a tiny change |
| Corr_len sweep (folder 9-RMSE) | Best corr_len (15 px) improved RMSE by 0.013 | Noise tuning operates in a ~0.7 RMSE budget; can't close the gap |

The fundamental issue is that **DOR's texture is a direct consequence of the stochastic design**. You need the noise to get Ext99 right (+0.13%). The noise creates realistic daily variability. But that variability doesn't perfectly cancel in time-means, leaving small-scale texture. To remove the texture you'd have to remove the noise, which destroys extremes.

LOCA2 avoids this because its spatial structure comes from observed analog days (inherently smooth), not from stochastic noise. That's a fundamentally different architecture, not a tuning difference.

**What could actually work** (but would be a major redesign): The cross-variable noise conditioning idea from `9-additional-pr-RMSE-fixes/PLAN-CROSS-VARIABLE-NOISE.md`. If the noise field were *informed* by temperature/humidity patterns instead of purely random, it would produce more spatially coherent precipitation patterns that cancel better in time-means. But this hasn't been tested yet — Phase 0 (feasibility diagnostic checking if the GCM's other variables predict precipitation spatial patterns) hasn't been run.

## 5. Would the `9-additional-pr-RMSE-fixes` plan affect this?

**Yes, if the cross-variable noise conditioning works, it would help both RMSE and texture.**

Here's the connection: the texture problem (DOR rougher than GridMET in time-means) and the RMSE problem (DOR 9.91 vs NEX 8.64) share the same root cause — **r ~ 0.025**. The daily spatial precipitation pattern is essentially random.

If cross-variable conditioning raises r from 0.025 to even 0.10-0.15:
- **RMSE** drops from 9.91 toward ~9.5 (matching LOCA2) because the noise is less random
- **Time-mean texture** improves because spatially informed noise cancels better over many days — the systematic component reinforces signal rather than averaging to noise-scale bumps
- **Ext99** should be preserved because the noise amplitude stays the same — it just gets steered toward more realistic locations

The corr_len sweep and other noise-tuning ideas (Ideas 1-8 in BRAINSTORMING.md) **cannot** fix the texture. They're all operating in the ~0.7 RMSE budget that noise contributes. Only improving r can simultaneously fix RMSE *and* texture.

**But:** This is speculative. The feasibility diagnostic (does R-squared > 0.05 between other GCM variables and precipitation spatial anomalies?) hasn't been run. If R-squared ~ 0, the idea is dead and the texture difference vs LOCA2 is an inherent architectural tradeoff — DOR trades smoothness for better extremes.

**Practical recommendation:** Run the Phase 0 feasibility diagnostic from `PLAN-CROSS-VARIABLE-NOISE.md` before investing more in texture fixes. If there's signal, it solves both problems at once. If there isn't, accept that DOR's texture is the cost of its extreme-precipitation accuracy and document the tradeoff.
