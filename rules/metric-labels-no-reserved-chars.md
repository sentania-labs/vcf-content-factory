---
id: RULE-022
decision_refs: []
---

# RULE-022: Metric labels cannot contain reserved characters

Metric and property labels must not contain the VCF Ops stat key reserved
characters: pipe (`|`) or colon (`:`). These characters are structural
separators in the internal metric path grammar and will cause collection
preview errors at runtime.

**If violated:** Collection preview fails with "Metric key cannot contain
reserved characters `|` or `:`." The adapter installs successfully but
metrics do not flow.

**Validation:** The loader should reject labels containing `|` or `:` at
validate time with a BLOCKING error, not defer to runtime discovery.

**Evidence:** Lessons learned from vSphere Storage Paths v2.0.0 install
campaign (2026-05-13), documented in
`context/lessons_pak_install_reliability.md` §2.
