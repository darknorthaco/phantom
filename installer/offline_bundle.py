#!/usr/bin/env python3
"""
Phantom offline / air-gapped bundle generator (Phase 3).

Produces a deterministic directory layout for the canonical Tauri deployer::

    offline_bundle/
      wheelhouse/           # pip wheels (+ optional sdists)
      binaries/             # optional platform payloads (see README)
      models/
        model_catalogue.json
      config_templates/
      requirements-deploy.txt
      resolver_manifest.json
      manifest.json         # sha256 for every file under the bundle

Usage (online machine with Python + pip)::

    python installer/offline_bundle.py generate --output ./dist/offline_bundle \\
        --engine-root ./phantom_core

See docs/offline_install.md for policy and verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

INSTALLER_DIR = Path(__file__).resolve().parent
REPO_ROOT = INSTALLER_DIR.parent
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

# Re-use verification helpers (same process guarantees schema alignment).
from offline_bundle_lib import (  # noqa: E402
    MANIFEST_NAME,
    validate_bundle_structure,
    verify_manifest,
)

DEFAULT_REQ = INSTALLER_DIR / "requirements-deploy.txt"
SCHEMA_VERSION = 1


def _export_model_catalogue() -> Dict[str, Any]:
    """Sovereign-filtered catalogue from installer backend (no download)."""
    sys.path.insert(0, str(INSTALLER_DIR))
    from backend_interface.model_downloader import MODELS  # noqa: WPS433

    payload = json.dumps(MODELS, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "compliance": "sovereign-filtered",
        "source": "installer.backend_interface.model_downloader.MODELS",
        "models": MODELS,
        "models_sha256": digest,
    }


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, dirs_exist_ok=False)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _pip_download(wheelhouse: Path, requirements: Path) -> None:
    wheelhouse.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(wheelhouse),
        "-r",
        str(requirements),
        "--no-cache-dir",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pip download failed: {proc.stderr[:2000] or proc.stdout[:2000]}"
        )


def _freeze_resolver_info(requirements: Path, wheelhouse: Path) -> Dict[str, Any]:
    """Record resolver inputs (not a full pip freeze — wheels are the truth)."""
    req_hash = (
        hashlib.sha256(requirements.read_bytes()).hexdigest()
        if requirements.exists()
        else ""
    )
    wheels = sorted(wheelhouse.glob("*.whl")) + sorted(wheelhouse.glob("*.tar.gz"))
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "requirements_deploy_sha256": req_hash,
        "requirements_deploy_path": "requirements-deploy.txt",
        "wheel_count": len(wheels),
        "python_executable": sys.executable,
        "platform": sys.platform,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def _write_config_templates(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    phantom = {
        "_comment": "Template only — Tauri bootstrap_config overwrites on deploy.",
        "controller": {
            "host": "127.0.0.1",
            "port": 8080,
            "security": "disabled",
            "identity_fingerprint": "",
            "socket_integrated": True,
        },
        "ports": {
            "controller_api": {"port": 8080, "protocol": "tcp", "required": True},
            "worker_http": {"port": 8090, "protocol": "tcp", "required": True},
            "discovery_udp": {"port": 8095, "protocol": "udp", "required": True},
            "socket_infra": {"port": 8081, "protocol": "tcp", "required": False},
        },
        "discovery": {"total_timeout_ms": 10000, "early_exit_on_first_worker": True},
        "execution_modes": {"default_mode": "manual"},
        "config_version": "1.0",
    }
    worker = {
        "_comment": "Local worker template — adjust after install.",
        "worker_id": "local-worker",
        "controller_host": "127.0.0.1",
        "controller_port": 8080,
        "worker_port": 8090,
    }
    _write_text(dest / "phantom_config.template.json", json.dumps(phantom, indent=2))
    _write_text(dest / "worker_config.template.json", json.dumps(worker, indent=2))
    _write_text(
        dest / "tls_README.txt",
        "Place PEM bundles here for manual TLS setup (offline).\n"
        "Expected names: controller.crt, controller.key (local policy).\n",
    )


def _write_binaries_readme(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _write_text(
        dest / "README.txt",
        "Optional payloads for air-gapped sites:\n\n"
        "- This repository does not ship standalone Rust binaries named "
        "phantom_controller / phantom_worker; the Stone-Home runtime uses "
        "Python controller/worker entrypoints copied from bundle engine/.\n"
        "- You may copy a built Tauri app executable or NSIS artifact here "
        "for archival; paths are hashed into manifest.json when present.\n",
    )


def _hash_all_files(bundle_root: Path) -> List[Dict[str, Any]]:
    """Collect every file's relative path, size, sha256 (excluding manifest itself)."""
    entries: List[Dict[str, Any]] = []
    root = bundle_root.resolve()
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name == MANIFEST_NAME:
                continue
            fp = Path(dirpath) / name
            rel = fp.relative_to(root).as_posix()
            st = fp.stat()
            h = hashlib.sha256()
            with fp.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            entries.append(
                {
                    "relative_path": rel,
                    "sha256": h.hexdigest(),
                    "size_bytes": st.st_size,
                }
            )
    entries.sort(key=lambda e: e["relative_path"])
    return entries


