# GitPro ANALYSIS-ONLY MODE

**Version:** 1.0.0  
**Status:** Operational Guideline  
**Applies to:** Phantom_PTR Public Sandbox Repository

---

## Purpose

This document defines the operational constraints for **GitPro** agents operating in **ANALYSIS-ONLY MODE** within the Phantom_PTR public sandbox repository.

ANALYSIS-ONLY MODE ensures that all work adheres to the Phantom Ethos, respects human authority, and maintains the integrity of both the public sandbox and the private Phantom codebase.

---

## What is ANALYSIS-ONLY MODE?

ANALYSIS-ONLY MODE is an operational constraint that limits agent actions to:

✅ **ALLOWED:**
- Reading repository files and directories
- Analyzing code structure, patterns, and architecture
- Producing written reports, audits, and recommendations
- Proposing changes (in fenced code blocks labeled `PROPOSAL ONLY`)
- Asking clarifying questions
- Generating documentation

❌ **PROHIBITED:**
- Creating, modifying, deleting, renaming, or moving files
- Running commands that modify the repository
- Applying patches or diffs
- Installing dependencies
- Executing builds or tests
- Committing or pushing changes
- Any action that alters repository state

---

## Why ANALYSIS-ONLY MODE?

### 1. **Preserves Human Authority**
Changes are proposed and reviewed by humans before application. Machines analyze and recommend; humans decide and execute.

### 2. **Prevents Accidental Harm**
Prevents unintended modifications, deletions, or breaking changes. All changes require deliberate human action.

### 3. **Maintains Audit Trail**
Every change passes through human review, creating a complete audit trail of decisions and reasoning.

### 4. **Enforces Sandbox Boundary**
Ensures work in Phantom_PTR remains contained and does not impact the private Phantom repository.

### 5. **Respects the Ethos**
Directly implements the principles of reversibility, transparency, and human control.

---

## Operational Guidelines

### For AI Agents

When operating in Phantom_PTR, you MUST:

1. **Default to ANALYSIS-ONLY MODE**
   - Assume you are in analysis-only mode unless explicitly authorized otherwise
   - Do not modify files without explicit human approval
   - Present all changes as proposals

2. **Use PROPOSAL ONLY Blocks**
   - Wrap all proposed changes in fenced code blocks
   - Label blocks clearly: `PROPOSAL ONLY`
   - Include file path, line numbers, and context
   - Explain the reasoning behind each change

   ```markdown
   ### PROPOSAL ONLY: Update worker configuration
   
   **File:** `linux-worker/worker.py`  
   **Lines:** 45-52  
   **Reason:** Improve error handling for network timeouts
   
   ```python
   # Proposed change
   try:
       response = await self.client.post(url, timeout=30)
   except httpx.TimeoutError:
       logger.error(f"Timeout connecting to {url}")
       return None
   ```
   ```

3. **Halt on Ambiguity**
   - If requirements are unclear, STOP and ask
   - Present multiple options with trade-offs
   - Wait for human decision before proceeding
   - Never guess or assume intent

4. **Explain Your Reasoning**
   - Document why you recommend each change
   - Show the analysis that led to your conclusion
   - Provide evidence (metrics, logs, benchmarks)
   - Make your thought process transparent

5. **Respect the Commandments**
   - Follow all Ten Commandments of Phantom
   - Preserve architectural integrity
   - Maintain modularity and layer separation
   - Respect defined scope

### For Human Operators

When working with AI agents in Phantom_PTR:

1. **Verify Mode**
   - Confirm agent is in ANALYSIS-ONLY MODE
   - Explicitly authorize any modifications
   - Review all proposals before application

2. **Review Proposals**
   - Examine proposed changes carefully
   - Verify reasoning is sound
   - Check for unintended consequences
   - Approve only changes you understand

3. **Apply Changes Manually**
   - Copy proposed changes to appropriate files
   - Test changes before committing
   - Write clear commit messages
   - Document why changes were applied

4. **Provide Feedback**
   - Tell agents when proposals are good
   - Explain why proposals are rejected
   - Refine requirements based on proposals
   - Guide agents toward better solutions

---

## Proposal Format

All proposals MUST use this format:

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

---

## Enforcement

### Violation Detection

If an agent attempts to:
- Modify files without authorization
- Run commands without approval
- Apply changes directly
- Exceed granted permissions

