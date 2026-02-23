#!/usr/bin/env python3
"""
Phantom Distributed Compute Fabric - Main Controller Entry Point
Enhanced version with integrated capabilities
"""

import uvicorn
import argparse
import sys
import os
from pathlib import Path

# Add the phantom_core directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "phantom_core"))


def main():
    parser = argparse.ArgumentParser(description="Phantom Distributed Controller")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument(
        "--integrated", action="store_true", help="Start with socket infrastructure"
    )
    parser.add_argument(
        "--security",
        choices=["disabled", "basic", "enhanced", "enterprise"],
        default="basic",
        help="Security level",
    )
    parser.add_argument(
        "--tls-cert",
        default=os.getenv("PHANTOM_TLS_CERT", ""),
        help="Path to TLS certificate PEM file",
    )
    parser.add_argument(
        "--tls-key",
        default=os.getenv("PHANTOM_TLS_KEY", ""),
        help="Path to TLS private key PEM file",
    )

    args = parser.parse_args()

    # Set environment variables for configuration
    os.environ["PHANTOM_HOST"] = args.host
    os.environ["PHANTOM_PORT"] = str(args.port)
    os.environ["PHANTOM_SECURITY"] = args.security

    if args.integrated:
        print("🚀 Starting Phantom with integrated socket infrastructure...")
        os.environ["PHANTOM_INTEGRATED"] = "true"
        from run_integrated_phantom import start_integrated_system

        start_integrated_system(args.host, args.port, args.security)
    else:
        print("🎯 Starting Phantom controller (original mode)...")
        # Import and start the original FastAPI app
        from controller_api import app

        ssl_kwargs = {}
        if args.tls_cert and args.tls_key:
            ssl_kwargs["ssl_certfile"] = args.tls_cert
            ssl_kwargs["ssl_keyfile"] = args.tls_key
            print(f"🔒 TLS enabled (cert={args.tls_cert})")

        uvicorn.run(
            "controller_api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
            **ssl_kwargs,
        )


if __name__ == "__main__":
    main()
