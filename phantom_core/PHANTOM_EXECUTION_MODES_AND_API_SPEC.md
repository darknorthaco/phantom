# PHANTOM Execution Modes and API Specification

**Version**: 1.0.0  
**Status**: Authoritative  
**Applies to**: Phantom_PTR Distributed Compute Fabric  
**Date**: 2026-02-18

---

## Purpose

This document defines the three execution modes for the Phantom distributed compute system, their operational semantics, API specifications, and governance requirements. These modes implement the core principles of PHANTOM_ETHOS.md by providing progressive levels of automation and human control.

---

## Overview

Phantom supports **three execution modes** that determine how task routing and worker selection decisions are made:

| Mode | Description | Human Involvement | Primary Use Case |
|------|-------------|-------------------|------------------|
| **AUTO** | Fully automated | None (monitoring only) | Production workloads, trusted environments |
| **HYBRID** | Human-governed | Approval required for routing | Development, testing, audit scenarios |
| **MANUAL** | Full human control | Manual worker selection | Debugging, experimentation, training |

---

## Core Principles

All execution modes comply with PHANTOM_ETHOS.md:

1. **Sovereignty** - Humans retain ultimate control in all modes
2. **Transparency** - All decisions are logged and auditable
3. **Reversibility** - Mode changes and task routing are reversible
4. **Human Control** - Modes progressively grant/restrict automation
5. **Minimalism** - Simplest appropriate mode for each scenario

---

## Execution Mode Definitions

### 1. AUTO Mode (Fully Automated)

**Status**: ✅ **IMPLEMENTED**

#### Description
Fully automated task routing with no human intervention required. The system autonomously selects optimal workers based on AI-powered or algorithmic routing.

#### Decision Flow
```
Task Submitted → AUTO Mode Check → Routing Algorithm → Worker Selected → Task Executed
                                   ↓
                        LLM Task Master (if available)
                                   ↓
                        Smart Programming Fallback
```

#### Features
- **LLM Task Master Integration**: AI-powered routing decisions via GTX 1080 worker
- **Smart Programming Fallback**: GPU-aware algorithmic selection if LLM unavailable
- **Zero-Latency**: Immediate task execution
- **Performance Tracking**: Learning from historical task performance
- **Load Balancing**: Automatic distribution across available workers

#### Configuration
```yaml
execution_mode: auto
enable_llm_taskmaster: true  # Optional: use LLM for routing
fallback_to_smart: true      # Use algorithmic routing if LLM fails
```

#### Environment Variables
```bash
PHANTOM_EXECUTION_MODE=auto
ENABLE_LLM_TASKMASTER=true
PHANTOM_INTEGRATED=true  # Required for socket-based LLM routing
```

#### API Behavior
- Task submission returns immediately with `task_id`
- Worker selection is automatic and transparent
- Status updates via WebSocket or polling

#### Compliance
- ✅ Sovereignty: Human operator can monitor and halt
- ✅ Transparency: All routing decisions logged
- ✅ Reversibility: Tasks can be cancelled, mode changed
- ✅ Minimalism: Most efficient for production workloads

---

### 2. HYBRID Mode (Human-Governed)

**Status**: ✅ **IMPLEMENTED** (this PR)

#### Description
Semi-automated workflow where the system proposes worker selections but requires human approval before execution. This mode implements the "propose-then-approve" pattern from PHANTOM_ETHOS.md.

#### Decision Flow
```
Task Submitted → HYBRID Mode Check → System Proposes Worker(s)
                                            ↓
                                     Human Reviews Proposal
                                            ↓
                                   Approve | Reject | Override
                                            ↓
                                     Task Executed (if approved)
```

#### Features
- **Proposal Generation**: System generates worker recommendation with reasoning
- **Human Approval**: Required before task execution
- **Override Capability**: Human can select different worker than proposed
- **Approval Timeout**: Tasks expire if not approved within configured time
- **Batch Approval**: Multiple tasks can be approved simultaneously
- **Audit Trail**: All approvals/rejections logged with human identity

#### Configuration
```yaml
execution_mode: hybrid
proposal_timeout: 300  # seconds (5 minutes default)
require_approval_reason: false  # Require human to provide approval reason
auto_expire_proposals: true     # Automatically expire old proposals
batch_approval_enabled: true    # Allow approving multiple tasks at once
```

