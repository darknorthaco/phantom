# ADR 0012: ANALYSIS-ONLY MODE for Phantom_PTR Public Sandbox

## Status
**ACCEPTED** - 2026-02-17

## Context

Phantom_PTR serves as a public sandbox for community exploration, experimentation, and contribution to the Phantom Distributed Compute Fabric project. As a public repository separate from the private production codebase, it requires governance mechanisms that:

1. **Preserve Human Authority** - Ensure all changes are human-reviewed and authorized
2. **Maintain Sandbox Boundary** - Prevent cross-contamination with private repository
3. **Uphold Phantom Principles** - Enforce alignment with Ethos, Commandments, and Soul
4. **Enable Community Contribution** - Allow public participation within defined boundaries
5. **Ensure Reversibility** - Make all changes reversible through human oversight

### The Problem

Without explicit governance:
- AI agents may modify files without human review
- Changes could be applied without proper analysis
- Sandbox boundary could be violated
- Phantom principles might not be consistently enforced
- Community contributions lack clear guidelines

### Current State

The repository contains:
- Production-quality code (phantom_core, workers, socket infrastructure)
- Extensive documentation (README, guides, ADRs)
- Active development and experimentation
- References to Phantom Ethos and Commandments (but not formally defined)
- No explicit governance framework

## Decision

We will implement **ANALYSIS-ONLY MODE** as the default operational constraint for all work in Phantom_PTR, supported by comprehensive governance documentation.

### Core Components

1. **PHANTOM_ETHOS.md** - Foundational principles
   - Sovereignty
   - Transparency
   - Reversibility
   - Modularity
   - Minimalism
   - Integrity
   - Human Control

2. **PHANTOM_COMMANDMENTS.md** - Ten operational rules
   - No unauthorized modifications
   - Honor defined scope
   - Don't assume - ask
   - Show reasoning
   - Preserve architectural integrity
   - Maintain modularity
   - Respect layer separation
   - No irreversible changes
   - Defer to human architect
   - Protect sovereignty

3. **PHANTOM_SOUL.md** - Philosophical foundation
   - What Phantom is and isn't
   - The Phantom Way for developers, operators, and contributors
   - The Phantom Manifesto

4. **GITPRO_ANALYSIS_MODE.md** - Operational guidelines
   - Allowed and prohibited actions
   - Proposal format and requirements
   - Enforcement mechanisms
   - Exception handling

5. **GOVERNANCE.md** - Repository governance model
   - Decision-making processes
   - Contribution guidelines
   - Access levels and enforcement
   - Quality standards

6. **ADR 0012** (this document) - Decision record

### ANALYSIS-ONLY MODE Rules

**ALLOWED:**
- ✅ Reading repository files and directories
- ✅ Analyzing code structure and architecture
- ✅ Producing written reports and recommendations
- ✅ Proposing changes (in `PROPOSAL ONLY` blocks)
- ✅ Asking clarifying questions
- ✅ Generating documentation

**PROHIBITED:**
- ❌ Creating, modifying, deleting, renaming, or moving files
- ❌ Running commands that modify repository
- ❌ Applying patches or diffs
- ❌ Installing dependencies
- ❌ Executing builds or tests (without authorization)
- ❌ Committing or pushing changes
- ❌ Any action that alters repository state

### Proposal Format

All change proposals must use:

```markdown
### PROPOSAL ONLY: [Brief Description]

**File:** [Path to file]
**Location:** [Line numbers or section]
**Reason:** [Why this change is needed]
**Impact:** [What effects this change will have]
**Alternatives:** [Other options considered]

```[language]
[Proposed code/content]
```

**Testing:** [How to validate this change]
**Rollback:** [How to undo if needed]
```

## Consequences

### Positive

1. **Human Authority Preserved**
   - All changes require explicit human review and approval
   - Machines propose, humans decide
   - Clear separation of analysis and execution

2. **Sandbox Boundary Maintained**
   - Work in Phantom_PTR remains contained
   - No accidental impacts on private repository
   - Cross-contamination prevented

3. **Quality Improved**
   - Proposals include reasoning and analysis
   - Multiple options considered
   - Trade-offs made explicit
   - Better decisions through deliberation

4. **Reversibility Guaranteed**
   - All changes are proposals until human applies them
   - No accidental irreversible modifications
   - Complete audit trail of decisions

5. **Community Enabled**
   - Clear guidelines for contribution
   - Transparent review process
   - Anyone can propose improvements
   - Meritocracy based on quality of analysis

6. **Principles Enforced**
   - Phantom Ethos consistently applied
   - Commandments become enforceable rules
   - Cultural alignment maintained

### Negative

1. **Increased Process Overhead**
   - Proposals require more documentation
   - Human review adds latency
   - May slow rapid iteration
   - **Mitigation:** Benefits outweigh costs; prevents costly mistakes

2. **Barrier to Entry**
   - Contributors must learn governance model
   - More complex than "just submit a PR"
   - **Mitigation:** Clear documentation and examples provided

3. **Potential for Bottleneck**
   - Human review required for all changes
   - Maintainer availability may limit throughput
   - **Mitigation:** Clear prioritization; multiple maintainers

### Neutral

1. **Cultural Shift**
   - Requires mindset change for some contributors
   - Emphasizes thoughtfulness over speed
   - Values analysis over immediate action

2. **Documentation Load**
   - More documents to maintain
   - References must stay consistent
   - Version control for governance docs

## Alternatives Considered

