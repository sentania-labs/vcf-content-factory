---
id: RULE-027
decision_refs: [DEC-002]
---

# RULE-027: APIs with parent-child encoded in URL paths require Tier 2

When the target API encodes object hierarchy in URL path structure
(e.g., `/Systems/{id}/Processors/{id}`, `/Chassis/{id}/Thermal#/Fans/{n}`)
rather than as flat scalar fields in response bodies, route to Tier 2
(native Java SDK). MPB Tier 1 (HTTP authoring) cannot model parent-child
relationships from URL-path extraction.

**If violated:** The MP builds and installs but produces a flat inventory
tree where all components appear as siblings instead of nested under their
parents. Workarounds (synthetic constants, cross-request broadcasts,
adapter_instance scope) have all been empirically falsified against MPB UI.

**Why MPB can't handle it:** MPB relationship expressions require both
parent and child to have a *metric value* (from the response body) to
compare. URL path components are not exposed as extractable fields in
MPB's metric DSL. Regex extraction is targeted for MPB 9.2 but not
present in current runtime.

**Evidence:** Dell PowerEdge Redfish investigation (2026-05-18). Attempted
multiple relationship strategies; all failed MPB UI Verify. Documented in
`context/lessons_dell_redfish_2026_05_18.md`.

**Examples of this shape:** Redfish (servers, storage, network), IPMI,
many RESTful hardware APIs.
