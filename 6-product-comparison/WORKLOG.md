# Product comparison — work log

Append-only audit trail. README summarizes usage; this file records **decisions and rationale**.

---

## 2026-04-14 — End-to-end run (local D: cache + shared DOR NPZs)

**Fixed:** `run_benchmark._figures` missing `pipeline_id` argument (NameError).

**Batch benchmark:** `DOR_BENCHMARK_SHARED_NPZ_ROOT=D:\drops-resilience-data\dor_npz\shared_benchmark` — `benchmark_summary_test8_v2.csv` / `v3` / `v4` + KGE/Ext99 PNGs (three runs use the same v8_2 NPZ mirror; metrics identical per ID).

**Climate signal:** `run_climate_signal_stages.py` respects `DOR_BENCHMARK_SHARED_NPZ_ROOT` for S4 DOR rows; outputs `climate_signal_by_stage.csv`, `climate_signal_preservation.csv`.

**Extended diagnostics:** `stage_diagnostics_extended.csv` (133 rows).

**Plots:** `plot_climatology_comparisons.py` (six `clim_mean_*_1981_2014.png`); `plot_validation_period.py` with `DOR_PRODUCT_ROOT` → shared NPZ (validation side-by-side + TS).

**LOCA2:** `load_loca2.py` — crop time/lat/lon **before** `pr×86400`; time-chunked interp (`DOR_LOCA2_TIME_CHUNK`, default 48) + float32 output to avoid multi‑GB allocations on full-historical loads.

**Multi-product plots:** `plot_comparison_driver.py --all` completed (~31 min) — `output/figures/4km_plots/hist_1981_2014/`, `validation_2006_2014/`, `delta_future_minus_hist/`, and `index.html`.

---

## 2026-04-14 — Memory: memmap slicing + float32 stacks

**Issue:** Scripts were materializing entire CMIP6 / GridMET memmap time axes as float64 (~4+ GB per stack) before date masking.

**Changes:** [`load_obs.py`](scripts/load_obs.py) and [`climate_signal_io.load_cmip6_variable`](scripts/climate_signal_io.py) slice the memmap to the requested **day index range** first; stacks are **float32** where returned from these loaders. [`plot_climatology_comparisons._mean_s3_cmip6`](scripts/plot_climatology_comparisons.py) computes the time mean in **chunks** without allocating the full timeline. [`plot_comparison_driver.py`](scripts/plot_comparison_driver.py) calls `gc.collect()` after each variable.

**If RAM is still tight:** run `plot_comparison_driver.py` with a subset, e.g. `--vars pr,tasmax`, or close other apps; multi-product alignment still holds several large arrays at once by design.

---

## 2026-04-13 — Local WRC_DOR cache on D: (memmaps + GridMET crop NPZ)

