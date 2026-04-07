"""B2: Physics before/after — psychrometric scatter + violation bars (Iowa, MPI)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bcv_config import METHODS, METRICS_DIR, PLOTS_DIR
from bcv_io import load_bc_historical, qsat_kgkg, slice_to_bc_validation

PLOTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "MPI"
N_SAMPLE = 8000


def main():
    d4 = pd.read_csv(METRICS_DIR / "04_physics_checks.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    sub = d4[d4["model"] == MODEL]
    x = np.arange(len(sub))
    ax.bar(x - 0.2, sub["pre_frac_huss_gt_qsat"], 0.4, label="pre huss>qsat")
    ax.bar(x + 0.2, sub["post_frac_huss_gt_qsat"], 0.4, label="post huss>qsat")
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=35, ha="right")
    ax.set_ylabel("fraction")
    ax.legend()
    ax.set_title(f"Physics correction — saturation violations ({MODEL})")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "07_violation_rates_huss.png", dpi=150)
    plt.close(fig)

    # Psychrometric scatter: mv_otbc huss vs tasmax, pre vs post
    method = "mv_otbc"
    for bcpc, phys, tag in [
        (False, False, "BC_pre"),
        (True, True, "BCPC_post"),
    ]:
        Lh = load_bc_historical(MODEL, method, "huss", bcpc=bcpc, physics_corrected=phys)
        Lt = load_bc_historical(MODEL, method, "tasmax", bcpc=bcpc, physics_corrected=phys)
        if Lh is None or Lt is None:
            continue
        h, tim, _, _ = Lh
        tx, _, _, _ = Lt
        h, _ = slice_to_bc_validation(h, tim)
        tx, _ = slice_to_bc_validation(tx, tim)
        rng = np.random.default_rng(0)
        flat_h = h.ravel()
        flat_t = tx.ravel()
        m = np.isfinite(flat_h) & np.isfinite(flat_t)
        flat_h, flat_t = flat_h[m], flat_t[m]
        if flat_h.size > N_SAMPLE:
            idx = rng.choice(flat_h.size, N_SAMPLE, replace=False)
            flat_h, flat_t = flat_h[idx], flat_t[idx]
        tc = np.linspace(-10, 40, 200)
        qs = qsat_kgkg(tc)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(flat_t, flat_h, s=2, alpha=0.2, c="C0")
        ax.plot(tc, qs, color="k", lw=2, label="q_sat(tasmax)")
        ax.set_xlabel("tasmax (°C)")
        ax.set_ylabel("huss (kg/kg)")
        ax.set_title(f"{method} {MODEL} {tag}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / f"07_psychrometric_{tag}.png", dpi=150)
        plt.close(fig)

    print(f"Wrote physics plots to {PLOTS_DIR}")


if __name__ == "__main__":
    main()
