---
id: RULE-005
---

# RULE-005: Exhaust built-ins before creating supermetrics

Before authoring a new supermetric, confirm via `ops-recon` that no built-in metric, transformation, or existing supermetric provides the required data. This is the orchestrator's responsibility to check before spawning `supermetric-author`.

**If violated:** The framework creates redundant content, increasing maintenance burden and confusing users who discover multiple ways to access the same data.
