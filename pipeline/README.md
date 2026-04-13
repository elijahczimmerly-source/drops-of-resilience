# Spatial downscaling pipeline

Canonical code for the Iowa **test8** stochastic spatial downscaling line (optional PR intensity, Schaake, WDF tuning).

## Layout

- **`scripts/test8_v2.py`** — **Bhuwan-parity-oriented** preset: default `PR_WDF_THRESHOLD_FACTOR=1.65`, `DOR_PR_CORR_LENGTH=35` (pr), `DOR_MULTIPLICATIVE_NOISE_DEBIAS=0`, no `PR_INTENSITY_BLEND` preset (impl default 1.0 when intensity is off). Still the shared fork in `_test8_sd_impl.py`, not a byte copy of Bhuwan’s server `test8_v2.py`.
- **`scripts/test8_v3.py`** — PR-intensity workflow with **legacy** wet-day scaling: default `PR_WDF_THRESHOLD_FACTOR=1.15` (blend defaults to **0.65** when unset).
- **`scripts/test8_v4.py`** — Recommended default for PR-intensity experiments: **tuned** WDF for Regridded_Iowa **216×192**: default `PR_WDF_THRESHOLD_FACTOR=1.65`, blend **0.65** when unset.
- **`scripts/_test8_sd_impl.py`** — Shared implementation; run via `test8_v2.py` / `test8_v3.py` / `test8_v4.py` (or `runpy` with `DOR_PIPELINE_ID` set).

Outputs go under **`<DOR_PIPELINE_ROOT>/output/<test8_v2|test8_v3|test8_v4>/`**. If `DOR_PIPELINE_ROOT` is unset, it defaults to the parent of `scripts/` (this `pipeline/` folder).

Memmaps and geo files usually live in **`data/`** next to the pipeline root. Point **`DOR_PIPELINE_ROOT`** at a folder that contains `data/` (for example the legacy task folder `4-test8-v2-pr-intensity/`) if those files are not under `pipeline/data/`.

## Regridding (100 km → 4 km GridMET skeleton)

Scripts for local OTBC → fine-grid regridding (bilinear / NN comparison harness) live in **`scripts/regrid/`**. Production parity with Bhuwan’s **`regrid_to_gridmet.py`** on the server (conservative `pr`, `gridmet_paths.py`) is documented there — see [`scripts/regrid/README.md`](scripts/regrid/README.md).

## Deprecated

- **`4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py`** — Thin wrapper that sets the task folder as `DOR_PIPELINE_ROOT` and runs **test8 v4** for backward-compatible paths.

## Further reading

- **`4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md`** — PR intensity / blend behavior.
- **`8-WDF-overprediction-fix/`** — WDF sweep tooling and rationale.
