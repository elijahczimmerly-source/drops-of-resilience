# Multivariate Sub-Grid Precipitation Prediction

## How precipitation actually works

Precipitation requires three ingredients converging at the same place and time: **moisture**, **instability**, and **lift**. All three must be present. Understanding exactly how each works — and which surface-level variables carry information about each — is essential for knowing what to test and what to expect.

### Ingredient 1: Moisture

Air must contain enough water vapor to sustain condensation and rainfall. The relevant quantities:

- **Specific humidity (huss)** measures the actual mass of water vapor per unit mass of air. It's a conserved quantity — an air parcel keeps its specific humidity as it moves, unless condensation or evaporation occurs. It tells you "how much water is available." Specific humidity varies smoothly over large scales because it's controlled by the moisture source (Gulf of Mexico for Iowa) and large-scale advection.

- **Relative humidity (hurs)** measures how close the air is to saturation at its current temperature. RH = 100% means condensation begins. RH is more directly tied to whether rain *can* form at a given location than specific humidity, because it accounts for temperature. However, RH changes with temperature even without any moisture change (warming lowers RH, cooling raises it), so it's more volatile spatially.

- **Vapor pressure deficit (VPD)** is the flip side of RH: it measures how far the air is from saturation in pressure units. Low VPD = near saturation = favorable for condensation. VPD is available in GridMET but not in standard CMIP6 output (would need to be derived from huss, tas, and ps).

- **Moisture flux convergence (MFC)** is where moisture and wind come together. MFC = -(d(q*u)/dx + d(q*v)/dy), which decomposes into an **advection term** (moisture being carried in by the wind) and a **convergence term** (moisture piling up because winds are converging). The convergence term is the more important one for precipitation — it tells you where moisture is accumulating, which is a direct precursor to rain. MFC has been used operationally by the Storm Prediction Center since the 1950s for short-term (0-3 hour) convective initiation forecasts. It requires wind components (uas, vas) and specific humidity (huss).

**Key insight for our problem:** Moisture fields are smooth and interpolate well. A bilinear interpolation of huss from ~100km to 4km should preserve the real large-scale moisture gradient across Iowa. The moisture *ingredient* is the one we're most likely to capture accurately from the GCM.

### Ingredient 2: Instability

The atmosphere must be unstable enough that once air starts rising, it keeps rising. The key concept is **Convective Available Potential Energy (CAPE)** — the integrated buoyancy a rising air parcel would experience. High CAPE means the atmosphere is a loaded spring: if something triggers uplift, strong convection (and heavy rain) follows.

CAPE depends on the vertical temperature and moisture profile. We don't have upper-air data from the GCM's surface variables, but we can approximate:

- **Surface temperature (tas, tasmax, ts)** — Higher surface temperature increases the temperature difference between the surface and upper atmosphere, increasing instability. The diurnal range (tasmax - tasmin) is also a proxy: large diurnal range = clear skies and dry air (stable), small diurnal range = cloudy/moist air (potentially unstable).

- **Surface specific humidity (huss)** — Higher low-level moisture increases CAPE because a rising moist parcel releases more latent heat, making it more buoyant. Research shows that increasing CAPE mainly results from increased low-level specific humidity.

- **Lapse rate proxies** — We don't have the actual lapse rate from surface data alone. But the combination of high surface temperature + high humidity + low shortwave radiation (indicating existing cloud cover) is a strong proxy for unstable, convectively active environments.

- **Convective Inhibition (CIN)** — The "cap" that prevents convection from initiating even when CAPE is high. CIN acts as a lid: warm air aloft (an inversion) prevents surface parcels from rising. CIN cannot be estimated from surface variables alone. This is a fundamental limitation — we can estimate the *potential* for convection (CAPE proxy) but not the *barrier* to initiation (CIN).

**Key insight for our problem:** Instability is partly estimable from surface variables (through CAPE proxies) but the triggering threshold (CIN) is not. This means we can identify *regions where convection is possible* but not reliably predict *whether and exactly where it fires*. For convective precipitation (dominant in Iowa summers), this is a real ceiling on predictability from surface data.

### Ingredient 3: Lift

Something must force air upward to overcome CIN and initiate condensation. This is the critical ingredient for *where* precipitation falls, and it operates through four mechanisms — each with different spatial scales and predictability:

#### a) Frontal lift
Cold air masses wedge under warm air, forcing it upward along the boundary. This is the dominant precipitation mechanism for Iowa in **winter, spring, and fall**. Fronts are identifiable from surface variables:

- **Temperature gradient** — Fronts are sharp boundaries in temperature. A strong spatial gradient in tas/tasmax across the domain indicates a front. The front lies *along* the gradient maximum.
- **Wind shift** — Ahead of a cold front, winds are from the south/southwest (warm moist Gulf air). Behind it, winds shift to northwest (cold dry Canadian air). This shows up as a sharp change in uas/vas across the front.
- **Pressure trough** — Fronts lie in pressure troughs. The gradient of psl points toward the front, and pressure is lowest along the frontal boundary.
- **Precipitation location** — Rain falls along and ahead of the front (for cold fronts) or in a broad region ahead of it (for warm fronts). The frontal position can be located from the temperature gradient, wind shift, and pressure trough. Rain falls within ~50-100km of this boundary.

Frontal precipitation is the **most predictable** type from surface variables because fronts are large-scale features (~500-1000km) that the GCM resolves well. After interpolation to 4km, the temperature/wind/pressure gradients should locate the front within the Iowa domain. The question is whether the interpolated position is accurate enough at the 4km scale to improve over random noise.

#### b) Convective lift (thermals)
The sun heats the ground unevenly, creating rising columns of warm air (thermals) that punch through the cap and trigger thunderstorms. This is the dominant mechanism for **Iowa summer afternoon precipitation**.

Predictability from surface variables is **low** because:
- Where exactly a thermal fires depends on tiny surface heterogeneities (a dark plowed field, a drying soil patch) at scales far below 100km.
- The timing is sensitive to the diurnal cycle — convection typically fires in the late afternoon when surface heating peaks.
- Once one storm fires, its outflow boundaries can trigger new storms nearby in unpredictable chain reactions.

However, the *preconditions* for convection are estimable: high surface temperature (rsds, tasmax), high humidity (huss), and large diurnal temperature range building through the day. These can identify "the atmosphere is primed for convection over this part of the domain" without pinpointing exactly where storms fire.

**Iowa-specific note:** The Great Plains low-level jet (LLJ) is critical for Iowa summer precipitation. The LLJ is a nocturnal wind maximum at ~850mb that transports Gulf of Mexico moisture northward into the central US. It drives mesoscale convective systems (MCSs) that produce 30-70% of Iowa's warm-season precipitation. The LLJ peaks at night, producing a nocturnal precipitation maximum (unusual — most places rain in the afternoon). The LLJ signature shows up in surface wind fields (strong southerly component, uas/vas), but its strength and position are upper-air features that surface variables capture imperfectly.

#### c) Orographic lift
Wind pushes air over terrain features, causing uplift on the windward side and rain shadow on the lee side. **Largely irrelevant for Iowa** — the terrain is flat (elevation varies by only ~400m across the state, gradually, with no ridges). This would matter for Colorado, the Appalachians, etc., but for Iowa we can ignore it. The elevation data (`Regridded_Elevation_4km.npz`) could be included as a feature but shouldn't be expected to contribute much.

#### d) Mesoscale convergence
Wind patterns at the 10-50km scale can create localized zones where air piles up and is forced upward. Sources include:
- Outflow boundaries from earlier storms
- Land-breeze circulations
- Differential surface heating (urban heat islands, crop/forest boundaries)
- Drylines (boundaries between moist and dry air masses)

These are **essentially unpredictable** from 100km GCM data because they exist entirely at sub-grid scales. They cannot be interpolated because the GCM doesn't simulate them.

### Ingredient 3.5: Soil moisture feedback (Iowa-specific)

Recent research (PNAS 2021, J. Applied Meteorology 2021) shows that soil moisture plays a significant role in Iowa warm-season precipitation:

