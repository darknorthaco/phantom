#!/usr/bin/env python3
"""
Foreign Transactions Scanner — forbidden top-level imports and os.fork in shared controller code.

Scans ``phantom_core/phantom_core/**/*.py`` (the controller package) for:

- Module-level imports of POSIX-only or high-risk stdlib modules.
- Any call to ``os.fork`` (unsupported on Windows; forbidden in shared controller package).

``fcntl`` must not appear at module scope anywhere (including ``trust_store_filelock.py``);
lazy import inside functions is required.

Doctrine: see ``meta/platform_assumptions_ledger.yaml``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Repo layout: this file lives at phantom_core/scripts/ci/
PHANTOM_CORE_PKG = Path(__file__).resolve().parents[2] / "phantom_core"

FORBIDDEN_MODULES = frozenset(
    {
        "fcntl",
        "termios",
        "pty",
        "pwd",
        "grp",
        "spwd",
        "resource",
        "syslog",
        "nis",
    }
)


def _top_level_imports(tree: ast.Module) -> list[tuple[str, int, str]]:
    """Return list of (module_name, lineno, kind)."""
    found: list[tuple[str, int, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".", 1)[0]
                found.append((base, node.lineno, "import"))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module.split(".", 1)[0]
                found.append((base, node.lineno, "from"))
    return found


def _is_os_fork_call(node: ast.AST) -> bool:
    """True if this AST node is a call to os.fork()."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "fork":
        if isinstance(func.value, ast.Name) and func.value.id == "os":
            return True
    if isinstance(func, ast.Name) and func.id == "fork":
        return True
    return False


def scan_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError) as e:
        return [f"{path}: parse error: {e}"]

    for mod, lineno, kind in _top_level_imports(tree):
        if mod in FORBIDDEN_MODULES:
            violations.append(
                f"{path}:{lineno}: forbidden top-level {kind} '{mod}' "
                f"(use OS-guarded helper; fcntl only inside a function body in trust_store_filelock)"
            )

    for node in ast.walk(tree):
        if _is_os_fork_call(node):
            violations.append(
                f"{path}:{getattr(node, 'lineno', 0)}: os.fork() forbidden in controller package "
                f"(Windows-incompatible; use multiprocessing or explicit subprocess)"
            )

    return violations


def main() -> int:
    if not PHANTOM_CORE_PKG.is_dir():
        print(f"ERROR: package dir not found: {PHANTOM_CORE_PKG}", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    for py in sorted(PHANTOM_CORE_PKG.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        all_violations.extend(scan_file(py))

    if all_violations:
        print("Platform assumptions violations:\n", file=sys.stderr)
        for v in all_violations:
            print(v, file=sys.stderr)
        return 1

    print(
        f"OK: scanned {PHANTOM_CORE_PKG} — no forbidden top-level imports, no os.fork",
        file=sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
