"""
GPU Detection and Information for Linux Systems
Supports NVIDIA (CUDA) and AMD (ROCm) GPUs
"""

import subprocess
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
import re

logger = logging.getLogger(__name__)


class GPUDetector:
    """Detects and provides information about available GPUs on Linux"""

    def __init__(self):
        self.nvidia_available = False
        self.amd_available = False
        self.detected_gpus = []

    async def detect_gpu(self) -> Optional[Dict[str, Any]]:
        """Detect the primary GPU for this worker"""
        try:
            # Check for NVIDIA GPUs first
            nvidia_gpus = await self.detect_nvidia_gpus()
            if nvidia_gpus:
                self.nvidia_available = True
                self.detected_gpus.extend(nvidia_gpus)
                return nvidia_gpus[0]  # Return primary NVIDIA GPU

            # Check for AMD GPUs
            amd_gpus = await self.detect_amd_gpus()
            if amd_gpus:
                self.amd_available = True
                self.detected_gpus.extend(amd_gpus)
                return amd_gpus[0]  # Return primary AMD GPU

            logger.warning("No compatible GPUs detected")
            return None

        except Exception as e:
            logger.error(f"GPU detection failed: {e}")
            return None

    async def detect_nvidia_gpus(self) -> List[Dict[str, Any]]:
        """Detect NVIDIA GPUs using nvidia-smi"""
        try:
            # Check if nvidia-smi is available
            result = await self.run_command(["nvidia-smi", "--version"])
            if result.returncode != 0:
                logger.debug("nvidia-smi not available")
                return []

            # Get GPU information in JSON format
            result = await self.run_command(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.free,memory.used,utilization.gpu,driver_version,compute_cap",
                    "--format=csv,noheader,nounits",
                ]
            )

            if result.returncode != 0:
                logger.warning("Failed to query NVIDIA GPU information")
                return []

            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = [part.strip() for part in line.split(",")]
                    if len(parts) >= 8:
                        gpu_info = {
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_total": int(parts[2]),
                            "memory_free": int(parts[3]),
                            "memory_used": int(parts[4]),
                            "utilization": float(parts[5]),
                            "driver_version": parts[6],
                            "compute_capability": parts[7],
                            "vendor": "NVIDIA",
                            "type": "CUDA",
                        }
                        gpus.append(gpu_info)
                        logger.info(
                            f"Detected NVIDIA GPU: {gpu_info['name']} ({gpu_info['memory_total']}MB)"
                        )

            return gpus

        except Exception as e:
            logger.warning(f"NVIDIA GPU detection failed: {e}")
            return []

    async def detect_amd_gpus(self) -> List[Dict[str, Any]]:
        """Detect AMD GPUs using rocm-smi or lspci"""
        try:
            # Try rocm-smi first
            rocm_gpus = await self.detect_amd_rocm()
            if rocm_gpus:
                return rocm_gpus

            # Fallback to lspci detection
            return await self.detect_amd_lspci()

        except Exception as e:
            logger.warning(f"AMD GPU detection failed: {e}")
            return []

    async def detect_amd_rocm(self) -> List[Dict[str, Any]]:
        """Detect AMD GPUs using rocm-smi"""
        try:
            # Check if rocm-smi is available
            result = await self.run_command(["rocm-smi", "--version"])
            if result.returncode != 0:
                logger.debug("rocm-smi not available")
                return []

            # Get GPU information
            result = await self.run_command(
                ["rocm-smi", "--showid", "--showproductname", "--showmeminfo", "vram"]
            )
            if result.returncode != 0:
                return []

            gpus = []
            current_gpu = {}

            for line in result.stdout.split("\n"):
                line = line.strip()
                if "GPU[" in line and "]:" in line:
                    # New GPU entry
                    if current_gpu:
                        gpus.append(current_gpu)

                    gpu_match = re.search(r"GPU\[(\d+)\]", line)
                    if gpu_match:
                        current_gpu = {
                            "index": int(gpu_match.group(1)),
                            "vendor": "AMD",
                            "type": "ROCm",
                        }

                elif "Card series:" in line:
                    current_gpu["name"] = line.split(":", 1)[1].strip()
                elif "VRAM Total Memory (B):" in line:
                    memory_bytes = int(line.split(":", 1)[1].strip())
                    current_gpu["memory_total"] = memory_bytes // (
                        1024 * 1024
                    )  # Convert to MB
                elif "VRAM Total Used Memory (B):" in line:
                    used_bytes = int(line.split(":", 1)[1].strip())
                    current_gpu["memory_used"] = used_bytes // (
                        1024 * 1024
                    )  # Convert to MB
                    if "memory_total" in current_gpu:
                        current_gpu["memory_free"] = (
                            current_gpu["memory_total"] - current_gpu["memory_used"]
                        )

            # Add the last GPU
            if current_gpu:
                gpus.append(current_gpu)

            # Set default values for missing fields
            for gpu in gpus:
                gpu.setdefault("utilization", 0.0)
                gpu.setdefault("driver_version", "unknown")
                gpu.setdefault("compute_capability", "unknown")
                gpu.setdefault(
                    "memory_free",
                    gpu.get("memory_total", 0) - gpu.get("memory_used", 0),
                )

                logger.info(
                    f"Detected AMD GPU: {gpu.get('name', 'Unknown')} ({gpu.get('memory_total', 0)}MB)"
                )

            return gpus

        except Exception as e:
            logger.warning(f"ROCm GPU detection failed: {e}")
            return []

    async def detect_amd_lspci(self) -> List[Dict[str, Any]]:
        """Detect AMD GPUs using lspci as fallback"""
        try:
            result = await self.run_command(["lspci", "-nn"])
            if result.returncode != 0:
                return []

            gpus = []
            gpu_index = 0

            for line in result.stdout.split("\n"):
                if "VGA compatible controller" in line and (
                    "AMD" in line or "ATI" in line
                ):
                    # Extract GPU name
                    name_match = re.search(r"controller: (.+?) \[", line)
                    gpu_name = name_match.group(1) if name_match else "AMD GPU"

                    # Create basic GPU info (limited information available via lspci)
                    gpu_info = {
                        "index": gpu_index,
                        "name": gpu_name,
                        "memory_total": 16000,  # Default for FirePro W9100
                        "memory_free": 15000,  # Estimate
                        "memory_used": 1000,  # Estimate
                        "utilization": 0.0,
                        "driver_version": "unknown",
                        "compute_capability": "unknown",
                        "vendor": "AMD",
                        "type": "OpenCL",
                    }

                    # Specific handling for known cards
                    if "FirePro W9100" in gpu_name:
                        gpu_info.update(
                            {
                                "memory_total": 16000,
                                "memory_free": 15000,
                                "compute_capability": "GCN 2.0",
                            }
                        )

                    gpus.append(gpu_info)
                    gpu_index += 1

                    logger.info(f"Detected AMD GPU (lspci): {gpu_name}")

            return gpus

        except Exception as e:
            logger.warning(f"lspci GPU detection failed: {e}")
            return []

    async def get_current_utilization(self) -> Optional[Dict[str, Any]]:
        """Get current GPU utilization and memory usage"""
        try:
            if self.nvidia_available:
                return await self.get_nvidia_utilization()
            elif self.amd_available:
                return await self.get_amd_utilization()

            return None

        except Exception as e:
            logger.warning(f"Failed to get GPU utilization: {e}")
            return None

    async def get_nvidia_utilization(self) -> Optional[Dict[str, Any]]:
        """Get NVIDIA GPU utilization"""
        try:
            result = await self.run_command(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.free,memory.used,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ]
            )

            if result.returncode != 0:
                return None

            lines = result.stdout.strip().split("\n")
            if lines and lines[0].strip():
                parts = [part.strip() for part in lines[0].split(",")]
                if len(parts) >= 3:
                    return {
                        "memory_free": int(parts[0]),
                        "memory_used": int(parts[1]),
                        "utilization": float(parts[2]),
                        "temperature": float(parts[3]) if len(parts) > 3 else 0.0,
                    }

            return None

        except Exception as e:
            logger.warning(f"Failed to get NVIDIA utilization: {e}")
            return None

    async def get_amd_utilization(self) -> Optional[Dict[str, Any]]:
        """Get AMD GPU utilization"""
        try:
            # Try rocm-smi for utilization
            result = await self.run_command(["rocm-smi", "--showuse", "--showmemuse"])
            if result.returncode == 0:
                # Parse rocm-smi output
                utilization = 0.0
                memory_used_percent = 0.0

                for line in result.stdout.split("\n"):
                    if "GPU use (%)" in line:
                        match = re.search(r"(\d+(?:\.\d+)?)", line)
                        if match:
                            utilization = float(match.group(1))
                    elif "GPU memory use (%)" in line:
                        match = re.search(r"(\d+(?:\.\d+)?)", line)
                        if match:
                            memory_used_percent = float(match.group(1))

                return {
                    "utilization": utilization,
                    "memory_used_percent": memory_used_percent,
                }

            # Fallback to basic info
            return {
                "utilization": 0.0,
                "memory_used_percent": 10.0,  # Conservative estimate
            }

        except Exception as e:
            logger.warning(f"Failed to get AMD utilization: {e}")
            return None

    async def run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Run a command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=stdout.decode("utf-8"),
                stderr=stderr.decode("utf-8"),
            )

        except Exception as e:
            logger.error(f"Command execution failed: {command} - {e}")
            return subprocess.CompletedProcess(
                args=command, returncode=1, stdout="", stderr=str(e)
            )

    def get_gpu_recommendations(self, task_type: str) -> Dict[str, Any]:
        """Get GPU recommendations for specific task types"""
        recommendations = {
            "ml_inference": {
                "preferred_memory": 8000,  # 8GB minimum
                "preferred_vendors": ["NVIDIA"],
                "notes": "CUDA acceleration preferred for ML inference",
            },
            "training": {
                "preferred_memory": 16000,  # 16GB minimum
                "preferred_vendors": ["NVIDIA"],
                "notes": "High memory and CUDA support essential for training",
            },
            "image_processing": {
                "preferred_memory": 4000,  # 4GB minimum
                "preferred_vendors": ["NVIDIA", "AMD"],
                "notes": "Both CUDA and OpenCL work well for image processing",
            },
            "data_processing": {
                "preferred_memory": 8000,  # 8GB minimum
                "preferred_vendors": ["AMD", "NVIDIA"],
                "notes": "AMD FirePro excellent for large dataset processing",
            },
        }

        return recommendations.get(
            task_type,
            {
                "preferred_memory": 4000,
                "preferred_vendors": ["NVIDIA", "AMD"],
                "notes": "General purpose computing",
            },
        )

    def is_gpu_suitable(self, gpu_info: Dict[str, Any], task_type: str) -> bool:
        """Check if a GPU is suitable for a specific task type"""
        recommendations = self.get_gpu_recommendations(task_type)

        # Check memory requirement
        if gpu_info.get("memory_free", 0) < recommendations.get("preferred_memory", 0):
            return False

        # Check vendor preference
        preferred_vendors = recommendations.get("preferred_vendors", [])
        if preferred_vendors and gpu_info.get("vendor") not in preferred_vendors:
            return False

        return True


