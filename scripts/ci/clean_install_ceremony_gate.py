#!/usr/bin/env python3
"""
PR-D structural clean-install gate.

This is a static guard that fails CI if release-source defaults permit legacy
deploy flows. It complements runtime tests by preventing the exact class of
regression that shipped v1.6.2 (legacy path reachable by default).
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    cargo = read("phantom_app/src-tauri/Cargo.toml")
    lib_rs = read("phantom_app/src-tauri/src/lib.rs")
    front = read("phantom_app/src/components/FrontPorchDeploy.tsx")
    ceremony = read("phantom_app/src/components/DeploymentCeremony.tsx")
    tauri_ts = read("phantom_app/src/utils/tauri.ts")

    assert_true('default = []' in cargo, "Cargo default features must be explicit")
    assert_true('legacy_deploy' not in cargo, "legacy_deploy feature must be fully removed")
    assert_true('async fn deploy_mode(' in lib_rs, "deploy_mode command missing")
    assert_true(
        '#[cfg(feature = "legacy_deploy")]' not in lib_rs,
        "legacy feature cfg blocks must be removed from lib.rs",
    )
    assert_true(
        "run_deployment_pre_scan" not in lib_rs
        and "complete_deployment_with_selection" not in lib_rs
        and "deploy_phantom" not in lib_rs,
        "legacy deploy commands must not exist in canonical backend",
    )

    # Canonical UI may not call legacy deploy functions.
    forbidden_ui_patterns = [
        "runDeploymentPreScan(",
        "completeDeploymentWithSelection(",
        "deployPhantom(",
    ]
    for p in forbidden_ui_patterns:
        assert_true(p not in front, f"FrontPorchDeploy still references legacy path: {p}")
        assert_true(p not in ceremony, f"DeploymentCeremony still references legacy path: {p}")
        assert_true(p not in tauri_ts, f"tauri.ts still exports legacy binding: {p}")

    # Build-mode helper must default to ceremony.
    mode_fn = re.search(r"export const deployModeFromBuild[\s\S]+?return 'ceremony';", tauri_ts)
    assert_true(mode_fn is not None, "deployModeFromBuild() must default to ceremony")

    print("clean_install_ceremony_gate: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"clean_install_ceremony_gate: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