#### Environment Variables
```bash
PHANTOM_EXECUTION_MODE=hybrid
HYBRID_PROPOSAL_TIMEOUT=300
HYBRID_REQUIRE_REASON=false
```

#### API Endpoints

##### Submit Task (HYBRID Mode)
```http
POST /tasks/submit
Content-Type: application/json

{
  "task_type": "ml_inference",
  "parameters": {...},
  "priority": 1,
  "execution_mode": "hybrid"  # Optional: override system default
}

Response (202 Accepted):
{
  "task_id": "uuid-1234",
  "status": "pending_approval",
  "proposal": {
    "proposed_worker": "worker-gpu-1080",
    "reasoning": "GTX 1080 optimal for this ML inference task (8GB VRAM, current load: 20%)",
    "alternatives": [
      {
        "worker_id": "worker-gpu-5080",
        "score": 0.85,
        "reason": "Higher performance but currently at 60% load"
      }
    ],
    "expires_at": "2026-02-18T16:38:17Z"
  },
  "approval_required": true
}
```

##### Get Pending Proposals
```http
GET /tasks/proposals

Response (200 OK):
{
  "proposals": [
    {
      "task_id": "uuid-1234",
      "task_type": "ml_inference",
      "submitted_at": "2026-02-18T16:33:17Z",
      "expires_at": "2026-02-18T16:38:17Z",
      "proposed_worker": "worker-gpu-1080",
      "reasoning": "...",
      "alternatives": [...]
    }
  ],
  "count": 1
}
```

##### Approve Proposal
```http
POST /tasks/{task_id}/approve
Content-Type: application/json

{
  "approved_worker": "worker-gpu-1080",  # Optional: override proposal
  "approval_reason": "Confirmed optimal for this workload",  # Optional
  "approver": "human-operator-1"
}

Response (200 OK):
{
  "task_id": "uuid-1234",
  "status": "queued",
  "worker_id": "worker-gpu-1080",
  "approved_at": "2026-02-18T16:34:17Z",
  "approved_by": "human-operator-1"
}
```

##### Reject Proposal
```http
POST /tasks/{task_id}/reject
Content-Type: application/json

{
  "rejection_reason": "Task no longer needed",
  "rejector": "human-operator-1"
}

Response (200 OK):
{
  "task_id": "uuid-1234",
  "status": "rejected",
  "rejected_at": "2026-02-18T16:34:17Z",
  "rejected_by": "human-operator-1"
}
```

##### Batch Approve
```http
POST /tasks/batch-approve
Content-Type: application/json

{
  "task_ids": ["uuid-1234", "uuid-5678"],
  "approver": "human-operator-1",
  "approval_reason": "Batch approval for routine ML tasks"
}

Response (200 OK):
{
  "approved_count": 2,
  "failed_count": 0,
  "results": [
    {"task_id": "uuid-1234", "status": "approved"},
    {"task_id": "uuid-5678", "status": "approved"}
  ]
}
```

#### WebSocket Messages (HYBRID Mode)

##### Proposal Notification
```json
{
  "type": "proposal_ready",
  "task_id": "uuid-1234",
  "proposed_worker": "worker-gpu-1080",
  "reasoning": "...",
  "expires_at": "2026-02-18T16:38:17Z",
  "requires_approval": true
}
```

##### Approval Result
```json
{
  "type": "proposal_approved",
  "task_id": "uuid-1234",
  "approved_worker": "worker-gpu-1080",
  "approved_by": "human-operator-1",
  "approved_at": "2026-02-18T16:34:17Z"
}
```

##### Proposal Expired
```json
{
  "type": "proposal_expired",
  "task_id": "uuid-1234",
  "expired_at": "2026-02-18T16:38:17Z",
  "reason": "No approval received within timeout period"
}
```

#### Compliance
- ✅ Sovereignty: Human approval required for all task execution
- ✅ Transparency: Full visibility into routing proposals and reasoning
- ✅ Reversibility: Tasks rejected before execution are never run
- ✅ Human Control: Explicit approval workflow enforced
- ✅ Audit-First: Propose, review, approve, apply workflow

---

### 3. MANUAL Mode (Full Human Control)

