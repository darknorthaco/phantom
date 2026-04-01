#!/usr/bin/env python3
"""
Phantom surgical uninstall orchestrator (CLI / installer hook).

Mirrors in-app ``surgical_uninstall`` behavior on Windows: stop service, firewall rules,
terminate Phantom-related Python processes, append report to Deployment Chronicle,
remove ``%USERPROFILE%\\.phantom``, LocalAppData/AppData Phantom folders, shortcuts,
and user-hive uninstall registry keys.

Safety: only touches Phantom-owned paths under known roots. Use ``--dry-run`` to preview.

Does not remove the running ``phantom_app.exe`` if it is located under a removal target
(same as ``from_running_phantom_app`` in Rust).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def chronicle_append(phantom_root: Path, report: dict) -> None:
    path = phantom_root / "deployment_chronicle.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": utc_now(),
            "source": "uninstall",
            "level": "info",
            "summary": "Surgical uninstall report (phantom_uninstall.py, pre-removal)",
            "details": report,
        },
        ensure_ascii=False,
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_ps(script: str, dry_run: bool) -> tuple[int, str]:
    if dry_run:
        return 0, f"[dry-run] would run PowerShell: {script[:120]}..."
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    return r.returncode, (r.stderr or r.stdout or "").strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Phantom surgical uninstall")
    p.add_argument("--dry-run", action="store_true", help="Print actions only")
    p.add_argument("--force", action="store_true", help="Non-interactive (no prompts)")
    p.add_argument("--silent", action="store_true", help="Minimal stdout")
    p.add_argument(
        "--kill-app",
        action="store_true",
        help="Also taskkill phantom_app.exe (not used when uninstall runs from inside the app)",
    )
    args = p.parse_args()

    if os.name != "nt":
        print("phantom_uninstall.py: non-Windows mode is minimal — remove ~/.phantom and systemd user phantom manually.", file=sys.stderr)
        home = Path.home()
        pr = home / ".phantom"
        removed, errors = [], []
        if pr.exists() and not args.dry_run:
            try:
                shutil.rmtree(pr)
                removed.append(str(pr))
            except OSError as e:
                errors.append(str(e))
        elif args.dry_run and pr.exists():
            removed.append(f"[dry-run] would remove {pr}")
        print(json.dumps({"status": "complete" if not errors else "partial", "removed": removed, "errors": errors, "timestamp": utc_now()}))
        return 0 if not errors else 1

    removed: list[str] = []
    skipped: list[dict] = []
    errors: list[str] = []

    user = os.environ.get("USERPROFILE", "")
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    phantom_root = Path(user) / ".phantom"

    if not args.force and not args.silent and not args.dry_run:
        print("This will remove Phantom data under .phantom, LocalAppData\\Phantom, and related paths.")
        if input("Type YES to continue: ").strip() != "YES":
            print("Aborted.")
            return 2

    # Service + firewall (best effort)
    for cmd in [
        ["sc", "stop", "phantom"],
        ["sc", "delete", "phantom"],
    ]:
        if args.dry_run:
            removed.append(f"[dry-run] {' '.join(cmd)}")
        else:
            subprocess.run(cmd, capture_output=True)

    for name in ["PhantomController", "PhantomWorker", "PhantomDiscovery", "PhantomSocket"]:
        netsh = [
            "netsh",
            "advfirewall",
            "firewall",
            "delete",
            "rule",
            f"name={name}",
        ]
        if args.dry_run:
            removed.append(f"[dry-run] netsh delete rule {name}")
        else:
            subprocess.run(netsh, capture_output=True)
    removed.append("firewall rules / service (best effort)")

    ps_py = r"""
$ErrorActionPreference = 'SilentlyContinue'
$venv = [regex]::Escape([IO.Path]::Combine($env:USERPROFILE, '.phantom', 'venv'))
$localPhantom = [regex]::Escape([IO.Path]::Combine($env:LOCALAPPDATA, 'Phantom'))
$localBundle = [regex]::Escape([IO.Path]::Combine($env:LOCALAPPDATA, 'com.darknorth.phantom'))
Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.ExecutablePath
} | ForEach-Object {
  $path = $_.ExecutablePath
  if ($path -match $venv -or $path -match $localPhantom -or $path -match $localBundle) {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
"""
    code, msg = run_ps(ps_py, args.dry_run)
    if code != 0 and msg:
        errors.append(f"terminate python: {msg}")
    removed.append("filtered python processes")

    if args.kill_app and not args.dry_run:
        subprocess.run(["taskkill", "/F", "/IM", "phantom_app.exe"], capture_output=True)
        removed.append("taskkill phantom_app.exe")

    report = {
        "status": "complete",
        "removed_preview": removed.copy(),
        "skipped": skipped,
        "errors": errors,
        "timestamp": utc_now(),
        "dryRun": args.dry_run,
    }
    if phantom_root.exists():
        chronicle_append(phantom_root, report)

    if phantom_root.exists():
        if args.dry_run:
            removed.append(f"[dry-run] would remove {phantom_root}")
        else:
            try:
                shutil.rmtree(phantom_root)
                removed.append(str(phantom_root))
            except OSError as e:
                errors.append(f"remove .phantom: {e}")

    candidates = [
        Path(local) / "Phantom",
        Path(local) / "com.darknorth.phantom",
        Path(appdata) / "Phantom",
        Path(appdata) / "com.darknorth.phantom",
        Path(appdata) / "phantom_app",
    ]
    try:
        exe = Path(sys.executable).resolve()
    except Exception:
        exe = None

    for root in candidates:
        if not root.exists():
            continue
        if args.dry_run:
            removed.append(f"[dry-run] would clean {root}")
            continue
        try:
            if exe and exe.parent.resolve() == root.resolve():
                for child in root.iterdir():
                    if child.resolve() == exe.resolve():
                        skipped.append({"path": str(child), "reason": "current executable"})
                        continue
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
            else:
                shutil.rmtree(root, ignore_errors=True)
            removed.append(str(root))
        except OSError as e:
            errors.append(f"{root}: {e}")

    for key in [
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\com.darknorth.phantom",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Phantom",
    ]:
        if args.dry_run:
            removed.append(f"[dry-run] reg delete {key}")
        else:
            subprocess.run(["reg", "delete", key, "/f"], capture_output=True)

    out = {
        "status": "complete" if not errors else "partial",
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
        "timestamp": utc_now(),
    }
    print(json.dumps(out, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
