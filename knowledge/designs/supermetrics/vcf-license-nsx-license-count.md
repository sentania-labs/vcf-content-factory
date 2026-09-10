# NSX Licensed Cores

- **Type:** supermetric
- **Slug:** vcf-license-nsx-license-count
- **Authored YAML:** supermetrics/vcf_license_nsx_license_count.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Licensed cores across the vSphere hosts that NSX knows about (hosts reachable from NSXT
  World through the NSX-to-vCenter relationship). The "how much of my VCF core count is
  NSX-bearing" number.
- Feeds NSX Usage Insights (NSX Licensed Cores), NSX Consumption Trend, NSX Licensing Overtime.

## Spec

**Name:** `[VCF Content Factory] NSX Licensed Cores` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2] NSX License Count`.

**Assignment (adapter kind / resource kind):**
- `NSXTAdapter / NSXT World` (assignment; 1 resource on ro818)
- iterates `VMWARE / HostSystem` related to NSXT World (depth 10)

**Unit:** `(none)`

**Source formula (verbatim):**

```
sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322, depth=10})
```

**Rebuild formula:**

```
sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|@supermetric:"[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)", depth=10})
```

**Raw keys used (8.18 recon status):**
- none directly; per-host SM keys via `vcf-license-host-licensed-cores.md`

**Dependencies (must be authored and policy-enabled first):**
- `[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)` (replaces `sm_5ea91f64`)

### Notes

- Only change from source: the dangling UUID becomes a name reference to the re-derived SM.
- Cross-adapter walk (NSXT World -> HostSystem) relies on the NSX adapter's relationship to
  vCenter hosts. Recon could not exercise it (0 TransportNode objects); live-verify.
- The semantics are "hosts NSX can see", which may be broader than "hosts prepared as
  transport nodes". Source behaviour kept; if Scott wants transport-node-only cores the
  formula would iterate TransportNode and needs a host-to-transport-node hop (chained SM).

## CONFIRMED BY SCOTT 2026-08-26 (was: assumption)

Inherits the 16-core-minimum assumption from the per-host SM.
