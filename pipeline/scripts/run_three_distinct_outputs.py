"""
Run test8_v2, test8_v3, and test8_v4 each into its own output folder with a full provenance record.

Writes (per run, under the pipeline OUT_DIR):
  - INVOCATION.json   — command, cwd, env snapshot, timestamps, git commit (if available)
  - run_manifest.json — from _test8_sd_impl.write_run_manifest() after the run completes

Environment (override as needed):
  DOR_PIPELINE_ROOT       — default: parent of pipeline/scripts/ (this repo's pipeline/ folder)
  DOR_TEST8_PR_DATA_DIR   — folder with cmip6_inputs_*.dat (default: local WRC cache mv_otbc)
  DOR_TEST8_GRIDMET_TARGETS_DAT, DOR_TEST8_GEO_MASK_NPY — defaults alongside Regridded_Iowa

Defaults match product-comparison expectations:
  - v2  → output/test8_v2/parity/           (no PR intensity ratio)
  - v3  → output/test8_v3/experiment_blend0p65/  (PR_USE_INTENSITY_RATIO=1, blend 0.65, WDF 1.15)
  - v4  → output/test8_v4/experiment_blend0p65/  (PR_USE_INTENSITY_RATIO=1, blend 0.65, WDF 1.65)

Archived blend+ratio-smooth attempt (not in this batch): ``test8_attempt2_pr_splotch_blend0p62_dor_ratio_smooth_sigma1p0.py``.

Use TEST8_MAIN_PERIOD_ONLY=0 for SSP585 future NPZs (slow; required for full climate-signal S4).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_PIPELINE_ROOT = _SCRIPTS.parent
_REPO_ROOT = _PIPELINE_ROOT.parent

# Local mirror (same defaults as 6-product-comparison/config.py)
_DEFAULT_CACHE = Path(os.environ.get("DOR_LOCAL_WRC_CACHE", r"D:\drops-resilience-data\WRC_DOR_cache"))
_REGRIDDED = _DEFAULT_CACHE / "Spatial_Downscaling" / "test8_v2" / "Regridded_Iowa"
_MV_OTBC = _REGRIDDED / "MPI" / "mv_otbc"


def _git_sha() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except OSError:
        pass
    return None


def _invocation_path(out_dir: Path) -> Path:
    return out_dir / "INVOCATION.json"


def _write_invocation_stub(
    *,
    out_dir: Path,
    pipeline_id: str,
    script_name: str,
    extra_env: dict[str, str],
    common_env: dict[str, str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "dor.pipeline.invocation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_id": pipeline_id,
        "entry_script": script_name,
        "repo_root": str(_REPO_ROOT),
        "pipeline_root": str(_PIPELINE_ROOT),
        "git_head": _git_sha(),
        "python": sys.executable,
        "environment": {**common_env, **extra_env},
        "purpose": (
            "Distinct stochastic downscale for benchmark/climate-signal; do not mix with other "
            "pipeline_ids. After completion, run_manifest.json is written by _test8_sd_impl."
        ),
    }
    _invocation_path(out_dir).write_text(json.dumps(record, indent=2), encoding="utf-8")


def _common_data_env() -> dict[str, str]:
    data_dir = os.environ.get("DOR_TEST8_PR_DATA_DIR", str(_MV_OTBC))
    gmt = os.environ.get(
        "DOR_TEST8_GRIDMET_TARGETS_DAT",
        str(_REGRIDDED / "gridmet_targets_19810101-20141231.dat"),
    )
    gmask = os.environ.get("DOR_TEST8_GEO_MASK_NPY", str(_REGRIDDED / "geo_mask.npy"))
    return {
        "DOR_PIPELINE_ROOT": str(_PIPELINE_ROOT),
        "DOR_TEST8_PR_DATA_DIR": data_dir,
        "DOR_TEST8_GRIDMET_TARGETS_DAT": gmt,
        "DOR_TEST8_GEO_MASK_NPY": gmask,
        "TEST8_SEED": os.environ.get("TEST8_SEED", "42"),
        "TEST8_MAIN_PERIOD_ONLY": os.environ.get("TEST8_MAIN_PERIOD_ONLY", "0"),
    }


def run_v2(common: dict[str, str]) -> int:
    pipeline_id = "test8_v2"
    out_dir = _PIPELINE_ROOT / "output" / pipeline_id / "parity"
    extra = {
        "DOR_PIPELINE_ID": pipeline_id,
        "PR_USE_INTENSITY_RATIO": "0",
        "DOR_MULTIPLICATIVE_NOISE_DEBIAS": os.environ.get("DOR_MULTIPLICATIVE_NOISE_DEBIAS", "0"),
        "DOR_PR_CORR_LENGTH": os.environ.get("DOR_PR_CORR_LENGTH", "35"),
    }
    _write_invocation_stub(
        out_dir=out_dir,
        pipeline_id=pipeline_id,
        script_name="test8_v2.py",
        extra_env=extra,
        common_env=common,
    )
    env = os.environ.copy()
    env.update(common)
    env.update(extra)
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / "test8_v2.py")],
        cwd=str(_SCRIPTS),
        env=env,
    ).returncode


def run_v3(common: dict[str, str]) -> int:
    pipeline_id = "test8_v3"
    out_dir = _PIPELINE_ROOT / "output" / pipeline_id / "experiment_blend0p65"
    extra = {
        "DOR_PIPELINE_ID": pipeline_id,
        "PR_USE_INTENSITY_RATIO": "1",
        "PR_INTENSITY_BLEND": os.environ.get("PR_INTENSITY_BLEND", "0.65"),
        "PR_INTENSITY_OUT_TAG": os.environ.get("PR_INTENSITY_OUT_TAG", "blend0p65"),
    }
    _write_invocation_stub(
        out_dir=out_dir,
        pipeline_id=pipeline_id,
        script_name="test8_v3.py",
        extra_env=extra,
        common_env=common,
    )
    env = os.environ.copy()
    env.update(common)
    env.update(extra)
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / "test8_v3.py")],
        cwd=str(_SCRIPTS),
        env=env,
    ).returncode


def run_v4(common: dict[str, str]) -> int:
    pipeline_id = "test8_v4"
    out_dir = _PIPELINE_ROOT / "output" / pipeline_id / "experiment_blend0p65"
    extra = {
        "DOR_PIPELINE_ID": pipeline_id,
        "PR_USE_INTENSITY_RATIO": "1",
        "PR_INTENSITY_BLEND": os.environ.get("PR_INTENSITY_BLEND", "0.65"),
        "PR_INTENSITY_OUT_TAG": os.environ.get("PR_INTENSITY_OUT_TAG", "blend0p65"),
    }
    _write_invocation_stub(
        out_dir=out_dir,
        pipeline_id=pipeline_id,
        script_name="test8_v4.py",
        extra_env=extra,
        common_env=common,
    )
    env = os.environ.copy()
    env.update(common)
    env.update(extra)
    return subprocess.run(
        [sys.executable, str(_SCRIPTS / "test8_v4.py")],
        cwd=str(_SCRIPTS),
        env=env,
    ).returncode


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Run distinct test8_v2/v3/v4 downscales with INVOCATION.json stubs")
    p.add_argument("--only", choices=("v2", "v3", "v4", "all"), default="all")
    args = p.parse_args()

    if not _MV_OTBC.is_dir():
        print(f"Missing data dir: {_MV_OTBC}", file=sys.stderr)
        print("Set DOR_TEST8_PR_DATA_DIR to a folder with cmip6_inputs_*.dat", file=sys.stderr)
        return 1

    common = _common_data_env()
    steps = []
    if args.only in ("all", "v2"):
        steps.append(("v2", run_v2))
    if args.only in ("all", "v3"):
        steps.append(("v3", run_v3))
    if args.only in ("all", "v4"):
        steps.append(("v4", run_v4))

    code = 0
    for name, fn in steps:
        print(f"\n========== Running {name} ==========\n", flush=True)
        rc = fn(common)
        if rc != 0:
            print(f"FAILED {name} exit {rc}", file=sys.stderr)
            code = rc
            break
    return code


if __name__ == "__main__":
    raise SystemExit(main())
