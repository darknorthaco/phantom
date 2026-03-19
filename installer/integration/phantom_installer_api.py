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
from backend_interface.config_writer import ConfigWriter, ConfigBootstrap  # noqa: E402
from backend_interface.installer_driver import (  # noqa: E402
    INSTALL_STAGES,
    InstallerDriver,
)
from backend_interface.dependency_fetcher import DependencyFetcher  # noqa: E402
from backend_interface.reboot_manager import (  # noqa: E402
    RebootManager,
    InstallerPhase,
    InstallerState,
)
from backend_interface.wsl_orchestrator import (  # noqa: E402
    WSLOrchestrator,
    WSLStatus,
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
        self._config_bootstrap: Optional[ConfigBootstrap] = None
        self._installer_driver: Optional[InstallerDriver] = None
        self._dep_fetcher: Optional[DependencyFetcher] = None
        self._reboot_manager: Optional[RebootManager] = None
        self._wsl_orchestrator: Optional[WSLOrchestrator] = None

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
        self._log(f"Worker discovery complete: {len(workers)} worker(s) found")
        return workers

    # ------------------------------------------------------------------ #
    # Model catalogue and download
    # ------------------------------------------------------------------ #

    def get_models(self) -> List[Dict]:
        """Return the curated model catalogue (sovereign-safe only; Chinese-origin models never listed)."""
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

    def write_worker_registry(self, workers: List[Dict], task_master: Dict) -> Path:
        """Write worker_registry.json."""
        path = self.config_writer.write_worker_registry(workers, task_master)
        self._log(
            f"Worker registry written: {path} "
            f"(task_master={task_master.get('ip', '?')})"
        )
        return path

    # ------------------------------------------------------------------ #
    # Step 4.5 — phantom_config.json bootstrap
    # ------------------------------------------------------------------ #

    def bootstrap_config(
        self,
        config_path: Path,
        host: str = "127.0.0.1",
        port: int = 8080,
        security: str = "disabled",
        identity_fingerprint: str = "",
        execution_mode: str = "manual",
    ) -> Path:
        """Write phantom_config.json atomically at deploy Step 4.5.

        This is the **authoritative** writer for phantom_config.json.  It
        must be called after the Controller Selection Ceremony and before
        the controller process is started (Step 5).

        A timestamped backup is created before overwriting any existing
        config file, and the write is atomic (tmp → rename).

        Args:
            config_path:          Absolute path where phantom_config.json
                                  should be written (e.g.
                                  ``~/.phantom/phantom_config.json``).
            host:                 Controller host from §1 ceremony.
            port:                 Controller port (default 8080).
            security:             ``"disabled"``, ``"basic"``, or ``"full"``.
            identity_fingerprint: Hex Ed25519 fingerprint from IdentityManager.
            execution_mode:       Default execution mode.

        Returns:
            Path of the written config file.
        """
        self._log(
            f"[Step 4.5] Bootstrapping phantom_config.json at {config_path} "
            f"(host={host}, port={port}, security={security})"
        )
        if self._config_bootstrap is None:
            self._config_bootstrap = ConfigBootstrap(Path(config_path))
        else:
            self._config_bootstrap = ConfigBootstrap(Path(config_path))

        path = self._config_bootstrap.write(
            host=host,
            port=port,
            security=security,
            identity_fingerprint=identity_fingerprint,
            execution_mode=execution_mode,
        )
        self._log(f"[Step 4.5] phantom_config.json written: {path}")
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

    # ------------------------------------------------------------------ #
    # Dependency fetching
    # ------------------------------------------------------------------ #

    @property
    def dep_fetcher(self) -> DependencyFetcher:
        if self._dep_fetcher is None:
            staging = self.install_dir / "staging"
            self._dep_fetcher = DependencyFetcher(staging)
        return self._dep_fetcher

    def fetch_dependencies(
        self,
        requirements_path: Path,
        status_cb: Callable[[str], None] = None,
    ) -> bool:
        """Download and stage pip dependencies.

        Returns True if all wheels downloaded and verified OK.
        """
        self._log(f"Fetching dependencies from {requirements_path}")
        specs = self.dep_fetcher.parse_requirements(requirements_path)
        specs = self.dep_fetcher.resolve_platform_constraints(specs)
        self._log(f"Resolved {len(specs)} dependency specs")

        ok = self.dep_fetcher.download_wheels(
            requirements_path,
            status_cb=status_cb,
        )
        all_ok, bad = self.dep_fetcher.verify_wheels(status_cb=status_cb)
        if bad:
            self._log(f"Corrupt wheels: {bad}", level="warning")
        self.dep_fetcher.write_manifest(requirements_path)
        self._log(f"Dependency fetch {'OK' if (ok and all_ok) else 'PARTIAL'}")
        return ok and all_ok

    def install_from_cache(
        self,
        target_dir: Path | None = None,
        status_cb: Callable[[str], None] = None,
    ) -> bool:
        """Install staged wheels with pip --no-index."""
        target = target_dir or self.install_dir / ".venv"
        self._log(f"Installing cached wheels into {target}")
        ok = self.dep_fetcher.install_from_cache(target, status_cb=status_cb)
        self._log(f"Cache install {'OK' if ok else 'FAILED'}")
        return ok

    def detect_privileged_deps(self) -> list:
        """Return list of privileged dependencies that require manual action."""
        return self.dep_fetcher.detect_privileged_deps()

    # ------------------------------------------------------------------ #
    # WSL orchestration (read-only)
    # ------------------------------------------------------------------ #

    @property
    def wsl_orchestrator(self) -> WSLOrchestrator:
        if self._wsl_orchestrator is None:
            self._wsl_orchestrator = WSLOrchestrator()
        return self._wsl_orchestrator

    def check_wsl_status(self) -> Dict:
        """Detect WSL readiness and return a summary dict for the GUI."""
        self._log("Checking WSL status")
        status = self.wsl_orchestrator.detect_wsl_status()
        summary = self.wsl_orchestrator.get_status_summary(status)
        self._log(f"WSL status: {summary['status']}")
        return summary

    def is_wsl_reboot_required(self) -> bool:
        """Return True when WSL kernel was just installed and needs reboot."""
        status = self.wsl_orchestrator.detect_wsl_status()
        return self.wsl_orchestrator.is_reboot_required(status)

    # ------------------------------------------------------------------ #
    # Reboot / resume state management
    # ------------------------------------------------------------------ #

    @property
    def reboot_manager(self) -> RebootManager:
        if self._reboot_manager is None:
            self._reboot_manager = RebootManager(self.install_dir)
        return self._reboot_manager

    def save_state(self) -> None:
        """Persist current installer state to disk."""
        self._log("Saving installer state")
        self.reboot_manager.save_state()

    def load_state(self) -> Optional[InstallerState]:
        """Load previously persisted installer state."""
        self._log("Loading installer state")
        state = self.reboot_manager.load_state()
        if state:
            self._log(f"Restored state — phase: {state.current_phase}")
        else:
            self._log("No saved state found")
        return state

    def prepare_reboot(self, reason: str = "") -> Optional[str]:
        """Prepare resume shortcut and state for reboot.

        Returns the shortcut path (or None if creation failed).
        This method NEVER triggers a reboot.  It only creates the
        resume artefact so the user can reboot at their discretion.
        """
        self._log(f"Preparing reboot resume (reason={reason})")
        shortcut = self.reboot_manager.prepare_reboot_resume(reason=reason)
        self._log(f"Resume shortcut: {shortcut or 'FAILED'}")
        return shortcut

    def complete_resume(self) -> None:
        """Called after reboot-resume to clean up artefacts."""
        self._log("Completing resume — cleaning up shortcut")
        self.reboot_manager.complete_resume()

    def has_resume_state(self) -> bool:
        """Check whether a resume-state file exists."""
        return self.reboot_manager.has_resume_state()

    def get_resume_screen_index(self) -> int:
        """Return the wizard screen index to resume at after reboot."""
        return self.reboot_manager.get_resume_screen_index()
