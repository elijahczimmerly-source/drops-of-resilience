"""Copy run_manifest.json + INVOCATION.json from each distinct pipeline output into benchmark_bundle/."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PC_ROOT.parent
sys.path.insert(0, str(PC_ROOT))

import config as cfg
import grid_suites as gs


def main() -> int:
    out = cfg.OUTPUT_DIR / "benchmark_bundle"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid, root in cfg.DOR_DEFAULT_OUTPUTS.items():
        inv = root / "INVOCATION.json"
        man = root / "run_manifest.json"
        bundle = out / pid
        bundle.mkdir(parents=True, exist_ok=True)
        for src, name in ((inv, "INVOCATION.json"), (man, "run_manifest.json")):
            if src.is_file():
                shutil.copy2(src, bundle / name)
        rows.append(
            {
                "pipeline_id": pid,
                "dor_output_dir": str(root.resolve()),
                "has_invocation": inv.is_file(),
                "has_run_manifest": man.is_file(),
            }
        )
    summary = {
        "bundle_dir": str(out.resolve()),
        "pipelines": rows,
    }
    (out / "bundle_index.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    for suite in sorted(gs.CANONICAL_SUITES):
        if suite == gs.SUITE_DOR_NATIVE:
            continue
        dest_parent = gs.suite_output_dir(suite)
        dest_parent.mkdir(parents=True, exist_ok=True)
        dest = dest_parent / "benchmark_bundle"
        if dest.is_dir():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print(f"Mirrored benchmark_bundle -> {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
