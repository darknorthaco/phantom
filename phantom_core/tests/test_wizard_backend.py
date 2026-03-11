#!/usr/bin/env python3
"""
Tests for the Phantom GUI Wizard backend modules.

Tests cover:
  - system_scan_adapter
  - worker_discovery_adapter
  - model_downloader
  - config_writer (ConfigWriter + ConfigBootstrap)
  - config_schema (ConfigSchema)
  - installer_driver
  - phantom_installer_api (integration)

These tests run without a display (no Tkinter import).
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add installer directory to path
# __file__ is phantom_core/tests/test_wizard_backend.py
# Go two levels up (.parent.parent = project root) then into installer/
_installer_dir = Path(__file__).parent.parent.parent / "installer"
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

# Add phantom_core package to path for config_schema imports
_phantom_core_dir = Path(__file__).parent.parent
if str(_phantom_core_dir) not in sys.path:
    sys.path.insert(0, str(_phantom_core_dir))


# ---------------------------------------------------------------------------
# ConfigSchema  (§8 Corrected Config Model)
# ---------------------------------------------------------------------------


class TestConfigSchema(unittest.TestCase):
    """Tests for phantom_core.config_schema.ConfigSchema."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_instance_passes_validation(self):
        from phantom_core.config_schema import ConfigSchema

        schema = ConfigSchema()
        schema.validate()  # must not raise

    def test_to_dict_contains_all_required_keys(self):
        from phantom_core.config_schema import ConfigSchema

        d = ConfigSchema().to_dict()
        for key in (
            "controller",
            "ports",
            "worker",
            "execution_modes",
            "config_version",
            "written_at",
            "written_by_step",
        ):
            self.assertIn(key, d)

    def test_from_dict_round_trip(self):
        from phantom_core.config_schema import ConfigSchema

        original = ConfigSchema()
        original.controller.host = "10.0.0.1"
        original.controller.port = 9000
        original.controller.security = "full"
        restored = ConfigSchema.from_dict(original.to_dict())
        self.assertEqual(restored.controller.host, "10.0.0.1")
        self.assertEqual(restored.controller.port, 9000)
        self.assertEqual(restored.controller.security, "full")

    def test_validate_rejects_invalid_security(self):
        from phantom_core.config_schema import ConfigSchema

        schema = ConfigSchema()
        schema.controller.security = "ultra"
        with self.assertRaises(ValueError):
            schema.validate()

    def test_validate_rejects_port_out_of_range(self):
        from phantom_core.config_schema import ConfigSchema

        schema = ConfigSchema()
        schema.controller.port = 0
        with self.assertRaises(ValueError):
            schema.validate()

    def test_load_raises_file_not_found_when_absent(self):
        from phantom_core.config_schema import ConfigSchema

        with self.assertRaises(FileNotFoundError):
            ConfigSchema.load(self.tmp / "nonexistent.json")

    def test_load_from_file_written_by_config_bootstrap(self):
        """ConfigSchema.load() must parse a file written by ConfigBootstrap."""
        from backend_interface.config_writer import ConfigBootstrap
        from phantom_core.config_schema import ConfigSchema

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write(host="192.168.0.5", port=8080, security="basic")
        schema = ConfigSchema.load(dest)
        self.assertEqual(schema.controller.host, "192.168.0.5")
        self.assertEqual(schema.controller.security, "basic")
        self.assertEqual(schema.written_by_step, "4.5")

    def test_locate_phantom_config_returns_path(self):
        """locate_phantom_config() must return a Path without raising."""
        from phantom_core.config_schema import locate_phantom_config

        path = locate_phantom_config()
        self.assertIsInstance(path, Path)


# ---------------------------------------------------------------------------
# system_scan_adapter
# ---------------------------------------------------------------------------


