"""
Gate for deprecated Python/package installers.

Canonical install path: the Phantom Tauri desktop application (see INSTALL.md).
"""

from __future__ import annotations

import os
import sys

_LEGACY_MESSAGE = """\
================================================================================
DEPRECATED INSTALLER
================================================================================
Phantom's canonical installation path is the Phantom desktop application (Tauri).

  • From source:  cd phantom_app && npm install && npm run tauri build
  • User data:    ~/.phantom  (Linux/macOS)  or  %USERPROFILE%\\.phantom  (Windows)

Documentation: INSTALL.md and DEPLOYMENT_CEREMONY.md at the repository root.

To run this legacy Python installer anyway (CI, air-gap tooling):
  export PHANTOM_ALLOW_LEGACY_INSTALLER=1    # Unix
  set PHANTOM_ALLOW_LEGACY_INSTALLER=1       # Windows CMD
================================================================================
"""


def exit_if_legacy_installer_disabled() -> None:
    """Call at the start of legacy installer ``main()``."""
    if os.environ.get("PHANTOM_ALLOW_LEGACY_INSTALLER") == "1":
        return
    print(_LEGACY_MESSAGE, file=sys.stderr)
    sys.exit(2)
