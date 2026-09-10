# VCF License Potential Cores

- **Type:** supermetric
- **Slug:** vcf-license-potential-cores
- **Authored YAML:** supermetrics/vcf_license_potential_cores.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Cores you pay for but do not have: licensed cores under the 16-per-socket minimum minus
  physical cores. Zero means every socket has at least 16 cores. Feeds vSphere Environment
  Insights (VCF License Potential Cores).

## Spec

**Name:** `[VCF Content Factory] VCF License Potential Cores` (RULE-006 prefix, literal brackets, one space).
Source name: `[VCF Consumption Overview v2]VCF License Potential Cores (dashboard W6 still carries the pre-rename `License Waste Count`)`.

**Assignment (adapter kind / resource kind):**
- `VMWARE / vSphere World`

**Unit:** `(none)`

**Source formula (verbatim):**

```
${this, metric=Super Metric|sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6} - ${this, metric=cpu|corecount_provisioned}
```

**Rebuild formula:**

```
${this, metric=Super Metric|@supermetric:"[VCF Content Factory] vSphere World VCF Licensed Cores"}
 - sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=cpu|corecount_provisioned, depth=10})
```

**Raw keys used (8.18 recon status):**
- `HostSystem` `cpu|corecount_provisioned` (metric, Cores): 8.18-verified, 56.0 on ro818
- (indirect) per-host licensed-cores keys

**Dependencies (must be authored and policy-enabled first):**
- `[VCF Content Factory] vSphere World VCF Licensed Cores` (replaces `sm_3b4464fc`)
- (transitively) `[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)`

### Notes

- **Deviation (bug fix, recon gap 3):** the source is assigned to `vSphere World` but reads
  `${this, metric=cpu|corecount_provisioned}`, a HostSystem metric that does not exist at World
  scope, so the subtraction could never evaluate. The rebuild keeps the World assignment (the
  dashboard reads it on vSphere World) and sums `cpu|corecount_provisioned` over descendant
  hosts, which is what the formula was trying to say.
- **Deviation (name drift):** dashboard W6 `metric_name` was `License Waste Count`; the
  rebuild's W6 references this SM by its new name. No view uses this SM.
- Alternative shape considered: a per-host "wasted cores" SM (licensed minus physical) rolled
  up with `sum` at the World. Rejected for now to keep the two re-derived SMs minimal; it
  would be the better shape if Scott later wants a per-host waste view.

## CONFIRMED BY SCOTT 2026-08-26 (was: assumption)

Inherits the 16-core-minimum assumption. Also confirm the World-scope fix matches
what you meant (the source SM cannot have produced data as exported).
