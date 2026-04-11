# Adapter describe.xml vs Suite API comparison

Captured 2026-04-10. Source: describe.xml files from VCF Ops 9.0.2
appliance (`/usr/lib/vmware-vcops/user/plugins/inbound/*/conf/describe.xml`)
compared against Suite API endpoints documented in
`context/adapter_describe_exploration.md`.

## TL;DR

The API is a **superset** of describe.xml. Every metric/property in
describe.xml appears in the API (zero XML-only keys found for VMWARE
adapter). The API adds server-generated metric categories that do not
exist in the XML. The API also transforms field names, values, and
the key structure. For metric key validation, **the API is the
authoritative source** — describe.xml is an incomplete subset.

## Key structural difference: metric key composition

In describe.xml, metric keys are **bare names** nested under
`<ResourceGroup>` elements. The API **composites** the group path
and the attribute key with `|` as separator.

```
XML:  <ResourceGroup key="cpu">
        <ResourceAttribute key="usage_average" ... />
      </ResourceGroup>

API:  { "key": "cpu|usage_average", ... }
```

Nested groups produce multi-level keys:
```
XML:  <ResourceGroup key="cost">
        <ResourceGroup key="allocation">
          <ResourceAttribute key="allocationBasedTotalCost" />
        </ResourceGroup>
      </ResourceGroup>

API:  { "key": "cost|allocation|allocationBasedTotalCost" }
```

Top-level attributes (outside any ResourceGroup) have no prefix.

## Metric/property count comparison (VMWARE adapter)

describe.xml contains only adapter-declared attributes. The API
includes those **plus** server-generated categories injected at
runtime by the analytics engine, capacity engine, badge system,
and super metric assignments.

| Resource Kind            | XML stats | API stats | XML props | API props |
|---|---|---|---|---|
| VirtualMachine           | 426 | 930 | 247 | 251 |
| HostSystem               | 403 | 813 | 198 | 202 |
| ClusterComputeResource   | 263 | 897 | 61 | 75 |
| Datastore                | 106 | 362 | 44 | 51 |

All XML keys are present in the API (zero XML-only keys). The
difference is entirely API-only additions.

### VcfAdapter

| Resource Kind | XML stats | API stats | XML props | API props |
|---|---|---|---|---|
| VCFWorld      | 77 | 159 | 0 | 3 |
| VCFDomain     | 38 | 85 | 8 | 11 |

Same pattern: XML is a proper subset of API.

## Categories of API-only metrics

The server injects these categories beyond what describe.xml declares.
Counts are for VirtualMachine; the pattern repeats across all resource
kinds.

| Category | Count | Description |
|---|---|---|
| Capacity analytics (`actual.capacity`, `capacityRemaining`, `consumer.*`, `demand_whatif`, etc.) | ~51 per resource group | Per-resource-group capacity metrics. Groups: `cpu`, `mem`, `mem-host`, `diskspace`, `diskspace-total`, `cpu-alloc`, `mem-alloc`, `diskspace-alloc`. |
| `summary\|*` | 30 | Cross-group capacity summaries (`capacityRemaining*`, `timeRemaining*`, `provider.count`, `consumer.count`). |
| `badge\|*` | 26 | Health/risk/efficiency/capacity badge scores (`alert_count_*`, `anomaly`, `compliance`, `efficiency`, `health`, `risk`, `workload`, etc.). |
| `System Attributes\|*` | 22 | Internal bookkeeping (`active_alarms`, `alert_count_*`, `all_metrics`, `availability`, `new_ki_alarms`, etc.). |
| `OnlineCapacityAnalytics\|*` | 15 | Online capacity analytics (`capacityRemaining`, `recommendedSize`, `timeRemaining` per resource group). |
| `Super Metric\|sm_<uuid>` | varies | Super metrics assigned to this resource kind. Instance-specific; count depends on what's been assigned. |
| `System Properties\|*` | 4-14 | Server-generated properties (`DT`, `custom_tag_*`, `object_type`). Count varies by resource kind. |

## Resource kind count comparison (all adapters)

| Match? | Adapters |
|---|---|
| Exact match (20 of 23) | VMWARE, VcfAdapter, SupervisorAdapter, NSXTAdapter, VirtualAndPhysicalSANAdapter, VMWARE_INFRA_HEALTH, VMWARE_INFRA_MANAGEMENT, VCFAutomation, vCenter Operations Adapter, OrchestratorAdapter, DiagnosticsAdapter, LogAssistAdapter, VCF_UNIFIED_CONFIG, ManagementPackBuilderAdapter, vRealizeOpsMgrAPI, VrAdapter, FederatedAdapter, APPLICATIONDISCOVERY, VCFOperationsvCommunity, tammpak |
| Minor mismatch (3) | Container (XML 27 / API 29), NETWORK_INSIGHT (XML 3 / API 4), APPOSUCP (XML 139 / API 135) |

