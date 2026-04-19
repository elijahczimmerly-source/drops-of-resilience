# Native suite vs `dor_native`: benchmark metric shifts (test8_v4)

This note summarizes **systematic differences** between evaluation on the **GridMET-target** suite (`dor_native`) and the **LOCA2 native** / **NEX native** suites, using the saved CSV outputs:

- `dor_native/benchmark_summary_test8_v4.csv` (rows use legacy label `gridmet_4km`; equivalent to `dor_native`)
- `loca2_native/benchmark_summary_test8_v4_loca2_native.csv`
- `nex_native/benchmark_summary_test8_v4_nex_native.csv`

Pipeline ID throughout: **`test8_v4`**.

---

## How to read cross-suite differences

- **`dor_native`**: Validation on the **216×192 GridMET** mesh; GridMET is the observation field on that grid.
- **`loca2_native` / `nex_native`**: Fields (including GridMET “obs”) are aligned onto **LOCA2’s** or **NEX’s** native Iowa subset grid; see `SUITES.md` and `WORKLOG_NATIVE_RESOLUTION.md`.

**Absolute metric levels are not strictly comparable** across suites: shifts mix real skill differences with **regridding, domain footprint, and how extremes behave under interpolation**.

---

## DOR (test8_v4): changes vs `dor_native`

### Precipitation (`pr`)

| Metric | `dor_native` | `loca2_native` | Δ | `nex_native` | Δ |
|--------|----------------|----------------|-----|--------------|-----|
| KGE | 0.02240 | 0.02297 | +0.00057 | 0.02370 | +0.00130 |
| RMSE (mm/d) | 9.982 | 9.942 | −0.040 | 9.890 | −0.092 |
| Ext99 bias % | +1.410 | +1.026 | −0.38 | +0.702 | −0.71 |
| Lag1 error | 0.05523 | 0.05487 | −0.00036 | 0.05331 | −0.00192 |
| WDF Obs % | 32.317 | 32.817 | +0.50 | 33.114 | +0.80 |
| WDF Sim % | 32.322 | 34.005 | +1.68 | 34.575 | +2.25 |

**Interpretation:** The **largest DOR shifts** are **wet-day frequency**: **simulated WDF** rises **~1.7–2.3 percentage points** on native grids vs the GridMET mesh, with **observed WDF** also **~0.5–0.8 pp** higher. **Ext99 bias** moves **~0.4–0.7 points** toward zero (more “centered” on native meshes). **RMSE** improves slightly; **KGE** ticks up by **~0.0006–0.0013** (small in absolute terms).

---

### Shortwave (`rsds`) — DOR

| Metric | `dor_native` | `loca2_native` | Δ | `nex_native` | Δ |
|--------|----------------|----------------|-----|--------------|-----|
| KGE | 0.76423 | 0.76439 | +0.00016 | 0.76473 | +0.00050 |
| RMSE (W m⁻²) | 56.579 | 56.538 | −0.041 | 56.483 | −0.096 |
| Bias | −0.420 | −0.421 | −0.001 | −0.433 | −0.013 |
| Ext99 bias % | +0.810 | +0.798 | −0.012 | +0.784 | −0.026 |
| **Lag1 error** | **0.003887** | **0.003710** | **−0.00018** | **0.002935** | **−0.00095** |

**Interpretation:** Pooled KGE/RMSE/bias/Ext99 move only a little. **Lag-1 error falls a lot in relative terms** on **`nex_native`**: about **0.00389 → 0.00294 (~−25% of the error metric)**. That is the clearest **non-PR** DOR change that stands out numerically.

---

### Wind (`wind`) — DOR

| Metric | `dor_native` | `loca2_native` | Δ | `nex_native` | Δ |
|--------|----------------|----------------|-----|--------------|-----|
| KGE | 0.08013 | 0.07978 | −0.00035 | 0.07844 | −0.00169 |
| RMSE | 2.218 | 2.216 | −0.002 | 2.215 | −0.004 |
| Ext99 bias % | −7.380 | −7.552 | −0.17 | −7.601 | −0.22 |
| Lag1 error | 0.05221 | 0.05209 | −0.00012 | 0.05385 | +0.00164 |

