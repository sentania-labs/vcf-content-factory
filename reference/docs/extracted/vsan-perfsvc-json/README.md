# vsan-perfsvc-json

Two verbatim responses from the vSAN Performance Manager over the vSphere
JSON API, captured read-only on the lab management vCenter.

1. `queryperf-cluster-domclient-2026-11-06.json`: the body returned by
   `POST /sdk/vim25/9.1.1.0/vsan/VsanPerformanceManager/vsan-performance-manager/VsanPerfQueryPerf`
   with one spec `{"_typeName":"VsanPerfQuerySpec","entityRefId":"cluster-domclient:*",
   "startTime":<now-7min UTC>,"endTime":<now UTC>}` and the cluster MoRef
   `domain-c6004`, request headers `vmware-api-session-id` and `Accept-Encoding: gzip`
   (the response body carries no session id, so nothing was scrubbed).
   Server pretty-printed; the `", "` separators are the server's.
2. `queryperf-fault-wildcardlimit-2026-11-06.json`: the HTTP 500 body
   returned by the same endpoint when two wildcard specs are sent in one
   call (`InvalidArgument`, fault key
   `com.vmware.vsan.perfsvc.fault.queryperf.wildcardlimit`).

- **Source:** vcf-lab-vcenter-mgmt.int.sentania.net, VMware vCenter Server
  9.1.1.0100 build 25784172, vSAN ESA cluster `vcf-lab-mgmt-cl01`.
  Local-only artifact: a live capture, not in any fetch registry.
- **Extracted:** 2026-11-06 (RULE-016, immutable once added). Neither file
  contains a credential or session id (scanned).
- **Digest:** `knowledge/context/api-maps/vsan-performance-service.md`,
  section "JSON API transport".
