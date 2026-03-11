"""
Phantom Installer Discovery Client — §3 / §9 Integration.

Sends UDP broadcast + unicast to discover workers, parses SignedManifest
responses, verifies signatures, and returns results for the installer's
Worker Selection Ceremony.
"""

import json
import logging
import socket
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

DISCOVERY_PORT = 8095
DISCOVER_PAYLOAD = b"PHANTOM_DISCOVER_WORKERS"
DEFAULT_TIMEOUT_MS = 1500


@dataclass
class DiscoveredWorker:
    """Worker discovered via UDP with verification status."""

    worker_id: str
    host: str
    port: int
    gpu_info: dict = field(default_factory=dict)
    source_ip: str = ""
    signature_verified: bool = False
    public_key_b64: str = ""
    fingerprint: str = ""

    def registration_host(self) -> str:
        if self.host in ("0.0.0.0", ""):
            return self.source_ip
        return self.host


class InstallerDiscoveryClient:
    """§9 — Sends UDP discover requests and verifies SignedManifest responses."""

    def __init__(self, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.timeout_ms = timeout_ms

    def discover(
        self,
        broadcast_addrs: Optional[List[str]] = None,
        include_localhost: bool = True,
    ) -> List[DiscoveredWorker]:
        """Run full discovery: unicast to localhost + broadcast on each subnet.

        Deduplicates by worker_id.
        """
        seen: set = set()
        results: List[DiscoveredWorker] = []

        if include_localhost:
            for w in self._collect("127.0.0.1", broadcast=False):
                if w.worker_id not in seen:
                    seen.add(w.worker_id)
                    results.append(w)

        for addr in broadcast_addrs or []:
            for w in self._collect(addr, broadcast=True):
                if w.worker_id not in seen:
                    seen.add(w.worker_id)
                    results.append(w)

        return results

    def _collect(self, addr: str, broadcast: bool) -> List[DiscoveredWorker]:
        """Send a single discovery request and collect responses."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if broadcast:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.timeout_ms / 1000.0)
            sock.bind(("0.0.0.0", 0))
        except OSError as e:
            logger.warning("Discovery socket error: %s", e)
            return []

        target = (addr, DISCOVERY_PORT)
        try:
            sock.sendto(DISCOVER_PAYLOAD, target)
        except OSError:
            sock.close()
            return []

        workers: List[DiscoveredWorker] = []
        buf_size = 4096
        while True:
            try:
                data, remote = sock.recvfrom(buf_size)
                source_ip = remote[0]
                w = self._parse_response(data, source_ip)
                if w is not None:
                    workers.append(w)
            except socket.timeout:
                break
            except Exception as e:
                logger.debug("Discovery recv: %s", e)
                break

        sock.close()
        return workers

    def _parse_response(
        self, data: bytes, source_ip: str
    ) -> Optional[DiscoveredWorker]:
        """Parse and verify a single manifest response."""
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            return None

        # Try to use the full SignedManifest verification path
        try:
            from phantom_core.discovery import parse_and_verify

            manifest = parse_and_verify(raw)
            if manifest is None:
                return None
            return DiscoveredWorker(
                worker_id=manifest.worker_id,
                host=manifest.address,
                port=json.loads(raw).get("port", 0),
                gpu_info=manifest.capabilities,
                source_ip=source_ip,
                signature_verified=manifest.signature_verified or False,
                public_key_b64=manifest.public_key_b64,
            )
        except ImportError:
            pass

        # Fallback: parse as legacy unsigned manifest
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        msg_type = obj.get("type", obj.get("msg_type", ""))
        if msg_type != "WORKER_MANIFEST":
            return None
        worker_id = obj.get("worker_id", "")
        if not worker_id:
            return None

        return DiscoveredWorker(
            worker_id=worker_id,
            host=obj.get("host", obj.get("address", "")),
            port=obj.get("port", 0),
            gpu_info=obj.get("gpu_info", obj.get("capabilities", {})),
            source_ip=source_ip,
            signature_verified=False,  # unsigned = unverified
        )
