"""
compare_regrid_methods.py — Generate bilinear vs NN regridding comparison report.
Outputs: week3/regrid_comparison_report.html
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import base64
import tempfile
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE     = r"C:\drops-of-resilience\bilinear-vs-nn-regridding"
BIL_CSV  = os.path.join(BASE, "pipeline", "output", "bilinear",         "Bilinear_Table1_Pooled_Metrics.csv")
NN_CSV   = os.path.join(BASE, "pipeline", "output", "nearest_neighbor", "NN_Table1_Pooled_Metrics.csv")
OUT_HTML = os.path.join(BASE, "regrid_comparison_report.html")

# ── Load ───────────────────────────────────────────────────────────────────────
bil = pd.read_csv(BIL_CSV).set_index("Variable")
nn  = pd.read_csv(NN_CSV).set_index("Variable")

VARS       = ["tasmax", "tasmin", "rsds", "wind", "huss"]
VAR_LABELS = ["tasmax", "tasmin", "rsds", "wind", "huss"]

# ── Differences ────────────────────────────────────────────────────────────────
kge_diff   = np.array([(nn.loc[v,"Val_KGE"]        - bil.loc[v,"Val_KGE"])        / abs(bil.loc[v,"Val_KGE"])        * 100 for v in VARS])
rmse_diff  = np.array([(nn.loc[v,"Val_RMSE_pooled"] - bil.loc[v,"Val_RMSE_pooled"]) / bil.loc[v,"Val_RMSE_pooled"]   * 100 for v in VARS])
ext99_diff = np.array([abs(nn.loc[v,"Val_Ext99_Bias%"]) - abs(bil.loc[v,"Val_Ext99_Bias%"])                                 for v in VARS])
lag1_diff  = np.array([(nn.loc[v,"Val_Lag1_Err"]   - bil.loc[v,"Val_Lag1_Err"])   / abs(bil.loc[v,"Val_Lag1_Err"])   * 100 for v in VARS])

# ── Performance tiers (absolute quality of the better model) ───────────────────
# Used for background shading: green = both models perform well here,
# yellow = moderate, red = both perform poorly (winner label is noise)
TIER_COLORS = {"good": "#d6eed9", "moderate": "#fff3cd", "poor": "#fde0df"}
TIER_LABELS = {"good": "both models perform well", "moderate": "moderate performance", "poor": "both models perform poorly — winner is noise"}

def kge_tier(var):
    best = max(bil.loc[var,"Val_KGE"], nn.loc[var,"Val_KGE"])
    if best >= 0.60: return "good"
    if best >= 0.30: return "moderate"
    return "poor"

def ext99_tier(var):
    best = min(abs(bil.loc[var,"Val_Ext99_Bias%"]), abs(nn.loc[var,"Val_Ext99_Bias%"]))
    if best <=  5.0: return "good"
    if best <= 10.0: return "moderate"
    return "poor"

def lag1_tier(var):
    best = min(bil.loc[var,"Val_Lag1_Err"], nn.loc[var,"Val_Lag1_Err"])
    if best <= 0.005: return "good"
    if best <= 0.015: return "moderate"
    return "poor"

def rmse_tier(var):
    # RMSE units differ per variable — use % difference magnitude as a proxy
    pct = abs(rmse_diff[VARS.index(var)])
    if pct >= 1.0: return "moderate"   # notable difference
    return "good"                       # differences are negligible

PANEL_TIER_FN = {
    "kge":   kge_tier,
    "rmse":  rmse_tier,
    "ext99": ext99_tier,
    "lag1":  lag1_tier,
}

# ── Meaningfulness (is the winning margin worth discussing?) ───────────────────
# A win only matters if (a) at least one model performs adequately AND
# (b) the difference is large enough to be non-negligible.
def is_meaningful(var, panel):
    tier = PANEL_TIER_FN[panel](var)
    if tier == "poor":
        return False
    if panel == "kge"   and abs(kge_diff  [VARS.index(var)]) < 1.0:   return False
    if panel == "rmse"  and abs(rmse_diff [VARS.index(var)]) < 0.5:   return False
    if panel == "ext99" and abs(ext99_diff[VARS.index(var)]) < 1.0:   return False
    if panel == "lag1":
        if tier == "good":
            return False
        if abs(lag1_diff[VARS.index(var)]) < 5.0:
            return False
    return True

# ── Drawing helpers ────────────────────────────────────────────────────────────
def bar_color(diff, higher_is_better):
    if higher_is_better:
        return "#4caf7d" if diff > 0 else "#e07060"
    else:
        return "#4caf7d" if diff < 0 else "#e07060"

def draw_panel(ax, diffs, panel_key, higher_is_better, title,
               ylabel=None, fmt="{:+.2f}%", pad_p=0.03, pad_n=-0.08):
    tier_fn = PANEL_TIER_FN[panel_key]
    ymax_abs = max(abs(diffs)) if max(abs(diffs)) > 0 else 1

    for i, (var, diff) in enumerate(zip(VARS, diffs)):
        tier      = tier_fn(var)
        meaningful = is_meaningful(var, panel_key)

        # Background shading per variable group
        ax.axvspan(i - 0.48, i + 0.48, alpha=0.55,
                   color=TIER_COLORS[tier], zorder=0, linewidth=0)

        # Bar
        color = bar_color(diff, higher_is_better)
        alpha = 1.0 if meaningful else 0.38
        hatch = None  if meaningful else "///"
        edge  = "white" if meaningful else "#aaa"
        ax.bar(i, diff, 0.55, color=color, alpha=alpha, hatch=hatch,
               edgecolor=edge, linewidth=0.5, zorder=2)

        # Numeric label
        pad = pad_p if diff >= 0 else pad_n
        ax.text(i, diff + pad, fmt.format(diff),
                ha="center", va="bottom", fontsize=7.5, zorder=3)

        # "n.s." overlay on non-meaningful bars
        if not meaningful:
            mid = diff * 0.45 if abs(diff) > ymax_abs * 0.05 else (pad_p * 0.4 if diff >= 0 else pad_n * 0.4)
            ax.text(i, mid, "n.s.", ha="center", va="center",
                    fontsize=7, color="#555", style="italic", zorder=4)

    ax.set_xticks(np.arange(len(VARS)))
    ax.set_xticklabels(VAR_LABELS, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.axhline(0, color="#555", linewidth=0.8, linestyle="--", zorder=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)

# ── Figure ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
fig.patch.set_facecolor("#fafafa")
for ax in axes.flat:
    ax.set_facecolor("#fafafa")

draw_panel(axes[0,0], kge_diff,   "kge",   True,  "KGE  (higher = better)",
           ylabel="% change vs bilinear")
draw_panel(axes[0,1], rmse_diff,  "rmse",  False, "RMSE  (lower = better)")
draw_panel(axes[1,0], ext99_diff, "ext99", False, "Ext99 Bias%  (|bias| closer to 0 = better)",
           ylabel="absolute diff (pp)", fmt="{:+.3f}", pad_p=0.008, pad_n=-0.025)
draw_panel(axes[1,1], lag1_diff,  "lag1",  False, "Lag1 Error  (lower = better)",
           pad_p=0.4, pad_n=-1.2)

# Legend: method winner + performance tier backgrounds
nn_patch   = mpatches.Patch(color="#4caf7d", label="NN better")
bil_patch  = mpatches.Patch(color="#e07060", label="Bilinear better")
good_patch = mpatches.Patch(color=TIER_COLORS["good"],     alpha=0.8, label="Both models perform well")
mod_patch  = mpatches.Patch(color=TIER_COLORS["moderate"], alpha=0.8, label="Moderate performance")
poor_patch = mpatches.Patch(color=TIER_COLORS["poor"],     alpha=0.8, label="Both perform poorly — winner is noise")
ns_patch   = mpatches.Patch(facecolor="#ccc", hatch="///", edgecolor="#aaa", label="Not meaningful (n.s.)")

fig.legend(handles=[nn_patch, bil_patch, good_patch, mod_patch, poor_patch, ns_patch],
           loc="upper center", ncol=3, frameon=False, fontsize=9,
           bbox_to_anchor=(0.5, 1.02))

fig.suptitle("Bilinear vs Nearest-Neighbor Regridding: % change (NN relative to Bilinear)\n"
             "Background shading reflects absolute model performance, independent of which method wins.",
             fontsize=11, y=1.07)
plt.tight_layout()

# Encode figure to base64
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
    fig.savefig(tmp.name, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    tmp_path = tmp.name
with open(tmp_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()
os.unlink(tmp_path)
plt.close()

# ── HTML table ─────────────────────────────────────────────────────────────────
METRICS = [
    ("Val_KGE",         "KGE",          4, True,  "kge"),
    ("Val_RMSE_pooled", "RMSE",         4, False, "rmse"),
    ("Val_Ext99_Bias%", "Ext99 Bias %", 2, None,  "ext99"),
    ("Val_Lag1_Err",    "Lag1 Error",   5, False, "lag1"),
]

def winner_style(bv, nv, hib):
    if hib is None:
        if abs(nv) < abs(bv): return "", "font-weight:bold;color:#2a7a50"
        if abs(bv) < abs(nv): return "font-weight:bold;color:#2a7a50", ""
    elif hib:
        if nv > bv: return "", "font-weight:bold;color:#2a7a50"
        if bv > nv: return "font-weight:bold;color:#2a7a50", ""
    else:
        if nv < bv: return "", "font-weight:bold;color:#2a7a50"
        if bv < nv: return "font-weight:bold;color:#2a7a50", ""
    return "", ""

# Map tier to HTML row background
TIER_HTML_BG = {"good": "#edf7ee", "moderate": "#fffbe6", "poor": "#fdf0f0"}
TIER_HTML_LABEL = {
    "good":     "&#9679; well-modelled",
    "moderate": "&#9679; moderate",
    "poor":     "&#9679; poorly modelled — comparison unreliable",
}
TIER_DOT_COLOR = {"good": "#2a7a50", "moderate": "#b8860b", "poor": "#c0392b"}

table_rows = ""
for var in VARS:
    first = True
    for col, label, dec, hib, panel_key in METRICS:
        bv  = bil.loc[var, col]
        nv  = nn.loc[var, col]
        bs, ns = winner_style(bv, nv, hib)
        tier = PANEL_TIER_FN[panel_key](var)
        row_bg = TIER_HTML_BG[tier]
        meaningful = is_meaningful(var, panel_key)
        ns_note = ' <span style="color:#888;font-style:italic;font-size:0.85em">(n.s.)</span>' if not meaningful else ""

        if first:
            var_cell = (f'<td rowspan="{len(METRICS)}" style="vertical-align:middle;'
                        f'font-weight:bold;border-right:1px solid #ddd">'
                        f'{var}</td>')
        else:
            var_cell = ""

        table_rows += f"""
        <tr style="background:{row_bg}">
          {var_cell}
          <td>{label}{ns_note}</td>
          <td style="{bs}">{bv:.{dec}f}</td>
          <td style="{ns}">{nv:.{dec}f}</td>
        </tr>"""
        first = False
    table_rows += '<tr><td colspan="4" style="padding:3px;border:none;background:#fff"></td></tr>'

# ── HTML ───────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Bilinear vs NN Regridding Comparison</title>
<style>
  body  {{ font-family: Georgia, serif; max-width: 920px; margin: 40px auto; color: #222; background: #fff; }}
  h1   {{ font-size: 1.4em; border-bottom: 2px solid #333; padding-bottom: 6px; }}
  h2   {{ font-size: 1.1em; margin-top: 2em; color: #444; }}
  p    {{ line-height: 1.65; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.92em; margin-top: 1em; }}
  th   {{ background: #333; color: #fff; padding: 8px 12px; text-align: left; }}
  td   {{ padding: 6px 12px; border-bottom: 1px solid #e8e8e8; }}
  .note {{ font-size: 0.85em; color: #666; margin-top: 0.4em; }}
  img  {{ width: 100%; max-width: 880px; margin: 1em 0; }}
  .tier-legend {{ display:flex; gap:1.5em; margin:0.5em 0 1em; font-size:0.85em; }}
  .tier-legend span {{ display:flex; align-items:center; gap:0.3em; }}
  .dot {{ width:11px; height:11px; border-radius:50%; display:inline-block; }}
</style>
</head>
<body>

<h1>Bilinear vs Nearest-Neighbor Regridding &mdash; Comparison Report</h1>
<p class="note">MPI-ESM1-2-HR &bull; OTBC physics-corrected &bull; Iowa domain &bull; Validation period 1981&ndash;2014</p>
<p class="note"><strong>Note on precipitation (pr):</strong> Both paths use conservative regridding for pr regardless of the bilinear/NN choice, because conservative is physically required to preserve total rainfall when moving from 100&nbsp;km to 4&nbsp;km. pr metrics are therefore identical between paths and are excluded from this comparison. The bilinear vs. NN distinction applies only to tasmax, tasmin, rsds, wind, and huss.</p>

<h2>Summary</h2>
<p>
For the four well-modelled variables (tasmax, tasmin, rsds, huss), no meaningful differences
exist between bilinear and NN regridding on any metric. In the absence of a clear winner,
NN is preferable because it makes fewer assumptions: bilinear interpolation introduces spatial
smoothing across 100&nbsp;km GCM cell boundaries that requires justification, whereas NN makes
no such assumption. NN also carries a modest computational advantage, though that is a secondary consideration.
</p>
<p>
For <strong>wind</strong>, NN reduces Ext99 Bias% by 2.1 percentage points (moderate performance tier),
while bilinear reduces RMSE by 1.3%. Since extreme wind behavior is more consequential for
downstream impact applications than mean error, NN is the preferred choice for wind.
</p>
<p>
<strong>Overall recommendation:</strong> switch to NN regridding for all variables (retaining
conservative for pr, as required). NN makes fewer assumptions than bilinear and matches or
outperforms it on the metrics that matter.
</p>

<h2>Figure: % Change in Key Metrics (NN relative to Bilinear)</h2>
<p class="note">
  Green bars: NN performs better &nbsp;|&nbsp; Red bars: Bilinear performs better.<br>
  <strong>Background shading</strong> reflects absolute model quality for that variable, independent of which method wins
  (green = both models perform well; yellow = moderate; red = both perform poorly).<br>
  <strong>Hatched bars (n.s.)</strong> indicate the difference is not meaningful. A bar is hatched if any of the following apply:
</p>
<ul class="note" style="margin-top:0.2em;line-height:1.8">
  <li>The background is <strong>red</strong> — both models perform poorly on this metric, so the winner label is noise.</li>
  <li>The % difference is too small to matter: &lt;1% for KGE, &lt;0.5% for RMSE, &lt;5% for Lag1.</li>
  <li>The absolute difference is too small to matter: &lt;1 percentage point for Ext99 Bias%.</li>
  <li><em>Lag1 only</em>: if the background is <strong>green</strong>, both models already have near-zero autocorrelation error (&le;0.005),
      so even a large % change represents a negligible absolute improvement.</li>
</ul>
<img src="data:image/png;base64,{img_b64}" alt="Bilinear vs NN metric comparison">

<h2>Table: Pooled Validation Metrics</h2>
<p class="note">
  Bold green = better value. Row shading reflects absolute performance tier (same as figure background).
  <em>n.s.</em> = difference not meaningful.
</p>
<div class="tier-legend">
  <span><span class="dot" style="background:#2a7a50"></span> Well-modelled</span>
  <span><span class="dot" style="background:#b8860b"></span> Moderate</span>
  <span><span class="dot" style="background:#c0392b"></span> Poorly modelled &mdash; winner comparison unreliable</span>
</div>
<table>
  <thead>
    <tr><th>Variable</th><th>Metric</th><th>Bilinear</th><th>Nearest-Neighbor</th></tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

</body>
</html>"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report written to: {OUT_HTML}")
