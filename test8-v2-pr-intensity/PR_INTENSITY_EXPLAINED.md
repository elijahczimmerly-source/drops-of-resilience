# What the PR intensity-dependent ratio does (and what we learned)

This note explains the optional precipitation tweak in `scripts/test8_v2_pr_intensity.py`: how it works, how it relates to **test6**, why it is **not** the same kind of problem as **double bias correction (BC)**, how `**PR_INTENSITY_BLEND`** scales it, and what the **metrics** showed.

---

## 1. The baseline (parity): how test8_v2 spreads coarse rain

Inputs are already **bias-corrected at coarse scale** (OTBC, etc.) and regridded to the fine GridMET grid. The downscaler's job is **spatial disaggregation**: spread each day's coarse precipitation onto fine pixels **without** inventing a second observational correction.

For **precipitation**, test8_v2 uses a **multiplicative** path (per pixel, per semi-monthly period):

1. **Spatial ratio `r_base` (flat ratio)**
  Pick one 4 km GridMET pixel. Pick one of the 24 semi-monthly periods -- say, "first half of March." Collect every day across all the training years that falls into that period (~15 days/year x ~20 years = ~300 days). For each of those ~300 days, you have two precipitation values at that pixel:
  - **Numerator:** the GridMET observed precipitation at that 4 km pixel on that day (natively on the fine grid).
  - **Denominator:** the GCM-simulated precipitation on that day, which was originally on the ~100 km coarse grid, then bias-corrected at that coarse scale via QDM, then bilinearly interpolated onto the 4 km grid. This value is nearly identical across all ~625 fine pixels inside the same coarse cell -- bilinear interpolation just smears the coarse value smoothly.
   `**r_base`** = (average of those ~300 GridMET values) / (average of those ~300 regridded coarse GCM values), clipped to reasonable bounds. This is computed independently for every 4 km pixel and every semi-monthly period.
   Because the denominator is nearly flat within a coarse cell but the numerator varies pixel-to-pixel with topography, `r_base` is what encodes fine-scale spatial texture. A mountain ridge pixel might have `r_base = 1.7` (it consistently gets more rain than the coarse cell average), while a rain-shadow pixel in the same cell might have `r_base = 0.5`.
   The limitation: `r_base` is the same multiplier whether today is a drizzle day or a massive storm. In reality, the spatial distribution of rain across fine pixels may look different during intense events.
   **Base field:** `y_base = (coarse PR at that day) x r_base`.
2. **Multiplicative noise**
  Random spatial noise (AR(1) in time, correlated in space) scales relative residuals so simulated fields vary like the historical residuals around that base.
3. **Wet-day handling**
  Thresholds and caps (e.g. wet-day frequency tuning, mm/day cap) follow the v2 script.

**Parity run:** `PR_USE_INTENSITY_RATIO=0` -- only this **flat** `r_base` is used for PR. That matches "normal" test8_v2-style PR disaggregation for this fork.

---

## 2. What changes when "intensity" is on

**Experiment run:** `PR_USE_INTENSITY_RATIO=1`.

### Computing `r_ext` during calibration

Same pixel, same semi-monthly period, same ~300 training days as `r_base`. But instead of averaging all ~300 values, you look at the **extremes**:

- Sort the ~300 GridMET daily values at that pixel from smallest to largest. Grab the value at the **95th percentile** (roughly the 15th wettest day).
- Do the same for the ~300 regridded coarse GCM values at that pixel.
- `**r_ext`** = (GridMET 95th percentile) / (coarse GCM 95th percentile), clipped to reasonable bounds.

Where `r_base` asks "on an average day, how does fine obs relate to the coarse input here?", `r_ext` asks "on a heavy day, how does the fine obs extreme relate to the coarse input extreme here?" If the mountain ridge captures a disproportionately larger share of rain during big storms than it does on average, `r_ext` will be bigger than `r_base` at that pixel.

