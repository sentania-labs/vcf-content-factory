# Distribution-view "No data to display" — property distributions rendered as numeric metric distributions

**Investigation date:** 2026-07-13. **Instances:** devel
(`vcf-lab-operations-devel.int.sentania.net`) + prod
(`vcf-lab-operations.int.sentania.net`), VCF Operations 9.x lab,
self-signed cert. **Trigger:** vcommunity-vsphere pak 0.0.0.11 dashboard
"ESXi Host Details" (`d6c4fc3f-c517-403e-ac3a-ec86c5e14624`): the four
distribution widgets ("ESXi Host Versions" `8a6d966f-76f4-4cd0-8e33-97fa3c6c0e0d`,
"ESXi Host Models"/Hardware, "ESXi Host Power State", "ESXi Host Maintenance
State") show "No data to display" and an Info dialog "Metrics displaying 0 of
23", while the pinned list-view widget on the same dashboard renders all 9
hosts (version + model columns) fine. Binding was already fixed in build 11
(PR #54: `selfProvider:true` + world resource entry).

> **UNSUPPORTED ENDPOINTS.** Uses `/suite-api/internal/views/{id}/data/export`
> and `/ui/vcops/services/router` (Ext.Direct), both requiring
> `X-Ops-API-use-unsupported: true` / a UI session. No back-compat guarantee.

**Read-only throughout — all live calls were GETs. No lab objects created,
nothing to clean up.**

---

## Headline verdict

The four distribution ViewDefs are **structurally deficient**: they declare a
string **resource property** (`summary|version`, `hardware|vendorModel`,
`runtime|powerState`, `runtime|maintenanceState`) as a **numeric metric** and
bucket it with a **fixed numeric histogram [0,100] / 10 buckets**. The widget
therefore queries the metric subsystem for a numeric metric that does not
exist → "Metrics displaying 0 of 23" → empty chart. The prime suspect from the
brief (the ViewDef, not the pin) is **confirmed**.

The known-working vendor original (same UUID, same attribute) declares the
column as `isProperty=true` + `isStringAttribute=true` and buckets it with a
**dynamic DISCRETE** control. This is the exact structural delta.

**This is NOT the same root cause as the pin/binding issue** (that was
`dashboard_selfprovider_pin_wire_format.md`). Binding is proven fixed; the data
is empty because the view asks the wrong subsystem for the wrong kind of value.

---

## The exact structural delta (our build 11 vs vendor known-working)

Both are the same view id `8a6d966f`, same attribute `summary|version`, same
subject `VMWARE/HostSystem`, same `distribution-view` DataProvider, same
`bar-chart` Presentation. Only the attribute-item shape and buckets-control
differ:

| Property | Our build 11 (BROKEN) | Vendor original (WORKING) | Fatal? |
|---|---|---|---|
| `isStringAttribute` | **`false`** | `true` | **yes** |
| `isProperty` | **`false`** | `true` | **yes** |
| buckets `isDynamic` | **`false`** | `true` | **yes** |
| buckets `dynamicCalcFunction` | (absent) | `DISCRETE` | **yes** |
| buckets `minValue`/`maxValue`/`bucketCount` | `0.0`/`100.0`/`10` | (absent) | yes (numeric histogram is wrong model) |
| `rollUpType` | `AVG` | (omitted for property) | no (harmless — list-view property cols carry it and work) |
| `rollUpCount` | `1` | `0` | no |
| `transformations` | `[CURRENT]` | (omitted) | no |
| `addTimestampAsColumn`/`isShowRelativeTimestamp` | `false`/`false` | (omitted) | no |
| buckets `isSum` | (absent) | `false` | no (defaulted) |
| metadata `distributionColor` | (absent) | `4ECAC2` | no (cosmetic) |

Our build-11 XML (extracted from
`dist/vcfcf_sdk_vcommunity_vsphere.0.0.0.11.pak`,
`content/reports/ESXi_Host_Versions_vCommunity/content.xml`), attribute item:
```
objectType=RESOURCE, attributeKey=summary|version, isStringAttribute=false,
adapterKind=VMWARE, resourceKind=HostSystem, rollUpType=AVG, rollUpCount=1,
transformations=[CURRENT], isProperty=false, displayName=ESXi Version,
addTimestampAsColumn=false, isShowRelativeTimestamp=false
buckets-control: isDynamic=false, minValue=0.0, maxValue=100.0, bucketCount=10
```
Vendor known-working XML
(`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/ESXi Host Versions vCommunity.xml`):
```
objectType=RESOURCE, attributeKey=summary|version, isStringAttribute=true,
adapterKind=VMWARE, resourceKind=HostSystem, rollUpCount=0, isProperty=true,
displayName=ESXi Version
buckets-control: dynamicCalcFunction=DISCRETE, isDynamic=true, isSum=false
```

**All four affected views share the identical defect** (each is a distribution
over a string property; vendor originals all use isProperty=true +
isStringAttribute=true + DISCRETE):

| View (ours) | id | attribute | vendor original file |
|---|---|---|---|
| ESXi Host Versions vCommunity | `8a6d966f-…` | `summary|version` | ESXi Host Versions vCommunity.xml |
| ESXi Host Hardware vCommunity | `8342e94a-…` | `hardware|vendorModel` | ESXi Host Hardware Models vCommunity.xml |
| ESXi Host Power State vCommunity | `56f47a85-…` | `runtime|powerState` | ESXi Host Power State vCommunity.xml |
| ESXi Host Maintenance Mode vCommunity | `2a1ce101-…` | `runtime|maintenanceState` | ESXi Host Maintenance State vCommunity.xml |

---

## Q1 — direct render of our view (the internal export endpoint is a RED HERRING here)

`GET /internal/views/8a6d966f/data/export?resourceId=<rid>`
(`X-Ops-API-use-unsupported: true`). devel vSphere World =
`ba1fe374-23fa-4584-9ca5-705cf1c637b0`; a HostSystem =
`1d6dae4e-…`; a cluster = `55b615f6-…`.

- **Our view → HTTP 200, `buckets:[]`** against world, host, AND cluster.
  So it is not a pin/scope problem — bound directly to the exact HostSystem it
  still returns zero buckets.
- **BUT the built-in, known-working product property-distributions also return
  `buckets:[]` via this endpoint** — "ESXi Distribution by Versions"
  (`524d0468`), "ESXi CPU Models" (`38896046`), "Configuration | Complex | ESXi
  Version (colorized)" (`98d46792`, used in shipped Skyline Operational
  Overview) all return `buckets:[]` against world/host/cluster.
- Meanwhile **numeric distributions populate fine** via the same endpoint:
  "ESXi Distribution by Core Counts" (`45281acb`), "ESXi Distribution by CPU
  GHz" (`e2d1f3c7`), "Datastore Configured Size Distribution" (`d9850e1a`) all
  return non-empty `buckets:[{key,label,min,max,value}…]`.

**Conclusion:** `/internal/views/{id}/data/export` only computes buckets for
**numeric-range** distributions; it does **not** compute DISCRETE
string/property buckets for *any* view (product or ours). So its empty result
is **not diagnostic** of our defect and must **not** be used to validate the
fix. The real widget data path is the ExtJS/report render layer (see Q4), which
this agent cannot exercise headless. The diagnosis rests on the static XML diff
against the known-working vendor + built-in definitions, which is unambiguous.

## Q2 — working comparison (built-in string-property distributions)

Enumerated 984 view entries via Ext.Direct
`viewServiceController.getGroupedViewDefinitionThumbnails`. The built-in
property distributions that work in shipped product dashboards use the same
`distribution-view` DataProvider + `bar-chart` Presentation as ours, and (per
the vendor corpus, which is byte-identical in shape) the same
isProperty=true / isStringAttribute=true / DISCRETE-dynamic-buckets encoding.
The renderer's numeric-histogram buckets (`render.py` `_xml_buckets_control`,
non-dynamic branch, and the unconditional `rollUpType=AVG`/`rollUpCount=1` in
`_xml_attribute_item`, ~lines 553-564) is the structural deficiency.

