# Phase 1 sweep vs plan success criteria

Reference Obs WDF% from runs: **~32.68%** (120×192 memmaps on `Data_Regrided_Gridmet`).

| Factor | pr Val_WDF_Sim% | Δ vs Obs | Ext99 Bias% | RMSE | Lag1 Err |
|--------|-----------------|----------|-------------|------|----------|
| 1.15 | 35.01 | +2.33pp | 4.21 | 10.80 | 0.020 |
| 1.20 | 34.22 | +1.54pp | 4.21 | 10.80 | 0.019 |
| 1.25 | 33.45 | +0.76pp | 4.21 | 10.81 | 0.018 |
| 1.30 | 32.69 | +0.01pp | 4.21 | 10.81 | 0.016 |
| 1.35 | 31.95 | −0.73pp | 4.21 | 10.81 | 0.015 |
| 1.40 | 31.23 | −1.45pp | 4.21 | 10.81 | 0.013 |

**WDF (plan: Sim within 1pp of Obs):** Factors **1.25–1.35** satisfy (and 1.30 essentially exact on Sim vs Obs).

**Ext99 (plan: within ±1% of zero):** **None** of the factors change Ext99 (4.207545 identical) — threshold censoring does not move pooled Ext99 on this configuration; criterion not met vs plan’s absolute Ext99 target.

**RMSE (plan: no worse than 9.91):** All factors ~10.80–10.81 (this grid’s blend-0.65 stack; higher than published 9.91 on 216×192 benchmark).

**Recommendation:** Use **`PR_WDF_THRESHOLD_FACTOR=1.30`** as the WDF-focused setting for this input stack (balances Sim≈Obs). Keep code default **1.15** unless project standardizes on 1.30 via env.
