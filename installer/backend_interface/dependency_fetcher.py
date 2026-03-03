#!/usr/bin/env python3
"""
Dependency Fetcher
Stages pip-installable dependencies into a local cache directory before
creating the virtual environment.  Supports offline re-runs and
bandwidth-efficient retries.

This module NEVER executes privileged operations.  Dependencies that
require elevation (e.g. WSL kernel, CUDA drivers) are flagged but not
fetched — they are returned as user-facing instruction strings.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class DepSpec:
    """A single parsed dependency specification."""

    __slots__ = ("name", "version_spec", "raw_line")

    def __init__(self, name: str, version_spec: str, raw_line: str):
        self.name = name
        self.version_spec = version_spec
        self.raw_line = raw_line

    def __repr__(self) -> str:
        return f"DepSpec({self.name!r}, {self.version_spec!r})"


class PrivilegedDep:
    """A dependency that requires privileged installation (conceptual only)."""

    __slots__ = ("name", "reason", "user_action", "required")

    def __init__(self, name: str, reason: str, user_action: str, required: bool = False):
        self.name = name
        self.reason = reason
        self.user_action = user_action
        self.required = required

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "reason": self.reason,
            "user_action": self.user_action,
            "required": self.required,
        }


# Well-known privileged dependencies — never auto-installed.
PRIVILEGED_DEPS: List[PrivilegedDep] = [
    PrivilegedDep(
        name="WSL2 Kernel Update",
        reason="Required for Linux worker containers inside WSL",
        user_action=(
            "Download and install manually from:\n"
            "  https://aka.ms/wsl2kernel"
        ),
        required=False,
    ),
    PrivilegedDep(
        name="NVIDIA CUDA Toolkit",
        reason="Required for GPU-accelerated inference via llama.cpp",
        user_action=(
            "Download the appropriate CUDA toolkit from:\n"
            "  https://developer.nvidia.com/cuda-downloads\n"
            "Install with default options."
        ),
        required=False,
    ),
]


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class DependencyFetcher:
    """Stages pip wheels into a local cache for offline venv creation.

    Usage flow (called by Phase P2 of the state machine):
        fetcher = DependencyFetcher(install_dir / "staging")
        deps = fetcher.parse_requirements(requirements_txt_path)
        deps = fetcher.resolve_platform_constraints(deps)
        cached = fetcher.check_cache()
        fetcher.download_wheels(deps, status_cb, progress_cb)
        ok = fetcher.verify_wheels()
        priv = fetcher.detect_privileged_deps()
        assert fetcher.stage_complete()
    """

    def __init__(self, staging_dir: Path):
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.staging_dir / "staging_manifest.json"

    # ------------------------------------------------------------------ #
    # 1. Parse requirements
    # ------------------------------------------------------------------ #

    def parse_requirements(self, req_file: Path) -> List[DepSpec]:
        """Parse a pip requirements.txt into DepSpec objects."""
        specs: List[DepSpec] = []
        if not req_file.exists():
            return specs
        for raw_line in req_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Split on first version specifier character
            for sep in (">=", "==", "<=", "!=", "~=", ">", "<"):
                if sep in line:
                    name = line[: line.index(sep)].strip()
                    ver = line[line.index(sep) :].strip()
                    specs.append(DepSpec(name, ver, line))
                    break
            else:
                # No version specifier
                specs.append(DepSpec(line, "", line))
        return specs

    # ------------------------------------------------------------------ #
    # 2. Platform constraints
    # ------------------------------------------------------------------ #

    def resolve_platform_constraints(self, deps: List[DepSpec]) -> List[DepSpec]:
        """Filter dependencies by current platform.

        Currently passes all through — extend if OS-specific exclusions needed.
        """
        return list(deps)

    # ------------------------------------------------------------------ #
    # 3. Check cache
    # ------------------------------------------------------------------ #

    def check_cache(self) -> List[str]:
        """Return list of already-cached wheel filenames in staging dir."""
        cached = []
        for f in self.staging_dir.iterdir():
            if f.suffix in (".whl", ".tar.gz", ".zip") and f.stat().st_size > 0:
                cached.append(f.name)
        return cached

    # ------------------------------------------------------------------ #
    # 4. Download wheels
    # ------------------------------------------------------------------ #

    def download_wheels(
        self,
        req_file: Path,
        status_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Download wheels for all requirements into staging_dir.

        Uses ``pip download`` under the hood.  This is a non-privileged
        operation that only writes into the staging directory.

        Args:
            req_file:    Path to requirements.txt.
            status_cb:   Called with human-readable status strings.
            progress_cb: Called with (step_current, step_total).

        Returns:
            True if download succeeded.
        """
        if status_cb:
            status_cb("Downloading Python dependencies…")

        python = sys.executable
        cmd = [
            python, "-m", "pip", "download",
            "--dest", str(self.staging_dir),
            "-r", str(req_file),
            "--no-cache-dir",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minute timeout
            )

            if result.returncode != 0:
                if status_cb:
                    status_cb(f"pip download failed: {result.stderr[:500]}")
                return False

            if status_cb:
                status_cb("Dependencies downloaded successfully.")
            return True

        except subprocess.TimeoutExpired:
            if status_cb:
                status_cb("Download timed out after 15 minutes.")
            return False
        except Exception as exc:
            if status_cb:
                status_cb(f"Download error: {exc}")
            return False

    # ------------------------------------------------------------------ #
    # 5. Verify wheels
    # ------------------------------------------------------------------ #

    def verify_wheels(
        self, status_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify integrity of downloaded wheels.

        Returns:
            (all_ok, list_of_bad_files)
        """
        bad: List[str] = []
        for f in self.staging_dir.iterdir():
            if f.suffix == ".whl":
                try:
                    with zipfile.ZipFile(f, "r") as zf:
                        # Attempt to read the zip — corrupt files will raise
                        if zf.testzip() is not None:
                            bad.append(f.name)
                except (zipfile.BadZipFile, Exception):
                    bad.append(f.name)

        ok = len(bad) == 0
        if status_cb:
            if ok:
                status_cb("All downloaded packages verified.")
            else:
                status_cb(f"Corrupt packages: {', '.join(bad)}")
        return ok, bad

    # ------------------------------------------------------------------ #
    # 6. Detect privileged deps
    # ------------------------------------------------------------------ #

    def detect_privileged_deps(self) -> List[PrivilegedDep]:
        """Return list of dependencies that require elevation.

        These are NEVER downloaded or installed automatically — they are
        returned as informational objects for the GUI to display.
        """
        return list(PRIVILEGED_DEPS)

    # ------------------------------------------------------------------ #
    # 7. Stage complete?
    # ------------------------------------------------------------------ #

    def stage_complete(self, req_file: Path) -> bool:
        """Return True if all non-privileged dependencies are staged."""
        specs = self.parse_requirements(req_file)
        cached = {f.lower() for f in self.check_cache()}
        # Heuristic: at least one cached file per spec name
        for spec in specs:
            name_lower = spec.name.lower().replace("-", "_")
            found = any(name_lower in c.lower().replace("-", "_") for c in cached)
            if not found:
                return False
        return True

    # ------------------------------------------------------------------ #
    # Write manifest
    # ------------------------------------------------------------------ #

    def write_manifest(self, req_file: Path) -> Path:
        """Write staging_manifest.json describing what was downloaded."""
        wheels = []
        for f in sorted(self.staging_dir.iterdir()):
            if f.suffix in (".whl", ".tar.gz", ".zip") and f.stat().st_size > 0:
                sha = hashlib.sha256(f.read_bytes()).hexdigest()
                wheels.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "sha256": sha,
                })

        # Hash the requirements file itself
        req_hash = ""
        if req_file.exists():
            req_hash = hashlib.sha256(
                req_file.read_bytes()
            ).hexdigest()

        manifest = {
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "requirements_hash": req_hash,
            "platform": sys.platform,
            "architecture": os.environ.get("PROCESSOR_ARCHITECTURE", "unknown"),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "wheels": wheels,
            "privileged_deps_required": [p.to_dict() for p in PRIVILEGED_DEPS],
        }

        self._manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return self._manifest_path

    # ------------------------------------------------------------------ #
    # Install from cache (offline)
    # ------------------------------------------------------------------ #

    def install_from_cache(
        self,
        pip_executable: Path,
        req_file: Path,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Install into a venv from locally cached wheels (offline).

        Args:
            pip_executable: Path to pip inside the target venv.
            req_file:       Path to requirements.txt.
            status_cb:      Human-readable status callback.
        """
        if status_cb:
            status_cb("Installing from local cache…")

        cmd = [
            str(pip_executable), "install",
            "--no-index",
            f"--find-links={self.staging_dir}",
            "-r", str(req_file),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                if status_cb:
                    status_cb(f"Install from cache failed: {result.stderr[:500]}")
                return False
            if status_cb:
                status_cb("Dependencies installed from cache.")
            return True
        except Exception as exc:
            if status_cb:
                status_cb(f"Error installing from cache: {exc}")
            return False
