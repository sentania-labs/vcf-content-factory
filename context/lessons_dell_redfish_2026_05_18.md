# Lessons — Dell PowerEdge Redfish relationship investigation (2026-05-18)

Empirical record of an attempt to make MPB-authored Dell PowerEdge MP
produce a proper inventory tree against the standard Redfish API
surface. We did not succeed within MPB Tier 1 (HTTP authoring). This
document captures what we tried, why each attempt failed against real
MPB UI on devel, and what the framework needs to absorb so the next
contributor doesn't repeat the loop.

## The complaint we were trying to fix

BC's PM, on a v4 MP someone else built from a fork of this framework:

> "There needs to be some improvements to how the relationships
> between properties and the Endpoint are handled. For example, the
> firmware version of components are created as same level objects
> as the Physical server."

Translated: in VCF Operations inventory, every per-component object
(Fan, PSU, Memory DIMM, Firmware Component, …) appeared as a sibling
of Dell PowerEdge Server rather than nested under it. The
intermediate "collection" object kinds (CPU.1, ProcessorsCollection,
Memory Devices Collection, Power, Thermal, …) appeared as siblings
too.

## What we tried

### 1. Structural cleanup (v4 1.x → v4 2.0)

Removed the eight intermediate collection-container object types
that v4 1.x carried as noise (Power, Thermal, ProcessorsCollection,
Memory Devices Collection, Firmware Inventory Collection, System
Ethernet Interface Collection, DellNumericSensorCollection, CPU.1).
Result: 11 object types instead of 19. This was the right work but
it did not address the actual complaint — the remaining 10
component types still appeared as flat peers of the Server because
the design declared no relationships at all.

**Discovery:** v4 1.x had `relationships: []` from the start. BC's
PM never authored relationships. The flat inventory wasn't a
regression we caused — it's a structural omission inherited from
the original design.

### 2. adapter_instance scope, three rendering strategies

The factory ships a Tier 3.3 `scope: adapter_instance` relationship
mode meant for exactly this case: a singleton parent (Server, one
per adapter instance) containing list-typed children. Three wire-
form strategies exist in `render.py`:

| Strategy | Wire form | MPB result |
|---|---|---|
| `synthetic_adapter_instance` | `originType: ATTRIBUTE`, `label: @@@adapterInstance` | Imports cleanly. MPB Relationships tab shows all 10 with red warnings: **"Child property used in relationship does not exist."** The `@@@adapterInstance` token references a property that has no metric definition on either object. |
| `shared_constant_property` | `originType: METRIC`, `label: __adapter_instance_const`, real synthesized metrics injected on every object with the same literal value | Imports cleanly. MPB Verify (test collection) fails with: **"`METRIC` error … regarding field 'expression'. Field was invalid. An expression does not contain at least one dynamic field from a response body or a request parameter."** MPB forbids literal-constant metric expressions. |
| `world_implicit` | `parentExpression: null`, `childExpression: null` | Rejected at design import: **HTTP 400 "Invalid input format. Unknown error when executing request."** MPB's import validator refuses null expressions outright. |

All three strategies in the factory carry `ASSUMPTION` comments in
their docstrings — they were authored as educated guesses, never
validated against a live MPB UI. None survived contact with the
real validator.

### 3. field_match with cross-request scalar (the UniFi pattern)

The pattern UniFi uses successfully (`field_match` with real metric
values that happen to share a key): each side of the relationship
has a real metric pulled from its own request's response body, and
the values are compared.

For Dell, the shared key would be the System identifier
(`System.Embedded.1`). Server's `system_info.Id` returns it as a
flat scalar. To put the same value on each component object, we
tried adding `from_request: system_info` as a second metricSet on
each child and pulling `system_info.Id` as a `system_id` property.

Result: **validator rejected with "non-primary metricSet on a list
object must declare either `chained_from: <primary>` (for a chained
secondary) or `primary: true`"**. We tried `chained_from`, which
then required a `bind:` entry describing how parent-row data flows
into the chained request — but our case is not a chain; it's a
broadcast scalar from an unrelated request. The factory's metric
DSL has no broadcast-scalar mode.

### 4. Regex / substring extraction

The most natural place to get the System identifier on each
component is the `@odata.id` URL embedded in every Redfish response
(e.g. `/redfish/v1/Chassis/System.Embedded.1/Thermal#/Fans/0`).
A simple regex extraction of `System\.Embedded\.\d+` would yield
the same string on every component, matching Server's `Id` field.

The factory's `MetricSourceDef` has an `extract:` field reserved
for this purpose, but `loader.py:2073` explicitly says: "Remove
the 'extract:' key — regex extraction is not yet supported."
The MPB wire format DOES carry `regex` and `regexOutput` fields
in `expressionParts[]` (UniFi sets them null), so the runtime
likely supports it — we just haven't built the loader/renderer
plumbing.

## The four framework gaps this surfaced

For Tier 1 MPB authoring to handle URL-path-encoded hierarchies
(Redfish and similar), the factory needs **at least one** of:

1. **Cross-request scalar broadcast on metricSets** — a way to pull
   a scalar from request A and broadcast it to every fan-out row of
   a list object whose primary is request B, without invoking
   chained-request semantics.

2. **Regex / substring extraction in metric expressions** — pull a
   field, run a regex, return the captured group. Already reserved
   in the YAML schema (`extract:`), not yet implemented in the
   renderer.

3. **Config-field source for metrics** — let a metric value come
   from an adapter instance configuration field rather than a
   response body. MPB exposes the `${@@@MPB_QUOTE_REQUEST_PARAMETERS
   <name> @@@MPB_QUOTE}` form in expressions, so the wire shape is
   known.

4. **Instanced groups in MPB UI** — the wire format
   `<ResourceGroup instanced="true">` is what Broadcom-authored
   paks (Kubernetes, FabricServer, PhysicalSAN) use, and what
   Onur's vCommunity Hardware pack uses via the Python Integration
   SDK. MPB UI / HTTP authoring doesn't expose it; we confirmed
   this earlier with api-explorer against Broadcom-built paks.

Any one of these closes today's loop. Regex extraction is the
cheapest (renderer change only, already-reserved YAML field).
Instanced groups is the most transformative (eliminates the need
for parent-child relationships entirely for hardware MPs) but the
biggest lift (new wire form, new YAML schema, new render path).

## How UniFi avoids all this

UniFi's data model gives MPB a free join: every Client object's
API response includes the uplink Device ID as a flat scalar field,
and every Device's response includes the Device ID as a flat
scalar field. Both sides have a real metric carrying the same
value, MPB compares them at collection time, edge appears. No
cross-request data, no regex, no constants — UniFi's data shape
matches MPB's relationship model out of the box.

Redfish is the opposite: parent-child lives in URL paths
(`/Systems/{id}/Processors/{id}`), not in flat scalar fields of
the child's body. Same hierarchy, different encoding, MPB Tier 1
can't bridge it.

## How Onur sidesteps the problem

The vmbro/VCF-Operations-Hardware-vCommunity adapter declares only
two object types — a config file and a single PhysicalServer —
and emits every PSU, fan, DIMM, drive, and firmware item as an
**instanced metric** on PhysicalServer using colon-delimited
naming (`Hardware|Power:PSU1|Power Output Watts`). One inventory
object per server, with hundreds of expandable per-component
metric instances hanging off it. No parent-child relationships
exist because there are no separate component objects.

This requires authoring the `<ResourceGroup instanced="true">`
describe.xml block, which MPB UI cannot produce. Onur works in
the Python Integration SDK (Docker container runtime), which
emits the wire format directly. Same outcome would be reachable
in our Tier 2 native Java SDK — full programmatic control over
the metric path strings, no MPB UI involved.

## What we shipped

- Five renderer fixes that arose during this investigation:
  - D27 regression gate (ResourceAttribute outside ResourceGroup)
  - REQUESTED_METRIC empty-array suppression (then unsuppressed when
    we discovered it was needed for the chain anchor signal)
  - `chain_anchor_stub` YAML field + stub-metric injection
  - Relationship dispatcher honors `--relationship-strategy` flag
  - `_trivial_shared_constant` actually injects the synthetic metric
- The `push-design` CLI command, which made MPB UI iteration cheap
  (one command instead of a curl ladder). This existed only as
  documented endpoint knowledge before today.
- `chain_anchor_stub` mechanism so MPs that bind a request purely
  to anchor children pass MPB's metric-completeness validator.

## What we did NOT ship

The actual relationship fix for BC's complaint. Dell stays at
"cleaner structure, still flat in the inventory tree." Closing
that gap requires one of the four framework capabilities above,
or a switch to Tier 2 SDK authoring.

## Lessons for the next contributor

1. **Audit inherited designs against the user's stated complaint
   before assuming a cleanup will fix it.** v4 1.x had
   `relationships: []` — the flat inventory wasn't a cleanup
   issue, it was a fundamental design omission. We spent
   significant time on cleanup before realizing the cleanup
   didn't address the complaint.

2. **MPB metric expressions can never be literal constants.**
   Every metric's value has to come from an API response body
   field or a request parameter. If a strategy in the renderer
   needs a constant matching key, MPB will reject it at Verify
   time even if the design imports cleanly.

3. **Test against MPB UI Verify before paking.** The `push-design`
   CLI now exists. Use it as the FIRST loop for any new MP —
   don't build a pak until the design is green in Verify against
   a mock or live source. Pak builds + sneaker-net are the
   expensive loop; MPB UI Verify is the cheap loop.

4. **The factory's three adapter_instance strategies were
   guesses.** They've now been empirically falsified. Don't
   re-trust them without re-validation against MPB UI; treat
   them as evidence MPB requires a different wire form than what
   the factory currently emits.

5. **For hardware MPs in particular, Tier 2 SDK is the right
   tool.** Tier 1 + Redfish hits this wall by construction. The
   framework's Tier 2 pipeline (commit 6861663) is Phase-1
   complete; the next adapter built against it should probably
   be a Dell-shape one to validate the framework against this
   exact problem.