**Interpretation:** **KGE** dips **~0.002** on **`nex_native`** vs GridMET (small absolute change but visible). Lag1 **worsens slightly** on **nex** vs **dor_native**. Overall: **minor, mixed**—not on the same scale as PR WDF or rsds Lag1.

---

### `tasmax`, `tasmin`, `huss` — DOR

Changes are **small** across suites (KGE/RMSE typically **≤ ~0.01** in temperature RMSE; Ext99 **≤ ~0.02 percentage points**; Lag1 **≤ ~0.0002**). Example: **tasmin** RMSE **7.063 → 7.054** on **`nex_native`** (**−0.01**). Nothing here jumps out like PR or rsds Lag1.

---

## External products: LOCA2 and NEX vs `dor_native`

### LOCA2 (`pr` only in these summary tables)

Comparing **LOCA2 on GridMET** (`dor_native`) to **LOCA2 on its native grid** (`loca2_native`) and to the **nex_native** run (LOCA2 interpolated to the NEX grid for that benchmark row):

| Metric | `dor_native` | `loca2_native` | Δ | `nex_native` | Δ |
|--------|----------------|----------------|-----|--------------|-----|
| KGE | 0.02274 | 0.02294 | +0.00020 | 0.02291 | +0.00017 |
| RMSE | 9.473 | 9.495 | +0.022 | 9.457 | −0.016 |
| Ext99 bias % | −4.609 | −3.900 | +0.71 (toward 0) | −4.338 | +0.27 |
| Lag1 error | 0.06623 | 0.07665 | +0.0104 | 0.07688 | +0.0107 |
| WDF Sim % | 31.235 | 29.572 | −1.66 | 32.142 | +0.91 |

**Interpretation:** **Ext99** for LOCA2 **PR** is **less negative** on **`loca2_native`** (~**+0.7 pp** vs GridMET mesh)—a **material** change for that metric. **Lag1 error worsens ~0.01** on native-grid evaluations vs `dor_native`. **WDF Sim** on **`loca2_native`** is **~1.7 pp lower** than on GridMET—large **relative** to typical WDF gaps used for DOR tuning.

### NEX (`pr` — full columns on `dor_native` and `nex_native` only)

| Metric | `dor_native` | `nex_native` | Δ |
|--------|----------------|--------------|-----|
| KGE | 0.00165 | 0.00270 | +0.00105 |
| RMSE | 8.640 | 8.643 | +0.003 |
| Ext99 bias % | −25.32 | −25.06 | +0.26 |
| Lag1 error | 0.04344 | 0.05520 | +0.0118 |
| WDF Sim % | 37.343 | 36.802 | −0.54 |

**Interpretation:** NEX **PR** metrics are **mostly stable** across meshes except **Lag1 error**, which **degrades ~0.012** on **`nex_native`** vs evaluating NEX interpolated to GridMET in `dor_native`.

For **tasmax**, **tasmin**, **rsds**, **wind**, **huss**, NEX values in `dor_native` vs `nex_native` differ only at the **roughly 1e-2–1e-3** level for RMSE/KGE—**not** large in the same sense as PR WDF or LOCA2 PR Ext99/Lag1.

---

## `loca2_native` vs `nex_native` (both vs `dor_native`)

- **`loca2_native` CSVs have no NEX columns** (only DOR + LOCA2 on the LOCA2 grid). Cross-product ranking on that suite is **DOR vs LOCA2** only in the saved table.
- **`nex_native`** includes **all three** products; the **largest cross-suite story** for competitors is still **LOCA2 PR** (Ext99, Lag1, WDF Sim) and **NEX PR** (Lag1).

---

## Summary: largest suite effects

1. **DOR `pr`:** **WDF (obs & sim)** shifts **~0.5–2.3 pp** depending on suite—the **largest suite effect** for the DOR product in these tables. **Ext99%** moves **~0.4–0.7 points** toward zero on native grids; **RMSE** improves slightly.
2. **DOR `rsds`:** **Lag-1 error** drops **markedly** on **`nex_native`** (~**25%** relative reduction)—standout among non-PR variables.
3. **DOR `wind`:** Small **KGE** dip on **`nex_native`**; otherwise minor.
4. **LOCA2 `pr`:** **Ext99**, **Lag1**, and **WDF Sim** show **substantial** changes vs GridMET evaluation—**grid choice matters a lot** for how LOCA2 looks vs obs in this benchmark.
5. **NEX `pr`:** Mostly stable except **Lag1**, which **worsens** when evaluated on **`nex_native`** vs interpolating NEX to GridMET in `dor_native`.

