# Automation Licensed Cores

- **Type:** supermetric
- **Slug:** vcf-license-automation-license-count
- **Authored YAML:** supermetrics/vcf_license_automation_license_count.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Licensed cores across the hosts Automation can see. Feeds Automation Usage Insights
  (Automation License Consumption), Automation Consumption Trend, Automation Licensing Overtime.

## Spec

**Name:** `[VCF Content Factory] Automation Licensed Cores` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2] Automation License Count`.

**Assignment (adapter kind / resource kind):**
- `CASAdapter / CAS World` (assignment)
- iterates `VMWARE / HostSystem` related to CAS World (depth 10)

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
- `CASAdapter / CAS World`: 0 resources on ro818 (structural validation only)

**Dependencies (must be authored and policy-enabled first):**
- `[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)` (replaces `sm_5ea91f64`)

### Notes

- Only change: dangling UUID becomes a name reference. Same caveats as NSX Licensed Cores.

## CONFIRMED BY SCOTT 2026-08-26 (was: assumption)

Inherits the 16-core-minimum assumption from the per-host SM.
