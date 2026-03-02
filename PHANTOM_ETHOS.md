# Phantom Ethos: Core Principles

**Version:** 1.0.0  
**Status:** HISTORICAL — Superseded by the Soul–Mind–Body governance stack  
**Superseded by:** [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) (Soul), [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) (Mind)  
**Applies to:** All Phantom Systems and Distributions

> **This document is retained for historical reference.**  
> The principles below have been absorbed into the Phantom Doctrine (Mind).  
> The authoritative governance chain is:  
> **Soul** → PHANTOM_MANIFEST.md → **Mind** → PHANTOM_DOCTRINE.md → **Body** → .cursorrules + PHANTOM_TEN_COMMANDMENTS.md

---

## Purpose

This document originally defined the foundational principles that guided all development, analysis, and operations within the Phantom ecosystem. These principles remain valid but are now expressed through the Doctrine.

---

## The Ethos

### 1. **Sovereignty**
Phantom is **sovereign compute**. No external entity, service, or system has authority over Phantom operations unless explicitly granted by the human operator.

- **Local-first architecture:** All compute, storage, and control remain on-premises
- **No cloud dependencies:** Phantom must operate without external cloud services
- **No telemetry without consent:** No data leaves the system without explicit authorization
- **Human authority is absolute:** Machines propose, humans decide

### 2. **Transparency**
Every operation, decision, and data flow must be **transparent and auditable**.

- **No hidden state:** All system state must be inspectable
- **Clear separation of concerns:** Boundaries between components are explicit
- **Traceable decisions:** Every routing decision, task assignment, and state change is logged
- **Open architecture:** System design is documented and understandable

### 3. **Reversibility**
No operation should be **irreversible without explicit human authorization**.

- **Audit-first workflow:** Propose, review, approve, apply
- **Non-destructive changes:** Preserve original state before modifications
- **Rollback capability:** Every change can be undone
- **Human-led execution:** Agents propose, humans apply

### 4. **Modularity**
System components are **swappable, composable, and independently functional**.

- **Clean interfaces:** Components communicate through well-defined contracts
- **Protocol agnostic:** Transport and encoding are abstraction layers
- **Plugin architecture:** Capabilities extended without core modifications
- **Minimal coupling:** Components depend on abstractions, not implementations

### 5. **Minimalism**
**Simplicity is sovereign.** Every component does one thing well.

- **Essential complexity only:** No accidental complexity
- **Smallest viable solution:** Solve the problem, nothing more
- **Clear purpose:** Every file, function, and feature has a reason
- **No premature optimization:** Optimize when measurements prove necessity

### 6. **Integrity**
The system's **architectural integrity** must never be compromised.

- **Respect existing patterns:** New code follows established conventions
- **No shortcuts:** Quick fixes that violate principles are prohibited
- **Security first:** Never compromise security for convenience
- **Quality over speed:** Correct solutions take precedence over fast delivery

### 7. **Human Control**
Humans **direct**, machines **execute**. Never reverse this hierarchy.

- **Explicit approval required:** Agents cannot apply changes autonomously
- **Clear proposals:** All suggestions are presented for human review
- **Halt on uncertainty:** Stop and ask rather than guess
- **Respect boundaries:** Do not exceed granted permissions

---

## References

- [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) — Soul of Phantom (highest authority)
- [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) — Mind of Phantom (governing principles)
- [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md) — Body of Phantom (operational rules)
- [.cursorrules](./.cursorrules) — Body of Phantom (development constraints)

---

**This document is historical. The Soul (Manifest) is now the highest authority. The human is sovereign. The machine serves.**
