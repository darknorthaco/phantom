# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

To report a security vulnerability, please send an email to:

**licensing@darknorthco.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fix (if any)

### Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Depends on severity |
| Disclosure | Coordinated with reporter |

We follow responsible disclosure practices. We will acknowledge receipt of your report, assess the vulnerability, and work with you on a coordinated disclosure timeline.

## Security Architecture

### Network Exposure

Phantom exposes the following network ports by default:

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 8765 | API | HTTP/WS | Controller API endpoint |
| 8082 | Socket | WebSocket | Real-time worker communication |
| 8080 | UI | HTTP | Web UI interface |

**All ports bind to localhost by default.** External exposure requires explicit configuration.

### Security Principles

Phantom's security posture is governed by the [Phantom Ethos](PHANTOM_ETHOS.md) and [Ten Commandments](PHANTOM_TEN_COMMANDMENTS.md), specifically:

- **Commandment X (Protect Sovereignty):** No cloud dependencies, no telemetry without consent, no external control surfaces
- **Ethos: Transparency:** All system state is inspectable; all data flows are auditable
- **Ethos: Reversibility:** No irreversible changes without explicit human authorization

### Key Security Features

- **LAN-first architecture:** No external network calls by default
- **No telemetry:** No data leaves the system without explicit user consent
- **Process isolation:** Workers operate independently with defined boundaries
- **Audit trails:** All operations are logged and traceable
- **Clean uninstall:** Complete system cleanup with process termination and port verification

### Configuration Hardening

- Bind services to `127.0.0.1` (default) — do not expose to `0.0.0.0` without firewall rules
- Enable TLS for production deployments (see `phantom_core/certs/` for certificate generation)
- Use virtual environments to isolate Python dependencies
- Review the security framework at `phantom_core/security_framework/`

## Known Security Considerations

- The default installation binds to localhost only
- Commercial deployments should implement TLS termination
- Worker authentication is recommended for multi-node deployments
- Port availability should be verified before installation (the installer checks this automatically)

## Scope

This security policy covers the Phantom unified distribution including:
- `phantom_core/` — Distributed computing engine
- `ui/` — UI framework and implementations
- `installer/` — Installation and uninstallation modules
- `package/` — Build and distribution scripts

Third-party dependencies are tracked via `requirements.txt` and should be audited independently.