**Status**: ✅ **IMPLEMENTED** (this PR)

#### Description
Fully manual worker selection where humans directly specify which worker should execute each task. The system provides no routing recommendations, only validation and execution.

#### Decision Flow
```
Task Submitted → MANUAL Mode Check → Human Specifies Worker
                                            ↓
                                   System Validates Worker
                                            ↓
                              Available ✓ | Unavailable ✗
                                            ↓
                                     Task Executed (if valid)
```

#### Features
- **Direct Worker Selection**: Human specifies exact worker in task submission
- **Validation Only**: System validates worker exists and is available
- **No Routing Algorithm**: System makes no routing decisions
- **Warnings**: System warns if selected worker is suboptimal (non-blocking)
- **Override Protection**: Safeguards prevent obviously harmful selections
- **Training Mode**: Ideal for learning system behavior and debugging

#### Configuration
```yaml
execution_mode: manual
validate_worker_availability: true
warn_suboptimal_selection: true
block_offline_workers: true
allow_worker_override: true  # Override warnings and proceed anyway
```

#### Environment Variables
```bash
PHANTOM_EXECUTION_MODE=manual
MANUAL_VALIDATE_WORKER=true
MANUAL_WARN_SUBOPTIMAL=true
```

#### API Endpoints

##### Submit Task (MANUAL Mode)
```http
POST /tasks/submit
Content-Type: application/json

{
  "task_type": "ml_inference",
  "parameters": {...},
  "priority": 1,
  "execution_mode": "manual",
  "target_worker": "worker-gpu-5080",  # REQUIRED in manual mode
  "override_warnings": false            # Optional: force execution despite warnings
}

Response (200 OK - Worker Available):
{
  "task_id": "uuid-1234",
  "status": "queued",
  "worker_id": "worker-gpu-5080",
  "mode": "manual",
  "warnings": []
}

Response (200 OK - Worker Available with Warnings):
{
  "task_id": "uuid-1234",
  "status": "queued",
  "worker_id": "worker-gpu-firepro",
  "mode": "manual",
  "warnings": [
    {
      "level": "warning",
      "message": "Selected worker 'worker-gpu-firepro' is suboptimal for task type 'ml_inference'",
      "recommendation": "Consider 'worker-gpu-5080' (85% better performance)",
      "blocking": false
    }
  ]
}

Response (400 Bad Request - Worker Unavailable):
{
  "error": "Worker unavailable",
  "details": {
    "requested_worker": "worker-gpu-1080",
    "status": "offline",
    "available_workers": ["worker-gpu-5080", "worker-gpu-5060"],
    "can_override": false
  }
}

Response (422 Unprocessable Entity - No Worker Specified):
{
  "error": "Manual mode requires target_worker",
  "message": "When execution_mode is 'manual', target_worker must be specified",
  "execution_mode": "manual"
}
```

##### List Available Workers
```http
GET /workers/available

Response (200 OK):
{
  "workers": [
    {
      "worker_id": "worker-gpu-5080",
      "status": "active",
      "gpu_info": {
        "name": "NVIDIA RTX 5080",
        "memory_total": 24576,
        "memory_free": 22000,
        "utilization": 10.5
      },
      "current_tasks": 1,
      "recommended_for": ["ml_inference", "training", "image_processing"]
    },
    {...}
  ]
}
```

##### Validate Worker Selection
```http
POST /workers/validate
Content-Type: application/json

{
  "worker_id": "worker-gpu-firepro",
  "task_type": "ml_inference"
}

Response (200 OK):
{
  "valid": true,
  "worker_id": "worker-gpu-firepro",
  "available": true,
  "warnings": [
    {
      "level": "info",
      "message": "Worker 'worker-gpu-firepro' is better suited for 'data_processing' tasks",
      "optimal_for": ["data_processing", "general"]
    }
  ],
  "performance_estimate": {
    "expected_score": 0.65,
    "optimal_score": 0.95,
    "efficiency": "68%"
  }
}
```

#### Warning Levels

| Level | Blocking | Description | Example |
|-------|----------|-------------|---------|
| **info** | No | Informational only | "Worker is available but not optimal" |
| **warning** | No | Suboptimal selection | "Worker has high current load" |
| **error** | Yes | Invalid selection | "Worker is offline or does not exist" |
| **critical** | Yes | Dangerous selection | "Worker lacks required GPU memory" |