### Other pipeline IDs

For **test8_v2** / **test8_v3**, the **suite-induced pattern for non-PR DOR rows** matches **v4** (same numbers for temperature, rsds, wind, huss in the CSVs where applicable). **PR Ext99** differs a lot between pipelines (e.g. v2 parity vs v4 blend); **WDF-level shifts** with suite are **similar in spirit** to v4. See `benchmark_summary_test8_v2*.csv` and `benchmark_summary_test8_v3*.csv` under each suite folder.

---

## What native suites add for **evaluating DOR** (beyond GridMET)

This section answers: **What did we learn from benchmarking at LOCA2 and NEX native resolutions that we did not already know from benchmarking at GridMET—and what is useful for judging our product?**

### What GridMET (`dor_native`) already answers

On the **Iowa GridMET grid**, with **GridMET as truth**, the benchmark shows how DOR, LOCA2, and NEX compare **for the use case tied to that observational product** (Iowa, daily fields, pooled metrics). That remains the **primary** evaluation: it matches the forcing many Iowa workflows use.

### What LOCA2 / NEX native suites add (one sentence)

They check whether **that competitive story still holds** when everyone is scored on **their** native Iowa grid, using the **same GridMET-based truth remapped** onto that grid. The question is not “which product is objectively best everywhere,” but **“Do our strengths and weaknesses vs LOCA2 and NEX change when we stop forcing everyone onto the 4 km GridMET mesh?”**

### Useful takeaways

1. **Main conclusions are stable.** Across suites, the **large** patterns **do not reverse**: for **PR**, archives still **beat DOR on pooled RMSE**; DOR still **beats them on extreme-rain bias (Ext99)** in the sense of being much closer to zero. For **other variables**, the broad ranking vs NEX (where all six vars exist) **does not flip** in a way that would overturn the GridMET narrative.

   **Useful meaning:** The GridMET benchmark was not a one-off artifact of “everything interpolated to 4 km.” When evaluation moves to **~6 km (LOCA2)** or **~25 km (NEX)**, the **same qualitative picture** still appears on the metrics that matter most in project reporting (especially **PR extremes vs RMSE**).

2. **Fragile metrics are identified.** The only clear **rank reversals** vs competitors are **tiny** (PR **KGE** vs LOCA2) or **easy to distort** (PR **Lag-1** vs NEX when the grid changes).

   **Useful meaning:** Do **not** lean on **PR KGE** or **PR Lag-1** as definitive proof of superiority or inferiority—grid effects can swamp them. **Do** lean on **large, stable** contrasts (**Ext99** for PR; **RMSE** ordering for PR) because they **did not** flip across suites.

3. **Practical framing for reviewers.** LOCA2 and NEX are often discussed on **their** grids. Native suites approximate: **“If we compare on their geometry, does DOR still look like the same kind of product relative to them?”**

   **Useful meaning:** You can say you checked **robustness under a common alternative framing** (native archive geometry); the **qualitative** comparison **did not fall apart**—even though **absolute numbers** must not be mixed across suite rows as if they were one scale.

4. **What native suites do *not* replace.** Truth on those runs is still **GridMET remapped** to LOCA2 or NEX grids, **not** LOCA2’s or NEX’s own native observational targets (e.g. Livneh, GMFD).

   **Useful meaning:** Native suites are a **robustness check on relative performance vs those archives under remapped GridMET truth**, not validation against **their** training/obs products. That is the right expectation for **product comparison**; a different study would be needed to validate against **their** obs.

### Short bottom line

- **From GridMET:** how DOR stacks up **for Iowa GridMET users**.
- **From native suites:** the **same headline story mostly holds** when the scoring grid matches LOCA2 or NEX better; **fragile metrics are flagged**; **strong conclusions** (especially PR: they win RMSE, we win extremes) **do not depend** on evaluating only on the 4 km mesh.

That **stability** is the main **new, useful** result for **evaluating DOR**—not a new magic score, but **confidence that the headline GridMET comparison is not a mesh-only artifact.**

---

*Generated from repository CSVs; update this file if benchmark summaries are regenerated.*
