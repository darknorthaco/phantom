# Contributing to Phantom Distributed Compute Fabric

Thank you for your interest in contributing to the Phantom Distributed Compute Fabric! This document provides guidelines for contributing to the project.

## 🚨 IMPORTANT: Governance Framework

**This repository (Phantom_PTR) is a public sandbox** operating under the Phantom governance framework. Before contributing, you **MUST** read and understand:

1. **[PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md)** - Core principles (sovereignty, transparency, human control)
2. **[PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md)** - Ten operational rules
3. **[PHANTOM_SOUL.md](./PHANTOM_SOUL.md)** - Philosophical foundation
4. **[GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md)** - ANALYSIS-ONLY MODE guidelines
5. **[GOVERNANCE.md](./GOVERNANCE.md)** - Repository governance model

### Key Principles

- **ANALYSIS-ONLY MODE by default**: Propose changes, don't apply them without authorization
- **Human authority**: Machines propose, humans decide
- **Sandbox boundary**: Work here does NOT affect the private Phantom repository
- **Proper proposals**: Use the [PROPOSAL_TEMPLATE.md](./PROPOSAL_TEMPLATE.md) format

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Git
- CUDA-capable GPU (optional, for GPU workers)
- Linux or Windows environment

### Setting Up Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/darknorthaco/phantom-test.git
   cd phantom-test
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

## Project Structure

```
phantom-test/
├── phantom_core/           # Core controller and orchestration
├── linux-worker/          # Linux worker implementation
├── windows-worker/         # Windows worker configurations
├── socket_infrastructure/  # WebSocket communication layer
├── llm_taskmaster/        # AI-powered task routing
├── security_framework/    # Security and authentication
├── scripts/               # Utility scripts
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## Development Guidelines

### Code Style
- Follow PEP 8 Python style guidelines
- Use Black for code formatting: `black .`
- Use flake8 for linting: `flake8 .`
- Maximum line length: 88 characters

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb in present tense
- Keep first line under 50 characters
- Add detailed description if needed

Example:
```
Add GPU memory optimization for RTX 50-series

- Implement dynamic memory allocation
- Add memory usage monitoring
- Optimize tensor operations for 4th gen cores
```

### Testing
- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for good test coverage
- Test on multiple GPU configurations when possible

### Documentation
- Update documentation for new features
- Include docstrings for all functions and classes
- Update README.md if adding major features
- Add examples for new functionality

## Contributing Process

### 1. Read Governance Documents
**REQUIRED FIRST STEP:**
- Read [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md)
- Read [PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md)
- Read [GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md)
- Understand ANALYSIS-ONLY MODE

### 2. Fork and Branch
```bash
git fork https://github.com/darknorthaco/phantom-test.git
git checkout -b feature/your-feature-name
```

### 3. Analyze and Propose
- **Analyze the codebase** - Understand what needs to change
- **Use PROPOSAL ONLY format** - Copy from [PROPOSAL_TEMPLATE.md](./PROPOSAL_TEMPLATE.md)
- **Document reasoning** - Explain WHY, not just WHAT
- **Consider alternatives** - Show you've thought through options
- **Include rollback plan** - Every change must be reversible

### 4. Create Proposals (Not Direct Changes)
- Write analysis and proposals in markdown
- Use `PROPOSAL ONLY` code blocks for suggested changes
- Include file paths, line numbers, and reasoning
- **Do NOT directly modify code files** (unless explicitly authorized)

### 5. Submit Pull Request
- Push your branch to your fork
- Create a pull request using the PR template
- Complete the governance compliance checklist
- Include any relevant issue numbers
- Wait for human review and authorization

### 6. Respond to Feedback
- Address reviewer comments
- Refine proposals based on feedback
- Accept human decisions (even if you disagree)
- Be patient - thoughtful review takes time

## Feature Requests and Bug Reports

### Bug Reports
When reporting bugs, please include:
- Operating system and version
- Python version
- GPU hardware details
- Steps to reproduce
- Expected vs actual behavior
- Error messages and logs

### Feature Requests
For new features, please provide:
- Clear description of the feature
- Use case and motivation
- Proposed implementation approach
- Any breaking changes

## Areas for Contribution

### High Priority
- GPU plugin development for new hardware
- Performance optimizations
- Security enhancements
- Documentation improvements

### Medium Priority
- Additional worker platforms (macOS, ARM)
- Monitoring and metrics
- Web UI improvements
- API enhancements

### Low Priority
- Code refactoring
- Additional examples
- Benchmarking tools
- Integration with other frameworks

## GPU Plugin Development

If you're adding support for new GPU hardware:

1. **Create plugin file:** `linux-worker/plugins/your_gpu_plugin.py`
2. **Implement required methods:**
   - `get_capabilities()`
   - `optimize_for_task()`
   - `get_memory_info()`
   - `get_performance_metrics()`

3. **Add detection logic:** Update `gpu_info_linux.py`
4. **Test thoroughly:** Ensure compatibility with existing system
5. **Document specifications:** Add hardware details to documentation

## Security Considerations

When contributing security-related features:
- Follow secure coding practices
- Never commit secrets or credentials
- Use established cryptographic libraries
- Document security implications
- Consider backward compatibility

## Getting Help

- **Documentation:** Check existing docs first
- **Issues:** Search existing issues before creating new ones
- **Discussions:** Use GitHub Discussions for questions
- **Discord:** Join our development Discord (link in README)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain professional communication

## 📜 Contributor License Agreement

By contributing to Phantom Distributed Compute Fabric, you agree that:

1. **You own the rights** to your contribution or have permission to contribute
2. **You grant Dark North Co.** the right to use your contribution under both MIT and commercial licenses
3. **You retain ownership** of your contribution
4. **Your contribution** may be included in commercial versions of the software
5. **You understand** the dual licensing model and its implications

This ensures:
- ✅ Open source community benefits from all contributions
- ✅ Commercial users get a sustainable, supported product
- ✅ Contributors are recognized and retain their rights
- ✅ Project can continue to grow and improve

## Governance and ANALYSIS-ONLY MODE

### For All Contributors

Phantom_PTR operates under **ANALYSIS-ONLY MODE** by default. This means:

✅ **You CAN:**
- Read and analyze code
- Propose changes in PROPOSAL ONLY format
- Write documentation and analysis
- Ask questions and discuss approaches

❌ **You CANNOT (without authorization):**
- Directly modify code files
- Apply patches or diffs
- Run commands that change the repository
- Commit code changes

### For AI Agents

If you are an AI agent (GitHub Copilot, ChatGPT, Claude, etc.):
- You MUST operate in ANALYSIS-ONLY MODE
- You MUST use PROPOSAL ONLY code blocks for all changes
- You MUST explain your reasoning
- You MUST halt on ambiguity and ask for clarification
- You MUST NOT modify files without explicit human authorization

See [GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md) for complete guidelines.

### Governance References

- **[GOVERNANCE.md](./GOVERNANCE.md)** - Complete governance model
- **[PROPOSAL_TEMPLATE.md](./PROPOSAL_TEMPLATE.md)** - Template for proposals
- **[.github/PULL_REQUEST_TEMPLATE.md](./.github/PULL_REQUEST_TEMPLATE.md)** - PR template with compliance checklist
- **[adr/0012-analysis-only-mode.md](./adr/0012-analysis-only-mode.md)** - ADR documenting this decision

---

Thank you for contributing to Phantom Distributed Compute Fabric! 🚀