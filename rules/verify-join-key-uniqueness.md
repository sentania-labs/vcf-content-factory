---
id: RULE-025
decision_refs: []
---

# RULE-025: Verify join key uniqueness across all collection sources

When designing cross-request joins, cross-adapter stitching, or
parent-child relationships that rely on a shared identifier, verify that
the chosen identifier is globally unique across all collection contexts
where the data will be gathered.

**If violated:** Silent data corruption. Resources from different sources
collide on the same identifier, causing metrics to appear on the wrong
resource, resources to disappear from inventory, or relationships to wire
incorrectly. No error is raised — the platform merges silently.

**Common traps:**
- VMware MOIDs (`host-20`) are per-vCenter, not global. Use FQDN instead.
- API-internal IDs may be scoped to a parent container.
- Array indices are never stable identifiers.

**Validation:** During design review, explicitly state the uniqueness
scope of every proposed identifier. Test with multiple collection sources
if available (multi-vCenter, multi-site, etc.).

**Evidence:** vSphere Storage Paths v2.0.0 used `host_moid` (VMEntityObjectID)
as the join key. Both wld01 and wld02 had `host-20`, causing wld02 hosts
to silently disappear and wld01 hosts to show wrong metric values. Fixed
by switching to `hostname` (VMEntityName, globally unique FQDN). Documented
in `context/lessons_pak_install_reliability.md` §6.
