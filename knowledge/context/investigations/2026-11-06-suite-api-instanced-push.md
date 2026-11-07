# Suite API stats push onto a vCenter HostSystem: instanced and undeclared keys

**Question:** can a Tier 2 adapter push instanced, undeclared stat keys onto
VMWARE HostSystem objects through the Suite API, and do they land and read
back? Feeds `2026-11-06-vsanhostmetrics-scale-plan.md` §2.

**Date / instance:** 2026-11-06 (UTC 2026-11-07 00:10-00:20), `devel`, VCF Ops
9.0.2; server clock matched local to the second.
Endpoints are in the supported public spec (`operations-api.json`:
`addStats`, `addStatsForResources`, `getStatsOfResource`); none in
`internal-api.json`. No `X-Ops-API-use-unsupported` header.
Wire shapes and batch semantics: `knowledge/context/api-surface/suite_api_batch_push.md`.

## Verdict

**Instanced keys: yes.** `Group|sub:instance|metric` and `group:instance|metric`
both accept, store and read back, one stat key per instance. **Undeclared
keys: yes.** Ops registers them on the resource on first push, no describe
entry needed. **Declare in describe.xml: not possible as designed, and not
needed for data to land.** The metadata the UI uses for labels and units
comes from the resource's own adapter kind (`VMWARE`); our keys are absent
from `/api/adapterkinds/VMWARE/resourcekinds/HostSystem/statkeys` after the
push, and an SDK pak's describe.xml declares its own adapter kind, not
VMWARE's. Plan on raw key segments as labels and no unit (UI rendering
not seen, see Visual), and put the unit in the metric name if it matters
(`latencyAvgWriteUs`). Read-back lags the 200 by 1 to 4 minutes; a
collect-cycle self-check must not treat "not yet readable" as failure.

## Target

`vcf-lab-wld01-esx01.int.sentania.net`, `1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6`
(VMWARE / HostSystem). Baseline: 412 stat keys, none `VCFCF*`.

## Requests that worked

Per-id, `POST /suite-api/api/resources/{id}/stats` (auth
`Authorization: OpsToken <token>`, JSON). Push 1, three points at 5 minute
spacing ending now (`ts = [now-600000, now-300000, now]`,
now = 1794010253106):

```json
{"stat-content":[
 {"statKey":"VCFCF Test|pNIC:vmnic0|rxDrops","timestamps":[ts],"data":[1.0,2.0,3.0]},
 {"statKey":"VCFCF Test|pNIC:vmnic1|rxDrops","timestamps":[ts],"data":[10.0,20.0,30.0]},
 {"statKey":"VCFCF Test|DOM Owner|latencyAvgWrite","timestamps":[ts],"data":[0.5,0.6,0.7]},
 {"statKey":"VCFCFTestNic:vmnic0|rxDrops","timestamps":[ts],"data":[4.0,5.0,6.0]},
 {"statKey":"VCFCFTestNic:vmnic1|rxDrops","timestamps":[ts],"data":[40.0,50.0,60.0]}]}
```

Push 2 (t = now-120000 = 1794010226765, value 7.0): `VCFCF Test|DOM Owner|latencyAvgWrite`,
`VCFCF Test|DOMOwner|latencyAvgWrite`, `VCFCF Test|latencyAvgWrite`,
`VCFCF Test|pNIC:vmnic0|rxDrops`. Push 3 (t = now = 1794010407382, value
8.0): `VCFCF Test|DOM Owner|latencyAvgWrite`, `VCFCF Test|latencyAvgWrite`,
`VCFCFTestFlat|latencyAvgWrite`.

Batch, `POST /suite-api/api/resources/stats`, same host, one request
(t = 1794010633659, value 9.0):

```json
{"resource-stat-content":[{"id":"1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6","stat-contents":[
 {"statKey":"VCFCF Test|pNIC:vmnic0|rxDrops","timestamps":[t],"data":[9.0]},
 {"statKey":"VCFCF Test|pNIC:vmnic1|rxDrops","timestamps":[t],"data":[9.0]},
 {"statKey":"VCFCF Test|DOM Owner|latencyAvgWrite","timestamps":[t],"data":[9.0]}]}]}
```

**Responses:** every push, per-id and batch, returned `200`, `Content-Length: 0`,
no body. Same shape for both; no per-key or per-resource acknowledgement.

## Read-back

`GET /suite-api/api/resources/{id}/stats?statKey=<key>&begin=<ms>&end=<ms>`
with no rollup params returns raw samples. `rollUpType=NONE` alone was a
400, as was `intervalType` without `rollUpType`; omit both.

Final state, ~5 minutes after the last push:

