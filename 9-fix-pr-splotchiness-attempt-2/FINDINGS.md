# PR texture: LOCA2 vs DOR vs GridMET (historical 1981–2014)

**Generated from:** [`scripts/pr_texture_investigation.py`](../6-product-comparison/scripts/pr_texture_investigation.py)  
**Data:** Aligned stacks from [`load_multi_product_historical('pr')`](../6-product-comparison/scripts/benchmark_io.py) — same inner-joined calendar for GridMET, S3 `cmip6_inputs`, DOR test8_v2/v3/v4, LOCA2, NEX.

**Note on dates:** Analysis uses **`HIST_START` / `HIST_END`** (1981-01-01 … 2014-12-31), **12,418 days**. If you referred to **1982–2014**, subtract one year from the mental model; conclusions are unchanged qualitatively.

---

## 1. Domain–time means (clarifies the “2.501 vs 2.396” confusion)

| Product | Mean pr (mm/day) | Wet-day fraction (% days &gt; 0.1 mm) |
|---------|------------------|----------------------------------------|
| GridMET | **2.396** | 38.2 |
| LOCA2 | **2.351** | 31.6 |
| DOR test8_v4 | **2.501** | 32.7 |
| DOR test8_v3 | 2.500 | 36.3 |
| DOR test8_v2 | 2.319 | 32.6 |
| S3 cmip6_inputs | 2.534 | 52.2 |
| NEX | 2.315 | 37.9 |

**Takeaway:** **2.396 mm/day is GridMET**, not LOCA2. **LOCA2 is drier in the domain–time mean (2.35) than GridMET (2.40) and slightly drier than DOR v4 (2.50).** So the earlier verbal comparison “v4 vs 2.396” was **v4 vs GridMET**, not v4 vs LOCA2. DOR v4 is **wetter than both** GridMET and LOCA2 on this pooled mean — consistent with **more localized “spots” of higher rain** contributing to the mean without necessarily matching large-scale gradients.

