# MPB Tier 1 and `<ResourceGroup instanced="true">`

**Question.** Can the MPB Tier 1 design wire format (`design.json` /
BuilderFile / `template.json`) emit a describe.xml with
`<ResourceGroup instanced="true">` — the construct that produces
colon-instance statkey paths like
`Hardware|Power:PS1|Power Output Watts`?

**Answer (high confidence, evidence-based).** **No.** MPB's
Tier 1 authoring surface has no field that maps to the
`instanced` attribute. Every describe.xml emitted by an MPB-built
pak in our reference set hard-codes `instanced="false"` on every
ResourceGroup it produces. The `instanced="true"` construct
exists in the platform XSD and is exercised by Broadcom-built
Java/SDK paks (VMware Kubernetes, Physical SAN, FabricServer) and
by the Python Integration SDK (Onur's `HardwarevCommunity`) — but
not by MPB.

This advances `context/cleanroom-spec/spec/05-resource-model.md`
§152 from "semantics TBD" to **"semantics confirmed; MPB does not
expose them."** The describe.xml feature is real, well-formed,
and runtime-supported. The MPB compiler simply doesn't author it.

## 1. Wire-form evidence

### 1.1 Real `<ResourceGroup instanced="true">` blocks

Found in Broadcom-built **legacy Java/SDK** paks (NOT MPB):

| Pak | File | Line | Element |
|---|---|---:|---|
| vmware-mpforkubernetes-2.2.0 | `KubernetesAdapter3/conf/describe.xml` | 395 | `<ResourceGroup instanced="true" key="Usage" nameKey="2024">` (nested under `<ResourceGroup key="Cpu" instanced="false">`) |
| vmware-mpforkubernetes-2.2.0 | same | 457 | `<ResourceGroup instanced="true" key="Interface" nameKey="2035">` (nested under `<ResourceGroup key="Network">`) |
| vmware-mpforkubernetes-2.2.0 | same | 480 | `<ResourceGroup instanced="true" key="Device" nameKey="2049">` (nested under `<ResourceGroup instanced="false" key="Filesystem">`) |
| vmware-mpforkubernetes-2.2.0 | same | 614 | `<ResourceGroup instanced="true" key="taints" nameKey="2176">` (flat, top-level under ResourceKind) |
| vmware-mpforkubernetes-2.2.0 | same | 724,735 | `tolerations`, `podCondition` (flat instanced groups under Pod) |
| vmware-mpforkubernetes-2.2.0 | same | 1006 | `<ResourceGroup key="K8S_Events" nameKey="2078" instanced="true">` |
| vmware-mpforphysicalsan-8.12.0 | `PhysicalSANAdapter3/conf/describe.xml` | 95 | `<ResourceGroup instanced="true" key="ArrayPorts" namekey="397">` |
| vmware-mpforphysicalsan-8.12.0 | same | 106 | `<ResourceGroup instanced="true" key="Configuration" namekey="345">` |
| vmware-mpforphysicalsan-8.12.0 | `FabricServerAdapter3/conf/describe.xml` | 30,55,63,77,100,108,122,141 | 8 instanced groups (ConfigurationProperties, SwitchPortStatistics, etc.) |

Canonical attribute set inside an instanced group — taken from
Kubernetes' `Cpu|Usage` example (lines 395–403):

```xml
<ResourceGroup instanced="false" key="Cpu" nameKey="2005" validation="">
  <ResourceGroup instanced="true" key="Usage" nameKey="2024" validation="">
    <ResourceAttribute dashboardOrder="1" dataType="double"
                       defaultMonitored="true" key="Total" nameKey="2053" />
    <ResourceAttribute dashboardOrder="2" dataType="double"
                       defaultMonitored="true" key="User" nameKey="2054" />
    <ResourceAttribute dashboardOrder="3" dataType="double"
                       defaultMonitored="true" key="System" nameKey="2055" />
  </ResourceGroup>
  ...
</ResourceGroup>
```

That declaration produces, at collection time, statkeys of the
form `Cpu|Usage:<instance>|Total` — matching the Dell empirical
pattern `Hardware|Power:PS1|Power Output Watts`. Nested instanced
also works: line 480 `Filesystem|Device:<dev>|Free` and the Dell
case `Hardware|Power:PS1|Input Ranges|Maximum Frequency` both
attest to multi-level nesting under an instanced group.

The colon is a literal separator: `<groupKeyPath>:<instanceName>|<sub-attribute-path>`.

### 1.2 `<ResourceGroup instanced="false">` everywhere in MPB paks

Both MPB-built paks examined emit only `instanced="false"`:

| Pak | File | Total ResourceGroups | `instanced="true"` count |
|---|---|---:|---:|
| Rubrik 1.1.0.25 (MPB) | `mpb_rubrik_adapter3/conf/describe.xml` | 8 | **0** |
| Ubiquiti UniFi 1.0.0.7 (MPB) | `mpb_ubiquiti_unifi_adapter3/conf/describe.xml` | 14 | **0** |
| HPE SimpliVity 1.5.0.2 (Java SDK, not MPB) | `HPESimplivityVropsAdapter/conf/describe.xml` | 11 | **0** |
| Pure Storage 3.2.0 (Java SDK, not MPB) | `PureStorageAdapter/conf/describe.xml` | 94 | **0** |
| Our `mpb_vcf_content_factory_dell_poweredge_v4` (factory MPB) | (live recon) | — | **0** |

MPB only ever emits two ResourceGroup *patterns* (both `instanced="false"`):
- `<ResourceGroup key="summary" instanced="false">` — top-level container for plain attributes/metrics
- `<ResourceGroup key="relationships" instanced="false">` — top-level container for stitching/foreign-key properties

Plus user-authored nested non-instanced groups via `BuilderMetricGroup.childGroups`.

## 2. BuilderFile (`template.json`) schema — no `instanced` field

From the disassembled MPB code we already documented in
`context/mpb_builderfile_schema.md` (which is identical to the
cleanroom mirror at `context/cleanroom-spec/spec/10-mpb-builderfile-schema.md`):

```kotlin
data class BuilderHttpResource(
    id, label, resourceKind, name, identifiers,
    isListResource: Boolean,                            // ← controls list-resource emission, NOT instanced groups
    icon,
    requestedMetrics: List<BuilderMetricRequest>,
    metricGroups: Map<String, BuilderMetricGroup>,      // ← THE group declaration
    metrics: List<IDescribedMetric>,
)

data class BuilderMetricGroup(
    id, key, label,
    childGroups: Map<String, BuilderMetricGroup>,       // ← only nesting; no instanced flag
)

data class BuilderHttpMetric(
    id, key, label,
    expression: ExpressionString,
    dataType: DataType,                                 // STRING | DECIMAL only
    property: Boolean,
    kpi: Boolean,
    groups: List<String>,                               // ← metric→group membership (group keys)
    unit: String,
    timeseries: BuilderHttpTimeseries?,
)
```

`BuilderMetricGroup` has **four fields total** — none of them is
`instanced`. There is no boolean and no enum that toggles the
emission of `instanced="true"` on the corresponding describe.xml
ResourceGroup. `isListResource` exists but operates at the resource
level (it controls whether a request produces one resource per item
in a JSON array, i.e., separate ResourceKey instances — not
instanced subgroups within one resource).

## 3. `design.json` schema — confirmed via reference paks

The in-pak `design.json` (the compiled designer output that ships
inside MPB paks) confirms the BuilderFile schema. Resources have
`metricGroups: {}` and metrics carry `groups: []` — but populated
or not, neither field has a sibling `instanced` boolean.

Audit across all four MPB design samples on disk:

| Design file | `groups: []` arrays | `groups: [...]` non-empty | `instanced`/`instance_required` keys |
|---|---:|---:|---:|
| `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7_MP_Builder_Design.json` (UI export) | 317 | 0 | 0 |
| `tmp/reference_paks/phpIPAM-1.0.0.11_MP_Builder_Design.json` (UI export) | 683 | 0 | 0 |
| `tmp/reference_paks/vSAN default storage policy.json` (UI export) | 57 | 0 | 0 |
| `reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json` (UI export) | 286 | 0 | 0 |
| `mpb_rubrik_adapter3/conf/design.json` (in-pak) | — | 0 | 0 |
| `mpb_ubiquiti_unifi_adapter3/conf/design.json` (in-pak) | — | 0 | 0 |

Boolean fields that DO exist on metric-like objects:

- In-pak (compiled) design.json: `kpi`, `property`
- UI-export standalone design.json: `advanced`, `editable`

Neither set contains anything that could plausibly drive
`instanced="true"`. The MPB designer UI has no toggle for it.

### Two design.json shapes (note for downstream)

There are two distinct JSON shapes both called "design.json":

1. **In-pak** (`<adapter>/conf/design.json`) — what the runtime sees.
   Top-level keys: `constants`, `id`, `name`, `pakSettings`,
   `relationships`, `source`, `version`. The MPB Designer compiles
   to this. Resources are at `source.resources[]`.

2. **UI-export** (downloaded from the MPB Designer UI as
   `*_MP_Builder_Design.json`) — what a human imports back into
   the UI. Top-level keys: `content`, `design`, `events`,
   `objects`, `relationships`, `requests`, `source`. Resources
   are at `objects[].object`.

Both confirm absence of any `instanced` field.

## 4. Mapping: design.json → BuilderFile → describe.xml

| describe.xml | BuilderFile (template.json) | design.json | Status |
|---|---|---|---|
| `<ResourceGroup key=… instanced="false">` | `BuilderMetricGroup{key, label, childGroups}` (any non-empty entry in `BuilderHttpResource.metricGroups`) | `resource.metricGroups[<key>]` | Authorable in MPB |
| `<ResourceGroup key=… instanced="true">` | **(no field exists)** | **(no field exists)** | **NOT authorable in MPB** |
| `<ResourceGroup key="summary" instanced="false">` | Implicit; always emitted by MPB describe-emitter | (always emitted) | Authorable (auto) |
| `<ResourceGroup key="relationships" instanced="false">` | Implicit; auto for external-resource bindings | (auto for ARIA_OPS bindings) | Authorable (auto) |
| `<ResourceAttribute key=…>` inside an instanced group | (no path) | (no path) | **NOT authorable in MPB** |

The MPB describe-emitter (documented in
`context/mpb_describe_xml_emission.md`) reads `BuilderMetricGroup`
entries from the BuilderFile and writes them as nested
`<ResourceGroup instanced="false" key=… nameKey=…>` elements. The
`instanced` attribute is hardcoded to `false` in the emitter
because the source-model class doesn't carry the value.

## 5. Implications for `src/vcfops_managementpacks/`

### 5.1 YAML schema delta on `MetricSetDef` (loader.py line 482)

To author instanced groups via the factory, the loader's
`MetricSetDef` (and/or a new sibling type) would need:

- A way to declare that a metricSet's collected rows are
  **per-instance under a parent group**, not **per-resource as a
  ResourceKind**. Currently the factory's "Pattern C" splits
  per-component data into separate ResourceKinds with separate
  ResourceKeys (matching how MPB itself thinks). The instanced
  pattern instead keeps everything on the parent resource and
  uses the colon-separator instance name as a discriminator.

- A grammar would resemble (illustrative; not normative):
  ```yaml
  metricSets:
    - from_request: power_supplies
      list_path: PowerSupplies
      instanced_group:                # NEW
        parent_path: ["Hardware", "Power"]
        instance_field: Name           # which response field becomes the instance label
      bind:
        - field: OutputWatts
          metric_key: "Power Output Watts"
        - field: InputWatts
          metric_key: "Power Input Watts"
  ```

- The loader needs to surface a clear error if any author tries to
  combine `instanced_group` with `stitch_to`/`stitch_match_field`
  (ARIA_OPS objects already attach to a foreign resource) or with
  the chained_from cardinality patterns that imply separate rows.

### 5.2 Renderer changes — and the wall they hit

`render_template.py`, `render.py`, `render_export.py` would each
need to:

1. Emit an entry in `BuilderHttpResource.metricGroups[<parent_key>]`
   shaped like `BuilderMetricGroup{key, label, childGroups}` — plus
   an instanced-flagged child. **The BuilderFile schema has no
   field for this.** MPB's runtime, when it parses template.json,
   ignores any unknown fields. Even if the factory wrote
   `"instanced": true` into template.json, MPB's describe-emitter
   wouldn't read it.

2. Emit per-metric `groups: ["<parent_key>", "<instanced_key>"]`
   linking each ResourceAttribute to its group ancestry. This part
   the factory could implement today (the `groups` field is in
   the schema; we just never populate it).

3. Configure the request handler to use the response field as the
   **instance name** rather than as the resource's identifier
   property. Today the factory's renderer always emits
   `BuilderHttpResource` with `isListResource: true` and uses the
   `listExpression` to fan out one resource per row. The instanced
   pattern requires fanning the rows out into per-attribute
   instance buckets under a single parent resource — a completely
   different runtime path.

**Conclusion: emitting `instanced="true"` is not a renderer
flag-flip. It requires the MPB runtime to have a code path that
honors an `instanced` toggle in the BuilderFile, and our disassembly
indicates that code path does not exist.** Adding the YAML field
and emitting the bit in template.json would produce a pak that
MPB's emitter then ignores — the describe.xml would still come out
with `instanced="false"`.

### 5.3 Can existing `Members.*` / list_id binding be adapted?

No. `listId` (e.g., `"data.power_supplies.*"`) tells the runtime
how to fan out rows from a JSON response into separate
`BuilderHttpResource` instances — separate ResourceKeys, each
with one full set of attributes. This is the factory's current
"Pattern C". The instanced-group pattern is the inverse: one
ResourceKey, with attributes that fan out internally indexed by an
instance name. The two are mutually exclusive at the runtime
level — `listId` already consumed the array dimension by emitting
multiple resources. Flipping a single flag will not collapse N
resources back into instance-buckets under 1 resource.

### 5.4 Path forward — three options for the orchestrator

1. **Stay on Pattern C** for the v5 Dell PowerEdge re-author. Live
   with separate ResourceKinds (PowerSupply, Fan, etc.) — accept
   that statkey paths will be flat per-component instead of
   colon-instanced. This is what our v4 pak already does. The
   tradeoff: views/dashboards need to traverse to the child
   resources to read per-component values, instead of reading them
   all from the parent PhysicalServer.

2. **Promote Dell PowerEdge to Tier 2 (native SDK).** Use the
   Python Integration SDK or a Kotlin Tier 2 adapter to author
   `<ResourceGroup instanced="true">` directly, the way Onur's
   `HardwarevCommunity` does. This is the only path that yields
   exactly the colon-instance wire form observed empirically.
   `context/cleanroom-spec/spec/05-resource-model.md` §152 should
   be updated to note this Tier 2-only status.

3. **Probe MPB further via live UI.** Build a deliberately
   instanced design in the MPB UI (if any UI control turns out to
   exist that we haven't found by reading the disassembly) and
   diff the resulting pak. Low probability of success — the
   reference designs are explicit on this — but it's the only
   experiment that could falsify finding #1.

## 6. Risks / unknowns

- **MPB version coverage.** All MPB paks examined are MPB ~2.0
  paks (Rubrik 1.1.0.25 is `mpb_clients-2.0.0-ga-32.jar`; UniFi
  1.0.0.7 is similar). If a newer MPB version added an instanced
  toggle, we wouldn't see it in these references. Validation
  requires a current MPB Designer UI walkthrough.

- **`childGroups` semantics on the wire.** We confirmed the field
  exists (`BuilderMetricGroup.childGroups: Map<String, BuilderMetricGroup>`)
  but we did not find a populated example in the four reference
  designs. The describe-emitter mapping `childGroups → nested
  <ResourceGroup>` is documented but unverified end-to-end.

- **`metric.groups: []` semantics.** All four reference designs
  leave this empty. We infer (per cleanroom spec) that
  `metric.groups: ["a","b"]` would emit the ResourceAttribute
  inside the chain `<ResourceGroup key="a"><ResourceGroup key="b">…</ResourceGroup></ResourceGroup>`,
  but we have no positive example. This affects option 1 (Pattern C
  with nested grouping) more than it affects the instanced-group
  question.

- **`metric.groups` and `metricGroups` cross-talk.** The runtime
  must reconcile a flat `metric.groups: ["Hardware","Power"]` with
  a resource-level `metricGroups: {"Hardware": {childGroups: {"Power": …}}}`.
  Convention or auto-creation? Unknown. Out of scope for the
  instanced question but relevant for any factory work that
  populates `groups`.

## 7. Cleanroom-spec status update

- `context/cleanroom-spec/spec/05-resource-model.md` §152 — advance
  from "semantics TBD" to: "Semantics confirmed by reference-pak
  inspection — `instanced='true'` indicates the runtime fans the
  group's `<ResourceAttribute>` children out into per-instance
  buckets at collection time, producing statkeys of the form
  `<groupPath>:<instanceName>|<attrPath>`. **The MPB Tier 1
  authoring surface does NOT expose this attribute** — only legacy
  Java SDK paks and Python Integration SDK paks declare instanced
  groups. Tier 2 only."

- `context/cleanroom-spec/spec/10-mpb-builderfile-schema.md` (and
  mirror `context/mpb_builderfile_schema.md`) — Limitations
  section should explicitly add:
  "`<ResourceGroup instanced='true'>` — not exposed; emitted only
  by SDK paks. The BuilderFile `BuilderMetricGroup` has no
  instanced flag."

## 8. Files examined

Read-only extraction; no writes outside `context/`.

Paks examined (uncompressed into `/tmp/instanced_recon/` as
working scratch; safe to delete):
- `reference/references/hol-2501-lab-files/HOL-2501-02/Module 1/vmware-mpforphysicalsan-8.12.0-21592050.pak`
- `reference/references/hol-2501-lab-files/HOL-2501-02/Module 2/vmware-mpforkubernetes-2.2.0-24050822.pak`
- `reference/references/brockpeterson_operations_management_packs/Rubrik-1.1.0.25.pak`
- `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7.pak`
- `tmp/reference_paks/PureStorageAdapter-3.2.0_signed.pak`
- `tmp/reference_paks/HPESimplivityVropsMP-1.5.0.2.pak`

Standalone design files audited:
- `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7_MP_Builder_Design.json`
- `tmp/reference_paks/phpIPAM-1.0.0.11_MP_Builder_Design.json`
- `tmp/reference_paks/vSAN default storage policy.json`
- `reference/references/brockpeterson_operations_management_packs/Rubrik Management Pack Design.json`

Spec context consulted:
- `context/cleanroom-spec/spec/02-describe-xml.md`
- `context/cleanroom-spec/spec/02a-describe-xsd-canonical.md`
- `context/cleanroom-spec/spec/05-resource-model.md` (§152 is the
  TBD this doc closes)
- `context/cleanroom-spec/spec/10-mpb-builderfile-schema.md`
- `context/cleanroom-spec/spec/11-mpb-designer-wire-format.md`
- `context/mpb_describe_xml_emission.md`
- `context/mpb_builderfile_schema.md`
- `context/mpb_designer_wire_format.md`
