import tempfile
import unittest
from pathlib import Path

from phantom_next import validate_tls_policy


class SecurityPolicyTests(unittest.TestCase):
    def test_wan_requires_tls(self) -> None:
        with self.assertRaises(ValueError):
            validate_tls_policy(wan_mode=True, tls_enabled=False)

    def test_tls_requires_existing_files(self) -> None:
        with self.assertRaises(ValueError):
            validate_tls_policy(
                wan_mode=False,
                tls_enabled=True,
                tls_cert_path="missing-cert.pem",
                tls_key_path="missing-key.pem",
            )

    def test_tls_accepts_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cert = Path(tmp) / "cert.pem"
            key = Path(tmp) / "key.pem"
            cert.write_text("cert", encoding="utf-8")
            key.write_text("key", encoding="utf-8")

            validate_tls_policy(
                wan_mode=True,
                tls_enabled=True,
                tls_cert_path=str(cert),
                tls_key_path=str(key),
            )


if __name__ == "__main__":
    unittest.main()
