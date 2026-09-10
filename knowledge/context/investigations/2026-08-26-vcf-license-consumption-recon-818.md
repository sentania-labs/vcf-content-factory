# VCF License Consumption Overview — recon (ro818 vs prod)

**Date:** 2026-08-26
**Task:** Rebuild Scott's community dashboard "VCF License Consumption
Overview" (sentania/AriaOperationsContent) as native factory content
targeting 8.x. Read-only recon against `ro818` (Aria Operations 8.18.7,
read-only user `vrops`) and `prod` (VCF Operations 9.1.0, read-only) as
comparison.

**Inputs:**
- `reference/references/AriaOperationsContent/VCF License Consumption Overview/supermetric.json`
  (12 super metrics)
- `.../VCF Consumption Overview v2/dashboard/dashboard.json` (1 dashboard,
  10 widgets)
- `.../Views/content.xml` (7 list/trend views)

All API calls GET-only. UI layer calls used `list_dashboards()` /
`list_views()` from `src/vcfops_dashboards/ui_client.py` (existing
read helpers, unsupported UI endpoints, no mutation).

## Extraction: raw metric/property keys and adapter/resource kinds

From the 12 super metric formulas (widgets and view columns reference
these SMs almost exclusively, not raw keys — 1 exception noted below):

| Adapter kind | Resource kind | Key | Type (per selector) |
|---|---|---|---|
| `VMWARE_INFRA_HEALTH` | `LicenseUsage` (formula `objecttype=`) | `Assets\|TotalUsage` | metric |
| `VMWARE_INFRA_HEALTH` | `LicenseUsage` | `CostUnitAttributes\|CostUnitLimit` | metric selector in formula, **actually a property on both instances** (see below) |
| `VMWARE_INFRA_HEALTH` | `LicenseUsage` | `ProductId` | property, used in `where="ProductId startsWith ..."` filter |
| `VMWARE` | `HostSystem` | `config\|name` | property (`count()` over attribute) |
| `VMWARE` | `HostSystem` | `cpu\|corecount_provisioned` | metric |
| `NSXTAdapter` | `TransportNode` | `summary\|NodeType` | metric selector in formula, **actually a property** |

Note: the SM's declared `resourceKinds` assignment block says
`LICENSE_USAGE_WORLD` (the world/rollup container resource kind), but
every formula's `${...}` selector targets **`objecttype=LicenseUsage`**
— a *different*, more granular resource kind that holds one resource
per license/product key. This is intentional in the source content
(SM assigned to the World, formula aggregates its `LicenseUsage`
descendants) — not a typo, but easy to get wrong when re-authoring:
statkey/property lookups must target `LicenseUsage`, not
`LICENSE_USAGE_WORLD`.