#### Safeguards

MANUAL mode includes safeguards to prevent obviously harmful decisions:

1. **Offline Worker Block**: Cannot assign tasks to offline workers (unless overridden)
2. **Memory Validation**: Warns if worker GPU memory insufficient for task
3. **Compatibility Check**: Validates worker supports required task capabilities
4. **Load Warning**: Warns if worker is heavily loaded (>80% utilization)

**Override**: Set `override_warnings: true` to bypass non-blocking warnings.

#### Compliance
- ✅ Sovereignty: Human has absolute control over routing
- ✅ Transparency: System explains why selections may be suboptimal
- ✅ Reversibility: Task assignments can be changed before execution
- ✅ Human Control: Maximum human authority over system
- ✅ Safety: Safeguards prevent dangerous selections while preserving control

---

## Mode Comparison Matrix

| Feature | AUTO | HYBRID | MANUAL |
|---------|------|--------|--------|
| **Human Approval Required** | No | Yes | No |
| **Routing Algorithm** | AI + Smart | AI + Smart (proposal) | None (human decides) |
| **Worker Specified in Request** | Optional | Optional | Required |
| **System Generates Recommendations** | Yes (internal) | Yes (explicit) | No |
| **Validation** | Internal | Proposal review | Worker availability |
| **Latency** | Lowest | Medium (approval wait) | Low |
| **Audit Trail** | Automatic | Automatic + Approval logs | Automatic |
| **Warnings** | None | In proposal | Explicit |
| **Best For** | Production | Development, Testing | Debugging, Training |

---

## Mode Selection Guidelines

### Use AUTO Mode When:
- ✅ Production workloads with trusted system
- ✅ High-throughput task processing required
- ✅ System has proven routing reliability
- ✅ Human monitoring available but not intervention
- ✅ Performance is critical

### Use HYBRID Mode When:
- ✅ Development and testing environments
- ✅ Audit and compliance requirements mandate human review
- ✅ Training new operators on system behavior
- ✅ High-value or sensitive workloads
- ✅ System reliability is being validated
- ✅ Learning system routing patterns

### Use MANUAL Mode When:
- ✅ Debugging routing issues
- ✅ Experimenting with worker capabilities
- ✅ Testing specific worker performance
- ✅ Training sessions for new users
- ✅ Developing new routing algorithms
- ✅ Forcing specific worker for benchmarking

---

## Configuration

### Global Execution Mode

Set system-wide default execution mode:

**Environment Variable:**
```bash
export PHANTOM_EXECUTION_MODE=auto  # auto | hybrid | manual
```

**Configuration File (`phantom_config.yaml`):**
```yaml
execution:
  default_mode: auto  # System default
  allow_per_task_override: true  # Allow tasks to specify their own mode
  mode_change_log: true  # Log all mode changes
```

### Per-Task Mode Override

Tasks can override the system default mode:

```python
task = {
    "task_type": "ml_inference",
    "parameters": {...},
    "execution_mode": "hybrid",  # Override system default
    "target_worker": "worker-gpu-5080"  # Only used in manual mode
}
```

### Mode Change Governance

Following PHANTOM_COMMANDMENTS.md, mode changes must be:

1. **Logged**: All mode changes recorded with timestamp, user, and reason
2. **Reversible**: Previous mode can be restored
3. **Authorized**: Only authorized users can change system-wide mode
4. **Auditable**: Complete history of mode changes maintained

#### API Endpoint: Change System Mode
```http
POST /system/execution-mode
Content-Type: application/json
Authorization: Bearer <admin-token>

{
  "mode": "hybrid",
  "reason": "Switching to hybrid for testing new routing algorithm",
  "changed_by": "admin-user-1",
  "effective_immediately": true
}

Response (200 OK):
{
  "previous_mode": "auto",
  "new_mode": "hybrid",
  "changed_at": "2026-02-18T16:35:17Z",
  "changed_by": "admin-user-1",
  "reason": "Switching to hybrid for testing new routing algorithm"
}
```

