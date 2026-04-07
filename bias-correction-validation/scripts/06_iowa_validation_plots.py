"""B1: Iowa validation plots (MPI); reads metrics CSVs + recomputes a few visuals."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, spearmanr

from bcv_config import BC_VARS, METHODS, METRICS_DIR, PLOTS_DIR, VAR_MAP
from bcv_io import (
    load_bc_historical,
    obs_values_in_bc_units,
    prepare_obs_for_bc_dates,
    slice_to_bc_validation,
)

PLOTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "MPI"


def spearman_corr_matrix(y: np.ndarray) -> np.ndarray:
    n = y.shape[1]
    out = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            m = np.isfinite(y[:, i]) & np.isfinite(y[:, j])
            if m.sum() < 30:
                continue
            r, _ = spearmanr(y[m, i], y[m, j])
            out[i, j] = out[j, i] = r
    return out


def domain_mean_stack(model: str, method: str) -> np.ndarray | None:
    cols = []
    tref = None
    lat = lon = None
    for var in BC_VARS:
        L = load_bc_historical(model, method, var)
        if L is None:
            return None
        data, time, lat, lon = L
        d, t = slice_to_bc_validation(data, time)
        if tref is None:
            tref = t
        elif len(t) != len(tref) or not np.array_equal(t, tref):
            return None
        cols.append(np.nanmean(d, axis=(1, 2)))
    return np.column_stack(cols)


def obs_domain_stack(model: str, tref, lat, lon) -> np.ndarray | None:
    cols = []
    for var in BC_VARS:
        obs = prepare_obs_for_bc_dates(VAR_MAP[var], tref, lat, lon)
        obs = obs_values_in_bc_units(VAR_MAP[var], obs)
        cols.append(np.nanmean(obs, axis=(1, 2)))
    return np.column_stack(cols)


def main():
    # --- Fig: mean bias maps (pr, tasmax), each method ---
    for var_plot in ("pr", "tasmax"):
        obs_v = VAR_MAP[var_plot]
        ncol = 4
        nrow = int(np.ceil(len(METHODS) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3.5 * nrow), squeeze=False)
        ax_flat = axes.ravel()
        for ax in ax_flat:
            ax.set_visible(False)
        for i, method in enumerate(METHODS):
            L = load_bc_historical(MODEL, method, var_plot)
            if L is None:
                continue
            data, time, lat, lon = L
            dval, tval = slice_to_bc_validation(data, time)
            obs = prepare_obs_for_bc_dates(obs_v, tval, lat, lon)
            obs = obs_values_in_bc_units(obs_v, obs)
            bias = np.nanmean(dval - obs, axis=0)
            ax = ax_flat[i]
            ax.set_visible(True)
            im = ax.pcolormesh(lon, lat, bias, shading="auto", cmap="RdBu_r")
            plt.colorbar(im, ax=ax, fraction=0.046)
            ax.set_title(f"{method}\nmean(BC−Obs) {var_plot}")
            ax.set_xlabel("lon")
            ax.set_ylabel("lat")
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / f"06_bias_maps_{var_plot}_{MODEL}.png", dpi=150)
        plt.close(fig)

    # --- QQ domain-mean pr: QDM, OTBC, Raw obs quantiles ---
    method_pick = ["qdm", "mv_otbc", "mv_bcca"]
    fig, ax = plt.subplots(figsize=(6, 6))
    qs = np.linspace(0.01, 0.99, 80)
    Lobs = load_bc_historical(MODEL, "mv_otbc", "pr")
    if Lobs is not None:
        _, time, lat, lon = Lobs
        d0, t0 = slice_to_bc_validation(Lobs[0], time)
        obs = prepare_obs_for_bc_dates("pr", t0, lat, lon)
        obs_dom = np.nanmean(obs, axis=(1, 2))
        q_obs = np.quantile(obs_dom[np.isfinite(obs_dom)], qs)
        ax.plot(q_obs, q_obs, color="k", ls="--", label="1:1")
        for method in method_pick:
            L = load_bc_historical(MODEL, method, "pr")
            if L is None:
                continue
            data, tim, _, _ = L
            dv, tv = slice_to_bc_validation(data, tim)
            if len(tv) != len(t0):
                continue
            bc_dom = np.nanmean(dv, axis=(1, 2))
            q_bc = np.quantile(bc_dom[np.isfinite(bc_dom)], qs)
            ax.plot(q_obs, q_bc, label=method)
        ax.set_aspect("equal")
        ax.legend()
        ax.set_xlabel("Obs quantile (mm/d)")
        ax.set_ylabel("BC quantile (mm/d)")
        ax.set_title(f"QQ domain-mean pr ({MODEL})")
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / "06_qq_pr_domain_mean.png", dpi=150)
        plt.close(fig)

    # --- Spearman error heatmap mv_otbc ---
    L = load_bc_historical(MODEL, "mv_otbc", "pr")
    if L is not None:
        _, time, lat, lon = L
        _, tref = slice_to_bc_validation(L[0], time)
        y_bc = domain_mean_stack(MODEL, "mv_otbc")
        y_ob = obs_domain_stack(MODEL, tref, lat, lon)
        if y_bc is not None and y_ob is not None:
            c_bc = spearman_corr_matrix(y_bc)
            c_ob = spearman_corr_matrix(y_ob)
            err = c_bc - c_ob
            fig, ax = plt.subplots(figsize=(7, 6))
            im = ax.imshow(err, cmap="RdBu_r", vmin=-0.3, vmax=0.3)
            ax.set_xticks(range(6))
            ax.set_yticks(range(6))
            ax.set_xticklabels(BC_VARS, rotation=45, ha="right")
            ax.set_yticklabels(BC_VARS)
            plt.colorbar(im, ax=ax)
            ax.set_title(f"Spearman error (BC−Obs) domain-mean {MODEL} mv_otbc")
            fig.tight_layout()
            fig.savefig(PLOTS_DIR / "06_corr_error_heatmap_mv_otbc.png", dpi=150)
            plt.close(fig)

    # --- Compound scatter tasmax vs pr (domain mean) ---
    fig, ax = plt.subplots(figsize=(6, 5))
    for label, method in [("Obs", None), ("QDM", "qdm"), ("OTBC", "mv_otbc")]:
        if label == "Obs":
            L = load_bc_historical(MODEL, "mv_otbc", "pr")
            if L is None:
                continue
            _, time, lat, lon = L
            _, tref = slice_to_bc_validation(L[0], time)
            pr_o = prepare_obs_for_bc_dates("pr", tref, lat, lon)
            tx_o = prepare_obs_for_bc_dates("tmmx", tref, lat, lon)
            pr_o = np.nanmean(pr_o, axis=(1, 2))
            tx_o = np.nanmean(obs_values_in_bc_units("tmmx", tx_o), axis=(1, 2))
            m = np.isfinite(pr_o) & np.isfinite(tx_o)
            ax.scatter(tx_o[m], pr_o[m], s=1, alpha=0.15, label=label)
        else:
            Lp = load_bc_historical(MODEL, method, "pr")
            Lt = load_bc_historical(MODEL, method, "tasmax")
            if Lp is None or Lt is None:
                continue
            dp, tp = slice_to_bc_validation(Lp[0], Lp[1])
            dt, tt = slice_to_bc_validation(Lt[0], Lt[1])
            if len(tp) != len(tt):
                continue
            pr_b = np.nanmean(dp, axis=(1, 2))
            tx_b = np.nanmean(dt, axis=(1, 2))
            m = np.isfinite(pr_b) & np.isfinite(tx_b)
            ax.scatter(tx_b[m], pr_b[m], s=1, alpha=0.15, label=label)
    ax.set_xlabel("tasmax (°C)")
    ax.set_ylabel("pr (mm/d)")
    ax.legend(markerscale=4)
    ax.set_title(f"Compound extremes domain-mean ({MODEL})")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "06_compound_tmax_pr.png", dpi=150)
    plt.close(fig)

    # --- Dry spell length KDE (pr) ---
    fig, ax = plt.subplots(figsize=(7, 4))

    def spells(pr):
        wet = pr > 0.1
        s = []
        run = 0
        for w in wet:
            if w:
                if run > 0:
                    s.append(run)
                run = 0
            else:
                run += 1
        if run > 0:
            s.append(run)
        return np.array(s, float)

    L = load_bc_historical(MODEL, "mv_otbc", "pr")
    if L is not None:
        _, time, lat, lon = L
        dv, tv = slice_to_bc_validation(L[0], time)
        obs = prepare_obs_for_bc_dates("pr", tv, lat, lon)
        for name, series in [
            ("Obs", np.nanmean(obs, axis=(1, 2))),
            ("QDM", None),
            ("OTBC", None),
        ]:
            if name == "QDM":
                L2 = load_bc_historical(MODEL, "qdm", "pr")
                if L2 is None:
                    continue
                d2, _ = slice_to_bc_validation(L2[0], L2[1])
                series = np.nanmean(d2, axis=(1, 2))
            elif name == "OTBC":
                series = np.nanmean(dv, axis=(1, 2))
            elif name == "Obs":
                pass
            sp = spells(series)
            if sp.size < 5:
                continue
            kde = gaussian_kde(sp)
            xs = np.linspace(1, min(60, sp.max()), 200)
            ax.plot(xs, kde(xs), label=name)
        ax.set_xlabel("Dry spell length (days)")
        ax.set_ylabel("density")
        ax.legend()
        ax.set_title(f"Dry spell KDE domain-mean pr ({MODEL})")
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / "06_dry_spell_kde.png", dpi=150)
        plt.close(fig)

    # --- Bar summary from CSVs ---
    d1 = pd.read_csv(METRICS_DIR / "01_marginal_checks.csv")
    d2 = pd.read_csv(METRICS_DIR / "02_dependence_checks.csv")
    d3 = pd.read_csv(METRICS_DIR / "03_temporal_checks.csv")
    g1 = d1.groupby("method")["mae"].mean()
    g2 = d2.groupby("method")["frobenius_spearman_error"].mean()
    g3 = d3.groupby("method")["lag1_err"].mean()
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    x = np.arange(len(METHODS))
    axes[0].bar(x, [g1.get(m, np.nan) for m in METHODS])
    axes[0].set_ylabel("mean MAE")
    axes[1].bar(x, [g2.get(m, np.nan) for m in METHODS])
    axes[1].set_ylabel("Frob. dep. err")
    axes[2].bar(x, [g3.get(m, np.nan) for m in METHODS])
    axes[2].set_ylabel("mean Lag1 err")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(METHODS, rotation=30, ha="right")
    fig.suptitle("Iowa validation (01–03 CSV aggregates)")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "06_summary_bars.png", dpi=150)
    plt.close(fig)

    print(f"Plots written to {PLOTS_DIR}")


if __name__ == "__main__":
    main()
