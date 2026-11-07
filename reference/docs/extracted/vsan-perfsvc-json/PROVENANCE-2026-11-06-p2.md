# Provenance: captures added 2026-11-06 (P2, VM and disk joins, Ops targets)

Companion to `README.md`, `PROVENANCE-2026-11-06-evening.md` and
`PROVENANCE-2026-11-06-build2.md` in this folder (immutable once committed,
so this round gets its own file). Answers design Prerequisite P2 in
`knowledge/designs/vsanperf-mp-v2.md`.

## Sources

- **vCenter:** vcf-lab-vcenter-mgmt.int.sentania.net, VMware vCenter Server
  9.1.1.0100 build 25784172 (`about.instanceUuid`
  `4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e`), cluster `vcf-lab-mgmt-cl01`
  (`domain-c6004`, 5-host ESA). Raw HTTPS from Python `http.client`,
  release id `8.0.3.0`, headers `vmware-api-session-id` and
  `Accept-Encoding: gzip`. Two sessions, both logged out (`204`). Read-only:
  Login, Logout, `ServiceInstance` content GET, `CreateContainerView`,
  `DestroyView`, `RetrievePropertiesEx`, `ContinueRetrievePropertiesEx`,
  `QueryDisksForVsan`, `QueryVsanManagedDisks`, `VsanPerfQueryPerf`.
- **VCF Ops:** `devel`, VCF Operations 9.0.2.0, Suite API, `OpsToken` auth.
  Captured 2026-11-07 05:30 to 05:45 UTC.
- **Captured:** 2026-11-06 ~23:15 to 23:45 America/Chicago
  (2026-11-07 05:15 to 05:45 UTC).
- Files are the gunzipped server output, byte for byte, server
  pretty-printing kept. Ops bodies are as received (Ops sent no
  `Content-Encoding`, so wire = decoded).
- **Scanned:** every file checked for the vCenter session id, the Ops token
  and the string `password` before writing; none present. Bodies carry lab
  uuids, VM names, disk paths and device serials only.

## vCenter: VM inventory scoped to the cluster

Common request: `POST /sdk/vim25/8.0.3.0/ViewManager/ViewManager/CreateContainerView`
with `{"container":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"},"type":["VirtualMachine"],"recursive":true}`,
then `POST /sdk/vim25/8.0.3.0/PropertyCollector/propertyCollector/RetrievePropertiesEx` with

```json
{"specSet":[{"_typeName":"PropertyFilterSpec",
  "propSet":[{"_typeName":"PropertySpec","type":"VirtualMachine","pathSet":<paths>}],
  "objectSet":[{"_typeName":"ObjectSpec","obj":{"_typeName":"ManagedObjectReference","type":"ContainerView","value":"<view moId>"},"skip":true,
    "selectSet":[{"_typeName":"TraversalSpec","name":"v","type":"ContainerView","path":"view","skip":false}]}]}],
 "options":{"_typeName":"RetrieveOptions"<, "maxObjects":10>}}
```

Light paths = `["name","config.instanceUuid","runtime.host"]`; devices paths =
light + `"config.hardware.device"`. Continuation:
`POST .../PropertyCollector/propertyCollector/ContinueRetrievePropertiesEx`
with `{"token":"<token from the previous page>"}`.

| File | Request | Objects | token | Wire B | Decoded B | ms |
|---|---|---|---|---|---|---|
| `retrievepropertiesex-vm-cluster-light-2026-11-06.json` | light, no maxObjects | 42 | none | 4,307 | 51,322 | 9.8 (first) |
| `retrievepropertiesex-vm-cluster-light-max10-page1-2026-11-06.json` | light, maxObjects 10 | 10 | `"4"` | 1,204 | 12,315 | 9.3 |
| `retrievepropertiesex-vm-cluster-light-max10-page2-2026-11-06.json` | Continue `"4"` | 10 | `"5"` | 972 | 12,238 | 2.6 |
| `retrievepropertiesex-vm-cluster-light-max10-page3-2026-11-06.json` | Continue `"5"` | 10 | `"6"` | 1,225 | 12,328 | 2.1 |
| `retrievepropertiesex-vm-cluster-light-max10-page4-2026-11-06.json` | Continue `"6"` | 10 | `"7"` | 1,186 | 12,270 | 3.9 |
| `retrievepropertiesex-vm-cluster-light-max10-page5-2026-11-06.json` | Continue `"7"` | 2 | absent | 469 | 2,487 | 1.6 |
| `retrievepropertiesex-vm-cluster-devices-max10-page1-2026-11-06.json` | devices, maxObjects 10 | 10 | yes | 30,537 | 222,949 | 20.9 |
| `retrievepropertiesex-vm-cluster-devices-max10-page2-2026-11-06.json` | Continue | 10 | yes | 32,160 | 233,765 | 19.1 |
| `retrievepropertiesex-fault-stale-token-2026-11-06.json` | Continue with page 1's already-consumed token `"4"` | n/a (HTTP 500 `InvalidArgument`, `invalidProperty: token`) | | | 139 | |
| `retrievepropertiesex-fault-device-subpath-2026-11-06.json` | pathSet `["config.hardware.device.backing"]` | n/a (HTTP 500 `InvalidProperty`) | | | 85 | |

