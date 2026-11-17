# mpb-adapter — per-adapter analysis

**Adapter kind**: `ManagementPackBuilderAdapter`
**Source pak**: `inputs/from-devel/paks/MPBAdapter-902025137890.pak`
**Decompiled at**: `analysis/decompiled/mpb-adapter/` (from
`inputs/from-devel/installed/mpb-adapter-installed.tar.gz`)
**Analysis date**: 2026-05-15
**Priority**: HIGH — dual-tier insight (Tier 1 + Tier 2)

## Structure (deployed form)

```
mpb-adapter.jar                                       # entry-point shim (59KB, 40 classes)
mpb-adapter/
    conf/
        describe.xml                                  # static adapter declaration
        resources/resources*.properties               # localization (10 locales)
        version.txt                                   # Major-Version=9, Minor-Version=0, Implementation-Version=25137890, Vcops_Minimum_Version=8.10.0
    lib/
        mpb_adapter-9.0.1-patch-1.jar                 # MPB runtime engine — the heavy lifter
        vcops-suiteapi-client-2.2-all.jar             # client for Operations' own REST API (SuiteAPI)
```

This is the canonical Track C sub-shape **C1-light**: a thin entry-point
jar at root + a `lib/` with the implementation dependencies.

## Lineage and naming

`mpb-adapter.jar` (root) uses package `com.vmware.adapter.mpb.*` — the
**new** VMware-namespaced shim. `mpb_adapter-9.0.1-patch-1.jar` (in
lib/) is the older naming convention; package inspection (not yet done)
will tell us whether the runtime is also `com.vmware.adapter.mpb.*` or
older (`com.integrien.*` or `com.vmware.vcops.mpb.*`). Flag: revisit
during Tier 1 deep-dive if useful.

## What it implements

`com.vmware.adapter.mpb.MPBAdapter` extends `AdapterBase` and
implements `ActionableAdapterInterface` (from
`com.integrien.alive.common.adapter3.action`). Overridden methods:

| Method | Override | Notes |
|---|---|---|
| `onConfigure(ResourceStatus, ResourceConfig)` | yes | required (abstract in base) |
| `onDescribe()` | yes | combines static describe.xml with dynamic content loaded from MPB designs at runtime |
| `onDiscover(DiscoveryParam)` | yes | required (abstract in base) |
| `onCollect(ResourceConfig, Collection<ResourceConfig>)` | yes | required (abstract in base) |
| `onTest(TestParam)` | yes | optional override |
| `onAction(ActionParam)` | yes | required by `ActionableAdapterInterface` |
| `checkActionStatus(ActionResult, ActionParam)` | yes | required by `ActionableAdapterInterface` |
| `onDiscard()` | yes | optional cleanup |
| `onChangePassword` | NO | uses base default |
| `onCheckCertificate` | NO | uses base default |
| `onStopCollection` | NO | uses base default |
| `onStopResources` / `onRemoveResources` | NO | uses base default |

No mix-in interfaces beyond `ActionableAdapterInterface` (no
`PartialCollectInterface`, `INonDisruptiveCertificate`,
`LicensableSolution`, or DataFeedHandler).

**Pattern observed: minimum-viable Track C adapter** = override 6
abstract+optional methods (configure, describe, discover, collect,
test, discard) on `AdapterBase`. Everything else uses base defaults.

## describe.xml shape

Static surface declared:

- **AdapterKind**: `ManagementPackBuilderAdapter`, schema version 8,
  namespace `http://schemas.vmware.com/vcops/schema`
- **One ResourceKind**: `ManagementPackBuilderAdapterInstance`
  (type=`7` — adapter instance), one identifier `COLLECTOR_UUID`
  (string, required)
- **One CredentialKind**: `ManagementPackBuilderAdapter_Custom_Credential`
  — a generic **multi-slot credential holder**. Fields
  `sensitiveCredKey1/sensitiveCredValue1` through `sensitiveCredKey20+`
  (20+ slots observed). Mix of `password="true"` (encrypted) and
  `password="false"` (cleartext) — values masked when sensitive.
  Design pattern: one MPB adapter instance holds credentials for many
  target systems, referenced by key from MPB designs at runtime.
