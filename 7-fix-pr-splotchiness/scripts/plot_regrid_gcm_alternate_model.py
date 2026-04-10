"""
Find a non-MPI `cmip6_inputs_19810101-20141231.dat` on the WRC_DOR tree (if present) and emit the
same **regrid-gcm** figure style as `pipeline_MPI_memmap_regrid_gcm_stage.png` (GridMET | GCM on the 4 km
memmap grid, mean 2006–2014).

Search roots (under `--wrc-dor-root`):
  Spatial_Downscaling/test8_v2/Regridded_Iowa
  Data/Regridded_Iowa

Files must match byte size of the reference MPI memmap (same H×W×days layout as GridMET targets).

If no alternate memmap exists, exit non-zero with a short message — you would need to build
`cmip6_inputs_*.dat` for another model with `regrid_to_gridmet_*.py` first.

Example:
  python plot_regrid_gcm_alternate_model.py \\
    --wrc-dor-root \\\\abe-cylo\\modelsdev\\Projects\\WRC_DOR \\
    --gridmet-targets ...\\Regridded_Iowa\\gridmet_targets_19810101-20141231.dat \\
    --geo-mask ...\\Regridded_Iowa\\geo_mask.npy \\
    --reference-mpi-cmip6 ...\\MPI\\mv_otbc\\cmip6_inputs_19810101-20141231.dat \\
    --out ..\\figures\\pr-splotch-side-by-side\\pipeline_MPI_memmap_regrid_gcm_GFDL-CM4.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from plot_gridmet_pipeline_side_by_side import cmd_regrid_gcm


def _collect_candidates(wrc: Path, fname: str) -> list[Path]:
    roots = [
        wrc / "Spatial_Downscaling" / "test8_v2" / "Regridded_Iowa",
        wrc / "Data" / "Regridded_Iowa",
        # Legacy flat memmap layout (often 84×96 — size filter drops if wrong grid):
        wrc / "Spatial_Downscaling" / "Data_Regrided_Gridmet",
    ]
    out: list[Path] = []
    for r in roots:
        if not r.is_dir():
            continue
        try:
            for p in r.rglob(fname):
                if p.is_file():
                    out.append(p)
        except OSError:
            continue
    # de-dupe same file resolved
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        k = p.as_posix().lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _is_mpi_path(p: Path) -> bool:
    parts = {x.upper() for x in p.parts}
    return "MPI" in parts or "MPI-ESM1-2-HR" in parts


def _label_from_path(p: Path) -> str:
    """Human-readable model hint for titles."""
    s = p.as_posix()
    for tok in (
        "GFDL-CM4",
        "EC-Earth3",
        "MRI-ESM2-0",
        "CMCC-ESM2",
        "MPI-ESM1-2-HR",
    ):
        if tok in s:
            return tok
    parts = p.parts
    for i, seg in enumerate(parts):
        if seg.lower() == "mv_otbc" and i > 0:
            return parts[i - 1]
    return "GCM"


def _preference_rank(p: Path) -> tuple[int, str]:
    """Prefer GFDL, then EC-Earth3, MRI, CMCC; then alphabetical."""
    u = p.as_posix().upper()
    for i, key in enumerate(
        ("GFDL", "EC-EARTH", "MRI", "CMCC"),
    ):
        if key in u:
            return (i, u)
    return (99, u)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--wrc-dor-root",
        type=Path,
        default=Path(r"\\abe-cylo\modelsdev\Projects\WRC_DOR"),
        help="WRC_DOR UNC root",
    )
    ap.add_argument(
        "--reference-mpi-cmip6",
        type=Path,
        required=True,
        help="MPI cmip6_inputs_19810101-20141231.dat (for expected file size)",
    )
    ap.add_argument("--gridmet-targets", type=Path, required=True)
    ap.add_argument("--geo-mask", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--cmip6-hist",
        type=Path,
        default=None,
        help="Skip discovery: use this memmap directly",
    )
    ap.add_argument("--val-start", default="2006-01-01")
    ap.add_argument("--val-end", default="2014-12-31")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument(
        "--suptitle",
        default="pr — after regrid_to_gridmet (alternate GCM drivers on 4 km grid)",
    )
    ap.add_argument(
        "--also-search",
        type=Path,
        action="append",
        default=[],
        help="Extra directory root(s) to search for cmip6_inputs (e.g. local "
        "Data_Regrided_Gridmet_All_Models). May be repeated.",
    )
    args = ap.parse_args()

    ref = args.reference_mpi_cmip6
    try:
        ref_sz = ref.stat().st_size
    except OSError as e:
        print(f"ERROR: cannot stat reference memmap {ref}: {e}", file=sys.stderr)
        return 1

    if args.cmip6_hist is not None:
        chosen = args.cmip6_hist
        try:
            if chosen.stat().st_size != ref_sz:
                print(
                    f"ERROR: size {chosen.stat().st_size} != reference {ref_sz}",
                    file=sys.stderr,
                )
                return 1
        except OSError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    else:
        fname = "cmip6_inputs_19810101-20141231.dat"
        candidates = _collect_candidates(args.wrc_dor_root, fname)
        for extra in args.also_search:
            candidates.extend(_collect_candidates(extra, fname))
        candidates = _dedupe_paths(candidates)
        ref_key = ref.as_posix().lower()
        alts: list[Path] = []
        for p in candidates:
            if p.as_posix().lower() == ref_key:
                continue
            if _is_mpi_path(p):
                continue
            try:
                if p.stat().st_size != ref_sz:
                    continue
            except OSError:
                continue
            alts.append(p)
        alts.sort(key=_preference_rank)
        if not alts:
            print(
                "No alternate cmip6_inputs memmap found under test8_v2/Regridded_Iowa or "
                "Data/Regridded_Iowa (non-MPI, same size as reference).\n"
                "Build one with regrid_to_gridmet for another model, or pass --cmip6-hist PATH.",
                file=sys.stderr,
            )
            return 2
        chosen = alts[0]
        if len(alts) > 1:
            print(f"Using first alternate ({len(alts)} total): {chosen}", file=sys.stderr)

    label = _label_from_path(chosen)
    title_right = f"{label} (OTBC → 4 km)\\nmean 2006–2014"
    ns = argparse.Namespace(
        gridmet_targets=str(args.gridmet_targets),
        geo_mask=str(args.geo_mask),
        out=args.out,
        val_start=args.val_start,
        val_end=args.val_end,
        dpi=args.dpi,
        title_right=title_right,
        suptitle=args.suptitle,
        cmip6_hist=str(chosen),
        shared_scale=False,
    )
    print(f"cmip6_inputs: {chosen}")
    return cmd_regrid_gcm(ns)


if __name__ == "__main__":
    raise SystemExit(main())