#### Mode Change Log Entry
```json
{
  "timestamp": "2026-02-18T16:35:17Z",
  "previous_mode": "auto",
  "new_mode": "hybrid",
  "changed_by": "admin-user-1",
  "reason": "Switching to hybrid for testing new routing algorithm",
  "affected_tasks": 0,
  "system_state": "running"
}
```

---

## API Schemas

### Task Submission Schema (Unified)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "task_type": {
      "type": "string",
      "enum": ["ml_inference", "training", "image_processing", "data_processing", "general"]
    },
    "parameters": {
      "type": "object",
      "description": "Task-specific parameters"
    },
    "priority": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "default": 1
    },
    "execution_mode": {
      "type": "string",
      "enum": ["auto", "hybrid", "manual"],
      "description": "Override system default execution mode"
    },
    "target_worker": {
      "type": "string",
      "description": "Required for manual mode, optional for others"
    },
    "override_warnings": {
      "type": "boolean",
      "default": false,
      "description": "Bypass non-blocking warnings in manual mode"
    }
  },
  "required": ["task_type", "parameters"],
  "if": {
    "properties": {"execution_mode": {"const": "manual"}}
  },
  "then": {
    "required": ["target_worker"]
  }
}
```

### Task Status Schema

```json
{
  "task_id": "string (UUID)",
  "task_type": "string",
  "parameters": "object",
  "priority": "integer (1-10)",
  "execution_mode": "auto | hybrid | manual",
  "status": "pending_approval | queued | running | completed | failed | rejected | expired",
  "worker_id": "string (if assigned)",
  "submitted_at": "ISO 8601 timestamp",
  "started_at": "ISO 8601 timestamp (nullable)",
  "completed_at": "ISO 8601 timestamp (nullable)",
  "result": "object (nullable)",
  "error": "string (nullable)",
  "proposal": {
    "proposed_worker": "string",
    "reasoning": "string",
    "alternatives": "array",
    "expires_at": "ISO 8601 timestamp"
  },
  "approval": {
    "approved_at": "ISO 8601 timestamp",
    "approved_by": "string",
    "approved_worker": "string",
    "approval_reason": "string (nullable)"
  }
}
```

---

## WebSocket Protocol

### Connection and Authentication
```javascript
const ws = new WebSocket('ws://localhost:8081');

// Authenticate (if security enabled)
ws.send(JSON.stringify({
  type: 'authenticate',
  token: '<jwt-token>',
  client_type: 'ui'  // ui | worker | llm_taskmaster | admin
}));
```

### Message Types

#### System Messages
```json
// Connection established
{"type": "welcome", "client_id": "uuid", "timestamp": "ISO 8601"}

// System mode changed
{"type": "mode_changed", "previous_mode": "auto", "new_mode": "hybrid", "timestamp": "ISO 8601"}
```

#### Task Lifecycle Messages (All Modes)
```json
// Task submitted
{"type": "task_submitted", "task_id": "uuid", "execution_mode": "auto"}

// Task started
{"type": "task_started", "task_id": "uuid", "worker_id": "worker-1"}

// Task completed
{"type": "task_completed", "task_id": "uuid", "result": {...}}

// Task failed
{"type": "task_failed", "task_id": "uuid", "error": "error message"}
```

#### HYBRID Mode Messages
```json
// Proposal ready for approval
{
  "type": "proposal_ready",
  "task_id": "uuid",
  "proposed_worker": "worker-1",
  "reasoning": "...",
  "alternatives": [...],
  "expires_at": "ISO 8601"
}

// Proposal approved
{
  "type": "proposal_approved",
  "task_id": "uuid",
  "approved_worker": "worker-1",
  "approved_by": "user-1"
}

// Proposal rejected
{
  "type": "proposal_rejected",
  "task_id": "uuid",
  "rejected_by": "user-1",
  "reason": "..."
}

// Proposal expired
{
  "type": "proposal_expired",
  "task_id": "uuid",
  "expired_at": "ISO 8601"
}
```

#### MANUAL Mode Messages
```json
// Worker validation result
{
  "type": "worker_validation",
  "task_id": "uuid",
  "worker_id": "worker-1",
  "valid": true,
  "warnings": [...]
}

