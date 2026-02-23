# Changelog

All notable changes to the Phantom distributed computing platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-23 — Initial Release (Unified Distribution)

### Added — Platform
- **Unified Repository**: Assimilated phantom_ptr, redblue-private, and rm-phantom into single distribution
- **Swappable UI Framework**: Abstract base UI with WebSocket/HTTP protocol adapters (`ui/ui_framework/`)
- **RedBlue Matrix UI**: Reference web and Android interface implementations (`ui/redblue_matrix/`)
- **Enhanced Installer/Uninstaller**: Windows GUI installer, cross-platform CLI, bulletproof uninstall with process termination and port verification
- **LLM Taskmaster**: AI-powered intelligent task routing and decomposition
- **Execution Modes**: Safe / Moderate / Full mode enforcement at runtime
- **Package Distribution**: Build scripts and installers for Windows and Linux (`package/`)

### Added — Governance & Documentation
- **Root LICENSE** (MIT with commercial/branding notices)
- **COMMERCIAL-LICENSE.md** (Professional $300/yr, Enterprise $1,500/yr, OEM custom)
- **README.md** (landing page with badges, quick start, architecture overview)
- **PHANTOM_ETHOS.md** (canonical governance — foundational principles)
- **PHANTOM_TEN_COMMANDMENTS.md** (canonical governance — operational rules)
- **GOVERNANCE.md** (decision-making, enforcement, access levels)
- **CONTRIBUTING.md** (development setup, workflow, CLA)
- **CODE_OF_CONDUCT.md** (Contributor Covenant v2.1 with Phantom adaptations)
- **SECURITY.md** (vulnerability reporting, network exposure, hardening)
- **INSTALLATION.md** (comprehensive multi-platform installation guide)
- **UNINSTALLATION.md** (comprehensive multi-platform uninstallation guide)
- **SUPPORT.md** (community + commercial support channels, FAQ)
- **VERSION** file (single source of truth: `1.0.0`)
- **docs/ARCHITECTURE.md** (system architecture, components, data flow, topology)
- **docs/UI_FRAMEWORK.md** (interface contract, protocol messages, custom UI guide)
- **CHANGELOG.md** (this file)
- **.gitignore** (excludes build artifacts, caches, editor files, binaries)

### Changed
- **Repository Structure**: Reorganized into enterprise-grade directory layout
- **Copyright**: Standardized to "Copyright (c) 2026 Dark North Co." across all LICENSE files
- **Commercial Pricing**: Unified to $300/$1,500/custom (resolved prior $999/$4,999 conflict)
- **SPDX Claim**: Corrected from false "all files include" to honest "in progress" language
- **Governance Docs**: Updated all "Phantom_PTR" / "public sandbox" references to "Phantom" / "unified distribution"

### Technical Details
- **Ports**: 8765 (Controller API), 8082 (WebSocket worker comm), 8080 (Web UI)
- **Process Cleanup**: pgrep-based detection with SIGTERM→SIGKILL escalation
- **Port Verification**: ss/lsof/netstat support for all three ports
- **UI Framework**: Abstract base class → protocol adapter → pluggable implementations
- **Licensing**: Dual-license (MIT + Commercial) normalized across all components

### Security
- Maintained Phantom security model throughout assimilation
- Preserved audit trails and clean uninstall capabilities
- No system pollution or persistent changes without user consent
- Network services bind to localhost by default

### Known Issues
- React UI example is placeholder (template structure only)
- macOS testing pending (Linux/Windows verified)
- SPDX headers not yet present in all legacy source files (adoption in progress)

---

## Version History
- **1.0.0**: Unified distribution — initial public release
- **Pre-1.0**: Individual component development (phantom_ptr, redblue-private, rm-phantom)