---
id: RULE-003
---

# RULE-003: Recon before authoring; reuse before authoring from scratch

Every authoring request begins with `ops-recon`. Check, in order:
1. Built-in metrics and transformations on the live instance
2. Existing content on the instance
3. Existing repo YAML
4. Allowlisted external reference repos (`knowledge/context/reference_sources.md`, grepped from `reference/references/`)

If any source has an exact match, stop — prefer adapt-and-import over authoring from scratch.

**For supermetrics specifically:** Exhaust built-in metrics and transformations before creating a new supermetric. This is the orchestrator's responsibility to verify before spawning `supermetric-author`.

**If violated:** Duplicate content proliferates. The framework wastes effort creating content that already exists — redundant supermetrics, views, or dashboards that appear in slightly different forms, increasing maintenance burden and confusing users who discover multiple paths to the same data.
