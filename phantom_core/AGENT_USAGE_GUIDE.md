# Agent Usage and Best Practices Guide

**Version**: 1.0.0  
**Status**: Operational Guide  
**Applies to**: Phantom_PTR Repository  
**Date**: 2026-02-18

---

## Purpose

This guide provides best practices for using AI agents (like GitHub Copilot) when contributing to the Phantom_PTR repository. Following these guidelines prevents branch bloat, maintains code quality, and ensures compliance with PHANTOM_ETHOS.md and PHANTOM_COMMANDMENTS.md.

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [Branching Strategy](#branching-strategy)
3. [Agent Workflow](#agent-workflow)
4. [Execution Mode Development](#execution-mode-development)
5. [Common Pitfalls](#common-pitfalls)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Core Principles

### The Three Laws of Agent Usage

1. **One Task, One Branch**: Each task gets a single focused branch
2. **Merge or Delete**: Branches are merged to `main` or deleted—no orphans
3. **Human Final Authority**: Agents propose, humans decide

### Compliance Requirements

All agent work must comply with:
- **PHANTOM_ETHOS.md** - Sovereignty, transparency, reversibility
- **PHANTOM_COMMANDMENTS.md** - No unauthorized modifications, honor scope
- **GITPRO_ANALYSIS_MODE.md** - Analysis-first approach when appropriate

---

## Branching Strategy

### Branch Types and Lifecycle

#### Permanent Branches
- `main` - Production-ready code (protected)
- `phantom-1` - Long-term feature branch (protected)

**Never develop directly on permanent branches.**

#### Task Branches (Temporary)
Format: `{type}/{short-description}`

```
Types:
├── feature/    → New features or capabilities
├── fix/        → Bug fixes
├── docs/       → Documentation changes
├── refactor/   → Code refactoring (no behavior change)
├── test/       → Test additions/improvements
├── chore/      → Maintenance tasks
└── copilot/    → Copilot agent tasks
```

**Examples:**
```bash
feature/hybrid-execution-mode
fix/socket-reconnection-timeout
docs/api-specification-update
refactor/worker-selection-logic
test/execution-mode-coverage
copilot/cleanup-branches-and-execution-modes
```

### Branch Naming Rules

✅ **Good Names:**
- Short (< 50 characters)
- Descriptive
- Lowercase with hyphens
- Indicates purpose

```bash
feature/manual-worker-selection
fix/memory-leak-in-socket-manager
docs/execution-modes-guide
```

❌ **Bad Names:**
- Too generic: `fix-bug`, `update-code`
- Too long: `feature/add-the-new-hybrid-execution-mode-that-allows-human-approval`
- Poor format: `FeatureNewMode`, `fix_socket_bug`
- Unclear: `temp`, `test`, `wip`

### Branch Lifecycle Management

#### 1. Create Branch
```bash
# Start from latest main
git checkout main
git pull origin main

# Create task branch
git checkout -b feature/hybrid-execution-mode
```

#### 2. Develop
- Make focused commits
- Test changes incrementally
- Update documentation alongside code

#### 3. Pull Request
- Create PR from task branch to `main`
- Write clear PR description
- Link related issues
- Request review from human maintainers

#### 4. Review and Merge
- Address review feedback
- Ensure CI passes
- Human maintainer merges PR
- Celebrate! 🎉

#### 5. Cleanup
```bash
# After merge, delete local branch
git checkout main
git pull origin main
git branch -d feature/hybrid-execution-mode

# Remote branch auto-deleted by GitHub (if configured)
```

**Typical Lifespan**: 1-7 days (not months!)

---

## Agent Workflow

### Step-by-Step Process

#### Phase 1: Understanding (ANALYSIS-ONLY)
```
1. Read issue/task description thoroughly
2. Explore codebase (read-only)
3. Understand existing patterns
4. Identify affected files
5. Plan minimal changes
```

**Agent Mode**: ANALYSIS-ONLY (no modifications)

#### Phase 2: Planning
```
1. Create task branch
2. Document plan as checklist in PR description
3. Get human approval for plan
4. Proceed with implementation
```

#### Phase 3: Implementation
```
For each item in plan:
  1. Make minimal focused change
  2. Test change in isolation
  3. Commit with clear message
  4. Report progress
  5. Repeat until complete
```

#### Phase 4: Validation
```
1. Run linters and formatters
2. Run test suite
3. Manual smoke testing
4. Request code review
5. Address feedback
```

#### Phase 5: Completion
```
1. Final validation
2. Update documentation
3. Clean commit history (if needed)
4. Mark PR as ready for review
5. Wait for human approval and merge
```

### Progress Reporting Pattern

Use `report_progress` tool frequently:

```python
# Initial plan
report_progress(
    commitMessage="Initial plan for hybrid execution mode",
    prDescription="""
    ## Implementation Plan
    - [ ] Create execution mode schema document
    - [ ] Add HYBRID mode to controller API
    - [ ] Implement proposal generation
    - [ ] Add approval endpoints
    - [ ] Create tests
    - [ ] Update documentation
    """
)

# After each completed item
report_progress(
    commitMessage="Add HYBRID mode proposal generation",
    prDescription="""
    ## Implementation Plan
    - [x] Create execution mode schema document
    - [x] Add HYBRID mode to controller API
    - [x] Implement proposal generation  ← COMPLETED
    - [ ] Add approval endpoints
    - [ ] Create tests
    - [ ] Update documentation
    """
)
```

---

## Execution Mode Development

### How to Add New Execution Modes

Following the pattern established in `PHANTOM_EXECUTION_MODES_AND_API_SPEC.md`:

#### 1. Define Mode Specification

Create or update specification document:

```markdown
### N. [MODE_NAME] Mode ([Description])

#### Description
[What the mode does]

#### Decision Flow
[ASCII flow diagram]

#### Features
- [Feature 1]
- [Feature 2]

#### Configuration
[YAML configuration]

#### API Endpoints
[API specifications]

#### Compliance
[PHANTOM_ETHOS compliance checklist]
```

#### 2. Implement Mode Logic

**File**: `phantom_core/controller_api.py`

```python
async def select_worker_for_task(task: TaskRequest) -> Optional[str]:
    """Enhanced worker selection with execution mode support"""
    
    # Get execution mode (from task or system default)
    mode = task.execution_mode or get_system_execution_mode()
    
    if mode == "auto":
        return await auto_mode_worker_selection(task)
    elif mode == "hybrid":
        return await hybrid_mode_worker_selection(task)
    elif mode == "manual":
        return await manual_mode_worker_selection(task)
    else:
        raise ValueError(f"Unknown execution mode: {mode}")

async def hybrid_mode_worker_selection(task: TaskRequest) -> Optional[str]:
    """HYBRID mode: Generate proposal, wait for human approval"""
    # 1. Generate worker proposal
    proposal = await generate_worker_proposal(task)
    
    # 2. Store proposal with expiration
    await store_proposal(task.task_id, proposal)
    
    # 3. Notify via WebSocket
    if socket_manager:
        await socket_manager.broadcast({
            "type": "proposal_ready",
            "task_id": task.task_id,
            "proposal": proposal
        })
    
    # 4. Return None (task waits for approval)
    return None
```

#### 3. Add API Endpoints

```python
@app.post("/tasks/{task_id}/approve")
async def approve_proposal(
    task_id: str,
    approval: ApprovalRequest
):
    """Approve a task proposal in HYBRID mode"""
    # Validate task exists and is pending approval
    task = tasks.get(task_id)
    if not task or task["status"] != "pending_approval":
        raise HTTPException(404, "No pending proposal found")
    
    # Apply approval
    task["status"] = "queued"
    task["worker_id"] = approval.approved_worker
    task["approved_by"] = approval.approver
    
    # Log approval
    log_approval(task_id, approval)
    
    # Execute task
    await execute_task(task_id, task["worker_id"], task)
    
    return {"status": "approved", "task_id": task_id}
```

#### 4. Update Configuration

**File**: `phantom_config.yaml`

```yaml
execution:
  # System-wide default mode
  default_mode: auto  # auto | hybrid | manual
  
  # Allow per-task mode override
  allow_task_override: true
  
  # HYBRID mode settings
  hybrid:
    proposal_timeout: 300  # seconds
    require_approval_reason: false
    auto_expire: true
  
  # MANUAL mode settings
  manual:
    validate_worker: true
    warn_suboptimal: true
    block_offline: true
```

#### 5. Add WebSocket Support

**File**: `phantom_core/socket_integration.py`

```python
async def handle_mode_message(self, message: Dict[str, Any]):
    """Handle execution mode related messages"""
    msg_type = message.get("type")
    
    if msg_type == "proposal_ready":
        # Broadcast to UI clients
        await self.broadcast_to_ui(message)
    
    elif msg_type == "approval_request":
        # Process approval request
        await self.process_approval(message)
```

#### 6. Create Tests

**File**: `tests/test_execution_modes.py`

```python
import pytest
from phantom_core.controller_api import app
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_hybrid_mode_proposal_generation():
    """Test HYBRID mode generates proposals correctly"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Submit task in HYBRID mode
        response = await client.post("/tasks/submit", json={
            "task_type": "ml_inference",
            "parameters": {},
            "execution_mode": "hybrid"
        })
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending_approval"
        assert "proposal" in data
        assert data["proposal"]["proposed_worker"]

@pytest.mark.asyncio
async def test_manual_mode_requires_worker():
    """Test MANUAL mode requires target_worker"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Submit task without target_worker
        response = await client.post("/tasks/submit", json={
            "task_type": "ml_inference",
            "parameters": {},
            "execution_mode": "manual"
        })
        
        assert response.status_code == 422
        assert "target_worker" in response.json()["error"]
```

#### 7. Update Documentation

- Add mode to README.md
- Update API documentation
- Include usage examples
- Document configuration options

### Pattern Summary

```
1. Specification → Define behavior and API
2. Implementation → Add logic to controller
3. Endpoints → Create REST API
4. Configuration → Add config options
5. WebSocket → Enable real-time updates
6. Tests → Validate functionality
7. Documentation → Guide users
```

This pattern is **extensible** - follow it to add future modes without breaking existing ones.

---

## Common Pitfalls

### ❌ Pitfall 1: Creating Multiple Branches for One Task

**Problem:**
```bash
copilot/add-hybrid-mode
copilot/hybrid-mode-fix
copilot/hybrid-mode-attempt-2
copilot/hybrid-mode-final
```

**Solution:**
- Use ONE branch per task
- Fix issues on the same branch
- Force push if needed (before PR merge)

```bash
# Work on same branch
git checkout copilot/add-hybrid-mode
# Make fixes
git commit -m "Fix hybrid mode validation"
git push origin copilot/add-hybrid-mode
```

### ❌ Pitfall 2: Expanding Scope Without Authorization

**Problem:**
Agent notices a bug while implementing hybrid mode and "helpfully" fixes it too.

**Solution:**
- Honor defined scope (COMMANDMENT II)
- Create separate issue/branch for unrelated fixes
- Ask human: "Should I fix this too, or create separate issue?"

### ❌ Pitfall 3: Not Deleting Branches After Merge

**Problem:**
Branch merged to `main` but branch still exists, causing clutter.

**Solution:**
- Enable GitHub "Auto-delete head branches" setting
- Manually delete local branches after merge
- Use `git branch -d` to clean up

### ❌ Pitfall 4: Making Assumptions on Ambiguous Requirements

**Problem:**
Issue says "implement hybrid mode" but doesn't specify approval timeout behavior.

**Solution:**
- HALT and ASK (COMMANDMENT III)
- Present options: "Should proposal timeout be 5min or 10min?"
- Wait for human decision
- Document decision in PR

### ❌ Pitfall 5: Modifying Files Without Understanding

**Problem:**
Agent changes file without reading related code or understanding patterns.

**Solution:**
- ALWAYS explore codebase first
- Use ANALYSIS-ONLY mode initially
- Understand existing patterns
- Match coding style
- Ask if unsure

---

## Best Practices

### ✅ DO: Minimal Changes

Make **smallest possible changes** to achieve goal:

```python
# ✅ Good: Minimal change
if execution_mode == "hybrid":
    return await hybrid_mode_selection(task)

# ❌ Bad: Unnecessary refactoring
def select_worker_with_mode_support(task, mode, config, logger, metrics):
    # ... 50 lines of refactored code ...
```

### ✅ DO: Incremental Commits

Small, focused commits with clear messages:

```bash
git commit -m "Add HYBRID mode enum to configuration"
git commit -m "Implement proposal generation logic"
git commit -m "Add approval endpoint"
git commit -m "Create HYBRID mode tests"
```

### ✅ DO: Test Early and Often

Don't wait until the end:

```bash
# After each change
python -m pytest tests/test_execution_modes.py::test_hybrid_mode -v

# Before final PR
python -m pytest tests/ -v
```

### ✅ DO: Follow Existing Patterns

Match established code style:

```python
# Existing pattern in codebase
@app.post("/workers/register")
async def register_worker(worker: WorkerInfo):
    """Register a new worker"""
    # ...

# Your new code (matching pattern)
@app.post("/tasks/{task_id}/approve")
async def approve_proposal(task_id: str, approval: ApprovalRequest):
    """Approve a task proposal"""
    # ...
```

### ✅ DO: Document Why, Not Just What

```python
# ✅ Good: Explains reasoning
# HYBRID mode requires proposal timeout to prevent
# indefinitely pending tasks. Default 5 minutes based
# on typical human response time analysis.
PROPOSAL_TIMEOUT = 300  # seconds

# ❌ Bad: Just states obvious
# Timeout is 300 seconds
PROPOSAL_TIMEOUT = 300
```

### ✅ DO: Report Progress Frequently

Update PR description as you work:

```markdown
## Progress
- [x] Create specification document
- [x] Add HYBRID mode configuration
- [x] Implement proposal generation  ← JUST COMPLETED
- [ ] Add approval endpoint
- [ ] Create tests
```

This shows humans where you are and builds confidence.

---

## Troubleshooting

### Problem: "Cannot create branch - already exists"

```bash
# Branch exists locally
git branch -D copilot/my-task
git fetch origin
git checkout -b copilot/my-task
```

### Problem: "Merge conflict"

```bash
# Update your branch with latest main
git checkout copilot/my-task
git fetch origin main
git merge origin/main

# Resolve conflicts in editor
# Then commit
git add .
git commit -m "Resolve merge conflicts"
git push
```

### Problem: "CI fails after my changes"

```bash
# Run tests locally first
python -m pytest tests/ -v
python -m black . --check
python -m flake8 .

# Fix issues
python -m black .  # Auto-format

# Commit fixes
git add .
git commit -m "Fix CI issues"
git push
```

### Problem: "Accidentally committed to main"

```bash
# Move commits to new branch
git checkout main
git checkout -b feature/my-feature

# Reset main (ONLY if not pushed!)
git checkout main
git reset --hard origin/main
```

⚠️ **Never force push to `main` or `phantom-1`!**

---

## Quick Reference

### Branch Workflow Cheatsheet

```bash
# 1. Start new task
git checkout main
git pull origin main
git checkout -b feature/my-feature

# 2. Make changes
# ... edit files ...
git add .
git commit -m "Clear description"

# 3. Push to GitHub
git push -u origin feature/my-feature

# 4. Create PR on GitHub
# - Go to repository
# - Click "Compare & pull request"
# - Fill in description
# - Request review

# 5. After merge
git checkout main
git pull origin main
git branch -d feature/my-feature
```

### Agent Checklist

Before starting any task:

- [ ] Read and understand the issue
- [ ] Explore codebase (ANALYSIS-ONLY)
- [ ] Identify minimal changes needed
- [ ] Create focused task branch
- [ ] Check out from latest `main`
- [ ] Create initial plan in PR description

While working:

- [ ] Make small, focused commits
- [ ] Test changes incrementally
- [ ] Report progress frequently
- [ ] Stay within defined scope
- [ ] Follow existing code patterns
- [ ] Document decisions

Before PR submission:

- [ ] Run full test suite
- [ ] Run linters/formatters
- [ ] Update documentation
- [ ] Review all changes
- [ ] Write clear PR description
- [ ] Link related issues

After merge:

- [ ] Verify merge completed
- [ ] Delete task branch
- [ ] Close related issues

---

## Summary

**Golden Rules for Agent Usage:**

1. 📝 **Plan First** - Understand before implementing
2. 🌲 **One Task, One Branch** - Focused work prevents clutter
3. 🔄 **Small Commits** - Incremental progress is safer
4. ✅ **Test Continuously** - Catch issues early
5. 📖 **Document Everything** - Future you will thank present you
6. 🤝 **Follow Patterns** - Match existing code style
7. 🛑 **Halt on Ambiguity** - Ask, don't assume
8. 🗑️ **Clean Up** - Delete branches after merge
9. 👤 **Human Authority** - Agents propose, humans decide
10. 📏 **Minimal Changes** - Smallest solution that works

Following these practices keeps the repository clean, maintainable, and aligned with PHANTOM_ETHOS principles.

---

## References

- [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md) - Core principles
- [PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md) - Operational rules
- [GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md) - Analysis mode
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution guidelines
- [BRANCH_INVENTORY.md](./BRANCH_INVENTORY.md) - Branch management
- [PHANTOM_EXECUTION_MODES_AND_API_SPEC.md](./PHANTOM_EXECUTION_MODES_AND_API_SPEC.md) - Execution modes

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-18  
**Status**: Active Guide

**Remember**: Machines propose. Humans decide. Clean branches win. 🚀