## Q3 — prod carries the same UUID and also returns empty via /internal

Prod render of `8a6d966f` → HTTP 200 `buckets:[]` against both prod world
(`da967cb5-…`) and a prod HostSystem (`0ba0f83d-…`). Because the internal
export endpoint cannot compute DISCRETE buckets for anyone (Q1), this tells us
nothing about which definition prod holds — it is the endpoint limitation, not
evidence. `GET /internal/views/{id}` (definition fetch) is 404 (no such
endpoint) and the Ext.Direct `getViewDefinition*` method names all return
"Internal server error" (wrong signature). The authoritative known-working
definition is therefore taken from the vendor source XML in
`reference/references/…/content/reports/ESXi Host Versions vCommunity.xml`
(and the three siblings), which is the pak the vendor ships and runs.

## Q4 — "Metrics displaying 0 of 23"

Not reproducible headless (no browser network trace; the internal export
endpoint doesn't drive the widget). Reasoned from the widget config + view def:
with `isProperty=false` the widget treats `summary|version` as a **metric** and
asks the metric subsystem for a numeric metric with `rollUpType=AVG` over the
selected resources. No such metric exists (version is a **property**), so 0 of
the ~23 candidate metric series resolve → the "0 of 23" info dialog and an
empty chart. The list-view widget renders version fine because a list column
reads the property store directly and does not require metric resolution — and
the version property IS collected (the list shows it for all 9 hosts).

---

## The smallest fix — view YAML (view-author), not renderer, not pin target

The prime lever is the **view YAML**. Add three fields to each of the four
affected distribution views under
`content/sdk-adapters/vcommunity-vsphere/views/`:

```yaml
data_type: distribution
columns:
- attribute: summary|version      # (per-view attribute)
  display_name: ESXi Version
  is_property: true               # ADD
  is_string_attribute: true       # ADD
buckets:                          # ADD
  dynamic: true
  calc_function: DISCRETE
```

Verified locally: `load_view` + `render_view_def_fragments` on the corrected
YAML emits `isStringAttribute=true`, `isProperty=true`, and a
`buckets-control` with `isDynamic=true` + `dynamicCalcFunction=DISCRETE` — the
three semantically-fatal fields fixed. (Loader keys: `is_property`,
`is_string_attribute` per column; view-level `buckets: {dynamic, calc_function}`
→ `BucketsConfig(is_dynamic, calc_function)`.)

**Residual (non-fatal) delta the YAML fix leaves behind**, and whether tooling
should also address it:
- `_xml_attribute_item` (`render.py` ~553-564) unconditionally emits
  `rollUpType=AVG`, `rollUpCount=1`, and a `transformations=[CURRENT]` block
  even for `isProperty=true` columns; the vendor omits `rollUpType`/
  `transformations` and sets `rollUpCount=0` for property columns. These extras
  are **empirically harmless** — our shipped, working list views carry the same
  extras on their property columns and render correctly — so they are **not**
  required for the data to appear. A renderer cleanup to match the vendor
  byte-for-byte (drop `rollUpType`/`transformations`, `rollUpCount=0` when
  `is_property and data_type==distribution`) is an **optional de-risking /
  fidelity** improvement (tooling), not the fix.
- The dynamic buckets branch omits `isSum=false`; vendor emits it. Defaulted,
  cosmetic. Optional.

**Fix ownership decision:**
1. **PRIMARY — view-author (content YAML):** set `is_property: true`,
   `is_string_attribute: true`, and `buckets: {dynamic: true, calc_function:
   DISCRETE}` on the four ESXi distribution views. This alone makes data appear.
2. **NOT the pin target / content design:** the pin (vSphere World +
   selfProvider) is fine; the widget renders zero regardless of the resource
   bound (proven against world, host, cluster).
3. **OPTIONAL — tooling (renderer):** match vendor property-column shape
   (suppress `rollUpType`/`transformations`, `rollUpCount=0`, emit `isSum`),
   and consider a validation WARNING when `data_type: distribution` has no
   `buckets:` block and/or a property-looking attribute with `is_property:
   false` — this class of view silently produces a data-less numeric histogram
   today, a footgun worth catching at validate time.
4. **Converter follow-up:** whatever produced these SDK-adapter view YAMLs from
   the vendor XML dropped the `isProperty`/`isStringAttribute`/discrete-buckets
   facts. If that converter is reused, it should preserve them (tooling).

After the YAML fix: rebuild the pak (content-packager) and confirm the four
widgets populate with a **qa-tester / Playwright browser pass** — the only path
that exercises the real distribution data layer, since the internal export
endpoint cannot (Q1).

## Cross-references
- `knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md` —
  the (separate, already-fixed) pin/binding issue; its hypothesis 3 noted
  distribution "No data" was a *different* root cause — this file is that root
  cause.
- `knowledge/context/api-surface/view_render_internal_endpoint.md` — the
  internal view render endpoint (now known to skip DISCRETE buckets).

## Addendum (2026-07-13, content-installer build-12 verification)

`GET /suite-api/internal/viewdefinitions/{id}` and `GET /suite-api/internal/viewdefinitions`
(bare list; `ids=` filter non-functional — always returns the full list, 787 entries on devel)
return 200 with thumbnail-shape ViewDef JSON: `name`, `type`, `presentationType`,
`subjects`, `active`, `owner`, `id`. Useful for existence / rename / active-flag
checks on pak-installed views (which `/api/content/operations/export` type
`VIEW_DEFINITIONS` does NOT return — that channel only exports UI-authored
"custom" views). Does NOT expose attribute items or buckets-control detail —
the attribute-level verification gap documented above still stands; browser
render remains the only proof of distribution-view internals.
