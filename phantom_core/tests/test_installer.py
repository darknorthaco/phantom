#!/usr/bin/env python3
"""
Test suite for Phantom Installer
"""

import unittest
import tempfile
import shutil
import sys
from pathlib import Path

# Add installer to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "installer"))

from modules.system_check import SystemChecker  # noqa: E402
from modules.component_manager import ComponentManager  # noqa: E402
from modules.worker_discovery import WorkerDiscovery  # noqa: E402
from modules.socket_manager import SocketManager  # noqa: E402
from modules.ui_integration import UIIntegration  # noqa: E402
from modules.venv_setup import VenvSetup  # noqa: E402
from modules.config_generator import ConfigGenerator  # noqa: E402
from modules.manifest_manager import ManifestManager  # noqa: E402
from modules.uninstall_manager import UninstallManager  # noqa: E402


class TestSystemChecker(unittest.TestCase):
    """Test system requirements checker"""

    def setUp(self):
        self.checker = SystemChecker()

    def test_python_version_check(self):
        """Test Python version check"""
        result = self.checker.check_python_version((3, 8))
        self.assertTrue(result, "Python version should meet requirements")

    def test_os_capabilities_check(self):
        """Test OS capabilities check"""
        result = self.checker.check_os_capabilities()
        self.assertTrue(result, "OS should be supported")

    def test_disk_space_check(self):
        """Test disk space check"""
        result = self.checker.check_disk_space(min_gb=1.0)
        self.assertTrue(result, "Should have sufficient disk space")

    def test_virtual_env_capability(self):
        """Test virtual environment capability"""
        result = self.checker.check_virtual_env_capability()
        self.assertTrue(result, "Virtual environment should be available")

    def test_run_all_checks(self):
        """Test running all checks"""
        result = self.checker.run_all_checks()
        self.assertTrue(result, "All checks should pass")

        report = self.checker.get_report()
        self.assertIn("passed", report)
        self.assertIn("failed", report)
        self.assertIn("warnings", report)


class TestComponentManager(unittest.TestCase):
    """Test component manager"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ComponentManager(self.temp_dir, use_git=False)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_components(self):
        """Test listing components"""
        components = self.manager.list_components()
        self.assertGreater(len(components), 0)

        # Check that required components exist
        component_ids = [c["id"] for c in components]
        self.assertIn("phantom_core", component_ids)

    def test_component_selection(self):
        """Test component selection"""
        self.manager.select_component("phantom_core")
        self.assertIn("phantom_core", self.manager.selected_components)

        self.manager.deselect_component("phantom_core")
        self.assertNotIn("phantom_core", self.manager.selected_components)

    def test_get_component_info(self):
        """Test getting component info"""
        info = self.manager.get_component_info("phantom_core")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "Phantom Core")
        self.assertTrue(info["required"])

    def test_redblue_ui_repo_reference(self):
        """RedBlue UI is already included in the main repo (no external clone needed)"""
        info = self.manager.get_component_info("redblue_ui")
        self.assertIsNotNone(info)
        self.assertIsNone(
            info["repo"],
            "RedBlue UI should have repo=None since it is bundled in the main installation",
        )

    def test_create_directory_structure(self):
        """Test directory structure creation"""
        result = self.manager.create_directory_structure()
        self.assertTrue(result)

        # Check directories exist
        self.assertTrue((Path(self.temp_dir) / "config").exists())
        self.assertTrue((Path(self.temp_dir) / "logs").exists())
        self.assertTrue((Path(self.temp_dir) / "data").exists())


class TestWorkerDiscovery(unittest.TestCase):
    """Test worker discovery"""

    def setUp(self):
        self.discovery = WorkerDiscovery()

    def test_set_discovery_mode(self):
        """Test setting discovery mode"""
        self.discovery.set_discovery_mode("manual")
        self.assertEqual(self.discovery.mode, "manual")

        self.discovery.set_discovery_mode("comprehensive")
        self.assertEqual(self.discovery.mode, "comprehensive")

        self.discovery.set_discovery_mode("skip")
        self.assertEqual(self.discovery.mode, "skip")

    def test_invalid_mode(self):
        """Test invalid discovery mode"""
        with self.assertRaises(ValueError):
            self.discovery.set_discovery_mode("invalid")

    def test_get_local_network(self):
        """Test getting local network"""
        network = self.discovery.get_local_network()
        # May be None in some environments, so just check it doesn't crash
        if network:
            self.assertIsNotNone(network)


class TestSocketManager(unittest.TestCase):
    """Test socket manager"""

    def setUp(self):
        self.manager = SocketManager()

    def test_enable_disable(self):
        """Test enabling and disabling sockets"""
        self.assertFalse(self.manager.enabled)

        self.manager.enable()
        self.assertTrue(self.manager.enabled)

        self.manager.disable()
        self.assertFalse(self.manager.enabled)

    def test_configure(self):
        """Test socket configuration"""
        self.manager.configure(host="127.0.0.1", port=9000)
        self.assertEqual(self.manager.host, "127.0.0.1")
        self.assertEqual(self.manager.port, 9000)

    def test_get_config(self):
        """Test getting configuration"""
        self.manager.enable()
        self.manager.configure(port=9000)

        config = self.manager.get_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["port"], 9000)

    def test_validate_config(self):
        """Test configuration validation"""
        self.manager.enable()
        self.manager.configure(port=8081)

        valid, error = self.manager.validate_config()
        self.assertTrue(valid)
        self.assertIsNone(error)

        # Test invalid port
        self.manager.configure(port=99999)
        valid, error = self.manager.validate_config()
        self.assertFalse(valid)
        self.assertIsNotNone(error)


class TestUIIntegration(unittest.TestCase):
    """Test UI integration"""

    def setUp(self):
        self.ui = UIIntegration()

    def test_enable_disable(self):
        """Test enabling and disabling UI"""
        self.assertFalse(self.ui.enabled)

        self.ui.enable()
        self.assertTrue(self.ui.enabled)

        self.ui.disable()
        self.assertFalse(self.ui.enabled)

    def test_configure(self):
        """Test UI configuration"""
        self.ui.configure(host="127.0.0.1", port=4000)
        self.assertEqual(self.ui.host, "127.0.0.1")
        self.assertEqual(self.ui.port, 4000)

    def test_socket_integration(self):
        """Test socket integration toggle"""
        self.assertFalse(self.ui.socket_integration)

        self.ui.enable_socket_integration()
        self.assertTrue(self.ui.socket_integration)

        self.ui.disable_socket_integration()
        self.assertFalse(self.ui.socket_integration)


class TestVenvSetup(unittest.TestCase):
    """Test virtual environment setup"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.venv_setup = VenvSetup(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_venv_path(self):
        """Test getting venv path"""
        venv_path = self.venv_setup.get_venv_path()
        self.assertEqual(venv_path, self.temp_dir / "venvs" / "phantom")

    def test_create_venv(self):
        """Test creating virtual environment"""
        # This test creates an actual venv, which can be slow
        result = self.venv_setup.create_venv()
        self.assertTrue(result)

        # Check that venv was created
        venv_path = self.venv_setup.get_venv_path()
        self.assertTrue(venv_path.exists())


