"""
Launcher for pipeline spatial downscaling with multiplicative noise debias enabled (plan file name).

Runs `pipeline/scripts/test8_v4.py` (debias on by default in the impl). Set `DOR_PIPELINE_ROOT` if
`data/` is not next to `pipeline/` (e.g. point at `4-test8-v2-pr-intensity`).
"""
import os
import subprocess
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_REPO, "pipeline", "scripts")
_MAIN = os.path.join(_SCRIPTS, "test8_v4.py")


def main() -> int:
    env = os.environ.copy()
    env.setdefault("DOR_MULTIPLICATIVE_NOISE_DEBIAS", "1")
    env.setdefault("DOR_PIPELINE_ROOT", os.path.join(_REPO, "4-test8-v2-pr-intensity"))
    return subprocess.call(
        [sys.executable, _MAIN] + sys.argv[1:], env=env, cwd=_SCRIPTS
    )


if __name__ == "__main__":
    raise SystemExit(main())