Robocopied from `\\abe-cylo\modelsdev\Projects\WRC_DOR\` into **`D:\drops-resilience-data\WRC_DOR_cache\`** (same subpaths as the server): `Spatial_Downscaling/test8_v2/Regridded_Iowa/` (`gridmet_targets_*.dat`, `geo_mask.npy`), `MPI/mv_otbc/` (`cmip6_inputs_19810101-20141231.dat`, `cmip6_inputs_ssp585_20150101-21001231.dat` only — **not** the large `cmip6_inputs_18500101-19801231.dat`), and `Data/Cropped_Iowa/GridMET/Cropped_pr_2006.npz`.

[`config.py`](config.py) prefers this tree when files exist (`DOR_LOCAL_WRC_CACHE` override, `DOR_CROPPED_GRIDMET_DIR` optional). Env vars `DOR_TEST8_*` still win when set.

---

## 2026-04-13 (later) — Plot driver + extended diagnostics table

**`scripts/plot_comparison_driver.py`** — Parameterized figures under `output/figures/4km_plots/`: `hist_1981_2014/` (full overlap with GridMET targets), `validation_2006_2014/` (benchmark window), `delta_future_minus_hist/` (S3, DOR test8_v2/v3/v4, LOCA2, NEX), plus `index.html`. Independent 2–98% color scales per panel. CLI: `--hist`, `--val`, `--delta`, or `--all` (default runs all).

**`scripts/benchmark_io.py`** — `load_multi_product_historical` / `load_multi_product_validation` align GridMET, optional S3 `cmip6_inputs`, DOR outputs for each `DOR_DEFAULT_OUTPUTS` pipeline, LOCA2 (where applicable), and NEX on a common calendar.

**`scripts/extended_stage_diagnostics.py`** — Tidy long-form `stage_diagnostics_extended.csv`: pooled variance, P01/P99, WDF (pr), lag-1 and seasonal range on domain-mean series, KGE vs GridMET for S3/DOR/LOCA2/NEX where applicable.

**S1/S2 coarse stacks:** Still deferred pending confirmed daily file layout under `Data/Cropped_Iowa/` (see earlier entry).

---

## 2026-04-13 — Climate signal, multi-pipeline benchmark, Bhuwan alignment

**Normative examples:** New loaders and signal math were checked against [`scripts/Bhuwan/Compare_All_Signals_Iowa_Parallel.py`](scripts/Bhuwan/Compare_All_Signals_Iowa_Parallel.py) (domain signal: **pr** as relative % change, other vars as absolute Δ; 1981–2014 baseline vs 2015–2044 future slice) and [`scripts/Bhuwan/crop_loca2_iowa_MPI.py`](scripts/Bhuwan/crop_loca2_iowa_MPI.py) (LOCA2 **×86400** for pr, lon 0–360°, Iowa buffer + `xarray.interp` to GridMET lat/lon).

**Config:** [`config.py`](config.py) adds `HIST_*`, `SIGNAL_*` windows, `CMIP6_HIST_DAT` / `CMIP6_FUTURE_DAT`, `NEX_FILE_PATTERN_SSP585`, `DOR_DEFAULT_OUTPUTS` for **test8_v2/v3/v4**, and figure roots `FIG_BY_*` / `FIG_4KM_PLOTS`.

**Scripts:**
- [`run_climate_signal_stages.py`](scripts/run_climate_signal_stages.py) → `output/climate_signal_by_stage.csv`, `climate_signal_preservation.csv` (S3↔S4 **r** / **RMSE** on Δ maps when DOR future NPZs exist). Use `--skip-dor` if only memmaps + externals.
- [`batch_benchmark_pipelines.py`](scripts/batch_benchmark_pipelines.py) runs [`run_benchmark.py`](scripts/run_benchmark.py) three times with `DOR_PIPELINE_ID` + `DOR_PRODUCT_ROOT`; writes `benchmark_summary_<pipeline_id>.csv` and `kge_by_variable_<pipeline_id>.png`.
- [`plot_climatology_comparisons.py`](scripts/plot_climatology_comparisons.py) → **1981–2014** climatological mean maps under `output/figures/4km_plots/` (independent 2–98% per panel).
- [`extended_stage_diagnostics.py`](scripts/extended_stage_diagnostics.py) → `stage_diagnostics_extended.csv` (pooled variance on validation window).

**Intentional deltas from older plotting:** [`plot_validation_period.py`](scripts/plot_validation_period.py) remains **validation-era** (2006–2014) for benchmark parity; climatological **full historical** means are **not** produced there — use `plot_climatology_comparisons.py` instead.

**Pipeline prerequisite:** Full SSP future downscale requires `TEST8_MAIN_PERIOD_ONLY=0` and `cmip6_inputs_ssp585_20150101-21001231.dat` next to historical memmaps (see [`pipeline/scripts/_test8_sd_impl.py`](../../pipeline/scripts/_test8_sd_impl.py)).

**Not implemented in code (deferred):** **S1_raw** / **S2_bc** coarse-grid loaders and coarse↔fine **Tier B** alignment — require a confirmed file layout under `Data/Cropped_Iowa/` / `100km-ScenarioMIP/` on `\\abe-cylo\...`. Set `DOR_SCENARIO_RAW_ROOT` / `DOR_CROPPED_BC_ROOT` in [`config.py`](config.py) when ready to add loaders.

**Benchmark CSV rename:** Default single-run output is now `benchmark_summary_<pipeline_id>.csv` (inferred from `DOR_PRODUCT_ROOT` or `DOR_PIPELINE_ID`), not a fixed `benchmark_summary.csv`.

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

---

## 2026-04-07 — NEX `rsds` mean bias pinned down

**Script:** `scripts/diagnose_nex_rsds.py` (outputs under `output/` and `output/figures/`).

**1. Interpolation is not the cause**  
Pooled mean **NEX − GridMET** on the **216×192 target grid:** **+36.68 W m⁻²**.  
Same quantity with **obs interpolated onto the NEX Iowa subset grid** (native resolution): **+36.63 W m⁻²**.  
**Decision:** Treat the ~37 W m⁻² offset as **inherent to NEX vs GridMET for this box/period**, not a bilinear regrid artifact.

**2. Scale**  
Mean GridMET `srad` ~**175 W m⁻²**; mean NEX ~**212 W m⁻²** → relative bias **~21%** of the observed domain mean.

**3. Seasonality**  
Monthly domain-mean bias is **positive every month** (see `nex_rsds_bias_monthly.csv`); largest mean bias in **Apr–May** (~47–53 W m⁻²), smallest in **Jan/Jul** (~21–30 W m⁻²). So it is **not** one bad season—it is a **persistent high bias** with **spring peak**.

**4. Cloudiness proxy (domain-mean obs quartiles)**  
Pooled bias by quartile of daily domain-mean observed srad (`nex_rsds_bias_by_obs_quartile.csv`): **Q1 (dullest)** ~**+42** W m⁻², **Q2–Q3** ~**+40–48**, **Q4 (brightest)** ~**+17** W m⁻². NEX is **too bright in all regimes**; error is **largest when observed SW is low** (consistent with **cloud / diffuse-radiation** mismatch).

**5. Reference data mismatch (from NEX global attrs)**  
NEX historical BCSD cites **Princeton Global Meteorological Forcings** (Sheffield et al. 2006) as reference-era observations—not GridMET. **Implication:** A **large systematic difference vs GridMET** can be **expected** in a “product vs product” check even when both claim W m⁻²; this is **not** equivalent to “NEX failed” in its own design spec.

**Follow-up (if publishing):** State explicitly that NEX was validated here against **GridMET**; optionally repeat a spot check against **PGF** or NEX’s own documentation metrics for MPI.

---

## 2026-04-07 — Validation-period figures (obs vs products)

**Script:** `scripts/plot_validation_period.py`. **Shared loader:** `scripts/benchmark_io.load_aligned_stacks` (same date/grid alignment as `run_benchmark.py` via `align.align_to_obs_with_dates` and the existing `load_*` modules).

**1. Domain-mean daily time series (`output/figures/validation_ts_<var>.png`)**  
For each of the six benchmark variables: **x** = date (2006–2014), **y** = `nanmean` over the 216×192 crop. Lines: **GridMET (target)**, **DOR (blend 0.65)**, **NEX-GDDP**, and **LOCA2** only for **`pr` / `tasmax` / `tasmin`** (no LOCA2 files for `rsds` / `wind` / `huss` in this tree — same as benchmark CSV `NaN` rows).

**2. Side-by-side maps — snapshot days (`output/figures/dor side-by-side/individual days/validation_maps_<var>_<YYYYMMDD>.png`)**  
Two columns, one row: **left** GridMET, **right** DOR on the **same** aligned day and grid. **Color scale:** combined 2nd–98th percentile of finite pixels in **both** panels (shared `vmin`/`vmax`); **`pr`** uses `Blues` with `vmin` floored at 0.

**2b. Time-aggregated side-by-side maps (`output/figures/dor side-by-side/time aggregated/`)**  
- **`validation_agg_mean_<var>.png`:** `nanmean` over the full validation window (2006–2014), same 2–98% scaling on the pair.  
- **`validation_agg_seasonal_<var>.png`:** four rows (meteorological **DJF / MAM / JJA / SON**), each row GridMET | DOR seasonal mean; **per row** a separate 2–98% scale from that row’s obs+DOR fields (so seasons with different magnitude remain readable).

**3. Snapshot dates**  
Fixed list in `config.VALIDATION_MAP_DATES_FIXED`: **2007-01-20** (winter), **2008-04-18** (spring), **2009-07-25** (summer), **2010-10-12** (fall). The script **dedupes** and adds the calendar day with **maximum domain-mean observed `pr`** over the validation window (computed from aligned `pr` stacks). **Maps do not include LOCA2 or NEX panels** (plan scope: target vs DOR minimum); LOCA2 remains time-series-only for the three variables where it exists.

**Performance:** Same heavy UNC reads as `run_benchmark.py`; suitable for occasional QA, not per-cell daily PDFs.