Minor mismatches are likely from runtime resource kind registration
(the server can add RKs beyond what the describe.xml ships). The
API also includes 3 `FDR_*` adapter keys with no corresponding
describe.xml files (these are Forwarder/FDR adapters, likely
generated server-side).

## XML namespace caveat

Not all describe.xml files use the same XML namespace. The VMWARE,
VcfAdapter, SupervisorAdapter, NSXTAdapter, VMWARE_INFRA_HEALTH, and
several others use `xmlns="http://schemas.vmware.com/vcops/schema"`.
Container, vCenter Operations Adapter, VirtualAndPhysicalSANAdapter,
APPOSUCP, FederatedAdapter, and others use **no namespace**. Any XML
parser must handle both.

## Field mapping: describe.xml ResourceAttribute -> API stat-key

| XML field | API field | Transform |
|---|---|---|
| `key` | `key` | Prefixed with `group\|` path from parent ResourceGroup elements |
| `nameKey` (int) | `name` (string) | Server resolves nameKey to localized display name |
| (none) | `description` | Server provides; XML has no description element |
| `dataType` | `dataType2` | XML: `float`/`integer`/`string`/`boolean`/`long` (lowercase). API: `FLOAT`/`INTEGER`/`STRING` (uppercase; no boolean/long — mapped to STRING/INTEGER) |
| (none) | `dataType` (legacy) | API includes only when non-FLOAT; absent for FLOAT metrics |
| `defaultMonitored` | `defaultMonitored` | XML: string `"true"`/`"false"`. API: JSON boolean |
| `rollupType` | `rollupType` | XML: `latest`/`max`/`min`/`sum` (lowercase); absent = AVG. API: `AVG`/`LATEST`/`MAX`/`MIN`/`SUM` (uppercase; always present) |
| `unit` | `unit` | Normalized to display-friendly abbreviations (see table below) |
| `isProperty` | `property` | XML: string. API: JSON boolean |
| `isDiscrete` | (not in API) | |
| `isRate` | (not in API) | |
| `dashboardOrder` | (not in API) | |
| `collectInstances` | (not in API) | |
| `favoriteGroups` | (not in API) | |
| `hidden` | (not in API) | |
| `keyAttribute` | (not in API) | |
| `maxVal`/`minVal` | (not in API) | |
| (none) | `instanceType` | Always `INSTANCED` in API |
| (none) | `monitoring` | Always `false` in API |

## Unit normalization (XML -> API)

| XML value | API value | Count (VM) |
|---|---|---|
| `percent` | `%` | 66 |
| `currency` | `US$` | 39 |
| `msec` | `ms` | 38 |
| `kb` | `KB` | 38 |
| `kbps` | `KBps` | 20 |
| `gb` | `GB` | 10 |
| `Mhz` / `mhz` | `MHz` | 9 |
| `sec` | `Second(s)` | 3 |
| `currencyMonth` | `US$/Month` | 3 |
| `min` | `Minute(s)` | 3 |
| `mb` | `MB` | 3 |
| `hr` | `Hour(s)` | 2 |
| `wh` | `Wh` | 2 |
| `KBps` | `KBps` | 19 (unchanged) |
| `GB` | `GB` | 16 (unchanged) |
| `KB` | `KB` | 9 (unchanged) |
| `MB` | `MB` | 3 (unchanged) |
| `bytes` | `bytes` | 3 (unchanged) |
| `GHz` | `GHz` | 1 (unchanged) |
| (absent) | `OIOs` / `vCPUs` / `IOPS` | 7 (API adds unit for capacity metrics with no XML unit) |

## Implications for metric key validation

1. **Use the API, not describe.xml, as the validation source.**
   describe.xml is missing ~50-70% of available statkeys (capacity,
   badges, system attributes, super metrics). Any metric key
   validator that checks only describe.xml will reject valid keys.

2. **describe.xml is still useful for understanding adapter-native
   metrics** — the keys that are guaranteed to exist before any
   analytics or capacity processing runs. For new-instance
   bootstrapping (before capacity analytics has populated data),
   only describe.xml keys will have data.

3. **Super Metric keys are instance-specific.** `Super Metric|sm_<uuid>`
   entries in the API reflect the current super metric assignments on
   that instance. These won't exist on a fresh instance or an instance
   with different SM assignments. Never validate SM keys against the
   statkeys API — use the super metrics API instead.

4. **The `hidden` attribute in describe.xml has no API equivalent.**
   Some metrics are marked `hidden="true"` in XML but appear in the
   API with no distinguishing flag. These metrics exist but are not
   shown in the default UI metric picker.

5. **Unit strings differ between XML and API.** Code that compares
   units must normalize. The API representation is the user-facing
   form.
