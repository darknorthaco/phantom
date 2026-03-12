"""
GPU Detection for Windows using pynvml.
Enumerates NVIDIA GPUs; collects name, memory, driver, temperature, compute capability.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_pynvml_available = False
try:
    import pynvml
    _pynvml_available = True
except ImportError:
    pass


class GPUDetector:
    """Detects and provides information about NVIDIA GPUs on Windows via pynvml."""

    def __init__(self) -> None:
        self.nvidia_available = False
        self.detected_gpus: List[Dict[str, Any]] = []
        self._nvml_initialized = False

    def _init_nvml(self) -> bool:
        """Initialize NVML. Returns True if successful."""
        if self._nvml_initialized:
            return self.nvidia_available
        if not _pynvml_available:
            logger.warning("gpu_detection_unavailable: pynvml not installed. pip install pynvml")
            self._nvml_initialized = True
            return False
        try:
            pynvml.nvmlInit()
            self._nvml_initialized = True
            self.nvidia_available = True
            return True
        except Exception as e:
            logger.warning("gpu_detection_unavailable: NVML init failed: %s", e)
            self._nvml_initialized = True
            return False

    async def detect_gpu(self) -> Optional[Dict[str, Any]]:
        """Detect the primary GPU for this worker."""
        if not self._init_nvml():
            return None
        gpus = await self._detect_nvidia_gpus()
        if gpus:
            self.detected_gpus.extend(gpus)
            return gpus[0]
        logger.warning("No compatible GPUs detected")
        return None

    async def _detect_nvidia_gpus(self) -> List[Dict[str, Any]]:
        """Detect NVIDIA GPUs using pynvml."""
        if not _pynvml_available:
            return []
        try:
            import pynvml
            count = pynvml.nvmlDeviceGetCount()
            gpus: List[Dict[str, Any]] = []
            for i in range(count):
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    name_str = name.decode("utf-8") if isinstance(name, bytes) else str(name)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    memory_total_mb = mem_info.total // (1024 * 1024)
                    memory_free_mb = mem_info.free // (1024 * 1024)
                    memory_used_mb = mem_info.used // (1024 * 1024)
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        utilization = float(util.gpu)
                    except Exception:
                        utilization = 0.0
                    try:
                        driver_ver = pynvml.nvmlSystemGetDriverVersion()
                        driver_str = driver_ver.decode("utf-8") if isinstance(driver_ver, bytes) else str(driver_ver)
                    except Exception:
                        driver_str = "unknown"
                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    except Exception:
                        temp = 0
                    try:
                        cuda_compute = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                        compute_cap = f"{cuda_compute[0]}.{cuda_compute[1]}"
                    except Exception:
                        compute_cap = "unknown"

                    gpu_info: Dict[str, Any] = {
                        "index": i,
                        "name": name_str,
                        "memory_total": memory_total_mb,
                        "memory_free": memory_free_mb,
                        "memory_used": memory_used_mb,
                        "utilization": utilization,
                        "driver_version": driver_str,
                        "temperature": temp,
                        "compute_capability": compute_cap,
                        "vendor": "NVIDIA",
                        "type": "CUDA",
                    }
                    gpus.append(gpu_info)
                    logger.info("Detected NVIDIA GPU: %s (%s MB)", name_str, memory_total_mb)
                except Exception as e:
                    logger.warning("Failed to get GPU %d info: %s", i, e)
            return gpus
        except Exception as e:
            logger.warning("NVIDIA GPU detection failed: %s", e)
            return []

    async def get_current_utilization(self) -> Optional[Dict[str, Any]]:
        """Get current GPU utilization and memory usage."""
        if not self.nvidia_available or not self.detected_gpus:
            return None
        try:
            import pynvml
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                utilization = float(util.gpu)
            except Exception:
                utilization = 0.0
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = 0.0
            return {
                "memory_free": mem_info.free // (1024 * 1024),
                "memory_used": mem_info.used // (1024 * 1024),
                "utilization": utilization,
                "temperature": temp,
            }
        except Exception as e:
            logger.warning("Failed to get GPU utilization: %s", e)
            return None
