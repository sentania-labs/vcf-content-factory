---
id: RULE-006
decision_refs: []
---

# RULE-006: UUIDs are part of the contract

UUIDs are part of the contract for super metrics, views, dashboards, and reports. Stable UUID in the YAML `id` field; cross-references resolve to literal `sm_<uuid>` / `viewDefinitionId` strings on the wire. Generate on first `validate`, never touch after. See `context/uuids_and_cross_references.md`.

**Carve-out:** Custom groups, symptoms, and alerts are identified by `name`, not UUID — server assigns the `id` on create.

**If violated:** Reinstalling the same content creates duplicates instead of updating. Cross-references break. Policy bindings point to orphaned objects.