class TestSystemScanAdapter(unittest.TestCase):
    """Tests for system_scan_adapter.run_system_scan()."""

    def test_returns_expected_structure(self):
        from backend_interface.system_scan_adapter import run_system_scan

        result = run_system_scan(ports=[19999, 19998])  # unused ports

        self.assertIn("ok", result)
        self.assertIn("checks", result)
        self.assertIsInstance(result["ok"], bool)
        self.assertIsInstance(result["checks"], dict)

    def test_check_keys_present(self):
        from backend_interface.system_scan_adapter import run_system_scan

        result = run_system_scan(ports=[19999])

        for key in ("os", "python", "disk", "ports", "gpu"):
            self.assertIn(key, result["checks"], f"Missing check key: {key}")

    def test_check_values_have_required_fields(self):
        from backend_interface.system_scan_adapter import run_system_scan

        result = run_system_scan(ports=[19999])

        for key, info in result["checks"].items():
            self.assertIn("name", info, f"{key}: missing 'name'")
            self.assertIn("status", info, f"{key}: missing 'status'")
            self.assertIn("detail", info, f"{key}: missing 'detail'")
            self.assertIn(
                info["status"],
                ("ok", "warning", "fail", "unknown"),
                f"{key}: unexpected status '{info['status']}'",
            )

    def test_ok_is_false_when_critical_fail(self):
        """ok must be False when python or os check fails."""
        from backend_interface import system_scan_adapter as mod

        # Patch SystemChecker to simulate a Python version failure
        with patch.object(
            mod.SystemChecker, "check_python_version", return_value=False
        ):
            result = mod.run_system_scan(ports=[19999])
            self.assertFalse(result["ok"])

    def test_passed_warnings_failed_lists_present(self):
        from backend_interface.system_scan_adapter import run_system_scan

        result = run_system_scan(ports=[19999])
        for key in ("passed", "warnings", "failed"):
            self.assertIn(key, result, f"Missing list key: {key}")
            self.assertIsInstance(result[key], list)


# ---------------------------------------------------------------------------
# worker_discovery_adapter
# ---------------------------------------------------------------------------


class TestWorkerDiscoveryAdapter(unittest.TestCase):
    """Tests for WorkerDiscoveryAdapter."""

    def setUp(self):
        from backend_interface.worker_discovery_adapter import WorkerDiscoveryAdapter

        self.adapter = WorkerDiscoveryAdapter()

    def test_get_local_network_delegates_to_backend(self):
        """get_local_network() should delegate to WorkerDiscovery backend."""
        with patch.object(
            self.adapter._backend, "get_local_network", return_value=None
        ) as mock:
            result = self.adapter.get_local_network()
            mock.assert_called_once()
            self.assertIsNone(result)

    def test_check_worker_port_delegates_to_backend(self):
        with patch.object(
            self.adapter._backend, "check_worker_port", return_value=True
        ) as mock:
            result = self.adapter.check_worker_port("192.168.1.1", 8090)
            mock.assert_called_once_with("192.168.1.1", 8090)
            self.assertTrue(result)

    def test_enrich_adds_display_fields(self):
        raw = [
            {
                "ip": "10.0.0.1",
                "gpu": "RTX 3090",
                "memory_total": 24576,
                "available": True,
            }
        ]
        enriched = self.adapter._enrich(raw)
        self.assertEqual(len(enriched), 1)
        w = enriched[0]
        self.assertIn("gpu_name", w)
        self.assertIn("vram_total_mb", w)
        self.assertIn("vram_display", w)
        self.assertIn("health", w)
        self.assertEqual(w["gpu_name"], "RTX 3090")
        self.assertEqual(w["vram_total_mb"], 24576)
        self.assertEqual(w["health"], "Healthy")

    def test_enrich_unknown_gpu(self):
        raw = [{"ip": "10.0.0.2", "available": False}]
        enriched = self.adapter._enrich(raw)
        self.assertEqual(enriched[0]["health"], "Unknown")
        self.assertEqual(enriched[0]["gpu_name"], "Unknown")

    def test_is_suitable_task_master_high_vram(self):
        worker = {"vram_total_mb": 16_384}
        self.assertTrue(self.adapter.is_suitable_task_master(worker))

    def test_is_suitable_task_master_low_vram(self):
        worker = {"vram_total_mb": 2_048}
        self.assertFalse(self.adapter.is_suitable_task_master(worker))

    def test_is_suitable_task_master_unknown_vram(self):
        """Unknown VRAM (0) should be allowed with a warning."""
        worker = {"vram_total_mb": 0}
        self.assertTrue(self.adapter.is_suitable_task_master(worker))

    def test_task_master_message_sufficient(self):
        worker = {"vram_total_mb": 8_192}
        msg = self.adapter.get_task_master_message(worker, model_vram_min_gb=6)
        self.assertIn("✓", msg)

    def test_task_master_message_insufficient(self):
        worker = {"vram_total_mb": 4_096}
        msg = self.adapter.get_task_master_message(worker, model_vram_min_gb=8)
        self.assertIn("⚠", msg)

    def test_task_master_message_unknown_vram(self):
        worker = {"vram_total_mb": 0}
        msg = self.adapter.get_task_master_message(worker, model_vram_min_gb=6)
        self.assertIn("unknown", msg.lower())

    def test_discover_comprehensive_delegates(self):
        with patch.object(
            self.adapter._backend,
            "discover_workers_comprehensive",
            return_value=[],
        ) as mock:
            result = self.adapter.discover_comprehensive()
            mock.assert_called_once()
            self.assertEqual(result, [])

    def test_discover_manual_delegates(self):
        with patch.object(
            self.adapter._backend,
            "discover_workers_manual",
            return_value=[],
        ) as mock:
            result = self.adapter.discover_manual()
            mock.assert_called_once()
            self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# model_downloader
