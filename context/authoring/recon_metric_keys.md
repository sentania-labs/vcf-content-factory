# Live metric-key reconciliation

Findings from investigating why
`views/vm_perf_storage.yaml` (UUID `590b5c28-d38d-55c5-a51f-d447f68b4975`)
installed cleanly but rendered every column blank in the UI on
`vcfops.example.com`, 2026-04-08.

## TL;DR

- `cpu|*`, `mem|*`: bare keys are correct as documented. They have data.
- `virtualDisk|numberReadAveraged_average`,
  `virtualDisk|numberWriteAveraged_average`,
  `virtualDisk|totalReadLatency_average`,
  `virtualDisk|totalWriteLatency_average`: **registered but never populated
  at the bare-key level**. Data is only stored under per-disk instanced
  keys (`virtualDisk:scsi0:N|...`) plus a synthetic
  `virtualDisk:Aggregate of all instances|...` rollup.
- `/api/adapterkinds/VMWARE/resourcekinds/VirtualMachine/statkeys` is the
  **type-level registry** and lists only bare keys (929 entries, zero
  contain `:`). It cannot tell you whether a key is instance-resolved at
  runtime. **Treat `statkeys` as a hint, not as ground truth for views.**
- Ground truth = query an actual representative resource of that kind via
  `GET /api/resources/{id}/stats?begin=…&end=…` and read the
  `statKey.key` strings that come back.

## Task 1: live view diff

Specimen: `context/specimens/vm_perf_storage_live.xml` (extracted from a
`POST /api/content/operations/export {scope:CUSTOM, contentTypes:[VIEW_DEFINITIONS]}`
zip → `views.zip` → `content.xml`, the only path Ops offers for views).

Our 9 columns came back unchanged from what was uploaded. The user
appended a **10th** column manually in the Ops UI as a worked example:

| # | YAML attributeKey | Live attributeKey | Has data? |
|---|---|---|---|
| 1 | `cpu\|usage_average` | same | yes |
| 2 | `cpu\|readyPct` | same | yes |
| 3 | `mem\|usage_average` | same | yes |
| 4 | `mem\|balloonPct` | same | yes |
| 5 | `mem\|swapoutRate_average` | same | yes |
| 6 | `virtualDisk\|numberReadAveraged_average` | same | **no — instanced only** |
| 7 | `virtualDisk\|numberWriteAveraged_average` | same | **no — instanced only** |
| 8 | `virtualDisk\|totalReadLatency_average` | same | **no — instanced only** |
| 9 | `virtualDisk\|totalWriteLatency_average` | same | **no — instanced only** |
| 10 (UI) | n/a | `virtualDisk:Aggregate of all instances\|totalReadLatency_average` | yes |

The user's manual column is the smoking gun. The wire format for an
instanced metric in a view is exactly the colon form, used as
`attributeKey` directly — no separate "instance" property, no escaping.

## Task 2: ground-truth procedure

### Why `statkeys` lies

`GET /api/adapterkinds/VMWARE/resourcekinds/VirtualMachine/statkeys` on the
lab returns 929 attributes. Zero contain `:`. The endpoint enumerates
the **schema** the adapter advertises for the resource kind; it does not
know which schema entries are realized as bare timeseries vs. as
per-instance fanout. For VirtualMachine, the adapter populates:

- `cpu|*`, `mem|*`, `net|*`, `sys|*`, etc. → bare keys, single timeseries.
- `virtualDisk|read_average`, `virtualDisk|write_average` → bare keys
  (these are throughput-style rollups Ops itself maintains).
- All other `virtualDisk|*` → no bare timeseries. Data lives under
  `virtualDisk:scsi0:N|<metric>` (one per vDisk) plus a synthetic
  `virtualDisk:Aggregate of all instances|<metric>` rollup.
- `datastore|*`, `guestfilesystem|*`, `net|*`: same instancing pattern
  is likely to apply (verify per case).

Documentation files like `docs/vcf9/metrics-properties.md` describe
metrics by their **bare** key. They do not flag instancing. So docs
agree with `statkeys` but neither tells the truth about what to put in
a view.

### Recon recipe (use this before authoring views or super metrics that
reference `virtualDisk|*`, `datastore|*`, `net:*`, `guestfilesystem:*`,
or any other instanced metric family)

