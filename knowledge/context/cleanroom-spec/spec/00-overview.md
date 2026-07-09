# VCF Operations Native Java Adapter SPEC — Overview

**Status**: DRAFT. First evidence pass from mpb-adapter (2026-05-15).
**Audience**: VCF-CF Tier 2 (Native) pipeline implementers.
**Scope**: Describe the API surface, lifecycle contracts, packaging
structure, and patterns observed in VCF Operations native Java
management-pack adapters (Track C) at the level needed to generate
new adapters mechanically.

## Non-goals

- The SPEC does not include any decompiled implementation source.
- The SPEC does not describe Track A (MPB-runtime-executed declarative
  content packs) or Track B (Integration SDK / Cloud Proxy
  containerized) — both are out of scope for the Tier 2 Native
  pipeline. (See `analysis/triage-report-2026-05-15.md` for triage.)
- The SPEC does not describe the MPB design schema (`builderJson`) or
  the MPB runtime internals — those belong to a separate Tier 1
  reference document.

## Vocabulary

| Term | Meaning |
|---|---|
| **Adapter** | A Java program loaded into the Operations appliance Tomcat that implements the `AdapterInterface3` contract and is invoked by the platform per a scheduled monitoring interval to discover and collect data from a target system. |
| **Adapter kind** | The named registration of an adapter (e.g., `ManagementPackBuilderAdapter`). Declared in `describe.xml` and used by the platform to route configuration / collection / actions to the correct adapter class. |
| **Adapter instance** | A configured deployment of an adapter — typically one per credentialed connection to a target system. Each adapter instance has its own `ResourceConfig` of kind `*AdapterInstance` (resource type `7`). |
| **Resource kind** | A class of monitored thing declared in `describe.xml` (e.g., `MongodbCluster`, `vSphereHost`). Has named identifiers, attributes (metrics + properties), and relationships. |
| **ResourceKey** | A runtime identity tuple uniquely naming an instance of a resource kind. Built from the resource kind + identifier values. |
| **Metric / Property** | Time-series numeric or discrete value attached to a resource. The SDK uses `MetricData` for both; properties are distinguished by a boolean on the `addMetricData` overload (presumably setting versioning behavior). |
| **describe.xml** | The declarative manifest at `<adapter>/conf/describe.xml` that registers an adapter kind's full surface (resource kinds, credential kinds, actions, alerts, capacity model, policy, etc.) with the platform. |
| **CollectResult** | The bucket the adapter fills during each `collect()` invocation. Contains per-resource updates (metrics, properties, status, events, relationships). |
| **Action** | A user-invokable operation on the monitored system, declared in `describe.xml` and executed by an adapter that implements `ActionableAdapterInterface`. |

## Track C runtime model

