# SymptomDefinition dynamic-threshold condition: content-import XML vs REST JSON

**Date:** 2026-10-28
**Investigator:** api-explorer
**Instances:** devel_8_18 (8.18.7), devel_9_1 (9.1.1). Read-only: SSH log and
file reads, REST token acquire + GET. Nothing created, nothing to clean up.
**Trigger:** Synology SDK pak `0.0.0.35` bundles 11 symptoms and 7 alerts; 10
and 6 land on both instances. Missing: `[VCF Content Factory] Synology Disk
Uncorrectable Sectors Increasing` (the only `metric_dynamic` symptom) and
`[VCF Content Factory] Synology Disk Failing` (the alert that references it).
Review W2 in `knowledge/context/reviews/synology-build-35.md` flagged the
unproven shape before the install.

## TL;DR

Content-import XML and REST JSON spell a dynamic-threshold (DT) condition
differently. The factory renderer used the REST spelling in XML and the import
rejected it.

| Path | Condition type | Operators |
|---|---|---|
| Content-import XML (pak `content/symptomdefs/`, `content/alertdefs/`, describe.xml) | `type="dtmetric"` (`dtsuper` for super metrics) | `above`, `below`, `abnormal` (lowercase, no prefix) |
| REST JSON / XML (`/api/symptomdefinitions`) | `"type": "CONDITION_DT"` (`CONDITION_DT_SUPER`) | `DT_ABOVE`, `DT_BELOW`, `DT_ABNORMAL` |

Correct content-import XML:

```xml
<Condition key="Health|unc_sectors" operator="above" type="dtmetric" instanced="false"/>
```

No `thresholdType`, no `value`, no `valueType`. Every vendor DT example omits
all three. A single-symptom DT is fully expressible in content import.

## 1. Why the import dropped it (server log)

The pak shipped:

```xml
<Condition key="Health|unc_sectors" operator="DT_ABOVE" type="metric" instanced="false" />
```

devel_9_1, `/storage/log/vcops/log/analytics-<node-uuid>.log`, install task at
07:14Z (02:14 CDT):

```
2026-10-28T07:14:42.538Z ERROR analytics ... SymptomDefinitionRetriever.importSymptomDefinitions
  - Cannot import Symptom Definitions: Invalid operator:dt_above
java.lang.RuntimeException: Invalid operator:dt_above
  at ...persistence.metadata.DescribeConversionUtil.convertOperator(DescribeConversionUtil.java:2416)
  at ...DescribeConversionUtil.convertSymptomConditionDescribe(DescribeConversionUtil.java:2749)
  at ...DescribeConversionUtil.convertSymptomStateDescribe(DescribeConversionUtil.java:2225)
  at ...DescribeConversionUtil.convertSymptomDefinitionDescribes(DescribeConversionUtil.java:2113)
  at ...SymptomDefinitionRetriever.importSymptomDefinitions(SymptomDefinitionRetriever.java:656)
  ...
  at ...SolutionManagerDistributedTask.installSymptomDefsContent(SolutionManagerDistributedTask.java:1171)
```

The parser lowercases the operator and runs it through the same
`DescribeConversionUtil` that converts describe.xml symptoms, so the operator
vocabulary is the describe.xml one (below). `type="metric"` sends it down the
static-threshold branch, where `dt_above` is not an operator.

The alert failed as a dependency cascade. Same log, earlier, when the
`alertdefs/` file was processed:

```
2026-10-28T07:14:38.865Z ERROR ... UserDataService.getSymptomRelationships - Could not retrieve all the requested symptom relationships.
Requested: [SymptomRelationship-SymptomDefinition-synology_diskstation-VCF_Content_Factory_Synology_Disk_Uncorrectable_Sectors_Increasing,
            SymptomRelationship-SymptomDefinition-synology_diskstation-VCF_Content_Factory_Synology_Disk_SMART_Failing]
Retrieved: []
2026-10-28T07:14:38.866Z ERROR ... createOrUpdateAlertDefinition - Cannot create alert definition AlertDefinition-synology_diskstation-VCF_Content_Factory_Synology_Disk_Failing because dependent symptoms [...]
2026-10-28T07:14:38.868Z ERROR ... AlertDefinitionServiceImpl.importAlertDefinitionsOnly - The following Alert Definition(s) [AlertDefinition-synology_diskstation-VCF_Content_Factory_Synology_Disk_Failing] are invalid and won't be imported.
```

The audit log (`analytics.audit-<node-uuid>.log`) records both:
`SYMPTOM_DEFINITION.IMPORT result="failure" ... reason="Cannot import Symptom
Definitions: Invalid operator:dt_above"` (07:14:38.802Z, the alertdefs file;
07:14:42.538Z, the symptomdefs file) and `ALERT_DEFINITION.IMPORT
result="failure" ... reason="Skipping import for invalid content"`.

**The symptom batch in one file is all-or-nothing.** The alertdefs file embeds
both `SMART_Failing` and `Uncorrectable_Sectors_Increasing`; its symptom import
logged `ID(s): []`, so `SMART_Failing` was not created from that file either.
`SMART_Failing` exists today only because it also ships in its own
`symptomdefs/` file, imported at 07:14:42.150Z, after the alert had already
been rejected. One bad condition in an alertdefs file takes down every symptom
in that file and every alert that references any of them.

devel_8_18 shows the same error, install at 06:35Z (01:35 CDT):
`/storage/log/vcops/log/vcops-bridge.log` lines 4478, 4484 and
`analytics.audit-<node-uuid>.log` lines 89352, 89368:
`Cannot import Symptom Definitions: Invalid operator:dt_above`.

