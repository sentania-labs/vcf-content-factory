# UniFi Controller Adapter v1 — Golden Baseline (devel, pre-migration)

**Captured:** 2026-06-10
**Instance:** vcf-lab-operations-devel.int.sentania.net (VCF Ops 9.0.2)
**Purpose:** Acceptance bar for framework v2 migration. Because the adapter is installed but has no configured adapter instance, there is no parity baseline to maintain. Post-migration acceptance criterion is "installs and collects cleanly."
**Secrets check:** No secrets present.

---

## 1. Adapter / Solution Status

The VCF Content Factory UniFi Controller management pack is **installed** on the devel instance — the solution is registered and the adapter kind is active. However, **no adapter instance has been configured**. There are zero resources of adapterKindKey `unifi_controller` anywhere in the instance.

| Field | Value |
|---|---|
| solution_id | VCF Content Factory UniFi Controller |
| solution_name | VCF Content Factory UniFi Controller |
| solution_version | **1.0.0.2** |
| vendor | VCF Content Factory |
| adapter_kind_key | `unifi_controller` |
| adapter_kind_name | UniFi Controller |
| adapter_kind_type | GENERAL |
| adapter_instances_configured | **0** |
| adapter_instance_resource_id | none |
| credentialInstanceId | none |
| monitoringInterval | N/A |
| numberOfResourcesCollected | 0 |
| numberOfMetricsCollected | 0 |
| lastCollected | never |
| resourceStatus | N/A |
| resourceHealth | N/A |
| messageFromAdapterInstance | N/A |

**Verification method:** Full resource enumeration across all 406 resources in the devel instance. Zero resources with `adapterKindKey=unifi_controller`. All 13 adapter instance IDs accounted for — none maps to `unifi_controller`. The 13 active adapter instance IDs are: `synology_diskstation` (1), `vcfcf_compliance` (2), `VMWARE` (4), `VMWARE_INFRA_HEALTH` (1), `Container/vC-Ops` (2), `VirtualAndPhysicalSANAdapter` (1), `VMWARE_INFRA_MANAGEMENT` (1), `ManagementPackBuilderAdapter` (1).

---

## 2. Adapter Own Resource Tree

No resources. The adapter kind was installed via pak but no instance has been created.

---

## 3. Stitched Properties on Foreign Resources

The solution description states: "LLDP-based stitching to ESXi hosts." In v1, this stitching has not been exercised because no adapter instance exists.

All 8 VMWARE/HostSystem resources were checked for properties with `unifi` in the key name. Result: **zero UniFi-namespaced properties on any HostSystem resource.** Confirmed: no stitching has occurred.

---

## 4. Collection Cadence

Not applicable. No adapter instance configured.

---

## 5. Post-Migration Acceptance Criteria

Since there is no v1 baseline to diff against, the acceptance criterion for the v2 migration is:

1. **Install:** The v2 pak installs cleanly on the devel instance without errors.
2. **Instance creation:** A new adapter instance can be created with UniFi controller credentials.
3. **Discovery:** The adapter discovers at least one site, gateway, switch, access point, or camera.
4. **Data collection:** Resources report `DATA_RECEIVING` / `STARTED` with `resourceHealth=GREEN` within one collection cycle.
5. **No regressions on Synology:** Synology adapter continues collecting (separate adapter kind; no expected interference).
6. **Stitching (if exercised):** If the lab has LLDP-reachable ESXi hosts, verify UniFi-namespaced properties appear on the corresponding VMWARE/HostSystem resources.

**Known inventory (from solution description):** The v2 adapter is designed to discover sites, gateways, switches, access points, NVR, and cameras, with per-switch-port and per-AP-radio child objects.
