# Policy capacity allocation model: read and write wire format

Verified live 2026-11-20 on Aria Ops 8.18.7 (build 25423534), VCF Ops
9.0.2 (build 25431135) and VCF Ops 9.1.1 (build 25795063), by
`api-explorer`. The lab change this was proven with is recorded in
`knowledge/context/investigations/2026-11-20-allocation-model-enable/README.md`.

Public, supported endpoints (`reference/docs/operations-api*.json`,
`/api/policies/{id}/settings` GET / PATCH / DELETE). No `/internal/`
endpoint is needed to read or write this setting; the only internal call
used was `POST /internal/policies/effective/query` to find which policy
governs the clusters (unsupported: needs `X-Ops-API-use-unsupported: true`,
Broadcom may change it without notice).

## Find the policy that actually governs the clusters

Do not assume the policy flagged `defaultPolicy: true` is the one in
force. Ask:

```
POST /suite-api/internal/policies/effective/query
X-Ops-API-use-unsupported: true
{"resourceIds": ["<cluster uuid>", ...]}
-> 200 {"effectivePolicies": [{"policyId": "...", "resourceIds": [...]}]}
```

On all four lab instances every `ClusterComputeResource` resolved to the
single default policy (2026-11-20).

## Read

```
GET /suite-api/api/policies/{id}/settings
    ?type=CAPACITY_ALLOCATION_MODEL
    &adapterKind=VMWARE&resourceKind=ClusterComputeResource
    [&includeInherited=true]
```

- `type` is required. Omitting it: `400 {"message": "Query Parameter \"type\"
  is required.", "apiErrorCode": 1509}` (8.18.7, 9.0.2, 9.1.1). There is
  no "all settings" read; snapshot each type separately
  (`CAPACITY_ALLOCATION_MODEL`, `CAPACITY_CUSTOM_PROFILE`,
  `CAPACITY_BUFFER`, `TIME_REMAINING`, `CAPACITY_REMAINING`, `WORKLOAD`).
- Without `includeInherited` (default false) a policy that inherits
  returns an empty `capacityAllocationSettings: []`.
- With `includeInherited=true` the effective value comes back with an
  `inherited` flag. Unset state on all four instances (inherited from Base
  Settings):

```json
{"capacitySettings": {"capacity": {
  "capacityAllocationSettings": [{
    "capacityAllocation": {"poweredOffVmsConsidered": false},
    "inherited": true,
    "resourceKindKey": {"adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource"}}],
  "capacityBufferSettings": [], "customProfileSettings": []}}}
```

  No `cpu` / `memory` / `diskspace` key means that resource is not in the
  allocation model.

## Write (verified, identical on 8.18.7, 9.0.2, 9.1.1)

```
PATCH /suite-api/api/policies/{id}/settings
Content-Type: application/json

{"capacitySettings": {"capacity": {"capacityAllocationSettings": [{
  "resourceKindKey": {"adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource"},
  "capacityAllocation": {"cpu": 3, "poweredOffVmsConsidered": false}}]}}}

-> 204 No Content (empty body)
```

- **A CPU-only body is accepted.** `memory` and `diskspace` may be
  omitted; they stay unset (cluster properties stay -1.0, see below).
  Nothing else is required besides `resourceKindKey`.
- `poweredOffVmsConsidered` was sent explicitly as `false` (its inherited
  value) so the block is fully specified; omitting it was not tested.
- Ratio bounds: the 9.0 and 9.1 specs declare `minimum: 1, maximum: 99`
  on `cpu`, `memory`, `diskspace`; the 8.18 spec (Swagger 2) declares no
  bounds. Out-of-range values were not tested.
- `capacityAllocationSettings` is `maxItems: 1` in 9.x: one resource kind
  per call.
- Same body on all three versions; no per-version difference found.

Read-back with `includeInherited=true` after the write (all four):

```json
[{"capacityAllocation": {"cpu": 3.0, "poweredOffVmsConsidered": false},
  "inherited": false,
  "resourceKindKey": {"adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource"}}]
```

### What the write changes, seen through policy export

`GET /api/policies/export?id=<id>` (zip, `exportedPolicies.xml`; element
order is not stable between exports, so diff it order-insensitively).
The PATCH added exactly one block to the policy and changed nothing else
(order-insensitive leaf diff: 0 removed, 9 added, on every instance):

