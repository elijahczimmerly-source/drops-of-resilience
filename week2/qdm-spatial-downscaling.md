# QDM produces spatial refinement — here's how

## The claim

Quantile Delta Mapping (QDM) can accomplish bias correction AND spatial downscaling in a single step. No separate downscaling method (e.g., delta-anomaly) is needed. This is not a novel technique — it follows directly from how QDM works — but it's easy to miss if you think of bias correction and downscaling as inherently separate steps.

## Why it works

QDM's formula at a given quantile τ:

```
corrected(τ) = obs_hist(τ) + [gcm_future(τ) − gcm_hist(τ)]
```

The key insight: **nothing in this formula requires obs_hist to be at the same spatial resolution as the GCM.** You can pair a coarse GCM cell with any finer-resolution observed dataset that overlaps it spatially.

A single 100km GCM cell covers many 4km observation grid cells (e.g., from PRISM). Each 4km cell has its own observed climate history and therefore its own CDF. When you run QDM, you run it independently at every fine-resolution cell:

- The **delta term** `[gcm_future(τ) − gcm_hist(τ)]` is identical for all fine cells within the same coarse GCM cell, because they all share the same overlapping GCM data.
- The **obs_hist(τ)** term is different at every fine cell, because each location has its own climate — a hilltop is colder than a valley.

So the corrected output differs spatially even though the GCM input is uniform. **The spatial detail comes from the observations. The climate change signal comes from the GCM. QDM combines them.**

This is conceptually the same thing delta-anomaly downscaling does — local observations plus a GCM-derived change — except QDM does it per-quantile instead of applying a single mean shift. QDM is therefore strictly more expressive than delta-anomaly for this purpose.

## Concrete example

### Setup

One GCM cell (100km) overlaps three observation locations at 4km resolution:

- **Hilltop** (620m elevation)
- **Plains** (340m elevation)  
- **River valley** (180m elevation)

### Input data

GCM historical (sorted, 6 values): `[16, 18, 21, 24, 27, 30]`
GCM future (sorted, 6 values):     `[20, 23, 26, 29, 33, 36]`

These are the SAME for all three locations — the GCM only has one cell here.

Per-quantile deltas (future − historical): `[+4, +5, +5, +5, +6, +6]`

Observed historical at each location (sorted):
- Hilltop: `[10, 12, 14, 16, 18, 20]`
- Plains:  `[14, 16, 18, 20, 22, 24]`
- Valley:  `[16, 18, 20, 22, 24, 26]`

Notice the hilltop runs ~4–6°C cooler than the valley. This spatial variation is real and comes from the observations.

### Applying QDM at each location

At each location, for each rank position: `corrected = obs + delta`

**Hilltop:**
```
obs:       [10, 12, 14, 16, 18, 20]
delta:     [+4, +5, +5, +5, +6, +6]
corrected: [14, 17, 19, 21, 24, 26]
```

**Plains:**
```
obs:       [14, 16, 18, 20, 22, 24]
delta:     [+4, +5, +5, +5, +6, +6]
corrected: [18, 21, 23, 25, 28, 30]
```

**Valley:**
```
obs:       [16, 18, 20, 22, 24, 26]
delta:     [+4, +5, +5, +5, +6, +6]
corrected: [20, 23, 25, 27, 30, 32]
```

### The result

The GCM input was one coarse cell. The output is three distinct fine-resolution time series. The hilltop's corrected rank-1 value is 14°, the valley's is 20° — a 6° spatial difference that the GCM never knew about. That's spatial downscaling.

No separate downscaling step was needed. No delta-anomaly. No interpolation. QDM did it all because the observations carried the spatial information.

## The remaining limitation

The delta row `[+4, +5, +5, +5, +6, +6]` is identical at all three locations. In reality, the hilltop might warm faster than the valley (due to elevation-dependent warming, snow-albedo feedback, etc.), but the GCM can't resolve that — it's one cell. This is the **spatial uniformity problem**, and it exists for delta-anomaly downscaling too. It's a GCM resolution limitation, not a QDM limitation.

## Why this matters for pipeline design

If QDM handles both bias correction and downscaling:
1. The pipeline is simpler (one step instead of two).
2. There's no risk of double-counting the climate change signal (which happens if you do QDM and then delta-anomaly, since both extract a GCM delta).
3. You get per-quantile signal preservation, which delta-anomaly alone doesn't provide.

The only tradeoff is computational cost — running QDM at every fine grid cell requires building CDFs everywhere, whereas delta-anomaly computes one mean delta per coarse cell. For a state-scale project this cost is real but manageable.
