# Native-resolution product benchmark — work log

Append-only notes for the parallel **LOCA2 native** / **NEX native** benchmark trees (`output/suites/`), keyed off `DOR_BENCHMARK_SUITE` and `scripts/grid_suites.py`.

## 2026-04-18

- Wired **suite-aware** runners: `run_e2e_suite.py` loops `DOR_E2E_SUITES` (default all three) for climate signal, extended diagnostics, `plot_comparison_driver`, `plot_climatology_comparisons`, `plot_validation_period`, `diagnose_nex_rsds` (gridmet + nex only), `pr_texture_investigation`; runs `batch_benchmark_pipelines` once; `collect_benchmark_provenance` mirrors `benchmark_bundle` into each native suite dir.
- **`plot_climatology_comparisons.py`** now uses `load_multi_product_historical` + `--suite`; writes under `suite_fig_4km_style_root` (same layout as the 4 km plot driver).
- **`plot_validation_period.py`** takes `--suite`; writes under `suite_fig_dir` / `dor side-by-side/…`; `load_aligned_stacks(..., suite=…)`.
- **`diagnose_nex_rsds.py`** uses `load_aligned_stacks("rsds")` for gridmet and nex_native; skips LOCA2 native; outputs under `suite_output_dir`.
- **`pr_texture_investigation.py`** `--suite` + suffixed CSV/JSON outputs when not `gridmet_4km`.
- Added **`output/suites/README.md`** (this tree) and this log.

- **`interp_from_gridmet_stack.py`**: Replaced `xarray.DataArray.interp(lat=..., lon=...)` (breaks on current xarray: treats `lat`/`lon` as dimension names, not 2D non-dimensional coords). GridMET→target rectilinear stacks now use **`scipy.ndimage.map_coordinates`** with **precomputed fractional indices** (fast path for ~12k days). Curvilinear LOCA→NEX uses **`scipy.interpolate.griddata`**. Optional GridMET `Cropped_srad_2006.npz` in `diagnose_nex_rsds` metadata when file is absent.

## 2026-04-18 (later)

- **`config.py`**: `DOR_DEFAULT_OUTPUTS` resolves via `DOR_PIPELINE_OUTPUT_ROOT`, else repo `pipeline/output`, else `D:\\drops-resilience-data\\dor_pipeline_output` when the v4 NPZ probe exists.
- **`batch_benchmark_pipelines.py`**: Uses `cfg.DOR_DEFAULT_OUTPUTS` for pipeline roots.
- **`interp_curvilinear_stack_to_target`**: Detects **rectilinear** `meshgrid(lat1d,lon1d)` (LOCA2/NEX Iowa crops) and delegates to **`interp_gridmet_stack_to_target`** instead of per-day `griddata` (was effectively hanging multi-hour on `nex_native` validation loads).
- **`run_e2e_suite.py`**: Sets `PYTHONUNBUFFERED=1` for child processes.

## 2026-04-19

- **`interp_curvilinear_stack_to_target`**: Rectilinear check uses `allclose(..., rtol=1e-6, atol=1e-5)` so float noise does not force the slow `griddata` path.
- **`climate_signal_io.load_dor_main_npz` / `load_dor_future_npz`**: Load DOR arrays as **float32** (was float64 ~3.8 GiB per var) to avoid `MemoryError` when running native-suite climate stages alongside other heavy jobs.
- **`run_native_suite_outputs.py`**: One-shot runner for extended diagnostics → plot comparison (all) → multivariate → climatology → validation plots → NEX rsds diagnose (gridmet + nex_native) → pr_texture (all suites) → provenance.
- **`run_climate_native_suites.py`**: Runs `run_climate_signal_stages` for `loca2_native` and `nex_native` (after float32 fix).
- **Executed end-to-end** (this session): `batch_benchmark_pipelines --suites nex_native` (after LOCA→NEX interp fix); `run_native_suite_outputs.py` (~9.9 h wall, exit 0); `run_climate_native_suites.py` after DOR float32 fix (exit 0). Climate CSVs present under `output/suites/loca2_native/` and `output/suites/nex_native/`.