Each Track C adapter runs **inside the Operations appliance's Tomcat**
process (or a Cloud Proxy in collector-only deployments — but the
adapter binaries and contract are the same; deployment topology
differs from Track B's containerized model). The platform:

1. Loads the adapter's classes from `<deployment>/<adapter-kind>/`
   plus the runtime classpath (which includes
   `vrops-adapters-sdk-2.2.jar` and shared appliance libs).
2. Reads `<adapter-kind>/conf/describe.xml` to register the adapter
   kind's surface.
3. Constructs the adapter class declared (via mechanism not yet
   inventoried — likely a ServiceLoader, class-name in manifest, or
   convention).
4. For each configured adapter instance, calls `configure()` with the
   instance's `AdapterConfig`. Calls `test()` when the user clicks
   "Test Connection" in the UI.
5. On schedule (the monitoring interval declared per resource kind or
   globally), calls `collect()`. The adapter fills the SDK-provided
   `CollectResult` bucket via `addMetricData`, `addEvent`,
   `setResourceStatus`, etc.
6. Calls `discover(DiscoveryParam)` on demand to find new resources.
7. On user action invocation, calls `onAction(ActionParam)` if the
   adapter implements `ActionableAdapterInterface`.
8. Calls `discard()` on shutdown or adapter removal.

## SPEC section index

| § | File | Status | Evidence base |
|---|---|---|---|
| 01 | `01-adapter-lifecycle.md` — `AdapterInterface3` + `AdapterBase` + `adapter.properties` + packaging | DRAFT (pass 3) | SDK 2.2; mpb-adapter + vim + mongodb |
| 02 | `02-describe-xml.md` — declarative model overview + MPB-runtime emission model | DRAFT | mpb-adapter + vim + mongodb describe.xml; SDK describe classes; MPB-runtime `Describe*` components (Pass 7) |
| 02a | `02a-describe-xsd-canonical.md` — authoritative XSD-derived grammar; full enum vocabularies; never-observed-but-permitted surfaces | DRAFT (pass 10) | vim's describeSchema.xsd v6.3.0 read directly; cross-checked against 6.1.0 variants |
| 03 | `03-credential-model.md` — credential kinds + fields | DRAFT (pass 3) | mpb-adapter + mongodb credential kinds |
| 04 | `04-actions.md` — legacy actions AND modern NMP tasks | DRAFT (pass 2) | mpb-adapter (legacy); vim (NMP) |
| 05 | `05-resource-model.md` — ResourceKind/Group/Attribute/Identifier | DRAFT (pass 3) | mongodb's 11-kind, 513-attribute model |
| 06 | `06-metrics-units-expressions.md` — metric keys, units, expression language | DRAFT (pass 3) | mongodb's 189 ComputedMetrics |
| 07 | `07-relationships-cross-mp.md` — TraversalSpec/ResourcePath syntax + cross-MP attachment | DRAFT (pass 4) | vSphere's 25 kinds + 5 TraversalSpecs (incl. STORAGE_DEVICES cross-MP edge); mongodb's ExternalRelationship pattern; VCFAutomation's 9/9 cross-MP paths; ResourceDto bridge |
| 08 | `08-alerts-symptoms-recommendations.md` — Symptom/Alert/Recommendation grammar, condition types, boolean compounds, applyOn-scoping | DRAFT (pass 8) | mongodb (214 symptoms, 12 alerts) + vSphere `vmwarevi_adapter3` (517 symptoms, 119 alerts, full variety) |
| 10 | `10-mpb-builderfile-schema.md` — MPB BuilderFile runtime model (Tier 1 vocabulary) | DRAFT (pass 15) | `mpb_adapter-9.0.1-patch-1.jar` Kotlin model; validated against 3 real designs in pass 17 |
| 11 | `11-mpb-designer-wire-format.md` — MPB designer JSON wire format + pak generation pipeline; **MPB output is Track C-shaped (not Track A)** with per-pak generated runtime code | DRAFT (pass 17) | UniFi + phpIPAM + vSAN designer JSONs + corresponding built paks |
| 12 | `12-mpb-handoff-for-vcf-cf.md` — **consolidated MPB findings handoff for VCF-CF Tier 1 implementers**; stands alone for strategic picture | HANDOFF | all MPB passes synthesized |
| 13 | `13-classloading-and-classpath.md` — appliance shared classpath + per-pak classloader isolation; pak shape bundling guidance | DRAFT (pass 13) | common-lib/ + per-adapter lib/ + entry-class import analysis |
| 14 | `14-ui-and-operational-surfaces.md` — Methods + Actions + Faults + LaunchConfigurations + PowerState + Icon | DRAFT (pass 20) | vSphere (canonical) + vSAN (Faults at scale) + AppOSUCPAdapter3 |
| 15 | `15-tier2-handoff-for-vcf-cf.md` — **consolidated Tier 2 (Native Java) handoff for VCF-CF**; stands alone for strategic picture | HANDOFF | all Tier 2 passes synthesized |
| 16 | `16-platform-install-and-signing.md` — appliance install pipeline (CASA→Python 7-phase state machine) + empirical signature-validation behavior (unsigned-accept, skip-dates, opt-in checkSignature) | DRAFT (pass 23) | Navani field-evidence bundle from live devel appliance |
| 17 | `17-vcfcf-framework-design-guidance.md` — **forward-looking design guidance for `vcfcf-adapter-base.jar`**: 4-layer architecture, what belongs in framework vs per-pak, MVP build order, design tenets, open decisions | DESIGN-GUIDE (pass 26) | synthesis across all spec sections |
| 99 | `99-summary-and-vcf-cf-recommendations.md` — final synthesis | DRAFT | all passes |

## Pass-coverage status

| Adapter | Pass | Date | Coverage |
|---|---|---|---|
| mpb-adapter | 1 | 2026-05-15 | Lifecycle, action subsystem, credential-holder pattern, `adapter.properties` |
| vim | 2 | 2026-05-15 | NMP task system, SDK-pinning, partial-obfuscation, declaration-light/impl-heavy axis |
| mongodb | 3 | 2026-05-15 | Adapter abstraction framework (`aria-ops-core`), hierarchical resource model, metric key paths, isRate/isProperty, computed-metric expression language |
| vmwarevi_adapter3 (vSphere) | 4 | 2026-05-15 | **TraversalSpec/ResourcePath syntax incl. cross-MP edges**, VirtualMachine identifier shape, vSphere SDK interfaces (VcCommunication/VcManagement/CompatibilityChecker), `vcf-ops-data-sdk` discovered |
| NSXTAdapter | 5 | 2026-05-15 | Modern clean architecture; **declarative-vs-runtime topology dichotomy** (NSX uses runtime-pushed via SDK Relationships, 0 TraversalSpecs); adapter-instance lifecycle reuse confirmed |
| VCFAutomation | 6 | 2026-05-15 | **9/9 ResourcePaths cross-MP** (VMWARE + SupervisorAdapter); **ResourceDto bridge type discovered**; aggregator-archetype documented |
| (bulk surveys) | 7+ | 2026-05-15 | Remaining devel + marketplace adapters surveyed for pattern conformance and distinctive findings |

## Source of authority

The SDK jar `vrops-adapters-sdk-2.2.jar` (Navani 2026-05-15 devel pull)
is the **canonical API surface source** for this SPEC. Adapter
implementations corroborate usage patterns but do not extend or
override the contract — they compile against the SDK and obey its
shape.
