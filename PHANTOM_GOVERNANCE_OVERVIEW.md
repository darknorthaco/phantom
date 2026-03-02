# PHANTOM GOVERNANCE OVERVIEW
### *Constitutional Hierarchy of the Phantom Intelligence Fabric*

**Version:** 1.0.0
**Status:** Authoritative
**Applies to:** All Phantom contributors, agents, maintainers, and systems

---

## 1. Purpose

This document is the single entry point for understanding Phantom's governance model.

Phantom is governed by a constitutional hierarchy called the **Soul–Mind–Body** stack. Every file, every decision, and every line of code must align with this hierarchy. This overview explains the stack, defines each layer's role and authority, and provides the decision workflow that all contributors must follow.

If you read one governance document, read this one. It tells you where to look for everything else.

---

## 2. Governance Hierarchy

```
Human Architect (absolute authority)
  └─ Soul: PHANTOM_MANIFEST.md
       └─ Mind: PHANTOM_DOCTRINE.md (11 principles)
            └─ Body: .cursorrules + PHANTOM_TEN_COMMANDMENTS.md
                 └─ SOPs, Best Practices
                      └─ PHANTOM_TOPOLOGY.md (descriptive only)

PHANTOM_ETHOS.md → historical, superseded
```

Authority flows **downward**. Each layer is subordinate to the layer above it. When layers conflict, the higher layer prevails. No exceptions.

---

## 3. Layer Definitions

### 3.1 Human Architect

**Role:** Final authority on all matters.

The Human Architect is the repository owner. No document, principle, or automated system overrides a direct human decision. The entire governance stack exists to serve the human, not the other way around.

- Approves or rejects all proposals
- May override any layer
- May amend the Soul under the Amendment Protocol

---

### 3.2 Soul — PHANTOM_MANIFEST.md

**Location:** `doctrine/PHANTOM_MANIFEST.md`
**Role:** Defines Phantom's identity and purpose.

The Manifest is the highest-authority document. It establishes:

- **The Three Pillars:** Soul–Mind–Body hierarchy definition
- **The Identity Contract:** Four non-negotiable invariants (Sovereignty, Humility, Authenticity, Transparency)
- **The Oath:** If any design choice conflicts with the Soul, the Soul prevails
- **The Amendment Protocol:** Conditions under which Phantom may evolve

**Relationship to other layers:**
- Superior to all other documents
- The Mind interprets the Soul; it does not amend it
- The Body enforces the Soul; it does not interpret it

---

### 3.3 Mind — PHANTOM_DOCTRINE.md

**Location:** `doctrine/PHANTOM_DOCTRINE.md`
**Role:** Interprets the Soul. Provides the principles for reasoning and decision-making.

The Doctrine translates the Manifest's identity into 11 actionable governing principles:

1. Human Priority
2. Sovereign Domains
3. Authentic Trust
4. Transparent Operation
5. Voluntary Mesh Participation
6. Consistent Behavior
7. Evolution Without Drift
8. Reversibility
9. Modularity
10. Minimalism
11. The Opera Principle

**Relationship to other layers:**
- Subordinate to the Soul (Manifest)
- Superior to the Body (.cursorrules + Commandments)
- If a Doctrine principle contradicts the Manifest, the Manifest prevails
- If a Body rule contradicts the Doctrine, the Doctrine prevails

---

### 3.4 Body — .cursorrules + PHANTOM_TEN_COMMANDMENTS.md

**Location:** `.cursorrules` (repo root) and `PHANTOM_TEN_COMMANDMENTS.md` (repo root)
**Role:** Enforces the Doctrine in action through operational rules and development constraints.

The Body has two components:

- **`.cursorrules`** — Machine-readable YAML. Defines banned patterns, structural requirements, alignment checks, and the hierarchy block. Consumed by development tools (Cursor, agents, CI).
- **PHANTOM_TEN_COMMANDMENTS.md** — Human-readable operational rules. Ten commandments with explicit violation/penalty definitions, a compliance checklist, and enforcement tiers.

Together they answer: *"What must I actually do (or not do) when writing code, submitting proposals, or operating Phantom?"*

**Relationship to other layers:**
- Subordinate to the Mind (Doctrine) and the Soul (Manifest)
- Superior to SOPs and Best Practices
- If a Commandment contradicts a Doctrine principle, the Doctrine prevails
- If `.cursorrules` contradicts the Commandments, the Commandments prevail (human-readable intent takes precedence over machine-readable expression)

---

### 3.5 SOPs and Best Practices

