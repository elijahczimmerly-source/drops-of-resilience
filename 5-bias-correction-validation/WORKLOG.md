# Bias-correction-validation — work and decision log

This file records **what** was done in this folder and **why** choices were made, so future you (or an agent) can follow the trail without re-deriving context from chat history.

**How to use:** Append new dated sections at the **top** (below this intro) when you change scripts, re-run experiments, or change assumptions. Keep entries factual: action → rationale → affected files.

---

## 2026-04-06 — Initial implementation of `plan.md` (agent session)

### Goal

Execute the full validation plan in `plan.md`: metrics scripts 01–05, plots 06–07, summary 08, using `\\abe-cylo\modelsdev\Projects\WRC_DOR\Data\Cropped_Iowa` and writing under `output/`.

### Decisions and rationale

| Decision | Why |
|----------|-----|
| **Separate `bcv_config.py` + `bcv_io.py`** | Single source for paths (`SERVER`, `DATA`, `OUT_DIR`, `VAR_MAP`, periods) and all NPZ loading. Avoids duplicating UNC paths and filename logic across eight scripts. |
| **Linear interpolation of GridMET → GCM grid** | BC and Raw are on the cropped **~100 km** grid (e.g. 10×9); GridMET is **4 km** (216×192). `plan.md` explicitly flags this risk and suggests aggregating or regridding. **Choice:** `scipy.interpolate.RegularGridInterpolator` at GCM cell centers. **Reason:** Fast, no extra weight files; good enough for independent sanity checks. **Tradeoff:** Not conservative/area-weighted; marginal metrics can differ from a production regrid. Documented in `output/findings.md`. |
| **Longitude 0–360 for obs** | BC `lon` is in 0–360° (e.g. 262.5°); GridMET uses negative °W. Interpolation requires a common system; **add 360° where lon < 0** before building the interpolator. |
| **Temperature units** | BC/Raw `tasmax`/`tasmin` are **°C** (spot-checked means ~15). GridMET `tmmx`/`tmmn` are **K**. **Subtract 273.15** in `obs_values_in_bc_units()` for obs only. |
| **Raw `wind`** | Plan allows `sqrt(uas²+vas²)`; server already exposes **`Cropped_wind_day_*.npz`**. **Use `wind` files** when present to avoid duplicating vector math. **`raw_year_path`** still has `_gn_` vs `_gr_` fallback for EC-Earth3. |
| **Multivariate NPZ discovery via glob** | MPI-style paths use `..._historical_18500101-20141231.npz`. **MRI** uses **`19000101-20141231`**. Hard-coding 1850 **silently dropped MRI** from all metrics. **Fix:** glob `Cropped_{var}_GROUP-*_METHOD-{method}_historical_*.npz`, exclude `*_physics_corrected*` when loading pre-physics BC, prefer `18500101` in the filename when multiple matches exist. |
| **QDM filename pattern** | QDM files use `Cropped_{var}_historical_qdm_1850-01-01_2014-12-31.npz`, not the `GROUP-..._METHOD-...` pattern. **Handled as a branch** in `historical_bc_path()`. |
| **Physics BC vs BCPC** | **Pre-physics:** `Data/Cropped_Iowa/BC/`. **Post-physics:** `BCPC/` with `*_physics_corrected.npz` for multivariate methods; QDM also has paired non-physics and physics-corrected names. **`load_bc_historical(..., bcpc=..., physics_corrected=...)`** encodes that. |
| **qdm has no `wind` in cropped data** | Listing `BC/.../qdm/` shows no wind NPZ. **01/03** skip missing combos; **02** requires six variables in one stack → **qdm omitted** from dependence/Frobenius CSV. **05** ranks Frobenius with `na_option='keep'` so qdm is not falsely ranked. |
| **Validation period 2006–2014** | Matches `plan.md` (`VAL_START`/`VAL_END`). Slicing uses **calendar dates** on BC `time` arrays (`datetime64`), not fixed indices, so different historical start years (1850 vs 1900) still align. |
| **Marginal stats: pooled subsample for KS** | Very large *n* makes KS *p*-values meaningless. **Still compute KS** for traceability but emphasize QQ / MAE / maps in `findings.md`. Optional subsample (e.g. 500k pairs) in `01_marginal_checks.py` for stability. |
| **Dependence: domain-mean daily Spearman** | Full space–time Spearman on six variables is expensive and not required for a coarse sanity check. **Build (T×6)** with spatial mean per day per variable, then **6×6 Spearman** vs same for obs; Frobenius norm of **C_bc − C_obs**. Matches the spirit of Bhuwan’s dependence diagnostics at Iowa scale, not a byte-for-byte reproduction of CONUS code. |
| **Temporal: domain-mean lag-1 and dry spells** | Lag-1 on **domain-mean** daily series; dry spells on domain-mean **pr** with **0.1 mm** wet threshold (same spirit as hydrology-style wet/dry). **Why:** Per-pixel lag-1 over all pixels was deemed heavier than needed for first-pass validation; can be extended later. |
| **Physics: simple Magnus q_sat** | `qsat_kgkg()` for saturation specific humidity vs **tasmax** in °C. **Why:** Quick, reproducible check without importing Bhuwan’s full psychrometry. Residual post-physics `huss > q_sat` at ~1e-4–1e-3 may reflect tolerance or pairing vs production physics — noted in `findings.md`. |
| **Plots (06–07) default to model MPI** | Reduces runtime and figure clutter; **plan** allows Iowa-focused figures. Other models remain in CSV metrics. |
| **06 summary bars: three subplots** | MAE, Frobenius error, and lag-1 error have **different units/scales**. **Why:** Single combined bar chart would be unreadable; stacked subplots keep one scale per metric. |
| **`run_all.py`** | Runs `01`–`08` in order via `subprocess` with repo-root cwd so imports (`bcv_io`) resolve the same as manual runs. |
| **`output/findings.md`** | Human-readable synthesis for Bhuwan/you; points back to CSVs and lists caveats (interpolation, qdm wind, KS at large *n*). |

### Artifacts created

- `bcv_config.py`, `bcv_io.py`
- `01_marginal_checks.py` … `08_summary_table.py`
- `run_all.py`
- `output/metrics/*.csv`, `output/plots/*.png`, `output/summary_table.csv`, `output/findings.md`
- This file: `WORKLOG.md`

### Follow-ups (not done)

- Conservative / area-weighted regrid of GridMET to GCM cells and comparison to linear interp.
- Per-pixel lag-1 (subsampled) as in `plan.md`.
- Optional five-variable dependence mode to include **qdm** (exclude wind).
- Join against Bhuwan’s CONUS `Physics_Constraint_Impact_Table.csv` for side-by-side physics rates.

---

## Template for new entries

Copy and fill:

```markdown
## YYYY-MM-DD — Short title

### Actions
- …

### Decisions
| Decision | Why |
|----------|-----|

### Files touched
- …

### Follow-ups
- …
```
