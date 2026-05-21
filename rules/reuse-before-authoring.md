---
id: RULE-004
---

# RULE-004: Reuse before authoring

When `ops-recon` finds existing content that solves the problem (built-in metrics, existing instance content, reference repo YAML), stop. Prefer adapt-and-import over authoring from scratch.

**If violated:** The framework wastes effort creating content that already exists, increasing maintenance burden and confusing users who discover multiple paths to the same data.
