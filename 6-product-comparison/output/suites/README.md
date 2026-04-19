# Native-resolution benchmark suites

Benchmarks, climate-signal CSVs, diagnostics, and figure trees for **LOCA2 native** and **NEX 0.25° native** evaluation grids are written beside the legacy GridMET stack:

| Suite ID (`DOR_BENCHMARK_SUITE`) | Output root |
|----------------------------------|-------------|
| `gridmet_4km` (default) | `6-product-comparison/output/` |
| `loca2_native` | `output/suites/loca2_native/` |
| `nex_native` | `output/suites/nex_native/` |

GridMET, DOR, and driving (S3) fields are interpolated from the 216×192 GridMET mesh onto each product’s grid; LOCA2 and NEX are compared on their native meshes (with cross-product alignment where needed). Provenance mirrors (`benchmark_bundle/`) are copied into each suite folder by `scripts/collect_benchmark_provenance.py`.

For orchestration, see `scripts/run_e2e_suite.py` and env `DOR_E2E_SUITES`. Implementation history: `WORKLOG_NATIVE_RESOLUTION.md` (repo root under `6-product-comparison/`).
