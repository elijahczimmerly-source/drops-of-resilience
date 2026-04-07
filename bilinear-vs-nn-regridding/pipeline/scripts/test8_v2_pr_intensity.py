"""
Shim: test8_v2_pr_intensity.py now lives under the dedicated experiment folder.
This file forwards to the canonical script so old commands still work.
"""

import subprocess
import sys

_TARGET = r"C:\drops-of-resilience\test8-v2-pr-intensity\scripts\test8_v2_pr_intensity.py"

if __name__ == "__main__":
    sys.stderr.write(
        "NOTE: test8_v2_pr_intensity.py has moved to:\n"
        f"  {_TARGET}\n"
        "Forwarding this run to the new location.\n\n"
    )
    raise SystemExit(subprocess.call([sys.executable, "-u", _TARGET, *sys.argv[1:]]))
