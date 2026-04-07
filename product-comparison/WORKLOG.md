# Product comparison — work log

Append-only audit trail. README summarizes usage; this file records **decisions and rationale**.

---

## 2026-04-06 — Charter

**Goal:** Benchmark the local PR-intensity **test8_v2** fork output (`PR_INTENSITY_BLEND=0.65`, `TEST8_SEED=42`) against **LOCA2** and **NEX-GDDP-CMIP6** (NASA) for **MPI-ESM1-2-HR**, using **GridMET targets** (same memmap as test8) as observations, on the **2006–2014** test window used in `V8_Table1_*` metrics.

**Non-goals:** Multivariate Schaake-style joint metrics on external products; modifying server files; claiming strict “method A beats method B” when products differ in BC, resolution, and construction.

**Self-containment:** All new code under `product-comparison/`; inputs are read-only from `\\abe-cylo\...` and `test8-v2-pr-intensity/`.

---

## 2026-04-06 — Blend verification (Step 0)

**Scoring rule (explicit):** For each blend folder with `V8_Table1_Pooled_Metrics_Stochastic.csv`, read **pr** row and compute  
`score = abs(Val_Ext99_Bias%) + 0.15 * Val_RMSE_pooled`  
(lower is better). This weights tail bias heavily but penalizes large RMSE. **Alternatives considered:** RMSE-only (parity wins; ignores tail goal); Ext99-only (ignores RMSE degradation).

**Result:** `scripts/verify_blend_choice.py` ranks **blend0.65** first on this score (see table at end of this file); canonical benchmark folder is **`experiment_blend0p65`**.

---

## 2026-04-06 — Spatial alignment

**Decision:** Interpolate external daily fields onto the **GridMET Iowa grid** defined by `lat`/`lon` in `Cropped_*_2006.npz` on the server (`Data/Cropped_Iowa/GridMET/`). Same 216×192 layout as DOR `Stochastic_V8_Hybrid_*.npz`.

**Rationale:** Metrics in `test8_v2_pr_intensity.py` are defined on that grid with `geo_mask.npy`. Regridding DOR outputs to LOCA’s native grid would discard the exact cells used internally.

**Alternatives rejected:** (1) Coarse common grid — loses comparability to published per-cell summaries. (2) Point-only comparison at one station — too narrow for pipeline validation.

**Implementation:** `xarray` linear `interp` onto a `lat`×`lon` mesh from `Cropped_pr_2006.npz`. LOCA2/NEX use **longitude 0–360°**; target longitudes are mapped to 0–360 for interpolation (`load_loca2.py`, `load_nex.py`).

---

## 2026-04-06 — Unit handling

- **pr:** LOCA2 and NEX report `kg m-2 s-1` → multiply by **86400** to match GridMET **mm/day** (and DOR npz).
- **tasmax, tasmin:** Kelvin — no conversion (matches cropped GridMET `tmmx`/`tmmn`).
- **rsds:** `W m-2` — no conversion vs `srad`.
- **sfcWind / vs:** treated as m/s; compare to GridMET `vs`.
- **huss / sph:** dimensionless humidity — no conversion.

---

## 2026-04-06 — Time alignment

- DOR npz `dates` are daily at **00:00**.
- NEX time coordinate uses **12:00** UTC — normalize with `pandas.to_datetime(...).normalize()` for merge.
- LOCA2 time checked similarly; slice **2006-01-01** through **2014-12-31** inclusive.

---

## 2026-04-06 — Disk cleanup

After `run_benchmark.py` succeeds, intermediate blend **`.npz`** under `test8-v2-pr-intensity/output/.../experiment_blend0p25|35|45|55/` and `experiment/` were removed; **CSV + run_manifest.json** retained. **parity/** and **experiment_blend0p65/** full outputs retained. Deletion list and byte counts recorded in the entry added on cleanup day.

---

## 2026-04-06 — Execution note

Run from repo root with conda env `drops-of-resilience`:

```text
python product-comparison/scripts/run_benchmark.py
python product-comparison/scripts/verify_blend_choice.py
```

Artifacts: `product-comparison/output/benchmark_summary.csv`, `figures/*.png`.

---

## 2026-04-07 — Benchmark run (completed)

**Executed:** `scripts/run_benchmark.py` with conda env `drops-of-resilience`. Runtime ~20 minutes dominated by LOCA2 single-file reads and `xarray.interp` over 2006–2014.

**Outputs checked:** `output/benchmark_summary.csv` — DOR vs LOCA2 vs NEX on six variables where data exist. LOCA2 has no `rsds` / `wind` / `huss` in this server tree, so those rows are `NaN` for LOCA2 (by design).

**Notable result:** NEX **rsds** shows a large mean bias vs GridMET (~37 W m⁻²) despite matching CF units on paper. **Decision:** treat as a **flag for follow-up** (subset plots, diurnal vs daily mean definitions, or local calibration), not as a final verdict — document in paper methods before leaning on that cell.

**Metrics warnings:** Earlier `Spatial_Bias` used `nanmean` on all-NaN planes for failed products; `metrics._spatial_bias` now returns quiet `NaN` in that case.

---

## 2026-04-07 — Local disk cleanup

Removed large `Stochastic_V8_Hybrid_*.npz` (and any `Deterministic_*.npz`) from intermediate PR-intensity blend folders under `test8-v2-pr-intensity/output/test8_v2_pr_intensity/` — **kept** `parity/`, `experiment_blend0p65/`, and all `V8_Table*.csv` + `run_manifest.json` in swept folders. **Rationale:** ~7 GB per full stochastic run; intermediate blends no longer needed after blend verification and benchmark. Server data untouched.

**Approx. freed:** 39,766,905,887 bytes (~37.0 GiB).

## 2026-04-06 — Blend verification result (script)

Rule: `score = abs(pr Ext99 bias %) + 0.15 * pr RMSE` (lower better).

| Rank | Run | Score | |Ext99| | RMSE |
|------|-----|-------|--------|------|
| 1 | blend0.65 | 1.6144 | 0.1278 | 9.9108 |
| 2 | blend0.55 | 2.3556 | 0.8791 | 9.8433 |
| 3 | blend0.45 | 3.3144 | 1.8477 | 9.7778 |
| 4 | blend0.35 | 4.2676 | 2.8104 | 9.7145 |
| 5 | blend1.0 | 4.7916 | 3.2756 | 10.1068 |
| 6 | blend0.25 | 5.2174 | 3.7694 | 9.6534 |
| 7 | parity | 7.7745 | 6.3475 | 9.5138 |

**Best by rule:** `blend0.65`. Benchmark still uses **blend0.65** per implementation plan.