class TestConfigGenerator(unittest.TestCase):
    """Test configuration generator"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.generator = ConfigGenerator(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_phantom_config(self):
        """Test generating Phantom configuration"""
        config = self.generator.generate_phantom_config(
            controller_host="localhost", controller_port=8080, security_level="disabled"
        )

        self.assertIn("controller", config)
        self.assertEqual(config["controller"]["host"], "localhost")
        self.assertEqual(config["controller"]["port"], 8080)

    def test_generate_worker_config(self):
        """Test generating worker configuration"""
        config = self.generator.generate_worker_config(
            worker_id="worker-1",
            controller_host="localhost",
            controller_port=8080,
            worker_port=8090,
        )

        self.assertEqual(config["worker_id"], "worker-1")
        self.assertEqual(config["controller_host"], "localhost")
        self.assertEqual(config["worker_port"], 8090)

    def test_save_config(self):
        """Test saving configuration"""
        config = {"test": "value"}
        result = self.generator.save_config(config, "test_config.yaml", "yaml")
        self.assertTrue(result)

        # Check file exists
        config_file = self.temp_dir / "config" / "test_config.yaml"
        self.assertTrue(config_file.exists())


class TestManifestManager(unittest.TestCase):
    """Test installation manifest manager"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manifest = ManifestManager(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_manifest(self):
        """Test manifest creation"""
        self.assertIsNotNone(self.manifest.manifest)
        self.assertEqual(self.manifest.manifest["version"], "1.0")
        self.assertEqual(self.manifest.manifest["install_dir"], self.temp_dir)

    def test_add_component(self):
        """Test adding component to manifest"""
        self.manifest.add_component("test_comp", "Test Component")
        components = self.manifest.get_components()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["id"], "test_comp")
        self.assertEqual(components[0]["name"], "Test Component")

    def test_add_file(self):
        """Test tracking file"""
        test_file = "/path/to/file.txt"
        self.manifest.add_file(test_file)
        files = self.manifest.get_files()
        self.assertIn(test_file, files)

    def test_add_directory(self):
        """Test tracking directory"""
        test_dir = "/path/to/dir"
        self.manifest.add_directory(test_dir)
        dirs = self.manifest.get_directories()
        self.assertIn(test_dir, dirs)

    def test_add_service(self):
        """Test tracking service"""
        self.manifest.add_service(
            "phantom", "/etc/systemd/system/phantom.service", "systemd"
        )
        services = self.manifest.get_services()
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["name"], "phantom")

    def test_add_config_file(self):
        """Test tracking config file"""
        config_file = "/opt/phantom/config/phantom_config.yaml"
        self.manifest.add_config_file(config_file)
        configs = self.manifest.get_config_files()
        self.assertIn(config_file, configs)

    def test_save_and_load_manifest(self):
        """Test saving and loading manifest"""
        self.manifest.add_component("test_comp", "Test Component")
        self.manifest.add_file("/test/file.txt")

        # Save
        result = self.manifest.save_manifest()
        self.assertTrue(result)

        # Verify file exists
        manifest_path = Path(self.temp_dir) / ".phantom_install_manifest.json"
        self.assertTrue(manifest_path.exists())

        # Load in new instance
        manifest2 = ManifestManager(self.temp_dir)
        self.assertEqual(len(manifest2.get_components()), 1)
        self.assertIn("/test/file.txt", manifest2.get_files())

    def test_set_venv_path(self):
        """Test setting venv path"""
        venv_path = "/opt/phantom/venvs/phantom"
        self.manifest.set_venv_path(venv_path)
        self.assertEqual(self.manifest.get_venv_path(), venv_path)

    def test_has_manifest(self):
        """Test manifest existence check"""
        self.assertFalse(self.manifest.has_manifest())
        self.manifest.save_manifest()

        # Create new instance to check
        manifest2 = ManifestManager(self.temp_dir)
        self.assertTrue(manifest2.has_manifest())


