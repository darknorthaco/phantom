#!/usr/bin/env python3
"""
Local CI runner — mirrors GitHub Actions ``test-controller`` / Windows Python smoke jobs.

Runs (in order):
  1. black --check phantom_core/
  2. flake8 (package tree)
  3. phantom_core/scripts/ci/check_platform_assumptions.py
  4. Controller import smoke
  5. pytest tests/test_controller_import_boot.py
  6. Optional: TCP bind probe on controller port (no admin)

Uses only the interpreter given on the CLI (typically Phantom venv); does not modify system PATH.
Emits JSON lines on stdout (``-u`` unbuffered) for GUI progress; human text on stderr.

Chronicle: appends JSONL records to ``<phantom_root>/deployment_chronicle.jsonl`` compatible with
Rust ``ChronicleRecord`` (ts, source, level, summary, details.event=local_ci_step).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_chronicle(
    phantom_root: Path | None,
    *,
    step: str,
    status: str,
    details: str,
    exit_code: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one line matching Tauri ``deployment_chronicle`` / ``ChronicleRecord`` shape."""
    if phantom_root is None:
        return
    path = phantom_root / "deployment_chronicle.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    level = "error" if status == "failed" else "info"
    payload: dict[str, Any] = {
        "event": "local_ci_step",
        "step": step,
        "status": status,
        "details": details[:8000],
    }
    if exit_code is not None:
        payload["exitCode"] = exit_code
    if extra:
        payload.update(extra)
    record = {
        "ts": _utc_ts(),
        "source": "local_ci",
        "level": level,
        "summary": f"Local CI {step}: {status}",
        "details": payload,
    }
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def emit(kind: str, json_progress: bool, **kw: Any) -> None:
    if not json_progress:
        return
    row = {"kind": kind, **kw}
    print(json.dumps(row, ensure_ascii=False), flush=True)


def log_err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def resolve_dev_tools_requirements(script_file: Path) -> Path:
    d = script_file.resolve().parent
    req = d / "dev_tools" / "requirements-local-ci.txt"
    if req.is_file():
        return req
    raise FileNotFoundError(f"requirements-local-ci.txt not found next to script at {req}")


def ensure_dev_tools(py: Path, script_file: Path) -> tuple[bool, str]:
    try:
        req = resolve_dev_tools_requirements(script_file)
    except FileNotFoundError as e:
        return False, str(e)
    log_err(f"[local_ci] Ensuring dev tools from {req} …")
    r = subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "-q",
            "--disable-pip-version-check",
            "-r",
            str(req),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONNOUSERSITE": "1"},
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
        return False, err
    return True, "pip install ok"


