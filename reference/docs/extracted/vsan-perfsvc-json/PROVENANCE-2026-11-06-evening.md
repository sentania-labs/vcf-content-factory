# Provenance: captures added 2026-11-06 (evening)

Companion to `README.md` in this folder (which is immutable under RULE-010 once
committed, so later captures get their own provenance file).
## Added 2026-11-06 (evening): Build 1 entity types, node information, inventory read

Same source vCenter, same session conventions (headers `vmware-api-session-id`,
`Accept-Encoding: gzip`; the bodies below are the gunzipped server output, byte
for byte, server pretty-printing kept). Release id in the path: `8.0.3.0`.
Cluster MoRef in every vSAN call:
`{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"}`.
Perf window for files 3 to 5: `startTime` `2026-11-07T02:28:26Z`, `endTime`
`2026-11-07T02:35:26Z` (7 min, UTC), one wildcard spec per call, `labels` = the
Build 1 list for the type in `knowledge/designs/vsanperf-mp-v1.md`
§"Build 1 metric list" (6 / 38 / 17 labels).

3. `queryperf-host-domclient-2026-11-06.json` (10,777 B; 918 B gzip on the wire):
   `POST /sdk/vim25/8.0.3.0/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`,
   spec `{"_typeName":"VsanPerfQuerySpec","entityRefId":"host-domclient:*",...,"labels":[6]}`.
   5 entities, 30 series.
4. `queryperf-host-domowner-2026-11-06.json` (64,463 B; 4,475 B wire): same,
   `entityRefId` `host-domowner:*`, 38 labels. 5 entities, 190 series.
5. `queryperf-vsan-pnic-net-2026-11-06.json` (56,337 B; 3,737 B wire): same,
   `entityRefId` `vsan-pnic-net:*`, 17 labels. 10 entities, 170 series.
6. `querynodeinformation-2026-11-06.json` (2,207 B; 468 B wire):
   `POST /sdk/vim25/8.0.3.0/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryNodeInformation`,
   body `{"cluster":<MoRef above>}`.
7. `retrievepropertiesex-cluster-hosts-2026-11-06.json` (9,821 B; 908 B wire):
   `POST /sdk/vim25/8.0.3.0/PropertyCollector/propertyCollector/RetrievePropertiesEx`,
   one `PropertyFilterSpec` over a ContainerView of `ClusterComputeResource`
   (root `group-d1`, recursive), traversal `ContainerView.view` then
   `ComputeResource.host`; cluster paths `name`, `host`; host paths `name`,
   `config.vsanHostConfig.enabled`, `config.vsanHostConfig.clusterInfo.uuid`,
   `config.vsanHostConfig.clusterInfo.nodeUuid`. Exact request in the digest.
8. `retrievepropertiesex-fault-invalidproperty-2026-11-06.json` (93 B): the
   HTTP 500 body for the same call with cluster pathSet
   `["name","configurationEx.vsanConfigInfo.enabled"]` (`InvalidProperty`).

- **Captured:** 2026-11-06 (America/Chicago; 2026-11-07 ~02:35 UTC), vCenter
  9.1.1.0100 build 25784172, read-only (queries, view create/destroy, login/logout).
- **Scanned:** no credential or session id in any file. The ContainerView moId
  (which embeds the vpxd session key) appears only in requests, never in these
  responses.
- **Digest:** `knowledge/context/api-maps/vsan-performance-service.md`, section
  "vim25 inventory over JSON (measured 2026-11-06)".
