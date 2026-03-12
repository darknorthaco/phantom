#!/usr/bin/env python3
"""
Phantom Windows Worker Main Entry Point
Windows-safe: SIGINT (Ctrl+C), KeyboardInterrupt. No Linux-only syscalls.
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

from .worker import PhantomWindowsWorker, create_worker
from .utils.config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Phantom Windows Worker")
    parser.add_argument("--config", required=True, help="Path to worker configuration file")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    config = load_config(args.config)
    logger.info("Loaded configuration: %s", config.get("worker_id", "unknown"))

    worker = create_worker(config)

    def signal_handler(signum: int, frame) -> None:
        logger.info("Received signal %s, initiating shutdown...", signum)
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.initialize()
        if not await worker.register_with_controller():
            logger.error("Failed to register with controller")
            return 1
        await worker.start_background_tasks()

        import uvicorn
        uvicorn_config = uvicorn.Config(
            worker.app,
            host="0.0.0.0",
            port=worker.worker_port,
            log_level=args.log_level.lower(),
        )
        server = uvicorn.Server(uvicorn_config)
        logger.info("Starting worker %s on port %s", worker.worker_id, worker.worker_port)
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down")
    except Exception as e:
        logger.error("Worker failed: %s", e)
        return 1
    finally:
        await worker.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