- **Positive feedback:** Wetter soil increases evapotranspiration, increasing low-level moisture and CAPE, favoring convective initiation over wet patches (when the LLJ isn't dominant).
- **Negative feedback (more complex):** Dry soil creates stronger sensible heat flux, which can initiate convection over dry patches — but the resulting storms then propagate to and strengthen over nearby wet patches.
- **LLJ interaction:** When the low-level jet is present (common in Iowa), the LLJ's moisture transport dominates over local soil moisture effects. Soil moisture matters more on LLJ-absent days.

The CMIP6 variable **mrsos** (surface soil moisture) could capture this, but only if the GCM's soil moisture spatial pattern is accurate at the 4km interpolated scale. Since soil moisture responds to recent precipitation (which the GCM gets wrong spatially), the GCM's soil moisture field may have limited sub-grid skill.

### Seasonal breakdown for Iowa

| Season | Dominant mechanism | Predictable from surface vars? |
|--------|-------------------|-------------------------------|
| **Winter (Dec-Feb)** | Frontal/cyclonic. Organized systems, pressure-driven. Low precipitation totals. | **Best chance.** Fronts are large-scale, show up in T/wind/pressure gradients. |
| **Spring (Mar-May)** | Mix of frontal and convective. Strong storms, tornado season. Gulf moisture surges. | **Moderate.** Frontal component is predictable; convective component less so. |
| **Summer (Jun-Aug)** | Convective dominant. MCSs driven by LLJ. Nocturnal maximum. 50-70% of annual pr. | **Hardest but highest stakes.** LLJ moisture transport may give some signal via uas/vas/huss. Individual storm placement is chaotic. |
| **Fall (Sep-Nov)** | Transitioning back to frontal. Decreasing moisture. | **Moderate-good.** Similar to spring. |

**This seasonal structure should inform testing.** If the approach works at all, it will likely show highest skill in winter/transition seasons and lowest in summer. Phase 1 and Phase 8 diagnostics should report skill by season to identify where the signal lives.

---

## How each candidate variable relates to precipitation: detailed assessment

### psl — Sea-level pressure [Tier 1: LIFT]

**Physical mechanism:** Pressure gradients drive geostrophic wind, and departures from geostrophic balance produce convergence/divergence. Low-pressure centers and troughs are where air converges and rises. Fronts lie in pressure troughs. In the midlatitudes, synoptic-scale low-pressure systems are the primary organizer of precipitation.

**What it tells us at 4km after interpolation:** The interpolated pressure field would show the position and depth of troughs crossing Iowa. Since pressure varies smoothly over hundreds of kilometers (typically ~1-2 hPa per 100km in a moderate system), bilinear interpolation should faithfully reproduce the pressure gradient across the domain. The gradient direction points toward convergence.

**Statistical downscaling literature:** Mean sea-level pressure is consistently ranked among the top 3 predictors for precipitation in every statistical downscaling study reviewed. The Canadian CMIP6 downscaling ensemble uses 26 predictor variables across 3 pressure levels — psl is included in every configuration.

**Limitation:** Pressure tells you about large-scale forcing but not the exact precipitation placement at 4km. A pressure trough across Iowa means "precipitation likely somewhere in this region" but not which specific pixels.

**Verdict: Definitely include. Likely the single most important predictor for the large-scale "where is the weather action" question.**

### uas, vas — Wind components [Tier 1: LIFT + MOISTURE TRANSPORT]

**Physical mechanism:** Three roles:
1. **Wind convergence** (-(duas/dx + dvas/dy) > 0) directly indicates where air is being forced upward. This is the most direct surface-level indicator of lift.
2. **Moisture transport** — southerly wind (positive vas in Iowa) brings Gulf moisture. The direction and speed determine how much moisture reaches Iowa.
3. **Frontal identification** — wind direction shifts sharply across fronts. Ahead of a cold front: southwesterly. Behind it: northwesterly. This discontinuity in uas/vas locates the front.

**What it tells us at 4km after interpolation:** Wind fields are moderately smooth but less so than pressure or temperature — real wind fields have mesoscale features (sea breezes, outflow boundaries) that the GCM can't capture. After interpolation, the large-scale wind pattern (e.g., "southerly flow across Iowa") is accurate, but localized convergence zones are lost. The interpolated convergence field would capture synoptic-scale convergence (associated with fronts and pressure troughs) but miss mesoscale convergence (associated with storm-scale features).

**Critical derived quantity — Moisture Flux Convergence:**
MFC = -(d(q*u)/dx + d(q*v)/dy)
This combines moisture availability with wind convergence into a single field that directly indicates "where moisture is accumulating." MFC has been used operationally for convective initiation forecasting since the 1950s. Surface MFC is a standard 0-3 hour prognostic tool at the Storm Prediction Center. Large MFC values (>= 100 x 10^-5 g/kg/s) are associated with severe weather initiation.

**Limitation:** The pipeline currently only has scalar wind speed (sfcWind), not components. uas and vas are available in the Cropped_Iowa raw data but haven't been used in the pipeline. They would need to be added to the regridded data.

**Verdict: Definitely include. Wind components unlock convergence and MFC — the most physically direct precipitation predictors available from surface data.**

### huss — Specific humidity [Tier 1: MOISTURE]

**Physical mechanism:** The mass of water vapor in the air. Sets the upper bound on how much rain can fall. Also a key input to CAPE — higher low-level specific humidity means more latent heat release in updrafts, increasing buoyancy and storm intensity.

**What it tells us at 4km after interpolation:** Specific humidity varies very smoothly over large scales — it's controlled by the moisture source region and large-scale advection. Interpolation fidelity should be excellent. The gradient across Iowa (typically wetter in the southeast, drier in the northwest, with day-to-day variation from Gulf moisture surges) should be well-captured.

**Role in prediction:** Huss is necessary but not sufficient. High humidity means the ingredients are there, but without lift, no rain forms. Huss is most valuable in combination with wind convergence (via MFC) or pressure gradients.

**Verdict: Include. Essential ingredient, and the one most faithfully preserved by interpolation.**

### hurs — Relative humidity [Tier 1: MOISTURE]

**Physical mechanism:** How close the air is to saturation. When RH approaches 100%, condensation begins. More directly tied to whether condensation *is happening* than huss, because it accounts for temperature.

**What it tells us at 4km after interpolation:** RH is smooth but more spatially variable than huss because it responds to both moisture and temperature. A localized warm patch (say from differential surface heating) lowers RH even without moisture change. After interpolation, the large-scale RH pattern is preserved but local variations from land-use differences are lost.

**Role in prediction:** High RH at the surface indicates the atmosphere is close to saturation — a favorable precondition for precipitation. The RH gradient could help distinguish the moist vs dry side of a front or dryline.

**Note:** GridMET provides rmax and rmin (daily max/min relative humidity), not instantaneous RH. CMIP6 provides hurs (daily mean) and hursmax/hursmin.

**Verdict: Include. Complementary to huss — captures saturation proximity.**

### tasmax, tasmin, tas — Temperature [Tier 2: INSTABILITY + FRONTAL DETECTION]

**Physical mechanism:** Multiple roles:
1. **Frontal detection** — The temperature gradient magnitude identifies fronts. The front lies along the gradient maximum. This is how meteorologists have located fronts for a century.
2. **Instability proxy** — High surface temperature + high humidity = high CAPE. Warm surfaces create buoyancy for convective updrafts.
3. **Diurnal range proxy** — (tasmax - tasmin) is inversely related to cloud cover and moisture. Large diurnal range = clear, dry, stable air (unfavorable for precipitation). Small diurnal range = cloudy, moist (favorable). This is available from GridMET.
4. **Sensible heat flux proxy** — (ts - tas) or high tasmax indicates strong surface heating, which drives convective boundary layer growth and eventually thunderstorm initiation.

**What it tells us at 4km after interpolation:** Temperature is the smoothest atmospheric field — it varies gradually across hundreds of kilometers, driven by latitude, elevation, and air mass properties. Bilinear interpolation should be highly faithful. The frontal temperature gradient, if present in the domain, should be accurately positioned.

**Limitation:** Temperature alone doesn't tell you much about precipitation. A warm day could be sunny and dry or the precursor to an afternoon thunderstorm. Temperature's value is in combination with moisture (for instability) and in spatial gradients (for frontal detection).

**Verdict: Include. Excellent interpolation fidelity. Valuable for frontal detection (gradients) and instability estimation (in combination with huss).**

### rsds — Downwelling shortwave radiation [Tier 2: CLOUD PROXY]

**Physical mechanism:** Rsds at the surface is primarily controlled by cloud cover. Clear sky rsds is predictable from time of year and latitude. The *departure from clear-sky rsds* is a direct measure of how much cloud is overhead.

- Low rsds (relative to clear-sky) = thick clouds overhead = likely precipitating or about to precipitate.
- High rsds = clear or thin clouds = currently dry.

This makes rsds an *indicator* of current precipitation, not a *cause*. But it's useful because it captures information about the atmospheric column (cloud thickness/depth) that other surface variables don't.

**What it tells us at 4km after interpolation:** Rsds is moderately smooth — cloud fields have more spatial structure than temperature but less than precipitation. A large cloud deck associated with a front shows up as a broad area of reduced rsds. Convective clouds are more patchy and harder to interpolate.

**Limitation:** Rsds is partly circular as a predictor — low rsds means it's cloudy, which correlates with rain, but the GCM's rsds field has the same spatial resolution limitations as its precipitation field. The GCM's cloud field is parameterized, not resolved at 4km. However, the large-scale cloud pattern (e.g., "overcast ahead of the front, clear behind it") should be captured.

**Verdict: Include. Useful as a cloud-cover/atmospheric-column proxy. Expect moderate interpolation fidelity.**

### rlds — Downwelling longwave radiation [Tier 2: CLOUD + MOISTURE COLUMN PROXY]

**Physical mechanism:** The atmosphere emits longwave radiation downward. The amount depends on:
1. **Cloud cover** — Clouds are strong longwave emitters. Cloudy nights are warmer than clear nights because of enhanced rlds.
2. **Atmospheric moisture content** — Water vapor is a greenhouse gas. A moist atmospheric column emits more rlds than a dry one.

High rlds indicates a warm, moist, and/or cloudy atmospheric column overhead — all favorable for precipitation.

**What it tells us at 4km after interpolation:** Similar to rsds, rlds captures atmospheric column information. It's less spatially variable than rsds (because the longwave emission integrates over the whole atmospheric depth) so it should interpolate reasonably well.

**Limitation:** Partially redundant with rsds (both respond to clouds) and huss (moisture column). But rlds combines them into one signal.

**Verdict: Include as secondary. Provides atmospheric column depth information not available from other surface variables.**

### ts — Surface skin temperature [Tier 2: CONVECTIVE HEATING]

**Physical mechanism:** The temperature of the ground surface itself (not the 2m air). Important because:
1. **(ts - tas)** measures the sensible heat flux — how much the ground is heating the air above it. Large positive (ts - tas) means strong surface heating, driving convective boundary layer growth and potentially triggering convection.
2. On its own, ts varies with land surface properties (albedo, soil moisture, vegetation). Wet soil is cooler (evaporative cooling). The ts field therefore carries information about soil moisture patterns without needing mrsos directly.

**What it tells us at 4km after interpolation:** ts is quite smooth over flat terrain like Iowa. The interpolated field should capture the large-scale surface temperature pattern. Local variations from different crop types or soil moisture are lost.

**Limitation:** ts is less commonly available in CMIP6 archives than tas/tasmax/tasmin.

**Verdict: Include if available. The (ts - tas) difference is a unique predictor not captured by other variables.**

### ps — Surface pressure [Tier 2: REDUNDANT WITH psl]

**Physical mechanism:** Same information as psl but including elevation effects. On flat terrain like Iowa, ps and psl are nearly interchangeable. ps adds value only when combined with terrain data on rugged terrain.

**Verdict: Skip. Use psl instead. ps adds no information over psl for Iowa's flat terrain.**

### prc — Convective precipitation [Tier 3: REGIME INDICATOR]

**Physical mechanism:** The GCM separately computes convective (parameterized) and large-scale (resolved) precipitation. The fraction prc/pr tells you what type of precipitation the GCM thinks is happening.

- High prc/pr = convective day. Precipitation placement is inherently less predictable from large-scale fields. Lower our confidence in the multivariate prediction.
- Low prc/pr = large-scale/frontal day. Precipitation placement is more tied to resolvable features (fronts, troughs). Higher confidence in prediction.

**What it tells us at 4km:** prc has the same spatial resolution problems as pr — it's noisy, not smooth. Its value is as a **domain-wide regime indicator** (what fraction of today's rain is convective?), not as a pixel-level predictor. Use it to weight the prediction confidence, not as a spatial feature.

**Verdict: Include as a scalar regime indicator (domain-mean prc/pr ratio), not as a spatial field.**

### clt — Cloud fraction [Tier 3: CLOUD COVER]

