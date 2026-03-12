"""
Structured JSON logging for Phantom Windows worker.
Mirrors linux-worker logging format.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _rfc3339_now() -> str:
    """Return current UTC timestamp in RFC3339 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StructuredLogHandler(logging.Handler):
    """Handler that emits structured JSON logs with sovereign fields."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry: Dict[str, Any] = {
                "timestamp": _rfc3339_now(),
                "event": record.name,
                "success": record.levelno < logging.ERROR,
                "duration_ms": getattr(record, "duration_ms", 0),
                "metadata": getattr(record, "metadata", None),
                "error_message": record.getMessage() if record.levelno >= logging.ERROR else None,
            }
            # Include standard fields
            entry["level"] = record.levelname
            entry["message"] = record.getMessage()
            if record.exc_info:
                entry["exc_info"] = self.formatter.formatException(record.exc_info) if self.formatter else None

            line = json.dumps(entry, default=str)
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
        except Exception:
            self.handleError(record)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure logging with structured JSON output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = StructuredLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s:%(lineno)d - %(message)s"))
    root.addHandler(handler)