```xml
<PolicySettings adapterKind="VMWARE" resourceKind="ClusterComputeResource">
  <CapacityTimeRemainingSettings>
    <ApplicableResourceContainer enabled="true"  hidden="true"  overCommitThreshold="3.0" resourceContainerKey="cpu" subResourceContainerKey="alloc"/>
    <ApplicableResourceContainer enabled="false" hidden="true"  overCommitThreshold="1.0" resourceContainerKey="mem" subResourceContainerKey="alloc"/>
    <ApplicableResourceContainer enabled="false" hidden="true"  overCommitThreshold="1.0" resourceContainerKey="diskspace" subResourceContainerKey="alloc"/>
    <ApplicableResourceContainer enabled="true"  hidden="false" overCommitThreshold="1.0" resourceContainerKey="cpu|mem|diskspace" subResourceContainerKey="demand"/>  (one row each)
    <ApplicableResourceContainer enabled="true"  hidden="true"  overCommitThreshold="1.0" resourceContainerKey="cpu|mem|diskspace"/>  (one row each)
  </CapacityTimeRemainingSettings>
</PolicySettings>
```

(The last two lines are condensed; the export carries one element per
container, nine in all.) So the allocation model is stored as the
`alloc` sub-containers of `CapacityTimeRemainingSettings` (the describe
XSD calls this "how Capacity Remaining and Time Remaining are
calculated"), with the ratio in `overCommitThreshold`. The demand and
total rows are written out at their default values (enabled, 1.0) along
with it: the policy now holds the whole block locally rather than
inheriting it. INFERRED: the UI's allocation-model checkbox writes the
same block.

`GET /api/policies/export` on Base Settings returned 500 on 8.18.7, so the
inherited block could not be compared directly.

## Turning it back off

Not verified (the lab change was meant to stay). Two inferred routes:

1. `DELETE /api/policies/{id}/settings?type=CAPACITY_ALLOCATION_MODEL&adapterKind=VMWARE&resourceKind=ClusterComputeResource`
   ("Make provided settings in the policy inherited from parent policy",
   all three specs). On the four lab policies the pre-change state was
   "inherited, nothing local", so this is the exact rollback. It should
   also drop the local `CapacityTimeRemainingSettings` block; verify with
   an export diff.
2. A PATCH that omits `cpu` was not tested and is not known to clear it
   (PATCH is "update only provided settings", so an absent field likely
   means "leave alone"). Do not rely on it.

Also untested: whether a CPU-only PATCH clears a memory or disk ratio
that was already set locally.

## Where the result surfaces

On each `VMWARE:ClusterComputeResource` governed by the policy:

| Key | Kind | Unset | After cpu 3 | Lag observed |
|---|---|---|---|---|
| `System Properties|cpu|alloc|overcommitRatioSetting` | property | -1.0 | 3.0 | under 90 s on 8.18.7; about 30-70 s on 9.0.2 / 9.1.1 |
| `System Properties|mem|alloc|overcommitRatioSetting` | property | -1.0 | -1.0 (unchanged) | n/a |
| `System Properties|diskspace|alloc|overcommitRatioSetting` | property | -1.0 | -1.0 (unchanged) | n/a |
| `System Properties|considerPowerOffVMs` | property | false | false | n/a |
| `cpu|alloc|usableCapacity` | metric | absent | 72.0 (24 cores x 3) | first sample 2-6 min after the write, then every 5 min |
| `OnlineCapacityAnalytics|cpu|alloc|capacityRemaining`, `...|timeRemaining`, `...|recommendedSize` | metrics | absent | 0.0, 0.0, 29-48 (cluster is past 3:1) | same as above |
| `OnlineCapacityAnalytics|cpu|alloc|capacityRemainingPercentage` | metric | absent | still absent 15 min later | never seen |

Capacity analytics (`OnlineCapacityAnalytics|*`) publishes on a 5-minute
cycle (demand-family timestamps on 9.1.1 were 13:04, 13:05 CST).

### Per-container percent keys exist but did not populate

The statkey listing for ClusterComputeResource on 9.1.1 (devel_9_1, prod)
carries `OnlineCapacityAnalytics|{cpu,mem,diskspace}|{demand,alloc}|capacityRemainingPercentage`,
but on a cluster with fresh demand data none of the `demand` ones had a
value; only the roll-up `OnlineCapacityAnalytics|capacityRemainingPercentage`
did. The 10-month-old prod alloc data (when 4:1 was set) also has
`cpu|alloc|capacityRemaining` but no `cpu|alloc|capacityRemainingPercentage`.
Treat the per-container percent keys as describe-only until a live value
is seen; derive a percent from `capacityRemaining` and the usable capacity
instead (RULE-002).

## Computing a remaining percent yourself (verified 2026-11-20, read-only)

The pairs to divide, from the live ClusterComputeResource statkey listing.
Every key below is present with identical spelling and unit on 8.18.7
(devel_8_18), 9.0.2 (devel) and 9.1.1 (devel_9_1, prod), so super metrics
built on them are portable across all three.

| Model / resource | Remaining key | Usable key | Unit (both) |
|---|---|---|---|
| alloc CPU | `OnlineCapacityAnalytics|cpu|alloc|capacityRemaining` | `cpu|alloc|usableCapacity` | vCPUs |
| alloc memory | `OnlineCapacityAnalytics|mem|alloc|capacityRemaining` | `mem|alloc|usableCapacity` | KB |
| alloc disk | `OnlineCapacityAnalytics|diskspace|alloc|capacityRemaining` | `diskspace|alloc|usableCapacity` | GB |
| demand CPU | `OnlineCapacityAnalytics|cpu|demand|capacityRemaining` | `cpu|demand|usableCapacity` | MHz |
| demand memory | `OnlineCapacityAnalytics|mem|demand|capacityRemaining` | `mem|demand|usableCapacity` | KB |
| demand disk | `OnlineCapacityAnalytics|diskspace|demand|capacityRemaining` | `diskspace|demand|usableCapacity` | GB |

Usable keys are named "<Resource>|<Model>|Usable Capacity after HA and
Buffer". `cpu|usable_capacity` and `mem|usable_capacity` do not exist on
any version; `diskspace|usable_capacity` (GB) exists on 9.0.2 and 9.1.1
but NOT on 8.18.7, so do not use it. Alloc memory and disk keys exist but
carry no value while their ratio is unset (only CPU is set in the lab).

Live values, 9.1.1, read 13:19-13:20 CST:

| Instance / cluster | cpu alloc rem / usable | cpu demand rem / usable (MHz) | overall `capacityRemainingPercentage` | overall `timeRemaining` (days) | cpu alloc / demand `timeRemaining` |
|---|---|---|---|---|---|
| devel_9_1 `vcf-lab-wld01-cl01` | 0 / 72 (0%) | 728.0 / 59904 (1.2%) | 0.0 | 0 | 0 / 366 |
| devel_9_1 `vcf-lab-mgmt-cl01` | 31 / 192 (16.1%) | 18655.6 / 159700.0 (11.68%) | 11.6817 | 27 | 366 / 27 |
| prod `vcf-lab-wld01-cl01` | 0 / 72 (0%) | 6988.4 / 59904 (11.7%) | 0.0 | 0 | 0 / 366 |
| prod `vcf-lab-mgmt-cl01` | 33 / 192 (17.1875%) | 34815.2 / 159700.0 (21.8%) | 17.1875 | 366 | 366 / 366 |

What this shows:

- The overall `OnlineCapacityAnalytics|capacityRemainingPercentage` is the
  minimum of remaining / usable x 100 across every enabled container
  (cpu, mem, disk; demand and alloc). It matched to four decimals:
  prod mgmt 33/192 = 17.1875 (alloc CPU won), devel_9_1 mgmt
  18655.6/159700 = 11.68 (demand CPU won). Memory and disk demand were
  looser (36-41%). So remaining / usable x 100 is the engine's own percent
  formula, and the overall key now does reflect allocation whenever
  allocation is the tighter constraint.
- Before the policy change, devel_9_1 wld01 overall read 1.105 (13:04) =
  demand CPU; after it reads 0.0 = alloc CPU. Overall `timeRemaining` also
  follows the most constraining container (0 on wld01 = alloc;
  27 on devel_9_1 mgmt = demand CPU).
- Alloc remaining floors at 0, never negative: wld01 has 84 vCPUs allocated
  (`cpu|vcpus_allocated_on_all_vms`) against 72 usable. It is also not
  simply usable minus allocated (mgmt: 192 - 166 = 26, engine says 31 and
  33); treat it as the engine's figure.
- Demand values differ between instances watching the same hosts (prod
  wld01 11.7% vs devel_9_1 1.2%): each instance runs its own analytics
  over its own history.
