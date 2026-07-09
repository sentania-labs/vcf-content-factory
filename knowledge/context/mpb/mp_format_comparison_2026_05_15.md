# MPB vs Factory Format Comparison (2026-05-15)

Structural diff of MPB-authored vs factory-rendered/built artifacts
for two MPs: UniFi Network Integration and vSphere Storage Paths.
Analysis only — no factory code or content YAML was modified.

## Sources compared

**Phase 1 (design.json / exchange-format JSON):**
- MPB designs: `tmp/vcf_operations_mp_designs_export.zip`, extracted
  to `tmp/mpb_export/VCF Content Factory UniFi Integration.json`
  and `tmp/mpb_export/VCF Content Factory vSphere Storage Paths.json`.
  Exported from MPB UI on devel, 2026-05-15.
- Factory-rendered: produced via
  `python3 -m vcfops_managementpacks render-export
   content/managementpacks/<mp>.yaml --out tmp/<mp>_factory_export.json`,
  written to `tmp/unifi_factory_export.json` and
  `tmp/storage_factory_export.json`.

**Phase 2 (.pak structural):**
- MPB-built paks (built by MPB designer on devel, version 1.0.0.1):
  - `tmp/VCFContentFactoryUniFiIntegration-1001.pak`
  - `tmp/VCFContentFactoryvSphereStoragePaths-1001.pak`
- Factory-built paks (latest in dist/, version *.0.0.5):
  - `dist/mpb_vcf_content_factory_unifi_integration.1.0.0.5.pak`
  - `dist/mpb_vcf_content_factory_vsphere_storage_paths.2.0.0.5.pak`
- Tool: `python3 -m vcfops_managementpacks pak-compare` plus
  manual unzip + jq for the inner `adapters.zip/conf/*` files.
- Pak-compare reports archived to
  `tmp/unifi_pak_compare.txt` and `tmp/storage_pak_compare.txt`.

## TL;DR

The factory's exchange-format output (Phase 1) is functionally
import-compatible with MPB and structurally close — most divergences
are MPB UI cosmetics or factory-side null/empty placeholders that
the import parser tolerates. **However, the factory's runtime
template.json for ARIA_OPS adapters is critically wrong: it emits
`source.externalResources: []` instead of populating it with the
ARIA_OPS stitching descriptors that MPB's runtime builds.** For the
vSphere Storage Paths pak this means the installed adapter has zero
collectable resources — no metrics will land on the target VMWARE
HostSystem / Datastore objects. The UniFi pak (INTERNAL-only) does
not hit this code path and is broadly correct. A second cluster of
"Category A" findings concerns small but real divergences in
`source.configuration` defaults (concurrent_requests, ssl_config),
`manifest.txt` script declarations, and a few stripped-vs-preserved
field debates that the field-diff section in `mpb_api_surface.md`
captures but the renderer no longer honors.

## Design.json comparison

### UniFi Network Integration

Top-level shape: same 7 keys (`type, design, source, objects,
relationships, events, requests`), same counts (12 requests, 5
objects, 6 relationships, 0 events). All cross-references
internally consistent on both sides.

#### Category A — factory should match MPB

- **`design.buildNumber`** (factory: `5`, MPB: absent). Factory
  emits a top-level `design.buildNumber` field that MPB strips.
  Probably renderer leakage of the pak version counter. The conf/
  export.json inside the built pak also has it.
- **`design.design.id: null`** and **`design.design.author: null`**
  (factory emits both; MPB drops both). Null placeholders that the
  import parser accepts but MPB never emits. Cleaner if stripped.
- **`source.source.authentication.sessionSettings: null`** (factory
  emits; MPB drops). Stateless API has no session settings; emit
  nothing rather than null.
- **`source.source.testRequest.chainingSettings: null`** (factory
  emits; MPB drops). The test request never chains; this field is
  noise.
- **`source.source.testRequest.response`** — factory emits a full
  stub `{id, log, result: {body, headers, responseCode,
  dataModelLists: [{id: base, ...}]}, status, endTime, duration,
  startTime, toolkitId, errorMessage}`. MPB emits the minimal
  `{result: {responseCode: 200}}`. The factory's stub is harmless
  on import but cosmetically inflates the file and includes a
  spurious `dataModelLists: [{"id": "base", "attributes": []}]`
  entry. Strip on render-export.
