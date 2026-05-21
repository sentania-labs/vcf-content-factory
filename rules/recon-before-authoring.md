---
id: RULE-003
---

# RULE-003: Recon before authoring

Every authoring request begins with `ops-recon`. Check live instance content, existing repo YAML, and allowlisted reference repos (`context/reference_sources.md`, grepped from `references/`) before creating anything new.

**If violated:** Duplicate content proliferates. The framework creates redundant supermetrics, views, or dashboards that already exist in slightly different form.
