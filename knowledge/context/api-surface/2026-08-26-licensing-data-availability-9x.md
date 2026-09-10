# Where license entitlement and consumption live on VCF Ops 9.x

Investigated 2026-08-26. Read-only (GET only). Instances:
`prod` profile = VCF Operations 9.1.0.0 build 25541561, `devel`
profile = 9.0.2.0 build 25137838. Both carry real, valid licenses
(SME-confirmed).

## Verdict

**License entitlement and consumption data ARE obtainable on 9.x, but
only through the unsupported `/internal/licenses*` API, never through
the resource/metrics inventory surface.**

The 8.x path (`VMWARE_INFRA_HEALTH` / `LicenseUsage` /
`LICENSE_USAGE_WORLD` resources carrying `Assets|TotalUsage` and
`CostUnitAttributes|CostUnitLimit`) has a surviving *schema* on both
9.0 and 9.1 but **zero live resources**. Licensing moved out of the
analytics plane and into a first-class **License Manager** plane that
is not modelled as resources or metrics. Consequence: **no dashboard,
view, report, super metric, or alert can consume 9.x licensing data**,
because none of those surfaces can read a non-resource REST endpoint.

The supported public API exposes only the Ops appliance's own license
state, not fleet entitlement or consumption.

## Surfaces checked

| Surface | Result |
|---|---|
| Public spec (`operations-api.json`, `operations-api-9.1.json`) | Only `/api/product/licensing/{info,edition,npc/status}`. Self-license only. |
| `/api/deployment/licenses` (historical guess) | **404** on 9.1. Does not exist. |
| Internal spec (`internal-api.json`, `internal-api-9.1.json`) | Full License Manager surface. See below. |
| Fleet management (`/api/fleet-management/*`) | IAM, certificates, passwords only. **No licensing.** |
| VCF integration (`/api/integrations/vcf/*`, `/internal/integrations/vcf/*`) | Credentials, certificates, inventory query. **No licensing.** |
| CaSA (`/casa/*`) | 401 with Suite API credentials. **UNVERIFIED** (different auth principal); moot, `/internal/licenses` already returns the data. |
| Resource/metrics inventory | Zero live licensing resources (prior recon; unchanged). |

## The working endpoints (9.1)

All require `X-Ops-API-use-unsupported: true`. Verified: without the
header, `GET /internal/licenses` returns **403 Forbidden**. These are
internal/unsupported endpoints; Broadcom may change them without
notice.

| Endpoint | 9.1 | 9.0 | Returns |
|---|---|---|---|
| `GET /internal/licenses` | 200 | 200 (empty on devel) | Array of entitlements (`VcfLicense`) |
| `GET /internal/licenses/{licenseAllocationId}` | 200 | present | One entitlement |
| `GET /internal/product/licensing/license` | 200 | 200 | "Best" product license for this appliance |
| `GET /internal/licenses/vcenter-usages` | 200 | 200 (empty on devel) | Per-vCenter, per-product usage |
| `GET /internal/licenses/vcenter-usages/{vcenterId}` | 200 | **404** | 9.1-only |
| `GET /internal/licenses/vcenter-assets/{vcenterId}` | 200 | **404** | 9.1-only; per-host / per-cluster asset licensing |
| `GET /internal/license-manager/registration/status` | 200 | 200 | Registration + usage-report schedule |
| `POST /internal/entitlements/query` | in 9.1 spec | **404** | 9.1-only feature-entitlement check. **UNVERIFIED** (POST, not tested under the GET-only mandate; non-mutating by contract) |
| `GET /internal/costdrivers/license`, `/config` | 200 | present | Cost-driver rates (Cost/pricing plane, not entitlement) |

Devel (9.0) returned an **empty** `/internal/licenses` array and
`registration/status = UNREGISTERED`. That is an environment state on
that node (its License Manager was never registered), not proof that
9.0 lacks the endpoint. Prod (9.1) is `status = ENTITLED`,
`connectivityMode = DISCONNECTED`.

## Verbatim identifier strings (9.1 lab, the load-bearing output)

These replace the 8.x `ProductId startsWith "vSphere 8 Enterprise
Plus for VCF"` filter. Nothing here is guessed; all captured from
live responses.

### Entitlement-level (`GET /internal/licenses`)

Two entitlements present:

```
name                = "(TLG) VMware Cloud Foundation (cores)"
productName         = "VMware Cloud Foundation"
productDisplayName  = "VMware Cloud Foundation (cores)"
productFamily       = "vSphere"
productType         = "BASE"
entitlementType     = "SUBSCRIPTION"
unitOfMeasure       = "CORE"
totalQuantity       = 300
consumedQuantity    = 300
licenseAllocationId = "a38e84ed-2ea1-4434-b013-67eb398f73af"
assetType           = "AC"          assetOrigin = "REAL"
```

