# PR RMSE Improvement — Analysis and Brainstorming

## The gap

| Product | RMSE | Ext99 Bias% | WDF Sim% | KGE |
|---------|------|-------------|----------|-----|
| **DOR blend 0.65** | **9.91** | +0.13% | 35.9% | 0.024 |
| DOR parity (no blend) | 9.51 | -6.35% | 35.9% | 0.024 |
| **DOR deterministic (noise=0)** | **9.21** | -11.6% | 37.2% | 0.026 |
| LOCA2 | 9.47 | -4.6% | 31.2% | 0.023 |
| NEX | 8.64 | -25.3% | 37.3% | 0.002 |

## Key observations

1. **NEX's low RMSE comes from compressing the precipitation distribution.** Ext99 = -25.3% means NEX underpredicts extreme rain by 25%. It also has the worst WDF overprediction (+4.6pp) and essentially zero KGE (0.002). NEX "wins" RMSE by dampening variability — less variance = fewer large squared errors. This is not a strategy worth imitating.

2. **DOR parity (no intensity blend) roughly ties LOCA2 on RMSE** (9.51 vs 9.47). The intensity blend adds ~0.4 to RMSE. But the blend is not the root cause of the gap — even at parity, we don't beat LOCA2.

3. **Deterministic DOR (noise=0) already beats both competitors** on RMSE (9.21 vs LOCA2 9.47 vs NEX 8.64). So the stochastic noise adds ~0.7 to RMSE (9.91 - 9.21). The noise is essential for extremes (deterministic Ext99 = -11.6%), but it's the largest single contributor to the RMSE gap.

4. **All three products have pr KGE ≈ 0** — no day-to-day temporal skill. RMSE is therefore dominated by variance mismatch and mean bias, not by correlation. Since bias is near zero for all products, the RMSE difference is almost entirely about how much excess variance each product adds.

## RMSE decomposition

RMSE² = Bias² + (σ_sim - σ_obs)² + 2·σ_sim·σ_obs·(1 - r)

With r ≈ 0 (no correlation) and Bias ≈ 0, this simplifies to:

RMSE² ≈ σ_sim² + σ_obs²