- **Two Actions**:
  - `CollectionPreview` (`actionType="update"`) — preview what a design
    would collect. Inputs: `builderJson` (the MPB design),
    `configuration`, `credentials`, `logLevel`, `trustedCertificates`.
    UI affordance: render a sample of resources/metrics for a design
    without committing it.
  - `RunRequest` (`actionType="update"`) — execute an arbitrary HTTP
    request. Used for design authoring / debugging.
- **Methods**: parameter declarations for the two actions. Notable
  knobs on RunRequest: `execTimeoutSeconds`, `requestTimeout`,
  `maxRetries`, `maxConcurrentRequests` — runtime tuning surface
  exposed to designs.

## Action subsystem — first concrete look

`mpb-adapter.jar` contains a structured action runtime:

- `com.vmware.adapter.mpb.MPBAdapter` (top-level, AdapterBase subclass)
- `com.vmware.adapter.mpb.ActionRunner` — manages async action lifecycle:
  `getAction(String) → IntegrationDesignerAction`,
  `startAction(IntegrationDesignerAction)`, `removeAction(String)`,
  `onDiscard()`
- `com.vmware.adapter.mpb.actions.IntegrationDesignerAction` (abstract or interface)
- `com.vmware.adapter.mpb.actions.CollectionPreviewAction` (with nested
  `CollectionPreviewActionParams` — a parameter binder)
- `com.vmware.adapter.mpb.actions.RunRequestAction` (with
  `RunRequestActionParams`)
- `com.vmware.adapter.mpb.actions.ActionLogger`
- Result models in `com.vmware.adapter.mpb.actions.result.collectionpreview.*`:
  `CollectedAdapter`, `CollectedData` (with `CollectedDataType`),
  `CollectedEvent`, `CollectedIdentifier`, `CollectedRelationship`,
  `CollectedResource`, `CollectedResourceKind`
- Result models in `com.vmware.adapter.mpb.actions.result.request.*`:
  `DataModelAttribute`, `DataModelList` (with inner `DataModel`),
  `HttpResponseHeader`, `HttpResponseResult`

**Pattern observed: action async-execution lifecycle** — actions can be
long-running, registered with an `ActionRunner` keyed by ID. The
`checkActionStatus(ActionResult, ActionParam)` method on
`ActionableAdapterInterface` is the polling endpoint. This explains
why the interface has two methods: the kick-off and the status-check.

## Theories — pan-out / disprove ledger

### CONFIRMED — mpb-adapter is the MPB runtime engine packaged as a Track C native adapter (CLAUDE.md priority hypothesis)

Evidence:
- Entry-point `MPBAdapter` class is a textbook Track C native adapter
  (extends `AdapterBase`, full `AdapterInterface3` contract).
- The `lib/mpb_adapter-9.0.1-patch-1.jar` is the actual MPB runtime.
- `describe.xml` exposes only the adapter's *own* static surface (one
  resource kind, one credential holder, two actions). The actual
  resource kinds / metrics / relationships that MPB content packs
  declare must be loaded dynamically at runtime — likely from a
  per-instance JSON design document (the `builderJson` parameter in
  the `CollectionPreview` action).

### CONFIRMED + REFINED — the legacy `mpb_adapter-*.jar` rule from CLAUDE.md

The original rule expected to find `lib/mpb_adapter-*.jar` at the
**outer pak level** as a Track A signature. That was looking in the
wrong place. The jar exists — in the MPBAdapter pak's **inner archive
under `mpb-adapter/lib/`** — as a runtime dependency of the Track C
shim. CLAUDE.md was right that the jar exists; it was wrong about who
ships it (it's a Track C runtime engine, not a Track A content-pack
signature).

### CONFIRMED — dual-tier insight is real

The two actions (`CollectionPreview`, `RunRequest`) plus the action
result models (`CollectedAdapter`, `CollectedData`, `CollectedEvent`,
`CollectedIdentifier`, `CollectedRelationship`, `CollectedResource`,
`CollectedResourceKind`, `DataModelAttribute`, `DataModelList`,
`HttpResponseResult`) tell us exactly what an MPB runtime collects
into. **This is the Tier 1 design schema.** A design (in JSON) maps
HTTP responses into these structures, and the runtime translates them
into the SDK's `MetricData`/`ResourceKey`/`Relationships`/etc. on
collect.

### PARTIALLY DISPROVEN — "Track C adapters need a vendor SDK in lib/"

