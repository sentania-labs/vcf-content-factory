# License usage on VCF Operations 9.1 — recon across devel/prod

**Date:** 2026-08-26
**Task:** Does any 9.x instance expose license-usage data, and in what
model? Follow-on to `2026-08-26-vcf-license-consumption-recon-818.md`
(which found `VMWARE_INFRA_HEALTH:LicenseUsage` populated on ro818
8.18.7, zero on `prod` 9.1.0). This recon widens the check to the
released 9.1 profiles: `devel` (9.1.x) and `prod` (9.1.0 GA,
read-only). All calls GET-only, via `VCFOpsClient.from_env(profile=...)`.
Raw statkey/property dumps and sweep scripts cached under the session
scratchpad (not committed).

## Bottom line

**Neither 9.1 instance has real license-consumption numbers.** The
8.18-era model (`VMWARE_INFRA_HEALTH:LicenseUsage`) is defined
identically on both but has **zero live resources**, the same dead end
the 818 recon already found on `prod`. No successor license-usage
resource kind with live data was found on either instance. **The
dashboard cannot be tested with real data on these labs today.**

## 1. Adapter kinds present (per instance)

| Adapter kind | devel | prod |
|---|---|---|
| `VMWARE_INFRA_HEALTH` (Infrastructure Health) | yes | yes |
| `VcfAdapter` (VMware Cloud Foundation) | yes | yes |
| `VMWARE_INFRA_MANAGEMENT` (Infrastructure Management) | yes | yes |
| (one platform-services adapter, not license-bearing) | yes | yes |
| `VCFAutomation` | yes | yes |
| `CASAdapter` (legacy Automation, superseded) | no | yes (0 resources) |
| `PingAdapter`, `SERVICENOW_ADAPTER`, `TAMManagementPack`, `mpb_*` | no | yes (lab-specific MPBs) |

21 adapter kinds on devel, 27 on prod. No adapter kind literally named
`VCF`; the VCF-9-era name remains `VcfAdapter` on both, consistent with
the 818 recon's finding.

## 2. `VMWARE_INFRA_HEALTH` license-family resource kinds — defined vs populated

Resource kinds defined under `VMWARE_INFRA_HEALTH` (49 kinds on each
instance, identical set): `LicenseUsage`, `LICENSE_USAGE_WORLD`,
`LicensedAsset`, `LicensedVC`, `vCenterLicensing`, `vCenterLicense`
among them. Schema (statkeys/properties) for `LicenseUsage` is
**byte-identical on both instances** and matches the 8.18 vocabulary
exactly:

| Key | Type | devel | prod |
|---|---|---|---|
| `Assets\|Total` | metric | defined | defined |
| `Assets\|TotalUsage` | metric | defined | defined |
| `CostUnitAttributes\|CostUnitType` | property | defined | defined |
| `CostUnitAttributes\|CostUnitLimit` | property | defined | defined |
| `ProductId` | property | defined | defined |

Live resource counts (`GET /api/resources?resourceKind=X&adapterKindKey=VMWARE_INFRA_HEALTH`,
field is `pageInfo.totalCount`):

| Resource kind | devel | prod |
|---|---|---|
| `LicenseUsage` | **0** | **0** |
| `LICENSE_USAGE_WORLD` | **0** | **0** |
| `LicensedAsset` | **0** | **0** |
| `LicensedVC` | **0** | **0** |
| `vCenterLicensing` | **0** | **0** |
| `vCenterLicense` | **0** | **0** |

Every one of the 8.18-model license resource kinds is defined
(describe.xml-level) but has **zero live objects on both 9.1
instances**.

## 3. Successor model

A full sweep of every adapter kind's resource kinds/statkeys/properties
for `license|productid|costunit|totalusage|entitlement|\bcore\b` found no
`Container/VcfLicensing` resource kind on either instance (404 on
statkeys/properties/resources).

## 4. Ruled out: `Container/Licensing`, platform-services adapter kinds, VCF Ops' own license

Three more candidates surfaced by name and were checked and excluded:

- **`Container/Licensing`** (no "Vcf" prefix) — present on both
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
  Capacity, ExpirationDate}`, populated on both (1 resource each).
  This is the **Ops appliance's own license** (both instances run on an
  `EVALUATION` license; `prod`'s is expired, `-8` days remaining),
  unrelated to vSphere/vSAN/NSX/Automation product license consumption.
  Matches the vendor doc's "License Metrics for Cluster Object" section
  (`reference/docs/vcf9/metrics-properties.md` pages 4428–4429) — that
  section is about the VCF Ops self-monitoring cluster, not a fleet
  license dashboard source.

## 5. Core-count vocabulary (dashboard's dangling SM dependency)

`cpu|corecount_provisioned` is defined and populated identically on
`VMWARE/HostSystem`, `ClusterComputeResource`, `Datacenter`,
`CustomDatacenter`, `vSphere World`, `vSphere Private World`, and
`VcfAdapter/VCFWorld` on **both** instances — this part of the 8.18
dashboard's requirements (the still-missing
`sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6` "VCF License Potential
Cores" dependency noted in the 818 recon) is fully buildable on 9.1,
independent of the license-usage gap above.

## Verdict

1. **Can the dashboard be tested on 9.1?** Not with real
   license-consumption data, on either `devel` or `prod`. The 8.x key
   set (`VMWARE_INFRA_HEALTH:LicenseUsage`) is schema-present but
   zero-populated on both. Core-count and host-OS-license-cost widgets
   (`VMWARE/HostSystem`, `vSphere World`) are fully testable with real
   numbers on both.
2. **Would a 9.x-native variant need different keys?** Not answerable
   from these two instances: no successor license-usage model with
   data was found. Re-check on a released instance with real
   entitlements loaded before designing one.

## Gap list

- **API gap:** no endpoint answers "is this fleet actually enrolled
  with real license keys" directly (read-only Ops API only).
- **Reference sources:** allowlisted repos in
  `knowledge/context/reference_sources.md` were not re-grepped this
  round (818 recon already established 0 matches for the dashboard/
  views/SMs across all of them and repo YAML; no new content type
  entered scope here).
