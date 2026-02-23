"""
Persistent state manager for Phantom controller.
Stores workers and tasks as JSON files so state survives restarts.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_DIR = os.getenv("PHANTOM_STATE_DIR", "/var/lib/phantom/state")


class StateManager:
    """Simple file-backed state persistence."""

    def __init__(self, state_dir: str | None = None):
        self.state_dir = Path(state_dir or _DEFAULT_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._workers_file = self.state_dir / "workers.json"
        self._tasks_file = self.state_dir / "tasks.json"

    # -- workers --------------------------------------------------------

    def load_workers(self) -> Dict[str, Any]:
        return self._load(self._workers_file)

    def save_workers(self, workers: Dict[str, Any]) -> None:
        self._save(self._workers_file, workers)

    # -- tasks ----------------------------------------------------------

    def load_tasks(self) -> Dict[str, Any]:
        return self._load(self._tasks_file)

    def save_tasks(self, tasks: Dict[str, Any]) -> None:
        self._save(self._tasks_file, tasks)

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _load(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load state from %s: %s", path, exc)
            return {}

    @staticmethod
    def _save(path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as fh:
                json.dump(data, fh, default=str)
            tmp.replace(path)
        except OSError as exc:
            logger.error("Failed to persist state to %s: %s", path, exc)
