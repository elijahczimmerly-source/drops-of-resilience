"""
Build a single self-contained HTML report combining:
  1. Quantitative metrics table (all vars bilinear vs NN + pr 3-way)
  2. NN vs bilinear figure (same as regrid_comparison_report.html; tasmax–huss only)
  3. Pr 3-way table + same-style 2×2 figure (vs bilinear reference)
  4. Pre-test8 vs post-test8 gallery (all 18 panels)

All images are base64-embedded so the HTML is fully portable.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT = Path(r"C:\drops-of-resilience\bilinear-vs-nn-regridding")
PIPELINE = ROOT / "pipeline"
OUT_HTML = ROOT / "combined_regrid_report.html"

# ─── data ────────────────────────────────────────────────────────────────────
bi_csv = pd.read_csv(PIPELINE / "output" / "bilinear" / "Bilinear_Table1_Pooled_Metrics.csv")
nn_csv = pd.read_csv(PIPELINE / "output" / "nearest_neighbor" / "NN_Table1_Pooled_Metrics.csv")
pr3_csv = pd.read_csv(PIPELINE / "output" / "pr_3way" / "pr_3way_metrics.csv")

PRE_POST_DIR = ROOT / "qualitative_plots" / "pre_post_test8"


def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def fig_to_b64(fig, dpi: int = 150) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    plt.close(fig)
    return b64


def _metric_pair(var: str, col: str) -> tuple[float, float]:
    """(bilinear_col, nn_col) for pooled metrics. pr uses dedicated pr regrid runs."""
    if var == "pr":
        b = float(pr3_csv.loc[pr3_csv["Method"] == "bilinear", col].values[0])
        n = float(pr3_csv.loc[pr3_csv["Method"] == "nearest", col].values[0])
        return b, n
    b = float(bi_csv.loc[bi_csv["Variable"] == var, col].values[0])
    n = float(nn_csv.loc[nn_csv["Variable"] == var, col].values[0])
    return b, n


# ═════════════════════════════════════════════════════════════════════════════
# Charts — copied from pipeline/scripts/compare_regrid_methods.py (same styling).
# Non-pr figure: identical to regrid_comparison_report.html.
# PR 3-way: same 2×2 layout; x = conservative | bilinear | nearest;
#   bar values are vs bilinear reference (bilinear = 0), matching original semantics.
# ═════════════════════════════════════════════════════════════════════════════

TIER_COLORS = {"good": "#d6eed9", "moderate": "#fff3cd", "poor": "#fde0df"}


def _make_nn_vs_bil_figure_identical_to_compare_script() -> plt.Figure:
    """Exact logic from compare_regrid_methods.py (tasmax…huss only, no pr)."""
    bil = bi_csv.set_index("Variable")
    nn = nn_csv.set_index("Variable")
    vars_list = ["tasmax", "tasmin", "rsds", "wind", "huss"]
    var_labels = ["tasmax", "tasmin", "rsds", "wind", "huss"]

    kge_diff = np.array(
        [(nn.loc[v, "Val_KGE"] - bil.loc[v, "Val_KGE"]) / abs(bil.loc[v, "Val_KGE"]) * 100 for v in vars_list]
    )
    rmse_diff = np.array(
        [
            (nn.loc[v, "Val_RMSE_pooled"] - bil.loc[v, "Val_RMSE_pooled"])
            / bil.loc[v, "Val_RMSE_pooled"]
            * 100
            for v in vars_list
        ]
    )
    ext99_diff = np.array(
        [abs(nn.loc[v, "Val_Ext99_Bias%"]) - abs(bil.loc[v, "Val_Ext99_Bias%"]) for v in vars_list]
    )
    lag1_diff = np.array(
        [
            (nn.loc[v, "Val_Lag1_Err"] - bil.loc[v, "Val_Lag1_Err"])
            / abs(bil.loc[v, "Val_Lag1_Err"])
            * 100
            for v in vars_list
        ]
    )

    def kge_tier(var):
        best = max(bil.loc[var, "Val_KGE"], nn.loc[var, "Val_KGE"])
        if best >= 0.60:
            return "good"
        if best >= 0.30:
            return "moderate"
        return "poor"

    def ext99_tier(var):
        best = min(abs(bil.loc[var, "Val_Ext99_Bias%"]), abs(nn.loc[var, "Val_Ext99_Bias%"]))
        if best <= 5.0:
            return "good"
        if best <= 10.0:
            return "moderate"
        return "poor"

    def lag1_tier(var):
        best = min(bil.loc[var, "Val_Lag1_Err"], nn.loc[var, "Val_Lag1_Err"])
        if best <= 0.005:
            return "good"
        if best <= 0.015:
            return "moderate"
        return "poor"

    def rmse_tier(var):
        pct = abs(rmse_diff[vars_list.index(var)])
        if pct >= 1.0:
            return "moderate"
        return "good"

    panel_tier_fn = {"kge": kge_tier, "rmse": rmse_tier, "ext99": ext99_tier, "lag1": lag1_tier}

    def is_meaningful(var, panel):
        tier = panel_tier_fn[panel](var)
        if tier == "poor":
            return False
        if panel == "kge" and abs(kge_diff[vars_list.index(var)]) < 1.0:
            return False
        if panel == "rmse" and abs(rmse_diff[vars_list.index(var)]) < 0.5:
            return False
        if panel == "ext99" and abs(ext99_diff[vars_list.index(var)]) < 1.0:
            return False
        if panel == "lag1":
            if tier == "good":
                return False
            if abs(lag1_diff[vars_list.index(var)]) < 5.0:
                return False
        return True

    def bar_color(diff, higher_is_better):
        if higher_is_better:
            return "#4caf7d" if diff > 0 else "#e07060"
        return "#4caf7d" if diff < 0 else "#e07060"

    def draw_panel(ax, diffs, panel_key, higher_is_better, title, ylabel=None, fmt="{:+.2f}%", pad_p=0.03, pad_n=-0.08):
        tier_fn = panel_tier_fn[panel_key]
        ymax_abs = max(abs(diffs)) if max(abs(diffs)) > 0 else 1

        for i, (var, diff) in enumerate(zip(vars_list, diffs)):
            tier = tier_fn(var)
            meaningful = is_meaningful(var, panel_key)

            ax.axvspan(i - 0.48, i + 0.48, alpha=0.55, color=TIER_COLORS[tier], zorder=0, linewidth=0)

            color = bar_color(diff, higher_is_better)
            alpha = 1.0 if meaningful else 0.38
            hatch = None if meaningful else "///"
            edge = "white" if meaningful else "#aaa"
            ax.bar(i, diff, 0.55, color=color, alpha=alpha, hatch=hatch, edgecolor=edge, linewidth=0.5, zorder=2)

            pad = pad_p if diff >= 0 else pad_n
            ax.text(i, diff + pad, fmt.format(diff), ha="center", va="bottom", fontsize=7.5, zorder=3)

            if not meaningful:
                mid = (
                    diff * 0.45
                    if abs(diff) > ymax_abs * 0.05
                    else (pad_p * 0.4 if diff >= 0 else pad_n * 0.4)
                )
                ax.text(i, mid, "n.s.", ha="center", va="center", fontsize=7, color="#555", style="italic", zorder=4)

        ax.set_xticks(np.arange(len(vars_list)))
        ax.set_xticklabels(var_labels, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.axhline(0, color="#555", linewidth=0.8, linestyle="--", zorder=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=10)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    fig.patch.set_facecolor("#fafafa")
    for ax in axes.flat:
        ax.set_facecolor("#fafafa")

    draw_panel(axes[0, 0], kge_diff, "kge", True, "KGE  (higher = better)", ylabel="% change vs bilinear")
    draw_panel(axes[0, 1], rmse_diff, "rmse", False, "RMSE  (lower = better)")
    draw_panel(
        axes[1, 0],
        ext99_diff,
        "ext99",
        False,
        "Ext99 Bias%  (|bias| closer to 0 = better)",
        ylabel="absolute diff (pp)",
        fmt="{:+.3f}",
        pad_p=0.008,
        pad_n=-0.025,
    )
    draw_panel(axes[1, 1], lag1_diff, "lag1", False, "Lag1 Error  (lower = better)", pad_p=0.4, pad_n=-1.2)

    nn_patch = mpatches.Patch(color="#4caf7d", label="NN better")
    bil_patch = mpatches.Patch(color="#e07060", label="Bilinear better")
    good_patch = mpatches.Patch(color=TIER_COLORS["good"], alpha=0.8, label="Both models perform well")
    mod_patch = mpatches.Patch(color=TIER_COLORS["moderate"], alpha=0.8, label="Moderate performance")
    poor_patch = mpatches.Patch(color=TIER_COLORS["poor"], alpha=0.8, label="Both perform poorly — winner is noise")
    ns_patch = mpatches.Patch(facecolor="#ccc", hatch="///", edgecolor="#aaa", label="Not meaningful (n.s.)")

    fig.legend(
        handles=[nn_patch, bil_patch, good_patch, mod_patch, poor_patch, ns_patch],
        loc="upper center",
        ncol=3,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 1.02),
    )

    fig.suptitle(
        "Bilinear vs Nearest-Neighbor Regridding: % change (NN relative to Bilinear)\n"
        "Background shading reflects absolute model performance, independent of which method wins.",
        fontsize=11,
        y=1.07,
    )
    plt.tight_layout()
    return fig


def _make_pr3way_figure_same_style() -> plt.Figure:
    """
    Same 2×2 panel style as compare_regrid_methods.py.
    x-axis: conservative, bilinear, nearest.
    Bar height vs bilinear (bilinear = 0): KGE/RMSE/Lag1 as % change; Ext99 as |bias| diff in pp.
    Colors: green = better than bilinear for that method; red = worse; gray at bilinear (0).
    """
    order = ["conservative", "bilinear", "nearest"]
    labels = ["conservative", "bilinear", "nearest"]

    def v(method: str, col: str) -> float:
        return float(pr3_csv.loc[pr3_csv["Method"] == method, col].values[0])

    bil_kge = v("bilinear", "Val_KGE")
    bil_rmse = v("bilinear", "Val_RMSE_pooled")
    bil_ext = v("bilinear", "Val_Ext99_Bias%")
    bil_lag = v("bilinear", "Val_Lag1_Err")

    kge_vals = np.array(
        [(v(m, "Val_KGE") - bil_kge) / (abs(bil_kge) + 1e-12) * 100 for m in order]
    )
    rmse_vals = np.array(
        [(v(m, "Val_RMSE_pooled") - bil_rmse) / bil_rmse * 100 for m in order]
    )
    ext99_vals = np.array(
        [abs(v(m, "Val_Ext99_Bias%")) - abs(bil_ext) for m in order]
    )
    lag1_vals = np.array(
        [(v(m, "Val_Lag1_Err") - bil_lag) / (abs(bil_lag) + 1e-12) * 100 for m in order]
    )

    def kge_tier_pr():
        best = max(v(m, "Val_KGE") for m in order)
        if best >= 0.60:
            return "good"
        if best >= 0.30:
            return "moderate"
        return "poor"

    def ext99_tier_pr():
        best = min(abs(v(m, "Val_Ext99_Bias%")) for m in order)
        if best <= 5.0:
            return "good"
        if best <= 10.0:
            return "moderate"
        return "poor"

    def lag1_tier_pr():
        best = min(v(m, "Val_Lag1_Err") for m in order)
        if best <= 0.005:
            return "good"
        if best <= 0.015:
            return "moderate"
        return "poor"

    def rmse_tier_pr():
        if abs(rmse_vals[0]) >= 1.0 or abs(rmse_vals[2]) >= 1.0:
            return "moderate"
        return "good"

    panel_tier_fn = {"kge": kge_tier_pr, "rmse": rmse_tier_pr, "ext99": ext99_tier_pr, "lag1": lag1_tier_pr}

    def is_meaningful_pr(panel):
        tier = panel_tier_fn[panel]()
        if tier == "poor":
            return False
        if panel == "kge":
            return abs(kge_vals[0]) >= 1.0 or abs(kge_vals[2]) >= 1.0
        if panel == "rmse":
            return abs(rmse_vals[0]) >= 0.5 or abs(rmse_vals[2]) >= 0.5
        if panel == "ext99":
            return abs(ext99_vals[0]) >= 1.0 or abs(ext99_vals[2]) >= 1.0
        if panel == "lag1":
            if tier == "good":
                return False
            return abs(lag1_vals[0]) >= 5.0 or abs(lag1_vals[2]) >= 5.0
        return True

    def bar_color_at(i: int, diff: float, higher_is_better: bool | None) -> str:
        if i == 1:
            return "#b0b0b0"
        if higher_is_better is None:
            return "#4caf7d" if diff < 0 else "#e07060"
        if higher_is_better:
            return "#4caf7d" if diff > 0 else "#e07060"
        return "#4caf7d" if diff < 0 else "#e07060"

    def draw_panel_pr(
        ax,
        diffs,
        panel_key,
        higher_is_better,
        title,
        ylabel=None,
        fmt="{:+.2f}%",
        pad_p=0.03,
        pad_n=-0.08,
    ):
        tier = panel_tier_fn[panel_key]()
        meaningful_panel = is_meaningful_pr(panel_key)
        ymax_abs = max(abs(diffs)) if max(abs(diffs)) > 0 else 1

        for i, diff in enumerate(diffs):
            ax.axvspan(i - 0.48, i + 0.48, alpha=0.55, color=TIER_COLORS[tier], zorder=0, linewidth=0)

            color = bar_color_at(i, diff, higher_is_better)
            m_here = meaningful_panel and (i != 1)
            alpha = 1.0 if m_here else (0.38 if i != 1 else 0.55)
            hatch = None if m_here else ("///" if i != 1 else None)
            edge = "white" if m_here else ("#aaa" if i != 1 else "#888")
            ax.bar(i, diff, 0.55, color=color, alpha=alpha, hatch=hatch, edgecolor=edge, linewidth=0.5, zorder=2)

            pad = pad_p if diff >= 0 else pad_n
            if panel_key == "ext99":
                ax.text(i, diff + pad, fmt.format(diff), ha="center", va="bottom", fontsize=8.5, zorder=3)
            else:
                ax.text(i, diff + pad, fmt.format(diff), ha="center", va="bottom", fontsize=7.5, zorder=3)

            if i != 1 and not m_here:
                mid = (
                    diff * 0.45
                    if abs(diff) > ymax_abs * 0.05
                    else (pad_p * 0.4 if diff >= 0 else pad_n * 0.4)
                )
                ax.text(i, mid, "n.s.", ha="center", va="center", fontsize=7, color="#555", style="italic", zorder=4)

        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, fontsize=10, rotation=15)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.axhline(0, color="#555", linewidth=0.8, linestyle="--", zorder=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=10)

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.2))
    fig.patch.set_facecolor("#fafafa")
    for ax in axes.flat:
        ax.set_facecolor("#fafafa")

    draw_panel_pr(
        axes[0, 0],
        kge_vals,
        "kge",
        True,
        "KGE  (higher = better)",
        ylabel="% change vs bilinear",
    )
    draw_panel_pr(axes[0, 1], rmse_vals, "rmse", False, "RMSE  (lower = better)")
    draw_panel_pr(
        axes[1, 0],
        ext99_vals,
        "ext99",
        None,
        "Ext99 Bias%  (|bias| closer to 0 = better)",
        ylabel="|bias| diff vs bilinear (pp)",
        fmt="{:+.3f}",
        pad_p=0.008,
        pad_n=-0.025,
    )
    draw_panel_pr(axes[1, 1], lag1_vals, "lag1", False, "Lag1 Error  (lower = better)", pad_p=0.4, pad_n=-1.2)

    cons_b = mpatches.Patch(color="#4caf7d", label="Better than bilinear")
    bil_w = mpatches.Patch(color="#e07060", label="Worse than bilinear")
    ref_patch = mpatches.Patch(color="#b0b0b0", label="Bilinear (reference)")
    good_patch = mpatches.Patch(color=TIER_COLORS["good"], alpha=0.8, label="Tier: well-modelled")
    mod_patch = mpatches.Patch(color=TIER_COLORS["moderate"], alpha=0.8, label="Tier: moderate")
    poor_patch = mpatches.Patch(color=TIER_COLORS["poor"], alpha=0.8, label="Tier: poorly modelled")
    ns_patch = mpatches.Patch(facecolor="#ccc", hatch="///", edgecolor="#aaa", label="Not meaningful (n.s.)")

    fig.legend(
        handles=[cons_b, bil_w, ref_patch, good_patch, mod_patch, poor_patch, ns_patch],
        loc="upper center",
        ncol=4,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 1.015),
    )

    fig.suptitle(
        "Precipitation (pr): conservative vs bilinear vs nearest-neighbor regridding\n"
        "Bar height vs bilinear reference (0); Ext99 shows |bias| difference in percentage points.\n"
        "Background shading reflects absolute model performance for pr.",
        fontsize=11,
        y=1.085,
    )
    plt.tight_layout()
    return fig


def make_nn_vs_bil_chart_b64() -> str:
    fig = _make_nn_vs_bil_figure_identical_to_compare_script()
    return fig_to_b64(fig, dpi=150)


def make_pr3way_chart_b64() -> str:
    fig = _make_pr3way_figure_same_style()
    return fig_to_b64(fig, dpi=175)


# ═════════════════════════════════════════════════════════════════════════════
# HTML GENERATION — tier shading matches compare_regrid_methods.py
# ═════════════════════════════════════════════════════════════════════════════

TIER_HTML_BG = {"good": "#edf7ee", "moderate": "#fffbe6", "poor": "#fdf0f0"}


def _main_kge_tier(var: str) -> str:
    bv, nv = _metric_pair(var, "Val_KGE")
    best = max(bv, nv)
    if best >= 0.60:
        return "good"
    if best >= 0.30:
        return "moderate"
    return "poor"


def _main_rmse_tier(var: str) -> str:
    bv, nv = _metric_pair(var, "Val_RMSE_pooled")
    pct = abs(nv - bv) / (abs(bv) + 1e-12) * 100
    if pct >= 1.0:
        return "moderate"
    return "good"


def _main_ext99_tier(var: str) -> str:
    bv, nv = _metric_pair(var, "Val_Ext99_Bias%")
    best = min(abs(bv), abs(nv))
    if best <= 5.0:
        return "good"
    if best <= 10.0:
        return "moderate"
    return "poor"


def _main_lag1_tier(var: str) -> str:
    bv, nv = _metric_pair(var, "Val_Lag1_Err")
    best = min(bv, nv)
    if best <= 0.005:
        return "good"
    if best <= 0.015:
        return "moderate"
    return "poor"


MAIN_PANEL_TIER_FN = {
    "Val_KGE": _main_kge_tier,
    "Val_RMSE_pooled": _main_rmse_tier,
    "Val_Ext99_Bias%": _main_ext99_tier,
    "Val_Lag1_Err": _main_lag1_tier,
}


def _main_nn_vs_bil_diffs(var: str) -> tuple[float, float, float, float]:
    """KGE%, RMSE%, ext99 pp, Lag1% — same definitions as compare_regrid_methods."""
    bk, nk = _metric_pair(var, "Val_KGE")
    br, nr = _metric_pair(var, "Val_RMSE_pooled")
    be, ne = _metric_pair(var, "Val_Ext99_Bias%")
    bl, nl = _metric_pair(var, "Val_Lag1_Err")
    kge_d = (nk - bk) / (abs(bk) + 1e-12) * 100
    rmse_d = (nr - br) / (abs(br) + 1e-12) * 100
    ext99_d = abs(ne) - abs(be)
    lag1_d = (nl - bl) / (abs(bl) + 1e-12) * 100
    return kge_d, rmse_d, ext99_d, lag1_d


def is_meaningful_main(var: str, panel_key: str) -> bool:
    """(n.s.) logic from compare_regrid_methods.py."""
    tier = MAIN_PANEL_TIER_FN[
        {
            "kge": "Val_KGE",
            "rmse": "Val_RMSE_pooled",
            "ext99": "Val_Ext99_Bias%",
            "lag1": "Val_Lag1_Err",
        }[panel_key]
    ](var)
    if tier == "poor":
        return False
    kge_d, rmse_d, ext99_d, lag1_d = _main_nn_vs_bil_diffs(var)
    if panel_key == "kge" and abs(kge_d) < 1.0:
        return False
    if panel_key == "rmse" and abs(rmse_d) < 0.5:
        return False
    if panel_key == "ext99" and abs(ext99_d) < 1.0:
        return False
    if panel_key == "lag1":
        if tier == "good":
            return False
        if abs(lag1_d) < 5.0:
            return False
    return True


def build_main_table() -> str:
    vars_all = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
    metrics = [
        ("KGE", "Val_KGE", False, "kge"),
        ("RMSE", "Val_RMSE_pooled", True, "rmse"),
        ("Ext99 Bias %", "Val_Ext99_Bias%", None, "ext99"),
        ("Lag1 Error", "Val_Lag1_Err", True, "lag1"),
    ]

    rows = []
    for var in vars_all:
        if var != "pr":
            bi_row = bi_csv[bi_csv["Variable"] == var]
            nn_row = nn_csv[nn_csv["Variable"] == var]
            if bi_row.empty or nn_row.empty:
                continue

        for mi, (label, col, lower_better, panel_key) in enumerate(metrics):
            bv, nv = _metric_pair(var, col)
            tier = MAIN_PANEL_TIER_FN[col](var)
            bg = TIER_HTML_BG[tier]

            if lower_better is None:
                bi_closer = abs(bv) < abs(nv)
            elif lower_better:
                bi_closer = bv < nv
            else:
                bi_closer = bv > nv

            ns = not is_meaningful_main(var, panel_key)

            def fmt(v, is_better):
                s = f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
                if is_better and not ns:
                    return f'<td style="font-weight:bold;color:#2a7a50">{s}</td>'
                if is_better and ns:
                    return f'<td style="font-weight:bold;color:#2a7a50">{s}</td>'
                return f"<td>{s}</td>"

            ns_tag = ' <span class="ns">(n.s.)</span>' if ns else ""
            td_var = f'<td rowspan="4" class="var-cell">{var}</td>' if mi == 0 else ""
            rows.append(
                f'<tr style="background:{bg}">{td_var}'
                f"<td>{label}{ns_tag}</td>"
                f"{fmt(bv, bi_closer)}{fmt(nv, not bi_closer)}</tr>"
            )
        rows.append('<tr><td colspan="4" class="sep"></td></tr>')

    return "\n".join(rows)


def _pr3_v(method: str, col: str) -> float:
    return float(pr3_csv.loc[pr3_csv["Method"] == method, col].values[0])


def _pr3_kge_tier() -> str:
    best = max(_pr3_v(m, "Val_KGE") for m in ("conservative", "bilinear", "nearest"))
    if best >= 0.60:
        return "good"
    if best >= 0.30:
        return "moderate"
    return "poor"


def _pr3_rmse_tier() -> str:
    br = _pr3_v("bilinear", "Val_RMSE_pooled")
    pct_c = abs(_pr3_v("conservative", "Val_RMSE_pooled") - br) / (abs(br) + 1e-12) * 100
    pct_n = abs(_pr3_v("nearest", "Val_RMSE_pooled") - br) / (abs(br) + 1e-12) * 100
    if pct_c >= 1.0 or pct_n >= 1.0:
        return "moderate"
    return "good"


def _pr3_ext99_tier() -> str:
    best = min(abs(_pr3_v(m, "Val_Ext99_Bias%")) for m in ("conservative", "bilinear", "nearest"))
    if best <= 5.0:
        return "good"
    if best <= 10.0:
        return "moderate"
    return "poor"


def _pr3_lag1_tier() -> str:
    best = min(_pr3_v(m, "Val_Lag1_Err") for m in ("conservative", "bilinear", "nearest"))
    if best <= 0.005:
        return "good"
    if best <= 0.015:
        return "moderate"
    return "poor"


def _pr3_wdf_tier(col: str) -> str:
    """Spread across methods: small spread = good (methods agree)."""
    vals = [_pr3_v(m, col) for m in ("conservative", "bilinear", "nearest")]
    if max(vals) - min(vals) < 1.0:
        return "good"
    return "moderate"


PR3_ROW_TIER_FN = {
    "Val_KGE": _pr3_kge_tier,
    "Val_RMSE_pooled": _pr3_rmse_tier,
    "Val_Ext99_Bias%": _pr3_ext99_tier,
    "Val_Lag1_Err": _pr3_lag1_tier,
    "Val_WDF_Obs%": lambda: _pr3_wdf_tier("Val_WDF_Obs%"),
    "Val_WDF_Sim%": lambda: _pr3_wdf_tier("Val_WDF_Sim%"),
}


def build_pr3_table() -> str:
    metrics = [
        ("KGE", "Val_KGE"),
        ("RMSE", "Val_RMSE_pooled"),
        ("Ext99 Bias %", "Val_Ext99_Bias%"),
        ("Lag1 Error", "Val_Lag1_Err"),
        ("WDF Obs %", "Val_WDF_Obs%"),
        ("WDF Sim %", "Val_WDF_Sim%"),
    ]
    methods = list(pr3_csv["Method"])

    header = "<tr><th>Metric</th>" + "".join(f"<th>{m.title()}</th>" for m in methods) + "</tr>"
    rows = [header]
    for label, col in metrics:
        vals = [pr3_csv.loc[pr3_csv["Method"] == m, col].values[0] for m in methods]
        tier = PR3_ROW_TIER_FN[col]()
        row_bg = TIER_HTML_BG[tier]
        if "RMSE" in col or "Lag1" in col:
            best_i = int(np.argmin([abs(v) for v in vals]))
        elif "Ext99" in col:
            best_i = int(np.argmin([abs(v) for v in vals]))
        elif "Bias" in col and "Ext99" not in col:
            best_i = int(np.argmin([abs(v) for v in vals]))
        else:
            best_i = int(np.argmax(vals))

        cells = []
        for i, v in enumerate(vals):
            s = f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
            if i == best_i:
                cells.append(f'<td style="font-weight:bold;color:#2a7a50">{s}</td>')
            else:
                cells.append(f"<td>{s}</td>")
        rows.append(f'<tr style="background:{row_bg}"><td>{label}</td>{"".join(cells)}</tr>')

    return "\n".join(rows)


def build_html():
    print("Generating charts...")
    chart1_b64 = make_nn_vs_bil_chart_b64()
    chart2_b64 = make_pr3way_chart_b64()

    print("Building main metrics table...")
    main_table_rows = build_main_table()
    pr3_table_rows = build_pr3_table()

    print("Embedding pre-post test8 gallery...")
    pre_post_images = []
    dates = ["20110715", "20060120", "20130801"]
    variables = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
    for date in dates:
        for var in variables:
            fname = f"pre_post_{var}_{date}.png"
            p = PRE_POST_DIR / fname
            if p.exists():
                pre_post_images.append((var, date, img_to_b64(p)))

    print("Assembling HTML...")
    prepost_html = ""
    for var, date, b64 in pre_post_images:
        d = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        prepost_html += f'<h3>{var} — {d}</h3>\n'
        prepost_html += f'<img src="data:image/png;base64,{b64}" alt="{var} {d}"/>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Combined Regridding Report — Bilinear vs NN + PR 3-Way</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 1000px; margin: 40px auto; color: #222; background: #fff; padding: 0 20px; }}
  h1 {{ font-size: 1.5em; border-bottom: 2px solid #333; padding-bottom: 6px; }}
  h2 {{ font-size: 1.2em; margin-top: 2.5em; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  h3 {{ font-size: 1em; margin-top: 1.5em; color: #555; }}
  p {{ line-height: 1.65; }}
  .note {{ font-size: 0.85em; color: #666; margin-top: 0.4em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.92em; margin-top: 1em; }}
  th {{ background: #333; color: #fff; padding: 8px 12px; text-align: left; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #e8e8e8; }}
  .ns {{ font-size: 0.85em; color: #888; font-style: italic; }}
  .var-cell {{ vertical-align: middle; font-weight: bold; border-right: 1px solid #ddd; }}
  .sep {{ padding: 3px; border: none; background: #fff; }}
  .tier-legend {{ display: flex; gap: 1.5em; margin: 0.5em 0 1em; font-size: 0.85em; }}
  .tier-legend span {{ display: flex; align-items: center; gap: 0.3em; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; display: inline-block; }}
  img {{ width: 100%; max-width: 960px; margin: 1em 0; border: 1px solid #ddd; }}
  .toc {{ background: #f8f8f8; padding: 1em 1.5em; border: 1px solid #ddd; margin: 1em 0 2em; }}
  .toc ul {{ margin: 0.3em 0; padding-left: 1.5em; }}
  .toc li {{ margin: 0.3em 0; }}
  .toc a {{ color: #2a7a50; text-decoration: none; }}
  .toc a:hover {{ text-decoration: underline; }}
  .highlight-row {{ background: #fffde0; }}
</style>
</head>
<body>

<h1>Bilinear vs Nearest-Neighbor Regridding &mdash; Combined Report</h1>
<p class="note">MPI-ESM1-2-HR &bull; OTBC physics-corrected &bull; Iowa domain (216&times;192) &bull; Validation 2006&ndash;2014 &bull; TEST8_SEED=42</p>

<div class="toc">
<strong>Contents</strong>
<ul>
  <li><a href="#summary">1. Summary &amp; Recommendations</a></li>
  <li><a href="#quant-all">2. Quantitative Metrics: All Variables (Bilinear vs NN)</a></li>
  <li><a href="#chart-pct">3. Figure: Key Metrics (same as regrid_comparison_report)</a></li>
  <li><a href="#pr3way">4. NEW: Precipitation 3-Way Comparison (Conservative / Bilinear / NN)</a></li>
  <li><a href="#prepost">5. Pre-test8 vs Post-test8 Gallery</a></li>
</ul>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<h2 id="summary">1. Summary &amp; Recommendations</h2>
<p>
For the four well-modelled variables (tasmax, tasmin, rsds, huss), no meaningful differences
exist between bilinear and NN regridding on any metric. In the absence of a clear winner,
NN is preferable because it makes fewer assumptions: bilinear interpolation introduces spatial
smoothing across 100&nbsp;km GCM cell boundaries that requires justification, whereas NN makes
no such assumption.
</p>
<p>
For <strong>wind</strong>, NN reduces Ext99 Bias&nbsp;% by 2.1 percentage points (moderate tier),
while bilinear reduces RMSE by 1.3%. Since extreme wind behavior is more consequential for
downstream impact applications than mean error, NN is the preferred choice.
</p>
<p>
<strong>Precipitation 3-way comparison:</strong> The main six-variable pipeline used conservative pr in both
bilinear and NN paths. We additionally regridded pr with bilinear and with NN to compare extremes (Section 4).
</p>
<ul>
  <li><strong>All three methods perform poorly</strong> for pr on KGE, Ext99&nbsp;Bias&nbsp;%, and Lag1
      (all below &ldquo;moderate&rdquo; tier thresholds). The stochastic downscaling (test8) overwhelms
      the regridding signal for precipitation regardless of method.</li>
  <li><strong>NN and conservative are nearly identical</strong> across all pr metrics (Ext99&nbsp;Bias&nbsp;%
      &minus;13.3% vs &minus;13.5%, KGE 0.029 vs 0.029).</li>
  <li><strong>Bilinear shows lower RMSE</strong> (&minus;3% vs conservative/NN) but scores worse
      on Ext99&nbsp;Bias&nbsp;% (&minus;17.3% vs &minus;13%), Lag1, and KGE. The RMSE advantage is
      likely an artifact of bilinear&rsquo;s spatial smoothing, which dampens variance and thus
      reduces squared error while simultaneously worsening extreme underprediction.
      However, all of these differences fall within the &ldquo;poor&rdquo; tier, limiting their
      practical significance.</li>
  <li><strong>Recommendation:</strong> For precipitation, conservative remains the standard choice on
      physical grounds (mass/flux conservation across grid cells). The empirical post-test8 metrics
      do not strongly differentiate the methods, since all perform poorly&mdash;but they offer no
      reason to deviate from the conventional practice of using conservative for pr.</li>
</ul>

<!-- ═══════════════════════════════════════════════════════════════ -->
<h2 id="quant-all">2. Quantitative Metrics: All Variables (Bilinear vs NN)</h2>
<p class="note">
  Bold green = better value. Row shading reflects absolute performance tier.
  <em>n.s.</em> = difference &lt; 1%, not meaningful.
  For <strong>pr</strong>, the Bilinear and Nearest-Neighbor columns are from dedicated pr regridding runs
  (same test8 setup as Section 4); other variables still reflect the full six-variable pipelines.
</p>
<div class="tier-legend">
  <span><span class="dot" style="background:#2a7a50"></span> Well-modelled</span>
  <span><span class="dot" style="background:#b8860b"></span> Moderate</span>
  <span><span class="dot" style="background:#c0392b"></span> Poorly modelled</span>
</div>
<table>
  <thead>
    <tr><th>Variable</th><th>Metric</th><th>Bilinear</th><th>Nearest-Neighbor</th></tr>
  </thead>
  <tbody>
{main_table_rows}
  </tbody>
</table>
<p class="note">Section 4 adds the <strong>conservative</strong> pr baseline alongside bilinear and NN.</p>

<!-- ═══════════════════════════════════════════════════════════════ -->
<h2 id="chart-pct">3. Figure: % Change in Key Metrics (NN relative to Bilinear)</h2>
<p class="note">
  Same figure as <code>regrid_comparison_report.html</code> (tasmax, tasmin, rsds, wind, huss only; pr excluded there).
  Green bars: NN better &nbsp;|&nbsp; Red: bilinear better. Background = absolute model quality. Hatched = not meaningful (n.s.).
  Ext99 uses <strong>absolute difference in |bias|</strong> (percentage points), not a percent change.
</p>
<p class="note" style="border-left:3px solid #888;padding-left:8px;color:#555">
  <strong>Note on hatching stability:</strong> Some variable&ndash;metric pairs sit very close to the
  meaningfulness thresholds (0.5&thinsp;% for RMSE, 5&thinsp;% for Lag1). Because test8 includes a
  stochastic component, small run-to-run variations can push borderline cases (e.g.&nbsp;tasmin&nbsp;RMSE,
  rsds&nbsp;Lag1) across the threshold, flipping their hatched/unhatched classification without any
  change in the underlying regridding. In practice, any metric near the threshold is effectively
  negligible regardless of which side it falls on.
</p>
<img src="data:image/png;base64,{chart1_b64}" alt="NN vs bilinear metric comparison"/>

<!-- ═══════════════════════════════════════════════════════════════ -->
<h2 id="pr3way">4. Precipitation 3-Way Comparison (Conservative / Bilinear / NN)</h2>
<p>
This section answers Bhuwan's question: &ldquo;Is NN possible for precip? Compare NN, bilinear,
and conservative for precipitation.&rdquo; All three methods use the same test8 stochastic
downscaler (multiplicative disaggregator + Schaake shuffle) with TEST8_SEED=42.
</p>
<table>
{pr3_table_rows}
</table>
<p class="note">Best value per metric in bold green. Ext99 Bias % closest to zero is best.</p>

<h3>Figure: same 2×2 layout, precipitation three-way (vs bilinear reference)</h3>
<p class="note">
  Conservative and NN are compared to <strong>bilinear as reference</strong> (bilinear bar = 0).
  KGE, RMSE, and Lag1 use % change vs bilinear; Ext99 uses <strong>|bias| difference in pp</strong> vs bilinear (same convention as the figure above).
  Gray bar = reference; green/red = better/worse than bilinear for conservative or NN.
</p>
<img src="data:image/png;base64,{chart2_b64}" alt="PR 3-way same-style figure"/>

<p>
<strong>Key finding:</strong> Bilinear smoothing degrades pr extremes substantially (Ext99 Bias
&minus;17.3% vs &minus;13.3% for NN/conservative). Conservative and NN produce nearly
identical results for all pr metrics.
</p>

<!-- ═══════════════════════════════════════════════════════════════ -->
<h2 id="prepost">5. Pre-test8 vs Post-test8 Gallery</h2>
<p class="note">
<strong>pr:</strong> three columns per row &mdash; conservative, bilinear, nearest-neighbor regrid (pr_3way inputs and <code>Stochastic_pr_*.npz</code>); bottom row is GridMET.<br>
<strong>Other variables:</strong> pre-test8 bilinear | pre-test8 NN | NN&minus;bilinear; post-test8 bilinear | post-test8 NN | NN&minus;bilinear; GridMET.<br>
Snapshot dates: 2011-07-15, 2006-01-20, 2013-08-01.
</p>
{prepost_html}

<hr>
<p class="note" style="text-align:center;margin-top:2em">
  Generated by build_combined_report.py &bull; Drops of Resilience
</p>
</body>
</html>"""

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nWrote {OUT_HTML} ({OUT_HTML.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    build_html()
