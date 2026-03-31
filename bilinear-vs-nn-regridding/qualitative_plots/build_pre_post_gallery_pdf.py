"""
One PDF for sharing: all figures from pre_post_test8/ in gallery order + short cover page.

Usage:
  python build_pre_post_gallery_pdf.py
  python build_pre_post_gallery_pdf.py --out path/to/out.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# Same order as pre_post_test8/index.html
FIGURES: list[tuple[str, str, str]] = [
    ("pr", "2011-07-15", "pre_post_pr_20110715.png"),
    ("tasmax", "2011-07-15", "pre_post_tasmax_20110715.png"),
    ("tasmin", "2011-07-15", "pre_post_tasmin_20110715.png"),
    ("rsds", "2011-07-15", "pre_post_rsds_20110715.png"),
    ("wind", "2011-07-15", "pre_post_wind_20110715.png"),
    ("huss", "2011-07-15", "pre_post_huss_20110715.png"),
    ("pr", "2006-01-20", "pre_post_pr_20060120.png"),
    ("tasmax", "2006-01-20", "pre_post_tasmax_20060120.png"),
    ("tasmin", "2006-01-20", "pre_post_tasmin_20060120.png"),
    ("rsds", "2006-01-20", "pre_post_rsds_20060120.png"),
    ("wind", "2006-01-20", "pre_post_wind_20060120.png"),
    ("huss", "2006-01-20", "pre_post_huss_20060120.png"),
    ("pr", "2013-08-01", "pre_post_pr_20130801.png"),
    ("tasmax", "2013-08-01", "pre_post_tasmax_20130801.png"),
    ("tasmin", "2013-08-01", "pre_post_tasmin_20130801.png"),
    ("rsds", "2013-08-01", "pre_post_rsds_20130801.png"),
    ("wind", "2013-08-01", "pre_post_wind_20130801.png"),
    ("huss", "2013-08-01", "pre_post_huss_20130801.png"),
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--gallery-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "pre_post_test8",
        help="Folder containing PNGs and index.html",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output PDF path (default: gallery-dir/Pre_Post_Test8_Gallery_Bhuwan.pdf)",
    )
    args = p.parse_args()
    gallery = args.gallery_dir.resolve()
    out = args.out or (gallery / "Pre_Post_Test8_Gallery_Bhuwan.pdf")
    out = out.resolve()

    if not gallery.is_dir():
        raise SystemExit(f"Gallery folder not found: {gallery}")

    cover_lines = [
        "Pre–test8 vs post–test8 (stochastic + Schaake)",
        "",
        "Rows: pre–test8 bilinear | pre–test8 NN | NN − bilinear; post–test8 (same); GridMET target.",
        "MPI-ESM1-2-HR, OTBC + physics-corrected, Iowa domain (216×192).",
        "Bilinear vs NN regrid paths; identical test8 logic and TEST8_SEED=42.",
        "",
        "Note: pr uses conservative regridding in both paths (not bilinear vs NN).",
        "",
        f"Snapshot dates: 2011-07-15, 2006-01-20, 2013-08-01  |  {len(FIGURES)} figures follow.",
    ]

    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.08, 0.92, "Bilinear vs nearest-neighbor — qualitative gallery", fontsize=16, weight="bold")
        y = 0.82
        for line in cover_lines:
            fig.text(0.08, y, line, fontsize=11, family="sans-serif", verticalalignment="top")
            y -= 0.045
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        for var, date_str, fname in FIGURES:
            path = gallery / fname
            if not path.is_file():
                raise SystemExit(f"Missing figure: {path}")
            img = plt.imread(path)
            h, w = img.shape[0], img.shape[1]
            fig_w = 11.0
            fig_h = max(4.0, fig_w * (h / w) + 0.6)
            fig, ax = plt.subplots(figsize=(fig_w, fig_h))
            ax.imshow(img)
            ax.set_title(f"{var} — {date_str}", fontsize=13, pad=10)
            ax.axis("off")
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight", dpi=120)
            plt.close(fig)

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
