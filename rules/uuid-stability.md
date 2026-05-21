---
id: RULE-009
---

# RULE-009: UUIDs are part of the contract

UUIDs are part of the contract for super metrics, views, dashboards, and reports. Generate stable UUID on first `validate`, never touch after. Cross-references resolve to literal `sm_<uuid>` / `viewDefinitionId` strings. See `context/uuids_and_cross_references.md`.

**Carve-out:** Custom groups, symptoms, and alerts are identified by `name`, not UUID — server assigns the `id` on create.

**If violated:** Reinstalling the same content creates duplicates instead of updating. Cross-references break. Policy bindings point to orphaned objects.
