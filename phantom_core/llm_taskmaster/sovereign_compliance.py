"""
Sovereign Compliance — Phantom LLM Model and Runtime Blocklist
===============================================================

Phantom MUST NEVER load, list, recommend, or execute Chinese-origin LLMs
or Chinese-origin LLM runtimes. This module enforces that policy.

Blocked: DeepSeek, Qwen, Yi, InternLM, Baichuan, ChatGLM, PRC-origin models/runtimes.
Allowed: Meta (Llama), Mistral, Microsoft (Phi), Google (Gemma), SmolLM (EU), etc.

Governed by PHANTOM_DOCTRINE.md and PHANTOM_MANIFEST.md.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocklist patterns (case-insensitive substring match)
# ---------------------------------------------------------------------------

BLOCKED_MODEL_PATTERNS: List[str] = [
    "deepseek",
    "qwen",
    "qwen2",
    "yi-",
    "yi1",
    "yi1.5",
    "internlm",
    "baichuan",
    "chatglm",
    "glm-4",
    "zhipu",
    "minimax",
    "moonshot",
    "kimi",
    "step",
    "zephyr-chinese",
    "chinese-llama",
    "chinese-alpaca",
    "moss",
    "ernie",
    "wenxin",
    "pangu",
    "yayi",
    "lingyi",
    "flagembed",
]

BLOCKED_RUNTIME_PATTERNS: List[str] = [
    "deepseek-runtime",
    "qwen-runtime",
    "qwen-inference",
    "lmdeploy",  # PRC-origin
    "vllm-chinese",
    "triton-chinese",
]

ALLOWED_BACKENDS: set = {
    "llama.cpp",
    "ollama",
    "vllm",
    "tgi",
    "text-generation-inference",
    "rule_engine",
}


def _normalize(s: str) -> str:
    return s.lower().strip() if s else ""


def is_model_allowed(model_id: str, model_name: str = "") -> bool:
    """Return True if the model is sovereign-safe (not blocked)."""
    combined = _normalize(model_id) + " " + _normalize(model_name)
    for pattern in BLOCKED_MODEL_PATTERNS:
        if pattern in combined:
            logger.warning("Sovereign compliance: blocked model %r (matched %r)", model_id, pattern)
            return False
    return True


def is_runtime_allowed(runtime_id: str) -> bool:
    """Return True if the runtime is sovereign-safe (not blocked)."""
    norm = _normalize(runtime_id)
    for pattern in BLOCKED_RUNTIME_PATTERNS:
        if pattern in norm:
            logger.warning("Sovereign compliance: blocked runtime %r (matched %r)", runtime_id, pattern)
            return False
    # Explicit allowlist for known backends
    if norm in {b.lower() for b in ALLOWED_BACKENDS}:
        return True
    # Unknown runtime — allow if not matching blocklist (conservative)
    return True


def filter_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter a list of model entries to only sovereign-safe models."""
    allowed = []
    for m in models:
        mid = m.get("id", "") or m.get("model_id", "")
        name = m.get("name", "") or m.get("model_name", "")
        if is_model_allowed(mid, name):
            allowed.append(m)
        else:
            logger.info("Sovereign compliance: excluding model id=%r name=%r", mid, name)
    return allowed


def validate_model_before_use(model_id: str, model_name: str = "") -> bool:
    """
    Validate model before loading/executing.
    Returns True if allowed, False if blocked.
    """
    return is_model_allowed(model_id, model_name)


def validate_tls_policy(
    wan_mode: bool,
    tls_enabled: bool,
    tls_cert_path: str,
    tls_key_path: str,
) -> None:
    """
    Phase 4 — transport policy for controller / workers.

    Rules:
    - WAN (``wan_mode``) requires TLS; plaintext is not allowed across households.
    - LAN may use plaintext when ``tls_enabled`` is false (Phases 1–3 unchanged).
    - When ``tls_enabled`` is true, cert and key paths must be configured (no
      silent fallback to HTTP on the controller).
    """
    if wan_mode and not tls_enabled:
        raise ValueError(
            "Sovereign transport policy: wan_mode requires tls_enabled "
            "(encrypted controller API). Enable TLS or disable wan_mode."
        )
    if tls_enabled:
        if not (tls_cert_path and str(tls_cert_path).strip()):
            raise ValueError(
                "tls_enabled requires a non-empty tls_cert_path (no mixed plaintext/TLS)."
            )
        if not (tls_key_path and str(tls_key_path).strip()):
            raise ValueError(
                "tls_enabled requires a non-empty tls_key_path (no mixed plaintext/TLS)."
            )
