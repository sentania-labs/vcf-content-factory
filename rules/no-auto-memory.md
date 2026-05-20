---
id: RULE-009
decision_refs: []
---

# RULE-009: Auto-memory is disabled by design

All persistent knowledge lives in `context/`, agent prompts, or skill prompts. If you want to remember something across sessions, that's a signal to add it to a context or rule file — not to enable memory.

Rationale: portability and reviewability. The `.claude/settings.json` setting `autoMemoryEnabled: false` enforces this. See `context/rules_codification.md` for where different kinds of knowledge belong.

**If violated:** The framework becomes dependent on per-user, per-machine state. It stops being a portable, self-documenting artifact and becomes a collection of tribal knowledge.