Two super metric formulas reference **external super metric UUIDs not
present in `supermetric.json`**: `sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322`
(used by "Automation License Count" and "NSX License Count") and
`sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6` (used by "VCF License
Potential Cores"). Neither ID resolves on either instance
(`GET /api/supermetrics/{id}` → 404 on both ro818 and prod). The
reference bundle is **incomplete** — it depends on a per-host core-count
super metric that isn't shipped in this file. `[VCF Consumption
Overview v2]VCF License Potential Cores` also has a resource-kind
mismatch worth flagging to the user: it's assigned to `vSphere World`
but its formula reads `${this, metric=cpu|corecount_provisioned}`,
a HostSystem-level metric that doesn't exist at World scope — looks
like a source-content bug, not something to reproduce as-is.

From dashboard.json widgets (raw keys used directly, not via SM):

| Adapter kind | Resource kind | Key | Type |
|---|---|---|---|
| `NSXTAdapter` | `NSXT World` | `Summary\|LogicalSwitchCount` | metric |
| `NSXTAdapter` | `NSXT World` | `Summary\|EdgeClusterCount` | metric |
| `CASAdapter` | `CAS World` | `summary\|VMCount` | metric |
| `CASAdapter` | `CAS World` | `summary\|Cost` | metric |
| `VMWARE` | `vSphere World` | `ObjectCountMetricGroup:HostSystem\|count` | metric (dynamic child-count instance) |
| `VMWARE` | `vSphere World` | `ObjectCountMetricGroup:VirtualMachine\|count` | metric (dynamic) |
| `VMWARE` | `vSphere World` | `ObjectCountMetricGroup:DistributedVirtualPortgroup\|count` | metric (dynamic) |

`content.xml` view columns are almost entirely `Super Metric|sm_<uuid>`
references to the 12 SMs above; the one raw-key exception is
`Summary|LogicalSwitchCount` in the "NSX Consumption Trend" view,
already captured above.

**Super metric names (12):**
`[VCF Consumption Overview v2] VCF Total License Usage`,
`Automation Host Count`, `vSAN Total License Usage`,
`Automation License Count`, `VCF Total License Usage Percent`,
`vSAN Total License Usage Percent` (two leading spaces after the
bracket in the source file — `[VCF Consumption Overview v2]  vSAN...`),
`Host Transport Node Core Count`, `Host Transport Node Count`,
`NSX License Count`, `VCF License Potential Cores` (no space after
bracket in source — `[VCF Consumption Overview v2]VCF License
Potential Cores`), `VCF Total License Count`, `vSAN Total License
Capacity`. All 12 names carry the source bundle's own naming
inconsistencies verbatim (spacing).

## ro818 (Aria Operations 8.18.7) — per-key table

Adapter kinds installed (34 total): includes `VMWARE`,
`VMWARE_INFRA_HEALTH`, `NSXTAdapter`, `CASAdapter`, `VcfAdapter`. No
adapter kind literally named `VCF` on either instance — the VCF-9-era
name for this is `VcfAdapter` ("VMware Cloud Foundation"), present on
**both** ro818 and prod. That specific 8.x/9.x split the task
anticipated didn't materialize for this adapter kind.

| Key | Defined | Populated | Unit | Sample |
|---|---|---|---|---|
| `VMWARE_INFRA_HEALTH/LicenseUsage` `Assets\|TotalUsage` | yes | **yes** (11 resources) | — | `[0.0]`–`[30.0]` across 11 license objects |
| `VMWARE_INFRA_HEALTH/LicenseUsage` `CostUnitAttributes\|CostUnitLimit` | yes (property) | **yes** | — | `2000.0` |
| `VMWARE_INFRA_HEALTH/LicenseUsage` `ProductId` | yes (property) | **yes** | — | `vSAN Enterprise`, `vSphere 8 Enterprise Plus for VCF`, `vSphere 8 Enterprise Plus`, `vCenter Server 8 Standard`, `vSphere 7 Enterprise Plus` |
| `VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD` (rollup, sanity check) | yes | yes (1 resource, "License Usage") | — | — |
| `VMWARE/HostSystem` `config\|name` | yes (property) | yes (42 hosts) | — | `host-1` |
| `VMWARE/HostSystem` `cpu\|corecount_provisioned` | yes | yes | Cores | `56.0` |
| `NSXTAdapter/TransportNode` `summary\|NodeType` | yes (property) | **NO_RESOURCE_FOUND** — 0 TransportNode objects in inventory | — | — |
| `NSXTAdapter/NSXT World` `Summary\|LogicalSwitchCount` | yes | yes (1 resource) | — | `0.0` |
| `NSXTAdapter/NSXT World` `Summary\|EdgeClusterCount` | yes | yes | — | `0.0` |
| `CASAdapter/CAS World` `summary\|VMCount` | yes | **NO_RESOURCE_FOUND** — 0 CASAdapter resources at all | — | — |
| `CASAdapter/CAS World` `summary\|Cost` | yes | **NO_RESOURCE_FOUND** | — | — |
| `VMWARE/vSphere World` `ObjectCountMetricGroup:HostSystem\|count` | not a static statkey entry (dynamic per-child-kind template, `ObjectCountMetricGroup\|count` is the generic entry in the catalog) | yes | — | `42.0` |
| `VMWARE/vSphere World` `ObjectCountMetricGroup:VirtualMachine\|count` | dynamic (as above) | yes | — | `722.0` |
| `VMWARE/vSphere World` `ObjectCountMetricGroup:DistributedVirtualPortgroup\|count` | dynamic (as above) | yes | — | `61.0` |

Super metrics: 292 total on instance; **0 of the 12** target names
found by exact match. External SM refs (`sm_5ea91f64...`,
`sm_3b4464fc...`) also 404.

Views/dashboard (UI layer, `getGroupedViewDefinitionThumbnails` +
`getDashboardList`, 2323 view entries / 267 dashboards visible to
`vrops`): **0 of the 7** target view names found by exact match, **0**
match for the dashboard name `VCF Consumption Overview v2`. One
loosely related pre-existing dashboard exists —
`Automation SDDC Resource Consumption Overview` — different content,
not a match.

## prod (VCF Operations 9.1.0) — per-key table

Adapter kinds installed (27 total, renamed labels vs ro818):
`VMWARE_INFRA_HEALTH` = "Infrastructure Health", `CASAdapter` = "VCF
Automation for VM Apps Organization" (0 resources — **superseded**),
`VCFAutomation` = "VCF Automation for All Apps Organization" (1
resource, resource kind `Automation World`, **not** `CAS World`),
`VcfAdapter` = "VMware Cloud Foundation" (present, same as ro818).

| Key | Defined | Populated | Unit | Sample |
|---|---|---|---|---|
| `VMWARE_INFRA_HEALTH/LicenseUsage` `Assets\|TotalUsage` | yes | **NO_RESOURCE_FOUND** — 0 LicenseUsage objects on this instance | — | — |
| `VMWARE_INFRA_HEALTH/LicenseUsage` `CostUnitAttributes\|CostUnitLimit` | yes (property) | **NO_RESOURCE_FOUND** | — | — |
| `VMWARE_INFRA_HEALTH/LicenseUsage` `ProductId` | yes (property) | **NO_RESOURCE_FOUND** | — | — |
| `VMWARE_INFRA_HEALTH/LICENSE_USAGE_WORLD` (rollup) | yes | **NO_RESOURCE_FOUND** — the World container itself has 0 instances here | — | — |
| `VMWARE/HostSystem` `config\|name` | yes | yes (44 hosts) | — | `host-1` |
| `VMWARE/HostSystem` `cpu\|corecount_provisioned` | yes | yes | Cores | `56.0` |
| `NSXTAdapter/TransportNode` `summary\|NodeType` | yes (property) | **NO_RESOURCE_FOUND** | — | — |
| `NSXTAdapter/NSXT World` `Summary\|LogicalSwitchCount` | yes | yes | — | `0.0` |
| `NSXTAdapter/NSXT World` `Summary\|EdgeClusterCount` | yes | yes | — | `0.0` |
| `CASAdapter/CAS World` `summary\|VMCount` | yes (statkey catalog entry still exists) | **NO_RESOURCE_FOUND** — adapter kind has 0 resources | — | — |
| `CASAdapter/CAS World` `summary\|Cost` | yes | **NO_RESOURCE_FOUND** | — | — |
| `VMWARE/vSphere World` `ObjectCountMetricGroup:*\|count` (3 keys) | dynamic (as ro818) | yes, all 3 | — | Host `44.0`, VM `837.0`, DVPG `63.0` |

Super metrics: only 6 total on this instance; **0 of the 12** target
names found. External SM refs also 404.

**VCF-9 replacement vocabulary gap (CASAdapter → VCFAutomation):**
`VCFAutomation/Automation World` is the live resource on prod, but it
does **not** carry `summary|VMCount` / `summary|Cost`. Its statkey
catalog (101 keys) has the renamed equivalents instead:
`summary|total_vms`, `summary|total_running_vms`, and
`Aggregate|VCFAOrganization|cost|aggregatedMtdTotalCost` for cost.
Confirmed live: `summary|VMCount`/`summary|Cost` return `{"values":
[]}` against the one Automation World resource; `summary|total_vms`
etc. were not further tested for population (out of the original key
set) but exist in the catalog. **This is a genuine key-rename gap**,
not a topology gap: if this dashboard is meant to work on VCF Ops 9
too, the Automation section needs the `VCFAutomation`/`Automation
World` vocabulary, not `CASAdapter`/`CAS World`.

Views/dashboard (UI layer, 1128 view entries / 190 dashboards visible):
**0 of 7** views found, **0** dashboard match.

## Policy enablement

Every "defined but unpopulated" key on both instances traces to **zero
resource instances of that resource kind** (`CASAdapter`: 0 resources
on both; `NSXTAdapter/TransportNode`: 0 on both; `VMWARE_INFRA_HEALTH/
LicenseUsage` and its `LICENSE_USAGE_WORLD` parent: 0 on prod). Policy
metric-collection toggles gate collection *on existing objects*; they
cannot explain zero object count. **Inferred, not exhaustively
verified**: `GET /api/policies/{id}/settings?type=...` (the closest
documented policy-inspection endpoint) only exposes pricing/capacity/
workload settings, not per-attribute KPI enable/disable — that lives
in the policy export XML (`/api/policies/export`, async, no per-key
filter). ro818 alone has 292 policies; an exhaustive per-key XML audit
across both instances was out of proportion to what the topology data
already explains. Marking as **API gap**: no lightweight endpoint
answers "is attribute X enabled in policy Y" directly; the mechanism
exists (policy export/import) but wasn't exercised here since it
wouldn't change the conclusion.

## Gap list (exception summary)

1. **No exact match anywhere** for the dashboard, any of its 7 views,
   or any of its 12 super metrics, on either instance, in repo YAML
   (`content/{supermetrics,views,dashboards}/` greps clean), or in any
   other allowlisted reference source (grepped for `Assets|TotalUsage`,
   `CostUnitLimit`, `LicenseUsage` — only the source bundle itself
   matches). **This is a from-scratch authoring job**, not reuse.
2. **Two dangling super metric dependencies** in the source bundle
   (`sm_5ea91f64...`, `sm_3b4464fc...`) — not shippable as-is; the
   per-host core-count SM they depend on must be reconstructed or the
   dependent formulas rewritten.
3. **`VCF License Potential Cores` has a resource-kind/formula
   mismatch** in the source content (assigned to `vSphere World`,
   formula reads a HostSystem-only metric) — don't reproduce verbatim.
4. **`ro818` has real per-product license consumption data**
   (`VMWARE_INFRA_HEALTH/LicenseUsage`, 11 objects, live
   `Assets|TotalUsage` + `ProductId` + `CostUnitAttributes|
   CostUnitLimit`) — the VCF/vSAN halves of the dashboard are
   buildable and testable there today.
5. **`ro818` has no CASAdapter or TransportNode data** (0 resources of
   either) — the Automation and "Host Transport Node" halves of the
   dashboard cannot be validated against live data on ro818.
6. **`prod` has no license consumption data at all**
   (`LicenseUsage`/`LICENSE_USAGE_WORLD` both 0 resources) — the
   VCF/vSAN halves aren't testable on prod, inverse of ro818.
7. **`prod`'s Automation adapter is `VCFAutomation`/`Automation
   World`, not `CASAdapter`/`CAS World`**, and does not carry
   `summary|VMCount`/`summary|Cost` — real vocabulary drift, not just
   a topology gap. Any 9.x-targeted version of this dashboard needs
   `summary|total_vms` / `Aggregate|VCFAOrganization|cost|
   aggregatedMtdTotalCost` instead. Task explicitly targets 8.x, so
   this is a heads-up for later, not a blocker now.
8. **`ObjectCountMetricGroup:{ChildKind}|count`** keys are dynamic
   per-child-kind instantiations of a generic template
   (`ObjectCountMetricGroup|count`) — they don't appear as literal
   entries in the static `/statkeys` catalog on either instance but
   are live and populated on both. Not a gap, just a vocabulary
   quirk worth noting for whoever authors the view/SM referencing
   them.
9. **Policy enablement**: not directly checked (API gap, see above);
   topology (0 resources) fully explains every unpopulated key on both
   instances without needing a policy answer.

## Recommendation

**Author**, targeting `ro818` first (8.x, per the task) where the
license-consumption data actually exists and is testable:
- The VCF/vSAN super metrics (6 of 12: Total Usage, Total Usage
  Percent, Total Count/Capacity for both VCF and vSAN) map cleanly to
  `VMWARE_INFRA_HEALTH/LicenseUsage` `Assets|TotalUsage` +
  `CostUnitAttributes|CostUnitLimit` + `ProductId` filter — all three
  confirmed defined and populated on ro818.
- The NSX pair (`Host Transport Node Count`/`Core Count`) needs
  `NSXTAdapter/TransportNode` `summary|NodeType`, which is defined but
  has **zero live TransportNode objects** on ro818 — will validate
  structurally but won't show non-zero data there. Flag to Scott
  before building: needs a lab with actual NSX transport nodes to
  prove out.
- The Automation pair (`Automation Host Count`/`License Count`) needs
  `CASAdapter/CAS World` `config|name`/`Super Metric` chaining, which
  is defined but has **zero CASAdapter resources** on ro818 (and is
  the wrong adapter kind entirely on prod, superseded by
  `VCFAutomation`). Same flag: no live Automation instance to validate
  against on either recon target.
- Drop or rebuild the two dangling external-SM dependencies
  (`sm_5ea91f64...`, `sm_3b4464fc...`) and fix the `VCF License
  Potential Cores` resource-kind mismatch rather than reproducing it.
- No existing content anywhere to reuse — this is bottom-up authoring
  (SM → view → dashboard) from the ground up, per
  `knowledge/designs/README.md` intent-capture convention.

## Follow-up recon (2026-08-26, second pass): host CPU topology, DSL ternary, world objects, ObjectCountMetricGroup

Read-only against `ro818` only (Aria Operations 8.18.7). All calls
GET-only via `VCFOpsClient.from_env(profile="ro818")`.

### 1. Host CPU topology: `hardware|cpuInfo|numCpuCores` / `numCpuPackages` (properties) and `cpu|corecount_provisioned` / `cpu|numpackages` (stats)

Both properties are **defined** (`GET
/api/adapterkinds/VMWARE/resourcekinds/HostSystem/properties`) and
both stat keys are **defined** (`.../HostSystem/statkeys`).

Populated check on three live hosts (identical values across all
three — same hardware SKU in this lab):

| Host | `numCpuCores` (prop) | `numCpuPackages` (prop) | `cpu\|corecount_provisioned` (stat) | `cpu\|numpackages` (stat) |
|---|---|---|---|---|
| host-1 (`044bb656-3992-4971-9298-11d6ad8ef1a2`) | 56.0 | 2.0 | 56.0 | **no data point returned** |
| host-2 (`0536a716-1a6e-4d2b-94ba-a8aababc6a1a`) | 56.0 | 2.0 | 56.0 | **no data point returned** |
| host-3 (`0bdcb5ed-9ba4-42ce-ae4c-adef767abf94`) | 56.0 | 2.0 | 56.0 | **no data point returned** |

Exception: `cpu|numpackages` is defined in the statkey catalog but
`GET /api/resources/{id}/stats/latest?statKey=cpu|numpackages`
returns `{"values": []}` on all three hosts, not collected on this
adapter/build. The **properties** path
(`hardware|cpuInfo|numCpuPackages`) is populated and is the reliable
source for socket count here, not the stat key.

Arithmetic check (cores per socket = numCpuCores / numCpuPackages):
56 / 2 = **28 cores/socket** on all three sample hosts, consistent
with `cpu|corecount_provisioned` (56) matching `numCpuCores` exactly
(both count total logical cores, not per-socket).

### 2. DSL ternary / conditional support, 8.18 build

Pulled all 292 super metrics (`GET /api/supermetrics?pageSize=500`)
and grepped formulas. **Ternary (`cond ? a : b`) is proven working
syntax on this build**: 36 of 292 formulas use it. No formula uses
literal `if(`. `max(` and `min(` are both in heavy use (44 and 45
formulas respectively) as aggregate functions over `${this, ...}`
operand arrays.

Two clean examples:

- `DA - VCF licenses needed` (directly relevant to this recon's
  subject matter):
  ```
  ${THIS, metric=hardware|cpuInfo|numCpuCores}/${THIS, metric=cpu|numCpuSockets} < 16 ? (${THIS, metric=cpu|numCpuSockets} *16) : ${THIS, metric=hardware|cpuInfo|numCpuCores}
  ```
  (Note: uses `cpu|numCpuSockets`, not `cpu|numpackages` — worth
  checking whether that stat key is populated if this formula is
  used as a pattern.)
- `Time On`:
  ```
  ${this, metric=sys|poweredOn}==1?5:0
  ```

### 3. World object display names and live instances

| Adapter kind | Resource kind key | Expected name | Live? |
|---|---|---|---|
| `VMWARE_INFRA_HEALTH` | `LICENSE_USAGE_WORLD` | License Usage | **YES** — 1 object, id `3891782c-00b5-4fed-ad72-4908f439337c`, name "License Usage", `resourceStatus=DATA_RECEIVING` |
| `NSXTAdapter` | `NSXT World` | NSX World | **YES** — 1 object, id `6fedd725-1350-40ce-a37f-1bdae6feef15`, name "NSX World", `resourceStatus=DATA_RECEIVING` |
| `CASAdapter` | `CAS World` | Automation World | Resource kind schema exists (name is literally "Automation World"), but **ABSENT live** — 0 objects of any kind under `CASAdapter`, and `GET /api/adapters?adapterKindKey=CASAdapter` returns zero adapter instances. No CASAdapter is configured on this instance at all, not just this world object. |

### 4. `ObjectCountMetricGroup:*|count` on vSphere World

Resource kind confirmed: `VMWARE:vSphere World` (display name
"vSphere World"), 1 live object (`6e146ce3-4403-4a41-9329-944b3a7ac07a`).

Not a gap, matches the prior pass's note (see Gap list item 8
above): the static `/statkeys` catalog lists a single **INSTANCED**
template key `ObjectCountMetricGroup|count`, not per-kind literal
entries. The per-child-kind variants (`ObjectCountMetricGroup:{Kind}
|count`) are dynamic instantiations that only appear in live
`stats/latest` output. Confirmed **defined and populated** on the
live vSphere World object, sample values: `VirtualMachine`=722,
`ClusterComputeResource`=6, `Datastore`=21,
`DistributedVirtualPortgroup`=61, `SupervisorCluster`=2, `Pod`=2,
`GuestCluster`=2, `Namespace`=8, `StoragePod`=1, `HostFolder`=1,
`VmwareDistributedVirtualSwitch`=6 (list truncated at first ~11 of
however many kind instances exist; all had non-null data).
