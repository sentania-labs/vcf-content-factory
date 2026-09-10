# License usage on VCF Operations 9.x — recon across qa/devel/main/prod

**Date:** 2026-08-26
**Task:** Does any 9.x instance expose license-usage data, and in what
model? Follow-on to `2026-08-26-vcf-license-consumption-recon-818.md`
(which found `VMWARE_INFRA_HEALTH:LicenseUsage` populated on ro818
8.18.7, zero on `prod` 9.1.0). This recon widens the check to all four
9.x profiles: `qa` (9.2.0.0), `devel` (9.1.x), `main` (9.2.0.0), `prod`
(9.1.0 GA, read-only). All calls GET-only, via
`VCFOpsClient.from_env(profile=...)`. Raw statkey/property dumps and
sweep scripts cached under the session scratchpad (not committed).

## Bottom line

**No 9.x instance has real license-consumption numbers.** The 8.18-era
model (`VMWARE_INFRA_HEALTH:LicenseUsage`) is defined identically on
all four 9.x boxes but has **zero live resources everywhere**, same
dead end the 818 recon already found on `prod`. VCF 9 does have a
successor model — `Container:VcfLicensing` — but it exists on only
**one** of the four instances (`main`), and even there every value is
a zero/sentinel: the object is wired up but nothing is feeding it real
per-product entitlement numbers. **The dashboard cannot be tested with
real data on any of these four labs today.** A 9.x-native variant
would need a different key set than the 8.x one, and that key set is
only schema-verified, not value-verified, on one instance.

## 1. Adapter kinds present (per instance)

| Adapter kind | qa | devel | main | prod |
|---|---|---|---|---|
| `VMWARE_INFRA_HEALTH` (Infrastructure Health) | yes | yes | yes | yes |
| `VcfAdapter` (VMware Cloud Foundation) | yes | yes | yes | yes |
| `VMWARE_INFRA_MANAGEMENT` (Infrastructure Management) | yes | yes | yes | yes |
| (one platform-services adapter, not license-bearing) | yes | yes | yes | yes |
| `VCFAutomation` | no | yes | yes | yes |
| `CASAdapter` (legacy Automation, superseded) | no | no | no | yes (0 resources) |
| `PingAdapter`, `SERVICENOW_ADAPTER`, `TAMManagementPack`, `mpb_*` | no | no | no | yes (lab-specific MPBs) |

22 adapter kinds on qa, 21 on devel, 22 on main, 27 on prod. No
adapter kind literally named `VCF`; the VCF-9-era name remains
`VcfAdapter` on all four, consistent with the 818 recon's finding.

## 2. `VMWARE_INFRA_HEALTH` license-family resource kinds — defined vs populated

Resource kinds defined under `VMWARE_INFRA_HEALTH` (49 kinds on every
instance, identical set): `LicenseUsage`, `LICENSE_USAGE_WORLD`,
`LicensedAsset`, `LicensedVC`, `vCenterLicensing`, `vCenterLicense`
among them. Schema (statkeys/properties) for `LicenseUsage` is
**byte-identical across all four instances** and matches the 8.18
vocabulary exactly:

| Key | Type | qa | devel | main | prod |
|---|---|---|---|---|---|
| `Assets\|Total` | metric | defined | defined | defined | defined |
| `Assets\|TotalUsage` | metric | defined | defined | defined | defined |
| `CostUnitAttributes\|CostUnitType` | property | defined | defined | defined | defined |
| `CostUnitAttributes\|CostUnitLimit` | property | defined | defined | defined | defined |
| `ProductId` | property | defined | defined | defined | defined |

Live resource counts (`GET /api/resources?resourceKind=X&adapterKindKey=VMWARE_INFRA_HEALTH`,
field is `pageInfo.totalCount`):

| Resource kind | qa | devel | main | prod |
|---|---|---|---|---|
| `LicenseUsage` | **0** | **0** | **0** | **0** |
| `LICENSE_USAGE_WORLD` | **0** | **0** | **0** | **0** |
| `LicensedAsset` | **0** | **0** | **0** | **0** |
| `LicensedVC` | **0** | **0** | **0** | **0** |
| `vCenterLicensing` | **0** | **0** | **0** | **0** |
| `vCenterLicense` | **0** | **0** | **0** | **0** |

Every one of the 8.18-model license resource kinds is defined
(describe.xml-level) but has **zero live objects on all four 9.x
instances**, `qa` and `main` included despite being 9.2.0.0 — this
isn't a 9.1-vs-9.2 version split.

