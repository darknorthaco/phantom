# Phantom TLS (Phase 4) — Controller ↔ worker transport

This document describes **encrypted, authenticated HTTP(S)** between workers and the **controller API** for WAN / cross-household deployments. It does **not** replace trust-ledger QUIC flows; it secures the **same HTTP API** the workers already use (callbacks, registration, etc.) when you enable TLS.

## Policy (sovereign)

| Mode | `wan_mode` | `tls_enabled` | Controller binds |
|------|------------|---------------|------------------|
| **LAN default** | `false` | `false` | HTTP (plaintext) — Phases 1–3 behavior preserved |
| **LAN + TLS** | `false` | `true` | HTTPS (optional hardening on LAN) |
| **WAN** | `true` | **must be `true`** | HTTPS — enforced by `sovereign_compliance.validate_tls_policy()` |

Rules:

- **No mixed mode:** Controller is either HTTP **or** HTTPS for a given config; there is no silent downgrade from HTTPS to HTTP.
- **No public CAs:** Use self-signed or operator-imported PEM files stored **only** under your Phantom profile (`~/.phantom` / `%USERPROFILE%\.phantom`).
- **No telemetry or cloud:** Certificate generation and validation are local.

## Configuration

### Controller — `phantom_config.json` (top level)

```json
{
  "wan_mode": false,
  "tls_enabled": false,
  "tls_cert_path": "",
  "tls_key_path": ""
}
```

- When `tls_enabled` is `true`, the Python controller passes `ssl_certfile` / `ssl_keyfile` to **uvicorn** (see `phantom_core/phantom_core/tls_runtime.py`: `uvicorn_ssl_kwargs`, `load_tls_config`, `validate_tls_paths`).
- Startup logs state whether TLS is active (see `log_tls_state`).

### Workers — `local_worker_config.json` or worker JSON

```json
{
  "tls_enabled": false,
  "tls_controller_cert_path": ""
}
```

- When `tls_enabled` is `true`, the worker uses **`https://`** for the controller base URL (`phantom_core/worker_tls.py`: `controller_base_url`).
- **`tls_controller_cert_path`** must point to the **controller’s certificate PEM** (pinning / verification for `httpx`). If TLS is on and this path is missing or not a file, the worker raises **before** connecting (no silent fallback).

## How workers validate controller identity

Workers pin the **exact PEM** you configure:

1. Operator enables TLS and sets `tls_cert_path` / `tls_key_path` on the controller.
2. The **same** public certificate file (or a copy) is referenced as `tls_controller_cert_path` on each worker.
3. `httpx` uses that file as `verify=...`, so TLS succeeds only if the server presents a chain compatible with that pinned cert (typical: same self-signed leaf).

This is **TOFU-style pinning**, not WebPKI. It matches sovereign / air-gapped operation.

## Generating a certificate (desktop app)

In **Experimental — Identity, Trust & WAN** (TOC):

1. **Generate certificate** — calls Tauri `generate_self_signed_cert` (rcgen, RSA key material suitable for TLS).
2. **Import certificate** — `import_tls_cert` copies operator PEMs into `state/tls/` after local PEM sanity checks.
3. **Validate cert PEM** — `validate_tls_cert` reads the file locally (BEGIN CERTIFICATE check).
4. **Save to phantom_config.json** — `save_phantom_tls_settings` merges `wan_mode`, `tls_enabled`, `tls_cert_path`, `tls_key_path` (requires deploy Step 4.5 to have created `phantom_config.json`).

After saving, **restart the controller service** so uvicorn picks up SSL.

## Enabling WAN mode

1. Generate or import certs; set paths in the UI and save.
2. Enable **WAN mode** and **TLS** (WAN forces TLS in the UI and in policy).
3. Open firewall paths for the controller API port (TCP) as you already do for deployment.
4. On **remote workers**, distribute config with `tls_enabled: true`, correct `controller_host` / `controller_port`, and `tls_controller_cert_path` pointing at the controller cert PEM they trust.

## Python API reference

| Function | Module | Role |
|----------|--------|------|
| `load_tls_config` | `phantom_core.tls_runtime` | Read TLS-related keys from `phantom_config.json` |
| `validate_tls_paths` | `phantom_core.tls_runtime` | Ensure cert/key files exist |
| `uvicorn_ssl_kwargs` | `phantom_core.tls_runtime` | SSL kwargs for uvicorn or `{}` for HTTP |
| `log_tls_state` | `phantom_core.tls_runtime` | One-line diagnostic log |
| `validate_tls_policy` | `llm_taskmaster.sovereign_compliance` | WAN requires TLS; TLS requires paths |
| `controller_base_url` | `worker_tls` | `http://` vs `https://` |
| `httpx_verify_for_worker` | `worker_tls` | `verify` argument for httpx |

## Tauri commands

| Command | Purpose |
|---------|---------|
| `generate_self_signed_cert` | Write `phantom.crt` / `phantom.key` under app `state/tls/` |
| `import_tls_cert` | Copy PEM pair to `imported.crt` / `imported.key` |
| `validate_tls_cert` | Local PEM certificate sanity check |
| `save_phantom_tls_settings` | Merge WAN/TLS fields into `phantom_config.json` |

## Related docs

- `docs/phantom_config_reference.md` — full `phantom_config.json` field list including Phase 4 keys  
- `INSTALL.md` — TLS section and WAN notes  
- `DEPLOYMENT_CEREMONY.md` — WAN ceremony path  
