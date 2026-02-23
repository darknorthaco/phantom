#!/usr/bin/env python3
"""
Phantom Distributed Compute Fabric - Enhanced Edition
Setup script for installation and distribution
"""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="phantom-distributed-enhanced",
    version="2.0.0",
    author="Phantom Team",
    author_email="contact@phantom-distributed.com",
    description="Enhanced distributed compute fabric with AI-powered task routing and multi-GPU support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/darknorthaco/phantom-test",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "ai": [
            "torch>=2.0.0",
            "transformers>=4.30.0",
            "accelerate>=0.20.0",
        ],
        "grpc": [
            "grpcio>=1.54.0",
            "grpcio-tools>=1.54.0",
            "protobuf>=4.23.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "phantom-controller=phantom_core.controller_api:main",
            "phantom-worker=linux_worker.worker:main",
            "phantom-integrated=run_integrated_phantom:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json", "*.sh"],
        "phantom_protocol_schemas": ["*.proto"],
    },
)
