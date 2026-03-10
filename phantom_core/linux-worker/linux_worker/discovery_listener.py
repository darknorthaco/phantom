"""
Phantom worker discovery listener. Responds to DISCOVER_WORKERS UDP broadcast
with a signed manifest. Workers self-identify; no controller host probing.
"""

import json
import logging
import socket
import threading

DISCOVERY_PORT = 8095
DISCOVER_PAYLOAD = b"PHANTOM_DISCOVER_WORKERS"

logger = logging.getLogger(__name__)


def run_discovery_listener(worker_id: str, host: str, port: int, gpu_info: dict) -> None:
    """Run UDP listener on DISCOVERY_PORT. Respond to DISCOVER_WORKERS with manifest."""

    def listen() -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
            sock.settimeout(1.0)
            logger.info("Discovery listener on 0.0.0.0:%s", DISCOVERY_PORT)
        except OSError as e:
            logger.warning("Discovery listener failed to bind: %s", e)
            return

        while True:
            try:
                data, addr = sock.recvfrom(512)
                if data == DISCOVER_PAYLOAD:
                    manifest = {
                        "type": "WORKER_MANIFEST",
                        "worker_id": worker_id,
                        "host": host,
                        "port": port,
                        "gpu_info": gpu_info or {},
                    }
                    payload = json.dumps(manifest).encode("utf-8")
                    sock.sendto(payload, addr)
                    logger.debug("Sent manifest to %s", addr)
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug("Discovery recv: %s", e)

    t = threading.Thread(target=listen, daemon=True)
    t.start()
