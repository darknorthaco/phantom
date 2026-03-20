#!/usr/bin/env python3
"""
Phantom GUI Installation Wizard — Entry Point

Launch this script to start the graphical installation wizard:

    python phantom_wizard.py

Resume after a reboot:

    python phantom_wizard.py --resume

The CLI installer remains fully functional:

    python phantom_installer.py

This wizard operates as an installation-phase interface module only.
It DOES NOT modify Phantom's constitutional architecture.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the installer package root is on sys.path.
_here = Path(__file__).parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from legacy_installer_gate import exit_if_legacy_installer_disabled

try:
    import tkinter  # noqa: F401 — verify Tkinter is available before importing wizard
except ModuleNotFoundError:
    print(
        "ERROR: Tkinter is not available.\n"
        "  • On Windows/macOS this is bundled with Python.\n"
        "  • On Debian/Ubuntu: sudo apt-get install python3-tk\n\n"
        "Alternatively, use the CLI installer:\n"
        "  python phantom_installer.py",
        file=sys.stderr,
    )
    sys.exit(1)

from gui.wizard import main


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phantom Distributed Compute Fabric — Setup Wizard",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume installation after a system reboot.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    exit_if_legacy_installer_disabled()
    args = _parse_args()
    resume_idx = None

    if args.resume:
        # Determine which screen to resume at from persisted state
        try:
            from backend_interface.reboot_manager import RebootManager
            rm = RebootManager(Path.home() / "phantom")
            if rm.has_resume_state():
                resume_idx = rm.get_resume_screen_index()
            else:
                # No saved state — land on the Resume screen (index 4)
                resume_idx = 4
        except Exception:
            resume_idx = 4

    main(resume_idx=resume_idx)
