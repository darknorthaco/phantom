#!/usr/bin/env python3
"""
Phantom Distributed Compute Fabric - Integrated System Entry Point
Runs the complete integrated system with socket infrastructure and security
"""

import asyncio
import uvicorn
import argparse
import sys
import os
import logging
from pathlib import Path

# Add the phantom_core directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "phantom_core"))


def main():
    parser = argparse.ArgumentParser(
        description="Phantom Integrated Distributed Controller"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument(
        "--socket-port", type=int, default=8081, help="Socket infrastructure port"
    )
    parser.add_argument(
        "--security",
        choices=["disabled", "basic", "enhanced", "enterprise"],
        default="basic",
        help="Security level",
    )
    parser.add_argument(
        "--enable-llm-taskmaster",
        action="store_true",
        help="Enable LLM Task Master (auto-assigns to best available GPU)",
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set environment variables for configuration
    os.environ["PHANTOM_HOST"] = args.host
    os.environ["PHANTOM_PORT"] = str(args.port)
    os.environ["PHANTOM_SOCKET_PORT"] = str(args.socket_port)
    os.environ["PHANTOM_SECURITY"] = args.security
    os.environ["PHANTOM_INTEGRATED"] = "true"
    os.environ["PHANTOM_LLM_TASKMASTER"] = str(args.enable_llm_taskmaster)

    print("🚀 Starting Phantom Integrated Distributed System")
    print("=" * 50)
    print(f"Controller: {args.host}:{args.port}")
    print(f"Socket Infrastructure: {args.host}:{args.socket_port}")
    print(f"Security Level: {args.security}")
    print(f"LLM Task Master: {'Enabled' if args.enable_llm_taskmaster else 'Disabled'}")
    print("=" * 50)

    # Start the integrated system
    asyncio.run(start_integrated_system(args.host, args.port, args.security, args))


async def start_integrated_system(host: str, port: int, security_level: str, args):
    """Start the complete integrated system"""

    # Start socket infrastructure
    socket_task = None
    if True:  # Always start socket infrastructure in integrated mode
        print("🔌 Starting socket infrastructure...")
        socket_task = asyncio.create_task(start_socket_infrastructure(args.socket_port))
        await asyncio.sleep(2)  # Give socket server time to start

    # Start LLM Task Master if enabled
    llm_task = None
    if args.enable_llm_taskmaster:
        print("🤖 Starting LLM Task Master...")
        llm_task = asyncio.create_task(start_llm_taskmaster(host, args.socket_port))
        await asyncio.sleep(2)  # Give LLM Task Master time to start

    # Start main controller
    print("🎯 Starting main controller...")
    controller_task = asyncio.create_task(
        start_main_controller(host, port, args.reload)
    )

    try:
        # Wait for all components
        tasks = [controller_task]
        if socket_task:
            tasks.append(socket_task)
        if llm_task:
            tasks.append(llm_task)

        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down integrated system...")

        # Cancel all tasks
        for task in [controller_task, socket_task, llm_task]:
            if task and not task.done():
                task.cancel()

        # Wait for graceful shutdown
        await asyncio.sleep(1)
        print("✅ Integrated system shutdown complete")


async def start_socket_infrastructure(socket_port: int):
    """Start the socket infrastructure"""
    try:
        from socket_infrastructure.hybrid_socket_server import HybridSocketServer

        server = HybridSocketServer(
            host=os.environ.get("PHANTOM_HOST", "127.0.0.1"), port=socket_port
        )
        await server.start()

    except ImportError:
        print("⚠️ Socket infrastructure not available, running without socket support")
    except Exception as e:
        print(f"❌ Socket infrastructure failed: {e}")


async def start_llm_taskmaster(controller_host: str, socket_port: int):
    """Start the LLM Task Master"""
    try:
        from llm_taskmaster.lightweight_llm_setup import LightweightLLMTaskMaster

        llm_taskmaster = LightweightLLMTaskMaster(controller_host, socket_port)
        await llm_taskmaster.initialize()

        # Keep running
        while llm_taskmaster.running:
            await asyncio.sleep(1)

    except ImportError:
        print("⚠️ LLM Task Master not available")
    except Exception as e:
        print(f"❌ LLM Task Master failed: {e}")


async def start_main_controller(host: str, port: int, reload: bool):
    """Start the main FastAPI controller"""
    try:
        # Import and start the enhanced controller
        from controller_api import app

        config = uvicorn.Config(
            "controller_api:app", host=host, port=port, reload=reload, log_level="info"
        )

        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        print(f"❌ Main controller failed: {e}")
        raise


if __name__ == "__main__":
    main()
