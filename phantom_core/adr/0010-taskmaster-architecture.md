# ADR 0010: LLM Task Master Architecture

## Status
Approved — 2026-02-28

## Context

Phantom Distributed Compute Fabric requires an LLM integration layer that routes
tasks to locally-hosted language models running on heterogeneous GPU hardware.
The integration must respect the Soul–Mind–Body governance hierarchy
(PHANTOM_MANIFEST > PHANTOM_DOCTRINE > .cursorrules) and the 11 Doctrine
Principles, in particular:

1. **Human Priority (P-01)** — The human operator can withdraw LLM autonomy at
   any time. Every LLM action must be reversible.
2. **Sovereign Domains (P-02)** — LLM operates only within its delegated scope;
   hardware control remains with the human.
3. **Transparent Operation (P-04)** — All LLM decisions and routing choices are
   logged and auditable.
4. **Consistent Behavior (P-06)** — Switching execution modes must not change
   which task types are accepted, only the approval gate.
5. **Evolution Without Drift (P-07)** — Adding new models or backends must not
   weaken governance constraints.

Previous designs treated the LLM layer as a standalone AI agent. This violated
multiple doctrine principles by granting the LLM implicit autonomy without a
human-controllable mode gate. The absence of explicit execution modes made it
impossible for operators to enforce the Human Priority principle.

## Decision

We adopt a **mode-aware LLM Task Master** with three execution modes and
a strict governance contract.

### Execution Modes

| Mode     | LLM Role                       | Human Gate            |
|----------|--------------------------------|-----------------------|
| `AUTO`   | Receives and executes tasks    | None (post-audit)     |
| `HYBRID` | Proposes actions, awaits approval | Approve / reject each |
| `MANUAL` | Bypassed entirely              | Human issues all commands |

The active mode is read from `llm_config.json` and enforced by the
`ExecutionMode` enum in `lightweight_llm_setup.py`. Every task passes through
`_enforce_mode_gate()` before execution.

### Hardware Discovery

Worker GPU inventory is **auto-discovered at runtime** during network scanning.
The controller queries each worker's `/gpu_info` endpoint (backed by
`gpu_info_linux.get_gpu_info()` on Linux workers). No GPU model names are
hardcoded in UI, configuration, or routing logic. The Task Master receives
discovered hardware capabilities and uses them for scheduling decisions.

### Routing Architecture

```
Operator
  │
  ▼
Mode Gate  ──────────────────── MANUAL → direct CLI / UI control
  │
  ▼ (AUTO or HYBRID)
LLM Task Master
  │
  ├─ Model Router       ← selects backend by discovered GPU capability
  │    ├─ ollama        ← default for local inference
  │    ├─ llama.cpp     ← GGUF models, CPU/GPU offload
  │    └─ vllm          ← high-throughput serving
  │
  ├─ Context Builder    ← injects Soul/Mind/Body governance prompts
  │
  └─ Approval Gate      ← HYBRID: blocks until human approves
                          AUTO:   logs and proceeds
```

### Configuration

All LLM routing is governed by `llm_config.json`:

```json
{
  "execution_mode": "HYBRID",
  "llm_backend": "llama_cpp",
  "model_name": "phi-3.5-mini",
  "model_quant": "Q4_K_M",
  "model_format": "GGUF",
  "fallback_backend": "ollama",
  "target_gpu": "auto",
  "human_override": true,
  "governance": {
    "manifest_ref": "doctrine/PHANTOM_MANIFEST.md",
    "doctrine_ref": "doctrine/PHANTOM_DOCTRINE.md"
  }
}
```

`human_override: true` is a non-negotiable default. Setting it to `false` is a
doctrine violation.

### Governance Injection

Every LLM prompt is prefixed with the system-governance preamble extracted from
PHANTOM_DOCTRINE.md. This ensures the model operates within doctrine bounds
regardless of which backend is active. The preamble is immutable at runtime; only
the Manifest author can change it.

## Consequences

### Positive

- **Human Priority enforced** — Operator can switch to MANUAL at any time,
  instantly revoking LLM autonomy.
- **Hardware-agnostic** — Routing adapts to whatever GPUs the network scan
  discovers; no hardcoded model names.
- **Backend-flexible** — New LLM backends can be added without changing the mode
  gate or governance layer.
- **Auditable** — Every task records its execution mode, the human who approved
  it (if HYBRID), and the governance preamble hash.

### Negative

- **Latency in HYBRID** — Each task blocks on human approval, adding variable
  delay. Mitigated by batch-approval UI in future.
- **Governance preamble cost** — Prepending doctrine text consumes context tokens.
  Mitigated by summarisation layer (planned).

### Neutral

- Existing controller/worker protocol (JSON over HTTP + WebSocket) is unchanged.
  Protocol evolution is handled by ADR-0011.

## Rationale

The mode-aware architecture is the minimum viable design that satisfies all 11
Doctrine Principles simultaneously. Simpler designs (always-AUTO, or no mode
concept) were rejected because they violate P-01 (Human Priority) and P-02
(Sovereign Domains). The three-mode model mirrors real-world industrial control
systems (fully automatic / semi-automatic / manual) and is immediately intuitive
to operators.

## References

- [PHANTOM_MANIFEST.md](../../doctrine/PHANTOM_MANIFEST.md) — Soul layer
- [PHANTOM_DOCTRINE.md](../../doctrine/PHANTOM_DOCTRINE.md) — Mind layer (11 Principles)
- [PHANTOM_EXECUTION_MODES_AND_API_SPEC.md](../PHANTOM_EXECUTION_MODES_AND_API_SPEC.md)
- [lightweight_llm_setup.py](../llm_taskmaster/lightweight_llm_setup.py) — Implementation
- [llm_config.json](../llm_taskmaster/llm_config.json) — Runtime configuration
- [ADR 0011: Protocol Abstraction Layer](0011-protocol-abstraction-layer.md)