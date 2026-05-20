---
id: DEC-002
status: decided
decided_date: 2026-05-18
decided_by: scott
rules_derived: []
applies_rules: [RULE-027]
supersedes: null
---

# DEC-002: Dell PowerEdge Redfish → Tier 2 (Java SDK)

## Decision

Dell PowerEdge Redfish-based management packs must be authored using Tier 2
(native Java SDK), not Tier 1 (MPB / HTTP authoring).

## Rule basis

RULE-027: APIs with parent-child encoded in URL paths require Tier 2.

Dell PowerEdge Redfish encodes the object hierarchy in URL path structure:
- `/redfish/v1/Systems/{id}/Processors/{id}`
- `/redfish/v1/Chassis/{id}/Thermal#/Fans/{n}`
- `/redfish/v1/Systems/{id}/Memory/{id}`

Components (Fans, PSUs, Memory DIMMs, Processors, Firmware) are children of
Server in the URL path, but no common key exists in the response bodies to
model this parent-child relationship in MPB Tier 1.

## Evidence

Dell PowerEdge Redfish relationship investigation (2026-05-18). Three
relationship strategies attempted against live MPB UI on devel:

1. **`adapter_instance` scope** — three rendering strategies
   (`synthetic_adapter_instance`, `shared_constant_property`,
   `world_implicit`). All failed MPB Verify validation. The first passed
   import but showed "Child property used in relationship does not exist"
   warnings. The second failed with "expression does not contain at least
   one dynamic field from response body." The third rejected at import with
   HTTP 400.

2. **`field_match` with cross-request scalar** — attempted to broadcast the
   System ID (`System.Embedded.1`) from the Server's response to each
   component via a secondary metricSet. Failed: "non-primary metricSet on
   a list object must declare `chained_from` or `primary: true`". The
   broadcast-scalar pattern is not supported by MPB's metric DSL.

3. **Regex extraction from `@odata.id`** — the most natural solution (extract
   `System\.Embedded\.\d+` from every component's `@odata.id` URL). The
   factory YAML reserves `extract:` for this, but the renderer strips it
   with "regex extraction is not yet supported." MPB runtime likely supports
   it (UniFi references `regex` / `regexOutput` fields set to null), but
   the factory tooling does not implement it yet.

All three strategies were empirically falsified against MPB UI. Dell v4
shipped with `relationships: []` (flat inventory) because the original
author could not solve this either.

Full investigation documented in
`context/lessons_dell_redfish_2026_05_18.md`.

## Trade-offs

**What we gave up:**
- MPB Tier 1 (HTTP authoring) is faster to author, easier to review, needs
  no JDK, produces smaller paks.
- The factory's existing Tier 1 pipeline is mature; Tier 2 is newer.

**What we gained:**
- Proper inventory tree with components nested under Server.
- Full programmatic control over metric extraction, relationship wiring,
  and resource naming.
- Framework validation: the Tier 2 pipeline was built for exactly this
  class of problem (Synology hit the same wall and proved Tier 2 works).

## Implications for other Redfish-based MPs

Any API conforming to the DMTF Redfish standard (servers, storage, network)
will hit RULE-027 for the same structural reason. This decision applies
to Dell specifically; other Redfish vendors (HPE iLO, Lenovo XClarity,
Cisco UCS, Supermicro) should evaluate against RULE-027 but may produce
separate decisions if their API shape differs.

## Relitigation

This decision is binding. To override:

1. Create `decisions/overrides/DEC-002-override.md`
2. Document which evidence changed:
   - Did MPB add regex extraction support?
   - Did the factory implement broadcast-scalar metricSets?
   - Did a fourth relationship strategy succeed in MPB UI Verify?
   - Did the Redfish API add flat scalar parent-ID fields to component
     responses?
3. Reference new cleanroom findings, MPB version notes, or API maps.
4. The override must be approved by the framework maintainer.

Casual users cannot relitigate. If you believe Tier 1 is now viable for
Dell Redfish, you must prove it against live MPB UI and document the
changed capability.
