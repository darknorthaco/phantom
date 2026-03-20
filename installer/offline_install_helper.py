#!/usr/bin/env python3
"""
Offline pip install helper for Phantom Phase 3.

Invoked by the Tauri backend (subprocess) or manually for diagnostics.
Uses ``--no-index`` and ``--find-links`` against the bundle wheelhouse.

No FastAPI; no outbound network when pip wheels are self-contained.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_INSTALLER = Path(__file__).resolve().parent
if str(_INSTALLER) not in sys.path:
    sys.path.insert(0, str(_INSTALLER))

from offline_bundle_lib import build_install_pip_argv  # noqa: E402


def install_deps(pip_exe: str, bundle_root: Path) -> int:
    argv = build_install_pip_argv(pip_exe, bundle_root)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "pip install failed\n")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Phantom offline pip helper")
    ap.add_argument("--bundle", type=Path, required=True, help="offline_bundle root")
    ap.add_argument(
        "--pip",
        required=True,
        help="Path to pip (usually venv Scripts/pip.exe or venv/bin/pip)",
    )
    ap.add_argument(
        "command",
        choices=("install-deps",),
        help="install-deps: pip install --no-index from wheelhouse",
    )
    args = ap.parse_args()
    if args.command == "install-deps":
        return install_deps(args.pip, args.bundle)
    return 2


if __name__ == "__main__":
    sys.exit(main())