## 3. VCF-9 replacement: `Container:VcfLicensing`

Full sweep of every adapter kind's resource kinds/statkeys/properties
for `license|productid|costunit|totalusage|entitlement|\bcore\b`
(445–480 adapter-kind/resource-kind pairs per instance) turned up a
resource kind not present in the 8.18 vocabulary: **`VcfLicensing`**,
under the generic `Container` adapter kind (the VCF Ops self-monitoring
grouping adapter, present on all four instances for unrelated
container objects).

| Instance | `Container/VcfLicensing` defined? | Live resources |
|---|---|---|
| qa (9.2.0.0) | **no** (404 on statkeys/properties/resources) | — |
| devel (9.1.x) | **no** | — |
| main (9.2.0.0) | **yes** — 88 statkeys, 24 properties | **1** ("VCF Licensing", id `d669c16b-9fa5-4332-a77c-67a39e6a87cd`) |
| prod (9.1.0 GA) | **no** | — |

Only `main` has this resource kind at all, so it isn't a clean
version split either (qa is the same build number and lacks it) —
looks like a lab/environment-specific pak or fleet-attachment
difference, not something predictable from the version string alone.

**Key vocabulary on `main` (schema only, see §4 for live values):**

- `Licenses|Product|Entitlement|{AssetCount, AllocatedCapacity,
  AvailableCapacity, UsedCapacity, UOM, IssueCount, Name, Product,
  LicenseType, LicenseServer, ExpirationDate, ExpirationReason,
  UsageDueDate}` — this is the direct successor to 8.18's
  `ProductId` + `CostUnitAttributes|CostUnitLimit`, restructured as
  an instanced group per product/entitlement rather than one resource
  per license.
- `Licenses|Product|ProductSummary|{TotalAllocatedCapacity,
  TotalUsedCapacity, TotalAvailableCapacity, Name, ProductFamily,
  DaysUntilNextLicenseExpiration, NextLicenseExpirationDate,
  NextExpirationReason, UsageDueDate}`
- `Licenses|LicensesSummary|{DaysToNextLicenseExpiration,
  DaysToUsageDue, TiBAvailableCapacity, CoresAvailableCapacity,
  HasExpiredInGraceUsage, HasExpiredPastGraceUsage,
  HasExpiredInGraceSubscription, HasExpiredPastGraceSubscription,
  NextLicenseExpirationDate, NextExpirationReason, UsageDueDate}` —
  fleet-wide rollup, no per-product breakdown.
- `Assets|{ESXHosts,vSANClusters,vCenter,PAIF}|{LicensedAssetCount,
  LicensedUsedCapacity, LicenseExpiredAssetCount,
  LicenseExpiredUsedCapacity, EvaluationAssetCount,
  EvaluationUsedCapacity, EvaluationExpiredAssetCount,
  EvaluationExpiredUsedCapacity, DaysToNextEvaluationExpiration,
  NextLicenseExpirationDate}` — per-asset-type breakdown; `PAIF` is
  the fourth asset class alongside hosts/vSAN/vCenter (VCF's
  Private AI Foundation component).

## 4. `main`'s `VcfLicensing` object — live values

`GET /api/resources/{id}/stats/latest` and `/properties`, single
resource "VCF Licensing":

- 46 stat entries returned, **every `Assets|*` count is `0.0`**, every
  `DaysToNextEvaluationExpiration` is `-1.0` (not-applicable
  sentinel), `Licenses|LicensesSummary|CoresAvailableCapacity` and
  `TiBAvailableCapacity` are both `0.0`.
- Properties: all `Licenses|LicensesSummary|HasExpired*` flags
  `false`, all expiration-date/reason properties empty string.
- No `Licenses|Product|Entitlement|*` or
  `Licenses|Product|ProductSummary|*` instanced children were
  observed in the top-level stat list (those are per-product
  instanced groups; none instantiated here, consistent with zero
  entitlements loaded).

**Interpretation:** the object exists and is wired into collection,
but nothing is feeding it real product entitlement data on this lab.
Likely cause: this lab's VCF fleet isn't running with real Broadcom
license keys synced through the depot/license service (evaluation or
unlicensed lab build) — same class of explanation the 818 recon gave
for other zero-population findings (policy toggles don't explain
zero *object* counts). **Inferred, not confirmed against SDDC
Manager/depot config** — out of scope for a read-only Ops-API recon.

