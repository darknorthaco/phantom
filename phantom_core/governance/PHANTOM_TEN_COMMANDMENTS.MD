📘 PHANTOM_TEN_COMMANDMENTS.md
The Immutable Laws That Govern Phantom’s Architecture and Safety
1. Humans Lead, Agents Execute
Agents must never make architectural decisions.
They propose, report, and wait for explicit human approval.
2. Protocols Are Sacred
Message schemas, routing rules, and broadcast formats are immutable contracts.
No agent may alter them without human authorization.
3. Tests Are Historical Truth
Phase 7 and future regression suites define canonical behavior.
Agents must never modify tests to “make them pass.”
4. No Simulator Artifacts in Production
Simulators are for testing only.
No synthetic metrics, fake inventories, or artificial data may leak into real operation.
5. All Changes Must Be Atomic, Auditable, and Reversible
Every modification must be minimal, isolated, diff‑visible, and reversible without side effects.
6. Phantom Must Always Be LAN‑First and Privacy‑First
No cloud dependencies.
No external calls.
No silent data flow beyond the user’s network.
7. Workers Must Be Honest About Their Capabilities
No hallucinated hardware.
No fabricated metrics.
No silent failures.
Workers report only what is real and measurable.
8. The Controller Must Never Lie
It must route faithfully, broadcast faithfully, and log faithfully.
No reinterpretation or mutation of worker data.
9. Safety Overrides Convenience
If an action risks protocol drift, architectural mutation, or runaway behavior, the agent must halt and report instead of proceeding.
10. Phantom Must Always Be Understandable
Every component must be readable, explainable, and maintainable.
If a change makes Phantom harder to understand, it violates the law.
