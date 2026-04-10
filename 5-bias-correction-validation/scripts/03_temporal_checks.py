"""A3: Lag-1 autocorrelation (domain-mean daily) and dry-spell lengths for PR."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

from bcv_config import BC_VARS, METRICS_DIR, METHODS, MODELS, OUT_DIR, VAR_MAP
from bcv_io import (
    load_bc_historical,
    load_raw_concat,
    normalize_time_days,
    obs_values_in_bc_units,
    prepare_obs_for_bc_dates,
    slice_to_bc_validation,
)

OUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

WET_PR_MM = 0.1


def lag1_corr(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    m = np.isfinite(x)
    x = x[m]
    if x.size < 3:
        return float("nan")
    x0, x1 = x[:-1], x[1:]
    if np.std(x0) < 1e-12 or np.std(x1) < 1e-12:
        return float("nan")
    return float(np.corrcoef(x0, x1)[0, 1])


def dry_spell_lengths(pr: np.ndarray) -> np.ndarray:
    """pr (T,) domain mean daily mm."""
    wet = pr > WET_PR_MM
    spells = []
    run = 0
    for w in wet:
        if w:
            if run > 0:
                spells.append(run)
            run = 0
        else:
            run += 1
    if run > 0:
        spells.append(run)
    return np.array(spells, dtype=np.int32) if spells else np.array([], dtype=np.int32)


def main():
    rows = []
    for model in MODELS:
        for method in METHODS:
            for var in BC_VARS:
                obs_var = VAR_MAP[var]
                loaded = load_bc_historical(model, method, var)
                if loaded is None:
                    continue
                data, time, lat, lon = loaded
                dval, tval = slice_to_bc_validation(data, time)
                obs = prepare_obs_for_bc_dates(obs_var, tval, lat, lon)
                obs = obs_values_in_bc_units(obs_var, obs)
                bc_dom = np.nanmean(dval, axis=(1, 2))
                ob_dom = np.nanmean(obs, axis=(1, 2))
                l1_bc = lag1_corr(bc_dom)
                l1_obs = lag1_corr(ob_dom)
                lag1_err = abs(l1_bc - l1_obs)
                raw_l1 = np.nan
                r = load_raw_concat(model, var)
                if r is not None:
                    rd, rt, _, _ = r
                    rt_d = normalize_time_days(rt)
                    idx = []
                    ok = True
                    for d in tval:
                        w = np.where(rt_d == d)[0]
                        if w.size != 1:
                            ok = False
                            break
                        idx.append(int(w[0]))
                    if ok:
                        raw_dom = np.nanmean(rd[idx], axis=(1, 2))
                        raw_l1 = lag1_corr(raw_dom)
                row = {
                    "model": model,
                    "method": method,
                    "variable": var,
                    "lag1_bc": l1_bc,
                    "lag1_obs": l1_obs,
                    "lag1_err": lag1_err,
                    "lag1_raw": raw_l1,
                }
                if var == "pr":
                    ds_bc = dry_spell_lengths(bc_dom)
                    ds_ob = dry_spell_lengths(ob_dom)
                    row["dryspell_mean_bc"] = float(np.mean(ds_bc)) if ds_bc.size else np.nan
                    row["dryspell_mean_obs"] = float(np.mean(ds_ob)) if ds_ob.size else np.nan
                    row["dryspell_median_bc"] = float(np.median(ds_bc)) if ds_bc.size else np.nan
                    row["dryspell_median_obs"] = float(np.median(ds_ob)) if ds_ob.size else np.nan
                rows.append(row)
    df = pd.DataFrame(rows)
    out = METRICS_DIR / "03_temporal_checks.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
