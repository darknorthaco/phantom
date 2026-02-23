# Contributing to Phantom

## Code of Conduct

This project follows a strict code of conduct emphasizing:
- **DARPA DevOps + GRC compliance**
- **Clean, auditable git history**
- **Security-first development**
- **Professional enterprise standards**

## Development Workflow

### Branching Strategy
- **NEVER** commit directly to `main`/`master`
- **ALWAYS** create feature branches: `feature/description` or `phase-N-description`
- **ALWAYS** open PRs with detailed descriptions and success criteria

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

## Licensing Requirements

### Dual-License Agreement
All contributions must be licensed under Phantom's dual-license model:
- **MIT** for open-source use
- **Commercial license** for commercial deployment

Contributors must include this header in all new files:

```python
# SPDX-License-Identifier: MIT OR LicenseRef-Commercial
```

### IP Attribution
- Clearly document assimilated code origins
- Maintain component license files
- Update AUDIT_LOG.md for all licensing changes

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

## Quality Standards

### Code Quality
- Type hints for all Python code
- Comprehensive docstrings
- Unit tests for all modules
- Linting with black, flake8, mypy

### Documentation
- Update docs for any user-facing changes
- API documentation for new features
- Audit trail updates in AUDIT_LOG.md
- Changelog entries for releases

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

## Review Process

### PR Review Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass and coverage maintained
- [ ] Documentation updated
- [ ] Security review completed
- [ ] License headers included
- [ ] Audit log updated
- [ ] Breaking changes documented

### Approval Requirements
- **2 maintainer approvals** for core changes
- **1 maintainer approval** for documentation/UI changes
- **Security review** for any security-related changes
- **Legal review** for licensing changes

## Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Update documentation
5. Open a PR with detailed description
6. Address review feedback
7. Merge after approval

## Areas for Contribution

### High Priority
- React UI example implementation
- macOS support and testing
- Performance optimization
- Security hardening

### General Contributions
- Bug fixes and improvements
- Documentation enhancements
- Test coverage expansion
- Example applications

### UI Development
- Custom UI implementations
- Framework enhancements
- Protocol adapter extensions

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Invited to maintainer discussions for significant contributions

## Questions?

For questions about contributing:
- Open an issue with `[CONTRIBUTING]` prefix
- Join the development discussions
- Review existing PRs for examples