mpb-adapter has only `vcops-suiteapi-client-2.2-all.jar` + the runtime
engine. No vendor SDK because mpb-adapter is generic (it doesn't talk
to a single vendor's product — designs do, at runtime). Refined
theory: vendor SDK presence is a feature of the **adapter's target
system**, not of Track C as a class.

### NEW THEORY — `vcops-suiteapi-client-*.jar` is the "look across to other Operations data" SDK

mpb-adapter has it as the only non-self lib. Hypothesis: this is the
Operations Suite API client, used when an adapter needs to query
Operations' own data (e.g., look up resources from other adapters,
post computed metrics, etc.). To test: see whether other Track C
adapters that don't need cross-adapter queries omit it (likely yes for
pure data collectors), and whether vim has it. Flag for pass 2.

### NEW THEORY — MPB designs are JSON

The action parameter is literally named `builderJson`. The
`DataModelList`/`DataModel`/`DataModelAttribute` classes are likely
the in-memory JSON document model. Confirms what was always assumed
about the MPB Designer UI output, but now we have evidence.

### NEW THEORY — MPB primarily collects from HTTP

The `RunRequest` action's tunables (`requestTimeout`, `maxRetries`,
`maxConcurrentRequests`, `execTimeoutSeconds`) and result types
(`HttpResponseResult`, `HttpResponseHeader`) suggest MPB designs are
predominantly HTTP-driven. The runtime probably supports REST /
SOAP / arbitrary HTTP, with retry / concurrency limits baked in. May
or may not support non-HTTP protocols — needs evidence from the
runtime jar to confirm.

## Tier 1 implications (VCF-CF MPB design authoring)

When VCF-CF generates an MPB design, the design schema (the JSON
shape `builderJson`) must produce, at runtime, structures matching the
`Collected*` result models. The translation chain is:

```
MPB design JSON
  ↓ (loaded by mpb_adapter runtime at scan time)
HTTP requests + response parsing rules
  ↓ (executed on collect())
DataModelList / HttpResponseResult
  ↓ (mapped per design's extraction rules)
CollectedAdapter
  └── CollectedResource (with CollectedIdentifier, CollectedData, CollectedEvent, CollectedRelationship)
       └── CollectedResourceKind
  ↓ (passed through AdapterBase.addMetricData / processProperties / etc.)
MetricData, ResourceKey, Relationships, ExternalEvent
```

VCF-CF Tier 1 needs:
- A design schema that targets the Collected* result types as its
  semantic model.
- Knowledge of the credential-slot pattern (designs reference creds by
  key name, not value).
- The runtime's HTTP tunables as design knobs.
- Awareness that `CollectionPreview` is the validation/dry-run path.

## Tier 2 implications (VCF-CF native adapter SPEC)

mpb-adapter is a clean reference for the minimum-viable Track C
adapter. Lifecycle observations to add to the SPEC:

1. `AdapterInterface3` is the contract (already in SDK survey).
2. `AdapterBase` is the standard implementation strategy.
3. Required overrides: `onConfigure`, `onDescribe`, `onDiscover`, `onCollect`.
4. Optional but commonly overridden: `onTest`, `onDiscard`.
5. Action support is a separate concern via `ActionableAdapterInterface` (mix-in).
6. Adapters that don't talk to a single vendor system can be very thin (mpb-adapter root jar is 59KB / 40 classes including a complete action library).

## Open questions for follow-up

1. **Runtime architecture of `mpb_adapter-9.0.1-patch-1.jar`** — what
   does it expose? Likely an in-memory interpreter for designs, an
   HTTP client pool, expression evaluator, JSON-path or similar
   extraction. Defer to a dedicated Tier 1 deep-dive pass; not needed
   for the Tier 2 SPEC.
2. **MPB design schema** — the actual structure of `builderJson`.
   Defer to Tier 1 pass; SPEC doesn't need this.
3. **Does mpb-adapter use `vcops-suiteapi-client` for anything beyond
   self-registration?** Could reveal a "post-process collected data via
   Suite API" pattern that informs Tier 2.
4. **`ActionableAdapterInterface` full contract** — only seen via
   `MPBAdapter`'s two overrides. Need to javap the interface itself in
   a pass 2 spot-check.

## Confidence

- Tier 1 dual-tier insights: **High** — the action declarations and
  result types are unambiguous evidence of the design→collection chain.
- Tier 2 lifecycle confirmation: **High** — mpb-adapter is a clean
  reference and the SDK survey corroborates.
- Specific MPB runtime internals: **Not yet attempted** — out of scope
  for this pass.