// Manual assignment confirmed
{
  "type": "manual_assignment",
  "task_id": "uuid",
  "worker_id": "worker-1",
  "assigned_by": "user-1"
}
```

---

## Logging and Audit Requirements

All execution modes must log:

1. **Task Submission**
   - Timestamp, task_id, task_type, execution_mode, submitter

2. **Routing Decision** (AUTO/HYBRID)
   - Timestamp, task_id, routing_algorithm, selected_worker, reasoning, alternatives

3. **Human Approval** (HYBRID)
   - Timestamp, task_id, approver, approved_worker, approval_reason, decision_time

4. **Manual Assignment** (MANUAL)
   - Timestamp, task_id, assigned_worker, assigner, validation_warnings

5. **Task Execution**
   - Timestamp, task_id, worker_id, execution_start, execution_end, result/error

6. **Mode Changes**
   - Timestamp, previous_mode, new_mode, changed_by, reason

### Log Format
```json
{
  "timestamp": "2026-02-18T16:35:17.123Z",
  "level": "info",
  "component": "execution_mode",
  "event_type": "task_submitted",
  "task_id": "uuid-1234",
  "execution_mode": "hybrid",
  "details": {
    "task_type": "ml_inference",
    "submitter": "api-client-1",
    "priority": 1
  }
}
```

### Audit Trail Storage
- **Location**: `logs/execution_mode_audit.jsonl` (append-only)
- **Retention**: 90 days minimum (configurable)
- **Access**: Read-only except for audit process
- **Backup**: Daily automated backups

---

## Security Considerations

### Authentication and Authorization

Execution mode operations require appropriate permissions:

| Operation | Required Permission | Notes |
|-----------|-------------------|-------|
| Submit task (any mode) | `task:submit` | All authenticated users |
| Approve proposal (HYBRID) | `task:approve` | Approval authority required |
| Reject proposal (HYBRID) | `task:approve` | Same as approve |
| Change system mode | `system:configure` | Admin only |
| View proposals | `task:view` | Task submitter or admin |
| Override warnings (MANUAL) | `task:override` | Elevated privilege |

### Rate Limiting

Prevent abuse of manual/hybrid modes:

```yaml
rate_limits:
  task_submission: 100/minute
  proposal_approval: 50/minute
  mode_changes: 5/hour
  batch_approvals: 10/minute
```

### Input Validation

All modes validate:
- Task type is supported
- Parameters match task type schema
- Worker IDs exist in system
- Execution mode is valid
- User has required permissions

---

## Migration from AUTO-Only System

Existing deployments can adopt HYBRID/MANUAL modes incrementally:

### Phase 1: Enable HYBRID Mode
1. Update configuration: `execution_mode: hybrid`
2. Deploy approval UI/CLI
3. Train operators on approval workflow
4. Monitor approval latency and bottlenecks

### Phase 2: Test MANUAL Mode
1. Use MANUAL mode for debugging/testing
2. Validate worker selection safeguards
3. Document use cases where MANUAL is preferred

### Phase 3: Dynamic Mode Selection
1. Enable per-task mode override
2. Develop policies for automatic mode selection
3. Implement mode recommendation system

### Backward Compatibility
- AUTO mode remains default
- Existing task submission API fully compatible
- No breaking changes to client code
- New fields optional in task schema

---

## Testing Requirements

Each execution mode must have:

1. **Unit Tests**
   - Mode detection and routing
   - Validation logic
   - Error handling

2. **Integration Tests**
   - End-to-end task submission and execution
   - WebSocket message flow
   - API endpoint responses

3. **User Acceptance Tests**
   - Operator approval workflow (HYBRID)
   - Manual worker selection (MANUAL)
   - Mode switching scenarios

4. **Performance Tests**
   - Approval timeout handling (HYBRID)
   - Validation latency (MANUAL)
   - Mode comparison benchmarks

---

## References

- [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md) - Core principles
- [PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md) - Operational rules
- [GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md) - Analysis mode guidelines
- [phantom_core/controller_api.py](./phantom_core/controller_api.py) - Controller implementation
- [socket_infrastructure/hybrid_socket_server.py](./socket_infrastructure/hybrid_socket_server.py) - WebSocket server

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-18 | Initial specification (AUTO existing, HYBRID/MANUAL new) |

---

**Approved By**: [Pending Human Review]  
**Implementation Status**: HYBRID and MANUAL modes implemented in this PR  
**Next Review Date**: 2026-03-18