def generate_bundle(
    output: Path,
    engine_root: Path,
    *,
    skip_pip_download: bool = False,
    requirements_file: Path | None = None,
) -> Path:
    """
    Build offline_bundle at *output*.

    Raises:
        RuntimeError on pip failure or missing engine_root.
    """
    output = output.resolve()
    engine_root = engine_root.resolve()
    if not (engine_root / "run.py").is_file():
        raise RuntimeError(f"engine_root must contain run.py: {engine_root}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    wh = output / "wheelhouse"
    req_src = Path(requirements_file) if requirements_file else DEFAULT_REQ
    if not req_src.is_file():
        raise RuntimeError(f"requirements file not found: {req_src}")
    shutil.copy2(req_src, output / "requirements-deploy.txt")

    if not skip_pip_download:
        _pip_download(wh, output / "requirements-deploy.txt")
    else:
        wh.mkdir(parents=True, exist_ok=True)
        _write_text(
            output / "staging_mode.txt",
            "pip download skipped (--skip-pip-download); not suitable for real air-gap install.\n",
        )
        _write_text(
            wh / ".gitkeep_placeholder",
            "pip download skipped (--skip-pip-download).\n",
        )

    resolver = _freeze_resolver_info(output / "requirements-deploy.txt", wh)
    _write_text(output / "resolver_manifest.json", json.dumps(resolver, indent=2))

    eng_dest = output / "engine"
    _copy_tree(engine_root, eng_dest)

    models_dir = output / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    catalogue = _export_model_catalogue()
    _write_text(models_dir / "model_catalogue.json", json.dumps(catalogue, indent=2))

    _write_config_templates(output / "config_templates")
    _write_binaries_readme(output / "binaries")

    file_entries = _hash_all_files(output)
    bundle_version = os.environ.get("PHANTOM_OFFLINE_BUNDLE_VERSION", "1.0.0")
    manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": bundle_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "phantom-offline-bundle",
        "files": file_entries,
    }
    _write_text(output / MANIFEST_NAME, json.dumps(manifest, indent=2))

    ok, issues = verify_manifest(output)
    ok2, issues2 = validate_bundle_structure(output)
    if not ok or not ok2:
        raise RuntimeError("Bundle self-check failed: " + "; ".join(issues + issues2))

    return output


def cmd_verify(bundle: Path) -> int:
    ok, issues = verify_manifest(bundle)
    ok2, issues2 = validate_bundle_structure(bundle)
    for line in issues + issues2:
        print(line, file=sys.stderr)
    return 0 if ok and ok2 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Phantom offline bundle tools (Phase 3)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Build offline_bundle directory")
    g.add_argument("--output", type=Path, required=True, help="Output directory")
    g.add_argument(
        "--engine-root",
        type=Path,
        default=REPO_ROOT / "phantom_core",
        help="Path to phantom_core (must contain run.py)",
    )
    g.add_argument(
        "--requirements",
        type=Path,
        default=None,
        help="Override requirements file (default: installer/requirements-deploy.txt)",
    )
    g.add_argument(
        "--skip-pip-download",
        action="store_true",
        help="Structure-only (no network pip); for doc/CI layout tests",
    )

    v = sub.add_parser("verify", help="Verify manifest + layout")
    v.add_argument("--bundle", type=Path, required=True)

    args = ap.parse_args()
    if args.cmd == "generate":
        try:
            out = generate_bundle(
                args.output,
                args.engine_root,
                skip_pip_download=args.skip_pip_download,
                requirements_file=args.requirements,
            )
        except Exception as exc:
            print(f"generate failed: {exc}", file=sys.stderr)
            return 1
        print(f"Offline bundle ready: {out}")
        return 0
    if args.cmd == "verify":
        return cmd_verify(args.bundle)
    return 2


if __name__ == "__main__":
    sys.exit(main())
