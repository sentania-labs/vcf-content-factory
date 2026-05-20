---
id: RULE-028
decision_refs: []
---

# RULE-028: Use human-readable resource names, not internal API IDs

The `ResourceKey` name field is the display label in the VCF Ops inventory
tree and dashboards. Derive display names from user-facing API fields
(model names, descriptive labels, computed display strings) rather than
internal API identifiers (GUIDs, opaque tokens, slot references).

**If violated:** The inventory tree shows cryptic internal IDs like
`reuse_1`, `sata1`, `disk_id_abc123` instead of readable labels like
"Storage Pool 1", "Drive 4 (WD Red 8TB)", "SSD Cache (Volume 2)". Users
cannot navigate the hierarchy without cross-referencing API documentation.

**Good patterns:**
- `"Storage Pool " + num_id` instead of `pool_path`
- `disk.name` ("Drive 4") instead of `disk.id` ("sata1")
- `"Volume " + volume.id + " (" + volume.name + ")"` instead of `volume_num`

**The identifier stays internal:** Use the stable API identifier for the
ResourceKey `identifiers` map (required for collection cycle matching).
Only the `name` field should be human-readable.

**Evidence:** Synology SDK adapter (2026-05-19) lesson 23. Using API
internals produced an unreadable hierarchy; switching to derived display
names made the inventory tree navigable. Documented in
`context/lessons_synology_sdk_2026_05_19.md` lines 148-154.