| Key | Timestamps landed | Data |
|---|---|---|
| `VCFCF Test\|pNIC:vmnic0\|rxDrops` | 653106, 953106, 226765, 253106, 633659 | 1, 2, 7, 3, 9 |
| `VCFCF Test\|pNIC:vmnic1\|rxDrops` | 653106, 953106, 253106, 633659 | 10, 20, 30, 9 |
| `VCFCF Test\|DOM Owner\|latencyAvgWrite` | all six pushed | 0.5, 0.6000000238418579, 7, 0.699999988079071, 8, 9 |
| `VCFCFTestNic:vmnic0\|rxDrops`, `…vmnic1…` | all three | 4,5,6 / 40,50,60 |
| `VCFCF Test\|latencyAvgWrite` | 226765, 407382 | 7, 8 |
| `VCFCF Test\|DOMOwner\|latencyAvgWrite` | 226765 | 7 |
| `VCFCFTestFlat\|latencyAvgWrite` | 407382 | 8 |
(timestamps: last six digits of 179400/179401xxxxxxx)

Findings:

- **Timestamps:** all three 5-minute-spaced points landed. A point 2 minutes
  in the past landed, **including when it was older than the newest
  stored sample** for that key (vmnic0: 226765 stored between 953106
  and 253106). Back-filling a lagging Performance Service sample is safe.
- **Lag:** read-back after a 200 took from under 60 s (pNIC keys, push 1)
  to over 3 minutes (`DOM Owner` key, push 1; `VCFCFTestFlat`, push 3).
  The first `DOM Owner` read returned `{"values":[]}` while the key was
  already listed in `/statkeys`; it was lag, not rejection.
- **Precision:** values are stored as float32 (0.6 reads back as
  0.6000000238418579).
- No key shape was rejected: spaces in segments, nested instance
  (`Group|sub:inst|m`), top-level instance (`grp:inst|m`), 2/3-segment flat keys.

## statkeys and attribution

- `GET /api/resources/{id}/statkeys` and `GET /api/resources/statkeys?resourceId=`
  list all eight test keys right after the push. Entries are bare
  `{"key": ...}`: no name, unit, adapter kind or source.
- `GET /api/adapterkinds/VMWARE/resourcekinds/HostSystem/statkeys`
  (812 declared attributes, each with name, unit, `instanceType`) does
  **not** include any pushed key. So no label, no unit, no
  `instanceType`.
- Attribution: no API surface shows which adapter a pushed key belongs to.
  The `addStats` doc says pushed data is attributed to the
  `vRealizeOpsMgrAPI` adapter instance by default (doc text, not observed).
- Baseline note: this host has no per-NIC vCenter keys (`net:vmnic0|…`);
  its only instanced groups are `net|disk|datastore|storageAdapter:Aggregate
  of all instances`. The devel policy has per-instance metrics off, so the
  "renders like `net:vmnic0`" comparison has no native reference here.
  Pushed instanced keys were stored regardless of that policy setting.

## Visual

VISUAL VERIFICATION: SKIPPED (no Playwright MCP tools in this session).
Open for a browser pass: does the Metrics tab tree show
`VCFCF Test > pNIC > vmnic0/vmnic1` or the raw `pNIC:vmnic0` segment; does
the instance-metrics policy setting hide pushed instanced keys in the UI
(they are stored, see above); what label does an undeclared leaf get.
Open `vcf-lab-wld01-esx01` on devel, Metrics tab, groups below.

## What remains on devel

No per-key stat delete exists in the Suite API; data ages out with
retention. Resource `1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6`
(`vcf-lab-wld01-esx01`) carries eight test keys:
`VCFCF Test|pNIC:vmnic0|rxDrops`, `VCFCF Test|pNIC:vmnic1|rxDrops`,
`VCFCF Test|DOM Owner|latencyAvgWrite`, `VCFCF Test|DOMOwner|latencyAvgWrite`,
`VCFCF Test|latencyAvgWrite`, `VCFCFTestNic:vmnic0|rxDrops`,
`VCFCFTestNic:vmnic1|rxDrops`, `VCFCFTestFlat|latencyAvgWrite`.
Nothing else was changed.

## Implications for the adapter design (§2)

- The "declare groups in describe.xml under the foreign kind" line in the
  scale plan §2 does not hold: pushed keys get no metadata from any describe.
  Treat units and labels as unavailable unless a browser pass shows otherwise.
- Use the batch endpoint (identical for one host). Its silent 200 means
  landing proof must come from a delayed read.
- Instance naming: both placements work. `Group|pNIC:vmnic0|metric` keeps
  everything under one `vSAN Perf` root, which is what the design wants.
