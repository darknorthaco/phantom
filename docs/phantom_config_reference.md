# `phantom_config.json` reference

Authoritative schema implementation: `phantom_core/phantom_core/config_schema.py` (`ConfigSchema`).

The file lives under the Phantom profile root: **`~/.phantom/phantom_config.json`** (Windows: **`%USERPROFILE%\.phantom\phantom_config.json`**). It is written at deploy **Step 4.5** and must exist before the controller starts.

## Top-level keys

| Key | Type | Description |
|-----|------|-------------|
| `controller` | object | Host, port, security level, identity fingerprint |
| `ports` | object | `controller_api`, `worker_http`, `discovery_udp`, optional `socket_infra` |
| `worker` | object | Readiness probe timings (`readiness_*`) |
| `execution_modes` | object | e.g. `default_mode` |
| `config_version` | string | Schema version |
| `written_at` | string | ISO timestamp when written |
| `written_by_step` | string | e.g. `"4.5"` |
| **`wan_mode`** | boolean | **Phase 4.** If `true`, cross-household / WAN semantics; **requires** `tls_enabled` |
| **`tls_enabled`** | boolean | **Phase 4.** If `true`, controller serves **HTTPS** (uvicorn SSL); workers use **https://** |
| **`tls_cert_path`** | string | **Phase 4.** Absolute path to PEM certificate for controller |
| **`tls_key_path`** | string | **Phase 4.** Absolute path to PEM private key for controller |

### Phase 4 transport rules

- **`wan_mode: true` + `tls_enabled: false`** → invalid (rejected at validation / controller startup).
- **`tls_enabled: true`** → `tls_cert_path` and `tls_key_path` must be non-empty and must refer to existing files.
- **`wan_mode: false`**, **`tls_enabled: false`** → LAN plaintext HTTP (default; Phases 1–3 unchanged).

See `sovereign_compliance.validate_tls_policy()` and `docs/tls.md`.

## `controller` object

| Key | Type | Description |
|-----|------|-------------|
| `host` | string | Controller bind / advertised host |
| `port` | int | Controller API port (e.g. 8080) |
| `security` | string | One of: `disabled`, `basic`, `full`, `enhanced`, `enterprise` |
| `identity_fingerprint` | string | From placement ceremony |

## `ports` object

Each named entry typically includes `port`, `protocol`, `required`.

## `worker` object

| Key | Type | Description |
|-----|------|-------------|
| `readiness_probe_interval_ms` | int | Unicast probe interval |
| `readiness_max_attempts` | int | Max probes |
| `readiness_attempt_timeout_ms` | int | Per-attempt timeout |

Remote / local worker **runtime** JSON (e.g. `local_worker_config.json`) may additionally include:

| Key | Type | Description |
|-----|------|-------------|
| `tls_enabled` | boolean | Match controller TLS |
| `tls_controller_cert_path` | string | PEM to pin controller cert for HTTPS |

## Example (minimal LAN + TLS)

```json
{
  "controller": {
    "host": "127.0.0.1",
    "port": 8080,
    "security": "basic",
    "identity_fingerprint": ""
  },
  "ports": {
    "controller_api": { "port": 8080, "protocol": "tcp", "required": true },
    "worker_http": { "port": 8090, "protocol": "tcp", "required": true },
    "discovery_udp": { "port": 8095, "protocol": "udp", "required": true }
  },
  "worker": {
    "readiness_probe_interval_ms": 500,
    "readiness_max_attempts": 20,
    "readiness_attempt_timeout_ms": 1000
  },
  "execution_modes": { "default_mode": "manual" },
  "config_version": "1.0",
  "written_at": "",
  "written_by_step": "4.5",
  "wan_mode": false,
  "tls_enabled": true,
  "tls_cert_path": "/home/you/.phantom/state/tls/phantom.crt",
  "tls_key_path": "/home/you/.phantom/state/tls/phantom.key"
}
```

## Related

- `docs/tls.md` — TLS operation and worker pinning  
- `DEPLOYMENT_CEREMONY.md` — when this file is written  
- `INSTALL.md` — install profile layout  