The light pages 1 to 5 are one complete chain. The devices chain ran to 5
pages (10, 10, 10, 10, 2 objects); pages 3 to 5 were not saved (30,162 /
40,653 / 8,626 B wire, 205,928 / 314,138 / 66,936 B decoded, 13.9 / 20.4 /
6.2 ms). The two devices pages are from a different chain than the light
pages, in the same session.

## vCenter: disk map for one host

- `querydisksforvsan-host-15151-2026-11-06.json`:
  `POST /sdk/vim25/8.0.3.0/HostVsanSystem/vsanSystem-15151/QueryDisksForVsan`,
  body `{}`, host `host-15151` (`vcf-lab-mgmt-esx04`), HTTP 200, 1,548 B
  wire, 7,734 B decoded, 10.8 ms. The vsanSystem moId came from the host's
  `configManager.vsanSystem` in a RetrievePropertiesEx read.
- `queryvsanmanageddisks-host-15151-2026-11-06.json`:
  `POST /sdk/vim25/8.0.3.0/vsan/VimClusterVsanVcDiskManagementSystem/vsan-disk-management-system/QueryVsanManagedDisks`,
  body `{"host":{"_typeName":"ManagedObjectReference","type":"HostSystem","value":"host-15151"}}`,
  HTTP 200, 860 B wire, 3,067 B decoded, 45.0 ms. Saved for the record.

## vCenter: ESA disk ids, same session

- `queryperf-vsan-esa-disk-layer-p2-2026-11-06.json`: `VsanPerfQueryPerf`,
  body `{"querySpecs":[{"_typeName":"VsanPerfQuerySpec","entityRefId":"vsan-esa-disk-layer:*","startTime":"2026-11-07T05:24:49Z","endTime":"2026-11-07T05:31:49Z","labels":["avgLatReadCapacity"]}],"cluster":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"}}`,
  HTTP 200, 463 B wire, 2,850 B decoded, 517 ms. 5 entities.

## VCF Ops devel: cluster and VM identifiers, push read-back

- `ops-devel-resources-clustercomputeresource-2026-11-06.json`:
  `GET /suite-api/api/resources?adapterKind=VMWARE&resourceKind=ClusterComputeResource&pageSize=100`,
  HTTP 200, 8,938 B, 167 ms, 3 clusters.
- `ops-devel-resources-virtualmachine-2026-11-06.json`:
  `GET /suite-api/api/resources?adapterKind=VMWARE&resourceKind=VirtualMachine&pageSize=500`,
  HTTP 200, 319,014 B, 1,357 ms, 109 VMs on one page (`totalCount` 109).
- Push (no file; the response has no body): `POST /suite-api/api/resources/stats`,
  HTTP 200, `Content-Length: 0`, 28 ms, body:

```json
{"resource-stat-content":[
 {"id":"d8b36417-e50a-4f42-84f7-ff0020501d55","stat-contents":[{"statKey":"VCFCF Test|Build2|clusterKey","timestamps":[1794029593951],"data":[42.0]}]},
 {"id":"0b2a707d-b2b7-414c-85a3-2d607a1bd9e9","stat-contents":[{"statKey":"VCFCF Test|Build2|vdisk:scsi0:0|probe","timestamps":[1794029593951],"data":[7.0]}]}]}
```

- `ops-devel-readback-virtualmachine-2026-11-06.json`:
  `GET /suite-api/api/resources/0b2a707d-b2b7-414c-85a3-2d607a1bd9e9/stats?statKey=VCFCF+Test%7CBuild2%7Cvdisk%3Ascsi0%3A0%7Cprobe&begin=1794029533951&end=1794029653951`.
  First read, ~42 s after the push (polling every 30 s after a reconnect;
  the first attempt to poll at +30 s failed on a dropped keep-alive
  connection, not on the stat), returned the sample.
- `ops-devel-readback-clustercomputeresource-2026-11-06.json`:
  `GET /suite-api/api/resources/d8b36417-e50a-4f42-84f7-ff0020501d55/stats?statKey=VCFCF+Test%7CBuild2%7CclusterKey&begin=1794029533951&end=1794029653951`.
  First returned the sample ~343 s after the push (the previous poll, ~30 s
  earlier, returned no sample).
- Afterwards `GET /suite-api/api/resources/{id}/statkeys` listed exactly one
  `VCFCF*` key on each resource (the pushed one).

- **Digest:** `knowledge/context/api-maps/vsan-performance-service.md`,
  section "P2: VM and disk joins over JSON, Ops cluster and VM targets
  (measured 2026-11-06)".
