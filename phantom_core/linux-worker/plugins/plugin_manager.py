"""
Plugin Manager for GPU-specific task execution
Manages different GPU plugins and routes tasks to appropriate handlers
"""

import logging
import importlib
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseGPUPlugin(ABC):
    """Base class for GPU-specific plugins"""

    def __init__(self, gpu_info: Dict[str, Any]):
        self.gpu_info = gpu_info
        self.supported_tasks = []
        self.plugin_name = "base"

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        pass

    @abstractmethod
    async def execute_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using this plugin"""
        pass

    @abstractmethod
    def can_handle_task(self, task_type: str) -> bool:
        """Check if this plugin can handle the given task type"""
        pass

    def get_performance_score(self, task_type: str) -> float:
        """Get performance score for this plugin handling the task type"""
        return 1.0 if self.can_handle_task(task_type) else 0.0

    async def cleanup(self):
        """Cleanup resources"""
        pass


class PluginManager:
    """Manages GPU plugins and routes tasks to appropriate handlers"""

    def __init__(self):
        self.plugins: List[BaseGPUPlugin] = []
        self.gpu_info = None
        self.initialized = False

    async def initialize(self, gpu_info: Dict[str, Any]):
        """Initialize the plugin manager with GPU information"""
        self.gpu_info = gpu_info

        try:
            # Load appropriate plugins based on GPU type
            await self.load_plugins()

            # Initialize all loaded plugins
            for plugin in self.plugins:
                try:
                    success = await plugin.initialize()
                    if success:
                        logger.info(
                            f"✅ Plugin {plugin.plugin_name} initialized successfully"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Plugin {plugin.plugin_name} initialization failed"
                        )
                except Exception as e:
                    logger.error(
                        f"❌ Plugin {plugin.plugin_name} initialization error: {e}"
                    )

            self.initialized = True
            logger.info(
                f"🔌 Plugin manager initialized with {len(self.plugins)} plugins"
            )

        except Exception as e:
            logger.error(f"Plugin manager initialization failed: {e}")
            raise

    async def load_plugins(self):
        """Load plugins based on GPU information"""
        if not self.gpu_info:
            raise Exception("GPU information not available")

        gpu_name = self.gpu_info.get("name", "").upper()
        gpu_vendor = self.gpu_info.get("vendor", "").upper()

        # Load vendor-specific plugins
        if "NVIDIA" in gpu_vendor:
            await self.load_nvidia_plugins(gpu_name)
        elif "AMD" in gpu_vendor:
            await self.load_amd_plugins(gpu_name)

        # Always load the general plugin as fallback
        await self.load_general_plugin()

    async def load_nvidia_plugins(self, gpu_name: str):
        """Load NVIDIA-specific plugins"""
        try:
            # RTX 50-series specific plugin
            if any(model in gpu_name for model in ["RTX 5080", "RTX 5060"]):
                from .rtx50_plugin import RTX50Plugin

                plugin = RTX50Plugin(self.gpu_info)
                self.plugins.append(plugin)
                logger.info("🎮 Loaded RTX 50-series plugin")

            # GTX 1080 specific plugin
            elif "GTX 1080" in gpu_name:
                from .gtx1080_plugin import GTX1080Plugin

                plugin = GTX1080Plugin(self.gpu_info)
                self.plugins.append(plugin)
                logger.info("🎮 Loaded GTX 1080 plugin")

            # General NVIDIA CUDA plugin
            from .nvidia_cuda_plugin import NVIDIACudaPlugin

            plugin = NVIDIACudaPlugin(self.gpu_info)
            self.plugins.append(plugin)
            logger.info("🎮 Loaded NVIDIA CUDA plugin")

        except ImportError as e:
            logger.warning(f"Failed to load NVIDIA plugins: {e}")

    async def load_amd_plugins(self, gpu_name: str):
        """Load AMD-specific plugins"""
        try:
            # FirePro W9100 specific plugin
            if "FIREPRO W9100" in gpu_name:
                from .firepro_plugin import FireProPlugin

                plugin = FireProPlugin(self.gpu_info)
                self.plugins.append(plugin)
                logger.info("🎮 Loaded FirePro W9100 plugin")

            # General AMD ROCm plugin
            from .amd_rocm_plugin import AMDRocmPlugin

            plugin = AMDRocmPlugin(self.gpu_info)
            self.plugins.append(plugin)
            logger.info("🎮 Loaded AMD ROCm plugin")

        except ImportError as e:
            logger.warning(f"Failed to load AMD plugins: {e}")

    async def load_general_plugin(self):
        """Load general-purpose plugin as fallback"""
        try:
            from .general_plugin import GeneralPlugin

            plugin = GeneralPlugin(self.gpu_info)
            self.plugins.append(plugin)
            logger.info("🎮 Loaded general plugin")
        except ImportError as e:
            logger.warning(f"Failed to load general plugin: {e}")

    def get_plugin_for_task(self, task_type: str) -> Optional[BaseGPUPlugin]:
        """Get the best plugin for handling a specific task type"""
        if not self.initialized:
            logger.warning("Plugin manager not initialized")
            return None

        # Find plugins that can handle this task type
        capable_plugins = [
            plugin for plugin in self.plugins if plugin.can_handle_task(task_type)
        ]

        if not capable_plugins:
            logger.warning(f"No plugins available for task type: {task_type}")
            return None

        # Select the plugin with the highest performance score
        best_plugin = max(
            capable_plugins, key=lambda p: p.get_performance_score(task_type)
        )

        logger.debug(f"Selected plugin {best_plugin.plugin_name} for task {task_type}")
        return best_plugin

    def get_supported_task_types(self) -> List[str]:
        """Get all supported task types across all plugins"""
        task_types = set()
        for plugin in self.plugins:
            task_types.update(plugin.supported_tasks)
        return list(task_types)

    def get_status(self) -> Dict[str, Any]:
        """Get plugin manager status"""
        return {
            "initialized": self.initialized,
            "plugin_count": len(self.plugins),
            "plugins": [
                {
                    "name": plugin.plugin_name,
                    "supported_tasks": plugin.supported_tasks,
                    "gpu_info": plugin.gpu_info.get("name", "Unknown"),
                }
                for plugin in self.plugins
            ],
            "supported_task_types": self.get_supported_task_types(),
        }

    async def cleanup(self):
        """Cleanup all plugins"""
        for plugin in self.plugins:
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.warning(f"Plugin {plugin.plugin_name} cleanup failed: {e}")

        self.plugins.clear()
        self.initialized = False
        logger.info("🧹 Plugin manager cleaned up")


# Task execution utilities
class TaskExecutionContext:
    """Context for task execution with resource management"""

    def __init__(self, plugin: BaseGPUPlugin, task_parameters: Dict[str, Any]):
        self.plugin = plugin
        self.task_parameters = task_parameters
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None

    async def __aenter__(self):
        """Enter the execution context"""
        import time

        self.start_time = time.time()
        logger.debug(f"Starting task execution with {self.plugin.plugin_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the execution context"""
        import time

        self.end_time = time.time()
        duration = self.end_time - self.start_time

        if exc_type:
            self.error = str(exc_val)
            logger.error(f"Task execution failed after {duration:.2f}s: {exc_val}")
        else:
            logger.debug(f"Task execution completed in {duration:.2f}s")

    async def execute(self) -> Dict[str, Any]:
        """Execute the task within this context"""
        try:
            self.result = await self.plugin.execute_task(self.task_parameters)
            return self.result
        except Exception as e:
            self.error = str(e)
            raise


