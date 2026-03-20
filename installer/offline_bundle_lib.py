"""
Offline bundle verification and catalogue loading (Phase 3).

Pure functions suitable for air-gapped validation and unit tests — no network,
no FastAPI. Used by ``offline_bundle.py`` CLI and ``installer/tests/``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

MANIFEST_NAME = "manifest.json"
REQUIRED_DIRS = ("wheelhouse", "models", "config_templates")
OPTIONAL_DIRS = ("binaries",)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_bundle_structure(bundle_root: Path) -> Tuple[bool, List[str]]:
    """
    Check that *bundle_root* has the canonical layout and required artefacts.

    Returns:
        (ok, list of human-readable issues).
    """
    issues: List[str] = []
    root = Path(bundle_root).resolve()
    if not root.is_dir():
        return False, [f"Bundle root is not a directory: {root}"]

    mf = root / MANIFEST_NAME
    if not mf.is_file():
        issues.append(f"Missing {MANIFEST_NAME}")

    for d in REQUIRED_DIRS:
        p = root / d
        if not p.is_dir():
            issues.append(f"Missing required directory: {d}/")

    wh = root / "wheelhouse"
    staging = root / "staging_mode.txt"
    if wh.is_dir() and not staging.is_file():
        wheels = list(wh.glob("*.whl")) + list(wh.glob("*.tar.gz"))
        if not wheels:
            issues.append("wheelhouse/ is empty (no .whl or .tar.gz)")

    cat = root / "models" / "model_catalogue.json"
    if not cat.is_file():
        issues.append("Missing models/model_catalogue.json")

    req = root / "requirements-deploy.txt"
    if not req.is_file():
        issues.append("Missing requirements-deploy.txt (copy from installer/)")

    return len(issues) == 0, issues


def verify_manifest(bundle_root: Path) -> Tuple[bool, List[str]]:
    """
    Verify every file entry in *manifest.json* against SHA-256 on disk.

    The manifest schema is produced by ``offline_bundle.py`` (Phase 3).
    """
    root = Path(bundle_root).resolve()
    mf = root / MANIFEST_NAME
    issues: List[str] = []
    if not mf.is_file():
        return False, [f"Missing {MANIFEST_NAME}"]

    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in manifest: {e}"]

    if data.get("schema_version") != 1:
        issues.append("manifest schema_version must be 1")

    files = data.get("files")
    if not isinstance(files, list) or not files:
        return False, issues + ["manifest.files must be a non-empty list"]

    for entry in files:
        if not isinstance(entry, dict):
            issues.append("manifest.files entry must be an object")
            continue
        rel = entry.get("relative_path") or entry.get("path")
        expected = entry.get("sha256")
        if not rel or not expected:
            issues.append(f"manifest entry missing relative_path or sha256: {entry!r}")
            continue
        fp = root / rel
        if not fp.is_file():
            issues.append(f"Missing file listed in manifest: {rel}")
            continue
        actual = _sha256_file(fp)
        if actual.lower() != str(expected).lower():
            issues.append(
                f"SHA-256 mismatch for {rel}: expected {expected[:16]}… got {actual[:16]}…"
            )

    return len(issues) == 0, issues


def load_model_catalogue(bundle_root: Path) -> Dict[str, Any]:
    """
    Load ``models/model_catalogue.json`` from a bundle.

    Raises:
        FileNotFoundError, json.JSONDecodeError, ValueError on invalid payload.
    """
    root = Path(bundle_root).resolve()
    cat_path = root / "models" / "model_catalogue.json"
    if not cat_path.is_file():
        raise FileNotFoundError(f"No model catalogue at {cat_path}")
    raw = json.loads(cat_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("model_catalogue.json must be a JSON object")
    if "models" not in raw:
        raise ValueError("model_catalogue.json must contain a 'models' array")
    if not isinstance(raw["models"], list):
        raise ValueError("model_catalogue.json 'models' must be a list")
    return raw


def build_install_pip_argv(
    pip_executable: str, bundle_root: Path, requirements_name: str = "requirements-deploy.txt"
) -> List[str]:
    """
    Build argv for offline pip install (used by tests and ``offline_install_helper``).

    Example:
        ``pip install --no-index --find-links=<wheelhouse> -r <requirements>``
    """
    root = Path(bundle_root).resolve()
    wh = root / "wheelhouse"
    req = root / requirements_name
    return [
        pip_executable,
        "install",
        "--no-index",
        f"--find-links={wh}",
        "-r",
        str(req),
    ]


if __name__ == "__main__":
    # Minimal CLI for CI: python -m installer.offline_bundle_lib verify <dir>
    if len(sys.argv) < 3 or sys.argv[1] != "verify":
        print("Usage: python offline_bundle_lib.py verify <bundle_root>", file=sys.stderr)
        sys.exit(2)
    ok, issues = verify_manifest(Path(sys.argv[2]))
    ok2, issues2 = validate_bundle_structure(Path(sys.argv[2]))
    all_ok = ok and ok2
    for line in issues + issues2:
        print(line, file=sys.stderr)
    sys.exit(0 if all_ok else 1)