## 5. Ruled out: `Container/Licensing`, platform-services adapter kinds, VCF Ops' own license

Three more candidates surfaced by name and were checked and excluded:

- **`Container/Licensing`** (no "Vcf" prefix) — present on all four
  instances, 2 live resources each (`Unlicensed Group`, `Product
  Licensing`; prod has 2 more, MPB-related). This is a generic
  health/risk/badge **grouping folder** object (`badge|health`,
  `System Attributes|*` only) — the "Licensing" folder in the object
  browser, not usage data.
- **One platform-services adapter's kinds (not license-bearing)**:
  service-health telemetry only; none of their statkeys/properties
  matched the license term sweep.
- **VCF Operations' own product license** —
  `vCenter Operations Adapter/vC-Ops-Cluster` exposes
  `Licensing|LicenseKey|{Usage, UsageCount, DaysRemaining, Type,
  Capacity, ExpirationDate}`, populated on all four (1 resource each).
  This is the **Ops appliance's own license** (all four instances are
  running on an `EVALUATION` license; `prod`'s is expired, `-8` days
  remaining), unrelated to vSphere/vSAN/NSX/Automation product license
  consumption. Matches the vendor doc's "License Metrics for Cluster
  Object" section (`reference/docs/vcf9/metrics-properties.md` pages
  4428–4429) — that section is about the VCF Ops self-monitoring
  cluster, not a fleet license dashboard source.

## 6. Core-count vocabulary (dashboard's dangling SM dependency)

`cpu|corecount_provisioned` is defined and populated identically on
`VMWARE/HostSystem`, `ClusterComputeResource`, `Datacenter`,
`CustomDatacenter`, `vSphere World`, `vSphere Private World`, and
`VcfAdapter/VCFWorld` on **all four** instances — this part of the
8.18 dashboard's requirements (the still-missing
`sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6` "VCF License Potential
Cores" dependency noted in the 818 recon) is fully buildable on any
of the four 9.x boxes, independent of the license-usage gap above.

## Verdict

1. **Can the dashboard be tested on any 9.x box?** Not with real
   license-consumption data, on any of `qa`, `devel`, `main`, or
   `prod`. The 8.x key set (`VMWARE_INFRA_HEALTH:LicenseUsage`) is
   schema-present but zero-populated on all four. The VCF-9 successor
   (`Container:VcfLicensing`) exists on only `main`, and even there
   every value is a zero/sentinel — usable to prove widget plumbing
   against an empty object, not to validate real percentages or
   alert thresholds. Core-count and host-OS-license-cost widgets
   (`VMWARE/HostSystem`, `vSphere World`) are fully testable with
   real numbers on any of the four.
2. **Would a 9.x-native variant need different keys?** Yes. Rebuild
   target moves from `VMWARE_INFRA_HEALTH:LicenseUsage`
   (`Assets|TotalUsage`, `CostUnitAttributes|CostUnitLimit`,
   `ProductId`, one resource per license) to `Container:VcfLicensing`
   (`Licenses|Product|Entitlement|*`, `Licenses|Product|ProductSummary|*`,
   `Assets|{ESXHosts,vSANClusters,vCenter,PAIF}|*`, one resource per
   fleet with per-product instanced children). That new key set is
   presently **schema-verified only** (on `main`), not
   value-verified, since `main`'s single instance carries no non-zero
   data. Building against it today would be authoring blind against
   real numbers; recommend re-checking `main` (or any lab with real
   Broadcom/VCF+ entitlements loaded through the depot/license
   service) later, or asking the user whether a zero-value schema
   build is acceptable for now.

## Gap list

- **API gap:** no endpoint answers "is this fleet actually enrolled
  with real license keys" directly; inferred from all-zero
  `Assets|*` counts on `main`'s `VcfLicensing` object, not confirmed
  against SDDC Manager/depot state (out of scope, read-only Ops API
  only).
- **Vocabulary gap, resolved:** `Container:VcfLicensing` was not in
  `reference/docs/vcf9/metrics-properties.md` (that doc's only
  license-adjacent section, "License Metrics for Cluster Object",
  page 4428, is the Ops-appliance self-license, ruled out in §5) —
  found via live sweep instead, not vendor doc.
- **Reference sources:** allowlisted repos in
  `knowledge/context/reference_sources.md` were not re-grepped this
  round (818 recon already established 0 matches for the dashboard/
  views/SMs across all of them and repo YAML; no new content type
  entered scope here).