```
name                = "(TLG) VMware vSAN (TiB)"
productName         = "VMware vSAN"
productDisplayName  = "VMware vSAN (TiB)"
productFamily       = "vSAN"
productType         = "ADDON"
entitlementType     = "SUBSCRIPTION"
unitOfMeasure       = "TIB"
totalQuantity       = 300
consumedQuantity    = 300
licenseAllocationId = "69eb7441-5bb8-4183-a665-f6043dccf5a7"
```

The `(TLG)` prefix is part of *this lab's* license name (a Broadcom
TLG-issued license). **Do not filter on it**; it is instance data,
not a product identifier. Filter on `productName` /
`productDisplayName` / `productFamily`.

### Component `editionKey` strings (the 9.x analogue of 8.x edition names)

VCF (cores) entitlement components:

```
esx.vcf.entitlement.cpuCoreMin          VMware ESX Server      costUnit "cpuCore:16core"  measureUsage true
vc.vcf.entitlement.cpuCoreMin           VMware VirtualCenter Server                       measureUsage false
nsx.vcf.entitlement.cpuCoreMin          VMware NSX                                        measureUsage false
aria.vcf.entitlement.cpuCoreMin         VMware Aria Suite                                 measureUsage false
vrnetinsight.vcf.entitlement.cpuCoreMin VMware Aria Operations Networks                   measureUsage false
hcx.vcf.entitlement.cpuCoreMin          VMware HCX                                        measureUsage false
```

vSAN (TiB) entitlement components:

```
vsan.entitlement.TiB          VMware VSAN          costUnit "TiB"  measureUsage true
vsan.witness.entitlement.TiB  VMware VSAN Witness                  measureUsage false
```

`componentDisplayNames` for the Aria component are the 9.x product
names: `["VCF Operations", "Fleet lifecycle", "VCF Automation",
"VCF Operations orchestrator", "Log management"]`.

`productCompatibility.allowedAutoAssignProducts` for the VCF
entitlement: `["VMware Cloud Foundation", "VCF Edge", "VMware Cloud
Foundation for eOEM", "VMware vSphere Foundation"]`.

### Units and cost units

`unitOfMeasure` (entitlement level) enum: **`CORE`**, **`TIB`**.

`costUnitId` (usage level), complete set observed live:

```
cpuCore:16core     <- the licensed/billable unit for VCF cores
cpuCore:8core
cpuPackage:32core
TiB                <- the licensed/billable unit for vSAN
vm
```

Only one cost unit per asset is the licensed one
(`defaultCostUnit: true` and carrying a `licenseAllocationId`); the
rest are reported-but-not-charged alternatives. **This is the single
most important shape fact:** raw usage is multi-unit, licensed usage
is the one flagged unit.

### Asset-level enums (`vcenter-assets`)

```
assetType       VCENTER | ESX_HOST | VSAN_CLUSTER | PAIF | UNKNOWN
assetStatus     LICENSED | EXPIRED_LICENSE | EVALUATION |
                EXPIRED_EVALUATION | LICENSED_BY_OTHER_OPS
assignmentType  EVALUATION | AUTO_ASSIGNED | AUTO_ASSIGNED_FROM_OTHER_OPS |
                OVERRIDE | OVERRIDE_FROM_OTHER_OPS | LICENSE_KEY
```

Observed live: `ESX_HOST` / `VMware ESX Server` and `VSAN_CLUSTER` /
`VMware VSAN`, all `AUTO_ASSIGNED`, all `EXPIRED_LICENSE` (this lab's
license passed its usage-expiration date).

`assetUri` format: `urn:vri:com.vmware.license.asset:host-6011-<vc-uuid>`
and `urn:vri:com.vmware.license.asset:domain-c6004-<vc-uuid>`.

## Response shapes (verbatim excerpts, prod 9.1)

`GET /internal/licenses/vcenter-usages` — one element:

```json
{
  "vcId": "4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e",
  "vcHost": "vcf-lab-vcenter-mgmt.int.sentania.net",
  "vcAdapterName": "vcf-lab-vcenter-mgmt.int.sentania.net",
  "productFamily": "vSphere",
  "productFamilyVersion": "9.1.0",
  "componentProductFamily": "VMware ESX Server",
  "componentProductFamilyVersion": "9.1.0",
  "licenseAllocationId": "a38e84ed-2ea1-4434-b013-67eb398f73af",
  "allocationId": "a38e84ed-2ea1-4434-b013-67eb398f73af",
  "expirationDate": 1787702400000,
  "override": false, "evaluation": false, "sddcManaged": true,
  "licensedUsage": {"costUnitId": "cpuCore:16core", "usage": 96, "usageV8": 0},
  "rawUsage": [
    {"costUnitId": "TiB", "usage": 20, "usageV8": 0},
    {"costUnitId": "cpuCore:16core", "usage": 96, "usageV8": 0},
    {"costUnitId": "cpuCore:8core", "usage": 88, "usageV8": 0},
    {"costUnitId": "cpuPackage:32core", "usage": 6, "usageV8": 0},
    {"costUnitId": "vm", "usage": 33, "usageV8": 0}
  ]
}
```