The pak manager log (`pakManager/vcopsPakManager.root.post_apply_adapter.log`)
shows only the file list and the `/internal/solution/install` call. Content
import errors are in the analytics, audit, and bridge logs, not the pak
manager logs.

REST after install, both instances:
`GET /api/symptomdefinitions?adapterKind=synology_diskstation` returns 10, no
`Uncorrectable Sectors Increasing`.

## 2. The correct encoding (vendor evidence)

### Vendor schema

`reference/references/vmware-vcf-operations-integration-sdk/vmware_aria_operations_integration_sdk/adapter_configurations/alertDefinitionSchema.xsd`,
`ConditionType` (lines 442-560):

- `type` enum: `metric`, `htmetric` (deprecated), `dtmetric`, `htsuper`
  (deprecated), `dtsuper`, `fault`, `property`, `msg_event`, `metric_event`,
  `smart`. "`dtmetric` - based on Metric Dynamic Threshold".
- `operator`: "For dtmetric and dtsuper: `above`, `below`, `abnormal`". The
  enum has no `DT_*` value.
- `instanced` applies to `dtmetric` and `dtsuper`.
- `thresholdType` (`static`/`metric`/`property`) is the hard-threshold
  right-hand side; it does not apply to DT.

`knowledge/context/mpb/mpb_describe_xsd_canonical.md` §Condition types already
listed `dtmetric` and `above`/`below`/`abnormal` for describe.xml. Content
import uses the same vocabulary.

### Vendor content-import file (same path shape as a factory pak)

devel_9_1, `/usr/lib/vmware-vcops/user/plugins/inbound/VMSP/content/alertdefs/alertdefs.xml`
line 355:

```xml
<SymptomDefinition adapterKind="VMSP" cancelCycle="3" disableInBasePolicy="true"
    id="SymptomDefinition-82f00df9-3955-48df-b162-89c661d0b1c3" nameKey="22120"
    resourceKind="ops-logs" waitCycle="3">
    <State severity="critical">
        <Condition key="ingestion|ops-logs-avg-write-response-time" operator="above" type="dtmetric"/>
    </State>
</SymptomDefinition>
```

The same definition over REST on devel_9_1
(`GET /api/symptomdefinitions?id=SymptomDefinition-82f00df9-3955-48df-b162-89c661d0b1c3`):

```json
"state": {
  "severity": "CRITICAL",
  "condition": {
    "type": "CONDITION_DT",
    "key": "ingestion|ops-logs-avg-write-response-time",
    "operator": "DT_ABOVE",
    "instanced": false
  }
}
```

So XML `type="dtmetric" operator="above"` imports as REST `CONDITION_DT` /
`DT_ABOVE`. `instanced` is absent in the XML and comes back `false`.

### Vendor describe.xml

devel_9_1, `/usr/lib/vmware-vcops/user/plugins/inbound/vmwarevi_adapter3/conf/describe.xml`:

| Line | Symptom id | Condition |
|---|---|---|
| 7858 | `PortLinkStateDown` | `key="network\|port_statistics\|link_state" instanced="true" operator="below" type="dtmetric"` |
| 8438 | `DatastoreSpaceUsageAboveDT` | `key="capacity\|usedSpacePct" operator="above" type="dtmetric"` |
| 8448 | `HostNetRxDroppedDTAbove` | `key="net\|droppedRx_summation" operator="above" type="dtmetric"` |
| 8453 | `HostNetTxDroppedDTAbove` | `key="net\|droppedTx_summation" operator="above" type="dtmetric"` |

`instanced="true"` is legal on `dtmetric` (line 7858).

### Reference corpus (policy exports)

The earlier "no vendor DT example" notes grepped for `DT_` and missed these.
Policy exports embed symptom definitions in the same XML grammar:

- `reference/references/AriaOperationsContent/vropstopdashboard/SampleDefaultPolicy.xml`
  lines 2538, 2663, 2813, 2878, 2913, 3003, 3363, for example line 2538
  `<Condition key="net|received|workload" operator="above" type="dtmetric"/>`.
- `reference/references/hol-2501-lab-files/HOL-2501-11/Module 5/autoscale-policy.xml`
  line 3112
  `<Condition instanced="true" key="network|port_statistics|link_state" operator="below" type="dtmetric"/>`.

No reference pak ships a DT symptom in `content/symptomdefs/` or
`content/alertdefs/`; the VMSP file above is the content-import proof. Under
`/usr/lib/vmware-vcops/user/plugins/inbound` on devel_9_1, the VMSP alertdefs
file and the vSphere describe.xml are the only DT hits.

`abnormal` is in the XSD but no vendor file uses it. Treat it as
schema-valid, not observed.

## 3. What the renderer must emit

`src/vcfcf_core/alerts/render.py::_add_condition_element`, `metric_dynamic`
branch. Today:

```python
attribs["operator"] = f"DT_{direction}"
attribs["type"] = "metric"
```

Must be:

```python
attribs["key"] = key
attribs["operator"] = direction.lower()   # ABOVE/BELOW/ABNORMAL -> above/below/abnormal
attribs["type"] = "dtmetric"
attribs["instanced"] = instanced
# no thresholdType, value, or valueType
```

The REST path (`src/vcfcf_core/symptoms/loader.py`, `CONDITION_DT` with
`DT_<direction>`) is correct and unchanged. A DT on a super metric would be
`type="dtsuper"` in XML and `CONDITION_DT_SUPER` in REST; the factory has no
YAML for it today.

The docstring note "No vendor XML example with a DT condition was found"
is wrong and should point here instead. A validator check that `metric_dynamic` renders
`dtmetric` would have caught this before a pak build; the platform drops the
symptom silently at install (the pak install reports success).