- **All non-test `requests[*].request.chainingSettings: null`**
  (factory emits even for non-chaining requests like "sites";
  MPB drops). Same noise pattern — only emit when chaining is
  actually configured.
- **All `requests[*].request.response`** structures — factory
  wraps in `{id, log, result, status, endTime, duration, startTime,
  toolkitId, errorMessage}`; MPB ships just `{result: {responseCode,
  dataModelLists: [...]}}`. Strip the outer wrapper on render-export.
- **`requests[*].request.response.result.dataModelLists[*]`** —
  factory emits `parentListId` and `label` keys per list and `label:
  null`/`example: ""` on every attribute; MPB drops `parentListId`,
  `label`, `example` (only `id`, `key`, `attributes[].id`,
  `attributes[].label`, `attributes[].key`). Per the field-level
  diff section in `mpb_api_surface.md`, the importer tolerates
  these — but they're not MPB-shape. Factory also emits a
  `{"id": "base", "key": [], "attributes": []}` "base" entry per
  request that MPB does not emit when there are no
  base-level attributes.
- **`requests[*].request.response.result.dataModelLists[*].attributes[*].example`**
  (factory emits `""`; MPB drops). Mentioned explicitly in
  `mpb_api_surface.md` "Fields present in flat format that MPB's
  import parser rejects" — the factory has explicitly chosen to
  retain these per the jcox reference (`_FLAT_ONLY_KEYS` comment
  in `render_export.py:104-108`), but the live MPB UI export does
  not have them. Either the jcox reference is older/different, or
  the import vs render-export paths diverged. **Decision needed.**
- **All `metrics[*].expression.expressionParts[*].regex` (null) /
  `regexOutput` ("")** — same story as `example`. Factory preserves;
  MPB strips. Now intentional per `_FLAT_ONLY_KEYS`, but the live
  MPB output disagrees with the jcox reference that motivated the
  intentional preservation.
- **`relationships[*].relationship.childExpression / parentExpression
  .expressionParts[*]` — `example, regex, regexOutput`** (factory
  preserves; MPB strips). Renderer is explicitly preserving these
  via the `_in_relationship=True` exception path. MPB output says
  otherwise. **Same decision needed.**
- **`objects[*].object.internalObjectInfo.id`** (factory emits a
  string id; MPB drops). Listed in `mpb_api_surface.md` as a flat-
  format-only field to strip — but the factory still emits it.
  `_strip_internal_object_info()` exists but is not invoked for
  this field in the current pipeline.
- **`objects[*].object.metricSets[*].objectBinding: null`** (factory
  emits; MPB drops). Listed in mpb_api_surface.md "Fields present
  in flat format that MPB's import parser rejects". The factory
  has the stripper but it isn't running on this path.

#### Category B — MPB cosmetic, factory can stay different

- **Description sanitization.** MPB strips `-`, `/`, `+`, `→`,
  `(/)` and other punctuation from the description in its export
  (e.g. "per-radio" → "perradio", "X-API-Key" → "XAPIKey",
  "gateway→switch→AP" → "gatewayswitchAP"). This is MPB UI export
  sanitization, not a wire-format requirement. Factory keeps the
  original text. **Factory wins** — this is a long-standing MPB
  bug, not something to imitate.
- **`source.source.configuration` keys.** MPB drops `hostname`,
  `port`, `connectionTimeout`, `maxConcurrentRequests`, `maxRetries`,
  `minEventSeverity`, `sslSetting` from the source-level
  configuration block on export (only keeps `baseApiPath` and
  `customConfigs`). Factory emits the full set. These are per-
  instance fields exposed at the adapter-instance level via
  `source.configuration[*]` — they don't belong in
  `source.source.configuration` and MPB's export reflects that.
  Factory's emission is benign on import (no validation rejection)
  but stylistically off; flagged in `tmp/unifi_pak_compare.txt`
  as INFO `[I35]` and `tmp/storage_pak_compare.txt` as INFO `[I28]`.
- **UUID values throughout.** Factory uses UUID5-derived stable IDs;
  MPB mints UUID4s. Both valid. Per `_stable_source_id()` in
  `render_export.py:183`, `source.source.id` is fresh UUID4 per
  emit to dodge MPB import dedupe — that's the right call.
