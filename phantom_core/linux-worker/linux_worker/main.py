#!/usr/bin/env python3
"""
Phantom Linux Worker Main Entry Point
"""

import asyncio
import argparse
import json
import logging
import signal
import sys
from pathlib import Path

from .worker import PhantomLinuxWorker, create_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load worker configuration from JSON file"""
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load config from %s: %s", config_path, e)
        raise


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Phantom Linux Worker")
    parser.add_argument(
        "--config", required=True, help="Path to worker configuration file"
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    config = load_config(args.config)
    logger.info("Loaded configuration: %s", config.get("worker_id", "unknown"))

    worker = create_worker(config)

    def signal_handler(signum, frame):
        logger.info("Received signal %s, initiating shutdown...", signum)
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
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
        logger.info(
            "Starting worker %s on port %s", worker.worker_id, worker.worker_port
        )
        await server.serve()
    except Exception as e:
        logger.error("Worker failed: %s", e)
        return 1
    finally:
        await worker.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