**Why the 95th percentile?** It needs to be extreme enough to capture genuinely different spatial behavior during heavy rain, but not so far into the tail that the estimate is based on too few days. The 95th percentile of ~300 days is roughly the 15th wettest day -- enough for a stable statistic. The 99th percentile would be ~3 days, which is noise.

### Applying intensity on each downscale day

On each downscale day, for each pixel:

1. Start with `**ratio = r_base`**.
2. Build a **weight** in [0, 1]:
  `weight = clip(today_coarse_pr / (gcm_95th + epsilon), 0, 1)`
   `**today_coarse_pr`** is the bias-corrected (QDM) GCM precipitation for that day, regridded onto the 4 km grid. This is not observed data -- at downscale time you don't have observations; you only have GCM output.
   `**gcm_95th**` is the 95th percentile of the regridded coarse GCM values at that pixel for that period -- the same denominator used when computing `r_ext` during calibration.
   `**clip(x, 0, 1)**` means: if x < 0, force it to 0; if x > 1, force it to 1.
   So: if today's coarse GCM says 1.2 mm/day and `gcm_95th` is 8.0 mm/day, weight = 0.15 -- light rain, stay close to `r_base`. If today is 7.5 mm/day, weight = 0.94 -- heavy rain, shift almost all the way toward `r_ext`. If today exceeds the 95th percentile, the clip caps weight at 1.
3. **Blend** the two ratios (see section 5 for the `PR_INTENSITY_BLEND` formula).
4. Multiply coarse PR by that **effective ratio**, then apply the **same** multiplicative noise and WDF logic as parity.

So the technique is **not** "bias correct again." It is: **change which calibrated spatial multiplier is used based on how hard it's raining in the coarse cell that day**, using two ratios both estimated from the same training setup as the ordinary multiplicative PR model.

---

## 3. How this differs from test6

**test6** (older script; see `dor-info.md`) used the **same core technique**: a base ratio, an extreme ratio derived from the 95th percentile, and a weight driven by today's intensity to slide between them.

The **one technique-level difference** is that test6 did not have `PR_INTENSITY_BLEND`. Its formula was:

```text
ratio_dynamic = r_base + (r_ext - r_base) * weight
```

On the heaviest day (weight = 1), test6 applied the **full** correction term `**(r_ext - r_base) x weight`** with no extra scalar. The `**PR_INTENSITY_BLEND**` parameter multiplies that **entire** term: `r_base + BLEND x (r_ext - r_base) x weight`. So the dial is **not** on `r_ext` alone -- it scales how much of the **intensity-dependent departure from `r_base`** you allow. The metrics confirmed that **BLEND = 1** (equivalent to test6) overshoots the tail.

Beyond that technique-level difference, **everything else that differs is infrastructure**, not the core idea:

- This runs inside **test8_v2**: **24 semi-monthly** periods, v2 **noise** and **residual CV** calibration off `sim_base = coarse x r_base`, **Schaake shuffle** across six variables, different **clips/caps**, etc.
- **test6** used the older **monthly** framing, different noise settings, different outputs, and a different place in the project history (and often a different input layout).

---

## 4. Why this is not "double BC" in the sense that hurt test7

**Double BC** in your project notes means something specific: applying a **second correction that pulls the solution toward observations** in a way that stacks on top of OTBC -- for example **test7**-style steps that effectively **nudge toward GridMET climatology** again inside the downscaler. That can **overfit** and was flagged as bad.

This intensity tweak **does not** add a new step like "match obs mean again" or "interpolate toward observed rainfall." It only changes **which calibrated multiplier** (`r_base` vs toward `r_ext`) is used when turning **today's coarse OTBC rain** into **fine-scale rain**, using weights driven by **today's coarse value**. Calibration still uses obs+GCM in the **training** window -- the same role GridMET always plays when learning spatial ratios in test8 -- but that is **learning the disaggregation map**, not an extra **post-hoc BC pass** on the output.

**Regridding** (bilinear, etc.) also is not double BC here: it only **resamples the GCM field** onto the fine grid; it does **not** inject observed rainfall into that step.