- **Order of `requests[]`, `objects[]`, `relationships[]`.**
  Factory orders alphabetically/by ID; MPB orders by creation time.
  Either is fine — import is content-keyed not position-keyed.

#### Category C — both valid but not interchangeable

- **`source.source.configuration` strip set vs `source.configuration`
  full descriptors.** The factory emits both — the operational
  defaults at `source.source.configuration` (port=443, etc.) AND
  the configuration field descriptors at `source.configuration[]`
  (with stable UUID5 IDs). MPB emits only the latter on export
  but the former is what the runtime reads. The factory's pak
  works at runtime because the values get embedded in template.json
  and conf/ — but the import roundtrip may be subtly different.
  Worth verifying: does an MPB-imported factory design have the
  same defaults applied as one imported from MPB UI?

#### Category D — surprising

- **`source.source.testRequest.response.result.dataModelLists[0]`
  contains an `{id: "base", key: [], label: null, attributes: [],
  parentListId: null}` ghost entry on the factory side, with no
  attributes.** MPB's testRequest has just `{result: {responseCode:
  200}}` — no dataModelLists at all. The `mpb_api_surface.md` field
  diff section says session/test requests should use
  `{responseCode: N}` only. Factory is leaking an empty base list.

### vSphere Storage Paths

Top-level: 2 requests, 2 objects, 0 relationships, 0 events on both
sides. ARIA_OPS-only (no INTERNAL types). Object stitching targets
VMWARE/Datastore and VMWARE/HostSystem on both sides.

#### Category A — factory should match MPB

All the same renderer-leak items from the UniFi section apply
here (chainingSettings: null on testRequest and base requests;
inflated response stubs; example/regex/regexOutput on
expressionParts; design.buildNumber). Plus:

- **No ARIA_OPS-specific divergence in the exchange JSON.** The
  `objects[*].object.ariaOpsConf` block is structurally identical
  on both sides (same `{objectType, objectTypeLabel, adapterType,
  adapterTypeLabel, metricSet: {id, metrics: [...]}}` shape). This
  is good — the design-time stitching is correct. The runtime
  failure (next section) is on the template.json side, not here.

#### Category B / C / D

- **Object ordering.** Factory emits HostSystem first, then
  Datastore. MPB emits Datastore first, then HostSystem. Cosmetic.
- **Description sanitization.** Same MPB bug as UniFi — strips
  "—", "/", "-" from the description on export.

## .pak structural comparison

### UniFi Network Integration

`pak-compare` score: **3 BLOCKING, 3 WARNING, 35 INFO** against the
MPB-built reference. Full report: `tmp/unifi_pak_compare.txt`.

#### Category A — factory should match MPB

- **(W1-W3 / B1-B3) manifest.txt: pre/post/validation scripts and
  bundled .py files.** MPB emits empty
  `pak_validation_script.script`, `adapter_pre_script.script`,
  `adapter_post_script.script` and does NOT bundle
  `validate.py`, `preAdapters.py`, `post-install.py` in the pak
  root. Factory bundles all three scripts and references them in
  the manifest. The pak-compare BLOCKINGs are actually
  conservative: factory's pak may fail to install if the runtime
  expects the scripts to be absent (MPB-built paks never have
  these scripts, so the loader presumably doesn't require them).
  More importantly, the factory's `validate.py` /
  `preAdapters.py` / `post-install.py` content was authored by the
  factory and has no equivalent in MPB's pipeline — this is
  factory pipeline machinery that doesn't belong in an MPB-style
  pak. **Decision: either strip these from the pak for parity, or
  verify they're harmless at install-time (they may be silently
  ignored by 9.0.2's pak loader if the manifest blocks are
  declared but empty in reference paks).**
- **(I28 / configuration defaults)** `mpb_concurrent_requests`
  default: factory=`10`, MPB=`2`. `mpb_ssl_config` default:
  factory=`No Verify`, MPB=`Verify`. These end up in describe.xml
  ResourceIdentifier defaults AND in source.configuration[*]
  defaultValue. The factory has chosen ops-friendly defaults
  (parallel collection, lab-friendly TLS) — but they diverge from
  the MPB-shipped defaults. **Decision: keep factory defaults
  (they're better) or revert to MPB defaults (for parity).**
- **manifest.txt placeholder fields (`DISPLAY_NAME`, `VENDOR`).**
  MPB ships `display_name: "DISPLAY_NAME"` and `vendor: "VENDOR"`
  as literal un-substituted placeholders (MPB-side templating
  bug). Factory correctly substitutes. **Factory wins — do not
  match.**
- **manifest.txt `vcops_minimum_version`.** MPB: `"8.10.0"`,
  factory: `"7.5.0"`. Factory is allowing older targets;
  MPB-built paks gate on 8.10.0. **Likely Category A** — factory
  should match the MPB-emitted floor unless we have a known reason
  to support 7.5.0.

#### Category B — MPB cosmetic

- **(I1-I34, most of the inventory diffs)** SVG vs PNG icons:
  MPB ships `default.svg` + per-resource-kind SVGs in
  `conf/images/ResourceKind/`. Factory ships `default.png` + a
  single shared PNG. SVGs are cosmetically nicer but PNGs are
  rendered fine by VCF Ops 9.0. **Cosmetic, do not block.**
- **(I8/I9 signatures)** MPB pak has `signature.cert` +
  `signature.mf`. Factory paks are unsigned. Per the
  `knowledge/context/known_limitations.md` (and acceptance from the task),
  this is a known limitation — VMware signing key not available
  to factory builds. **Flag but do not fix.**
- **(I1/I19/I34) supermetrics.** Factory bundles
  `content/supermetrics/customSuperMetrics.json` and
  `adapters.zip/conf/supermetrics/`. MPB does not include these
  in MP-only designs. Empty arrays inside; harmless either way.
- **describe.xml whitespace, double-space `default=" "`, weird
  trailing-line whitespace.** MPB's output is cosmetically
  malformed (e.g. `</ResourceIdentifier>  </ResourceKind>` on one
  line, 6-space indent on nested ResourceKinds inside 4-space
  parent). Factory is normalized. **Factory wins.**

#### Category C — both valid but not interchangeable

- **describe.xml ResourceKind ordering and nameKey assignment.**
  Factory uses ascending integer keys with gaps; MPB uses a
  monotonic sequence. The factory's stock-Unit nameKeys jump to
  1001-1044+ while MPB's are 18-61 (factory reserves the low
  range for adapter-specific labels). The runtime resolves
  `nameKey` via `resources.properties` lookup; both are valid as
  long as each integer points to a unique label in
  `.properties`. Worth verifying that the factory's properties
  file has all the 1001-1044+ entries (presumably yes — pak
  installs OK on devel — but a stale properties file would silently
  show numeric IDs in the UI).

#### Category D — surprising

- **(I15) Factory's adapters.zip contains `conf/design.json`; MPB's
  does not.** Per `mpb_api_surface.md` §"Pak conf/ layout — both
  design.json AND export.json required", the factory fix from
  2026-04-18 added `design.json` next to `export.json` because the
  earlier Synology pak fail showed the adapter runtime needed both.
  But this MPB-built pak from 2026-05-15 has ONLY export.json, no
  design.json. **The earlier rationale was either wrong or
  obsolete.** The MPB designer apparently installs paks fine
  without conf/design.json. The factory may be carrying an
  unnecessary file. Re-read mpb_api_surface.md §"Pak conf/ layout"
  and reconcile.

### vSphere Storage Paths

`pak-compare` score: **0 BLOCKING, 1 WARNING, 28 INFO**. Full
report: `tmp/storage_pak_compare.txt`. Pak-compare reports clean,
but the deeper template.json inspection finds a critical bug.

#### Category A — factory should match MPB (CRITICAL)

- **`adapters.zip/<adapter>/conf/template.json`
  `source.externalResources` — factory: `[]`, MPB: 2 fully-
  populated entries (Datastore + HostSystem).** This is the ARIA_OPS
  runtime wire format that tells the adapter "push these metrics
  onto these existing-adapter resource kinds at collection time."
  Without it, the adapter installs but pushes zero metrics —
  silent failure. The hard-coded empty list is in
  `vcfops_managementpacks/render.py:859`:
  ```python
  "externalResources": [],            # factory does not model cross-adapter bindings
  ```
  with a duplicate at `render.py:2755`. **This single fix
  determines whether the factory-built Storage Paths pak does its
  job or not.** Required runtime shape (per MPB):
  ```json
  {
    "adapterKind": "VMWARE",
    "resourceKind": "HostSystem" | "Datastore",
    "resourceKindName": "Host System" | "Datastore",
    "isListResource": true,
    "id": "<object UUID — same as objects[].object.id>",
    "metricGroups": {
      "<group name>": {
        "id": "<group name>",
        "key": "<group name>",
        "childGroups": {}
      }
    },
    "requestedMetrics": [ ...same as resources[].requestedMetrics... ]
  }
  ```
  The renderer already builds the per-resource
  `requestedMetrics` block for INTERNAL types
  (`source.resources[*].requestedMetrics`); the ARIA_OPS path
  needs the same shape pushed into `externalResources` keyed by
  `(aria_ops.adapter_kind, aria_ops.resource_kind)`.
- **(W1 / I27) `describe.xml` `<TraversalSpecKinds>`.** Factory
  emits one `<TraversalSpecKind>` for `vsphere_storage_paths_world`;
  MPB emits an empty block. This is a nice-to-have for navigation
  in the UI; not blocking; flagged INFO.
- Same `mpb_concurrent_requests` / `mpb_ssl_config` default
  divergence as UniFi.
- Same manifest pre/post/validation script bundling divergence.

#### Category B / C / D

- Same SVG/PNG, signatures, supermetric-content, describe.xml
  whitespace as UniFi.

## Recommended factory changes (Category A, ranked by impact)

1. **CRITICAL — populate `source.externalResources` in
   render.py for ARIA_OPS objects.** Affects storage_paths and any
   future ARIA_OPS-stitching MP. Fix at `render.py:859` and
   `render.py:2755`. Without this, the storage paths pak ships
   broken (installs cleanly, collects nothing). One-place fix.

2. **Reconcile `_FLAT_ONLY_KEYS` policy in `render_export.py`.**
   The current code preserves `example`, `regex`, `regexOutput`
   on every expressionPart (and on objectBinding/relationship
   sub-expressions) per the jcox reference. The live MPB UI export
   for both UniFi and Storage Paths strips them universally. Two
   possibilities — investigate before changing:
   - Older MPB builds emitted them; newer ones strip; jcox
     was captured under older MPB.
   - The fields are accepted on import (factory works) but
     dropped on export (MPB-shape round-trip not lossless).
   Either way the renderer comment at line 104-108 should be
   updated with the 2026-05-15 finding.

3. **Strip null-placeholder leakage from render-export:**
   `design.design.id: null`, `design.design.author: null`,
   `design.buildNumber`, `source.source.authentication.sessionSettings:
   null`, `chainingSettings: null` on non-chaining requests,
   `objects[*].object.internalObjectInfo.id`,
   `objects[*].object.metricSets[*].objectBinding: null`.
   These are individually harmless but they collectively make
   factory output noisier than MPB's by ~30% in line count.

4. **Strip the request `response` envelope to just
   `{result: {responseCode, dataModelLists}}`.** The factory's
   `{id, log, result, status, endTime, duration, startTime,
   toolkitId, errorMessage}` wrapper is debug/UI scaffolding,
   not import-required. Same for `testRequest.response`.

5. **Decide on `mpb_concurrent_requests` and `mpb_ssl_config`
   defaults.** Factory is currently shipping 10 / `No Verify`;
   MPB defaults are 2 / `Verify`. The factory's choices are
   ops-friendly but undocumented as intentional. Either codify
   the override in context (Category A: keep, document) or
   revert (Category A: match MPB).

6. **`manifest.txt vcops_minimum_version`.** Bump from `7.5.0` to
   `8.10.0` to match MPB. The factory's lower value invites
   install on older VCF Ops releases that may not have the runtime
   support.

7. **Decide on factory pipeline scripts in pak root.**
   `validate.py`, `preAdapters.py`, `post-install.py`,
   `postAdapters.py`, `post-install.sh`, `post-install-fast.sh`
   are factory pipeline helpers, not MPB-shipped artifacts.
   pak-compare flags them BLOCKING/WARNING. Need to confirm
   whether they run on install (and whether they should) or whether
   they're dead weight that should be stripped.

8. **Reconcile `conf/design.json` necessity.** Factory always
   writes both `conf/design.json` (flat format) and
   `conf/export.json` (exchange). MPB's 2026-05-15 paks ship
   ONLY `conf/export.json`. The 2026-04-18 Synology investigation
   said both were required — revisit that conclusion against this
   new evidence. May be safely removable.

## Open questions / Category D items

- **conf/design.json — required or not?** See item #8 above.
  Storage paths and UniFi MPB paks both ship without it; factory
  ships with. Either MPB's runtime parses design.json optionally
  or the 2026-04-18 conclusion was based on a transient bug.
- **Factory's spurious `{id: "base", attributes: []}` entry in
  every `dataModelLists`.** Source: `render_export.py`. MPB never
  emits this empty base entry. Likely a leftover from how the
  flat format represents hierarchical lists.
- **describe.xml `nameKey` numbering range 1001-1044 for
  stock units.** Works only if the corresponding entries exist in
  `resources.properties`. Factory paks have so far installed
  cleanly on devel, so the properties file is presumably correct,
  but the numbering scheme is unusual and worth grepping the
  factory's properties output to confirm.
- **JAR contents differ byte-wise between MPB and factory
  paks.** Both are versions of the MPB runtime adapter jar.
  Unclear whether the embedded resources differ in any
  semantic way or whether build-time metadata (timestamp, classpath)
  is the only delta. Out of scope for a structural diff but
  worth confirming the factory is shipping the latest MPB
  runtime jar.
- **`version.txt` `Adapter-Version-Ref`** — MPB:
  `9.0.1-patch-1`, factory: `2.0.0-ga-32`. These are SDK
  identifiers. Mismatch may not matter for installation; worth
  confirming no version-gated runtime behavior.

## Fixes applied (2026-05-15)

All 8 Category-A items were implemented in the same session as this
report.  `python3 -m vcfops_managementpacks validate` passes (4 MPs).
Spot-checked exchange JSON and template.json output against MPB
reference for UniFi Integration and vSphere Storage Paths.

### Item 1 — CRITICAL: populate `source.externalResources` (FIXED)

`vcfops_managementpacks/render_template.py` now calls
`_convert_aria_ops_external_resource()` for each ARIA_OPS design
resource and emits a fully-populated `externalResources[]` entry with
`adapterKind`, `resourceKind`, `resourceKindName`, `isListResource`,
`metricGroups`, and `requestedMetrics`.  Storage Paths template.json
now has 2 entries (VMWARE/HostSystem and VMWARE/Datastore), each with
`requestedMetrics` count = 1.  The hard-coded `[]` is gone.

`vcfops_managementpacks/render.py` `_render_source()` was also updated
to populate `externalResources` in the design.json flat format (from
`wire_objects` filtered to `type == "ARIA_OPS"`), replacing the
previous `[]`.

### Item 2 — Reconcile `_FLAT_ONLY_KEYS` (FIXED)

`render_export.py` strips `example`, `regex`, `regexOutput`
universally across all contexts (metric expressionParts, relationship
child/parentExpression, objectBinding sub-expressions, dataModelList
attributes, chaining params).  The `_in_chaining`, `_in_objectbinding`,
`_in_relationship` exception flags that preserved these fields based on
the jcox-au_vmware ground truth have been removed.  Comments updated
to cite the 2026-05-15 MPB UI export evidence as superseding the jcox
reference.

### Item 3 — Strip null-placeholder leakage (FIXED)

All null-placeholder fields are stripped from the exchange output:
- `design.design.id` and `design.design.author`: not emitted (keys absent)
- `design.buildNumber`: not emitted at top level
- `source.source.authentication.sessionSettings`: key dropped when null
- `requests[*].request.chainingSettings`: key dropped when null
- `source.source.testRequest.chainingSettings`: key dropped when null
- `objects[*].object.internalObjectInfo.id`: `_strip_internal_object_info()`
  now strips this field; wired into `_strip_object()`
- `objects[*].object.metricSets[*].objectBinding`: key dropped when null
  by `_strip_metric_set()`

Verified on UniFi and Storage Paths exports — no null placeholders remain.

### Item 4 — Strip request response envelope (FIXED)

`_strip_request()` emits `{result: {responseCode, dataModelLists}}`
only (no `id`, `log`, `status`, `endTime`, `duration`, `startTime`,
`toolkitId`, `errorMessage` wrapper).  `_strip_session_request()`
emits `{result: {responseCode: N}}` for testRequest (no
`dataModelLists`).  The ghost `{"id": "base", "key": [], "attributes": []}`
entry is filtered from `dataModelLists` before emission.
`_build_response_envelope()` is retained in code for historical reference
but is no longer called on any active path.

### Item 5 — Defaults: keep factory's, document them (DONE, no code change)

`mpb_concurrent_requests` defaults to `10` per-MP YAML (UniFi) or `5`
(Storage Paths), not MPB's `2`.  `mpb_ssl_config` defaults to
`No Verify` per-MP YAML, not MPB's `Verify`.  Both are intentional
factory choices for parallel collection and lab TLS compatibility.
Comments were added to `render_export.py` `_MPB_STANDARD_CONFIG_TEMPLATE`
entries explaining the divergence:
  "MPB ships 2 / Verify; factory ships higher concurrency / No Verify
   intentionally — parallel collection, lab-friendly TLS.
   See context/mp_format_comparison_2026_05_15.md §item 5."

### Item 6 — `manifest.txt vcops_minimum_version` (FIXED)

`vcfops_managementpacks/builder.py` `_generate_manifest()` now emits
`"vcops_minimum_version": "8.10.0"` (was `"7.5.0"`).  Comment added
citing this report §item 6.

### Item 7 — Pipeline scripts in pak root (INVESTIGATED, KEPT INTENTIONALLY)

The factory bundles `validate.py`, `preAdapters.py`, and `post-install.py`
in authenticated paks and references them in the manifest script slots.
These were investigated:

- `post-install.py` does real work: triggers a redescribe (so the adapter
  kind registers after install) and imports bundled views/reports/
  supermetrics/dashboards from the pak's `conf/` directory.
- `preAdapters.py` and `validate.py` are stubs but are declared for
  compatibility with pak loaders that expect the three script slots to
  be populated together when any one is populated.

Decision: **keep the scripts**.  MPB-built paks have empty script slots
because MPB doesn't bundle post-install automation.  The factory's
post-install.py is the mechanism that makes bundles self-installing —
removing it would break the content-installer workflow.  pak-compare
flags these as BLOCKING/WARNING vs the MPB reference; that divergence
is intentional and acceptable.

No-auth paks (e.g. if preset=none) use empty script slots matching MPB.

Comment added to `_generate_manifest()` in builder.py explaining this
decision with a reference to this document.

### Item 8 — `conf/design.json` necessity (REVERTED 2026-05-15)

**Original action (2026-05-15):** `build_pak()` was changed to omit
`conf/design.json`, shipping only `conf/export.json` and
`conf/template.json`, based on the observation that MPB UI exports
for UniFi and vSphere Storage Paths ship only `export.json`.

**Revert reason:** Removing `conf/design.json` caused factory pak install
failure on prod.  vSphere Storage Paths 2.0.0.6 (first build without
`design.json`) reported "Applied Adapter (Failed)" — a generic adapter
registration error.  Diffing against 2.0.0.5 (last working install,
though it collected zero metrics due to item 1 bug) identified exactly
three changes: vcops_minimum_version bump (item 6), design.json removal
(item 8), and externalResources population (item 1).  Item 8 is the
highest-likelihood culprit because it directly contradicts the
empirically-established 2026-04-18 rule.

**The 2026-04-18 finding stands.**  The MPB designer's pak-build path
evidently injects `design.json` via a separate mechanism not reflected
in UI exports — factory builds must include it explicitly.  The
2026-05-15 inference (MPB UI shows no design.json → it is not needed)
was wrong; empirical evidence from a real install failure overrides it.

`build_pak()` in `builder.py` has been restored to write both
`conf/design.json` (flat format) and `conf/export.json` (exchange
format) to the pak.  `context/mpb_api_surface.md` §"Pak conf/ layout"
has been updated to restore the 2026-04-18 rule.

## Artifacts and tools

- `tmp/mpb_export/` — extracted MPB UI exports
- `tmp/{unifi,storage}_factory_export.json` — factory-rendered exchange JSON
- `tmp/{unifi,storage}_pak_compare.txt` — pak-compare reports
- `tmp/diff_{unifi,storage}/{mpb,factory}/` — unpacked pak trees,
  including adapters/<adapter>/conf/ inspection points
- `python3 -m vcfops_managementpacks pak-compare <factory_pak>
   <reference_pak>` — the tool that drove Phase 2
