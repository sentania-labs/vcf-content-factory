# Automation Managed Host Count

- **Type:** supermetric
- **Slug:** vcf-license-automation-host-count
- **Authored YAML:** supermetrics/vcf_license_automation_host_count.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Number of vSphere hosts under vCenters that VCF Automation has as cloud accounts.
- Feeds Automation Usage Insights (Managed vSphere Hosts), Automation Consumption Trend,
  Automation Licensing Overtime. Formula unchanged.

## Spec

**Name:** `[VCF Content Factory] Automation Managed Host Count` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2] Automation Host Count`.

**Assignment (adapter kind / resource kind):**
- `CASAdapter / CAS World` (assignment)
- iterates `VMWARE / HostSystem` related to CAS World (depth 10)

**Unit:** `(none)`

**Source formula (verbatim):**

```
count(${adaptertype=VMWARE, objecttype=HostSystem, attribute=config|name, depth=10})
```

**Rebuild formula:**

```
count(${adaptertype=VMWARE, objecttype=HostSystem, attribute=config|name, depth=10})
```

**Raw keys used (8.18 recon status):**
- `HostSystem` `config|name` (property): defined, populated on ro818 (42 hosts)
- `CASAdapter / CAS World`: adapter kind installed on ro818, **0 resources** (no Automation
  instance); on prod the adapter kind is superseded by `VCFAutomation / Automation World`

**Dependencies (must be authored and policy-enabled first):**
- none

### Notes

- Counts every host under any Automation-attached vCenter, not just hosts running
  Automation-managed VMs. Source behaviour; the text widget explains the comparison.
- Target is 8.x, so `CASAdapter / CAS World` stays. Heads-up recorded in the dashboard
  note: 9.x needs `VCFAutomation / Automation World`.
- Cannot be proven non-zero on either recon instance (0 CAS resources).
