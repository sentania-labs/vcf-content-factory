---
id: RULE-019
decision_refs: []
---

# RULE-019: Nested-array iteration in expressions requires Tier 2

When metric extraction requires patterns like `data.*.metrics.*.value`, route to the Java SDK (Tier 2) pipeline. MPB's expression grammar supports dot-path + single `data.*` only (Pass 25 empirical finding).

**If violated:** The MP builds but silently produces zero metrics. Nested iteration expressions are invalid in MPB.
