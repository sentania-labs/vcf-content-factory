# vSphere Storage Paths MP — v2 Stitching Plan

Status: **COMPLETE.** v2.0.0.5 installed on prod (2026-05-14).
MOID collision fixed (hostname→VMEntityName). Adapter kind aligned
to MPB convention. Events stripped from pak (runtime format unknown).

Previous status: ARIA_OPS stitching tooling landed, YAML authored,
MOID collision discovered. Blocked on join key decision.

## Current state (2026-05-13 session 2)

### What's built and validated
- MP YAML: `content/managementpacks/vsphere_storage_paths.yaml` (v2.0.0)
- .pak: `dist/mpb_vsphere_storage_paths.2.0.0.1.pak` (builds clean)
- Design JSON: `tmp/vsphere_storage_paths_design.json` (renders clean)
- Both objects use `type: ARIA_OPS` with `aria_ops:` block
- Full ARIA_OPS tooling support landed in loader, renderer, builder,
  render_export, render_template

### What's running on devel (user's v1.25, NOT the factory v2)
- Adapter kind: `mpb_vcf_content_factory_vsphere_storage_paths`
- Installed via MPB UI (design import → build → install)
- 5 of 7 metrics flowing onto VMWARE HostSystem objects
- Missing: Unknown Paths, Path Health % (not in user's MPB design)
- Properties do NOT stitch (platform limitation — metrics only)
- Adapter healthy, collecting every 5 min, ~4 cycles observed

### Ground truth references saved
- `context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json`
  — user's MPB UI export of the working ARIA_OPS stitch design
- `tmp/mpb_reference_none_auth.json` — minimal no-auth MPB export
- `tmp/mpb_exported_design.json` — v1 round-trip export
- `tmp/mpb_exported_v2.json` — v1.25 round-trip export with stitching

### Tooling landed this session

1. `builder.py`: empty CredentialKinds fix for `preset: none`
2. `render_export.py`: credentialType NONE→CUSTOM, content null→absent,
   stripped metrics[].key and other extra fields
3. `loader.py`: AriaOpsConf dataclass, ARIA_OPS validation rules
4. `render.py`: ARIA_OPS object rendering with ariaOpsConf,
   objectBindingType, UUID cross-reference to bind metric
5. `builder.py`: ARIA_OPS objects excluded from describe.xml ResourceKinds
6. `render_export.py`: ariaOpsConf preserved for ARIA_OPS objects
7. `render_template.py`: ARIA_OPS handling for template format

## BLOCKING ISSUE: MOID collision

### The problem
`host_moid` (VMEntityObjectID) is NOT globally unique across vCenters.
Both wld01 and wld02 have hosts with `host-20` and `host-18`. The
current binding (`stitch_match_field: host_moid` → `bind_metric:
VMEntityObjectID`) causes:

- wld02 hosts silently lost (only 6 of 8 hosts appear)
- Cross-contamination: wld01-esx01 shows 6.0 active paths (should be
  5.0) — it's getting wld02-esx02's data (which has 6.0)

### Join key options

| Option | Our field | HostSystem field | Unique? | Status |
|---|---|---|---|---|
| A. FQDN | `hostname` | `VMEntityName` | Yes (globally) | VMEntityName is `isPartOfUniqueness: false` — unknown if works as bind_metric |
| B. Composite MOID+VCID | `host_moid` + ??? | `VMEntityObjectID` + `VMEntityVCID` | Yes (composite PK) | API doesn't provide vCenter UUID; multi-key stitch support unknown |
| C. Composite MOID+vcenter_name | `host_moid` + `vcenter` | `VMEntityObjectID` + ??? | Maybe | No HostSystem property maps to our `vcenter` short name ("wld01") |

### Open question: multi-key stitch?
Can MPB's objectBinding match on TWO fields simultaneously? The
objectMatchExpression has `expressionParts[]` (an array) — maybe
multiple parts means composite matching? This needs investigation:

1. Check the Rubrik reference for multi-part expressionParts
2. Check the jcox UniFi reference — does any objectBinding use
   multiple expressionParts?
3. Try building a multi-key stitch in the MPB UI to see the wire format
4. If multi-key works: ask the API author to add `vcenter_uuid`
   (VMEntityVCID equivalent) to the host-path-summary response

### Recommended path
Option A (hostname → VMEntityName) is the simplest fix. Even though
VMEntityName is `isPartOfUniqueness: false`, it IS a resource
identifier on HostSystem objects and should be queryable for binding.
Test this first. Fall back to composite key only if VMEntityName
doesn't work as a bind target.

If multi-key IS possible, the cleanest solution is to have the API
add `vcenter_uuid` and bind on `(host_moid, vcenter_uuid)` →
`(VMEntityObjectID, VMEntityVCID)`. This matches the actual PK.

## ARIA_OPS stitching — confirmed wire format

From the ground-truth export, the correct structure is:

```json
{
  "object": {
    "type": "ARIA_OPS",
    "isListObject": true,
    "ariaOpsConf": {
      "objectType": "HostSystem",
      "objectTypeLabel": "Host System",
      "adapterType": "VMWARE",
      "adapterTypeLabel": "vCenter",
      "metricSet": {
        "id": "<uuid>",
        "metrics": [{
          "id": "<uuid-A>",
          "label": "VM Entity Object ID",
          "dataType": "STRING",
          "usage": "ARIA_OPS_REFERENCE_ID",
          "expression": {
            "expressionText": "",
            "expressionParts": [{
              "originType": "ARIA_OPS_METRIC",
              "originId": "VMEntityObjectID"
            }]
          }
        }]
      }
    },
    "metricSets": [{
      "objectBinding": {
        "objectBindingType": "ATTRIBUTE_TO_PROPERTY",
        "matchExpression": { "originType": "ATTRIBUTE", "label": "host_moid" },
        "objectMatchExpression": { "originType": "ARIA_OPS_METRIC", "originId": "<uuid-A>" }
      }
    }]
  }
}
```

Key: `objectMatchExpression.originId` is a UUID cross-referencing
`ariaOpsConf.metricSet.metrics[].id`, NOT the string-format
`aria-VMWARE-HostSystem-VMEntityObjectID`.

## Other findings

### Properties don't stitch
ARIA_OPS stitching delivers metrics only. Properties declared on
ARIA_OPS objects (`hostname`, `vcenter`, `host_moid`) are silently
dropped — `collected_properties = 0` confirmed. This is a platform
limitation. Consider removing properties from ARIA_OPS objects to
avoid confusion, or keep them for documentation/future use.

### Stat key namespace
Stitched metrics appear on HostSystem with the group prefix from the
MP display name: `VCF Content Factory vSphere Storage Paths|Dead Paths`.
The `VCF-CF|` label text in the YAML becomes the metric label in the
picker but the group/stat-key prefix is the MP name. This is how MPB
groups metrics from different adapters — any super metrics or symptoms
referencing these need to use the full stat key path.

### Metric label prefix
User chose `VCF-CF|` as the label prefix. The pipe `|` in VCF Ops
metric paths is the group separator. So `VCF-CF|Dead Paths` means
group `VCF-CF`, metric `Dead Paths`. This may interact with the
MP-name-based stat key grouping. Verify on devel whether the final
stat key is `VCF Content Factory vSphere Storage Paths|VCF-CF|Dead Paths`
or just `VCF-CF|Dead Paths`.

## Execution plan (next session)

1. **Investigate multi-key stitch** — check Rubrik/jcox references
   for multi-part objectBinding expressionParts. Try in MPB UI if
   needed.
2. **Decide join key** — hostname→VMEntityName (simple) vs
   composite (host_moid+vcenter_uuid)→(VMEntityObjectID+VMEntityVCID).
3. **Update YAML** with correct join key.
4. **Install factory v2 on devel** — either .pak or design import.
   Verify all 8 hosts get metrics (wld02 hosts no longer lost).
5. **Verify stat key format** — confirm the actual metric path on
   HostSystem so super metrics / symptoms can reference it.
6. **Author content** — views/dashboards/symptoms/alerts for the
   stitched storage path metrics on HostSystem objects.

## Files to read on resume

- This file
- `content/managementpacks/vsphere_storage_paths.yaml` (v2 YAML)
- `context/mpb_wire_reference/vsphere_storage_paths_aria_ops_stitch.json`
  (ground-truth MPB export)
- `context/mpb_object_binding_wire_format.md` (§3.5 stitching)
- `context/management_pack_authoring.md` (YAML grammar)
- `vcfops_managementpacks/loader.py` — AriaOpsConf, ARIA_OPS validation
- `vcfops_managementpacks/render.py` — _render_aria_ops_conf()
