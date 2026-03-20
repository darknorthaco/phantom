"""
Phase 3 offline bundle tests — no network, no FastAPI.

Run with pytest (if installed)::

    pytest installer/tests/test_offline_bundle.py -q

Or stdlib only::

    python installer/tests/test_offline_bundle.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

INSTALLER = Path(__file__).resolve().parent.parent
if str(INSTALLER) not in sys.path:
    sys.path.insert(0, str(INSTALLER))

from offline_bundle import generate_bundle  # noqa: E402
from offline_bundle_lib import (  # noqa: E402
    build_install_pip_argv,
    load_model_catalogue,
    validate_bundle_structure,
    verify_manifest,
)

REPO = INSTALLER.parent


class TestOfflineBundleLib(unittest.TestCase):
    def test_validate_bundle_structure_minimal(self) -> None:
        root = Path(self._temp()) / "b"
        root.mkdir()
        (root / "wheelhouse").mkdir()
        (root / "models").mkdir()
        (root / "config_templates").mkdir()
        (root / "requirements-deploy.txt").write_text("x==1\n", encoding="utf-8")
        (root / "staging_mode.txt").write_text("skip\n", encoding="utf-8")
        (root / "manifest.json").write_text("{}", encoding="utf-8")
        (root / "models" / "model_catalogue.json").write_text(
            '{"models": []}', encoding="utf-8"
        )
        ok, issues = validate_bundle_structure(root)
        self.assertTrue(ok, str(issues))

    def test_manifest_hash_verification(self) -> None:
        root = Path(self._temp()) / "b"
        root.mkdir()
        d = root / "data"
        d.write_bytes(b"hello phantom")
        h = hashlib.sha256(b"hello phantom").hexdigest()
        manifest = {
            "schema_version": 1,
            "bundle_version": "test",
            "files": [{"relative_path": "data", "sha256": h}],
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        ok, issues = verify_manifest(root)
        self.assertTrue(ok, str(issues))
        d.write_bytes(b"tampered")
        ok2, issues2 = verify_manifest(root)
        self.assertFalse(ok2)
        self.assertTrue(any("mismatch" in m for m in issues2))

    def test_load_model_catalogue(self) -> None:
        root = Path(self._temp()) / "b"
        (root / "models").mkdir(parents=True)
        payload = {"models": [{"id": "a"}]}
        (root / "models" / "model_catalogue.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        out = load_model_catalogue(root)
        self.assertEqual(out["models"][0]["id"], "a")

    def test_wheelhouse_argv_contains_no_index(self) -> None:
        root = Path(self._temp()) / "b"
        root.mkdir(parents=True)
        (root / "wheelhouse").mkdir()
        (root / "requirements-deploy.txt").write_text("pip\n", encoding="utf-8")
        argv = build_install_pip_argv("/venv/bin/pip", root)
        self.assertIn("--no-index", argv)
        self.assertTrue(any(x.startswith("--find-links=") for x in argv))

    def test_offline_install_helper_mocked_pip(self) -> None:
        import offline_install_helper as h

        root = Path(self._temp()) / "b"
        root.mkdir(parents=True)
        (root / "wheelhouse").mkdir()
        (root / "requirements-deploy.txt").write_text("x==1\n", encoding="utf-8")
        recorded: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: object):
            recorded.append(cmd)
            return mock.Mock(returncode=0, stderr="", stdout="")

        with mock.patch.object(h.subprocess, "run", fake_run):
            code = h.install_deps(str(Path(root) / "pip"), root)
        self.assertEqual(code, 0)
        self.assertTrue(recorded)
        self.assertIn("--no-index", recorded[0])

    def _temp(self) -> str:
        import tempfile

        return tempfile.mkdtemp()


class TestGenerateBundleSkipPip(unittest.TestCase):
    def test_generate_bundle_skip_pip(self) -> None:
        engine = REPO / "phantom_core"
        if not (engine / "run.py").is_file():
            self.skipTest("phantom_core/run.py not in workspace")
        out = INSTALLER / "tests" / "_test_bundle_out"
        if out.exists():
            shutil.rmtree(out)
        try:
            generate_bundle(out, engine, skip_pip_download=True)
            ok, issues = verify_manifest(out)
            ok2, issues2 = validate_bundle_structure(out)
            self.assertTrue(ok and ok2, str(issues + issues2))
            cat = load_model_catalogue(out)
            self.assertIn("models", cat)
        finally:
            if out.exists():
                shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()
