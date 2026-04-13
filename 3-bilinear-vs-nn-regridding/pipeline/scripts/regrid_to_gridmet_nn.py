"""
DEPRECATED — use ``pipeline/scripts/regrid/regrid_to_gridmet_nn.py`` (env-based paths).

This wrapper forwards to the canonical script under the repo-root ``pipeline/`` folder.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "pipeline" / "scripts" / "regrid" / "regrid_to_gridmet_nn.py"


def main() -> None:
    print(
        "regrid_to_gridmet_nn.py moved to:\n  ",
        _SCRIPT,
        "\nForwarding...\n",
        sep="",
    )
    raise SystemExit(subprocess.call([sys.executable, str(_SCRIPT), *sys.argv[1:]]))


if __name__ == "__main__":
    main()