**Attempt 2 (archived):** `PR_INTENSITY_BLEND=0.62` + `DOR_RATIO_SMOOTH_SIGMA=1` produced **~2.49 mm/day** pooled mean (slightly closer to GridMET than v4 on paper) but **multipanel pr maps looked the same as v4** — see [`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md). Not pursued in the production pipeline.

Full table: [`domain_time_means_pr.csv`](./domain_time_means_pr.csv).

---

## 2. Spatial pattern fidelity vs GridMET (time-mean maps)

Metrics are computed on **seasonal or full-period mean fields** `E[pr | season]`, spatially over 216×192.

### Correlation with GridMET (`r_vs_gridmet`)

- **DJF:** LOCA2 **0.992** ≈ DOR v2 **0.992**; DOR v3/v4 **~0.990** (slightly lower).
- **MAM:** LOCA2 **0.956** vs DOR v3/v4 **~0.959** — similar ballpark; **v2 higher (0.972)**.
- **JJA:** **LOCA2 0.842** vs DOR v3 **0.901** / v4 **0.900** — **DOR actually higher r** than LOCA2 this season; LOCA2 **lower RMSE** vs GridMET here (see CSV).
- **SON:** LOCA2 **0.940** vs DOR v3 **0.919** / v4 **0.918** — LOCA2 wins on r.
- **Full 1981–2014:** LOCA2 **0.978** vs DOR v4 **0.983** — **DOR v4 slightly higher** linear correlation than LOCA2 on the **single** full-period mean map.

So the narrative “LOCA2 always looks more like GridMET” is **not** uniformly true in **linear correlation** on these means: it **depends on season**, and **full-period r** can favor DOR.

### RMSE vs GridMET (`rmse_vs_gridmet_mm_day`)

- **Full:** LOCA2 **0.09** mm/day vs DOR v4 **0.15** — **LOCA2 lower RMSE** (closer pointwise to GridMET on the mean map).
- **MAM / SON:** DOR v3/v4 RMSE **~0.17–0.31** vs LOCA2 **~0.17–0.24** — **LOCA2 often lower RMSE** in shoulder seasons.

So **pointwise closeness to GridMET** on the mean map often favors **LOCA2**, even when **r** is mixed — matching the **visual** “smoother, gradient-like” impression versus **DOR’s speckle** (local deviations that don’t cancel in RMSE).

Full metrics: [`time_mean_map_metrics_pr.csv`](./time_mean_map_metrics_pr.csv).

---

## 3. “Splotchiness” — gradient and high-frequency proxies

| Season (full / typical) | LOCA2 vs DOR v4 `mean_grad_mag` | DOR v4 `high_freq_power_frac` (r≥20) vs GridMET |
|-------------------------|----------------------------------|--------------------------------------------------|
| full | LOCA2 **0.015** vs DOR v4 **0.025** | DOR **higher** HF fraction than LOCA2 (0.014 vs 0.004) |
| DJF | 0.015 vs 0.027 | DOR higher HF vs LOCA2 |
| MAM | 0.021 vs 0.045 | DOR much higher HF |

**Interpretation:**

- **DOR v3/v4** show **larger mean gradient magnitude** and **more spectral power at higher radial wavenumbers** (proxy: fraction of 2D FFT power at **r ≥ 20** in grid units) than **LOCA2**, and often **more than GridMET** on the same mean field.
- **NEX** has the **lowest** gradients and HF fraction here — consistent with **yearly NC + interpolation** smoothing.
- **S3** is **smoother** than obs in HF — driving field is not the sole source of DOR’s speckle; **downscaling + noise** adds variance.

**True culprits (combined):**

1. **LOCA2 pipeline:** Native LOCA2 fields are **regridded with `xarray.interp`** to the target grid ([`load_loca2.py`](../6-product-comparison/scripts/load_loca2.py)), which **acts as a low-pass filter** and aligns with **visually smoother** gradients.
2. **DOR pipeline:** **Stochastic** multiplicative noise, **OTBC**, **Schaake**, and (v3/v4) **PR intensity ratio** **preserve/inject fine-scale variance** by design — **not a bug**, but it **increases** local maxima and gradient energy vs a smoothed product.
3. **Plots:** [`plot_comparison_driver.py`](../6-product-comparison/scripts/plot_comparison_driver.py) uses **independent 2–98% color scales per panel** (`_vmin_vmax_one` per field), which **amplifies perceived** differences between products.

---

## 4. Optional next steps

- **`DOR_RATIO_SMOOTH_SIGMA` &gt; 0** in [`_test8_sd_impl.py`](../pipeline/scripts/_test8_sd_impl.py): Gaussian smooth on calibrated **spatial ratios** — **Attempt 2** (`sigma=1`, blend 0.62) did **not** improve visible texture vs v4 ([`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md)); further sweeps would be a new experiment.
- **Shared vmin/vmax** across GridMET / LOCA2 / DOR for the **same** figure — fairer **visual** comparison (optional CLI flag on the plot driver).
- **Spectral comparison** to S3-only mean map to separate **GCM-scale** structure from **downscaling** variance.

---

## 5. Bottom line

- **LOCA2** tracks GridMET **closely in RMSE** on many seasonal **mean** maps and looks **smoother** because of **algorithm + bilinear regrid to 4 km**.
- **DOR v3/v4** are **rougher** (higher gradients / HF proxy) by construction; **domain–time mean pr** is **higher than both GridMET and LOCA2**, consistent with **more intense localized rain** in the pooled average.
- **Correlation** vs GridMET is **season-dependent**; **do not** infer “LOCA2 always wins” from **r** alone — use **RMSE**, **gradients**, and **fair color scales** together.

## 6. Attempt 2 archive (blend 0.62 + ratio smooth σ=1)

Documented in [`NEGATIVE_RESULT_ATTEMPT2.md`](./NEGATIVE_RESULT_ATTEMPT2.md): **no visible map improvement** vs v4; production comparison plots remain **v2 / v3 / v4** only.
