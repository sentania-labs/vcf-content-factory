---
name: vcfops-sdk-adapter
description: >
  Playbook for authoring Tier 2 Java SDK management pack adapters in
  the VCF Content Factory (content/sdk-adapters/). Covers the adapter
  lifecycle, reflection-tolerant vim25 SOAP reads over JAX-WS, the
  Suite API property pusher that bypasses the Java SDK SuiteAPIClient,
  ARIA_OPS stitching identity (the MOID trap), the canonical benchmark
  loader contract, the unreadable-is-not-compliant scoring rule, and
  the build-sdk → pak-compare verify loop. Use this skill whenever
  writing, modifying, debugging, or reviewing a Tier 2 SDK adapter's
  Java source, describe.xml, or build. The compliance adapter
  (content/sdk-adapters/compliance/) is the reference implementation.
---

# VCF Ops Tier 2 SDK Adapter Playbook

Tier 2 adapters are Java that runs inside the VCF Ops collector,
talks to a target API (vim25 SOAP, REST, …), and pushes
metrics/properties onto resources. Unlike Tier 1 (MPB YAML → JSON
descriptor), Tier 2 is real code with a real classpath. This skill is
the accumulated how-not-to-get-burned for that surface.

Reference implementation: `content/sdk-adapters/compliance/`.

## Project layout

```
content/sdk-adapters/<adapter>/
  adapter.yaml          # name, version, build_number, adapter_kind, entry_class, bundled_content
  describe.xml          # ResourceKinds, ResourceIdentifiers, credential/connection params
  src/                  # adapter Java source (com/.../*.java) — the ADAPTER repo's own src/, not the factory's top-level src/
  lib/                  # bundled jars (vim25, vapi-runtime, ...) — classpath is pak-isolated
  profiles/             # input data (e.g. benchmark CSVs)
  resources/            # resources.properties (nameKey -> label resolution)
  icons/
  CANONICAL_SCHEMA.md   # the data contract — do not silently break it
  REFERENCE.md          # generated from describe.xml + resources.properties
  CHANGELOG.md          # one line per build
```

## Build / verify loop

Cheap loop first — every structural error caught here is one not paid
for at pak-install time:

```
python3 -m vcfops_managementpacks validate-sdk content/sdk-adapters/<adapter>
python3 -m vcfops_managementpacks build-sdk    content/sdk-adapters/<adapter> -o dist
python3 -m vcfops_managementpacks pak-compare   dist/<built>.pak --reference-dir <ref-dir>
```

`scaffold-sdk "<Name>"` generates a skeleton. **Zero BLOCKING from
pak-compare is the install gate.** Bump `adapter.yaml` `build_number`
and add a `CHANGELOG.md` line every build.

## Classloader isolation — the first-principles constraint

Each pak gets its **own classloader**. You cannot borrow jars from
another installed adapter (you cannot reach the VMWARE adapter's
vSphere SDK). Anything you need must be bundled in `lib/`. Plain
`vim25.jar` exposes a narrower surface than the full vSphere/vSAN
Management SDKs — when a read needs a richer interface
(`VsanConfigSystem`, `VsanFileServiceConfig`, …) that isn't on your
classpath, that's a **classpath gap**: keep the control informational,
document it, never fake the read.

## vim25 over JAX-WS — read reflection-tolerantly, never cast

The single most important coding pattern. JAX-WS bindings drift across
vCenter 7/8/9 point releases: `Boolean` vs `boolean` flips
`getX()`/`isX()`; some fields are inherited from non-public
superclasses; subclass shapes vary. **Never cast to a concrete vim25
subclass.** Walk the graph with PropertyCollector + reflective getters.

The primitives (all in the compliance `VSphereClient`):

- `getRawProperty(moRef, "config.defaultPortConfig")` — PropertyCollector
  `retrieveProperties` for any property path; returns the unwrapped
  JAX-WS value (or null).
- `getMoRef(moRef, path)` — follow a path that resolves to a child MoRef.
- `getViewMembersTyped(containerView, "DistributedVirtualSwitch")` —
  generic inventory walker (type is a parameter, not hardcoded).
- `invokeGetter(target, "getSecurityPolicy")` — reflective zero-arg
  getter; `NoSuchMethodException` → null (skip), never throw.
- `readBoolean(target, "isEnabled", "getEnabled")` — try both accessor
  shapes; null when neither exists.
- `readBoolPolicy(secPol, "getForgedTransmits")` — unwrap a `BoolPolicy`
  to its `.value`/`.isValue()`; null = "not present", not false.

Rule of thumb: a missing field is **null → skip**, never an exception
and never a default. An accessor that throws crashes the whole
collection cycle.