`GET /internal/licenses/vcenter-assets/{vcenterId}` — one element:

```json
{
  "assetUri": "urn:vri:com.vmware.license.asset:host-6011-1b46463b-c05f-4e79-93a8-3aa9c2a9f251",
  "assetName": "vcf-lab-mgmt-esx03.int.sentania.net",
  "assetType": "ESX_HOST",
  "assignmentType": "AUTO_ASSIGNED",
  "assetStatus": "EXPIRED_LICENSE",
  "componentProductFamily": "VMware ESX Server",
  "componentProductFamilyVersion": "9.1",
  "clusterName": "vcf-lab-mgmt-cl01",
  "dataCenterName": "vcf-lab-mgmt-dc01",
  "expirationDate": 1787702400000,
  "vcenterExpirationDate": 1787702400000,
  "assetCostUnits": [
    {"costUnitId": "cpuCore:16core", "usage": 16,
     "licenseAllocationId": "a38e84ed-2ea1-4434-b013-67eb398f73af",
     "licenseName": "(TLG) VMware Cloud Foundation (cores)",
     "licenseExpirationDate": 1787702400000, "override": false,
     "productDisplayName": "VMware Cloud Foundation (cores)",
     "defaultCostUnit": true},
    {"costUnitId": "TiB", "usage": 4, "defaultCostUnit": false},
    {"costUnitId": "cpuCore:8core", "usage": 16, "defaultCostUnit": false},
    {"costUnitId": "cpuPackage:32core", "usage": 1, "defaultCostUnit": false},
    {"costUnitId": "vm", "usage": 6, "defaultCostUnit": false}
  ]
}
```

`GET /api/product/licensing/info` (public, supported) — self-license
only, no consumption:

```json
{"licenseKey":"","licensed":true,"expirationDate":1787702400000,
 "licenseName":"(TLG) VMware Cloud Foundation (cores)"}
```

`GET /api/product/licensing/edition` -> `{"productLicensingEdition":"ENTERPRISE"}`
`GET /api/product/licensing/npc/status` -> `{"npcEnabled":true}`

## Gotchas found

1. **`consumedQuantity` is not current usage.** Per spec and observed:
   both entitlements report `totalQuantity = consumedQuantity = 300`,
   which is the *reported* quantity from the last usage report, not
   live consumption. The `usage` field on `VcfLicense` was **absent**
   (null) on both entitlements in this build.
2. **Current consumption must be derived** by summing
   `licensedUsage.usage` from `vcenter-usages` grouped by
   `licenseAllocationId` + `costUnitId`. Live prod computation:
   `a38e84ed... cpuCore:16core = 160` (of 300 CORE) and
   `69eb7441... TiB = 19` (of 300 TIB).
3. **`vcenter-assets` `pageInfo.totalCount` is wrong**: reports `0`
   while `content` holds 7 / 2 / 2 items. Do not paginate on
   `totalCount` for that endpoint. `vcenter-usages` reports it
   correctly (`totalCount: 5`).
4. **Multiple rows per vCenter** in `vcenter-usages`: one per
   `componentProductFamily` (ESX row plus a vSAN row for the same
   `vcId`). Do not key on `vcId` alone.
5. **`usageV8`** appears alongside every usage figure and was `0`
   everywhere in this lab. Presumed the 8.x-model usage carry-over.
   **UNVERIFIED.**
6. `/internal/license-manager/cloud/exchanges` requires a `startDate`
   query parameter (400 without it).
7. `/internal/costdrivers/license` is the **Cost/pricing** plane
   (rates per core, `osLicenseType` such as `VCF_PER_CORE`,
   `VMWARE_VSAN_ADDON`), not entitlement. Different question, do not
   conflate.

## Implications for the 8.x dashboard modernization

There is no metric-plane path. A faithful 9.x "License Consumption
Overview" cannot be built from dashboards/views/super metrics against
built-in content. Options, in order of honesty:

1. **Declare it not portable.** Ship nothing; the data is not in the
   analytics plane on 9.x.
2. **Build a management pack** that polls `/internal/licenses` and
   `/internal/licenses/vcenter-usages` and pushes entitlement and
   consumption as `ARIA_OPS` metrics onto existing resources (or as
   its own resource kind). That reconstitutes a metric surface that
   dashboards can then consume. Depends on an unsupported internal
   endpoint, which must be stated loudly in the MP description.
3. **Point users at the built-in UI** (Administration -> Licensing),
   which is what consumes these endpoints today.

## Not tested

- `POST /internal/entitlements/query` (9.1 only) — GET-only mandate.
- CaSA `/casa/*` licensing paths — 401 under Suite API credentials.
- Whether a **registered, connected** License Manager populates
  `VcfLicense.usage` and a non-zero `usageReportId`. This lab is
  `DISCONNECTED`.
- Whether 9.0 populates `/internal/licenses` when its License Manager
  is registered. Devel was `UNREGISTERED`.
