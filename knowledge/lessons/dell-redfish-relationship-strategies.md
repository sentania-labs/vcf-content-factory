# War Story: Dell Redfish — Three Relationship Strategies, All Failed

**Target:** Dell PowerEdge Redfish API  
**Verdict:** Tier 2 (Java SDK). Do not attempt Tier 1 (MPB).  
**Date:** 2026-05-18

## What we were trying to do

The Dell PowerEdge MP (v4, forked from this framework) had a flat inventory:
every per-component object (Fan, PSU, Memory DIMM, Firmware Component) appeared
as a sibling of Dell PowerEdge Server rather than nested under it. BC's PM
summarized the problem: "The firmware version of components are created as same
level objects as the Physical server."

We spent a full session trying to fix this in MPB Tier 1. We didn't succeed.
Here is what we tried and why each strategy failed.

## Why Redfish is hard for MPB

Redfish encodes the object hierarchy in URL path structure, not in response body
fields:

- `/redfish/v1/Systems/{id}/Processors/{id}`
- `/redfish/v1/Chassis/{id}/Thermal#/Fans/{n}`
- `/redfish/v1/Systems/{id}/Memory/{id}`

MPB's relationship model expects both sides of a relationship to have a real
metric carrying the same value (a "join key"). Redfish components don't carry
their parent's ID as a flat scalar field — the only place the parent ID appears
is in the `@odata.id` URL path. MPB can't join on URL path structure.

## Strategy 1: `adapter_instance` scope (three rendering variants)

The factory's `scope: adapter_instance` relationship mode is designed for a
singleton parent (one Server per adapter instance) containing list-typed
children. Three wire-form strategies exist in `render.py`:

**`synthetic_adapter_instance`** — uses `originType: ATTRIBUTE`, `label: @@@adapterInstance`.
*Result:* Imports cleanly. MPB Relationships tab shows all 10 with red warnings:
"Child property used in relationship does not exist." The `@@@adapterInstance`
token references a property that has no metric definition on either object.

**`shared_constant_property`** — injects a synthetic metric with a literal
constant value on every object, then joins on matching constants.
*Result:* Imports cleanly. MPB Verify fails: "An expression does not contain at
least one dynamic field from a response body or a request parameter." MPB
forbids literal-constant metric expressions entirely. No workaround.

**`world_implicit`** — uses `parentExpression: null`, `childExpression: null`.
*Result:* Rejected at design import with HTTP 400 "Invalid input format."
MPB's validator refuses null expressions outright.

All three strategies in the factory were authored as educated guesses, never
validated against a live MPB UI. None survived contact with the real validator.

## Strategy 2: `field_match` with cross-request scalar

The UniFi pattern: each side of a relationship carries a real metric pulled
from its own response body, and MPB compares the values. The shared key would
be the System identifier (`System.Embedded.1`).

We tried adding `from_request: system_info` as a second metricSet on each
component object, broadcasting `system_info.Id` (the System ID) to every
component so MPB could join on it.

*Result:* Validator rejected with: "non-primary metricSet on a list object must
declare either `chained_from: <primary>` (for a chained secondary) or
`primary: true`." A "broadcast scalar from unrelated request" pattern doesn't
exist in MPB's metric DSL. The metric must come from the object's own primary
request or a chained secondary request — not from an unrelated singleton request.

## Strategy 3: Regex extraction from `@odata.id`

The cleanest path: extract `System\.Embedded\.\d+` from each component's
`@odata.id` URL. Every Redfish component carries its parent's ID in its own
URL. A regex extraction would yield the same string on every component,
matching Server's `Id` field.

The factory's `MetricSourceDef` has an `extract:` field reserved for this.
*Result:* `loader.py` explicitly strips it: "Remove the 'extract:' key —
regex extraction is not yet supported." The MPB wire format carries `regex`
and `regexOutput` fields in `expressionParts[]` (UniFi sets them null), so
the runtime likely supports it — the factory tooling doesn't implement it yet.

## What this means for future Redfish work

To make MPB Tier 1 work with URL-path-encoded hierarchies, the factory needs
at least ONE of:

1. **Regex extraction** — implement the `extract:` field in the renderer.
   Already reserved in the YAML schema. Cheapest fix.
2. **Cross-request scalar broadcast** — pull a scalar from one request and
   broadcast it to every row of a list object from a different request.
   Not standard chaining; needs new metricSet semantics.
3. **Instanced groups** — the `<ResourceGroup instanced="true">` wire form
   that Broadcom-authored paks (Kubernetes, FabricServer) use. MPB UI can't
   produce it; requires direct wire format control (Tier 2 or Python SDK).

None of these was implemented during this session. Until one is, **Redfish-
style APIs with parent-child encoded in URL paths require Tier 2.**

## The Onur sidestep (reference for future work)

The vmbro/VCF-Operations-Hardware-vCommunity adapter uses instanced metrics:
it emits every PSU, fan, DIMM as a per-component metric on a single
PhysicalServer object (`Hardware|Power:PSU1|Power Output Watts`). No parent-
child relationships, no separate component objects. This requires
`<ResourceGroup instanced="true">` in describe.xml, which MPB UI can't
produce — Onur's Python Integration SDK does it directly. The same outcome is
achievable in our Tier 2 Java SDK.

## How UniFi avoids this

UniFi's API carries the uplink Device ID as a flat scalar field on every
Client response. MPB compares matching scalars at collection time — no URL
path parsing needed. Redfish is the opposite: the parent ID lives only in the
URL path, not in the body.

## Lessons for the next contributor

1. **Audit inherited designs against the user's stated complaint before
   assuming a cleanup will fix it.** v4 1.x had `relationships: []` from the
   start — the flat inventory wasn't a regression, it was a fundamental design
   omission. We spent significant time on cleanup before realizing cleanup
   didn't address the complaint.

2. **MPB metric expressions can never be literal constants.** If a relationship
   strategy needs a constant matching key, MPB will reject it at Verify time
   even if the design imports cleanly.

3. **The factory's three `adapter_instance` strategies were guesses.** They've
   been empirically falsified. Don't re-trust them without re-validation against
   MPB UI.

4. **Use `push-design` + MPB UI Verify as the cheap loop.** Don't build a pak
   until the design is green in Verify. Pak builds + sneaker-net are the
   expensive loop; MPB UI Verify is the cheap loop.

5. **For hardware MPs with URL-path hierarchies, Tier 2 SDK is the right tool.**
   Tier 1 + Redfish hits this wall by construction.

## Reference files

- `designs/managementpacks/dell-poweredge.md` — original design intent
- `context/tier_decision_framework.md` — trigger table row 9 (custom transforms
  / regex extraction) and the URL-hierarchy trigger
- `context/api-maps/dell-poweredge-redfish.md` — full API surface