### Logical name → vim path translation

The data contract uses *logical* keys (`securityPolicy.forgedTransmits`,
`vsanConfig.enabled`), not raw vim paths
(`config.defaultPortConfig.securityPolicy.forgedTransmits.value` +
BoolPolicy unwrap). Something must own that translation. Today it's
bespoke per-reader (`readSecurityPolicy`, `getClusterVsanConfig`). When
generalizing to a data-driven reader, decide *where* the vim-structural
knowledge lives (a Java recipe registry keyed by logical prefix, or a
read-recipe column in the source data) and keep the translation in one
place — scattering it reintroduces silent mis-reads.

## Pushing data — the Suite API property pusher

The Java SDK's `SuiteAPIClient` / `ResourceCollection` path **drops
foreign-resource data** (it only keeps metrics for resources the
adapter itself discovered). To stitch onto existing VMWARE resources
you bypass it: use the injected `suiteAPIClient.getClient()` via
reflection to POST properties/stats directly to the Suite API
(`SuiteApiPropertyPusher` in the compliance adapter). Push DTO-backed
resources by their resolved resourceId.

## ARIA_OPS stitching identity — the MOID trap

ARIA_OPS objects attach data to resources another adapter owns
(VMWARE HostSystem, VirtualMachine, …); they don't appear in
describe.xml/template.json as discoverable kinds. To attach correctly
you must resolve the *foreign* resourceId. **MOID is not unique across
vCenters** — `host-12` exists in every vCenter. Join on a stable key:
FQDN hostname, or vCenter `instanceUuid` + MOID. Getting this wrong is
silent data corruption (compliance data landing on the wrong host).
`getVCenterInstanceUuid()` (`ServiceContent.about.instanceUuid`) is the
stable per-vCenter discriminator.

## Dynamic metrics / properties

Override `isDynamicMetricsAllowed()` → `true` when property keys vary
at runtime (e.g. per active profile). `addProperty()` builds a
`MetricKey` with `isProperty=true`; `getAutoDiscoveryEnabled()` →
`true`. `|` is a safe separator in Tier 2 property keys (the `|`/`:`
restriction is a Tier 1 MPB metric-label rule only).

## The bulk-read dynamic pattern (zero code per new control)

Where the target exposes a whole namespace in one call, read it all
once and look the wanted key up — then new keys are pure data, no code.
Compliance does this for advanced settings: `queryOptions(mgr, null)`
returns *every* option; the evaluator just does a map lookup +
typed compare. Any new `advanced_setting` row works next cycle with no
Java change. Prefer this shape whenever the API allows it.

## Unreadable is NOT compliant — the cardinal scoring rule

The defining failure mode (and the reason the compliance canonical
schema exists): a value the adapter failed to read must never become a
pass or a sentinel score.

- A read that finds nothing → **skip** the control (drop it from the
  denominator) or surface it as an explicit unreadable/error signal.
- Zero-divisor contract: when *no* controls were evaluable against a
  resource, score = 100.0 **with totalCount = 0**, and every caller
  must refuse to fold a `totalCount==0` result into a per-resource or
  fleet average. `total_count = 0` is how an operator tells "perfect"
  from "nothing was actually evaluated."
- No-signal resources (read succeeded but nothing scored, or the read
  failed) get a **profile-name-only push** so they still appear in the
  metric browser without polluting rollups with a fake score.

Never widen the "evaluable" set without backing it with a real
assessment path. `advanced_setting` and `vim_property` are evaluable in
compliance precisely because each has a verified reader; adding a kind
to the evaluable set without a reader silently scores garbage.

## Canonical data loader contract

Parse input by **header name, never by column position.** Positional
indexing tuned to one source format reads garbage when a newer source
reorders columns — and garbage-in produces a deceptively perfect score.
Build a `name → index` map from the header row; hard-fail (throw, take
the adapter Down with a descriptive message) if a required column is
missing. Normalize vendor formats into one canonical schema *before*
the adapter loads them; the adapter parses only the canonical schema.

## Events

Pak-runtime event format is a known TOOLSET GAP — events are stripped
from SDK pak builds. Prefer factory symptoms + alerts on the pushed
metrics over adapter-emitted events.

## Gaps — name them, never hide them

- **TOOLSET GAP** — builder/validator/template/runtime-format limit →
  orchestrator routes to `tooling` / `api-explorer`.
- **CLASSPATH GAP** — needed SDK not bundleable → control stays
  informational, documented.
- **DESIGN GAP** — an unanswerable decision (stitching key, action
  model) → stop and ask; never guess when wrong guesses corrupt data.
