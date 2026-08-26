# vSphere World VCF Licensed Cores

- **Type:** supermetric
- **Slug:** vcf-license-vsphere-world-licensed-cores
- **Authored YAML:** supermetrics/vcf_license_vsphere_world_licensed_cores.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Whole-environment count of VCF license cores the hosts would consume under the 16-core
  minimum rule, rolled up to vSphere World.
- Exists only to feed VCF License Potential Cores (`this` on vSphere World). Not on the
  dashboard directly.

## Spec

**Name:** `[VCF Content Factory] vSphere World VCF Licensed Cores` (RULE-006 prefix, literal brackets, one space).
Source name: `(missing from export: Super Metric|sm_3b4464fc-5dbc-4344-ba8e-e243818df6c6, name unknown)`.

**Assignment (adapter kind / resource kind):**
- `VMWARE / vSphere World`

**Unit:** `(none)`

**Source formula (verbatim):**

```
(not available; referenced only by UUID from VCF License Potential Cores as ${this, metric=Super Metric|sm_3b4464fc...} on vSphere World)
```

**Rebuild formula:**

```
sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|@supermetric:"[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)", depth=10})
```

**Raw keys used (8.18 recon status):**
- none directly; sums the per-host SM (`hardware|cpuInfo|numCpuCores` / `numCpuPackages`,
  see `vcf-license-host-licensed-cores.md`)

**Dependencies (must be authored and policy-enabled first):**
- `[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)`

### Notes

- Re-derivation: the consumer reads it as `${this, ...}` on vSphere World and subtracts a core
  count, so this must be a World-scoped core total. Sum of the per-host SM is the only
  reading consistent with the source description ("wasted due to ... smaller then 16 per socket").
- `depth=10` walks vSphere World > vCenter > Datacenter > Cluster > Host (and standalone hosts).

## CONFIRMED BY SCOTT 2026-08-26 (was: assumption)

Same licensing assumption as `vcf-license-host-licensed-cores.md` (16-core-per-socket
minimum, no cap). Scott: confirm this World total is what `sm_3b4464fc` computed, or whether
it was something else (e.g. only hosts under VCF-licensed clusters).