1. **Find representative resources of the target kind** that have actual
   data for the area you care about. For VMs:
   ```
   GET /api/resources?adapterKind=VMWARE&resourceKind=VirtualMachine&pageSize=50
   ```
   Filter to powered-on VMs that look like they exercise the subsystem
   (e.g. for storage metrics, prefer VMs with several vDisks).

2. **Pull the last hour of stats** for one or two of those resources:
   ```
   GET /api/resources/{id}/stats?begin=<now-3600000>&end=<now>
   ```
   The response contains `values[].stat-list.stat[].statKey.key` —
   collect into a set.

3. **Grep that set for the metric family you want.** If you only see
   `virtualDisk:<instance>|...`, the bare key is not usable in a view;
   you must pick one of:
   - `virtualDisk:Aggregate of all instances|<metric>` — single column,
     pre-rolled across all disks. **This is what list views should use
     unless the user explicitly wants per-disk fanout.**
   - `virtualDisk:scsi0:0|<metric>` — pinned to a specific disk; only
     useful if every VM in scope has the same disk layout, which is
     rare. Avoid in cross-VM views.

4. **Cross-check at least one second VM** to make sure the
   `Aggregate of all instances` rollup is actually present (it is for
   instanced families on VirtualMachine in the lab). For VMs that
   currently have no data at all (powered off, no recent samples) the
   stat list will be sparse — that's not a missing metric, it's a
   missing sample.

5. **Use the exact `statKey.key` string verbatim as `attributeKey`** in
   the view YAML / view XML. No transformation, no escaping. The colon
   is part of the key.

### The minimum reproducible commands

```python
from vcfops_supermetrics.client import VCFOpsClient
import time
c = VCFOpsClient.from_env(); c._ensure_auth()
end = int(time.time()*1000); begin = end - 3600*1000
vms = c._request('GET', '/api/resources',
    params={'adapterKind':'VMWARE','resourceKind':'VirtualMachine','pageSize':50}
).json()['resourceList']
for v in vms:
    j = c._request('GET', f"/api/resources/{v['identifier']}/stats",
                   params={'begin':begin,'end':end}).json()
    keys = {sl['statKey']['key']
            for s in j.get('values', [])
            for sl in s.get('stat-list', {}).get('stat', [])}
    if any('virtualDisk:' in k for k in keys):
        for k in sorted(k for k in keys if 'virtualDisk' in k):
            print(k)
        break
```

This is the canonical test. ops-recon should run an analogous probe
whenever an authoring brief involves an instanced-metric family.

## Corrected key list for the 9 view columns

```
cpu|usage_average                                              # OK
cpu|readyPct                                                   # OK
mem|usage_average                                              # OK
mem|balloonPct                                                 # OK
mem|swapoutRate_average                                        # OK
virtualDisk:Aggregate of all instances|numberReadAveraged_average     # was virtualDisk|numberReadAveraged_average
virtualDisk:Aggregate of all instances|numberWriteAveraged_average    # was virtualDisk|numberWriteAveraged_average
virtualDisk:Aggregate of all instances|totalReadLatency_average       # was virtualDisk|totalReadLatency_average
virtualDisk:Aggregate of all instances|totalWriteLatency_average      # was virtualDisk|totalWriteLatency_average
```

All five corrected keys verified present on lab VM
`0cd093f1-f684-46d0-95c5-1910c09ffa1a` (a 14-vDisk VM with active IO)
via `GET /api/resources/{id}/stats?begin=…&end=…`, 2026-04-08.

## Implications for the agent roster

- **ops-recon brief should always include a "list the live `statKey.key`
  values for these metrics on a representative resource" check** when
  the user's request mentions a virtualDisk, datastore, network
  interface, guest filesystem, or other instanced family. Add to
  `context/recon_*` checklist.
- **view-author must not trust `metrics-properties.md` alone** for
  instanced families. The doc-only path is what produced this bug.
- **Loader/packager needs no change.** The colon form passes through
  `attributeKey` untouched (verified — the user's UI-added column
  serializes exactly as `<Property name="attributeKey" value="virtualDisk:Aggregate of all instances|totalReadLatency_average"/>`).

## Cleanup

No mutations were made to the instance during this investigation. The
view itself was already installed by the user prior to handoff and was
left as-is for the user to overwrite via the corrected re-author. The
only API calls made were exports (`POST /api/content/operations/export`
+ GET zip), `GET /api/adapterkinds/.../statkeys`, `GET /api/resources`,
and `GET /api/resources/{id}/stats[/latest]`. All read-only or
self-cleaning.