### Alternative 1: No Governance (Status Quo)
**Pros:**
- No process overhead
- Fast iteration
- No barriers to contribution

**Cons:**
- Risk of unauthorized changes
- No enforcement of principles
- Sandbox boundary violations
- Loss of human control
- Inconsistent quality

**Verdict:** Unacceptable - violates Phantom principles

### Alternative 2: Branch Protection Only
**Pros:**
- Simple technical control
- Built into GitHub
- No additional documentation

**Cons:**
- Only prevents direct pushes to main
- No guidance on proper proposals
- Doesn't enforce analysis-first approach
- No cultural or philosophical alignment

**Verdict:** Insufficient - technical control without principle enforcement

### Alternative 3: Full Production Governance
**Pros:**
- Maximum control and quality
- Enterprise-grade processes
- Comprehensive review

**Cons:**
- Overkill for public sandbox
- Stifles experimentation
- High barrier to contribution
- Slow iteration

**Verdict:** Too restrictive - defeats sandbox purpose

### Alternative 4: Separate Branches for AI vs Human Work
**Pros:**
- Isolates AI work from human work
- Clear separation

**Cons:**
- Complex branch management
- Doesn't address core issue
- Merging branches still requires review
- Doesn't enforce analysis-first

**Verdict:** Doesn't solve the problem - adds complexity without benefit

## Implementation Strategy

### Phase 1: Documentation (Complete)
- ✅ Create PHANTOM_ETHOS.md
- ✅ Create PHANTOM_COMMANDMENTS.md
- ✅ Create PHANTOM_SOUL.md
- ✅ Create GITPRO_ANALYSIS_MODE.md
- ✅ Create GOVERNANCE.md
- ✅ Create ADR 0012

### Phase 2: Integration
- [ ] Update CONTRIBUTING.md to reference governance
- [ ] Create .github/PULL_REQUEST_TEMPLATE.md with compliance checklist
- [ ] Create PROPOSAL_TEMPLATE.md for easy copy-paste
- [ ] Update README.md to reference governance framework

### Phase 3: Communication
- [ ] Announce governance in repository discussions
- [ ] Update documentation to link to governance docs
- [ ] Create examples of proper proposals
- [ ] Provide guidance for existing contributors

### Phase 4: Enforcement
- [ ] Review PRs for compliance
- [ ] Provide feedback on governance alignment
- [ ] Refine processes based on experience
- [ ] Update documentation as needed

## Success Metrics

### Quantitative
- **100%** of changes go through proposal process
- **<2 days** average review time for proposals
- **>90%** of proposals include proper reasoning
- **0** unauthorized file modifications
- **0** sandbox boundary violations

### Qualitative
- Contributors understand and follow governance
- Proposal quality improves over time
- Decisions are well-reasoned and documented
- Community feels empowered to contribute
- Phantom principles are consistently upheld

## Compliance with Phantom Ethos

- ✅ **Sovereignty:** Human authority explicitly preserved
- ✅ **Transparency:** All decisions documented and explained
- ✅ **Reversibility:** Proposals enable review before application
- ✅ **Modularity:** Governance documents are separate, composable
- ✅ **Minimalism:** Simplest governance that achieves goals
- ✅ **Integrity:** Architectural principles formalized
- ✅ **Human Control:** Machines propose, humans decide

## Compliance with Ten Commandments

1. ✅ **No unauthorized modifications:** Enforced by ANALYSIS-ONLY MODE
2. ✅ **Honor defined scope:** Governance defines clear boundaries
3. ✅ **Don't assume:** Halt-and-ask explicitly required
4. ✅ **Show reasoning:** Proposal format requires explanation
5. ✅ **Preserve architecture:** Principles documented and enforced
6. ✅ **Maintain modularity:** Governance supports modular changes
7. ✅ **Respect layers:** Architecture review part of process
8. ✅ **No irreversible changes:** Proposal-before-application guarantees this
9. ✅ **Defer to human:** Explicitly required in governance
10. ✅ **Protect sovereignty:** Sandbox boundary enforced

## References

- [PHANTOM_ETHOS.md](../PHANTOM_ETHOS.md) - Foundational principles
- [PHANTOM_COMMANDMENTS.md](../PHANTOM_COMMANDMENTS.md) - Operational rules
- [PHANTOM_SOUL.md](../PHANTOM_SOUL.md) - Philosophical foundation
- [GITPRO_ANALYSIS_MODE.md](../GITPRO_ANALYSIS_MODE.md) - Analysis guidelines
- [GOVERNANCE.md](../GOVERNANCE.md) - Repository governance

## Notes

This ADR establishes the governance framework for Phantom_PTR going forward. All future work in the repository should comply with these guidelines.

### For Contributors
Read the governance documents before contributing. Follow ANALYSIS-ONLY MODE. Propose changes properly. Wait for human review.

### For Maintainers
Enforce the governance fairly and consistently. Provide helpful feedback. Guide contributors toward compliance. Update governance based on experience.

### For AI Agents
Default to ANALYSIS-ONLY MODE. Use proper proposal format. Explain your reasoning. Halt when uncertain. Respect human authority.

---

## Decision

**ACCEPTED** - ANALYSIS-ONLY MODE is now the default operational constraint for Phantom_PTR.

**Effective Date:** 2026-02-17  
**Implementation:** Immediate  
**Review Date:** 2026-05-17 (quarterly)

**Approved by:** Human Architect  
**Status:** Active and Enforced
