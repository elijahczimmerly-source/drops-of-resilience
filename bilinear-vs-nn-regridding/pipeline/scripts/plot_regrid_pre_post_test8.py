"""
Qualitative maps: regridded inputs (pre–test8) vs stochastic outputs (post–test8),
bilinear vs NN, for the same calendar days.

Requires:
  - pipeline/data/{bilinear,nearest_neighbor}/cmip6_inputs_19810101-20141231.dat
  - pipeline/data/{bilinear,nearest_neighbor}/gridmet_targets_19810101-20141231.dat
  - pipeline/output/{bilinear,nearest_neighbor}/Stochastic_{Bilinear|NN}_{var}.npz
    (written after test8_* completes; post–test8 row is skipped if npz missing)

For **pr** only (three-way regrid, not the identical conservative-in-both pipelines):
  - pipeline/output/pr_3way/regridded_hist_pr_{cons,bil,nn}.npy
  - pipeline/output/pr_3way/Stochastic_pr_{cons,bil,nn}.npz
  (from pr_3way_regrid_compare.py)

Memmap layout matches test8: (n_days, 6, H, W) with channels
  pr, tasmax, tasmin, rsds, wind, huss.

Usage:
  python plot_regrid_pre_post_test8.py --dates 2011-07-15,2006-01-20
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

VARS_INTERNAL = ["pr", "tasmax", "tasmin", "rsds", "wind", "huss"]
HIST_START = pd.Timestamp("1981-01-01")
HIST_END = pd.Timestamp("2014-12-31")
N_DAYS = int((HIST_END - HIST_START).days) + 1
CMIP_START = pd.Timestamp("1850-01-01")

# pr 3-way file tags (pr_3way_regrid_compare.py)
PR3_REGRID_TAGS = [("conservative", "cons"), ("bilinear", "bil"), ("nearest", "nn")]


def _repo_pipeline() -> Path:
    return Path(__file__).resolve().parents[1]


def day_index(date: pd.Timestamp) -> int:
    i = int((date.normalize() - HIST_START).days)
    if i < 0 or i >= N_DAYS:
        raise ValueError(f"{date.date()} outside 1981-01-01 .. 2014-12-31")
    return i


def cmip_day_index(date: pd.Timestamp) -> int:
    """Index into regridded_hist_pr_*.npy (time starts 1850-01-01)."""
    return int((date.normalize() - CMIP_START).days)


def pooled_vmin_vmax(*arrays: np.ndarray, mask: np.ndarray, lo: float = 2.0, hi: float = 98.0):
    parts = []
    for a in arrays:
        v = a[mask]
        v = v[np.isfinite(v)]
        if v.size:
            parts.append(v.ravel())
    if not parts:
        return 0.0, 1.0
    stacked = np.concatenate(parts)
    return float(np.percentile(stacked, lo)), float(np.percentile(stacked, hi))


def plot_one(
    var: str,
    date: pd.Timestamp,
    mask: np.ndarray,
    bi_dat: Path,
    nn_dat: Path,
    bi_out: Path,
    nn_out: Path,
    out_png: Path,
    dpi: int,
) -> bool:
    vi = VARS_INTERNAL.index(var)
    di = day_index(date)
    H, W = mask.shape

    bi_in = np.memmap(bi_dat, dtype=np.float32, mode="r", shape=(N_DAYS, 6, H, W))
    nn_in = np.memmap(nn_dat, dtype=np.float32, mode="r", shape=(N_DAYS, 6, H, W))
    tar = np.memmap(bi_dat.parent / "gridmet_targets_19810101-20141231.dat", dtype=np.float32, mode="r", shape=(N_DAYS, 6, H, W))

    pre_bi = np.asarray(bi_in[di, vi], dtype=np.float64)
    pre_nn = np.asarray(nn_in[di, vi], dtype=np.float64)
    obs = np.asarray(tar[di, vi], dtype=np.float64)

    bi_npz = bi_out / f"Stochastic_Bilinear_{var}.npz"
    nn_npz = nn_out / f"Stochastic_NN_{var}.npz"
    has_post = bi_npz.is_file() and nn_npz.is_file()

    if has_post:
        with np.load(bi_npz) as z:
            post_bi = np.asarray(z["data"][di], dtype=np.float64)
        with np.load(nn_npz) as z:
            post_nn = np.asarray(z["data"][di], dtype=np.float64)
    else:
        post_bi = post_nn = None

    # Temperature: align obs to K if needed (same heuristic as plot_regrid_qualitative)
    if var in ("tasmax", "tasmin"):
        if np.nanmedian(obs) < 100 and np.nanmedian(pre_bi) > 200:
            obs = obs + 273.15

    diff_pre = pre_nn - pre_bi

    if has_post:
        diff_post = post_nn - post_bi
        nrows = 3
    else:
        diff_post = None
        nrows = 2

    fig, axes = plt.subplots(nrows, 3, figsize=(12, 3.6 * nrows), constrained_layout=True)
    fig.suptitle(f"{var} — {date.date()}  (pre = regridded OTBC; post = after test8 + Schaake)", fontsize=12)

    def _show_row(row_ax, left, mid, right, t0, t1, t2, *, diff_idx: int | None, state_label=""):
        vmin_m = pooled_vmin_vmax(left, mid, obs, mask=mask)
        fields = (left, mid, right)
        titles = (t0, t1, t2)
        for col, (ax, fld, title) in enumerate(zip(row_ax, fields, titles)):
            if diff_idx is not None and col == diff_idx:
                dmin, dmax = pooled_vmin_vmax(fld, mask=mask, lo=5, hi=95)
                lim = max(abs(dmin), abs(dmax), 1e-9)
                im = ax.imshow(np.where(mask, fld, np.nan), origin="upper", cmap="coolwarm", vmin=-lim, vmax=lim)
            else:
                im = ax.imshow(np.where(mask, fld, np.nan), origin="upper", cmap="viridis", vmin=vmin_m[0], vmax=vmin_m[1])
            ax.set_title(f"{state_label}{title}")
            ax.set_xticks([])
            ax.set_yticks([])
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    _show_row(
        axes[0],
        pre_bi,
        pre_nn,
        diff_pre,
        "Bilinear",
        "NN",
        "NN − bilinear",
        diff_idx=2,
        state_label="Pre–test8: ",
    )

    if has_post:
        _show_row(
            axes[1],
            post_bi,
            post_nn,
            diff_post,
            "Bilinear",
            "NN",
            "NN − bilinear",
            diff_idx=2,
            state_label="Post–test8: ",
        )
        obs_row = 2
    else:
        obs_row = 1

    vmin_o, vmax_o = pooled_vmin_vmax(obs, pre_bi, pre_nn, mask=mask)
    im = axes[obs_row, 0].imshow(np.where(mask, obs, np.nan), origin="upper", cmap="viridis", vmin=vmin_o, vmax=vmax_o)
    axes[obs_row, 0].set_title("GridMET (target)")
    axes[obs_row, 0].set_xticks([])
    axes[obs_row, 0].set_yticks([])
    plt.colorbar(im, ax=axes[obs_row, 0], fraction=0.046, pad=0.02)
    axes[obs_row, 1].axis("off")
    axes[obs_row, 2].axis("off")
    if not has_post:
        axes[obs_row, 1].text(
            0.05,
            0.5,
            "Run test8_bilinear.py and test8_nn.py to generate\nStochastic_*.npz for the post–test8 row.",
            fontsize=10,
            va="center",
            transform=axes[obs_row, 1].transAxes,
        )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    return has_post


def plot_one_pr_3way(
    date: pd.Timestamp,
    mask: np.ndarray,
    pipeline_root: Path,
    targets_dat: Path,
    pr3_dir: Path,
    out_png: Path,
    dpi: int,
) -> bool:
    """
    pr only: pre/post maps for conservative, bilinear, and NN regrids (pr_3way outputs).
    Layout: 3×3 — row0 pre, row1 post, row2 GridMET + blanks.
    """
    H, W = mask.shape
    di = day_index(date)
    ci = cmip_day_index(date)

    tar = np.memmap(targets_dat, dtype=np.float32, mode="r", shape=(N_DAYS, 6, H, W))
    vi = VARS_INTERNAL.index("pr")
    obs = np.asarray(tar[di, vi], dtype=np.float64)

    pre_fields: list[np.ndarray] = []
    for _label, tag in PR3_REGRID_TAGS:
        p = pr3_dir / f"regridded_hist_pr_{tag}.npy"
        if not p.is_file():
            raise FileNotFoundError(f"Missing pr regrid {p} (run pr_3way_regrid_compare.py)")
        mm = np.load(p, mmap_mode="r")
        if ci >= mm.shape[0]:
            raise ValueError(f"cmip index {ci} out of range for {p}")
        pre_fields.append(np.asarray(mm[ci], dtype=np.float64))

    post_npz = [pr3_dir / f"Stochastic_pr_{tag}.npz" for _l, tag in PR3_REGRID_TAGS]
    has_post = all(f.is_file() for f in post_npz)
    post_fields: list[np.ndarray] | list[None]
    if has_post:
        post_fields = []
        for f in post_npz:
            with np.load(f) as z:
                post_fields.append(np.asarray(z["data"][di], dtype=np.float64))
    else:
        post_fields = [None, None, None]

    titles = ("Conservative", "Bilinear", "Nearest (NN)")
    all_for_scale = pre_fields + [obs]
    if has_post:
        all_for_scale = all_for_scale + [p for p in post_fields if p is not None]
    vmin_m, vmax_m = pooled_vmin_vmax(*all_for_scale, mask=mask)

    nrows = 3 if has_post else 2
    fig, axes = plt.subplots(nrows, 3, figsize=(12, 3.6 * nrows), constrained_layout=True)
    fig.suptitle(
        f"pr — {date.date()}  (three-way regrid: conservative / bilinear / NN; post = test8 + Schaake)",
        fontsize=12,
    )

    def _row(row_ax, fields: list[np.ndarray], state_label: str) -> None:
        for ax, fld, t in zip(row_ax, fields, titles):
            im = ax.imshow(np.where(mask, fld, np.nan), origin="upper", cmap="viridis", vmin=vmin_m, vmax=vmax_m)
            ax.set_title(f"{state_label}{t}")
            ax.set_xticks([])
            ax.set_yticks([])
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    _row(axes[0], pre_fields, "Pre–test8: ")

    if has_post:
        assert all(p is not None for p in post_fields)
        _row(axes[1], post_fields, "Post–test8: ")
        obs_row = 2
    else:
        obs_row = 1

    im = axes[obs_row, 0].imshow(np.where(mask, obs, np.nan), origin="upper", cmap="viridis", vmin=vmin_m, vmax=vmax_m)
    axes[obs_row, 0].set_title("GridMET (target)")
    axes[obs_row, 0].set_xticks([])
    axes[obs_row, 0].set_yticks([])
    plt.colorbar(im, ax=axes[obs_row, 0], fraction=0.046, pad=0.02)
    axes[obs_row, 1].axis("off")
    axes[obs_row, 2].axis("off")
    if not has_post:
        axes[obs_row, 1].text(
            0.05,
            0.5,
            "Run pipeline/scripts/pr_3way_regrid_compare.py to generate\n"
            "Stochastic_pr_cons.npz, Stochastic_pr_bil.npz, Stochastic_pr_nn.npz.",
            fontsize=10,
            va="center",
            transform=axes[obs_row, 1].transAxes,
        )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    return has_post


def write_pre_post_index(plot_dir: Path) -> None:
    """index.html from all pre_post_*.png (date order, then VARS_INTERNAL order)."""
    pat = re.compile(r"^pre_post_(.+)_(\d{8})$")

    def sort_key(p: Path) -> tuple[str, int]:
        m = pat.match(p.stem)
        if not m:
            return ("99999999", 99)
        var, ymd = m.group(1), m.group(2)
        vi = VARS_INTERNAL.index(var) if var in VARS_INTERNAL else 99
        return (ymd, vi)

    pngs = sorted(plot_dir.glob("pre_post_*.png"), key=sort_key)
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Pre vs post test8</title>",
        "<style>body{font-family:sans-serif;max-width:1400px;margin:1rem auto;} img{max-width:100%;border:1px solid #ccc;margin:0.5rem 0;}</style></head><body>",
        "<h1>Regrid (pre–test8) vs stochastic downscaling (post–test8)</h1>",
        "<p class=\"note\" style=\"font-size:0.9em;color:#444\">pr: conservative / bilinear / NN regrid (pr_3way). Other variables: bilinear vs NN.</p>",
    ]
    for p in pngs:
        m = pat.match(p.stem)
        if not m:
            continue
        var, ymd = m.group(1), m.group(2)
        d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        lines.append(f"<h2>{var} {d}</h2><img src='{p.name}'/>")
    lines.append("</body></html>")
    idx = plot_dir / "index.html"
    idx.write_text("\n".join(lines), encoding="utf-8")
    print(f"Index: {idx}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dates", default="2011-07-15,2006-01-20,2013-08-01")
    p.add_argument(
        "--vars",
        default="pr,tasmax,tasmin,rsds,wind,huss",
        help="Comma-separated. pr uses pr_3way outputs (conservative/bilinear/NN); other vars use bilinear vs NN .dat pipelines.",
    )
    p.add_argument("--dpi", type=int, default=120)
    p.add_argument("--pipeline-root", type=Path, default=None)
    args = p.parse_args()

    root = args.pipeline_root or _repo_pipeline()
    data_bi = root / "data" / "bilinear"
    data_nn = root / "data" / "nearest_neighbor"
    out_bi = root / "output" / "bilinear"
    out_nn = root / "output" / "nearest_neighbor"
    plot_dir = root.parent / "qualitative_plots" / "pre_post_test8"
    pr3_dir = root / "output" / "pr_3way"
    mask_path = data_bi / "geo_mask.npy"
    targets_dat = data_bi / "gridmet_targets_19810101-20141231.dat"

    if not mask_path.is_file():
        print(f"Missing {mask_path}", file=sys.stderr)
        sys.exit(1)
    mask = np.load(mask_path).astype(bool)

    bi_dat = data_bi / "cmip6_inputs_19810101-20141231.dat"
    nn_dat = data_nn / "cmip6_inputs_19810101-20141231.dat"
    vars_list = [v.strip() for v in args.vars.split(",") if v.strip()]
    need_bi_nn_dat = any(v != "pr" for v in vars_list)
    if need_bi_nn_dat:
        for fpath in (bi_dat, nn_dat):
            if not fpath.is_file():
                print(f"Missing {fpath}", file=sys.stderr)
                sys.exit(1)
    if not targets_dat.is_file():
        print(f"Missing {targets_dat}", file=sys.stderr)
        sys.exit(1)

    for ds in args.dates.split(","):
        ds = ds.strip()
        if not ds:
            continue
        date = pd.Timestamp(ds)
        for var in vars_list:
            if var not in VARS_INTERNAL:
                print(f"Skip unknown var {var}", file=sys.stderr)
                continue
            out_png = plot_dir / f"pre_post_{var}_{date.strftime('%Y%m%d')}.png"
            if var == "pr":
                try:
                    has_post = plot_one_pr_3way(
                        date, mask, root, targets_dat, pr3_dir, out_png, args.dpi
                    )
                except FileNotFoundError as e:
                    print(f"Skip pr {date.date()}: {e}", file=sys.stderr)
                    continue
            else:
                has_post = plot_one(
                    var, date, mask, bi_dat, nn_dat, out_bi, out_nn, out_png, args.dpi
                )
            print(f"Wrote {out_png}  (post row: {'yes' if has_post else 'no — run test8'})")

    write_pre_post_index(plot_dir)


if __name__ == "__main__":
    main()
