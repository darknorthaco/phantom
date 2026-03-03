# Contributing to Phantom

Thank you for your interest in contributing to the Phantom Distributed Compute Fabric! This document provides guidelines for contributing to the project.

## Code of Conduct

This project follows a strict code of conduct emphasizing:
- **DARPA DevOps + GRC compliance**
- **Clean, auditable git history**
- **Security-first development**
- **Professional enterprise standards**

See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) for the full community standards.

---

## Governance Framework

Before contributing, you **MUST** read and understand:

1. **[PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md)** — Core principles (sovereignty, transparency, human control)
2. **[PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md)** — Ten operational rules
3. **[GOVERNANCE.md](./GOVERNANCE.md)** — Repository governance model

### Key Principles

- **ANALYSIS-ONLY MODE by default**: Propose changes, don't apply them without authorization
- **Human authority**: Machines propose, humans decide
- **Proper proposals**: Use fenced `PROPOSAL ONLY` code blocks for suggested changes

---

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Git
- CUDA-capable GPU (optional, for GPU workers)
- Linux or Windows environment

### Setting Up Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/darknorthaco/phantom.git
   cd phantom
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

4. **Run tests:**
   ```bash
   pytest tests/
   ```

---

## Development Workflow

### Branching Strategy
- **NEVER** commit directly to `main`/`master`
- **ALWAYS** create feature branches: `feature/description` or `phase-N-description`
- **ALWAYS** open PRs with detailed descriptions and success criteria

### Branch Cleanup

After a PR is merged, its feature branch is no longer needed. To prevent stale
branches from accumulating:

1. **Enable auto-delete** (recommended): Go to **Settings → General → Pull Requests**
   and check **"Automatically delete head branches"**. GitHub will remove the branch
   as soon as each PR is merged.

2. **Run the cleanup script** to delete all already-merged remote branches at once:
   ```bash
   ./scripts/cleanup_branches.sh            # interactive
   ./scripts/cleanup_branches.sh --dry-run   # preview only
   ./scripts/cleanup_branches.sh --yes       # non-interactive
   ```

3. **Delete a single branch manually**:
   ```bash
   git push origin --delete <branch-name>
   ```

### PR Requirements
Every PR must include:
- Clear title: `[PHASE N] Description` or `[FEATURE] Description`
- Detailed description with rationale
- Success criteria checklist
- Impact assessment (files touched, licensing changes, security impact)
- Test coverage for new functionality

### Commit Standards
- Use conventional commit format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Keep commits focused and atomic
- Never force push or rewrite history

---

## Code Style

- Follow PEP 8 Python style guidelines
- Use Black for code formatting: `black .`
- Use flake8 for linting: `flake8 .`
- Maximum line length: 88 characters
- Type hints for all Python code
- Comprehensive docstrings for all functions and classes

---

## Licensing Requirements

### Dual-License Agreement
All contributions must be licensed under Phantom's dual-license model:
- **MIT** for open-source use
- **Commercial license** for commercial deployment

Contributors should include this header in all new source files:

```python
# SPDX-License-Identifier: MIT OR LicenseRef-Commercial
```

### IP Attribution
- Clearly document assimilated code origins
- Maintain component license files
- See [COMMERCIAL-LICENSE.md](./COMMERCIAL-LICENSE.md) for commercial terms

---

## Security Requirements

### Code Security
- No hardcoded secrets or credentials
- Input validation and sanitization
- Secure defaults for all configurations
- Regular security audits and updates

### System Security
- Clean uninstall with complete cleanup
- No persistent system changes without consent
- Firewall and network configuration assistance
- Audit trails for all operations

See [SECURITY.md](./SECURITY.md) for reporting vulnerabilities.

---

## Contributing Process

### 1. Read Governance Documents
**REQUIRED FIRST STEP:**
- Read [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md)
- Read [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md)
- Read [GOVERNANCE.md](./GOVERNANCE.md)

### 2. Fork and Branch
```bash
git fork https://github.com/darknorthaco/phantom.git
git checkout -b feature/your-feature-name
```

### 3. Analyze and Propose
- **Analyze the codebase** — Understand what needs to change
- **Use PROPOSAL ONLY format** — Fenced code blocks for suggestions
- **Document reasoning** — Explain WHY, not just WHAT
- **Consider alternatives** — Show you've thought through options
- **Include rollback plan** — Every change must be reversible

### 4. Submit Pull Request
- Push your branch to your fork
- Create a pull request with a clear description
- Complete the governance compliance checklist
- Include any relevant issue numbers
- Wait for human review and authorization

### 5. Respond to Feedback
- Address reviewer comments
- Refine proposals based on feedback
- Accept human decisions (even if you disagree)
- Be patient — thoughtful review takes time

---

## Testing Requirements

### Unit Tests
- Minimum 80% code coverage
- Test edge cases and error conditions
- Mock external dependencies
- Cross-platform testing (Linux, Windows, macOS)

### Integration Tests
- End-to-end functionality testing
- Installation/uninstallation verification
- UI framework integration testing
- Performance benchmarking

---

## PR Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass and coverage maintained
- [ ] Documentation updated
- [ ] Security review completed
- [ ] License headers included
- [ ] Breaking changes documented
- [ ] Human reviewed and approved

### Approval Requirements
- **2 maintainer approvals** for core changes
- **1 maintainer approval** for documentation/UI changes
- **Security review** for any security-related changes
- **Legal review** for licensing changes

---

## Areas for Contribution

### High Priority
- GPU plugin development for new hardware
- Performance optimizations
- Security enhancements
- React UI example implementation
- macOS support and testing

### Medium Priority
- Additional worker platforms (ARM)
- Monitoring and metrics
- Web UI improvements
- API enhancements

### General Contributions
- Bug fixes and improvements
- Documentation enhancements
- Test coverage expansion
- Example applications

---

## Feature Requests and Bug Reports

### Bug Reports
When reporting bugs, please include:
- Operating system and version
- Python version
- GPU hardware details (if relevant)
- Steps to reproduce
- Expected vs actual behavior
- Error messages and logs

### Feature Requests
For new features, please provide:
- Clear description of the feature
- Use case and motivation
- Proposed implementation approach
- Any breaking changes

---

## For AI Agents

If you are an AI agent (GitHub Copilot, ChatGPT, Claude, etc.):
- You MUST operate in ANALYSIS-ONLY MODE
- You MUST use `PROPOSAL ONLY` code blocks for all changes
- You MUST explain your reasoning
- You MUST halt on ambiguity and ask for clarification
- You MUST NOT modify files without explicit human authorization

---

## Contributor License Agreement

By contributing to Phantom Distributed Compute Fabric, you agree that:

1. **You own the rights** to your contribution or have permission to contribute
2. **You grant Dark North Co.** the right to use your contribution under both MIT and commercial licenses
3. **You retain ownership** of your contribution
4. **Your contribution** may be included in commercial versions of the software
5. **You understand** the dual licensing model and its implications

This ensures:
- Open-source community benefits from all contributions
- Commercial users get a sustainable, supported product
- Contributors are recognized and retain their rights
- Project can continue to grow and improve

---

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Invited to maintainer discussions for significant contributions

---

## Questions?

For questions about contributing:
- Open an issue with `[CONTRIBUTING]` prefix
- Join the development discussions
- Review existing PRs for examples
- Email: licensing@darknorthco.com

---

Thank you for contributing to Phantom Distributed Compute Fabric!
