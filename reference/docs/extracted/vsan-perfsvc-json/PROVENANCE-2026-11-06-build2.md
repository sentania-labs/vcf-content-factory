# Provenance: captures added 2026-11-06 (Build 2 entity types)

Companion to `README.md` and `PROVENANCE-2026-11-06-evening.md` in this folder
(both immutable under RULE-010 once committed, so this round gets its own file).

## Added 2026-11-06 (late evening): Build 2 entity types

Same source vCenter and conventions as the evening round: raw HTTPS from
Python `http.client`, headers `vmware-api-session-id` and
`Accept-Encoding: gzip`, one session for the whole round (login, 30 queries,
join-key reads, logout `204`). The files are the gunzipped server output,
byte for byte, server pretty-printing kept. Release id in the path: `8.0.3.0`.

- **Endpoint:** `POST /sdk/vim25/8.0.3.0/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`
- **Body:** `{"querySpecs":[{"_typeName":"VsanPerfQuerySpec","entityRefId":"<type>:*","startTime":"2026-11-07T05:01:41Z","endTime":"2026-11-07T05:08:41Z","labels":[...]}],"cluster":{"_typeName":"ManagedObjectReference","type":"ClusterComputeResource","value":"domain-c6004"}}`
- **Window:** 7 min, UTC, the same for every call.
- **Labels:** exactly the Python pack's `metric_scope.COVERED` labels for the
  type's kind (kind per `perfsvc_model.ENTITIES`, or `perfsvc_model_extra.ENTITIES`
  for the 8 kinds the live model does not carry). Counts are in the table.
- **Order:** serial, the table order below.

One wildcard spec per call. Every call returned HTTP 200. "Empty" means the
response was the wildcard echo only, e.g. `[{"_typeName":"VsanPerfEntityMetricCSV","entityRefId":"cache-disk:*","sampleInfo":""}]`
(no `value` key). Empty types have no file.