def run_step(
    py: Path,
    args: list[str],
    *,
    cwd: Path | None,
    env: dict[str, str],
    step_name: str,
    phantom_root: Path | None,
    json_progress: bool,
) -> tuple[bool, str, int]:
    emit("step_begin", json_progress, step=step_name)
    log_err(f"[local_ci] === {step_name} ===")
    log_err(f"[local_ci] cwd={cwd} {' '.join(args)}")
    r = subprocess.run(
        [str(py), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        env=env,
    )
    out = (r.stdout or "") + (r.stderr or "")
    snippet = out.strip()[-4000:] if out.strip() else f"(no output, exit {r.returncode})"
    ok = r.returncode == 0
    status = "passed" if ok else "failed"
    append_chronicle(
        phantom_root,
        step=step_name,
        status=status,
        details=snippet,
        exit_code=r.returncode,
    )
    emit(
        "step_end",
        json_progress,
        step=step_name,
        ok=ok,
        exitCode=r.returncode,
        detail=snippet[:2000],
    )
    return ok, snippet, r.returncode


def run_platform_scanner(py: Path, scanner: Path, phantom_root: Path | None, json_progress: bool) -> tuple[bool, str, int]:
    step_name = "platform_assumptions"
    emit("step_begin", json_progress, step=step_name)
    log_err(f"[local_ci] === {step_name} ===")
    log_err(f"[local_ci] {py} {scanner}")
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    r = subprocess.run([str(py), str(scanner)], capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    snippet = out.strip()[-4000:] if out.strip() else f"(no output, exit {r.returncode})"
    ok = r.returncode == 0
    status = "passed" if ok else "failed"
    append_chronicle(
        phantom_root,
        step=step_name,
        status=status,
        details=snippet,
        exit_code=r.returncode,
    )
    emit("step_end", json_progress, step=step_name, ok=ok, exitCode=r.returncode, detail=snippet[:2000])
    return ok, snippet, r.returncode


def run_import_smoke(
    py: Path,
    phantom_core_home: Path,
    phantom_root: Path | None,
    json_progress: bool,
) -> tuple[bool, str, int]:
    step_name = "controller_import"
    code = "from phantom_core.controller_api import app; assert app is not None"
    emit("step_begin", json_progress, step=step_name)
    log_err(f"[local_ci] === {step_name} ===")
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    r = subprocess.run(
        [str(py), "-c", code],
        cwd=str(phantom_core_home),
        capture_output=True,
        text=True,
        env=env,
    )
    out = (r.stdout or "") + (r.stderr or "")
    snippet = out.strip()[-4000:] if out.strip() else f"(no output, exit {r.returncode})"
    ok = r.returncode == 0
    status = "passed" if ok else "failed"
    append_chronicle(
        phantom_root,
        step=step_name,
        status=status,
        details=snippet,
        exit_code=r.returncode,
    )
    emit("step_end", json_progress, step=step_name, ok=ok, exitCode=r.returncode, detail=snippet[:2000])
    return ok, snippet, r.returncode


def optional_port_bind_check(port: int, phantom_root: Path | None, json_progress: bool) -> tuple[bool, str]:
    step_name = "port_bind_probe"
    emit("step_begin", json_progress, step=step_name, detail=f"127.0.0.1:{port}")
    log_err(f"[local_ci] === {step_name} :{port} ===")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.close()
        msg = f"Port {port} is available for bind on 127.0.0.1."
        append_chronicle(phantom_root, step=step_name, status="passed", details=msg, exit_code=0)
        emit("step_end", json_progress, step=step_name, ok=True, exitCode=0, detail=msg)
        return True, msg
    except OSError as e:
        msg = f"Port {port} bind failed ({e!s}). Another process may be listening — matches common Windows CI failure mode."
        append_chronicle(phantom_root, step=step_name, status="failed", details=msg, exit_code=1)
        emit("step_end", json_progress, step=step_name, ok=False, exitCode=1, detail=msg)
        return False, msg


def read_controller_port(phantom_root: Path) -> int | None:
    cfg = phantom_root / "phantom_config.json"
    if not cfg.is_file():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        c = data.get("controller") or {}
        p = c.get("port")
        if isinstance(p, int):
            return int(p)
        if isinstance(p, str) and p.isdigit():
            return int(p)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


@dataclass
class RunResult:
    ok: bool = True
    failed_steps: list[str] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phantom local CI checks (GitHub-equivalent).")
    parser.add_argument(
        "--python",
        dest="python_exe",
        type=Path,
        help="Absolute path to Python executable (Phantom venv). Required unless sys.executable is intended.",
    )
    parser.add_argument(
        "--phantom-core-home",
        type=Path,
        help="Directory containing run.py and phantom_core/ package (engine root).",
    )
    parser.add_argument(
        "--phantom-root",
        type=Path,
        help="Phantom state dir; chronicle written to deployment_chronicle.jsonl here.",
    )
    parser.add_argument(
        "--ensure-dev-tools",
        action="store_true",
        help="pip install -r dev_tools/requirements-local-ci.txt into this interpreter's environment.",
    )
    parser.add_argument(
        "--port-check",
        action="store_true",
        help="After tests, probe bind on controller port from phantom_config.json (or --port).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override port for --port-check.",
    )
    parser.add_argument(
        "--json-progress",
        action="store_true",
        help="Emit JSON progress lines on stdout (for Tauri GUI).",
    )
    args = parser.parse_args()

    py = args.python_exe or Path(sys.executable)
    py = py.resolve()
    if not py.is_file():
        log_err(f"Python executable not found: {py}")
        return 2

    script_file = Path(__file__).resolve()
    phantom_root: Path | None = args.phantom_root.resolve() if args.phantom_root else None

    core_home = args.phantom_core_home
    if core_home is None:
        guess = script_file.parent.parent / "phantom_core"
        if guess.is_dir() and (guess / "run.py").is_file():
            core_home = guess
        else:
            log_err(
                "Missing --phantom-core-home (and no ../phantom_core from script). "
                "Pass engine root (directory with run.py)."
            )
            return 2
    core_home = core_home.resolve()
    if not (core_home / "phantom_core").is_dir():
        log_err(f"Invalid --phantom-core-home (no phantom_core package dir): {core_home}")
        return 2

    json_progress = args.json_progress
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}

    emit("run_begin", json_progress, phantomCoreHome=str(core_home), python=str(py))

    if args.ensure_dev_tools:
        ok_pip, pip_msg = ensure_dev_tools(py, script_file)
        append_chronicle(
            phantom_root,
            step="ensure_dev_tools",
            status="passed" if ok_pip else "failed",
            details=pip_msg,
            exit_code=0 if ok_pip else 1,
        )
        emit("step_end", json_progress, step="ensure_dev_tools", ok=ok_pip, detail=pip_msg[:2000])
        if not ok_pip:
            log_err(pip_msg)
            emit("run_summary", json_progress, ok=False, failedSteps=["ensure_dev_tools"])
            return 1

    result = RunResult()
    scanner = core_home / "scripts" / "ci" / "check_platform_assumptions.py"
    if not scanner.is_file():
        log_err(f"Platform scanner missing: {scanner}")
        append_chronicle(
            phantom_root,
            step="platform_assumptions",
            status="failed",
            details=f"Missing scanner at {scanner}",
            exit_code=2,
        )
        emit("run_summary", json_progress, ok=False, failedSteps=["platform_assumptions"])
        return 1

    # 1–2: black + flake8 (cwd = core_home, same as CI working-directory phantom_core)
    ok, _, code = run_step(
        py,
        ["-m", "black", "--check", "phantom_core/"],
        cwd=core_home,
        env=env,
        step_name="black",
        phantom_root=phantom_root,
        json_progress=json_progress,
    )
    if not ok:
        result.ok = False
        result.failed_steps.append("black")

    ok, _, code = run_step(
        py,
        [
            "-m",
            "flake8",
            "--max-line-length=120",
            "--extend-ignore=E203,W503",
            "--exclude=venv,build,dist,.eggs",
            "phantom_core/",
        ],
        cwd=core_home,
        env=env,
        step_name="flake8",
        phantom_root=phantom_root,
        json_progress=json_progress,
    )
    if not ok:
        result.ok = False
        result.failed_steps.append("flake8")

    # 3: platform assumptions
    ok, _, _ = run_platform_scanner(py, scanner, phantom_root, json_progress)
    if not ok:
        result.ok = False
        result.failed_steps.append("platform_assumptions")

    # 4: import smoke
    ok, _, _ = run_import_smoke(py, core_home, phantom_root, json_progress)
    if not ok:
        result.ok = False
        result.failed_steps.append("controller_import")

    # 5: pytest (in-process /health)
    ok, _, _ = run_step(
        py,
        ["-m", "pytest", "tests/test_controller_import_boot.py", "-v", "--tb=short"],
        cwd=core_home,
        env=env,
        step_name="pytest_health_smoke",
        phantom_root=phantom_root,
        json_progress=json_progress,
    )
    if not ok:
        result.ok = False
        result.failed_steps.append("pytest_health_smoke")

    # 6: optional port bind
    if args.port_check:
        port = args.port
        if port is None and phantom_root:
            port = read_controller_port(phantom_root)
        if port is None:
            port = 8080
        ok_bind, _ = optional_port_bind_check(port, phantom_root, json_progress)
        if not ok_bind:
            result.ok = False
            result.failed_steps.append("port_bind_probe")

    summary_status = "passed" if result.ok else "failed"
    append_chronicle(
        phantom_root,
        step="local_ci_summary",
        status=summary_status,
        details=json.dumps({"failedSteps": result.failed_steps}),
        exit_code=0 if result.ok else 1,
    )
    emit(
        "run_summary",
        json_progress,
        ok=result.ok,
        failedSteps=result.failed_steps,
    )

    log_err(f"[local_ci] === SUMMARY: {'PASS' if result.ok else 'FAIL'} ===")
    if result.failed_steps:
        log_err(f"[local_ci] Failed steps: {', '.join(result.failed_steps)}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