# ---------------------------------------------------------------------------


class TestModelDownloader(unittest.TestCase):
    """Tests for ModelDownloader and MODELS catalogue."""

    def test_models_catalogue_structure(self):
        from backend_interface.model_downloader import MODELS

        self.assertGreater(len(MODELS), 0)
        for m in MODELS:
            for field in (
                "id",
                "name",
                "filename",
                "url",
                "vram_min_gb",
                "vram_rec_gb",
                "file_size_gb",
            ):
                self.assertIn(field, m, f"Model {m.get('id')} missing '{field}'")

    def test_exactly_one_recommended(self):
        from backend_interface.model_downloader import MODELS

        recommended = [m for m in MODELS if m.get("recommended")]
        self.assertEqual(len(recommended), 1)

    def test_verify_checksum_empty_skips(self):
        from backend_interface.model_downloader import ModelDownloader

        fd, path = tempfile.mkstemp(suffix=".gguf")
        tmp = Path(path)
        try:
            import os

            os.write(fd, b"dummy data")
            os.close(fd)
            self.assertTrue(ModelDownloader._verify_checksum(tmp, ""))
        finally:
            tmp.unlink(missing_ok=True)

    def test_verify_checksum_correct(self):
        import hashlib, os
        from backend_interface.model_downloader import ModelDownloader

        data = b"test content"
        expected = hashlib.sha256(data).hexdigest()
        fd, path = tempfile.mkstemp(suffix=".gguf")
        tmp = Path(path)
        try:
            os.write(fd, data)
            os.close(fd)
            self.assertTrue(ModelDownloader._verify_checksum(tmp, expected))
        finally:
            tmp.unlink(missing_ok=True)

    def test_verify_checksum_incorrect(self):
        import os
        from backend_interface.model_downloader import ModelDownloader

        fd, path = tempfile.mkstemp(suffix=".gguf")
        tmp = Path(path)
        try:
            os.write(fd, b"real data")
            os.close(fd)
            self.assertFalse(ModelDownloader._verify_checksum(tmp, "deadbeef" * 8))
        finally:
            tmp.unlink(missing_ok=True)

    def test_download_skips_existing_valid_file(self):
        """If a valid file already exists it should be returned without re-downloading."""
        from backend_interface.model_downloader import ModelDownloader

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            dl = ModelDownloader(tmp_dir)
            model = {
                "id": "test",
                "name": "Test",
                "filename": "test.gguf",
                "url": "http://example.com/test.gguf",
                "sha256": "",  # no checksum — always valid
            }
            # Create the file already
            (tmp_dir / "test.gguf").write_bytes(b"existing")
            with patch.object(dl, "_download_file") as mock_dl:
                result = dl.download(model)
                mock_dl.assert_not_called()
            self.assertEqual(result, tmp_dir / "test.gguf")
        finally:
            shutil.rmtree(tmp_dir)

    def test_download_raises_on_failure(self):
        from backend_interface.model_downloader import ModelDownloader, DownloadError

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            dl = ModelDownloader(tmp_dir)
            model = {
                "id": "test",
                "name": "Test",
                "filename": "bad.gguf",
                "url": "http://invalid.example.com/bad.gguf",
                "sha256": "",
            }
            with patch.object(
                dl, "_download_file", side_effect=ConnectionError("refused")
            ):
                with self.assertRaises(DownloadError):
                    dl.download(model)
        finally:
            shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# config_writer