# Plugin discovery utilities
def discover_available_plugins() -> List[str]:
    """Discover all available plugin modules"""
    import os
    import glob

    plugin_dir = os.path.dirname(__file__)
    plugin_files = glob.glob(os.path.join(plugin_dir, "*_plugin.py"))

    plugins = []
    for plugin_file in plugin_files:
        plugin_name = os.path.basename(plugin_file)[:-3]  # Remove .py extension
        plugins.append(plugin_name)

    return plugins


def get_plugin_info(plugin_name: str) -> Dict[str, Any]:
    """Get information about a specific plugin"""
    try:
        module = importlib.import_module(f".{plugin_name}", package=__package__)

        # Look for plugin class
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseGPUPlugin)
                and attr != BaseGPUPlugin
            ):
                plugin_class = attr
                break

        if plugin_class:
            return {
                "name": plugin_name,
                "class": plugin_class.__name__,
                "module": module.__name__,
                "docstring": plugin_class.__doc__ or "No description available",
            }
        else:
            return {"name": plugin_name, "error": "No valid plugin class found"}

    except ImportError as e:
        return {"name": plugin_name, "error": f"Import failed: {e}"}


# Example usage and testing
if __name__ == "__main__":
    import asyncio

    async def test_plugin_manager():
        # Mock GPU info for testing
        test_gpu_info = {
            "name": "RTX 5080",
            "vendor": "NVIDIA",
            "memory_total": 24000,
            "memory_free": 20000,
        }

        manager = PluginManager()
        await manager.initialize(test_gpu_info)

        print("Plugin Manager Status:")
        status = manager.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

        # Test task routing
        test_tasks = ["ml_inference", "image_processing", "data_processing"]
        for task_type in test_tasks:
            plugin = manager.get_plugin_for_task(task_type)
            if plugin:
                print(f"Task '{task_type}' -> Plugin '{plugin.plugin_name}'")
            else:
                print(f"Task '{task_type}' -> No suitable plugin")

        await manager.cleanup()

    asyncio.run(test_plugin_manager())
