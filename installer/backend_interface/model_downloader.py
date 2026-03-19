#!/usr/bin/env python3
"""
Model Downloader
Downloads GGUF model files with progress tracking and checksum verification.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Curated model catalogue — sovereign-safe only (Meta, Mistral, Microsoft, Google, EU)
# Chinese-origin models are NEVER listed. See phantom_core/llm_taskmaster/sovereign_compliance.py
# ---------------------------------------------------------------------------

_MODELS_RAW: List[Dict] = [
    {
        "id": "phi35_q4_k_m",
        "name": "Phi-3.5 Mini Q4_K_M",
        "description": "Recommended — Microsoft, best balance of speed and quality",
        "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF"
            "/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 6,
        "vram_rec_gb": 8,
        "file_size_gb": 2.4,
        "recommended": True,
    },
    {
        "id": "phi35_q3_k_m",
        "name": "Phi-3.5 Mini Q3_K_M",
        "description": "Lighter model — Lower VRAM requirement",
        "filename": "Phi-3.5-mini-instruct-Q3_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF"
            "/resolve/main/Phi-3.5-mini-instruct-Q3_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 4,
        "vram_rec_gb": 6,
        "file_size_gb": 2.0,
        "recommended": False,
    },
    {
        "id": "phi35_q5_k_m",
        "name": "Phi-3.5 Mini Q5_K_M",
        "description": "Higher quality — Requires more VRAM",
        "filename": "Phi-3.5-mini-instruct-Q5_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF"
            "/resolve/main/Phi-3.5-mini-instruct-Q5_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 8,
        "vram_rec_gb": 10,
        "file_size_gb": 2.8,
        "recommended": False,
    },
    {
        "id": "llama31_8b_q4_k_m",
        "name": "Llama 3.1 8B Q4_K_M",
        "description": "Recommended — Meta, strong general-purpose model",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
            "/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 6,
        "vram_rec_gb": 8,
        "file_size_gb": 4.9,
        "recommended": True,
    },
    {
        "id": "mistral_7b_q4_k_m",
        "name": "Mistral 7B Q4_K_M",
        "description": "Recommended — Mistral AI, efficient 7B model",
        "filename": "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF"
            "/resolve/main/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 6,
        "vram_rec_gb": 8,
        "file_size_gb": 4.4,
        "recommended": True,
    },
    {
        "id": "gemma2_2b_q4_k_m",
        "name": "Gemma 2 2B Q4_K_M",
        "description": "Google — Compact, efficient",
        "filename": "gemma-2-2b-it-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF"
            "/resolve/main/gemma-2-2b-it-Q4_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 4,
        "vram_rec_gb": 6,
        "file_size_gb": 1.5,
        "recommended": False,
    },
    {
        "id": "smollm2_360m",
        "name": "SmolLM2 360M Q4_K_M",
        "description": "EU-origin — Ultra-lightweight",
        "filename": "SmolLM2-360M-Instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF"
            "/resolve/main/SmolLM2-360M-Instruct-Q4_K_M.gguf"
        ),
        "sha256": "",
        "vram_min_gb": 2,
        "vram_rec_gb": 4,
        "file_size_gb": 0.3,
        "recommended": False,
    },
]


def _get_models() -> List[Dict]:
    """Return sovereign-safe models only. Filters out any blocked entries."""
    try:
        # Add phantom_core to path when running from installer tree (matches config_writer pattern)
        _pc = Path(__file__).resolve().parent.parent.parent / "phantom_core"
        if _pc.exists() and str(_pc) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(_pc))
        from llm_taskmaster.sovereign_compliance import filter_models
        return filter_models(_MODELS_RAW)
    except ImportError:
        # Fallback if phantom_core not on path (e.g. during installer tests)
        return _MODELS_RAW


# Public API: always filtered
MODELS: List[Dict] = _get_models()


class DownloadError(Exception):
    """Raised when download or verification fails."""


class ModelDownloader:
    """Downloads and verifies GGUF model files into a target directory."""

    CHUNK_SIZE = 65_536  # 64 KB

    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def download(
        self,
        model: Dict,
        status_cb: Callable[[str], None] = None,
        progress_cb: Callable[[int, int], None] = None,
    ) -> Path:
        """Download *model* and return the path to the installed GGUF file.

        Args:
            model:       Entry from the MODELS list.
            status_cb:   Called with human-readable status strings.
            progress_cb: Called with (bytes_downloaded, bytes_total).
        """
        # Sovereign compliance: never download blocked models
        mid = model.get("id", "")
        name = model.get("name", "")
        try:
            _pc = Path(__file__).resolve().parent.parent.parent / "phantom_core"
            if _pc.exists() and str(_pc) not in __import__("sys").path:
                __import__("sys").path.insert(0, str(_pc))
            from llm_taskmaster.sovereign_compliance import is_model_allowed
            if not is_model_allowed(mid, name):
                raise DownloadError("Model not allowed by sovereign compliance policy.")
        except ImportError:
            pass  # Allow when compliance module unavailable (tests)
        dest = self.models_dir / model["filename"]

        # Skip download if the file already exists and checksum matches.
        if dest.exists():
            if self._verify_checksum(dest, model.get("sha256", "")):
                if status_cb:
                    status_cb(f"Model already present: {dest.name}")
                return dest
            # File exists but checksum fails — log and remove before re-downloading.
            if status_cb:
                status_cb(f"Existing file failed checksum; re-downloading: {dest.name}")
            dest.unlink()

        if status_cb:
            status_cb(f"Connecting to {model['url'].split('/')[2]}…")

        tmp = dest.with_suffix(".part")
        try:
            self._download_file(
                model["url"], tmp, status_cb=status_cb, progress_cb=progress_cb
            )
        except Exception as exc:
            if tmp.exists():
                tmp.unlink()
            raise DownloadError(f"Download failed: {exc}") from exc

        # Verify checksum (skipped when sha256 is empty).
        sha = model.get("sha256", "")
        if sha:
            if status_cb:
                status_cb("Verifying checksum…")
            if not self._verify_checksum(tmp, sha):
                tmp.unlink()
                raise DownloadError("Checksum mismatch — file may be corrupt.")

        tmp.rename(dest)

        if status_cb:
            status_cb(f"Model installed: {dest.name}")
        return dest

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _download_file(
        self,
        url: str,
        dest: Path,
        status_cb: Callable[[str], None] = None,
        progress_cb: Callable[[int, int], None] = None,
    ) -> None:
        with urllib.request.urlopen(url, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            if status_cb and total:
                mb = total / (1024 * 1024)
                status_cb(f"Downloading {mb:.0f} MB…")
            downloaded = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = response.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

    @staticmethod
    def _verify_checksum(path: Path, expected: str) -> bool:
        """Return True if *expected* is empty (skip) or matches file SHA-256."""
        if not expected:
            return True
        sha = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65_536), b""):
                sha.update(chunk)
        return sha.hexdigest().lower() == expected.lower()
