# 2026-11-20: CPU allocation model 3:1 enabled on all four lab instances

Lab state change, owner-approved. Approval, in the repo owner's words
(2026-11-20): "set it 3:1 in all instances. they all monitor the same
hosts". Applied by `api-explorer` at 13:05-13:08 CST. Wire format:
`knowledge/context/api-surface/policy_capacity_allocation_model.md`.

## What changed

One setting per instance: the capacity allocation model for
`VMWARE:ClusterComputeResource`, CPU ratio unset (inherited from Base
Settings, no ratio) to **3** (3:1). Memory and disk space left unset.
`poweredOffVmsConsidered` stays `false` (was inherited, now held locally
at the same value). Every cluster on each instance is governed by the
policy written (confirmed with `/internal/policies/effective/query`
just before the write).

| Instance | Version | Policy written | Time (CST) | PATCH | Read-back |
|---|---|---|---|---|---|
| devel_8_18 | 8.18.7 | vSphere Solution's Default Policy (Oct 15, 2026 10:32:47 AM) `5df3a83d-8fc3-4afd-ad43-9f330fabd615` | 13:05:05 | 204 | cpu 3.0, inherited false |
| devel | 9.0.2 | vSphere Solution's Default Policy (Apr 17, 2026 3:50:38 PM) `9c1d42be-09b7-4149-92fc-2224e3d778bd` | 13:06:41 | 204 | cpu 3.0, inherited false |
| devel_9_1 | 9.1.1 | Default Policy `ccbcafb4-d61e-4bf3-bea2-3de1f54fce70` | 13:06:58 | 204 | cpu 3.0, inherited false |
| prod | 9.1.1 | Default Policy `e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd` | 13:07:24 | 204 | cpu 3.0, inherited false |

Body sent (identical everywhere):

```json
{"capacitySettings": {"capacity": {"capacityAllocationSettings": [{
  "resourceKindKey": {"adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource"},
  "capacityAllocation": {"cpu": 3, "poweredOffVmsConsidered": false}}]}}}
```

## Nothing else changed

- `before-<instance>.json` / `after-<instance>.json`: every capacity
  settings type for VMWARE/ClusterComputeResource, with and without
  `includeInherited`. Diff on every instance: only the CPU ratio
  appeared, and the allocation block went from inherited to local
  (`poweredOffVmsConsidered` false either way). Buffer, custom profile,
  time-remaining, capacity-remaining and workload thresholds unchanged
  (all still inherited). Policy summary (name, parent, default flag)
  unchanged.
- Whole-policy export before and after, diffed order-insensitively:
  0 elements removed, 9 added, all inside one new
  `PolicySettings VMWARE/ClusterComputeResource > CapacityTimeRemainingSettings`
  block (cpu alloc enabled at 3.0; mem/disk alloc disabled; demand and
  total rows at defaults). Metrics, alerts, symptoms untouched. The
  exports are bulky and kept off the repo at
  `/mnt/holding/vcf-content-factory/2026-11-20-allocation-model-enable/`
  (`before-` / `after-<instance>-policy-export.zip`).

## Rollback

Every policy had no local capacity settings before. Rollback per
instance (inferred, not run):

```
DELETE /suite-api/api/policies/<policyId>/settings?type=CAPACITY_ALLOCATION_MODEL&adapterKind=VMWARE&resourceKind=ClusterComputeResource
```

then confirm `includeInherited=true` shows `inherited: true` with no
`cpu`, and that the cluster property returns to -1.0. If the delete does
not restore it, `before-<instance>.json` is the target state and the
before-export zip is importable through `POST /api/policies/import`.

## Effect observed

`System Properties|cpu|alloc|overcommitRatioSetting` on
`vcf-lab-wld01-cl01` read 3.0 on all four instances by 13:07:51
(-1.0 before); mem and disk ratio properties stayed -1.0.
Alloc metrics on `vcf-lab-wld01-cl01` (24 cores), first sample and
value, unchanged through 13:21:

| Instance | First seen (CST) | `cpu|alloc|usableCapacity` | `...cpu|alloc|capacityRemaining` | `...cpu|alloc|timeRemaining` | `...cpu|alloc|recommendedSize` |
|---|---|---|---|---|---|
| devel_8_18 | 13:11 | 72.0 | 0.0 | 0.0 | 29.0 |
| devel | 13:08 | 72.0 | 0.0 | 0.0 | 31.0 |
| devel_9_1 | 13:09 | 72.0 | 0.0 | 0.0 | 48.0 |
| prod | 13:10 | 72.0 | 0.0 | 0.0 | 48.0 |

At 3:1 this cluster has no CPU allocation headroom left (remaining 0,
time remaining 0). `OnlineCapacityAnalytics|cpu|alloc|capacityRemainingPercentage`
did not populate on any instance. recommendedSize differs across
instances watching the same hosts (29 / 31 / 48); not investigated.
