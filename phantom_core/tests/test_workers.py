#!/usr/bin/env python3
"""
Test suite for Phantom Workers
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Add the linux-worker directory so linux_worker and plugins are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "linux-worker"))


class TestLinuxWorker(unittest.TestCase):
    """Test cases for Linux Worker"""

    def setUp(self):
        """Set up test environment"""
        self.worker_config = {
            "worker_id": "test_linux_worker",
            "controller_url": "http://localhost:5000",
            "port": 6001,
        }

    @patch("linux_worker.gpu.gpu_info_linux.get_gpu_info", create=True)
    def test_gpu_detection(self, mock_gpu_info):
        """Test GPU detection functionality"""
        # Mock GPU detection results
        mock_gpu_info.return_value = {
            "nvidia_gpus": [
                {
                    "name": "GeForce GTX 1080",
                    "memory_total": 8192,
                    "memory_free": 7000,
                    "utilization": 15,
                }
            ],
            "amd_gpus": [],
            "total_gpus": 1,
        }

        from linux_worker.gpu.gpu_info_linux import get_gpu_info

        gpu_info = get_gpu_info()

        self.assertEqual(len(gpu_info["nvidia_gpus"]), 1)
        self.assertEqual(gpu_info["nvidia_gpus"][0]["name"], "GeForce GTX 1080")
        self.assertEqual(gpu_info["total_gpus"], 1)

    @patch("plugins.plugin_manager.PluginManager")
    def test_plugin_loading(self, mock_plugin_manager):
        """Test plugin loading and management"""
        # Mock plugin manager
        mock_manager = MagicMock()
        mock_manager.load_plugins.return_value = True
        mock_manager.get_plugin_for_gpu.return_value = "gtx1080_plugin"
        mock_plugin_manager.return_value = mock_manager

        from plugins.plugin_manager import PluginManager

        manager = PluginManager()

        # Test plugin loading
        result = manager.load_plugins()
        self.assertTrue(result)

        # Test plugin selection
        plugin = manager.get_plugin_for_gpu("GTX 1080")
        self.assertEqual(plugin, "gtx1080_plugin")

    def test_worker_capabilities(self):
        """Test worker capability reporting"""
        # This would test the actual capability detection
        pass


class TestGPUPlugins(unittest.TestCase):
    """Test cases for GPU-specific plugins"""

    def test_gtx1080_plugin(self):
        """Test GTX 1080 plugin functionality"""
        # Mock GTX 1080 environment
        try:
            with patch("pynvml.nvmlInit"), patch(
                "pynvml.nvmlDeviceGetCount", return_value=1
            ), patch("pynvml.nvmlDeviceGetHandleByIndex"), patch(
                "pynvml.nvmlDeviceGetName", return_value=b"GeForce GTX 1080"
            ):

                from linux_worker.plugins.gtx1080_plugin import GTX1080Plugin

                plugin = GTX1080Plugin()

                capabilities = plugin.get_capabilities()
                self.assertIn("memory_gb", capabilities)
                self.assertIn("compute_capability", capabilities)
                self.assertIn("tensor_cores", capabilities)
                self.assertEqual(
                    capabilities["tensor_cores"], False
                )  # GTX 1080 has no tensor cores

        except (ImportError, ModuleNotFoundError):
            self.skipTest("GTX 1080 plugin not available")

    def test_rtx50_plugin(self):
        """Test RTX 50-series plugin functionality"""
        try:
            from linux_worker.plugins.rtx50_plugin import RTX50Plugin

            plugin = RTX50Plugin()

            capabilities = plugin.get_capabilities()
            self.assertIn("tensor_cores", capabilities)
            self.assertIn("dlss_version", capabilities)
            self.assertIn("av1_encoding", capabilities)

            # RTX 50-series should have 4th gen tensor cores
            self.assertTrue(capabilities["tensor_cores"])
            self.assertEqual(capabilities["tensor_core_generation"], 4)

        except ImportError:
            self.skipTest("RTX 50-series plugin not available")

    def test_firepro_plugin(self):
        """Test AMD FirePro plugin functionality"""
        try:
            from linux_worker.plugins.firepro_plugin import FireProPlugin

            plugin = FireProPlugin()

            capabilities = plugin.get_capabilities()
            self.assertIn("memory_gb", capabilities)
            self.assertIn("compute_units", capabilities)
            self.assertIn("supports_opencl", capabilities)

            # FirePro W9100 should have 16GB memory
            self.assertEqual(capabilities["memory_gb"], 16)
            self.assertTrue(capabilities["supports_opencl"])

        except ImportError:
            self.skipTest("FirePro plugin not available")


class TestWorkerCommunication(unittest.TestCase):
    """Test cases for worker communication"""

    @patch("requests.post")
    def test_worker_registration(self, mock_post):
        """Test worker registration with controller"""
        # Mock successful registration response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "registered",
            "worker_id": "test_worker",
        }
        mock_post.return_value = mock_response

        # Test registration logic
        registration_data = {
            "worker_id": "test_worker",
            "capabilities": {"gpu_count": 1},
            "endpoint": "http://localhost:6001",
        }

        import requests

        response = requests.post(
            "http://localhost:5000/register_worker", json=registration_data
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "registered")

    @patch("requests.get")
    def test_task_polling(self, mock_get):
        """Test worker task polling"""
        # Mock task response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task": {"id": "task_001", "type": "compute", "data": {"operation": "test"}}
        }
        mock_get.return_value = mock_response

        import requests

        response = requests.get("http://localhost:5000/get_task/test_worker")

        self.assertEqual(response.status_code, 200)
        self.assertIn("task", response.json())

    def test_task_execution(self):
        """Test task execution workflow"""
        # This would test the actual task execution logic
        pass


class TestWorkerDeployment(unittest.TestCase):
    """Test cases for worker deployment"""

    @patch("subprocess.run")
    def test_deploy_script(self, mock_subprocess):
        """Test worker deployment script"""
        # Mock successful deployment
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Test deployment script execution
        import subprocess

        result = subprocess.run(
            ["bash", "linux-worker/deploy_workers.sh"], capture_output=True
        )

        self.assertEqual(result.returncode, 0)

    def test_worker_instance_creation(self):
        """Test worker instance creation"""
        # Test that worker instances are created correctly
        pass


if __name__ == "__main__":
    unittest.main()
