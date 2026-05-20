---
id: RULE-021
decision_refs: []
---

# RULE-021: Exhaust built-in metrics and transformations before creating supermetrics

Before authoring a new supermetric, confirm via `ops-recon` that no built-in metric, transformation, or existing supermetric already provides the required data. Prefer adapt-and-import over authoring from scratch.

**If violated:** The framework creates redundant content, increasing maintenance burden and confusing users who discover multiple ways to access the same data.
