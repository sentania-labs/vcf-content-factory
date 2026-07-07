---
id: RULE-002
---

# RULE-002: Never fabricate metric or attribute names

Ground all metric and attribute references in `ops-recon` results, `reference/docs/`, or OpenAPI specs. If a metric or attribute key doesn't appear in those sources, it doesn't exist.

**If violated:** Super metrics, views, or dashboards reference nonexistent data. Content installs successfully but displays nothing at runtime.
