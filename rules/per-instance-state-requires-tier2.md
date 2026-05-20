---
id: RULE-020
decision_refs: []
---

# RULE-020: Per-instance long-lived state requires Tier 2

When collection requires a schema cache that survives across cycles, complex token-refresh state machines, or other per-instance persistent state, route to the Java SDK (Tier 2) pipeline. MPB has no per-instance cache.

**If violated:** The MP cannot maintain the required state and either fails collection or re-fetches state on every cycle, causing performance degradation or rate-limit violations.
