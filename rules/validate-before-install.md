---
id: RULE-004
decision_refs: []
---

# RULE-004: Always validate before installing

Delegate to `content-installer` which validates before every sync. Never push content to a live instance without running validation first.

**If violated:** Malformed YAML or broken cross-references reach production, causing partial installs, broken dashboards, or corrupted policy bindings.
