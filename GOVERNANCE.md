# Phantom Governance

**Version:** 1.0.0  
**Repository:** darknorthaco/phantom  
**Type:** Unified Distribution  
**Status:** Active

---

## Purpose

This document defines the governance model for the Phantom unified distribution repository. It establishes decision-making processes, contribution guidelines, and enforcement mechanisms to ensure alignment with the Phantom Soul–Mind–Body governance hierarchy:

- **Soul:** [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) — Identity and purpose (highest authority)
- **Mind:** [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) — Governing principles
- **Body:** [.cursorrules](./.cursorrules) + [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md) — Operational enforcement

---

## Governance Hierarchy

### 1. **Human Architect** (Final Authority)
The repository owner and designated maintainers have **final decision authority** on all matters.

**Responsibilities:**
- Define strategic direction
- Approve or reject proposals
- Resolve disputes
- Enforce governance policies
- Authorize exceptions to rules

**Powers:**
- Accept or reject contributions
- Modify governance policies
- Grant or revoke access
- Override automated systems

### 2. **Phantom Manifest (Soul)** (Foundational Identity)
The [Phantom Manifest](./doctrine/PHANTOM_MANIFEST.md) defines Phantom's identity, purpose, and the Identity Contract. It is the highest authority after the Human Architect.

### 3. **Phantom Doctrine (Mind)** (Governing Principles)
The [Phantom Doctrine](./doctrine/PHANTOM_DOCTRINE.md) interprets the Soul. It provides the principles for reasoning and decision-making.

**Key Principles:**
- Human Priority
- Sovereign Domains
- Authentic Trust
- Transparent Operation
- Voluntary Mesh Participation
- Consistent Behavior
- Evolution Without Drift
- Reversibility
- Modularity
- Minimalism
- The Opera Principle

### 4. **Ten Commandments + .cursorrules (Body)** (Operational Rules)
The [Ten Commandments](./PHANTOM_TEN_COMMANDMENTS.md) and [.cursorrules](./.cursorrules) enforce the Doctrine in action.

**Enforcement:** Mandatory for all contributors and automated agents.

### 5. **Standard Operating Procedures** (Detailed Workflows)
SOPs define step-by-step processes for common activities.

**Examples:**
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution process
- ADRs - Architecture decision records

---

## Contribution Process

### For All Contributors

1. **Read the Governance Documents**
   - [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) - Soul (identity and purpose)
   - [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) - Mind (governing principles)
   - [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md) - Body (operational rules)
   - [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) - Community standards

2. **Operate in ANALYSIS-ONLY MODE**
   - Analyze and propose changes
   - Do not apply changes without authorization
   - Use PROPOSAL ONLY format for suggestions
   - Wait for human review and approval

3. **Submit Proposals via Pull Request**
   - Fork the repository
   - Create a feature branch
   - Add your analysis and proposals
   - Submit PR for review
   - Respond to feedback

4. **Await Human Review**
   - Maintainers review all proposals
   - Feedback provided on alignment with governance
   - Approved proposals may be merged
   - Rejected proposals include explanation

### For AI Agents

AI agents (including GitPro, GitHub Copilot, and other automated tools) MUST:

1. **Default to ANALYSIS-ONLY MODE**
   - Do not modify files without explicit authorization
   - Present all changes as proposals
   - Explain reasoning for recommendations

2. **Follow Proposal Format**
   - Use fenced code blocks labeled `PROPOSAL ONLY`
   - Include file path, location, and reasoning
   - Document impact and alternatives

3. **Respect the Commandments**
   - Honor defined scope
   - Do not assume or guess
   - Show reasoning explicitly
   - Preserve architectural integrity

4. **Halt on Ambiguity**
   - Stop when requirements are unclear
   - Present options with trade-offs
   - Wait for human decision

---

## Decision-Making Process

### For Technical Decisions

1. **Proposal Submission**
   - Contributor submits detailed proposal
   - Proposal includes analysis, reasoning, and impact
   - Proposal format follows standards

2. **Community Review** (Optional)
   - Other contributors may review and comment
   - Discussion on merits and concerns
   - Refinement based on feedback

3. **Maintainer Review** (Required)
   - Maintainer evaluates against governance
   - Checks alignment with Ethos and Commandments
   - Assesses technical merit and impact

4. **Decision**
   - **Approve:** Merge and document
   - **Reject:** Explain reasoning
   - **Defer:** Request more information
   - **Modify:** Suggest changes

5. **Implementation**
   - Approved proposals are implemented
   - Changes tested before merge
   - Documentation updated
   - Changelog entry added

### For Governance Changes

Changes to governance documents require:

1. **ADR (Architecture Decision Record)**
   - Document proposed change
   - Explain rationale
   - Assess impact on existing governance

2. **Extended Review Period**
   - Minimum 7 days for community feedback
   - Public discussion encouraged

3. **Maintainer Approval**
   - Unanimous approval from all maintainers
   - Human architect has veto power

4. **Documentation Update**
   - Update affected governance documents
   - Update references and cross-links
   - Announce change to community

