# vSAN Total License Capacity (TiB)

- **Type:** supermetric
- **Slug:** vcf-license-vsan-total-license-capacity
- **Authored YAML:** supermetrics/vcf_license_vsan_total_license_capacity.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Total vSAN capacity licensed (TiB), sum of cost-unit limits over vSAN license keys.
- Feeds License Overview (Total vSAN License Capacity (TiB)) and the VCF Licensing
  Overtime table. Formula unchanged.

## Spec

**Name:** `[VCF Content Factory] vSAN Total License Capacity (TiB)` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2] vSAN Total License Capacity`.

**Assignment (adapter kind / resource kind):**
- `VMWARE_INFRA_HEALTH / LICENSE_USAGE_WORLD` (assignment; 1 resource "License Usage" on ro818)
- iterates `VMWARE_INFRA_HEALTH / LicenseUsage` (11 resources on ro818)

**Unit:** `(none)`

**Source formula (verbatim):**

```
sum(${adaptertype=VMWARE_INFRA_HEALTH, objecttype=LicenseUsage, metric=CostUnitAttributes|CostUnitLimit, depth=10, where="ProductId startsWith vSAN"})
```

**Rebuild formula:**

```
sum(${adaptertype=VMWARE_INFRA_HEALTH, objecttype=LicenseUsage, metric=CostUnitAttributes|CostUnitLimit, depth=10, where="ProductId startsWith vSAN"})
```

**Raw keys used (8.18 recon status):**
- `LicenseUsage` `CostUnitAttributes|CostUnitLimit` (property, addressed via `metric=`): defined, populated on ro818
- `LicenseUsage` `ProductId` (property, where clause): defined, populated on ro818

**Dependencies (must be authored and policy-enabled first):**
- none

### LicenseUsage object model (8.18-verified)

`VMWARE_INFRA_HEALTH` adapter. The SM is assigned to the single rollup resource
`LICENSE_USAGE_WORLD` ("License Usage", 1 resource on ro818) and the formula
walks its `LicenseUsage` descendants (one per license key/product, 11 on ro818):

| Key | Kind | ro818 |
|---|---|---|
| `Assets|TotalUsage` | metric | populated, 0.0 to 30.0 |
| `CostUnitAttributes|CostUnitLimit` | **property** (formula uses `metric=`, accepted) | populated, 2000.0 |
| `ProductId` | property, bare key, where-clause only | populated: `vSAN Enterprise`, `vSphere 8 Enterprise Plus for VCF`, `vSphere 8 Enterprise Plus`, `vCenter Server 8 Standard`, `vSphere 7 Enterprise Plus` |

Do not point statkey lookups at `LICENSE_USAGE_WORLD`; the keys live on `LicenseUsage`.
- The `ProductId startsWith ...` literal is the whole filter. On 8.18 the strings above are
  confirmed present, so the literal is kept verbatim. Any other product string sums to zero
  silently (DSL pitfall 4); the description must say so.
- Single string operator in the where clause, no `&&` (DSL pitfall 1). Kept as source.
- `depth=10` kept: World to LicenseUsage is one hop but 10 is harmless and matches source.
- No existing content or built-in covers this (recon: 0/12 SM names on ro818 and prod, repo clean).
