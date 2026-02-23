# Phantom Distributed Compute Fabric

**Your AI. Your Hardware. Your Rules.**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](VERSION)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## What Is Phantom?

Phantom is a **unified distributed computing platform** designed for heterogeneous GPU clusters, AI workload distribution, and sovereign compute. It combines a battle-tested distributed engine, a professional cross-platform installer suite, and a swappable UI architecture into a single, market-ready distribution.

Phantom exists to **restore digital sovereignty**. Your hardware, your models, your data, your truth — computed locally, on your machines, with no cloud dependencies and no external control surfaces unless you explicitly allow them.

> *"The Ethos is law. The human is sovereign. The machine serves."*

Read the full philosophy: [PHANTOM_ETHOS.md](PHANTOM_ETHOS.md) | [PHANTOM_TEN_COMMANDMENTS.md](PHANTOM_TEN_COMMANDMENTS.md)

---

## Key Features

- **Distributed Task Processing** — Intelligent routing across heterogeneous GPU/CPU nodes
- **LLM Task Master** — AI-powered task scheduling with AUTO, HYBRID, and MANUAL execution modes
- **Swappable UI Framework** — Plug-and-play UI architecture with RedBlue Matrix as the default professional interface
- **Enterprise Installer Suite** — Cross-platform GUI and CLI installers with wizard-level UX
- **Bulletproof Uninstaller** — Complete system cleanup with process termination, port verification, and rollback
- **LAN-First / Privacy-First** — No cloud dependencies, no telemetry without consent, no external control
- **Dual-License Model** — MIT for open-source use, commercial license for enterprise deployment

---

## Quick Start

### Prerequisites

- Python 3.8+
- Network ports 8765, 8082, 8080 available
- Administrator/root privileges for service installation

### Windows (GUI Installer)

```cmd
python installer\windows_gui_installer.py
```

### Windows (CLI)

```cmd
package\install.bat
```

### Linux / macOS

```bash
sudo ./package/install.sh
```

For detailed instructions, see [INSTALLATION.md](INSTALLATION.md).

---

## Architecture

```
phantom/
├── phantom_core/       # Distributed computing engine (controller, workers, protocols)
├── ui/
│   ├── redblue_matrix/ # Default professional UI (Matrix-inspired cyberpunk aesthetic)
│   ├── ui_framework/   # Swappable UI base classes and protocol adapters
│   └── examples/       # Reference UI implementations (web, terminal)
├── installer/          # Installation modules (process cleanup, port verification)
├── package/            # Build scripts and cross-platform installers
├── docs/               # Architecture, UI framework, and audit documentation
└── governance/         # Licensing, contributing, and commercial terms
```

For the full architecture overview, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Execution Modes

Phantom operates in three execution modes — a core architectural principle:

| Mode | Description | Human Involvement |
|------|-------------|-------------------|
| **MANUAL** | Human directs every task | Full control (sacred default) |
| **HYBRID** | AI proposes, human approves | Supervised automation |
| **AUTO** | AI executes within guardrails | Autonomous within boundaries |

> MANUAL mode is **sacred**. AUTO and HYBRID are convenience layers — never the default.

---

## Governance

Phantom is governed by foundational documents that are **non-negotiable**:

- [PHANTOM_ETHOS.md](PHANTOM_ETHOS.md) — Core principles: sovereignty, transparency, reversibility, human control
- [PHANTOM_TEN_COMMANDMENTS.md](PHANTOM_TEN_COMMANDMENTS.md) — Operational rules: immutable laws governing architecture and safety
- [GOVERNANCE.md](GOVERNANCE.md) — Decision-making, authority hierarchy, enforcement
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute (branching, PRs, code standards)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Community standards of behavior

---

## Licensing

Phantom uses a **dual-license model**:

### Open Source (MIT)
The core platform is released under the MIT License. See [LICENSE](LICENSE).
For commercial use, Dark North Co. requests a commercial license — see [LICENSE-NONCOMMERCIAL](LICENSE-NONCOMMERCIAL) for guidance.

### Commercial
Required for business deployment, white-label redistribution, and revenue-generating use.  
See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) for pricing tiers and terms.  
Contact: licensing@darknorthco.com

For the full licensing explanation, see [governance/LICENSING.md](governance/LICENSING.md).

---

## Documentation

| Document | Description |
|----------|-------------|
| [INSTALLATION.md](INSTALLATION.md) | Installation guide (all platforms) |
| [UNINSTALLATION.md](UNINSTALLATION.md) | Uninstallation and cleanup guide |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture overview |
| [docs/UI_FRAMEWORK.md](docs/UI_FRAMEWORK.md) | Swappable UI framework guide |
| [docs/AUDIT_LOG.md](docs/AUDIT_LOG.md) | Assimilation and compliance audit trail |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [SECURITY.md](SECURITY.md) | Security policy and vulnerability reporting |
| [SUPPORT.md](SUPPORT.md) | Support channels and issue reporting |

---

## Platform Support

| Platform | Status | Installer |
|----------|--------|-----------|
| Windows 10/11 | Supported | GUI wizard + CLI batch |
| Ubuntu 20.04+ | Supported | CLI shell script + systemd |
| Debian 11+ | Supported | CLI shell script + systemd |
| RHEL 8+ | Supported | CLI shell script + systemd |
| macOS 12+ | Beta | CLI shell script |

---

## Security

For vulnerability reporting, see [SECURITY.md](SECURITY.md).  
Do **not** open public issues for security vulnerabilities.

---

## Contributing

We welcome contributions. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the [PHANTOM_ETHOS.md](PHANTOM_ETHOS.md) before submitting a PR.

---

## Contact

**Dark North Co.**  
Email: licensing@darknorthco.com  
Website: darknorthco.com

---

*Built with sovereignty in mind. Phantom belongs to the people who use it.*