---

## Enforcement

### Compliance Monitoring

All contributions are checked for:
- ✅ Alignment with Phantom Manifest (Soul)
- ✅ Alignment with Phantom Doctrine (Mind)
- ✅ Compliance with Ten Commandments (Body)
- ✅ Proper proposal format
- ✅ ANALYSIS-ONLY MODE adherence
- ✅ License compliance (MIT + Commercial)

### Violation Response

**Minor Violations (e.g., formatting issues):**
- Request corrections in PR review
- Provide guidance on proper format
- Allow contributor to fix

**Moderate Violations (e.g., scope creep):**
- Reject PR with explanation
- Guide contributor to proper scope
- May request resubmission

**Major Violations (e.g., unauthorized file modifications):**
- Immediate PR rejection
- Warning to contributor
- May restrict future contributions

**Severe Violations (e.g., attempts to bypass governance):**
- PR rejection and closure
- Contributor banned
- Report to repository owner

---

## Access Levels

### Public Contributors
- Read access to public repository
- Can fork and create PRs
- Subject to governance review
- ANALYSIS-ONLY MODE required

### Maintainers
- Write access to repository
- Review and merge PRs
- Enforce governance policies
- Can authorize exceptions

### Repository Owner
- Full administrative access
- Final decision authority
- Can modify governance
- Can grant/revoke maintainer status

---

## Quality Standards

All contributions must meet:

### Code Quality
- Follows existing style and conventions
- Properly documented with docstrings
- Includes tests where appropriate
- No linting errors

### Documentation Quality
- Clear and concise writing
- Proper markdown formatting
- Internal links are valid
- Examples are working

### Security
- No hardcoded credentials
- No security vulnerabilities
- Dependencies are vetted
- Follows secure coding practices

### License Compliance
- All code under MIT license (open-source track)
- Commercial license for commercial deployment
- Proper attribution for third-party code
- No license violations
- See [COMMERCIAL-LICENSE.md](./COMMERCIAL-LICENSE.md) for commercial terms

---

## Communication Channels

### GitHub Issues
- Bug reports
- Feature requests
- Questions about usage
- Governance discussions

### Pull Requests
- Code contributions
- Documentation improvements
- Proposal submissions
- Bug fixes

### Discussions (if enabled)
- General questions
- Architecture discussions
- Best practices sharing
- Community support

---

## Conflict Resolution

### Technical Disagreements

1. **Present Options**
   - Document all viable approaches
   - Show trade-offs clearly
   - Provide evidence for recommendations

2. **Seek Community Input**
   - Invite feedback from contributors
   - Consider diverse perspectives
   - Build consensus where possible

3. **Maintainer Decision**
   - Maintainers make final call
   - Decision documented with reasoning
   - Minority opinions recorded

4. **Human Architect Override**
   - Repository owner can override any decision
   - Override reasoning must be documented
   - Community is informed

### Governance Disputes

1. **Document Concern**
   - Clearly state the issue
   - Reference specific governance policies
   - Propose resolution

2. **Escalate to Maintainers**
   - Maintainers review concern
   - Investigate facts
   - Consult governance documents

3. **Resolution**
   - Issue decision with reasoning
   - Update governance if needed
   - Implement resolution

4. **Final Appeal**
   - Repository owner makes final decision
   - No further appeals
   - Decision is binding

---

## Review and Updates

### Regular Review
- Governance reviewed quarterly
- Assessment of effectiveness
- Identification of gaps
- Proposals for improvements

### Amendment Process
1. Propose amendment via ADR
2. Community review period (7 days)
3. Maintainer discussion
4. Owner approval
5. Update documentation
6. Announce changes

---

## Compliance Checklist

Before merging any contribution:

- [ ] Aligns with Phantom Manifest (Soul)
- [ ] Aligns with Phantom Doctrine (Mind)
- [ ] Follows Ten Commandments (Body)
- [ ] Uses proper proposal format
- [ ] Includes clear reasoning
- [ ] Documented and tested
- [ ] License compliant
- [ ] Security verified
- [ ] Human reviewed and approved

---

## References

- [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) - Soul (identity and purpose)
- [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) - Mind (governing principles)
- [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md) - Body (operational rules)
- [.cursorrules](./.cursorrules) - Body (development constraints)
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution guide
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) - Community standards
- [SECURITY.md](./SECURITY.md) - Security policy
- [LICENSE](./LICENSE) - MIT License
- [COMMERCIAL-LICENSE.md](./COMMERCIAL-LICENSE.md) - Commercial License

---

## Conclusion

Governance in Phantom is designed to:
- Maintain alignment with Phantom principles
- Ensure quality and security
- Respect human authority
- Enable community contribution
- Sustain a dual-license ecosystem

By following these guidelines, we build a productive, principled, and collaborative environment for the Phantom distributed compute platform.

**Good governance enables good work. Follow the rules, and build great things.**

---

**Version:** 1.0.0  
**Effective Date:** 2026-02-17  
**Next Review:** 2026-05-17  
**Status:** Active and Enforced