**Physical mechanism:** Directly tells you where clouds are. Clouds mean condensation is occurring and precipitation is possible (though many clouds don't precipitate).

**Limitation:** The GCM's cloud fraction is parameterized and has limited spatial skill at sub-grid scales. After interpolation, it's a smooth field that adds little beyond what rsds/rlds already tell you about cloud presence.

**Verdict: Skip. Redundant with rsds (which is a more reliable proxy for cloud cover at the surface).**

### mrso, mrsos — Soil moisture [Tier 3: IOWA-SPECIFIC FEEDBACK]

**Physical mechanism:** As discussed in the soil moisture feedback section, soil moisture influences convective initiation in Iowa's warm season. Wet soil increases evapotranspiration and low-level moisture; dry soil increases sensible heat flux and boundary layer depth.

**Limitation:** The GCM's soil moisture field depends on its own (inaccurate) precipitation history. If the GCM rained in the wrong place last week, its soil moisture spatial pattern is wrong this week. This makes soil moisture a potentially unreliable predictor from the GCM specifically. From observations (GridMET/ERA5-Land), it would be more trustworthy — but we don't have observed soil moisture at 4km.

**Verdict: Test in Phase 8 but expect limited skill. The GCM's soil moisture spatial pattern is contaminated by its own precipitation errors.**

### VPD — Vapor pressure deficit [GridMET only]

**Physical mechanism:** VPD = saturation vapor pressure - actual vapor pressure. Low VPD = near-saturation = favorable for condensation. High VPD = dry atmosphere = unfavorable.

**Availability:** GridMET provides VPD directly. CMIP6 does not, but it can be derived from huss, tas, and ps.

**Verdict: Include in Phase 1 (GridMET-based). Derive from other variables in Phase 5 and apply in Phase 8.**

---

## Derived features: the physics-informed combinations

Raw variables provide ingredients. Derived features capture the *interactions* between ingredients that actually trigger precipitation. These are more important than individual variables.

### Moisture flux convergence (MFC) [MOST IMPORTANT DERIVED FEATURE]

**Formula:** MFC = -(d(q*u)/dx + d(q*v)/dy)

Decomposed:
- **Advection term:** -(u * dq/dx + v * dq/dy) — moisture being carried in by the wind
- **Convergence term:** -q * (du/dx + dv/dy) — moisture piling up because winds are converging

The convergence term is more important for precipitation initiation. Positive MFC means more moisture is flowing into a region than flowing out — moisture is accumulating. This accumulated moisture must go somewhere: upward, forming clouds and rain.

**Operational use:** The Storm Prediction Center uses surface MFC routinely for 0-3 hour convective initiation forecasts. Large MFC centers are among the most reliable surface indicators of where storms will fire. The spatial pattern of MFC (where the convergence maxima are) predicts storm location.

**At 4km from interpolated GCM data:** The interpolated uas, vas, and huss fields are all smooth. Their product and spatial derivatives will also be smooth. The resulting MFC field captures synoptic-scale convergence patterns (associated with fronts and pressure troughs) but misses mesoscale features. For frontal precipitation, this may be sufficient. For convective initiation, the synoptic-scale MFC identifies the *region* where storms are favored, not the exact pixel.

**Requirements:** uas, vas, huss — all available in Cropped_Iowa raw data.

### Temperature gradient magnitude [FRONTAL DETECTION]

**Formula:** |grad(T)| = sqrt((dT/dx)^2 + (dT/dy)^2)

Using tasmax or tas. Identifies frontal boundaries. The front lies along the maximum gradient. Precipitation concentrates along and ahead of the front.

**At 4km from interpolated data:** Temperature gradients interpolate very well. If a front crosses the Iowa domain, the interpolated temperature gradient should locate it within ~50-100km of its true position (approximately one GCM cell width of uncertainty). This is coarse, but it's directional information the current noise model doesn't have at all.

### Pressure gradient [CONVERGENCE INDICATOR]

**Formula:** |grad(psl)| = sqrt((dpsl/dx)^2 + (dpsl/dy)^2)

Strong pressure gradients mean strong winds and active weather. The direction of the gradient points toward the low-pressure center. Precipitation organizes around pressure troughs.

### Thermal instability proxy

**Formula:** CAPE_proxy = tasmax * huss (or more physically: huss * (tasmax - tasmin_climatology))

This is crude but captures the two main drivers of CAPE: surface heat and low-level moisture. Days with high tasmax AND high huss are convectively unstable. Days with high tasmax but low huss are hot and dry (stable).

**Limitation:** This is a scalar proxy for a quantity (CAPE) that properly requires a full atmospheric sounding. It captures the *surface contribution* to instability but misses upper-air influences.

### Cloud cover proxy

**Formula:** cloud_proxy = 1 - (rsds / rsds_clearsky)

Where rsds_clearsky is the expected clear-sky shortwave for that day of year and latitude (can be computed from solar geometry or from the climatological maximum rsds for that calendar day). Values near 0 = clear. Values near 1 = thick overcast.

### Diurnal temperature range

**Formula:** DTR = tasmax - tasmin

Low DTR = cloudy/moist atmosphere (favorable for rain). High DTR = clear/dry (unfavorable). Available from both GridMET and GCM.

---

## The idea

The GCM can't tell us which 4km pixels got rain — its native precipitation field is one value per ~100km cell. But it *can* tell us, with reasonable accuracy, the spatial patterns of temperature, humidity, pressure, wind, and radiation. These fields are physically smooth, so bilinear interpolation from ~100km to 4km produces gradients that approximate reality.

Within a single GCM cell, each interpolated variable has its own gradient — temperature might increase from west to east, humidity from south to north, pressure dropping toward the northwest. At each 4km pixel, the combination of all these interpolated values creates a unique multivariate signature. Precipitation is threshold-driven: it occurs when the right combination of conditions (moisture, instability, uplift) converge at a specific location. A model trained on observed relationships could learn which multivariate signatures correspond to rain, producing a spatially complex wet/dry prediction within each GCM cell — even though every individual input is smooth.

This is fundamentally different from the cross-variable noise conditioning plan (PLAN-CROSS-VARIABLE-NOISE.md), which proposed blending weather information into the existing random noise field. That plan would modestly bias noise toward the right region. This plan attempts to directly predict the sub-grid precipitation field from the multivariate inputs, which could produce sharp wet/dry boundaries where threshold conditions are met.

## Why this could work

1. **Interpolation is accurate for smooth fields.** Temperature, humidity, and pressure vary smoothly over ~100km. Bilinear interpolation between cell centers recovers the large-scale gradient within each cell. For Iowa (flat terrain, no coastlines), these interpolated gradients are especially trustworthy because there are few local geographic features to disrupt the smooth large-scale pattern.

2. **Multiple gradients create complex patterns.** One smooth gradient is boring — a linear ramp. But 10-20 smooth gradients pointing in different directions, with different magnitudes, create a rich multivariate field at each pixel. A nonlinear model (or even a threshold-based model) operating on this field can produce spatially complex output.

3. **Precipitation is physically determined by these variables.** Rain requires moisture, instability, and lift — all of which are at least partly captured by the available surface variables. These aren't arbitrary correlations — they're causal physical mechanisms.

4. **GCM has demonstrated skill for these variables.** tasmax KGE = 0.80, tasmin KGE = 0.82, huss KGE = 0.78. The GCM gets these fields right at the large scale, and interpolation preserves the gradient information.

## Why this might not work

1. **Summer convection dominates Iowa precipitation (50-70% of annual total) and is the least predictable type.** The physics section explains why: convective triggering is chaotic at sub-grid scales, and the most important forcing (the LLJ, mesoscale convergence) operates at scales the GCM can't resolve. The approach may work for winter/spring frontal precipitation but fail in summer when it matters most.

2. **Interpolated gradients reflect large-scale structure only.** The within-cell gradient comes entirely from the difference between neighboring cell center values. Any real sub-cell variation driven by local features (that aren't captured by neighboring cells) is invisible. Iowa's flatness helps, but it doesn't eliminate the issue.

3. **Training on observations could overfit to GridMET's own interpolation artifacts.** GridMET itself is an interpolated product from station data. Its 4km precipitation field has its own spatial smoothing and interpolation assumptions.

4. **The GCM's variable fields, while skillful, are not perfect.** KGE = 0.80 means there's still 20% of the signal that's wrong. The errors may be correlated across variables (e.g., if the GCM's frontal position is wrong, temperature, wind, and pressure are all wrong in the same direction).

5. **CIN is unknowable from surface data.** Even when all surface indicators say "convection should happen here," a capping inversion aloft can prevent it. We have no way to estimate this from the available variables.

---

## The current pipeline

The DOR pipeline processes climate variables through these steps:

```
1. Regrid observed GridMET (4km) → 100km GCM grid
       Script: regrid-gridmet-100km.py
       Method (regrid_to_gridmet.py default): conservative for pr/fluxes, bilinear for state variables

2. Bias correct GCM at 100km using regridded historical observations (OTBC)
       Scripts: in Bias_Correction/ (MV-QDM / OTBC method)

3. Crop bias-corrected 100km data to Iowa region (with 3° buffer)
       Script: crop_2_scott_bc_mpi.py

4. Regrid bias-corrected GCM from 100km → 4km (GridMET grid)
       Script: regrid_to_gridmet.py
       Method actually used to produce the test8_v2 inputs: bilinear for pr (Bhuwan
       confirmed in chat — overriding the script's conservative-for-pr default).
       For the other 5 variables Bhuwan was unsure when asked and never followed up;
       working assumption is bilinear via the script's defaults but NOT explicitly
       confirmed. See `dor-info.md` § "Bilinear vs Nearest-Neighbor Comparison".

5. Apply stochastic downscaling (adds realistic sub-grid spatial variability)
       Script: test8_v2.py (current version)
       Method: multiplicative noise for pr/wind, additive noise for temperature/radiation/humidity
```

**Currently, the pipeline processes 6 variables:** pr, tasmax, tasmin, rsds, wind (sfcWind), huss.

Every variable that goes through this pipeline gets: bias correction against GridMET observations (OTBC), proper regridding to 4km, and stochastic downscaling to add realistic spatial variability. The result is a bias-corrected, high-resolution field that can be meaningfully compared to GridMET at the pixel level.

---

## Classes of predictor variables

This plan uses variables from other fields to predict where precipitation falls. Predictor variables fall into four classes based on which datasets they appear in (GridMET, GCM, non-GridMET observed/reanalysis):

### Class 1: GridMET and GCM (have 4km ground truth)

These variables exist in GridMET at 4km AND have a corresponding GCM variable. They CAN go through the full pipeline (OTBC + regridding + stochastic downscaling), producing a bias-corrected, properly downscaled 4km field.

**Currently in pipeline (6):** pr, tasmax, tasmin, rsds, wind (sfcWind), huss

**Not yet in pipeline but potentially Class 1:** rmax (hursmax) and rmin (hursmin) — *only if* MPI-ESM1-2-HR provides them as daily output. Phase 0 verifies this. If MPI doesn't provide them, they fall to Class 3a instead. Note that **VPD is NOT a Class 1 candidate** because no standard CMIP6 model outputs VPD directly — it's always Class 3a.

**Rule: GridMET-and-GCM variables must ALWAYS go through the full pipeline before being used.** Never use a raw or merely-regridded GCM version of a variable that has GridMET ground truth. The pipeline exists to fix biases and add realistic spatial structure — skipping it means using a worse version of something we could make better.

### Class 2: GCM only (no 4km ground truth)

These variables exist in the GCM but have NO GridMET equivalent (and no other observed truth we plan to use). They CANNOT go through the full pipeline because there's nothing to bias-correct against. The best we can do is bilinear interpolation from ~100km to 4km.

**Examples:** psl (sea-level pressure), uas (eastward wind), vas (northward wind), rlds (downwelling longwave), ts (surface skin temperature), mrsos (surface soil moisture).

**Known limitations of GCM-only variables:**
- **No bias correction:** Systematic GCM biases in absolute values are NOT corrected. This matters for threshold-based precipitation prediction — if hurs is biased 5% high, thresholds are crossed in the wrong places.
- **No interpolation verification:** Phase 4 tests interpolation fidelity for Class 1 (GridMET-and-GCM) variables using a round-trip test (4km → 100km → 4km). This test is impossible for GCM-only variables because there's no 4km ground truth to compare against.
- **No stochastic downscaling:** The interpolated field is smooth — it has no realistic sub-grid variability beyond what bilinear interpolation produces.

**Partial mitigation for uas/vas:** Wind speed magnitude (sqrt(uas² + vas²)) can be compared against GridMET's wind speed. If the magnitude matches, the components are probably not wildly wrong. For psl, there is no equivalent check.

**Rule: GCM-only variables are used as-is (bilinearly interpolated) and results that depend on them must be flagged as lower-confidence.**

### Class 3: Derived variables (no direct GCM output, must be derived from other variables)

Some physically important precipitation predictors are NOT in standard daily CMIP6 output. They cannot go through the pipeline because there's no GCM input field to bias-correct. Instead, they must be **derived from variables we DO have** (Class 1 pipeline outputs and Class 2 bilinearly-interpolated outputs) using physical formulas. These are "Class 3" variables.

Class 3 splits into two sub-types based on what observed ground truth is available to validate the derivation — either a GridMET-only variable (Class 3a) or a non-GridMET-observed-only variable from reanalysis (Class 3b):

#### Class 3a: GridMET only (has 4km GridMET truth, no GCM)

These are variables observed in GridMET at 4km but lacking a corresponding standard CMIP6 daily output. We have 4km ground truth to validate against, but the model side has to be derived.

**Examples:**
- **VPD** (vapor pressure deficit): GridMET provides it directly; CMIP6 does not. Derive from tasmax + huss + ps using the Magnus equation.
- **rmax / rmin** (daily max/min relative humidity): GridMET provides them; CMIP6 *may* provide hursmax/hursmin daily, but it depends on the model. If MPI-ESM1-2-HR doesn't output them, they become Class 3a and are derived from tasmax/tasmin + huss + ps.

**Validation in Phase 5:** at 4km against GridMET. This is the strongest validation we can do — same resolution as the actual application in Phase 8.

#### Class 3b: Non-GridMET observed only (reanalysis truth only, no GCM, no GridMET)

These are variables important for precipitation that aren't in GridMET or in standard daily CMIP6 output, but ARE available from reanalyses (ERA5, NARR) at coarser resolution (~25-32 km).

**Examples:**
- **CAPE** (convective available potential energy): approximate from surface tasmax + huss + a lapse-rate assumption.
- **CIN** (convective inhibition): proxy from DTR + low-level moisture.
- **PWAT** (precipitable water): approximation from surface huss with a scale-height assumption.
- **Theta-e** (equivalent potential temperature): direct formula from T + q + p.
- **K-index, Lifted index**: traditional derived stability indices.
- **Frontogenesis**: derivable from temperature gradients + wind.

**Validation in Phase 6:** at the reanalysis's native resolution against the reanalysis target. Coarser than 4km, but we're testing the formula not spatial detail.

**Rule (both 3a and 3b): Class 3 variables are USE-AT-OWN-RISK approximations until they pass the Phase 5 (3a) or Phase 6 (3b) derivation-fidelity test.** Class 3 variables must NEVER be referenced by phases that assume a pipelined GCM input exists for them — they can't go through OTBC because there's nothing on the GCM side to correct.

---

## Available variables — full inventory

### GCM side (CMIP6 / MPI-ESM1-2-HR)

The full CMIP6 catalog has hundreds of variables. The server's public share (`\\abe-cylo\public\CMIP\`) has a comprehensive list in `CMIP6_Variables.xlsx`. The Cropped_Iowa raw data already has: pr, tasmax, tasmin, rsds, wind, huss, uas, vas. Additional variables can be downloaded from CMIP6 archives as needed.

### GridMET side

GridMET provides: pr, tmmx (tasmax), tmmn (tasmin), srad (rsds), vs (wind speed), sph (huss), rmax, rmin, vpd, and potentially others. The exact inventory will be confirmed in Phase 0, which also adds Class 1 (GridMET-and-GCM) variables to the pipeline. Class 3a (GridMET-only) variables — definitely VPD, possibly rmax/rmin — are routed to Phase 5 for derivation instead.

### Variable classification table

| Variable | GridMET? | GCM? | Class | Pipeline status | Physics role |
|----------|----------|------|-------|----------------|-------------|
| pr | Yes | Yes | 1 | In pipeline | TARGET |
| tasmax | Yes | Yes | 1 | In pipeline | INSTABILITY + FRONTAL |
| tasmin | Yes | Yes | 1 | In pipeline | INSTABILITY (DTR) |
| rsds | Yes | Yes | 1 | In pipeline | CLOUD PROXY |
| wind (sfcWind) | Yes | Yes | 1 | In pipeline | GENERAL |
| huss | Yes | Yes | 1 | In pipeline | MOISTURE |
| rmax (hursmax) | Yes | Maybe (model-dependent) | 1 if MPI outputs it; else 3a | Phase 0 inventory decides | MOISTURE (saturation) |
| rmin (hursmin) | Yes | Maybe (model-dependent) | 1 if MPI outputs it; else 3a | Phase 0 inventory decides | MOISTURE (saturation) |
| VPD | Yes | **No** | **3a** | **Cannot pipeline — derive in Phase 5** | MOISTURE (saturation deficit) |
| psl | No | Yes | 2 | N/A — bilinear only | LIFT (pressure trough) |
| uas | No | Yes | 2 | N/A — bilinear only | LIFT + MOISTURE TRANSPORT |
| vas | No | Yes | 2 | N/A — bilinear only | LIFT + MOISTURE TRANSPORT |
| rlds | No | Yes | 2 | N/A — bilinear only | MOISTURE COLUMN PROXY |
| ts | No | Yes | 2 | N/A — bilinear only | CONVECTIVE HEATING |
| mrsos | No | Yes | 2 | N/A — bilinear only | SOIL FEEDBACK |
| VPD (validated) | GridMET 4km | No | **3a** | Derived from tasmax + huss + ps | MOISTURE (saturation deficit) |
| rmax / rmin (if MPI lacks hursmax/min) | GridMET 4km | No (in this case) | **3a** | Derived from tasmax/tasmin + huss + ps | MOISTURE (saturation) |
| CAPE | ERA5 / NARR (~25-32 km) | No (daily) | **3b** | Derived from Class 1/2 | INSTABILITY (deep convection) |
| CIN | ERA5 / NARR (~25-32 km) | No (daily) | **3b** | Derived from Class 1/2 | CONVECTIVE INHIBITION |
| PWAT (prw) | ERA5 / NARR (~25-32 km) | No (daily, most models) | **3b** | Derived from Class 1/2 | MOISTURE COLUMN |
| theta-e | ERA5 / NARR | No | **3b** | Derived from Class 1/2 | MOISTURE + INSTABILITY |
| Lifted Index / K-index | ERA5 / NARR | No | **3b** | Derived from Class 1/2 | STABILITY |
| Frontogenesis | ERA5 / NARR | No | **3b** | Derived from Class 1/2 | FRONTAL FORCING |

### Derived features (computed from the above on the 4km grid)

| Feature | Inputs | Class of inputs | Physics role |
|---------|--------|----------------|-------------|
| **DTR** | tasmax, tasmin | Class 1 (pipeline) | Cloud cover/moisture proxy |
| **Cloud proxy** | rsds | Class 1 (pipeline) | Current cloud cover |
| **CAPE proxy** | tasmax, huss | Class 1 (pipeline) | Convective instability |
| **|grad(tasmax)|** | tasmax | Class 1 (pipeline) | Frontal boundary location |
| **|grad(huss)|** | huss | Class 1 (pipeline) | Moisture boundary |
| **MFC** | uas, vas, huss | **Mixed: Class 2 + Class 1** | Where moisture accumulates |
| **Wind convergence** | uas, vas | Class 2 (bilinear only) | Where air is forced upward |
| **Pressure gradient** | psl | Class 2 (bilinear only) | Convergence/frontal indicator |

Note: MFC uses a mix of Class 1 (huss, through pipeline) and Class 2 (uas/vas, bilinear only) inputs. Its reliability is limited by the weaker ingredient.

### Variables to skip (with physics justification)
| Variable | Why skip |
|----------|----------|
| **ps** | Redundant with psl on flat Iowa terrain |
| **clt** | Redundant with rsds as cloud proxy; parameterized in GCM |
| **prsn** | Noisy like pr; limited value |
| **rsus, rlus** | Redundant with rsds, ts respectively |
| **tas** | Redundant with tasmax/tasmin (can compute mean) |

---

## Phase 0: Expand the pipeline to all GridMET-and-GCM variables

**Goal:** Before any prediction work begins, add every GridMET variable that isn't already in the pipeline AND has a corresponding GCM daily output (the Class 1 candidates) as a full pipeline variable. This means running them through OTBC + regridding + stochastic downscaling, so they're bias-corrected and properly downscaled at 4km — just like the existing 6 variables. **GridMET variables that have no GCM equivalent (e.g. VPD, possibly rmax/rmin) cannot be added to the pipeline because there is nothing on the GCM side to bias-correct against — they are Class 3a and are handled in Phase 5 by deriving them from the pipelined Class 1 variables.**

**Why this must come first:** Every later phase uses Class 1 (GridMET-and-GCM) variables as predictors. If we use raw or merely-regridded GCM versions of variables that COULD go through the pipeline, we're using worse data than we need to. The whole point of the pipeline is to produce the best possible 4km fields. Any variable with GridMET ground truth should go through it.

### Step 0a: Inventory

List the contents of:
- `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\GridMET\` — what GridMET variables are available?
- `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\Raw\` — what MPI variables are available?

For each GridMET variable NOT currently in the pipeline, determine:
1. **Does the corresponding GCM variable exist in Cropped_Iowa/Raw, or is it available daily from MPI-ESM1-2-HR in CMIP6?** (e.g., GridMET rmax ↔ GCM hursmax). If yes → it's a Class 1 candidate, proceed to step 0b. If no → it's Class 3a, skip it here and add it to the Phase 5 candidate list.
2. Is the variable a state variable or a flux? (historically determined regridding method — bilinear vs conservative — but note that Bhuwan switched pr to bilinear for the test8_v2 inputs, so this classification is no longer automatic; confirm with Bhuwan per variable)
3. Is the variable multiplicative (like pr, wind — always ≥ 0, right-skewed) or additive (like temperature — can be negative, roughly symmetric)? (determines noise pathway in the downscaler)

**Known Class 3a (definitely no GCM equivalent):** VPD. Skip this in Phase 0 and route directly to Phase 5.

**Conditional Class 3a:** rmax, rmin. Check whether MPI-ESM1-2-HR outputs hursmax/hursmin daily. If yes, treat as Class 1 (continue to step 0b). If no, treat as Class 3a (route to Phase 5).

Record results — including the Class 1 vs Class 3a verdict for each variable — in `9-additional-pr-RMSE-fixes/output/phase0_variable_inventory.txt`.

### Step 0b: Run each new Class 1 variable through the pipeline

For each new GridMET variable identified in Step 0a as **Class 1** (has a GCM equivalent):

1. **OTBC bias correction at 100km.** Run the same OTBC workflow used for the existing 6 variables. This requires the GCM variable at 100km and the GridMET variable regridded to 100km.
2. **Regrid to 4km.** Use the same `regrid_to_gridmet.py` approach Bhuwan used for the test8_v2 inputs: **bilinear for pr** (overriding the script's conservative-for-pr default — Bhuwan confirmed this in chat) and bilinear for state variables. For new flux variables specifically, ask Bhuwan whether to keep the script's conservative default or also switch to bilinear for consistency with how he handled pr.
3. **Stochastic downscaling.** Add the variable to test8_v2's processing. Determine whether it should use the multiplicative pathway (like pr/wind) or the additive pathway (like temperature). Humidity variables (rmax, rmin) are bounded [0, 100] — this may require special handling.

**This step requires Bhuwan's input** on:
- Whether existing OTBC code handles the new variables or needs modification
- Which downscaling pathway (additive/multiplicative) is appropriate for each
- Whether bounded variables (rmax, rmin: 0-100%) need clipping or transformation

### Step 0c: Validate new pipeline variables

For each newly-added pipeline variable, compute on the validation period (2006-2014):
- **KGE** (pooled across all pixel-days)
- **Pixel-level Pearson r** (spatial correlation averaged across days)
- **RMSE**
- **Mean bias**

Compare DOR output → GridMET. If any variable has pathological results (negative KGE, very low r), something went wrong in the pipeline setup. Fix before proceeding.

### Output
- `9-additional-pr-RMSE-fixes/output/phase0_variable_inventory.txt` — full inventory of available variables and classification
- `9-additional-pr-RMSE-fixes/output/phase0_new_pipeline_validation.csv` — metrics for newly added pipeline variables
- Updated pipeline data files on the server (new variables added to the memmap or equivalent)

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase0_expand_pipeline.py` (or may require modifications to existing pipeline scripts)

---

## Phase 1: Baseline metrics

**Goal:** Establish quantitative baselines for every variable so we know exactly what the pipeline currently achieves and where the gaps are. Numbers only — no plots. Phase 2 handles visual inspection.

**Scope:** This phase deals only with Class 1 (pipeline-processed GridMET) variables. Class 3a variables (VPD etc.) appear here only on the GridMET side as an upper-bound reference. Class 2 and Class 3b variables do not appear in this phase.

### Step 1a: Full per-variable metrics

For every Class 1 pipeline variable (the original 6: pr, tasmax, tasmin, rsds, wind, huss — plus any newly-pipelined Class 1 variables like rmax/rmin if MPI provides hursmax/hursmin), compute on the validation period (2006-2014):
- **KGE** (pooled across all pixel-days)
- **Pixel-level Pearson r** (spatial correlation averaged across days — the key metric for this plan)
- **RMSE**
- **Ext99 Bias%**
- **Lag1 autocorrelation error**
- **WDF** (for pr only)
- **Domain-mean temporal correlation**
- **Mean bias**

Compute for both GCM input → GridMET and DOR output → GridMET.

Also include **derived features** computed from pipeline-processed Class 1 variables: DTR (tasmax - tasmin), |grad(tasmax)|, |grad(huss)|, cloud_proxy (1 - rsds/rsds_clearsky), CAPE_proxy (tasmax * huss normalized).

Record in: `9-additional-pr-RMSE-fixes/output/phase1_baseline_metrics.csv`

**Why this matters:** We need the pixel-level spatial r for every pipeline variable, not just pr. The physics argument is that the GCM has real spatial skill for temperature/humidity (high r) but not precipitation (low r). If the GCM's daily spatial r for tasmax is also low, the premise is weaker than we think.

### Step 1b: Per-variable spatial correlation by season

Compute pixel-level spatial r for **every Class 1 pipeline variable** (GCM input and DOR output, each vs GridMET), broken out by season (DJF, MAM, JJA, SON). This tests the physics expectation that:
- Temperature spatial r should be high in all seasons
- Humidity spatial r should be high in all seasons
- Precipitation spatial r should be near zero in all seasons (but maybe slightly better in winter)
- Wind spatial r — unclear, this will be informative

Output: `9-additional-pr-RMSE-fixes/output/phase1_spatial_r_by_season.csv`

### Step 1c: Pixel-level correlation between each predictor and precipitation

For **every non-pr Class 1 (GridMET-and-GCM) variable** — all pipeline-processed variables and all derived features — compute the **spatial Pearson correlation with observed pr** across all valid pixels, for each day, then average across days. This directly measures "does this variable's spatial pattern correspond to where it rains?"

Compute this for both the GridMET side (theoretical relationship) and the DOR output / GCM input side (relationship after the pipeline). The gap between them measures how much the pipeline preserves the predictor-pr relationship.

**For Class 3a variables (VPD, and rmax/rmin if they end up Class 3a)**: compute the spatial-r-with-pr ONLY on the GridMET side. There is no pipelined DOR/GCM version of these variables yet — the corresponding model side comes from Phase 5. Including them here measures the upper bound: "if our Phase 5 derivation were perfect, what skill could VPD contribute?"

Also compute by season — the physics predicts that rsds-pr correlation (cloud proxy) should be strong (negative) in all seasons, while temperature-pr correlation might only be meaningful during frontal seasons.

Output: `9-additional-pr-RMSE-fixes/output/phase1_predictor_pr_correlation.csv`

### Data sources
- GridMET at 4km: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat` — shape (12418, 6, 216, 192).
- Additional GridMET (rmax, rmin, VPD): `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\GridMET\` — yearly NPZ files.
- CMIP6 inputs at 4km: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat`
- DOR output: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Iowa_Downscaled\v8_2\Stochastic_V8_Hybrid_*.npz`
- Geo mask: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy`

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase1_baseline_metrics.py`

### How to interpret
- If the pipeline's daily spatial r for tasmax/huss is high (>0.7) and for pr is near zero (<0.05): the premise holds. Proceed.
- If the pipeline's daily spatial r for tasmax/huss is also low (<0.3): the pipeline doesn't have spatial skill for *any* variable. The premise of the plan is wrong. Stop.
- If predictor-pr correlations (Step 1c) from GridMET show |r| > 0.2 for any variable: there's a detectable spatial relationship between that variable and precipitation.
- If ALL predictor-pr correlations are |r| < 0.05: the relationship may be nonlinear, but expectations should be lowered.

---

## Phase 2: Visual inspection of representative days

**Goal:** Plot predictor variables alongside observed precipitation for representative days, to build intuition and catch data problems that pure metrics miss. Plots only — Phase 1 already covers numerical baselines.

**Scope:** Class 1 (GridMET-and-GCM) pipeline-processed variables, plus Class 3a (GridMET-only) variables (VPD, rmax/rmin) on the GridMET side only. No Class 2 (GCM-only: uas/vas/psl) variables — those first appear in Phase 7.

### Step 2a: Day selection

Pick **12 days** — 3 per season — that represent distinct precipitation regimes. For each season, pick:
1. **A strong frontal day** — a clear band of precipitation crossing the domain, visible in the GridMET pr field as a coherent stripe or arc. (For summer, pick an MCS/squall line day instead.)
2. **A scattered convective day** — patchy, disorganized precipitation with wet and dry pixels interleaved. (For winter, pick a day with light scattered snow/rain.)
3. **A mostly dry day with localized precipitation** — only a small region of the domain is wet.

To find these days: load the GridMET pr field, compute the wet-pixel fraction and spatial autocorrelation for each day, then sample from different regimes. Print the dates selected and why.

Output: `9-additional-pr-RMSE-fixes/output/phase2_selected_days.csv` — the 12 selected dates with regime labels and selection rationale. **These same 12 days are reused by Phases 3, 5, 6, and 8 for consistency.**

### Step 2b: Plot set 1 — Observed variables vs observed precipitation (GridMET only)

For each of the 12 selected days, produce one figure with **10 panels in a 2x5 grid**:

Row 1 (the target):
- Panel 1: **Observed pr** (GridMET, 4km). Use a diverging or sequential colormap that makes wet/dry obvious. Mark the 1mm wet-day threshold.

Row 1 continued + Row 2 (the predictors):
- Panel 2: **tasmax** — look for temperature gradients that line up with rain bands or uniform warmth
- Panel 3: **huss** — look for moisture gradients; rain should be on the moist side
- Panel 4: **rsds** — low rsds should correspond to cloudy/rainy areas
- Panel 5: **wind speed** — less clear what to expect; include for completeness
- Panel 6: **DTR (tasmax - tasmin)** — low DTR should correspond to cloudy/rainy areas
- Panel 7: **VPD** — low VPD (near saturation) should correspond to rainy areas
- Panel 8: **|grad(tasmax)|** — temperature gradient magnitude; maxima should align with frontal rain bands
- Panel 9: **|grad(huss)|** — moisture gradient magnitude; sharp moisture boundaries may align with rain edges
- Panel 10: **rmax** — high relative humidity should correspond to rainy areas

Suptitle: the date, the regime label, AND the spatial r between each predictor and observed pr for that specific day (printed as a compact row of numbers at the top). This ties the visual to the quantitative.

All panels use the same spatial domain and geo_mask. Use a shared colorbar per variable (not per panel — the same variable should have the same color scale across all 12 days so days are comparable).

**What to look for:**
- On frontal days: does the temperature gradient line up with the rain band? Is rsds low where it's raining? Is huss higher on the rainy side?
- On convective days: is there any spatial correspondence at all, or is the precipitation pattern completely unrelated to the smooth predictor fields?
- On dry days with localized rain: does anything in the predictor fields hint at where the rain is?
- Red flags: if rsds is HIGH where it's raining, or huss is LOW where it's raining, something is wrong with the data alignment.
- **Check that the per-day r values in the suptitle match what you see in the plot.**

### Step 2c: Plot set 2 — Derived features vs observed precipitation

For the **same 12 days**, produce a second figure with 6 panels:
- Panel 1: **Observed pr** (same as above)
- Panel 2: **|grad(tasmax)|** — frontal boundary detection
- Panel 3: **|grad(huss)|** — moisture boundary detection
- Panel 4: **cloud_proxy** (1 - rsds/rsds_clearsky) — inferred cloud cover
- Panel 5: **CAPE_proxy** (tasmax * huss, normalized) — convective instability
- Panel 6: **DTR** — diurnal range as stability indicator

Include per-day spatial r with observed pr in the suptitle for each derived feature.

### Step 2d: Plot set 3 — Pipeline output vs GridMET vs observed precipitation

For the **same 12 days**, produce a third figure comparing pipeline DOR output for each Class 1 predictor variable to its GridMET counterpart alongside observed precipitation:
- Panel 1: **Observed pr** (GridMET, 4km)
- Panel 2: **DOR tasmax** vs GridMET tasmax difference map
- Panel 3: **DOR huss** vs GridMET huss difference map
- Panel 4: **DOR rsds** vs GridMET rsds difference map
- Panel 5: **DOR wind** vs GridMET wind difference map
- Panel 6: **DOR pr** vs GridMET pr difference map

Include per-day spatial r between each DOR field and its GridMET counterpart in the suptitle.

**What to look for:**
- Do the DOR fields for temperature and humidity look like reasonable reproductions of the GridMET fields for that day?
- On frontal days: does DOR show temperature gradients in roughly the right places?
- How does DOR pr compare to observed pr? The contrast between "DOR pr is spatially random" and "DOR tasmax/huss match GridMET well" is the visual case for this approach.

### Data sources
Same as Phase 1.

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase2_visual_inspection.py`

### Output
- `9-additional-pr-RMSE-fixes/output/phase2_selected_days.csv` — 12 selected dates with regime labels
- `9-additional-pr-RMSE-fixes/figures/phase2_visual/` — 12 days × 3 plot sets

### How to interpret
- **Frontal days show clear visual correspondence** (T gradient aligns with rain band, huss is higher on the wet side, rsds is low where it rains): the approach has both a quantitative and visual basis. Proceed.
- **Convective days show no correspondence**: expected. Doesn't kill the approach — confirms summer convective skill will be limited.
- **Even frontal days show no correspondence**: the physics story doesn't hold at 4km over Iowa. Reconsider.
- **DOR output fields look totally different from GridMET** for predictor variables: the pipeline has issues that need fixing before this plan can proceed.

---

## Phase 3: Theoretical ceiling from observations

**Goal:** Determine the maximum possible skill if we had perfect 4km predictor fields. This uses ONLY GridMET observed data — no GCM involved. It answers: "given perfect knowledge of today's temperature, humidity, radiation, and wind at every 4km pixel, how well can we predict which pixels got rain?"

### Available GridMET variables for this test
pr, tasmax (tmmx), tasmin (tmmn), wind speed (vs), rsds (srad), huss (sph), rmax, rmin, VPD, plus any others found in the inventory. **All variables here are at the 4km observation level — Phase 3 uses the GridMET-side ground truth regardless of whether a variable is Class 1 or Class 3a.** Note: **no pressure, no wind components (direction), no longwave radiation, no soil moisture.** This limits Phase 3 to testing the MOISTURE and INSTABILITY ingredients. The LIFT ingredient (the most important one for *where* rain falls) cannot be tested with GridMET alone.

### Two parallel tracks

From this point forward, two approaches are developed in parallel. Bhuwan decides which to try first.

---

### TRACK A: Physics-based function

Design a precipitation likelihood function from known physical relationships, with a small number of tunable weights.

#### Functional form

The function encodes the three precipitation ingredients using GridMET variables:

```python
# Moisture term: high humidity → more likely rain
moisture = normalize(huss) + normalize(rmax) - normalize(VPD)

# Instability term: warm + moist + cloudy → convective potential
instability = normalize(tasmax) * normalize(huss) * normalize(cloud_proxy)
# where cloud_proxy = 1 - rsds / rsds_clearsky

# Lift term (limited — no pressure or wind components in GridMET):
# Use temperature and humidity gradients as frontal proxies
lift = normalize(|grad(tasmax)|) + normalize(|grad(huss)|)

# Combined precipitation likelihood
rain_likelihood = w1 * moisture + w2 * instability + w3 * lift
                + w4 * moisture * lift   # interaction: moisture along a front
```

This has ~4 tunable weights. The functional form comes from physics; only the weights are fit from data.

#### Tuning the weights

Simple grid search over w1-w4 on the training period (1981-2005), optimizing for spatial correlation r between `rain_likelihood` and observed pr. This is NOT model training — it's parameter tuning on a fixed functional form, the same kind of thing as tuning `NOISE_FACTOR_MULTIPLICATIVE` or `PR_WDF_THRESHOLD_FACTOR` in the existing pipeline.

#### Metrics
- **Spatial correlation r** between rain_likelihood and observed pr, averaged across days
- **Wet/dry classification accuracy** using a threshold on rain_likelihood
- Stratify by season (DJF, MAM, JJA, SON) and regime (clearly wet, marginal, dry days)

#### Advantages
- Simple, interpretable, consistent with the rest of the pipeline
- No overfitting risk with only 4 parameters
- Easy to integrate — the function runs inline during downscaling
- Easy to understand what's working and what isn't

#### Limitations
- Can only capture relationships we thought to encode
- Linear combinations may miss threshold interactions (e.g., "rain only when humidity AND lift are BOTH high")
- Limited to GridMET variables (no pressure, no wind components)

#### Script: `9-additional-pr-RMSE-fixes/scripts/phase3A_physics_function.py`

---

### TRACK B: Trained statistical model

Let a model learn the mapping from predictor variables to precipitation from data.

#### Method

For each day in 1981-2005:

1. Load the GridMET 4km fields for all available non-pr variables.
2. At each pixel, assemble the feature vector: tasmax, tasmin, DTR, huss, rmax, rmin, VPD, rsds, wind speed, cloud_proxy.
3. Also compute spatial gradient features: dT/dx, dT/dy, |grad(T)|, dhuss/dx, dhuss/dy, drsds/dx, drsds/dy.
4. The target is the observed pr field: both binary (wet/dry using 1mm threshold) and continuous (mm/day).

Train models pooled across all days:
- **Logistic regression** for wet/dry classification
- **Ridge regression** for pr amount (on wet pixels only)

If linear models show signal but limited skill, try **random forest** (captures nonlinear threshold interactions naturally). Do NOT jump to deep learning.

#### Metrics
- **Spatial correlation r** between predicted and observed pr fields, averaged across days
- **Wet/dry classification AUC and accuracy**
- **R-squared** for pr amount on wet days
- Stratify by season (DJF, MAM, JJA, SON) and regime (clearly wet, marginal, dry days)

#### Advantages
- Can discover relationships we didn't think of
- Naturally captures nonlinear threshold interactions (especially with tree-based models)
- Can optimize for exactly the metric we care about (spatial r)
- Can handle many predictors without manually specifying interactions

#### Limitations
- Overfitting risk (mitigated by train/validation split and simple models first)
- Black box — harder to understand what's driving the predictions
- Adds a trained model dependency to the pipeline (model artifacts, retraining concerns)
- More complex to integrate and maintain

#### Script: `9-additional-pr-RMSE-fixes/scripts/phase3B_trained_model.py` (Track B of Phase 3 — not to be confused with the old "Phase 3B")

---

### Shared: Stratify by season and regime

Both tracks report skill separately for:
- **DJF, MAM, JJA, SON** — physics predicts different predictability by precipitation type
- **"Clearly wet days"** (domain-mean pr > 2mm), **"marginal days"** (0.5-2mm), and **"dry days"** (<0.5mm)
- If summer skill is near zero but winter skill is meaningful, that's consistent with the physics (convective vs frontal) and the approach isn't dead — it just has a seasonal limit

### Shared: Validation plots (MANDATORY)

For the same 12 days selected in Phase 2, plot the predicted precipitation likelihood/field side by side with the observed pr field. This lets us visually verify the approach is doing something sensible. Also plot residuals (predicted - observed) for a few days — look for systematic spatial patterns in the errors.

**For Track A specifically:** also plot each individual term (moisture, instability, lift) alongside observed pr for a few days. This shows which ingredient is contributing what.

### Shared: How to interpret
- **r > 0.3 from observations:** Strong ceiling. Even with GCM degradation, there's a realistic path to useful skill. Proceed confidently.
- **r = 0.1-0.3:** Moderate ceiling. Proceed, but note this is the ceiling *without pressure and wind components*, so the real ceiling could be higher.
- **r < 0.1 even with gradients:** The variables GridMET provides (moisture + instability, no lift) aren't enough. **This does NOT kill the approach** — it means the LIFT ingredient (psl, uas/vas, MFC) may be where the signal lives. Phase 8 can still test this directly with GCM data.
- **Track A vs Track B comparison:** If Track B substantially outperforms Track A (e.g., r = 0.2 vs r = 0.1), the relationship is nonlinear and the physics function is missing important interactions. If they're similar, the physics function captures most of the signal and is the better choice (simpler, more interpretable).

### Shared: Data sources
- GridMET targets at 4km: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\gridmet_targets_19810101-20141231.dat` — shape (12418, 6, 216, 192), var index 0=pr, and others for the 6 pipeline variables.
- Additional GridMET variables (rmax, rmin, VPD): `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\GridMET\` — yearly NPZ files per variable. **All used here as observed truth at 4km.** Phase 3 only needs the GridMET side; whether each variable is Class 1 or Class 3a doesn't affect this phase.
- Geo mask: `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\geo_mask.npy`

### Shared: Output
- `9-additional-pr-RMSE-fixes/output/phase3_observation_ceiling.md` — r values for both tracks, comparison, interpretation, go/no-go
- `9-additional-pr-RMSE-fixes/output/phase3_ceiling_by_season.csv` — skill by season and regime for both tracks
- `9-additional-pr-RMSE-fixes/figures/phase3_ceiling/` — predicted vs observed plots for both tracks on the 12 selected days

---

## Phase 4: Interpolation fidelity test

**Goal:** For each candidate predictor variable, measure how much sub-cell spatial information survives the regrid-to-100km-then-interpolate-back-to-4km round trip. This tells us which variables are worth using as GCM-derived predictors. **This phase only tests Class 1 (GridMET-and-GCM) variables** (which have 4km ground truth). Class 2 (GCM-only) variables (psl, uas, vas) cannot be tested this way — see Phase 7 for how they're handled.

**Scope:** Phase 4 tests Class 1 (GridMET-and-GCM) variables only — variables that ARE in the pipeline and where the round-trip 4km→100km→4km test corresponds to a real pipeline operation. Class 3a (GridMET-only) variables (VPD, possibly rmax/rmin) are NOT tested here because they aren't pipelined: their 4km field is built by deriving from pipelined inputs in Phase 8, not by interpolating a coarse field. Their fidelity question is answered by Phase 5 instead.

### Physics-informed expectations
Based on the analysis above, expected ranking from best to worst interpolation fidelity (Class 1 only):
1. **tasmax, tasmin** — temperature is very smooth
2. **huss** — smooth, controlled by large-scale advection
3. **rmax, rmin** (if Class 1) — smooth but more responsive to local temperature variations
4. **rsds** — moderately smooth (cloud fields have more structure)
5. **wind speed** — moderately smooth but wind has more mesoscale structure than T or q
6. **pr** — worst (confirms direct interpolation of pr doesn't work)

### Method

For each variable available in GridMET at 4km:

1. Load the original 4km field for a given day.
2. Regrid to ~100km (average within GCM-sized cells, using MPI's 9x10 grid geometry).
3. Bilinear interpolate back to 4km.
4. Compare the interpolated field to the original:
   - **Pixel-level correlation** between original and round-tripped fields
   - **Gradient preservation:** correlation between the original spatial gradient and the round-tripped gradient
   - **Sub-cell variance explained:** what fraction of within-cell spatial variance is captured by interpolation

Average these metrics across many days (sample 100+ days across all seasons).

### Visualization (MANDATORY)

For 4 selected days (1 per season, use the frontal days from Phase 2), plot for each variable:
- **Left panel:** Original 4km field
- **Middle panel:** Round-tripped field (4km → ~100km → 4km)
- **Right panel:** Difference (original - round-tripped)

This shows exactly what information is lost. If the difference map looks like random noise, the large-scale gradient was captured. If the difference has coherent spatial structure (e.g., localized features that the round-trip smoothed away), that's real sub-grid information being lost.

Also overlay GCM cell boundaries on the round-tripped field so we can see the blocky interpolation structure.

### How to interpret
- Variables with pixel-level r > 0.9 after round-trip: interpolation is highly faithful. Safe to use as sub-grid predictors.
- Variables with r = 0.7-0.9: interpolation captures the broad gradient but misses details. Still useful with caveats.
- Variables with r < 0.7: too much information lost. Don't rely on sub-grid structure from interpolation for these.
- **Visual check:** if the difference map for pr looks like the precipitation field itself (all structure is lost), while the difference map for tasmax looks like low-amplitude noise (most structure is preserved), the visual contrast makes the case for using interpolated tasmax but not interpolated pr.

### Important notes
- Use the GCM's actual grid geometry (MPI's 9x10 over the Iowa crop) for the regrid step.
- Report results by season — temperature gradients may interpolate better in winter (stronger fronts) than summer.

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase4_interpolation_fidelity.py`

### Output
- `9-additional-pr-RMSE-fixes/output/phase4_interpolation_fidelity.md`
- `9-additional-pr-RMSE-fixes/output/phase4_fidelity_by_variable.csv`
- `9-additional-pr-RMSE-fixes/figures/phase4_fidelity/` — original vs round-tripped vs difference plots

---

## Phase 5: Class 3a derivation fidelity (vs GridMET 4km)

**Goal:** For each Class 3a variable (no GCM output, but 4km GridMET truth), test whether a simple physical formula can derive the variable from inputs we DO have, validated against GridMET at 4km. Each candidate gets a pass/conditional/fail verdict before it can be used as a predictor in Phase 8.

### Class 3a candidates

| Variable | Truth source | Inputs available to us | Derivation formula(s) to test |
|----------|-------------|------------------------|------------------------------|
| **VPD** (always Class 3a) | GridMET `vpd` | tasmax, huss, ps | Magnus equation: e_s(T) − e_a(huss, ps); test with tasmax vs tas, with/without ps |
| **rmax** (if MPI lacks hursmax) | GridMET `rmax` | tasmax, huss, ps | RH from Clausius-Clapeyron at tasmax with huss/ps |
| **rmin** (if MPI lacks hursmin) | GridMET `rmin` | tasmin, huss, ps | RH from Clausius-Clapeyron at tasmin with huss/ps |

The Phase 0 inventory determines whether rmax/rmin are Class 1 (pipelined) or Class 3a (handled here).

### Method

For each candidate:

1. **Inputs at GridMET 4km.** Take the GridMET-native versions of the input variables (e.g. GridMET tasmax, sph for huss). These are the cleanest 4km inputs we have. This decouples derivation error from upstream pipeline error.
2. **Apply the derivation formula** at 4km.
3. **Compare to the GridMET target field** pixel by pixel at 4km:
   - Pixel-level correlation across all days in the training period (1981-2005)
   - Bias (mean(derived) − mean(observed))
   - RMSE
   - Spatial r per day, then averaged across days
   - Seasonal breakdown
4. **Repeat using pipelined-DOR inputs** instead of GridMET inputs (apply the same formula to DOR-output tasmax/huss/ps). The drop in skill between (3) and (4) measures how much DOR's upstream errors hurt the derivation. **This second pass directly previews how Class 3a will perform when used in Phase 8.**

### Visualization (MANDATORY)

For 4 selected days (1 per season — reuse Phase 2's frontal/convective days where possible), plot for each derived variable a 4-panel figure:
- **Panel 1:** GridMET ground truth (4km)
- **Panel 2:** Derived field using GridMET inputs (formula error only)
- **Panel 3:** Derived field using DOR-pipelined inputs (formula + upstream error)
- **Panel 4:** Difference (panel 1 − panel 3)

A derivation that produces the right *spatial pattern* but a constant offset is fine — the offset is calibrated out. A derivation that produces the wrong pattern is dead.

### Decision rule

| Spatial r (vs GridMET, pipelined-input pass) | Verdict |
|---------------------------------------------|---------|
| > 0.85 | **Passes.** Use in Phase 8 with confidence. Document calibration constants. |
| 0.6 - 0.85 | **Conditional pass.** Use in Phase 8 but flag results. Try a more sophisticated formula. |
| < 0.6 | **Fails.** Drop. The simplified formula doesn't recover the variable from pipelined inputs. |

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase5_class3a_derivation.py`

### Output
- `9-additional-pr-RMSE-fixes/output/phase5_class3a_derivation.md` — verdicts per Class 3a variable
- `9-additional-pr-RMSE-fixes/output/phase5_class3a_by_variable.csv` — r, bias, RMSE per variable per season
- `9-additional-pr-RMSE-fixes/figures/phase5_class3a/` — 4-panel plots per variable per selected day

---

## Phase 6: Class 3b derivation fidelity (vs reanalysis)

**Goal:** For each Class 3b variable (no GCM output, no GridMET truth, only reanalysis truth at coarser resolution), test whether a simple physical formula can derive the variable from inputs we have, validated against the reanalysis at its native grid. Each candidate gets a pass/conditional/fail verdict before it can be used as a predictor in Phase 8.

**Key insight: resolution doesn't have to be 4km here.** Phase 6 is testing the *derivation formula*, not spatial detail. We work at the reanalysis's native resolution (~25 km for ERA5, ~32 km for NARR). Only after a derivation passes do we apply the formula at 4km on top of pipeline+bilinear inputs in Phase 8.

### Class 3b candidates

| Variable | Reanalysis source | Native res | Inputs available to us | Derivation formula(s) to test |
|----------|------------------|-----------|------------------------|------------------------------|
| **PWAT** | ERA5 `tcwv` | ~25 km | huss (Class 1, surface) | Surface-q × scale-height; calibrated regression huss → PWAT |
| **Theta-e (sfc)** | ERA5 / computed | ~25 km | tasmax, huss, ps | Direct Bolton (1980) formula |
| **CAPE (proxy)** | ERA5 `cape` | ~25 km | tasmax, huss, tasmin | Surface parcel CAPE assuming standard lapse rate; or huss×T product proxy |
| **CIN (proxy)** | ERA5 `cin` | ~25 km | tasmax, tasmin (DTR) | DTR-based stability proxy |
| **Lifted Index** | NARR / derived | ~32 km | tasmax, huss | T_500 from lapse rate + parcel theta-e |
| **K-index** | NARR / derived | ~32 km | tasmax, tasmin, huss | Reformulation using surface vars only |
| **Frontogenesis** | ERA5 / derived | ~25 km | tasmax, uas, vas (Class 1+2) | Petterssen frontogenesis from grad(T) and wind |

### Prerequisite: Acquire reanalysis data

This is the first time the project pulls from reanalysis. Coordinate with Bhuwan on storage location. Download covering Iowa for 1981-2014:
- **ERA5 daily**: tcwv, cape, cin, plus 2m temperature, 2m dewpoint, surface pressure, 10m winds. From Copernicus CDS. ERA5 daily for Iowa over 34 years is small (a few GB).
- **NARR daily**: lifted index, K-index, CAPE, plus standard surface variables. From NOAA/NCEP.

Crop to the Iowa domain. Save as memmaps or NPZ in `9-additional-pr-RMSE-fixes/data/reanalysis/`.

### Method

For each candidate:

1. **Inputs at reanalysis resolution.** Take the reanalysis-native versions of the input variables (e.g. ERA5 t2m, d2m, sp). These play the role of "what we'd have if we trusted our pipeline+bilinear outputs perfectly." This decouples derivation error from upstream input error.
2. **Apply the derivation formula** at the reanalysis grid.
3. **Compare to the reanalysis target field** at the same grid:
   - Pixel-level correlation across all days in the training period (1981-2005)
   - Bias, RMSE
   - Spatial r per day, then averaged across days (the metric most relevant to Phase 8)
   - Seasonal breakdown (especially summer for CAPE/CIN, winter for frontogenesis)
4. **Repeat using upscaled GridMET inputs** for the Class 1 components (averaged onto the reanalysis grid). The drop in skill between (3) and (4) measures how much input source matters.

### Visualization (MANDATORY)

For 4 selected days (1 per season — reuse Phase 2's frontal/convective days), plot for each derived variable:
- **Left panel:** Reanalysis ground truth
- **Middle panel:** Derived field (using clean reanalysis inputs)
- **Right panel:** Difference

A derivation that produces the right *spatial pattern* but a constant offset is fine. A derivation that produces the wrong pattern is dead.

### Decision rule

| Spatial r (vs reanalysis) | Verdict |
|--------------------------|---------|
| > 0.85 | **Passes.** Use in Phase 8 with confidence. Document calibration constants. |
| 0.6 - 0.85 | **Conditional pass.** Use in Phase 8 but flag results. |
| < 0.6 | **Fails.** Drop. |

**Important caveat carried into Phase 8:** Phase 6 validates the formula at the reanalysis grid using clean reanalysis inputs. A derivation that passes here may still produce a worse field at 4km in Phase 8 if the Class 1/2 inputs have errors the reanalysis inputs didn't. Phase 8's ablation group 6 measures this directly.

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase6_class3b_derivation.py`

### Output
- `9-additional-pr-RMSE-fixes/output/phase6_class3b_derivation.md` — verdicts per Class 3b variable
- `9-additional-pr-RMSE-fixes/output/phase6_class3b_by_variable.csv` — r, bias, RMSE per variable per season
- `9-additional-pr-RMSE-fixes/figures/phase6_class3b/` — reanalysis vs derived vs difference plots

---

## Phase 7: Acquire and verify Class 2 GCM variables

**Goal:** Get the Class 2 (GCM-only) variables (uas, vas, psl) onto the 4km grid and check that they're trustworthy enough to use in Phase 8. This is pure data-prep + sanity check — no prediction work yet.

### What to do

1. **Inventory.** Check `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa\Raw\` for uas, vas, psl. uas and vas are expected to be present. If psl is missing, download from CMIP6 archives.
2. **Bilinear regrid to 4km** using `scipy.interpolate.RegularGridInterpolator` with the same target grid as the existing 4km data. Save as a memmap or NPZ alongside the pipeline outputs.
3. **Wind speed magnitude check.** Compute sqrt(uas² + vas²) from the regridded GCM components and compare against GridMET wind speed (which is already in the pipeline). Compute pixel-r and bias spatially and temporally.
   - If r > 0.5: uas/vas are probably trustworthy enough for use as predictors.
   - If 0.3 < r < 0.5: usable but flag results that depend on them.
   - If r < 0.3: uas/vas are unreliable. Phase 8 should still try them (with the caveat) but expect noise.
4. **psl sanity plot.** No quantitative verification possible (no GridMET equivalent). Just generate a few daily snapshots and check the field looks like a real synoptic pressure pattern (smooth, plausible gradients, coherent highs/lows).

### Why a separate phase

The variables prepared here have **no 4km ground truth**, **no OTBC bias correction**, and **no interpolation fidelity test** (Phase 4 only tests Class 1 (GridMET-and-GCM) variables). They are fundamentally unverified — the wind-speed-magnitude check is the strongest validation possible. Doing this prep + verification cleanly before Phase 8 means Phase 8 can focus on prediction rather than data plumbing.

### Script location
`9-additional-pr-RMSE-fixes/scripts/phase7_class2_acquire_verify.py`

### Output
- `9-additional-pr-RMSE-fixes/data/class2_4km/uas_4km.npz`, `vas_4km.npz`, `psl_4km.npz` (or memmap equivalents)
- `9-additional-pr-RMSE-fixes/output/phase7_class2_verification.md` — wind magnitude check results, psl sanity verdict
- `9-additional-pr-RMSE-fixes/figures/phase7_class2/` — wind-magnitude scatter, psl daily snapshots

---

## Phase 8: GCM-derived prediction — combine all predictors

**Goal:** Test whether the full set of GCM-derived predictors — Class 1 (pipelined), Class 2 (bilinear, from Phase 7), Class 3a (derived from pipelined inputs, validated in Phase 5), and Class 3b (derived, validated in Phase 6) — improves precipitation prediction beyond what GridMET-available variables can do. This is where everything comes together to test the GCM-side ceiling.

### Two parallel tracks (continued from Phase 3)

Both tracks use the same predictor pool (Class 1 + Class 2 + Class 3a passed + Class 3b passed). Bhuwan picks which to run first.

---

### TRACK A: Physics-based function with GCM variables

Extend the Phase 3 Track A physics function to include the LIFT ingredient now that we have uas, vas, and potentially psl from Phase 7.

#### Extended functional form

```python
# Same moisture and instability terms as Phase 3 Track A, but now using
# GCM values (pipeline variables from CMIP6 inputs memmap)

# NEW: Lift term using actual wind/pressure data
wind_convergence = -(duas/dx + dvas/dy)  # positive = converging = uplift
MFC = -(d(huss*uas)/dx + d(huss*vas)/dy)  # moisture flux convergence

lift = w3a * normalize(wind_convergence)
     + w3b * normalize(MFC)
     + w3c * normalize(|grad(tasmax)|)  # frontal temperature gradient
     # + w3d * normalize(|grad(psl)|)   # if psl available

# Combined
rain_likelihood = w1 * moisture + w2 * instability + w3 * lift
                + w4 * moisture * lift
```

Now ~6-8 tunable weights. Still a simple grid search to tune.

#### Script: `9-additional-pr-RMSE-fixes/scripts/phase8A_physics_function_gcm.py`

---

### TRACK B: Trained model with GCM variables

Extend the Phase 3 Track B trained model to include all available GCM-derived features.

#### Method

Same as Phase 3 Track B, but:
1. Use **GCM input fields** (from CMIP6 inputs memmap, all pipeline-processed Class 1) instead of GridMET for the pipeline variables. This tests how much the GCM's imperfections cost.
2. Add **Class 2 GCM variables** from Phase 7: uas, vas, psl (regridded to 4km bilinearly).
3. Add **derived features**: MFC, wind convergence, pressure gradient.
4. Add **Class 3a derived variables that passed Phase 5**: VPD (always), and rmax/rmin if they ended up Class 3a. Computed at 4km from the pipelined Class 1 inputs.
5. Add **Class 3b derived variables that passed Phase 6**: e.g. CAPE proxy, PWAT, theta-e, lifted index, frontogenesis.

#### Model options (in order of preference)
1. **Logistic regression (wet/dry) + ridge regression (amount | wet)** — start here.
2. **Random forest** — try if linear models show signal but limited skill.
3. **Gradient-boosted trees** — try if random forest shows meaningful improvement.

#### Script: `9-additional-pr-RMSE-fixes/scripts/phase8B_trained_model_gcm.py`

---

### Shared: Ablation groups (both tracks)

Test these groups incrementally to identify where the signal comes from:
1. **Class 1 only (GCM side):** huss, tasmax, tasmin, rsds, wind, plus any newly-pipelined Class 1 variables from Phase 0 (+ gradients, derived features). Directly comparable to Phase 3 — the difference measures GCM degradation. **Does NOT include VPD or any other Class 3a variable** — those are only available via derivation, not pipeline.
2. **+ Class 2 wind components:** uas, vas, wind convergence
3. **+ MFC:** uas, vas, huss combined into moisture flux convergence
4. **+ Class 2 pressure:** psl, pressure gradient (if available)
5. **+ Class 3a derived variables:** VPD etc. derived from pipelined inputs. Adds the GridMET-validated derivations only.
6. **+ Class 3b derived variables:** add only the Class 3b variables that passed Phase 6.

**Interpretation:**
- If group 2/3 substantially outperforms group 1, the LIFT variables are the key contributors (consistent with physics).
- If group 5 outperforms group 4, the Class 3a derivations are paying off — strong result because they have 4km validation behind them.
- If group 6 outperforms group 5, the Class 3b reanalysis-validated derivations are also paying off despite coarse-resolution validation.
- If groups 1-6 are similar, the signal comes from moisture/instability (or there's no signal at all).

### Shared: Validation
- Train on 1981-2005. Validate on 2006-2014.
- **Stratify by season** (DJF, MAM, JJA, SON) — physics predicts winter/spring will show more skill than summer.
- Primary metric: spatial correlation **r** between predicted and observed pr fields, averaged across validation days.
- Secondary: RMSE, wet/dry classification AUC, bias.
- Compare against Phase 3 (same track) to quantify: (a) GCM degradation for pipeline variables, (b) value added by Class 2 / Class 3a / Class 3b inputs.

### Shared: Validation plots (MANDATORY)

For the same 12 days from Phase 2 (or the closest validation-period equivalents):
- Plot **predicted pr vs observed pr** side by side, for each ablation group. This visually shows what each ingredient adds.
- For Track A: plot each individual term (moisture, instability, lift, MFC) alongside observed pr.
- For Track B: plot **feature importance** as a bar chart (from tree-based model if used).
- Plot the **MFC field** overlaid with observed precipitation contours for the frontal days — this is the key visual test of whether wind convergence predicts rain location.

### Shared: Data sources
- CMIP6 inputs (already regridded to 4km): `\\abe-cylo\modelsdev\Projects\WRC_DOR\Spatial_Downscaling\test8_v2\Regridded_Iowa\MPI\mv_otbc\cmip6_inputs_19810101-20141231.dat`
- Class 2 4km fields: from Phase 7 outputs.
- Class 3a/3b derivation formulas: from Phase 5 / Phase 6 outputs.
- GridMET targets: same as Phase 3.
- Geo mask: same as Phase 3.

### Shared: Output
- `9-additional-pr-RMSE-fixes/output/phase8_gcm_prediction.md` — results for both tracks, ablation comparison, interpretation
- `9-additional-pr-RMSE-fixes/output/phase8_prediction_by_season.csv` — skill by season for both tracks and all ablation groups
- `9-additional-pr-RMSE-fixes/figures/phase8_prediction/` — predicted vs observed plots, ablation comparison, MFC overlay plots

---

## Phase 9: Integration into the pipeline

**Only proceed if Phase 8 shows r > 0.1 on the validation period for either track.**

### How to integrate — depends on which track succeeded

---

### TRACK A integration: Physics function in the noise step

The physics function produces a spatial field `rain_likelihood(pixel)` for each day. This modulates the noise step directly:

**Option A1: Bias the noise field**
```python
weather_signal = normalize(rain_likelihood)  # zero mean, unit variance
noise_field = alpha * weather_signal + (1 - alpha) * random_spatial_pattern
y_final = y_base * (1 + noise_field * cv_resid * nf)
```
Where alpha controls the blend (0 = current behavior, 1 = fully physics-driven). Sweep alpha in {0.1, 0.2, 0.3, 0.4, 0.5}.

**Option A2: Use physics function for wet/dry, noise for intensity**
```python
rain_prob = sigmoid(rain_likelihood)  # convert to 0-1 probability
wet_mask = rain_prob > threshold  # tunable threshold replacing current WDF logic
y_final = where(wet_mask, y_base * (1 + noise * cv_resid * nf), 0)
```

**Option A3: Seasonal switching**
```python
if season in ['DJF', 'MAM', 'SON']:  # frontal-dominant, physics function has skill
    use Option A1 or A2 with higher alpha
elif season == 'JJA':  # convective-dominant, physics function has less skill
    use Option A1 with lower alpha (or pure noise if summer skill is zero)
```

Advantages of Track A integration: the function runs inline during downscaling — no model artifacts, no serialized model files, just a formula with a few constants. Easy to maintain, easy to understand, easy to port.

---

### TRACK B integration: Trained model in the noise step

The trained model produces a spatial prediction field `p_rain(pixel)` for each day.

**Option B1: Blend prediction with noise** (same formula as A1 but using model output)
```python
weather_signal = normalize(model.predict(features))
noise_field = alpha * weather_signal + (1 - alpha) * random_spatial_pattern
y_final = y_base * (1 + noise_field * cv_resid * nf)
```

**Option B2: Use model for wet/dry, noise for intensity** (same as A2 but using model output)

**Option B3: Seasonal switching** (same as A3)

Additional complexity for Track B: the trained model must be serialized and loaded at runtime. If using tree-based models, this means shipping a pickled model file alongside the pipeline code.

---

### Shared: Validation plots (MANDATORY)

Before declaring success, produce the standard pipeline comparison plots:
- Time-mean spatial maps: GridMET vs DOR (with prediction) vs DOR (baseline, noise-only), for each of the three time periods (1981-2005, 2006-2014, 1981-2014). Look for: does the splotchiness improve? Do new artifacts appear?
- Distribution plots: QQ plots of predicted vs observed precipitation. Check that Ext99 is preserved.
- Spatial correlation time series: r per day, plotted over the validation period. Color by season. Look for: is the improvement concentrated in winter/spring (expected) or uniform?

### Shared: Re-calibration required
Any integration will change the precipitation distribution. Must re-tune:
- `PR_WDF_THRESHOLD_FACTOR` (wet-day frequency)
- `NOISE_FACTOR_MULTIPLICATIVE` (variance matching)
- `PR_INTENSITY_BLEND` (if the prediction partially handles what the blend was doing)

### Shared: Success criteria

| Metric | Requirement |
|--------|-------------|
| pr RMSE | Must improve by at least 0.3 (to <= 9.6) to justify the complexity. Target: < 8.64 (beat NEX). |
| pr Ext99 Bias% | Must stay within +/-2% of zero |
| pr WDF | Must stay within 2pp of observed (after re-tuning threshold) |
| pr Lag1 Err | Must not increase by more than 0.02 |
| All other variables | Must be unchanged (this only modifies the pr noise/prediction field) |

---

## Execution order

Each phase below is intentionally a bite-sized unit of work — small enough that an agent (or Cursor) can one-shot it, with one script and a handful of outputs.

1. **Phase 0 — EXPAND PIPELINE.** Inventory GridMET-observed variables not yet in the pipeline. For each, check whether MPI-ESM1-2-HR provides a daily GCM equivalent. Variables with a GCM equivalent (Class 1 / GridMET-and-GCM candidates — possibly rmax/rmin) get added to the pipeline (OTBC + regridding + stochastic downscaling). Variables WITHOUT a GCM equivalent (Class 3a / GridMET-only — definitely VPD, possibly rmax/rmin) are routed to Phase 5 for derivation. Requires Bhuwan's input on pipeline modifications for the Class 1 additions.

2. **Phase 1 — BASELINE METRICS.** Numerical baselines only (no plots) for all pipeline variables: full per-variable RMSE/KGE/Bias%/etc., spatial-r-with-pr by season, predictor-pr correlation by season. Establishes what the pipeline currently achieves.

3. **Phase 2 — VISUAL INSPECTION.** Plot predictor variables alongside observed precipitation for 12 representative days (3 per season). These same 12 days are reused by Phases 3, 5, 6, and 8 for consistency.

4. **Phase 3 — OBSERVATION CEILING.** Uses only GridMET data. Tests the MOISTURE + INSTABILITY ingredients. **Run both Track A (physics function) and Track B (trained model)** — the comparison tells us whether a simple physics function captures most of the signal, or whether learned nonlinearities matter. Includes validation plots on the 12 days from Phase 2.

5. **Phase 4 — INTERPOLATION FIDELITY.** Uses only GridMET data (Class 1: GridMET-and-GCM). Tests which variables retain sub-cell information after a coarsen-then-interpolate round trip. **Only tests Class 1 variables** — Class 2 (GCM-only) variables can't be verified this way and are handled in Phase 7.

6. **Phase 5 — CLASS 3a DERIVATION FIDELITY.** First appearance of Class 3a variables (VPD always; rmax/rmin if Phase 0 marks them Class 3a). Validate the derivation formula at 4km against GridMET, both with clean GridMET inputs and with pipelined-DOR inputs. Each candidate gets a pass/conditional/fail verdict before it can be used in Phase 8.

7. **Phase 6 — CLASS 3b DERIVATION FIDELITY.** First appearance of Class 3b variables (CAPE, CIN, PWAT, theta-e, lifted index, frontogenesis, etc.) — variables with reanalysis truth (ERA5/NARR) but no daily GCM output. Validate the derivation formula at the reanalysis's native ~25-32 km resolution. **Resolution is intentionally coarser than 4km here** because we're testing the formula, not spatial detail. Each candidate gets a pass/conditional/fail verdict.

8. **Phase 7 — ACQUIRE & VERIFY CLASS 2 GCM VARIABLES.** First appearance of Class 2 variables (uas, vas, psl) at 4km. Pure data-prep + sanity checking: bilinear regrid to 4km, wind-speed-magnitude check against GridMET, psl daily-snapshot sanity. No prediction work here — that's Phase 8.

9. **Phase 8 — GCM PREDICTION (full predictor set).** **Run both Track A and Track B.** The ablation study (6 groups) walks from Class 1 only → +Class 2 wind components → +MFC → +Class 2 pressure → +Class 3a derived → +Class 3b derived. Comparison to Phase 3 quantifies GCM degradation; the ablation isolates the marginal value of each predictor class.

10. **Phase 9 — INTEGRATION INTO PIPELINE.** Only if Phase 8 shows r > 0.1 on the validation period for either track. Pipeline integration using whichever track performed better (or Track A if similar, since it's simpler). Seasonal adaptation, re-tuning, and final validation plots.

## Relationship to PLAN-CROSS-VARIABLE-NOISE.md

That plan proposed blending weather information into the noise field at the GCM-cell scale. This plan subsumes it — if the multivariate sub-grid prediction works, it's a strictly better version of that idea. If Phases 0-8 fail, the cross-variable noise plan's Phase 0 diagnostic is also answered (no signal = both approaches dead).

## File organization

```
9-additional-pr-RMSE-fixes/
  PLAN-MULTIVARIATE-SUBGRID-PREDICTION.md     This file
  PLAN-CROSS-VARIABLE-NOISE.md                Superseded by this plan
  scripts/
    phase0_expand_pipeline.py                 Phase 0 — inventory + add Class 1 GridMET vars to pipeline
    phase1_baseline_metrics.py                Phase 1 — numerical baselines (no plots)
    phase2_visual_inspection.py               Phase 2 — predictor vs observed pr plots, 12 days
    phase3A_physics_function.py               Phase 3 Track A — physics-based function (GridMET only)
    phase3B_trained_model.py                  Phase 3 Track B — trained statistical model (GridMET only)
    phase4_interpolation_fidelity.py          Phase 4 — round-trip test (GridMET Class 1 only)
    phase5_class3a_derivation.py              Phase 5 — Class 3a derivation validation vs GridMET 4km
    phase6_class3b_derivation.py              Phase 6 — Class 3b derivation validation vs reanalysis
    phase7_class2_acquire_verify.py           Phase 7 — bilinear regrid uas/vas/psl + sanity checks
    phase8A_physics_function_gcm.py           Phase 8 Track A — physics function + all predictor classes
    phase8B_trained_model_gcm.py              Phase 8 Track B — trained model + all predictor classes
    phase9_integration.py                     Phase 9 — pipeline integration (only if Phase 8 succeeds)
  data/
    reanalysis/                               ERA5/NARR ground truth for Phase 6 (Iowa crop)
  figures/
    phase2_visual/                            12 days x 3 plot sets
    phase3_ceiling/                           Track A + B predicted vs observed plots
    phase4_fidelity/                          original vs round-tripped vs difference
    phase5_class3a/                           4-panel plots per Class 3a variable per selected day
    phase6_class3b/                           reanalysis vs derived vs difference (Class 3b)
    phase7_class2/                            wind-magnitude scatter, psl daily snapshots
    phase8_prediction/                        Track A + B predicted vs observed, MFC overlays
  output/
    phase0_variable_inventory.txt             All available variables (both sides), Class 1 vs 3a verdicts
    phase0_new_pipeline_validation.csv        Metrics for newly added pipeline variables
    phase1_baseline_metrics.csv               Full per-variable metrics
    phase1_spatial_r_by_season.csv            Spatial r per variable per season
    phase1_predictor_pr_correlation.csv       Predictor-pr correlation by season
    phase2_selected_days.csv                  12 selected dates with regime labels
    phase3_observation_ceiling.md             Phase 3 results (both tracks)
    phase3_ceiling_by_season.csv              Phase 3 data (both tracks)
    phase4_interpolation_fidelity.md          Phase 4 results
    phase4_fidelity_by_variable.csv           Phase 4 data
    phase5_class3a_derivation.md              Phase 5 verdicts per Class 3a variable
    phase5_class3a_by_variable.csv            Phase 5 r/bias/RMSE per variable per season
    phase6_class3b_derivation.md              Phase 6 verdicts per Class 3b variable
    phase6_class3b_by_variable.csv            Phase 6 r/bias/RMSE per variable per season
    phase7_class2_verification.md             Phase 7 wind magnitude check + psl sanity verdict
    phase8_gcm_prediction.md                  Phase 8 results (both tracks, all ablation groups)
    phase8_prediction_by_season.csv           Phase 8 seasonal data (both tracks)
```
