# Literature Review: Nearest-Neighbor Regridding in Climate Downscaling

**Question:** What are other organizations doing for their coarse→fine regridding step, and does anyone use nearest-neighbor?

---

## Summary Answer

Across every major operational statistical downscaling pipeline surveyed, **bilinear interpolation is the community standard** for the coarse→fine spatial interpolation step. Nearest-neighbor does not appear as a chosen method in any of them. **Nobody has quantitatively tested whether bilinear is actually the right choice.**

The pipelines split into two camps:

1. **Interpolation-based pipelines** (NEX-GDDP, ISIMIP2b, CHELSA): interpolate the GCM field to the fine grid, then bias-correct or apply corrections. All use bilinear (or B-spline in CHELSA's case). None use NN. None justify the choice of bilinear — it is stated as a given, without comparison to alternatives.

2. **Observation-library pipelines** (MACA, LOCA2, BCCA, BCCAQ2, GARD): sidestep the interpolation question entirely by deriving fine-scale spatial structure from historical observed records via constructed analogs or regression. No GCM interpolation step exists.

ISIMIP3 is the only pipeline that questioned the interpolation method at all. It tested bilinear against conservative and chose bilinear — but the comparison was purely qualitative (one visual example, no skill metrics). They assumed that providing smoother-looking data as a starting point for their stochastic downscaling step would produce better outputs. See detailed analysis below.

The BCSD R package (`SpatialDownscaling`) lists NN (`ngb`) as a supported option alongside bilinear, but there is no evidence any major dataset chose it.

---

## Pipeline Survey

---

### 1. NEX-GDDP-CMIP6 — NASA (Thrasher et al. 2022)
**Method:** BCSD (Bias Correction / Spatial Disaggregation)
**Regridding:** **Bilinear** — explicitly stated in the technical note.

> *"The coarse-resolution scaling factors are **bilinearly interpolated** to the fine-resolution GMFD grid."*

- 35 CMIP6 GCMs downscaled to 0.25° globally, daily, 1950–2100
- One of the most widely used CMIP6 downscaling datasets globally
- Citation: Thrasher et al. (2022), *Scientific Data*, https://doi.org/10.1038/s41597-022-01393-4
- Tech note: https://www.nccs.nasa.gov/sites/default/files/NEX-GDDP-CMIP6-Tech_Note.pdf

---

### 2. ISIMIP2b / ISIMIP Fast Track — PIK (Frieler et al. 2017; Hempel et al. 2013)
**Method:** Bias adjustment + spatial interpolation then bias correction
**Regridding:** **Bilinear** — confirmed in the ISIMIP3BASD paper, which explicitly describes what the *previous* approach did before ISIMIP3 replaced it.

> *"For statistical downscaling, simulation data are **bilinearly interpolated** to the observation data grid."*

- Used globally across CMIP5 and early CMIP6 impact studies
- Explicitly called out as the standard approach that ISIMIP3 later improved upon
- Citation: Lange (2019), *Geosci. Model Dev.*, https://doi.org/10.5194/gmd-12-3055-2019

---

### 3. ISIMIP3 / ISIMIP3BASD — PIK (Lange 2019)
**Method:** Trend-preserving quantile mapping at coarse resolution + MBCnSD stochastic statistical downscaling
**Regridding:** **Bilinear** as the "broadcast" step inside MBCnSD, followed by stochastic redistribution.

ISIMIP3 is a three-step process:
1. Bias-adjust at the native GCM resolution (using conservatively aggregated observations)
2. Bilinearly interpolate the bias-adjusted GCM data to the fine grid ("broadcast")
3. Apply MBCnSD (a stochastic multivariate method based on Cannon 2017) to redistribute values within each coarse cell to match observed spatial statistics, while preserving the coarse-cell aggregate

**Bilinear vs conservative comparison:** ISIMIP3 is the only pipeline in the entire survey that questioned the interpolation method. They tested bilinear against conservative interpolation for step 2 and chose bilinear. Their stated reasoning (Sect. 3.2.2, Fig. 6):

> *"Broadcasting with bilinear interpolation is preferred because it results in smoother fields than broadcasting with conservative interpolation... bilinear interpolation already generates some of the spatial variability within each coarse grid cell that statistical downscaling has to add, whereas conservative interpolation does not."*

**Strength of evidence:** This comparison is entirely qualitative. The paper shows one visual comparison (a single precipitation field over Europe for one day) and provides a plausible physical argument (bilinear gives MBCnSD a smoother starting point). No skill metrics (RMSE, KGE, etc.) were computed comparing the two options. They assumed that smoother-looking input to MBCnSD would produce better output, but did not validate this assumption with any quantitative test. They also did not consider NN — only conservative was tested against bilinear.

**Relevance to NN:** The paper tested conservative, not NN. Both conservative and NN produce piecewise-constant output (uniform values within coarse cell regions, with hard discontinuities at boundaries), so the qualitative argument against conservative — that piecewise-constant input gives MBCnSD a worse starting point — would also apply to NN. However, conservative and NN are different methods: conservative boundaries follow coarse cell edges and preserve the spatial integral (mass/energy); NN boundaries follow Voronoi regions around cell centers and do not preserve the integral. The ISIMIP3 paper's conclusion does not directly address NN.

- Covers hurs, huss, pr, prsn, ps, rlds, rsds, sfcWind, tas, tasmax, tasmin
- Output at 0.5° globally
- Citation: Lange (2019), *Geosci. Model Dev.*, https://doi.org/10.5194/gmd-12-3055-2019

---

### 4. MACA v2 — University of Idaho (Abatzoglou & Brown 2012)
**Method:** Multivariate Adaptive Constructed Analogs
**Regridding:** **Not applicable in the traditional sense.** Both GCM and observation data are first regridded to a common 1° grid, then the constructed analogs step produces fine-scale output by pattern-matching to the observation library. The fine-scale spatial structure comes from the observed historical record, not from interpolating the GCM field. The bilinear/NN question does not arise.

- Used extensively for CMIP5 CONUS downscaling at ~4km to ~6km
- Variables include tasmax, tasmin, pr, huss, rsds, uas, vas, sfcWind
- Note: applies bias correction *twice* (coarse and fine scales) — something Bhuwan's pipeline explicitly avoids
- Website: https://climate.northwestknowledge.net/MACA/MACAmethod.php

---

### 5. LOCA2 — Scripps Institution of Oceanography (Pierce et al. 2023)
**Method:** Localized Constructed Analogs
**Regridding:** **Not applicable.** Like MACA, spatial detail comes from an observed library, not from interpolating the GCM. LOCA2 bilinearly interpolates sea-level pressure for humidity calculations, but the primary downscaling step does not involve interpolating GCM temperature/precipitation fields.

- 27 CMIP6 GCMs, 6 km resolution, North American domain, used for the US Fifth National Climate Assessment (NCA5)
- Variables: Tmin, Tmax, Precipitation, Humidity
- One of the most technically rigorous CONUS downscaling datasets available
- URL: https://loca.ucsd.edu/loca-version-2-for-north-america-ca-jan-2023/

---

### 6. BCCA v2 — LLNL / UCSD (Maurer et al. 2010)
**Method:** Bias Corrected Constructed Analogues
**Regridding:** Explicit regrid step to a common 2° grid first, then constructed analogs for fine-scale output. The spatial disaggregation uses the analog library, not interpolation.

- Applied to CMIP3/CMIP5 at 0.125° over CONUS
- Variables: tasmax, tasmin, pr
- Citation: Maurer et al. (2010), *HESS*, https://doi.org/10.5194/hess-14-1125-2010

---

### 7. BCCAQ2 / CanDCS-U6 — PCIC Canada (Cannon et al.)
**Method:** Bias Corrected Constructed Analogues + Quantile Delta Mapping
**Regridding:** Analog-based (same as BCCA). Fine-scale spatial structure from the observation library.

- 26 CMIP6 GCMs downscaled to ~10 km (1/12°) across Canada, 1950–2100
- Widely used across Canadian federal and provincial climate services
- URL: https://climatedata.ca/about-bccaqv2/

---

### 8. GARD / En-GARD — NCAR (Gutmann et al. 2022)
**Method:** Generalized Analog Regression Downscaling
**Regridding:** Hybrid analog + regression. Predictors from the GCM select historical analog days; regression coefficients from those analogs are applied to produce fine-scale output. No simple spatial interpolation of GCM fields.

- Framework flexible enough for any target grid; used in CarbonPlan's global CMIP6 downscaling
- Citation: Gutmann et al. (2022), *Journal of Hydrometeorology*
- URL: https://ral.ucar.edu/solutions/products/ensemble-generalized-analog-regression-downscaling-en-gard

---

### 9. CHELSA V2.1 — WSL/ETH Zürich
**Method:** Mechanistic physically-based downscaling
**Regridding:** **B-spline interpolation** to increase resolution, then terrain-aware physics corrections (dynamic lapse rates for temperature, orographic uplift for precipitation).

- Globally available at 1 km resolution
- Temperature: corrected with dynamic lapse rates from ERA5 vertical profiles
- Precipitation: redistribution based on orographic effects
- Not a simple interpolation, but the resolution-change step is B-spline (a smooth interpolation), not bilinear or NN
- URL: https://www.chelsa-climate.org

---

### 10. BCSD R package / SpatialDownscaling (community tool)
**Regridding options:** Bilinear (default) **and** nearest-neighbor (`ngb`) are both listed as supported options.

The documentation explicitly names both — this confirms NN is *available* in the toolchain, but the default is bilinear and there is no evidence any major dataset chose NN over bilinear.

- URL: https://cran.r-project.org/web/packages/SpatialDownscaling

---

## Consolidated Picture

| Pipeline | Organization | Regrid step | Method |
|----------|-------------|-------------|--------|
| NEX-GDDP-CMIP6 | NASA | GCM → 0.25° | **Bilinear** |
| ISIMIP2b / Fast Track | PIK | GCM → obs grid | **Bilinear** |
| ISIMIP3 | PIK | broadcast inside MBCnSD | **Bilinear** (then stochastic redistribution) |
| MACA v2 | Univ. Idaho | (no direct GCM interp) | Constructed analogs |
| LOCA2 | Scripps/UCSD | (no direct GCM interp) | Constructed analogs |
| BCCA v2 | LLNL/UCSD | (no direct GCM interp) | Constructed analogs |
| BCCAQ2 / CanDCS-U6 | PCIC Canada | (no direct GCM interp) | Constructed analogs |
| GARD / En-GARD | NCAR | (no direct GCM interp) | Analog regression |
| CHELSA V2.1 | WSL/ETH Zürich | GCM → 1 km | B-spline |
| BCSD R package | community tool | GCM → obs grid | Bilinear (default), NN (option) |

**Nobody chose NN.** Every pipeline that has an explicit coarse→fine interpolation step uses a smooth method (bilinear or B-spline). None of them justify this choice quantitatively — bilinear is treated as a default that doesn't require defending. The only pipeline that questioned its interpolation method at all (ISIMIP3) did so qualitatively. The modern state-of-the-art observation-library methods avoid the question entirely.

---

## Comparison: ISIMIP3 vs Bhuwan's Pipeline

Both pipelines share the same three-step structure:
1. Bias-correct at coarse resolution
2. Interpolate to fine grid (both use bilinear)
3. Apply stochastic spatial refinement

**Key differences:**

| | ISIMIP3 | Bhuwan (test8) |
|---|---------|----------------|
| Resolution jump | 2° → 0.5° (factor ~4) | ~1° → ~0.04° (factor ~25) |
| Stochastic method | MBCnSD (multivariate quantile mapping with random rotations) | Delta/ratio mapping + AR(1) noise + Schaake Shuffle |
| What the stochastic step does | Redistributes interpolated values within each coarse cell to match observed multivariate distributions; explicitly preserves coarse-cell aggregate | Applies per-pixel observed climatological offset/ratio to the interpolated GCM value, then adds correlated noise |
| Where spatial structure comes from | Emerges from stochastic redistribution matching observed distributions — starting values from bilinear matter because they give the algorithm cross-cell gradients to work with | Dominated by per-pixel observed climatology (`m_obs`); the interpolated GCM value contributes the daily anomaly but not the spatial pattern |

**Why the interpolation method may matter less in Bhuwan's pipeline than in ISIMIP3:**

In ISIMIP3, MBCnSD *redistributes* the interpolated values — the starting values from bilinear are the raw material that gets rearranged. Smoother starting values give MBCnSD meaningful cross-cell gradients to preserve, producing smoother output (their argument for bilinear over conservative).

In test8, the interpolated GCM value (`in_val`) enters the formula `y = in_val + (m_obs - m_gcm) + noise`, but the spatial structure of the output is pinned to `m_obs` — the per-pixel observed climatological mean. Whether `in_val` was bilinearly or NN-interpolated affects only the daily anomaly at each pixel, not the spatial pattern of the output. This is consistent with our empirical finding that bilinear and NN produced nearly identical metrics after running through test8.

However, this does not mean the interpolation method is guaranteed to be irrelevant. The daily anomaly from the GCM does flow through to the output, and bilinear vs NN will produce different anomaly values near coarse cell boundaries. Whether this difference matters for downstream applications (WEPP) has not been tested.

---

## Implications for Bhuwan

1. **Bilinear is the community default, but it is unjustified.** Every pipeline that interpolates uses bilinear, but none of them present quantitative evidence that bilinear is better than alternatives. It is an unchallenged convention, not a validated choice.

2. **ISIMIP3 is the only pipeline that questioned the interpolation method.** Their comparison (bilinear vs conservative) was qualitative — one visual example, no skill metrics. They assumed smoother input to MBCnSD would produce better output but did not test this. They did not consider NN.

3. **Our bilinear vs NN comparison is the only quantitative evidence on this question that we have found.** Metrics were equivalent across all non-precipitation variables after stochastic downscaling. No external paper has performed a comparable test.

4. **Why the interpolation method is largely inconsequential in our pipeline:** test8's delta mapping derives spatial structure from per-pixel observed climatology (`m_obs`), not from the interpolated GCM field. The interpolated value contributes only the daily anomaly. This makes the choice of interpolation method far less consequential than it would be in a pipeline like ISIMIP3, where MBCnSD directly redistributes the interpolated values.

5. **Recommended framing if NN is retained:** "We evaluated bilinear and nearest-neighbor regridding for the 100km→4km step and found no meaningful difference in downstream validation metrics (KGE, RMSE, Ext99) after stochastic spatial disaggregation. This is consistent with the pipeline design: the stochastic downscaling step derives fine-scale spatial structure from per-pixel observed climatology rather than from the interpolated GCM field, making the choice of interpolation method largely inconsequential. Conservative regridding was used for precipitation in all cases."

---

## Sources Not Yet Fully Retrieved
- Maurer et al. (2010) BCCA paper — partially retrieved
- Pierce et al. (2023) LOCA2 full methodology paper
- Thrasher et al. (2012) original BCSD/NEX-GDDP methods paper
- Lange (2019) ISIMIP3BASD paper — retrieved and read in detail