class TestUninstallManager(unittest.TestCase):
    """Test uninstallation manager"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manifest = ManifestManager(self.temp_dir)
        self.uninstaller = UninstallManager(self.temp_dir, self.manifest)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_mode(self):
        """Test dry-run mode"""
        self.assertFalse(self.uninstaller.dry_run)
        self.uninstaller.set_dry_run(True)
        self.assertTrue(self.uninstaller.dry_run)

    def test_set_backup_dir(self):
        """Test setting backup directory"""
        backup_dir = "/tmp/backup"
        self.uninstaller.set_backup_dir(backup_dir)
        self.assertEqual(str(self.uninstaller.backup_dir), backup_dir)

    def test_remove_pid_files_dry_run(self):
        """Test removing PID files in dry-run mode"""
        # Create a test PID file
        pid_dir = Path(self.temp_dir) / "run"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_file = pid_dir / "test.pid"
        pid_file.write_text("12345")

        self.manifest.add_pid_file(str(pid_file))

        # Dry run should not remove file
        self.uninstaller.set_dry_run(True)
        result = self.uninstaller.remove_pid_files()
        self.assertTrue(result)
        self.assertTrue(pid_file.exists())

    def test_remove_pid_files_real(self):
        """Test actually removing PID files"""
        # Create a test PID file
        pid_dir = Path(self.temp_dir) / "run"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_file = pid_dir / "test.pid"
        pid_file.write_text("12345")

        self.manifest.add_pid_file(str(pid_file))

        # Real run should remove file
        self.uninstaller.set_dry_run(False)
        result = self.uninstaller.remove_pid_files()
        self.assertTrue(result)
        self.assertFalse(pid_file.exists())

    def test_backup_configs(self):
        """Test backing up configuration files"""
        # Create a test config file
        config_dir = Path(self.temp_dir) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "test_config.yaml"
        config_file.write_text("test: value")

        self.manifest.add_config_file(str(config_file))

        # Set backup directory
        backup_dir = Path(self.temp_dir) / "backup"
        self.uninstaller.set_backup_dir(str(backup_dir))

        # Backup
        result = self.uninstaller.backup_configs()
        self.assertTrue(result)

        # Check backup exists
        backup_file = backup_dir / "test_config.yaml"
        self.assertTrue(backup_file.exists())
        self.assertEqual(backup_file.read_text(), "test: value")

    def test_remove_directories_preserve_configs(self):
        """Test removing directories while preserving configs"""
        # Create subdirectories
        for subdir in ["venv", "logs", "tmp", "cache", "config"]:
            dir_path = Path(self.temp_dir) / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            (dir_path / "test.txt").write_text("test")

        # Remove with preserve_configs=True
        result = self.uninstaller.remove_directories(preserve_configs=True)
        self.assertTrue(result)

        # Check that venv, logs, tmp, cache are removed but config remains
        self.assertFalse((Path(self.temp_dir) / "venv").exists())
        self.assertFalse((Path(self.temp_dir) / "logs").exists())
        self.assertTrue((Path(self.temp_dir) / "config").exists())

    def test_remove_manifest(self):
        """Test removing manifest file"""
        # Save manifest
        self.manifest.save_manifest()
        manifest_path = Path(self.temp_dir) / ".phantom_install_manifest.json"
        self.assertTrue(manifest_path.exists())

        # Remove
        result = self.uninstaller.remove_manifest()
        self.assertTrue(result)
        self.assertFalse(manifest_path.exists())


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