---

## 5. How `PR_INTENSITY_BLEND` works

With intensity on, the effective ratio is:

```text
ratio = r_base + PR_INTENSITY_BLEND x (r_ext - r_base) x weight
```

The **weight** (section 2) scales `**(r_ext - r_base)`** day by day from today's coarse rain. The **blend** scales that **whole product** `**(r_ext - r_base) x weight`** together: it is **not** applied only to `r_ext`.

- `**PR_INTENSITY_BLEND = 0`** -- the term vanishes; always `r_base` (same as parity).
- `**PR_INTENSITY_BLEND = 1**` -- full `**(r_ext - r_base) x weight**` added to `r_base`. Equivalent to test6 when weight is as in test6.
- **Between 0 and 1** -- only a **fraction** of `**(r_ext - r_base) x weight`**. On the heaviest day (weight = 1), you move `**BLEND**` of the way along the segment from `r_base` to `r_ext`, not the whole segment.

**Why not just use blend = 1?** Because the **full** correction `**(r_ext - r_base) x weight`** is too strong in v2: the tail bias flips from dry to wet and RMSE gets worse. `**r_ext**` is also noisier than `**r_base**` (fewer effective heavy days per period). The blend dials down the **amplitude of the intensity-dependent increment**, not `r_ext` as an isolated quantity.

The **blend sweep** explored values from ~0.25 to ~0.65 at a **fixed `TEST8_SEED`** for fair comparison.

---

## 6. What we expected vs what the numbers showed

**Rough expectations going in**

- Maybe intensity would **lift** the **upper tail** of simulated rain (help **Ext99**) without destroying the rest of the v2 pipeline.
- **WDF** (wet-day frequency gap) might move if spatial stretching interacted with thresholds.

**What we saw (canonical runs, bilinear memmaps, six variables + Schaake)**


| Finding                          | Detail                                                                                                                                                                                                                                                                                                                             |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Parity vs Bhuwan**             | Local **parity** **Ext99** is close to Bhuwan's published **v8_2** ballpark -- the fork + data are in the right family when intensity is **off**.                                                                                                                                                                                  |
| **Full intensity (`blend = 1`)** | **Ext99** swung from modest **dry** bias (parity) to **wet** bias; **RMSE** went **up**. So the **straight** "full test6-style" mix inside v2 was **not** a free lunch.                                                                                                                                                            |
| **WDF gap**                      | Changed **slowly** relative to **Ext99** -- not the main lever in these tables.                                                                                                                                                                                                                                                    |
| **Blend sweep**                  | **Smaller `PR_INTENSITY_BLEND`** moves **Ext99** back toward **neutral** from parity's negative tail bias, with **RMSE** rising **moderately** (on the order of **a few percent** vs parity). So you can **trade** a bit of pooled RMSE for a **much** different tail error -- useful if extremes matter more for the application. |
| **"Win" or not**                 | **Not automatic.** It is a **controlled tradeoff**. For **extremes-focused** goals, a **tuned blend** (e.g. in the ~0.45-0.55 range on our grid/seed) can look **reasonable**; for **minimum RMSE**, **parity** wins.                                                                                                              |


**Where to look in outputs**

- Parity vs full experiment: `output/test8_v2_pr_intensity/v2_pr_intensity_comparison.csv`
- Blend grid: `output/test8_v2_pr_intensity/blend_sweep_results.csv`
- Ranked summary (Bhuwan-comparable columns): `output/test8_v2_pr_intensity/pr_validation_metrics_ranked.csv`

---

## 7. One-line summary

**Intensity-dependent PR** = start from `**r_base`**, then add `**PR_INTENSITY_BLEND x (r_ext - r_base) x weight**`, with **weight** from today's coarse intensity. It is **disaggregation under OTBC**, not a second BC layer like test7. **Full** blend (equivalent to test6) **overshot** the tail; **partial** blends give a **tunable** trade between **Ext99** and **RMSE** on the current stack.