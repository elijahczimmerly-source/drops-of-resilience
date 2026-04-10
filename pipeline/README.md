# Spatial downscaling pipeline

Canonical code for the Iowa **test8** stochastic spatial downscaling line (PR intensity path, Schaake, WDF tuning).

## Layout

- **`scripts/test8_v3.py`** — Entry point with **legacy** wet-day threshold scaling: default `PR_WDF_THRESHOLD_FACTOR=1.15` (PR intensity blend defaults to **0.65** when unset).
- **`scripts/test8_v4.py`** — Recommended default: same as v3 with **tuned** WDF scaling for Regridded_Iowa **216×192**: default `PR_WDF_THRESHOLD_FACTOR=1.65`.
- **`scripts/_test8_sd_impl.py`** — Shared implementation; run only via v3/v4 (or `runpy` with `DOR_PIPELINE_ID` set).

Outputs go under **`<DOR_PIPELINE_ROOT>/output/<test8_v3|test8_v4>/`**. If `DOR_PIPELINE_ROOT` is unset, it defaults to the parent of `scripts/` (this `pipeline/` folder).

Memmaps and geo files usually live in **`data/`** next to the pipeline root. Point **`DOR_PIPELINE_ROOT`** at a folder that contains `data/` (for example the legacy task folder `4-test8-v2-pr-intensity/`) if those files are not under `pipeline/data/`.

## Deprecated

- **`4-test8-v2-pr-intensity/scripts/test8_v2_pr_intensity.py`** — Thin wrapper that sets the task folder as `DOR_PIPELINE_ROOT` and runs **test8 v4** for backward-compatible paths.

## Further reading

- **`4-test8-v2-pr-intensity/PR_INTENSITY_EXPLAINED.md`** — PR intensity / blend behavior.
- **`8-WDF-overprediction-fix/`** — WDF sweep tooling and rationale.
