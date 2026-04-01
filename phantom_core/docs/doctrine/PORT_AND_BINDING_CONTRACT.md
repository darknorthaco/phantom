# Port and Binding Contract (Phantom)

Enumerates **default** ports and binding behavior. Deployments may override via config (`phantom_config.json` / env); this contract describes canonical defaults in tree.

## TCP — controller HTTP API

- **Default port:** `8080` (see `run.py`, `phantom_core/config_schema.py`, `controller_api` CORS defaults).
- **Bind:** Typically `127.0.0.1` in dev; production bind is deployment-specific.
- **On bind failure:** Uvicorn / OS raises; the process must **not** silently choose another port without logging and human-visible configuration. The Stone-Home deployer surfaces health-check failures when nothing listens.

## TCP — socket infrastructure (integrated mode)

- **Default port:** `8081` (`run_integrated_phantom.py`, `hybrid_socket_server.py`, worker socket clients).
- **Role:** WebSocket / hybrid socket plane between controller and workers when `PHANTOM_INTEGRATED=true`.

## UDP — LAN worker discovery

- **Port:** `8095` (`DISCOVERY_PORT` in `linux-worker` and `windows-worker` `discovery_listener.py`).
- **Bind:** `0.0.0.0` with `SO_REUSEADDR` where supported.
- **On bind failure:** Implementations retry (see listeners); after exhaustion, **log at ERROR** with the port number and last error — must not fail silently.

## Worker HTTP

- **Manifest / task ports:** Per-worker configuration (e.g. `7000` in tests); not fixed globally.

## Logging requirements

- Successful bind: **INFO** with host and port (or equivalent) where implemented.
- Failure: **ERROR** including port and exception / errno text.

## CI / audit

- Changes to default ports require updating this document and the Platform Assumptions Ledger review.
- No automated CI parser for this file yet (P2); release checklist references manual verification.