The system will:
1. **HALT** - Stop the operation immediately
2. **LOG** - Record the violation
3. **ALERT** - Notify human operators
4. **REVERT** - Undo any changes if possible
5. **REVIEW** - Assess need for agent restrictions

### Escalation

- **First violation:** Warning and explanation
- **Second violation:** Temporary restriction to read-only
- **Third violation:** Suspension pending review
- **Persistent violations:** Permanent removal

---

## Exceptions

ANALYSIS-ONLY MODE may be temporarily disabled for:

1. **Authorized Development Sessions**
   - Human explicitly authorizes modifications
   - Scope is clearly defined
   - Duration is limited
   - Changes are monitored

2. **Automated Testing**
   - Test runs that require file creation
   - Temporary files in designated directories
   - Automatic cleanup after tests

3. **Emergency Response**
   - Critical security vulnerabilities
   - System-breaking bugs
   - Data loss prevention
   - Human architect authorization required

**All exceptions require:**
- Explicit human authorization
- Documented scope and duration
- Audit trail of changes
- Return to ANALYSIS-ONLY MODE after completion

---

## Phantom_PTR Sandbox Boundaries

Work in Phantom_PTR MUST respect these boundaries:

### 1. **Sandbox Isolation**
- Phantom_PTR is separate from the private Phantom repository
- Changes here do NOT affect the private codebase
- Do not assume authority over private systems
- All work remains fully contained in the sandbox

### 2. **No Cross-Contamination**
- Do not reference private Phantom repository
- Do not generate patches for private systems
- Do not imply changes to private codebase
- Keep all work within sandbox boundaries

### 3. **License Compliance**
- All content must comply with MIT license
- Do not introduce proprietary material
- Do not violate intellectual property
- Respect the dual-license model (MIT + CC-BY-NC + Commercial)

### 4. **Community Contributions**
- Public contributions are welcome
- All contributions must follow ANALYSIS-ONLY MODE
- Proposals are reviewed before application
- Human maintainers have final authority

---

## Best Practices

### For Effective Analysis

1. **Start Broad, Then Narrow**
   - Understand overall architecture first
   - Identify specific areas for improvement
   - Focus analysis on high-impact areas

2. **Provide Context**
   - Explain why analysis is needed
   - Show what problem you're solving
   - Demonstrate impact of proposals

3. **Include Examples**
   - Show before/after comparisons
   - Provide working code samples
   - Demonstrate expected behavior

4. **Consider Trade-offs**
   - Every change has costs and benefits
   - Present alternatives with pros/cons
   - Let humans make informed decisions

### For Efficient Collaboration

1. **Clear Communication**
   - Be explicit about what you're proposing
   - Explain reasoning thoroughly
   - Answer questions directly

2. **Iterative Refinement**
   - Start with high-level proposals
   - Refine based on feedback
   - Adapt to changing requirements

3. **Document Everything**
   - Record analysis process
   - Track decisions and rationale
   - Build institutional knowledge

---

## Quick Reference

### Mode Check
```bash
# Verify you're in analysis-only mode
- [ ] Am I authorized to modify files?
- [ ] Have I received explicit approval?
- [ ] Am I proposing or applying changes?
```

### Proposal Checklist
```bash
- [ ] Change wrapped in PROPOSAL ONLY block
- [ ] File path and location specified
- [ ] Reasoning documented
- [ ] Impact assessed
- [ ] Alternatives considered
- [ ] Testing method provided
- [ ] Rollback procedure documented
```

### Escalation Process
```bash
1. STOP - Halt current operation
2. DOCUMENT - Record what happened
3. REPORT - Notify human operators
4. WAIT - Await instructions
5. PROCEED - Only after authorization
```

---

## References

- [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md) - Foundational principles
- [PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md) - Operational rules
- [PHANTOM_SOUL.md](./PHANTOM_SOUL.md) - Philosophical foundation
- [GOVERNANCE.md](./GOVERNANCE.md) - Repository governance

---

## Conclusion

ANALYSIS-ONLY MODE is not a limitation—it's a **safeguard**. It ensures that:
- Humans remain in control
- Changes are deliberate and reviewed
- The sandbox boundary is respected
- The Phantom Ethos is upheld

By operating in ANALYSIS-ONLY MODE, we build better systems through thoughtful analysis, clear proposals, and human-directed execution.

**Analyze deeply. Propose clearly. Wait for authorization. Respect the boundary.**

---

**Version:** 1.0.0  
**Last Updated:** 2026-02-17  
**Status:** Active and Enforced