| # | Type | Labels sent | Entities | Series | Wire B | Decoded B | ms | File |
|---|---|---|---|---|---|---|---|---|
| 1 | `cache-disk` | 8 | 0 (empty) | 0 | 119 | 129 | 153.1 | none |
| 2 | `capacity-disk` | 13 | 0 (empty) | 0 | 121 | 132 | 117.8 | none |
| 3 | `vsan-cluster-capacity` | 5 | 1 | 5 | 416 | 1,917 | 138.6 | `queryperf-vsan-cluster-capacity-2026-11-06.json` |
| 4 | `cluster-domclient` | 11 | 1 | 11 | 453 | 3,800 | 216.3 | `queryperf-cluster-domclient-labels-2026-11-06.json` (see note) |
| 5 | `cluster-domcompmgr` | 12 | 1 | 12 | 443 | 4,100 | 166.7 | `queryperf-cluster-domcompmgr-2026-11-06.json` |
| 6 | `cluster-domowner` | 23 | 1 | 23 | 696 | 7,739 | 195.7 | `queryperf-cluster-domowner-2026-11-06.json` |
| 7 | `cluster-esa-dedup-domclient-io` | 24 | 1 | 24 | 588 | 8,201 | 144.8 | `queryperf-cluster-esa-dedup-domclient-io-2026-11-06.json` |
| 8 | `cluster-rdt-network-latency` | 9 | 1 | 9 | 435 | 3,160 | 124.7 | `queryperf-cluster-rdt-network-latency-2026-11-06.json` |
| 9 | `cluster-zdom-top-stats` | 7 | 1 | 7 | 404 | 2,525 | 121.1 | `queryperf-cluster-zdom-top-stats-2026-11-06.json` |
| 10 | `cmmds-net` | 10 | 5 | 50 | 1,178 | 17,293 | 140.2 | `queryperf-cmmds-net-2026-11-06.json` |
| 11 | `vsan-cpu` | 7 | 5 | 35 | 872 | 12,188 | 120.4 | `queryperf-vsan-cpu-2026-11-06.json` |
| 12 | `vsan-direct-cluster` | 8 | 0 (empty) | 0 | 127 | 138 | 119.4 | none |
| 13 | `vsan-direct-host` | 8 | 0 (empty) | 0 | 124 | 135 | 129.5 | none |
| 14 | `vsan-esa-disk-layer` | 5 | 5 | 25 | 920 | 9,417 | 126.9 | `queryperf-vsan-esa-disk-layer-2026-11-06.json` |
| 15 | `vsan-esa-disk-scsifw` | 5 | 5 | 25 | 766 | 9,316 | 232.9 | `queryperf-vsan-esa-disk-scsifw-2026-11-06.json` |
| 16 | `vsan-file-service` | 8 | 0 (empty) | 0 | 125 | 136 | 138.0 | none |
| 17 | `host-domcompmgr` | 16 | 5 | 80 | 2,510 | 27,671 | 127.3 | `queryperf-host-domcompmgr-2026-11-06.json` |
| 18 | `host-esa-dedup-domclient-io` | 24 | 5 | 120 | 2,526 | 40,919 | 122.4 | `queryperf-host-esa-dedup-domclient-io-2026-11-06.json` |
| 19 | `vsan-host-net` | 8 | 5 | 40 | 1,172 | 14,161 | 122.1 | `queryperf-vsan-host-net-2026-11-06.json` |
| 20 | `host-zdom-top-stats` | 11 | 5 | 55 | 1,859 | 19,225 | 144.4 | `queryperf-host-zdom-top-stats-2026-11-06.json` |
| 21 | `ioinsight` | 82 | 0 (empty) | 0 | 118 | 128 | 81.2 | none |
| 22 | `vsan-memory` | 12 | 5 | 60 | 1,986 | 21,576 | 161.0 | `queryperf-vsan-memory-2026-11-06.json` |
| 23 | `rdt-network-latency` | 11 | 5 | 55 | 1,251 | 18,950 | 116.3 | `queryperf-rdt-network-latency-2026-11-06.json` |
| 24 | `vsan-tcpip-stats` | 12 | 5 | 60 | 1,779 | 20,670 | 143.9 | `queryperf-vsan-tcpip-stats-2026-11-06.json` |
| 25 | `virtual-disk` | 7 | 148 | 1,036 | 19,884 | 372,560 | 252.5 | `queryperf-virtual-disk-2026-11-06.json` |
| 26 | `virtual-machine` | 6 | 30 | 180 | 4,884 | 65,245 | 111.0 | `queryperf-virtual-machine-2026-11-06.json` |
| 27 | `vsan-vnic-net` | 10 | 5 | 50 | 1,246 | 17,526 | 120.4 | `queryperf-vsan-vnic-net-2026-11-06.json` |
| 28 | `vnic-rdt-network-latency` | 10 | 5 | 50 | 1,278 | 17,345 | 126.3 | `queryperf-vnic-rdt-network-latency-2026-11-06.json` |
| 29 | `vscsi` | 8 | 148 | 1,184 | 23,786 | 414,348 | 249.8 | `queryperf-vscsi-2026-11-06.json` |
| 30 | `zdom-vtx` | 10 | 5 | 50 | 1,364 | 17,850 | 124.8 | `queryperf-zdom-vtx-2026-11-06.json` |

Totals: 30 calls, 4.395 s wall (serial, one timer around the loop), 73,430 B
wire, 1,148,500 B decoded, 403 entities, 3,246 series. 24 files saved.

- **Name collision:** `queryperf-cluster-domclient-2026-11-06.json` already
  exists in this folder (the unfiltered capture from the README round). This
  round's labels-filtered capture of the same type is saved as
  `queryperf-cluster-domclient-labels-2026-11-06.json`; the existing file was
  not touched.
- **Captured:** 2026-11-06 ~23:09 America/Chicago (2026-11-07 05:08 UTC),
  vCenter 9.1.1.0100 build 25784172, cluster `vcf-lab-mgmt-cl01` (5-host ESA),
  read-only (queries, ContainerView create/destroy, login/logout). The
  join-key reads in the same session (PropertyCollector, `QueryDisksForVsan`,
  `QueryVsanManagedDisks`) were not saved here; they are summarized in the digest.
- **Scanned:** every saved file checked for the session id and the string
  `password` before writing; neither present. The bodies carry lab uuids and
  VM disk paths only.
- **Digest:** `knowledge/context/api-maps/vsan-performance-service.md`, section
  "Build 2 entity types (measured 2026-11-06)".
