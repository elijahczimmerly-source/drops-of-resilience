# 216×192 Regridded_Iowa — WDF threshold confirmation

**Data paths (UNC):** `Spatial_Downscaling/test8_v2/Regridded_Iowa/` — `MPI/mv_otbc/cmip6_inputs_*.dat`, `gridmet_targets_*.dat`, `geo_mask.npy`.

## Single run `experiment_wdf_factor_1p30_216x192` (plan “expected” check)

| pr metric | Value |
|-----------|-------|
| Val_WDF_Obs% | 32.317 |
| Val_WDF_Sim% | 34.586 |
| Δ WDF | **+2.27pp** (outside ±1pp) |
| Val_Ext99_Bias% | −0.054 |
| Val_RMSE_pooled | 9.906 |
| Grid (manifest) | **H=216, W=192** |

**Conclusion:** Factor **1.30** (optimal on the wrong 120×192 memmaps) is **not** sufficient on the benchmark grid — higher factors are required.

## Follow-up sweep `--regridded-iowa-server --tag-suffix _216`

Results in `wdf_threshold_sweep_216x192.csv`:

| Factor | WDF Sim% | WDF Obs% | Δ | Ext99 Bias% | RMSE |
|--------|----------|----------|---|-------------|------|
| 1.40 | 33.886 | 32.317 | +1.57pp | −0.054 | 9.908 |
| 1.45 | 33.553 | 32.317 | +1.23pp | −0.054 | 9.908 |
| **1.50** | **33.233** | **32.317** | **+0.92pp** | **−0.054** | **9.909** |

**Within ±1pp WDF:** **1.50** (and likely ~1.48–1.52 in between).

**Success vs plan (correct data):**

- WDF Sim within 1pp of Obs: **met at 1.50**
- Ext99 within ±1%: **met** (−0.05%)
- RMSE ≤ 9.91: **met** (9.909)
- Lag1 Err ≤ 0.060: **met** (~0.055)
- Wind Ext99: stable (~−7.38% vs ~−7.5% benchmark)

## Extended sweep 1.55–1.70 (outputs on **D:**)

Runs used `DOR_TEST8_V2_PR_INTENSITY_ROOT=D:\WRC_DOR_runs\4-test8-v2-pr-intensity` (junction to repo `scripts/`; **`output/` on D:**) to avoid C: full-disk NPZ failures. CSV: `wdf_threshold_sweep_216_1p55plus.csv`. Figures: `D:\WRC_DOR_runs\wdf_figures_216\`.

Obs WDF% = **32.317** (same all runs).

| Factor | WDF Sim% | Δ vs Obs | RMSE | Lag1 Err |
|--------|----------|----------|------|----------|
| 1.50 | 33.233 | +0.92pp | 9.909 | 0.0551 |
| 1.55 | 32.924 | +0.61pp | 9.909 | 0.0549 |
| 1.60 | 32.625 | +0.31pp | 9.910 | 0.0548 |
| **1.65** | **32.336** | **+0.02pp** | 9.910 | 0.0547 |
| 1.70 | 32.055 | −0.26pp | 9.911 | 0.0546 |

**Interpretation:** **1.65** is essentially **on** observed WDF (round-trip noise). **1.70** crosses slightly **dry** (underpredicts wet days). **1.55** is still a bit wet vs obs. RMSE drifts up by ~0.001 from 1.50→1.70 — small vs WDF gain.

## Code default

`test8_v2_pr_intensity.py` default `PR_WDF_THRESHOLD_FACTOR` set to **1.65** (best WDF match on 216×192; env override still works).

## Disk space incident (superseded)

Earlier sweep to C: hit `No space left on device`. Use **D:** for large experiment trees or delete old `output\test8_v2_pr_intensity\experiment_*` folders on C: if space is needed (~160+ GB possible).

## Sweep script

`sweep_wdf_threshold.py` no longer defaults to wrong `Data_Regrided_Gridmet` paths: use **`--regridded-iowa-server`** or pass all three path flags explicitly.
