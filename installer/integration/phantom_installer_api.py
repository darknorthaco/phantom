#!/usr/bin/env python3
"""
Phantom Installer API
Safe wrapper around all backend modules for use by the GUI wizard.

This module is the single integration point between the wizard UI and the
existing Phantom installer machinery.  It MUST NOT modify any constitutional
pipeline code.  All actions are logged to installation_audit.log.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Ensure installer root is on sys.path (backend_interface sibling dir).
_installer_dir = Path(__file__).parent.parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

# Re-use backend_interface modules — do NOT add duplicate logic here.
from backend_interface.system_scan_adapter import run_system_scan  # noqa: E402
from backend_interface.worker_discovery_adapter import (  # noqa: E402
    WorkerDiscoveryAdapter,
)
from backend_interface.model_downloader import (  # noqa: E402
    MODELS,
    DownloadError,
    ModelDownloader,
)
from backend_interface.config_writer import ConfigWriter  # noqa: E402
from backend_interface.installer_driver import (  # noqa: E402
    INSTALL_STAGES,
    InstallerDriver,
)


class PhantomInstallerAPI:
    """Unified API consumed by the GUI wizard screens.

    Responsibilities:
    - Provide a single import surface for all wizard backends.
    - Write every significant action to *installation_audit.log*.
    - Never modify constitutional pipeline code.
    """

    AUDIT_LOG_NAME = "installation_audit.log"

    def __init__(self, install_dir: Path):
        self.install_dir = Path(install_dir)
        self.install_dir.mkdir(parents=True, exist_ok=True)

        self._logger = self._setup_audit_logger()

        # Lazily initialised sub-systems
        self._worker_adapter: Optional[WorkerDiscoveryAdapter] = None
        self._model_downloader: Optional[ModelDownloader] = None
        self._config_writer: Optional[ConfigWriter] = None
        self._installer_driver: Optional[InstallerDriver] = None

        self._log("PhantomInstallerAPI initialised")

    # ------------------------------------------------------------------ #
    # Audit logging
    # ------------------------------------------------------------------ #

    def _setup_audit_logger(self) -> logging.Logger:
        # Use a fixed logger name scoped to the install directory to avoid proliferation.
        logger_name = f"phantom_audit.{self.install_dir.name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            fh = logging.FileHandler(
                self.install_dir / self.AUDIT_LOG_NAME, encoding="utf-8"
            )
            fh.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] %(levelname)-7s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(fh)
        return logger

    def _log(self, msg: str, level: str = "info") -> None:
        getattr(self._logger, level, self._logger.info)(msg)

    # ------------------------------------------------------------------ #
    # System scan
    # ------------------------------------------------------------------ #

    def run_system_scan(self, ports: List[int] = None) -> Dict:
        """Run system compatibility checks via existing SystemChecker."""
        self._log("Running system scan")
        result = run_system_scan(ports=ports)
        status = "PASSED" if result["ok"] else "FAILED"
        self._log(
            f"System scan {status}: "
            f"{len(result.get('passed', []))} passed, "
            f"{len(result.get('warnings', []))} warnings, "
            f"{len(result.get('failed', []))} failed"
        )
        return result

    # ------------------------------------------------------------------ #
    # Worker discovery
    # ------------------------------------------------------------------ #

    @property
    def worker_adapter(self) -> WorkerDiscoveryAdapter:
        if self._worker_adapter is None:
            self._worker_adapter = WorkerDiscoveryAdapter()
        return self._worker_adapter

    def discover_workers(
        self,
        mode: str = "comprehensive",
        progress_cb: Callable[[str], None] = None,
    ) -> List[Dict]:
        """Discover workers using the existing WorkerDiscovery backend.

        Args:
            mode: ``'comprehensive'``, ``'manual'``, or ``'skip'``.
        """
        self._log(f"Starting worker discovery (mode={mode})")
        if mode == "comprehensive":
            workers = self.worker_adapter.discover_comprehensive(
                progress_cb=progress_cb
            )
        elif mode == "manual":
            workers = self.worker_adapter.discover_manual(progress_cb=progress_cb)
        else:
            workers = []
        self._log(
            f"Worker discovery complete: {len(workers)} worker(s) found"
        )
        return workers

    # ------------------------------------------------------------------ #
    # Model catalogue and download
    # ------------------------------------------------------------------ #

    def get_models(self) -> List[Dict]:
        """Return the curated model catalogue."""
        return MODELS

    def download_model(
        self,
        model: Dict,
        status_cb: Callable[[str], None] = None,
        progress_cb: Callable[[int, int], None] = None,
    ) -> Path:
        """Download and verify a model. Returns path to installed GGUF file."""
        self._log(f"Starting model download: {model['name']}")
        models_dir = self.install_dir / "models"
        if self._model_downloader is None:
            self._model_downloader = ModelDownloader(models_dir)
        path = self._model_downloader.download(
            model, status_cb=status_cb, progress_cb=progress_cb
        )
        self._log(f"Model ready: {path}")
        return path

    # ------------------------------------------------------------------ #
    # Configuration writing
    # ------------------------------------------------------------------ #

    @property
    def config_writer(self) -> ConfigWriter:
        if self._config_writer is None:
            self._config_writer = ConfigWriter(self.install_dir)
        return self._config_writer

    def write_llm_config(self, model_path: Path, model_info: Dict) -> Path:
        """Write llm_config.json for the selected model."""
        path = self.config_writer.write_llm_config(model_path, model_info)
        self._log(f"LLM config written: {path}")
        return path

    def write_worker_registry(
        self, workers: List[Dict], task_master: Dict
    ) -> Path:
        """Write worker_registry.json."""
        path = self.config_writer.write_worker_registry(workers, task_master)
        self._log(
            f"Worker registry written: {path} "
            f"(task_master={task_master.get('ip', '?')})"
        )
        return path

    # ------------------------------------------------------------------ #
    # Installation execution
    # ------------------------------------------------------------------ #

    def get_install_stages(self) -> List[str]:
        """Return ordered list of installation stage names."""
        return list(INSTALL_STAGES)

    def prepare_installer(
        self,
        worker_configs: List[Dict] = None,
        install_type: str = "all",
    ) -> InstallerDriver:
        """Initialise and configure the InstallerDriver.

        Must be called before ``run_installation_stage()``.
        """
        self._installer_driver = InstallerDriver(
            install_dir=self.install_dir,
            worker_configs=worker_configs or [],
        )
        self._installer_driver.select_default_components(install_type)
        self._log(
            f"Installer prepared (type={install_type}, "
            f"workers={len(worker_configs or [])})"
        )
        return self._installer_driver

    def run_installation_stage(
        self,
        stage_idx: int,
        progress_cb: Callable[[int, str], None] = None,
        log_cb: Callable[[str], None] = None,
    ) -> bool:
        """Run one installation stage and audit-log the outcome."""
        if self._installer_driver is None:
            raise RuntimeError("Call prepare_installer() before running stages.")

        def _audited_log(msg: str) -> None:
            self._log(f"[Stage {stage_idx}] {msg}")
            if log_cb:
                log_cb(msg)

        ok = self._installer_driver.run_stage(
            stage_idx, progress_cb=progress_cb, log_cb=_audited_log
        )
        self._log(
            f"Stage {stage_idx} "
            f"({'OK' if ok else 'FAILED'}): {INSTALL_STAGES[stage_idx]}"
        )
        return ok
