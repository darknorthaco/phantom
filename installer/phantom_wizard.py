#!/usr/bin/env python3
"""
Phantom GUI Installation Wizard — Entry Point

Launch this script to start the graphical installation wizard:

    python phantom_wizard.py

The CLI installer remains fully functional:

    python phantom_installer.py

This wizard operates as an installation-phase interface module only.
It DOES NOT modify Phantom's constitutional architecture.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the installer package root is on sys.path.
_here = Path(__file__).parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

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

if __name__ == "__main__":
    main()
