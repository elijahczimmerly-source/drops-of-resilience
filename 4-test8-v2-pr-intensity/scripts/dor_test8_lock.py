"""
Single-instance lock for test8_*.py — must be acquired only from __main__ (not at import).

Windows spawn workers re-import the main script; a module-level lock would see the parent PID
as alive and call sys.exit(1) in every worker.
"""

from __future__ import annotations

import atexit
import os
import signal
import sys
import time


def _win_pid_is_running(pid: int) -> bool:
    import ctypes

    k = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    k.CloseHandle(h)
    return True


def acquire_run_lock(lock_path: str, label: str) -> None:
    """Create lock file or exit if another live process holds it. Registers release on exit/signals."""

    def try_create() -> bool:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = f"{os.getpid()}\n{int(time.time())}\n".encode("ascii")
                os.write(fd, payload)
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            return False

    def release_lock() -> None:
        try:
            os.remove(lock_path)
        except OSError:
            pass

    if try_create():
        atexit.register(release_lock)
    else:
        old_pid = -1
        try:
            with open(lock_path, "r", encoding="ascii", errors="ignore") as f:
                first = f.readline().strip()
                if first:
                    old_pid = int(first)
        except (OSError, ValueError):
            old_pid = -1
        if old_pid > 0 and _win_pid_is_running(old_pid):
            print(
                f"Another {label} is already running (PID {old_pid}). "
                f"If that process is gone, delete {lock_path} and retry.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            os.remove(lock_path)
        except OSError:
            pass
        if not try_create():
            print(f"Could not acquire run lock: {lock_path}", file=sys.stderr)
            sys.exit(1)
        atexit.register(release_lock)

    def _on_signal(signum: int, _frame) -> None:
        release_lock()
        sys.exit(128 + signum if signum > 0 else 1)

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass
