# PHANTOM SOCKET ARCHITECTURE REMINDER

**Version:** 1.0.0
**Status:** Authoritative Reference – Permanent
**Applies to:** All AI agents and developers analyzing or modifying Phantom protocol code

---

## Purpose

This document exists so that no future agent ever forgets the core design insight
behind Phantom's communication layer: **the socket/protocol architecture was built
from the start to make protocol upgrades a configuration change, not a code
rewrite.**

Reference this document before assessing the complexity of any protocol
modification task.

---

## 1. Architectural Foundation

Phantom's transport layer is a **transport-agnostic abstraction framework**
composed of three orthogonal concerns:

```
┌─────────────────────────────────────────────────────┐
│                  Business Logic                      │
│         (controller, worker, orchestrator)           │
└─────────────────────┬───────────────────────────────┘
                      │  calls
┌─────────────────────▼───────────────────────────────┐
│               ChannelManager                         │
│   (phantom_protocol/channels.py)                    │
│   routes messages through registered protocol stacks│
└──────────┬──────────────────────┬───────────────────┘
           │                      │
┌──────────▼──────────┐  ┌───────▼──────────────────┐
│  MessageSerializer  │  │    TransportAdapter       │
│  (interfaces.py)    │  │    (interfaces.py)        │
│                     │  │                           │
│  • json (default)   │  │  • http  (default)        │
│  • protobuf ✅ NEW  │  │  • grpc  ✅ NEW           │
│  • flatbuffers      │  │  • websocket              │
│  • msgpack          │  │  • quic / zeromq          │
└─────────────────────┘  └───────────────────────────┘
           │                      │
┌──────────▼──────────────────────▼───────────────────┐
│               ProtocolConfig                         │
│   (phantom_protocol/config.py)                      │
│   per-channel: serializer + transport selection     │
│   source: code, dict, or environment variables      │
└─────────────────────────────────────────────────────┘
```

**The critical insight:** business logic never calls HTTP or gRPC directly.
It calls `ChannelManager.send_and_receive()`.  The actual wire protocol is
chosen at runtime by `ProtocolConfig`.

---

## 2. Design Patterns Baked Into This Architecture

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Factory** | `factory.py` → `create_channel_manager()` | Creates a fully-wired manager from config |
| **Strategy** | `serializers/`, `transports/` | Pluggable implementations swapped at runtime |
| **Configuration** | `config.py` → `ProtocolConfig` | Runtime protocol selection without code change |
| **Abstraction** | `interfaces.py` | Business logic depends on abstract contracts only |

---

## 3. Complexity Assessment Decision Tree

```
Is the change a protocol modification?
│
├─► Does it operate THROUGH the socket framework?
│       (ChannelManager / ProtocolConfig / new serializer or transport)
│   │
│   └─► YES → ✅ LOW COMPLEXITY
│               Configuration change or a new pluggable module.
│               Existing tests keep passing.
│               JSON+HTTP default is never touched.
│
└─► Does it BYPASS the socket framework?
        (direct httpx/requests/websockets calls in business logic)
    │
    └─► YES → ⚠️  HIGH COMPLEXITY
                Requires architectural review.
                Risk of violating Commandment VII (Layer separation).
```

**Default assumption for protocol modifications:** LOW COMPLEXITY.

**Exception (HIGH complexity):** the change bypasses the abstraction layer.

---

## 4. What a Low-Complexity Protocol Addition Looks Like

Phase 4 (gRPC + Protobuf) is a canonical example of low-complexity work:

| What changed | Where | Why it's low-risk |
|---|---|---|
| `.proto` schemas | `phantom_protocol_schemas/` | New directory, zero deps on existing code |
| `ProtobufSerializer` | `phantom_protocol/serializers/` | New file implementing existing interface |
| `GRPCTransport` | `phantom_protocol/transports/` | New file implementing existing interface |
| `setup.py` extras | `setup.py` | Added `[grpc]` optional dep group |
| Factory wiring | `factory.py` | Import + register, plus loud error if deps absent |
| Tests | `tests/test_protocol/` | 16 additional tests, 0 existing tests broken |
| Docs | This file + PROTOCOL_MIGRATION_GUIDE | Transparency |

**Zero changes to:** `channels.py`, `interfaces.py`, `config.py`, `json_serializer.py`,
`http_transport.py`, or any business-logic file.

---

## 5. Safe Defaults Enforced By the Framework

| Concern | Default | Override mechanism |
|---|---|---|
| Serialization | JSON | `ProtocolConfig.channels[name].serializer = "protobuf"` |
| Transport | HTTP | `ProtocolConfig.channels[name].transport = "grpc"` |
| Timeout | 30 s (gRPC) / per-channel (HTTP) | `ChannelConfig.timeout` or env var |
| Max message | 4 MiB (gRPC) | `GRPCTransport` channel options |
| Silent fallback | **NEVER** – missing dep raises `RuntimeError` | Explicit `allow_fallback` flag (not yet added; default false) |

---

## 6. How to Enable gRPC+Protobuf (and How to Roll Back)

### Enable

```bash
# 1. Install optional extras
pip install .[grpc]

# 2a. Code (recommended for gradual rollout – one channel at a time)
from phantom_protocol.config import ProtocolConfig
config = ProtocolConfig()
config.update_channel("task_distribution", serializer="protobuf", transport="grpc")
manager = create_channel_manager(config)

# 2b. Environment variables (for deployment-wide switch)
export PHANTOM_PROTOCOL_SERIALIZER=protobuf
export PHANTOM_PROTOCOL_TRANSPORT=grpc
```

### Roll Back

```bash
# Remove env vars (JSON+HTTP is the hardcoded default – no env var needed)
unset PHANTOM_PROTOCOL_SERIALIZER
unset PHANTOM_PROTOCOL_TRANSPORT

# Or in code – just don't call update_channel; defaults are already json+http
manager = create_channel_manager()   # ← always JSON+HTTP with no config
```

Roll-back is instant and requires no code deployment.

---

## 7. Test Commands

```bash
# Base tests (no grpc deps required)
pytest tests/test_protocol/test_protocol_layer.py -v

# gRPC + Protobuf tests (requires pip install .[grpc])
pytest tests/test_protocol/test_grpc_protobuf.py -v

# All protocol tests
pytest tests/test_protocol/ -v
```

---

## 8. Critical Rules for Future Agents

1. **Never modify `interfaces.py` to add protocol-specific logic.**
   New protocols go in new files under `serializers/` or `transports/`.

2. **Never import `grpc` or `google.protobuf` in `channels.py`, `config.py`,
   or `factory.py` at module level.**  All protocol imports are lazy/optional.

3. **Never silently fall back to JSON when gRPC is configured.**
   Fail loud with a `RuntimeError` that names the missing package and the
   install command.

4. **Always keep JSON+HTTP the zero-configuration default.**
   Any deployment with no env vars / no `ProtocolConfig` customization must
   use JSON over HTTP, exactly as before Phase 4.

5. **Treat each channel independently.**  One channel using gRPC does not
   force all channels to use gRPC.

---

## 9. References

| Document | Purpose |
|---|---|
| `phantom_protocol/interfaces.py` | Abstract contracts (the law) |
| `phantom_protocol/config.py` | Per-channel configuration schema |
| `phantom_protocol/factory.py` | Wiring and dependency validation |
| `phantom_protocol_schemas/*.proto` | Protobuf schemas (source of truth for gRPC messages) |
| `PROTOCOL_MIGRATION_GUIDE.md` | Enable/rollback instructions with examples |
| `PHANTOM_COMMANDMENTS.md` | Commandment VII: never violate layer separation |
| `PHANTOM_PROTOCOL_ANALYSIS.md` | Original architecture analysis |

---

**This architecture is Phantom's secret weapon for seamless protocol evolution.
Never let an agent forget it.**
