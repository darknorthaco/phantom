#!/usr/bin/env python3
"""
PR-D chronicle severity regression gate.

Ensures schema v2 + severity plumbing remain present in source.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CHRON = ROOT / "phantom_app/src-tauri/src/backend/ceremony/ceremony_chronicle.rs"
ORCH = ROOT / "phantom_app/src-tauri/src/backend/ceremony/orchestrator.rs"


def assert_contains(text: str, needle: str, msg: str) -> None:
    if needle not in text:
        raise AssertionError(msg)


def main() -> int:
    chron = CHRON.read_text(encoding="utf-8")
    orch = ORCH.read_text(encoding="utf-8")

    assert_contains(chron, 'CEREMONY_CHRONICLE_SCHEMA_VERSION: &str = "2"', "schema version must be 2")
    assert_contains(chron, "pub enum Severity", "Severity enum missing")
    assert_contains(chron, "pub severity: Severity", "severity field missing from chronicle line")
    assert_contains(chron, "new_with_severity", "severity constructor missing")
    assert_contains(orch, "Severity::Critical", "orchestrator critical severity mapping missing")
    assert_contains(orch, "Severity::Warn", "orchestrator warn severity mapping missing")

    print("chronicle_severity_gate: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"chronicle_severity_gate: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
