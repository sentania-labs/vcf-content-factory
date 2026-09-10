# Host VCF Licensed Cores (16-core minimum)

- **Type:** supermetric
- **Slug:** vcf-license-host-licensed-cores
- **Authored YAML:** supermetrics/vcf_license_host_licensed_cores.yaml
- **Date:** 2026-08-26
- **Status:** drafted

## Initial prompt

> Can you review it and rebuild it it as a native VCF Conctent facory dashboard targetting VCF Operations 8.x? I believe there are some missing supermetrics and the like.

Source: https://github.com/sentania/AriaOperationsContent/tree/main/VCF%20License%20Consumption%20Overview
(Scott's public community content, "VCF Consumption Overview v2"). Inventory:
`knowledge/context/investigations/2026-08-26-vcf-license-consumption-inventory.md`.
8.18 recon: `knowledge/context/investigations/2026-08-26-vcf-license-consumption-recon-818.md`.

## Vision

- Per-host number of VCF license cores the host consumes under per-core licensing with the
  16-core-per-socket minimum. A 2-socket, 8-core-per-socket host counts as 32, not 16.
- Upstream for NSX License Count, Automation License Count and (via the World roll-up)
  VCF License Potential Cores. Not shown directly on the dashboard.
- This SM replaces the dangling `sm_5ea91f64` reference; it is a re-derivation, not a recovery.

## Spec

**Name:** `[VCF Content Factory] Host VCF Licensed Cores (16-core minimum)` (RULE-006 prefix, literal brackets, one space).
Source name: `(missing from export: Super Metric|sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322, name unknown)`.

**Assignment (adapter kind / resource kind):**
- `VMWARE / HostSystem`

**Unit:** `(none)`

**Source formula (verbatim):**

```
(not available; referenced only by UUID from NSX License Count and Automation License Count)
```

**Rebuild formula:**

```
(${this, metric=hardware|cpuInfo|numCpuCores} / ${this, metric=hardware|cpuInfo|numCpuPackages}) < 16
  ? 16 * ${this, metric=hardware|cpuInfo|numCpuPackages}
  : ${this, metric=hardware|cpuInfo|numCpuCores}
```

**Raw keys used (8.18 recon status):**
- `HostSystem` `hardware|cpuInfo|numCpuCores` (property): in vendor docs, **not 8.18-verified**
- `HostSystem` `hardware|cpuInfo|numCpuPackages` (property): in vendor docs, **not 8.18-verified**
- fallback `HostSystem` `cpu|corecount_provisioned` (metric): 8.18-verified, 56.0 on ro818
- fallback `HostSystem` `cpu|numpackages` (metric, vendor docs): not 8.18-verified

**Dependencies (must be authored and policy-enabled first):**
- none

### Notes

- Assigned to HostSystem only. Consumers walk to it with `depth=10` from NSXT World, CAS World
  and vSphere World; each of those adapters' worlds must actually relate to the vCenter hosts
  (the source relied on that for NSX and Automation, and it is how the source got a per-world
  subset of hosts).
- Should be enabled in the same policy as its three consumers.

## CONFIRMED BY SCOTT 2026-08-26 (was: assumption)

`sm_5ea91f64-b7e9-4a77-baa7-1e8ebea1e322` is not in the export and 404s on both recon
instances. It is re-derived from what its consumers expect:

- `NSX License Count` and `Automation License Count` both do
  `sum(${adaptertype=VMWARE, objecttype=HostSystem, metric=Super Metric|sm_5ea91f64..., depth=10})`
  and their dashboard labels are "NSX Licensed Cores" / "Automation License Consumption".
  So the missing SM is **per HostSystem**, unit **cores**, and its value is the number of
  license cores that host consumes (not a count, not a percent).
- `VCF License Potential Cores` (via `sm_3b4464fc`) subtracts physical provisioned cores from
  it and its source description says: "The number of core licences wasted due to system with
  core count smaller then 16 per socket". So the per-host value is **physical cores rounded up
  to the VCF per-CPU minimum of 16 cores per socket**.

Licensing assumption used: **VCF is licensed per physical core with a 16-core minimum per CPU
(socket): `licensed cores = max(16, cores per socket) * sockets`.** No cap per socket is
applied (Broadcom's per-core model has a minimum, not a maximum). Hyperthreads are not counted.

Keys: `hardware|cpuInfo|numCpuCores` (total physical cores) and
`hardware|cpuInfo|numCpuPackages` (sockets) are HostSystem properties in the vendor property
tables (`reference/docs/vcf9/metrics-properties.md` Table 1393). **Neither was checked on
8.18 by the recon** (only `cpu|corecount_provisioned` and `config|name` were). Alternates if
they are absent on 8.18: `cpu|corecount_provisioned` (verified, 56.0 on ro818) for total cores
and `cpu|numpackages` for sockets. `ops-recon` must confirm the two chosen keys on ro818
before `supermetric-author` spawns.

Scott, please confirm: (a) the 16-core-per-socket minimum is the rule you intended in the
original `sm_5ea91f64`; (b) there is no additional rounding you applied (e.g. per-cluster,
or rounding to license-pack sizes); (c) whether the same per-host number should drive both
the NSX and Automation counts (the source did that) or whether Automation should use a
different denominator.

Formula-shape assumption: the DSL skill lists `max` only as a looping function, so the
rebuild uses the ternary operator instead of a scalar `max(16, x)`. If the ternary does not
validate against `${this,...}` operands on 8.18, the fallback is two SMs
(`16 * sockets` and `cores`) combined with `max([...])` array form; report as TOOLSET GAP
if neither works.