**Locations:** `GOVERNANCE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, ADRs
**Role:** Detailed workflows and recommended practices.

SOPs define how to contribute, how decisions are made, and how violations are handled. Best Practices are recommendations, not requirements.

**Relationship to other layers:**
- Subordinate to the Body
- Cannot override Commandments, Doctrine, or Manifest
- May be updated by maintainers without triggering the Amendment Protocol

---

### 3.6 Topology — PHANTOM_TOPOLOGY.md

**Location:** `doctrine/PHANTOM_TOPOLOGY.md`
**Classification:** Descriptive only.

The Topology maps Phantom's physical architecture: hardware, roles, network links, and security posture. It describes what exists. It does not govern identity, reasoning, or behavior.

**Relationship to other layers:**
- Has no governing authority
- May be updated freely as hardware changes
- Must not contradict the Soul, Mind, or Body, but does not constrain them

---

### 3.7 Ethos — PHANTOM_ETHOS.md (Historical)

**Location:** `PHANTOM_ETHOS.md` (repo root)
**Status:** Historical. Superseded by PHANTOM_MANIFEST.md (Soul) and PHANTOM_DOCTRINE.md (Mind).

The Ethos was the original foundational principles document. Its unique content (Reversibility, Modularity, Minimalism) has been absorbed into the Doctrine. It is retained for historical reference only.

**Relationship to other layers:**
- Has no governing authority
- Must not be cited as authoritative in new work
- References within point to the current governance stack

---

## 4. How to Apply the Hierarchy

When making any decision — writing code, reviewing a proposal, resolving a conflict, or designing a feature — walk the stack from top to bottom:

### Step 1: Check the Soul
Does this decision align with the Identity Contract?
- Sovereignty: Does it preserve local control?
- Humility: Does it yield to the human?
- Authenticity: Is communication signed and verifiable?
- Transparency: Is there hidden state or silent behavior?

If it violates the Soul, **stop**. The decision is rejected.

### Step 2: Check the Mind
Does this decision align with the 11 Doctrine principles?
- Does it respect Human Priority?
- Does it maintain Sovereign Domains?
- Is trust explicit?
- Is the operation transparent?
- Is mesh participation voluntary?
- Is behavior consistent across deployments?
- Does it evolve without drift?
- Is it reversible?
- Is it modular?
- Is it minimal?
- Does it follow the Opera Principle?

If it violates the Doctrine, **stop**. Revise to comply.

### Step 3: Check the Body
Does this decision comply with the Ten Commandments and `.cursorrules`?
- Does it introduce banned patterns?
- Does it require authorization that hasn't been granted?
- Does it violate scope, assumptions, or layer boundaries?

If it violates the Body, **stop**. Revise to comply.

### Step 4: Check SOPs
Does this decision follow the contribution process, governance model, and coding standards defined in GOVERNANCE.md, CONTRIBUTING.md, and related documents?

### Step 5: Check Topology
Is this decision consistent with the physical architecture described in PHANTOM_TOPOLOGY.md? (Informational only — topology does not override governance.)

---

## 5. Authority Resolution Rule

When any two governance documents conflict, the higher layer prevails:

```
Manifest (Soul) > Doctrine (Mind) > Body > SOPs > Topology
```

The Human Architect may override any layer at any time.

No lower layer may amend, reinterpret, or contradict a higher layer. If a conflict is discovered, it must be escalated to the Human Architect for resolution.

---

## 6. Document Map

| Layer | Document | Location | Authority |
|---|---|---|---|
| Soul | PHANTOM_MANIFEST.md | `doctrine/` | Highest |
| Mind | PHANTOM_DOCTRINE.md | `doctrine/` | Subordinate to Soul |
| Body | .cursorrules | repo root | Subordinate to Mind |
| Body | PHANTOM_TEN_COMMANDMENTS.md | repo root | Subordinate to Mind |
| SOP | GOVERNANCE.md | repo root | Subordinate to Body |
| SOP | CONTRIBUTING.md | repo root | Subordinate to Body |
| Descriptive | PHANTOM_TOPOLOGY.md | `doctrine/` | No governing authority |
| Historical | PHANTOM_ETHOS.md | repo root | Superseded |

---

## 7. References

- [PHANTOM_MANIFEST.md](./doctrine/PHANTOM_MANIFEST.md) — Soul
- [PHANTOM_DOCTRINE.md](./doctrine/PHANTOM_DOCTRINE.md) — Mind
- [PHANTOM_TEN_COMMANDMENTS.md](./PHANTOM_TEN_COMMANDMENTS.md) — Body (operational rules)
- [.cursorrules](./.cursorrules) — Body (development constraints)
- [GOVERNANCE.md](./GOVERNANCE.md) — Repository governance model
- [PHANTOM_TOPOLOGY.md](./doctrine/PHANTOM_TOPOLOGY.md) — Architecture map
- [PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md) — Historical reference

---

**The Soul defines. The Mind reasons. The Body enforces. The Human decides.**