So RMSE is approximately `sqrt(σ_sim² + σ_obs²)`. This means:
- If σ_sim = σ_obs (variance-matched): RMSE ≈ σ_obs · √2 ≈ σ_obs · 1.414
- If σ_sim > σ_obs: RMSE increases
- If σ_sim < σ_obs: RMSE decreases (but you're under-dispersed — bad for extremes)

**The only way to reduce RMSE without sacrificing variance accuracy is to improve correlation (r).** Even a small improvement in r would reduce the 2·σ_sim·σ_obs·(1-r) term significantly because σ_sim·σ_obs is large for precipitation.

## Where does the stochastic noise's RMSE cost come from?

The noise adds 0.7 to RMSE (9.91 vs 9.21 deterministic). This is because:
- On any given day, the noise draws a random spatial pattern of storm amplification/suppression
- This pattern is uncorrelated with the actual observed pattern
- So the noise adds pure variance without adding any useful signal
- Over many days, this doesn't cancel in RMSE — each day's random error contributes independently

The noise is doing something valuable (generating realistic variability at the right scale) but it's doing it at a fixed RMSE cost because it's completely uninformed about what actually happened on each day.

---

## Brainstormed approaches

### Idea 1: Condition the noise on the GCM's daily anomaly signal

**Current:** The noise draw is independent of the GCM's daily precipitation field. On a day where the GCM says "very wet everywhere," the noise still randomly amplifies some pixels and suppresses others.

**Idea:** Use the GCM's daily spatial anomaly (deviation from its climatological pattern) to modulate the noise. On days where the GCM's spatial pattern departs from its training-period mean, bias the noise in the direction of that departure.

For example: if the GCM says the northwest is anomalously wet today relative to the GCM's own climatology, the noise field could be shifted to make the northwest wetter. This would inject a tiny amount of spatial skill from the GCM's large-scale dynamics.

**Why this is novel:** Most stochastic downscalers treat the noise as fully random. This would make the noise partially informed by the GCM's spatial dynamics while remaining stochastic. It's not the same as what LOCA2 does (analog matching) or NEX does (quantile mapping) — it's using the GCM's own spatial departure as a weak prior on the noise field.

**Risk:** The GCM's spatial departures at 4km may be meaningless — after bilinear interpolation from ~100km, the spatial anomaly within a GCM cell is essentially flat. The "signal" would only exist at the inter-cell scale (~3-4 cells across Iowa), giving very few degrees of freedom.

**How to test:** Compute `gcm_daily_anomaly = gcm_day / gcm_climatology` (ratio relative to training-period mean for that semi-monthly period), then correlate it with `obs_daily_anomaly = obs_day / obs_climatology` across pixels. If r > 0, there's spatial signal to exploit. If r ≈ 0, this won't help.

### Idea 2: Use the domain-mean GCM precipitation to scale the noise amplitude

**Current:** `noise_mult = 1.0 + cn * cv_resid * nf` where nf = 0.16 is constant.

**Idea:** On days where the GCM predicts more total precipitation over the domain, the downscaler should produce more spatial variability (bigger storms, more heterogeneous rain field). On drier days, less variability.

Concretely: compute `domain_intensity = mean(gcm_pr_today) / mean(gcm_pr_climatology)` and scale the noise factor: `nf_today = nf * f(domain_intensity)` where f is some function that increases noise on wetter days and decreases it on drier days.

**Why this could improve RMSE:** On dry days, the current noise adds variance that creates false positives (rain where there shouldn't be). Scaling noise down on dry days would reduce these false positives without affecting extreme events (which happen on wet days where noise would be scaled up).

**Risk:** Could worsen WDF if dry-day noise suppression causes fewer pixels to exceed the wet-day threshold. But it could also help WDF — fewer false wet pixels on domain-dry days.

### Idea 3: Spatially varying noise factor calibrated to minimize residual variance

**Current:** `NOISE_FACTOR_MULTIPLICATIVE = 0.16` is a single global constant applied everywhere.

**Idea:** Calibrate `nf` per pixel (or per region) to minimize the expected squared error between `y_final` and `obs`. Pixels in areas where the GCM already gets the variability right should have lower noise; pixels where the GCM undershoots variability should have more noise.

**Why this could help:** The current global nf = 0.16 is a compromise. Some pixels need more noise (to match observed variance) and some need less. Over-noised pixels contribute excess RMSE; under-noised pixels contribute variance mismatch. Pixel-level tuning would optimize the tradeoff everywhere.

**Implementation:** For each pixel, find the nf that minimizes `E[(y_final - obs)²]` on training data. This could be done analytically or via a simple 1D sweep per pixel per semi-monthly period. Store as a `(N_PERIODS, H, W)` array alongside `resid_cv`.

**Risk:** Overfitting to training data — the per-pixel optimal nf might not generalize to validation. Could regularize by smoothing the nf field spatially, similar to the spatial_ratio smoothing idea.

### Idea 4: Reduce noise on near-zero precipitation days (intensity-dependent noise scaling)

**Current:** The noise multiplier is applied uniformly regardless of `y_base`. When `y_base` is small (light rain or near the wet/dry threshold), noise can flip the sign — turning light rain into moderate rain or vice versa. These small-value errors contribute heavily to RMSE because they happen frequently.

**Idea:** Scale the noise factor by the magnitude of `y_base` relative to the pixel's climatological mean. When `y_base` is small (near the WDF threshold), reduce the noise amplitude. When `y_base` is large (clearly a storm day), apply full or enhanced noise.

Something like: `nf_effective = nf * sigmoid((y_base - threshold) / scale)` — noise ramps from ~0 near the threshold to full nf well above it.

**Why this is different from reducing nf globally:** This preserves full noise on extreme events (where noise is needed for Ext99) while reducing it on marginal wet days (where noise creates the most RMSE).

**Risk:** Could interact with WDF calibration — the threshold was calibrated assuming a specific noise behavior near the threshold. Would need to recalibrate the threshold after implementing this.

### Idea 5: Temporal conditioning — use yesterday's observed domain-mean to condition today's noise

**Current:** The AR(1) model gives temporal persistence in the noise field, but only in the noise itself — yesterday's noise correlates with today's noise. There's no conditioning on actual observed or GCM-predicted weather evolution.

**Idea:** Use the GCM's day-to-day change in domain-mean precipitation to modulate the noise. If the GCM says "wetter today than yesterday," the noise field could be shifted to be slightly more positive overall (producing more rain). This exploits the GCM's temporal dynamics without needing to match individual storm positions.

**Why this might help:** The GCM does have *some* temporal skill in precipitation (the domain-mean time series tracks wet/dry spells, even if individual pixel timing is wrong). This is consistent with the AR(1) lag1 correlation being nonzero for observations (~0.36) and for DOR (~0.42). There's temporal signal in the domain mean that could be exploited.

**Risk:** Domain-mean conditioning is very weak — Iowa is small enough that one GCM cell dominates the domain mean. The "signal" might be too coarse to help pixel-level RMSE.

### Idea 6: Optimize the noise correlation length for RMSE

**Current:** `corr_len = 35.0` px for pr — set to match "mesoscale moisture/storm structures."

**Idea:** The correlation length determines the spatial scale of noise patterns. If this is wrong (too large or too small), the noise creates spatial structure at the wrong scale, adding unnecessary RMSE. Sweep `corr_len` and measure the RMSE/Ext99 tradeoff.

**Why this could help:** The correlation length was set heuristically, not optimized. If the observed residual spatial structure is at a different scale than 35 px, we're injecting noise at the wrong scale. A sweep from 15 to 60 px would quickly reveal whether there's a better value.

**This is easy to test** — it's a single constant change, one run per value.

### Idea 7: Replace uniform AR(1) with state-dependent noise persistence

**Current:** `rho = 0.5` for all multiplicative variables, all days, all pixels.

**Idea:** Make rho depend on the weather state. During sustained wet periods (GCM says high domain-mean pr for several days running), use higher rho (more persistence — storms persist). During transitions (yesterday dry, today wet), use lower rho (less persistence — storms are new).

**Why this is novel:** Standard AR(1) downscaling uses fixed rho. Adaptive persistence would better model the difference between frontal systems (multi-day, spatially coherent) and convective events (short, patchy). This matters for Lag1 accuracy and could indirectly improve RMSE by better modeling temporal structure.

**Risk:** Complexity without payoff — rho=0.5 may already be close enough. The Lag1 error is currently 0.056, which isn't the worst metric.

### Idea 8: Post-hoc RMSE optimization via ensemble selection

**Current:** One noise realization per run (deterministic given the seed).

**Idea:** Run 5-10 realizations with different seeds. For each day, select the realization whose domain-mean precipitation is closest to the GCM's domain-mean (which is a reasonable target since we can't match the spatial pattern). This "best-of-N" approach would reduce RMSE by selecting against the worst noise draws without hardcoding the noise field.

**Why this could work:** The domain-mean precipitation has some physical meaning — it reflects the total moisture flux through the domain. By selecting the realization that best matches this constraint, we remove some of the random variance without biasing the distribution.

**Risk:** Expensive (N× compute). Also, selecting based on domain-mean might create a distribution that's too narrow (effectively reducing variance → same problem as NEX). Would need to verify that the selected ensemble preserves Ext99.

---

## Why noise-tuning ideas (1–8) cannot close the RMSE gap

### The math

RMSE² = Bias² + (σ_sim − σ_obs)² + 2·σ_sim·σ_obs·(1 − r)

Where:
- **Bias** ≈ 0 for DOR (already calibrated)
- **σ_sim, σ_obs** are the standard deviations of simulated and observed precipitation, pooled across all pixel-days
- **r** is the Pearson correlation between simulated and observed precipitation across all pixel-days

When Bias ≈ 0 and σ_sim ≈ σ_obs ≈ σ (variance-matched, which DOR is — that's why Ext99 is good):

**RMSE² ≈ 2σ²(1 − r)**

With σ ≈ 7.1 mm/day (estimated from DOR's RMSE and r):

| r | RMSE |
|---|------|
| 0.025 (DOR now) | 9.91 |
| 0.10 | 9.52 |
| 0.20 | 8.98 |
| **0.26** | **8.64 (= NEX)** |
| 0.30 | 8.40 |

### What r means in plain language

On any given day, real precipitation has a specific spatial pattern — maybe it's raining in the northwest corner of Iowa and dry in the southeast, because a front is passing through. GridMET records this actual pattern.

DOR doesn't try to reproduce that. Here's what it gets right and what it gets wrong:

- **What DOR gets right (spatial_ratio):** Over the long run, some pixels are climatologically wetter than others — because of terrain, latitude, proximity to moisture sources. The `spatial_ratio` captures this from 25 years of training data. This is correct *on average*.

- **What DOR also gets right (noise):** Real precipitation is highly variable day-to-day. The stochastic noise generates realistic variability — the simulated *distribution* of rain amounts matches the observed distribution. This is why Ext99 is nearly perfect.

- **What DOR gets wrong (daily spatial pattern):** On January 15, 2008, DOR might put the heavy rain in the southeast while GridMET shows it was actually in the northwest. The noise field is spatially random — it has no information about where it actually rained that day. Over thousands of days, these random patterns average out to the correct climatology, but on any individual day, the pattern is essentially a guess.

That's what r ≈ 0.025 means. The daily spatial pattern is random. Every day that the noise puts rain in the wrong place, that's squared error in RMSE.

### Why noise tuning can't help

The stochastic noise adds ~0.7 to RMSE (9.91 stochastic − 9.21 deterministic). All of Ideas 1–8 try to make the noise better — change its amplitude, scale, spatial structure, or temporal persistence. But even if we perfectly optimized the noise to add **zero** RMSE (which is physically impossible — the noise is there to generate variability, and variability costs RMSE when r ≈ 0), we'd get RMSE = 9.21. **NEX is at 8.64.** We'd still lose.

The correlation length sweep (Idea 6) confirmed this: the best corr_len (15 px) improved RMSE by 0.013 (9.916 → 9.903). The entire noise-optimization budget can yield fractions of a point. The gap to NEX is 1.27 points.

### How NEX gets its low RMSE

NEX doesn't have better correlation (KGE = 0.002, essentially zero — even worse than DOR). NEX gets low RMSE by **compressing the precipitation distribution**: Ext99 = −25.3% means it underpredicts extreme rain by 25%. With σ_sim much smaller than σ_obs, the 2·σ_sim·σ_obs·(1 − r) term shrinks even though r ≈ 0. Less variance = less RMSE, but also wrong extremes.

**DOR cannot and should not imitate this.** Our Ext99 = −0.05% is the product's standout metric — the reason it matters for WEPP/SWAT+.

### The only path to beating NEX on RMSE without sacrificing Ext99

Improve **r** from ~0.025 to ~0.26. This is the only term in the decomposition that can close a 1.27 gap while keeping σ_sim ≈ σ_obs. See [`PLAN-CROSS-VARIABLE-NOISE.md`](PLAN-CROSS-VARIABLE-NOISE.md).