# ---------------------------------------------------------------------------


class TestConfigWriter(unittest.TestCase):
    """Tests for ConfigWriter."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_llm_config(self):
        from backend_interface.config_writer import ConfigWriter

        writer = ConfigWriter(self.tmp)
        model_path = self.tmp / "models" / "model.gguf"
        model_info = {
            "id": "phi35_q4_k_m",
            "name": "Phi-3.5 Mini Q4_K_M",
            "vram_min_gb": 6,
            "vram_rec_gb": 8,
        }
        dest = writer.write_llm_config(model_path, model_info)
        self.assertTrue(dest.exists())
        cfg = json.loads(dest.read_text())
        self.assertEqual(cfg["model_id"], "phi35_q4_k_m")
        self.assertEqual(cfg["model_path"], str(model_path))
        self.assertEqual(cfg["vram_min_gb"], 6)
        self.assertEqual(cfg["backend"], "llama_cpp")

    def test_write_worker_registry(self):
        from backend_interface.config_writer import ConfigWriter

        writer = ConfigWriter(self.tmp)
        task_master = {
            "ip": "192.168.1.10",
            "port": 8090,
            "hostname": "master-node",
            "gpu_name": "RTX 5080",
            "vram_total_mb": 16_384,
            "health": "Healthy",
        }
        workers = [
            task_master,
            {
                "ip": "192.168.1.11",
                "port": 8090,
                "hostname": "worker-1",
                "gpu_name": "GTX 1080",
                "vram_total_mb": 8_192,
                "health": "Healthy",
            },
        ]
        dest = writer.write_worker_registry(workers, task_master)
        self.assertTrue(dest.exists())
        reg = json.loads(dest.read_text())
        self.assertEqual(reg["task_master"]["ip"], "192.168.1.10")
        self.assertEqual(len(reg["workers"]), 2)

    def test_config_dir_created_automatically(self):
        from backend_interface.config_writer import ConfigWriter

        new_dir = self.tmp / "fresh_install"
        writer = ConfigWriter(new_dir)
        self.assertTrue((new_dir / "config").exists())


# ---------------------------------------------------------------------------
# ConfigBootstrap  (§8 Corrected Config Model)
# ---------------------------------------------------------------------------


class TestConfigBootstrap(unittest.TestCase):
    """Tests for ConfigBootstrap — Step 4.5 atomic writer for phantom_config.json."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_creates_phantom_config_json(self):
        """write() must produce a phantom_config.json at the specified path."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        cb = ConfigBootstrap(dest)
        result = cb.write()
        self.assertTrue(dest.exists())
        self.assertEqual(result, dest)

    def test_written_config_has_required_top_level_keys(self):
        """phantom_config.json must contain all top-level keys from the schema."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        cfg = json.loads(dest.read_text())
        for key in (
            "controller",
            "ports",
            "worker",
            "execution_modes",
            "config_version",
            "written_at",
            "written_by_step",
        ):
            self.assertIn(key, cfg, f"Missing top-level key: {key!r}")

    def test_written_by_step_annotation_is_4_5(self):
        """written_by_step must be '4.5'."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        cfg = json.loads(dest.read_text())
        self.assertEqual(cfg["written_by_step"], "4.5")

    def test_controller_block_reflects_arguments(self):
        """The controller block must mirror the host/port/security arguments."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write(
            host="192.168.1.50",
            port=9090,
            security="basic",
            identity_fingerprint="aabbccdd",
        )
        cfg = json.loads(dest.read_text())
        ctrl = cfg["controller"]
        self.assertEqual(ctrl["host"], "192.168.1.50")
        self.assertEqual(ctrl["port"], 9090)
        self.assertEqual(ctrl["security"], "basic")
        self.assertEqual(ctrl["identity_fingerprint"], "aabbccdd")

    def test_required_ports_block_present(self):
        """ports block must contain controller_api, worker_http, discovery_udp."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        cfg = json.loads(dest.read_text())
        for key in ("controller_api", "worker_http", "discovery_udp"):
            self.assertIn(key, cfg["ports"], f"Missing port entry: {key!r}")

    def test_worker_readiness_defaults_present(self):
        """worker block must contain readiness probe defaults."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        cfg = json.loads(dest.read_text())
        for key in (
            "readiness_probe_interval_ms",
            "readiness_max_attempts",
            "readiness_attempt_timeout_ms",
        ):
            self.assertIn(key, cfg["worker"], f"Missing worker key: {key!r}")

    def test_atomic_write_uses_tmp_then_rename(self):
        """A .tmp file must not persist after write() completes."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        tmp_path = dest.with_suffix(".json.tmp")
        self.assertFalse(tmp_path.exists(), ".tmp file should not remain after write()")

    def test_existing_config_is_backed_up_before_overwrite(self):
        """A pre-existing phantom_config.json must be backed up, not silently clobbered."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        # Write an initial config
        dest.write_text('{"original": true}', encoding="utf-8")
        ConfigBootstrap(dest).write()
        # Original must be preserved as a .bak.<timestamp> file
        backups = list(self.tmp.glob("phantom_config.json.bak.*"))
        self.assertEqual(len(backups), 1, "Expected exactly one backup file")
        original = json.loads(backups[0].read_text())
        self.assertTrue(original.get("original"))

    def test_invalid_security_raises_value_error(self):
        """write() must raise ValueError for an unknown security level."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        with self.assertRaises(ValueError):
            ConfigBootstrap(dest).write(security="ultra-secret")

    def test_parent_directories_created_automatically(self):
        """write() must create missing parent directories."""
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "deep" / "nested" / "phantom_config.json"
        ConfigBootstrap(dest).write()
        self.assertTrue(dest.exists())

    def test_written_at_is_iso8601(self):
        """written_at must be an ISO 8601 UTC timestamp string."""
        import re
        from backend_interface.config_writer import ConfigBootstrap

        dest = self.tmp / "phantom_config.json"
        ConfigBootstrap(dest).write()
        cfg = json.loads(dest.read_text())
        ts = cfg["written_at"]
        self.assertIsInstance(ts, str)
        # Accept both offset-aware (±HH:MM) and Zulu (Z) formats.
        self.assertRegex(
            ts,
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            "written_at should start with YYYY-MM-DDTHH:MM:SS",
        )


# ---------------------------------------------------------------------------
# installer_driver
# ---------------------------------------------------------------------------


class TestInstallerDriver(unittest.TestCase):
    """Tests for InstallerDriver."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_stages_count(self):
        from backend_interface.installer_driver import INSTALL_STAGES

        self.assertEqual(len(INSTALL_STAGES), 7)

    def test_select_default_components(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        driver.select_default_components("all")
        # phantom_core is required and auto-added by validate_selection
        # other components depend on OS; at minimum socket_infrastructure should be there
        self.assertTrue(len(driver.component_manager.selected_components) > 0)

    def test_stage_0_creates_directories(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        ok = driver.run_stage(0)
        self.assertTrue(ok)
        self.assertTrue((self.tmp / "config").exists())
        self.assertTrue((self.tmp / "logs").exists())

    def test_stage_2_generates_configs(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        # Stage 0 must run first to create dirs
        driver.run_stage(0)
        ok = driver.run_stage(2)
        self.assertTrue(ok)
        self.assertTrue((self.tmp / "config" / "phantom_config.yaml").exists())

    def test_stage_6_saves_manifest(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        driver.run_stage(0)  # dirs needed for manifest path
        ok = driver.run_stage(6)
        self.assertTrue(ok)
        manifest = self.tmp / ".phantom_install_manifest.json"
        self.assertTrue(manifest.exists())

    def test_unknown_stage_returns_false(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        ok = driver.run_stage(999)
        self.assertFalse(ok)

    def test_log_callback_called(self):
        from backend_interface.installer_driver import InstallerDriver

        driver = InstallerDriver(install_dir=self.tmp)
        logs = []
        driver.run_stage(0, log_cb=logs.append)
        self.assertTrue(len(logs) > 0)

    def test_run_all_stages(self):
        from backend_interface.installer_driver import InstallerDriver
        from unittest.mock import patch

        driver = InstallerDriver(install_dir=self.tmp)
        driver.select_default_components("all")
        # Patch install_selected_components to avoid real git calls
        with patch.object(
            driver.component_manager,
            "install_selected_components",
            return_value=(list(driver.component_manager.selected_components), []),
        ):
            ok = driver.run_all_stages()
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# phantom_installer_api (integration)
# ---------------------------------------------------------------------------


class TestPhantomInstallerAPI(unittest.TestCase):
    """Integration tests for PhantomInstallerAPI."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_api(self):
        from integration.phantom_installer_api import PhantomInstallerAPI

        return PhantomInstallerAPI(self.tmp)

    def test_audit_log_created(self):
        api = self._make_api()
        log_file = self.tmp / "installation_audit.log"
        self.assertTrue(log_file.exists())

    def test_get_models_returns_catalogue(self):
        api = self._make_api()
        models = api.get_models()
        self.assertGreater(len(models), 0)
        self.assertIn("id", models[0])

    def test_run_system_scan_returns_structure(self):
        api = self._make_api()
        result = api.run_system_scan(ports=[19999])
        self.assertIn("ok", result)
        self.assertIn("checks", result)

    def test_prepare_installer(self):
        api = self._make_api()
        driver = api.prepare_installer(worker_configs=[], install_type="all")
        self.assertIsNotNone(driver)

    def test_run_stage_requires_prepare(self):
        from integration.phantom_installer_api import PhantomInstallerAPI

        api = PhantomInstallerAPI(self.tmp)
        with self.assertRaises(RuntimeError):
            api.run_installation_stage(0)

    def test_run_stage_after_prepare(self):
        api = self._make_api()
        api.prepare_installer()
        ok = api.run_installation_stage(0)  # create directories
        self.assertTrue(ok)

    def test_write_llm_config(self):
        api = self._make_api()
        model_path = self.tmp / "models" / "test.gguf"
        model_info = {
            "id": "phi35_q4_k_m",
            "name": "Phi-3.5 Mini Q4_K_M",
            "vram_min_gb": 6,
            "vram_rec_gb": 8,
        }
        dest = api.write_llm_config(model_path, model_info)
        self.assertTrue(dest.exists())

    def test_write_worker_registry(self):
        api = self._make_api()
        tm = {"ip": "10.0.0.1", "port": 8090, "gpu_name": "RTX 3090"}
        workers = [tm]
        dest = api.write_worker_registry(workers, tm)
        self.assertTrue(dest.exists())

    def test_audit_log_records_actions(self):
        api = self._make_api()
        api.run_system_scan(ports=[19999])
        log_file = self.tmp / "installation_audit.log"
        log_content = log_file.read_text()
        self.assertIn("system scan", log_content.lower())

    def test_discover_workers_skip(self):
        api = self._make_api()
        workers = api.discover_workers(mode="skip")
        self.assertEqual(workers, [])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
