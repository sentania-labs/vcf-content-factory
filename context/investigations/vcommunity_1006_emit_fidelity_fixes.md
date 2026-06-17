# vCommunity 1.0.0.6 Live Install — Emit Fidelity Bug Analysis

**Date:** 2026-06-17
**Pak under investigation:** `vcfcf_sdk_vcommunity.1.0.0.6.pak`
**Symptom appliance:** vcf-lab-operations-devel
**Result:** 95/96 views + 12 dashboards imported; symptoms and 2 new SMs failed

---

## Bug 1 — Symptom operator value rejected (BLOCKING)

### Live error
`Cannot import Symptom Definitions: Invalid operator:not_eq`

### Root cause
`vcfops_alerts/render.py` `_add_condition_element()` passed the YAML/API-style
operator name (`NOT_EQ`) directly as the XML attribute value.  The VCF Ops
content importer expects symbolic operators, not API enum names.

### Reference ground truth
Both symptomdefs in
`references/vmbro_vcf_operations_vcommunity/Management Pack/content/symptomdefs/`:
```xml
<Condition ... operator="!=" ... value="Running" valueType="string"/>
```
Alertdefs in the same pack use `&lt;` (decoded: `<`) for LT and `&gt;=`
(decoded: `>=`) for GT_EQ.

### Full operator mapping (YAML name → XML symbol)
| YAML / API name | XML symbol |
|-----------------|------------|
| EQ              | ==         |
| NOT_EQ          | !=         |
| GT              | >          |
| GT_EQ           | >=         |
| LT              | <          |
| LT_EQ           | <=         |
| CONTAINS        | contains   |
| NOT_CONTAINS    | notContains |
| STARTS_WITH     | startsWith |
| NOT_STARTS_WITH | notStartsWith |
| ENDS_WITH       | endsWith   |
| NOT_ENDS_WITH   | notEndsWith |
| REGEX           | regex      |
| NOT_REGEX       | notRegex   |

ElementTree serializes `<` and `>=` as `&lt;` / `&gt;=` automatically.

### Fix
Added `_XML_OPERATOR_MAP` dict and `_xml_operator()` helper in
`vcfops_alerts/render.py`.  Both `metric_static` and `property` condition
branches now call `_xml_operator(operator)` before setting the XML attribute.
Dynamic (`DT_ABOVE/DT_BELOW/DT_ABNORMAL`) operators pass through unchanged —
they are not in the YAML map and the DT_ prefix is generated internally.

---

## Bug 2 — SM JSON missing modificationTime (BLOCKING for new SMs)

### Live errors
- `SuperMetricImportParam.readUUID: Invalid UUID string`
- `readLong: For input string: ""`
- 2 new SMs (`Total Non-default Settings`, `vSphere VM Performance`) failed to CREATE

### Root cause
`vcfops_managementpacks/sdk_builder.py` SM emit omitted `modificationTime`
and `modifiedBy`.  The importer deserializes SM JSON by calling `readLong()`
on `modificationTime`; when the field is absent the deserializer gets the
zero-value empty string and throws.

Existing SMs update by name (not CREATE) and are unaffected.  Only SMs that
do not exist on the target instance hit the CREATE path and fail.

### Reference ground truth
`references/vmbro_vcf_operations_vcommunity/Management Pack/content/supermetrics/Total Non-default Settings.json`:
```json
{"f30f298c-385f-4ef8-b511-4092a348a346": {
   "resourceKinds": [...],
   "modificationTime": 1753166113814,
   "name": "Total Non-default Settings",
   "formula": "...",
   "description": "...",
   "unitId": "",
   "modifiedBy": "8a399472-453b-435f-b57d-84aa33550d08"
}}
```

### Fix
Changed SM payload emit in `sdk_builder.py` (lines ~1617-1624) to include:
- `"modificationTime": 0` — valid long integer; epoch zero is accepted by the platform
- `"modifiedBy": ""` — empty string; server assigns the real value on CREATE
- Field order now matches reference: `resourceKinds`, `modificationTime`, `name`,
  `formula`, `description`, `unitId`, `modifiedBy`

---

## Bug 3 — One view short (95 of 96) — Source-content edge case

### Live behavior
96 view XMLs present in pak; `VIEW_DEFINITION_IMPORT` fired 95×.

### Root cause
The 96th view `Guest OS List of Services`
(`content/sdk-adapters/vcommunity/views/Guest OS List of Services.yaml`)
has `adapter_kind: APPLICATIONDISCOVERY` — the optional "Service Discovery"
adapter.  When that adapter is not installed on the target instance the VCF Ops
content importer silently skips views targeting unavailable adapters.

The view itself renders correctly and the pak carries all 96 view XMLs.
This is **not a format bug** — it is expected platform behavior for optional
adapter dependencies.

### Resolution
No code change.  The view's description already notes:
> "Note: this requires Service Discovery adapter."

The 95/96 import result on instances without Service Discovery is correct
and expected.

---

## Test coverage
`tests/test_emit_fidelity_bugs.py` — 16 new tests:
- `TestSymptomOperatorTranslation` (8 tests): NOT_EQ→`!=`, EQ→`==`, GT→`>`,
  GT_EQ→`>=`, LT→`<`, LT_EQ→`<=`, verbatim reference check, well-formed XML.
- `TestSMJsonIncludesModificationTime` (6 tests): field present, is integer,
  modifiedBy present, JSON round-trips, field order, end-to-end pak check.
- `TestViewCountAndEdgeCase` (2 tests): all 96 views render without error,
  APPLICATIONDISCOVERY view is well-formed.
