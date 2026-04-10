"""
Verify PR_INTENSITY_BLEND choice using an explicit composite score on Table1 CSVs.
Appends one line to ../WORKLOG.md with the ranking table.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PC_ROOT.parent
OUT_BASE = REPO_ROOT / "pipeline" / "output" / "test8_v4"


def score_row(pr_ext99_abs: float, pr_rmse: float, w_rmse: float = 0.15) -> float:
    return pr_ext99_abs + w_rmse * pr_rmse


def main() -> int:
    folders = {
        "parity": OUT_BASE / "parity",
        "blend0.25": OUT_BASE / "experiment_blend0p25",
        "blend0.35": OUT_BASE / "experiment_blend0p35",
        "blend0.45": OUT_BASE / "experiment_blend0p45",
        "blend0.55": OUT_BASE / "experiment_blend0p55",
        "blend0.65": OUT_BASE / "experiment_blend0p65",
        "blend1.0": OUT_BASE / "experiment",
    }
    rows = []
    for label, folder in folders.items():
        csv_path = folder / "V8_Table1_Pooled_Metrics_Stochastic.csv"
        if not csv_path.is_file():
            continue
        with csv_path.open(newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            pr = next(x for x in rdr if x["Variable"] == "pr")
        ext = abs(float(pr["Val_Ext99_Bias%"]))
        rmse = float(pr["Val_RMSE_pooled"])
        rows.append((label, ext, rmse, score_row(ext, rmse)))

    rows.sort(key=lambda x: x[3])
    print("Rank (lower score better): abs(Ext99%)+0.15*RMSE on pr")
    for label, ext, rmse, sc in rows:
        print(f"  {label:12} score={sc:.4f}  |Ext99|={ext:.4f}  RMSE={rmse:.4f}")

    best = rows[0][0] if rows else "n/a"
    print(f"\nBest by rule: {best}")
    if best != "blend0.65":
        print(
            "NOTE: Canonical benchmark folder remains experiment_blend0p65 per project plan; "
            "revisit if you adopt this scoring rule as authoritative.",
            file=sys.stderr,
        )

    log_path = PC_ROOT / "WORKLOG.md"
    block = (
        "\n## 2026-04-06 — Blend verification result (script)\n\n"
        f"Rule: `score = abs(pr Ext99 bias %) + 0.15 * pr RMSE` (lower better).\n\n"
        "| Rank | Run | Score | |Ext99| | RMSE |\n"
        "|------|-----|-------|--------|------|\n"
    )
    for i, (label, ext, rmse, sc) in enumerate(rows, 1):
        block += f"| {i} | {label} | {sc:.4f} | {ext:.4f} | {rmse:.4f} |\n"
    block += f"\n**Best by rule:** `{best}`. Benchmark still uses **blend0.65** per implementation plan.\n"

    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(block)
    print(f"\nAppended summary to {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
