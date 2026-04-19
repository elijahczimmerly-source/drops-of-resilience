# Native-resolution benchmark suites

Benchmarks, climate-signal CSVs, diagnostics, and figure trees for the **GridMET-target** suite and for **LOCA2 native** and **NEX 0.25° native** evaluation grids live as **parallel folders** under `6-product-comparison/`:

| Suite ID (`DOR_BENCHMARK_SUITE`) | Output root | Notes |
|----------------------------------|-------------|--------|
| `dor_native` (default) | `6-product-comparison/dor_native/` | GridMET 216×192 mesh; alias `gridmet_4km` is accepted and normalized to `dor_native`. |
| `loca2_native` | `6-product-comparison/loca2_native/` | |
| `nex_native` | `6-product-comparison/nex_native/` | |

Multi-panel comparison plots (hist / validation / delta) are written **directly** under each suite’s `figures/` directory (no `figures/plots/` or `4km_plots/` segment).

Secondary artifacts (not part of that gallery) use dedicated subfolders on the suite root, for example:

- `benchmark_figures/` — KGE / Ext99 bar charts from `run_benchmark.py`
- `validation_obs_vs_dor/` — validation-era side-by-side maps and `validation_ts_*.png` from `plot_validation_period.py`
- `nex_rsds_diagnostic/` — PNGs from `diagnose_nex_rsds.py` (CSVs/JSON stay at the suite root)

GridMET, DOR, and driving (S3) fields are interpolated from the 216×192 GridMET mesh onto each product’s grid where needed; LOCA2 and NEX are compared on their native meshes (with cross-product alignment where needed). Provenance mirrors (`benchmark_bundle/`) are copied into each native suite folder by `scripts/collect_benchmark_provenance.py`.

For orchestration, see `scripts/run_e2e_suite.py` and env `DOR_E2E_SUITES`. Implementation history: `WORKLOG_NATIVE_RESOLUTION.md`.