# Utility functions
async def detect_primary_gpu() -> Optional[Dict[str, Any]]:
    """Convenience function to detect the primary GPU"""
    detector = GPUDetector()
    return await detector.detect_gpu()


async def get_all_gpus() -> List[Dict[str, Any]]:
    """Get information about all available GPUs"""
    detector = GPUDetector()

    all_gpus = []

    # Get NVIDIA GPUs
    nvidia_gpus = await detector.detect_nvidia_gpus()
    all_gpus.extend(nvidia_gpus)

    # Get AMD GPUs
    amd_gpus = await detector.detect_amd_gpus()
    all_gpus.extend(amd_gpus)

    return all_gpus


def format_gpu_info(gpu_info: Dict[str, Any]) -> str:
    """Format GPU information for display"""
    if not gpu_info:
        return "No GPU information available"

    return (
        f"{gpu_info.get('name', 'Unknown')} "
        f"({gpu_info.get('vendor', 'Unknown')}) - "
        f"{gpu_info.get('memory_total', 0)}MB VRAM, "
        f"{gpu_info.get('utilization', 0):.1f}% utilization"
    )


# Example usage and testing
if __name__ == "__main__":

    async def test_detection():
        print("Testing GPU detection...")

        detector = GPUDetector()
        primary_gpu = await detector.detect_gpu()

        if primary_gpu:
            print(f"Primary GPU: {format_gpu_info(primary_gpu)}")

            # Test utilization
            utilization = await detector.get_current_utilization()
            if utilization:
                print(f"Current utilization: {utilization}")
        else:
            print("No compatible GPU detected")

        # Test all GPUs
        all_gpus = await get_all_gpus()
        print(f"\nAll detected GPUs ({len(all_gpus)}):")
        for i, gpu in enumerate(all_gpus):
            print(f"  {i}: {format_gpu_info(gpu)}")

    asyncio.run(test_detection())
