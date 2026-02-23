"""
Tests for security defaults and CORS settings improvements.
Validates that default configurations follow security best practices.
"""

import unittest
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSecurityDefaults(unittest.TestCase):
    """Test that security defaults are set to safe values"""

    def test_run_py_default_host(self):
        """run.py should default to 127.0.0.1 (not 0.0.0.0)"""
        with open(os.path.join(os.path.dirname(__file__), "..", "run.py")) as f:
            content = f.read()
        self.assertIn('default="127.0.0.1"', content)
        self.assertNotIn('default="0.0.0.0"', content)

    def test_run_py_default_security(self):
        """run.py should default to 'basic' security (not 'disabled')"""
        with open(os.path.join(os.path.dirname(__file__), "..", "run.py")) as f:
            content = f.read()
        self.assertIn('default="basic"', content)

    def test_run_py_security_choices(self):
        """run.py security choices should match SecurityLevel enum values"""
        with open(os.path.join(os.path.dirname(__file__), "..", "run.py")) as f:
            content = f.read()
        for level in ["disabled", "basic", "enhanced", "enterprise"]:
            self.assertIn(level, content)

    def test_run_integrated_default_host(self):
        """run_integrated_phantom.py should default to 127.0.0.1"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "run_integrated_phantom.py")
        ) as f:
            content = f.read()
        self.assertIn('default="127.0.0.1"', content)
        self.assertNotIn('default="0.0.0.0"', content)

    def test_run_integrated_default_security(self):
        """run_integrated_phantom.py should default to 'basic' security"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "run_integrated_phantom.py")
        ) as f:
            content = f.read()
        self.assertIn('default="basic"', content)

    def test_start_script_default_host(self):
        """start_complete_phantom.sh should default to 127.0.0.1"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "start_complete_phantom.sh")
        ) as f:
            content = f.read()
        self.assertIn("CONTROLLER_HOST:-127.0.0.1", content)
        self.assertNotIn("CONTROLLER_HOST:-0.0.0.0", content)

    def test_start_script_default_security(self):
        """start_complete_phantom.sh should default to 'basic' security"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "start_complete_phantom.sh")
        ) as f:
            content = f.read()
        self.assertIn("SECURITY_LEVEL:-basic", content)
        self.assertNotIn("SECURITY_LEVEL:-disabled", content)

    def test_start_script_set_u(self):
        """start_complete_phantom.sh should use set -u for safety"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "start_complete_phantom.sh")
        ) as f:
            content = f.read()
        self.assertIn("set -u", content)


class TestCORSSettings(unittest.TestCase):
    """Test that CORS configuration follows security best practices"""

    def test_no_wildcard_origins(self):
        """controller_api.py should not use allow_origins=['*']"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "controller_api.py"
            )
        ) as f:
            content = f.read()
        self.assertNotIn('allow_origins=["*"]', content)

    def test_cors_origins_configurable(self):
        """CORS origins should be configurable via PHANTOM_CORS_ORIGINS env var"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "controller_api.py"
            )
        ) as f:
            content = f.read()
        self.assertIn("PHANTOM_CORS_ORIGINS", content)

    def test_cors_origins_parsing(self):
        """Test CORS_ORIGINS parsing from environment variable"""
        # Simulate how the module parses the env var
        test_origins = "http://localhost:3000,http://example.com"
        origins = [o.strip() for o in test_origins.split(",") if o.strip()]
        self.assertEqual(origins, ["http://localhost:3000", "http://example.com"])

    def test_cors_methods_restricted(self):
        """CORS should not use allow_methods=['*']"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "controller_api.py"
            )
        ) as f:
            content = f.read()
        self.assertNotIn('allow_methods=["*"]', content)

    def test_cors_headers_restricted(self):
        """CORS should not use allow_headers=['*']"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "controller_api.py"
            )
        ) as f:
            content = f.read()
        self.assertNotIn('allow_headers=["*"]', content)


class TestBindAddresses(unittest.TestCase):
    """Test that default bind addresses are localhost"""

    def test_controller_api_main_block(self):
        """controller_api.py __main__ should bind to 127.0.0.1"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "controller_api.py"
            )
        ) as f:
            content = f.read()
        self.assertIn('host="127.0.0.1"', content)

    def test_socket_integration_default(self):
        """socket_integration.py SocketManager should bind to 127.0.0.1"""
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "phantom_core", "socket_integration.py"
            )
        ) as f:
            content = f.read()
        # The default in websockets.serve should be 127.0.0.1
        self.assertIn('"127.0.0.1"', content)

    def test_hybrid_socket_server_default(self):
        """hybrid_socket_server.py should default to 127.0.0.1"""
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "socket_infrastructure",
                "hybrid_socket_server.py",
            )
        ) as f:
            content = f.read()
        self.assertIn('host: str = "127.0.0.1"', content)


class TestDependencies(unittest.TestCase):
    """Test that requirements.txt has correct dependencies"""

    def test_no_flask_dependency(self):
        """requirements.txt should not include flask (FastAPI is used)"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        ) as f:
            content = f.read()
        # Check no flask line exists
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                self.assertFalse(
                    stripped.lower().startswith("flask"),
                    f"Flask should not be in requirements.txt, found: {stripped}",
                )

    def test_fastapi_dependency(self):
        """requirements.txt should include fastapi"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        ) as f:
            content = f.read()
        self.assertIn("fastapi", content)

    def test_uvicorn_dependency(self):
        """requirements.txt should include uvicorn"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        ) as f:
            content = f.read()
        self.assertIn("uvicorn", content)

    def test_httpx_dependency(self):
        """requirements.txt should include httpx"""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        ) as f:
            content = f.read()
        self.assertIn("httpx", content)


class TestSecurityManagerDefaults(unittest.TestCase):
    """Test SecurityManager configuration defaults"""

    def test_basic_level_enables_api_keys(self):
        """Basic security level should enable API keys"""
        from security_framework.integrated_security import SecurityManager

        manager = SecurityManager("basic")
        self.assertTrue(manager.config.api_keys_enabled)

    def test_basic_level_enables_rate_limiting(self):
        """Basic security level should enable rate limiting"""
        from security_framework.integrated_security import SecurityManager

        manager = SecurityManager("basic")
        self.assertTrue(manager.config.rate_limiting_enabled)

    def test_basic_level_enables_audit_logging(self):
        """Basic security level should enable audit logging"""
        from security_framework.integrated_security import SecurityManager

        manager = SecurityManager("basic")
        self.assertTrue(manager.config.audit_logging_enabled)

    def test_disabled_level_all_off(self):
        """Disabled security level should disable everything"""
        from security_framework.integrated_security import SecurityManager

        manager = SecurityManager("disabled")
        self.assertFalse(manager.config.api_keys_enabled)
        self.assertFalse(manager.config.rate_limiting_enabled)
        self.assertFalse(manager.config.audit_logging_enabled)


if __name__ == "__main__":
    unittest.main()
