# vsanperf 0.0.0.7 on two Cloud Proxies: 8.18 instance FAILED, 9.0.2 log scan (2026-11-06)

Read-only SSH (key auth as root, `BatchMode=yes`) on `vcf-lab-operations-devel-8-collector`
(Aria Ops 8.18.7, collector id 2) and `vcf-lab-operations-devel-collector` (VCF Ops 9.0.2,
collector id 2), run 2026-11-06 around 22:17 to 22:30 America/Chicago. Only ls, cat, grep,
find, head/tail, `java -version`. Nothing was changed on either node. Layout precedent:
`2026-10-24-devel-8-18-sdk-jar-and-proxy-log.md`.

Log stamps are UTC. Chicago is CST (UTC-6) since 2026-11-01, so `03:42Z` on 11-07 is 21:42 on
11-06. Redaction: session ids, 32+ char hex and long token-like strings are replaced with
`<REDACTED>`; the only 32+ hex string in the vsanperf logs is the framework source commit hash.

## 1. 8.18 proxy: why instance 013010e1-... stayed FAILED

**Answer: the pak never reached the proxy.** The collector got the "Update Adapters" task for
`vcfcf_vsanperf.jar`, asked the controller for the files ("Sync Adapters"), gave up after 30 s
waiting for the answer (the answer arrived at 31.5 s), and then tried to load a jar that was
never written. The adapter kind was therefore unknown to this collector, so every start and stop
for the instance was rejected with "Unknown adapter type". Nothing retried the sync before the
instance was deleted. Not a Java version or class-loading problem: the code never got as far as
loading a class.

| Fact | Value | Source |
|---|---|---|
| `plugins/inbound/vcfcf_vsanperf/` or `vcfcf_vsanperf.jar` | **Absent.** No file named `*vsanperf*` anywhere on the proxy outside Docker image layers (pyVmomi stubs) | ls, find |
| Sibling factory paks, same dir | `vcfcf_compliance/` (conf, doc, lib) + `vcfcf_compliance.jar` (2026-10-28 05:16); `unifi_controller/` + `.jar` (10-15 14:22); `synology_diskstation/` + `.jar` (10-28 01:34); `VsanHostMetrics/` (conf only, Python pak) + `VsanHostMetrics.conf` (10-29 16:04) | ls -la |
| `plugins/` dir mtime | 2026-11-06 21:43 (entry churn at the update; no surviving file); `inbound/` mtime unchanged since 10-29 | ls -la |
| Per-adapter log dir | None for vsanperf under `/storage/log/vcops/log/adapters/` (an adapter class never ran) | ls |
| Instance UUID `013010e1` in collector.log | 0 hits. The collector logs the internal id: the instance is **AIR=1478** | grep |
| Sync Adapters wait | Sent 03:42:34.920Z, timeout logged 03:43:04.930Z (30.0 s), response received 03:43:06.403Z, "Elapsed Time: 31482 msecs" | collector.log |
| Sync history on this proxy (10-23 to 11-07) | 14 completed syncs, 12.1 s to 148.8 s. The 30 s wait was exceeded 4 times: 10-23 15:55Z, 10-26 18:14Z, 10-28 09:39Z (all `vcfcf_compliance.jar` updates, where the old jar stayed in place) and 11-07 03:43Z (vsanperf, a new kind with no prior jar) | collector.log* |
| Recovery precedent | The 10-28 09:39Z compliance timeout was followed by a successful re-push at 10:15Z (jar mtime 10-28 05:16 CDT = 10:16Z) | ls, collector.log.7 |
| Later Update/Sync tasks after 03:43Z | None through 04:17Z | grep |
| UnsupportedClassVersionError / ClassNotFoundException | 0 / 0 | grep |
| NoClassDefFoundError | 1,088 hits, all `com/vmware/identity/cdc/CdcFactory` from the SSO admin client ("CDC not configured"), unrelated | grep |
| Collector JVM, Cloud Proxy | `/usr/java/jre-vmware/bin/vcops-collector`, OpenJDK 11.0.30+9-LTS (2026-01-20). Unchanged from 10-24 | ps, java -version |
| Collector JVM, 8.18 analytics node | OpenJDK 11.0.30+9 LTS per the 10-24 record. Not re-read today: `ssh root@vcf-lab-operations-devel-8` failed host key verification, not bypassed | 10-24 doc |
| JVM differs proxy vs node? | No (same build string, 10-24) | |

Verbatim (8.18 proxy `collector.log`, `sessionId` redacted, stack frames omitted):

```
2026-11-07T03:42:15,948+0000 INFO  [TasksManager-ReceivedTasksProcessor-1]  com.integrien.alive.common.communication.TasksManager.run - Received task. ID: 55935, Name: Remove Adapters, CollectorID: 2, Created at: 1794022935272, Details: null, Elapsed Time: 675 msecs.
2026-11-07T03:42:21,135+0000 INFO  [TasksManager-ReceivedTasksProcessor-1]  com.integrien.alive.common.communication.TasksManager.run - Received task. ID: 55937, Name: Update Adapters, CollectorID: 2, Created at: 1794022940102, Details: [Jar files: {vcfcf_vsanperf.jar}] [Property files: {}], Elapsed Time: 1033 msecs.
2026-11-07T03:42:34,920+0000 INFO  [TasksManager-TaskHandler-25580]  com.integrien.alive.common.communication.TasksManager.sendTask - Sending task. ID: 19374, Name: Sync Adapters, CollectorID: 2, Details: Collector version: 35.
2026-11-07T03:43:04,930+0000 WARN  [TasksManager-TaskHandler-25580]  com.integrien.alive.common.communication.TasksManager.sendTaskAndGetResponse - Did not receive response from Controller for 'Sync Adapters' task. Wait for response timed out.
2026-11-07T03:43:04,932+0000 ERROR [TasksManager-TaskHandler-25580]  com.integrien.alive.collector.Collector.syncAdapterJars - Failed to send sync adapters task
2026-11-07T03:43:04,947+0000 ERROR [TasksManager-TaskHandler-25580]  com.integrien.alive.collector.Collector.updateAdapters - Adapter jar synchronization failed : PlatformException: Failed to send sync adapters task
2026-11-07T03:43:04,964+0000 ERROR [TasksManager-TaskHandler-25580]  com.integrien.alive.common.adapters.AdapterLoader.loadAdapters - Problem occurred while loading adapter: vcfcf_vsanperf.jar : FileNotFoundException: /usr/lib/vmware-vcops/user/plugins/inbound/vcfcf_vsanperf.jar (No such file or directory)
2026-11-07T03:43:06,403+0000 INFO  [TasksManager-ReceivedTasksProcessor-1]  com.integrien.alive.common.communication.TasksManager.run - Received response. ID: 19374, Name: Sync Adapters, CollectorID: 2, Created at: 1794022954920, Details: Collector version: 35, Response{filesToDelete=[AppOSUCPAdapter3/conf/3fb4e12a-25a1-4052-ab67-c1597b30995a60.ser], folderToDelete=[], sessionId=<REDACTED>}, Elapsed Time: 31482 msecs.
2026-11-07T03:44:30,340+0000 INFO  [TasksManager-ReceivedTasksProcessor-1]  com.integrien.alive.common.communication.TasksManager.run - Received task. ID: 55993, Name: Start monitoring, CollectorID: 2, Created at: 1794023069509, Details: {AIR=1478,ResId={1478};}, Elapsed Time: 831 msecs.
2026-11-07T03:44:30,344+0000 ERROR [TasksManager-TaskHandler-25595]  com.integrien.alive.collector.Collector.startMonitoring - Unknown adapter type is specified in collector configuration. (Type = vcfcf_vsanperf)
2026-11-07T03:53:04,935+0000 ERROR [TasksManager-TaskHandler-25615]  com.integrien.alive.collector.Collector.stopMonitoring - Unknown adapter type is specified in collector configuration. (Type = vcfcf_vsanperf)
2026-11-07T03:54:48,320+0000 ERROR [TasksManager-TaskHandler-25618]  com.integrien.alive.collector.Collector.stopMonitoring - Unknown adapter type is specified in collector configuration. (Type = vcfcf_vsanperf)
```

The loaded-adapter list printed right after the failure (03:43:04.965Z) includes `vcfcf_compliance`
0.0.0.103, `synology_diskstation` 0.0.0.35, `unifi_controller` 0.0.0.14, `VsanHostMetrics` 2.0.0,
`ClusterPerfRisk` 2.1.0 and no `vcfcf_vsanperf`.

Contrast, 9.0.2 proxy, same minute: the same race showed up (a Start monitoring arrived at
03:42:42.118Z before the jar landed and logged the identical "Unknown adapter type" ERROR), but its
Sync Adapters answered in about 30 s inside the wait (sent 03:42:15.469Z, received 03:42:45.197Z),
the jar loaded at 03:42:47.284Z (`Loaded adapter entry class com.vcfcf.adapters.vsanperf.VsanPerfAdapter
of adapter 'vcfcf_vsanperf'`, version `0.0.0.0.0.7`), and the next start at 03:44:04Z worked.

Operational reading (INFERRED from the above, not tested): on these lab proxies the controller's
Sync Adapters reply routinely takes 12 to 150 s against a 30 s collector wait. For a jar update of
an existing kind a timeout is silent (the old jar keeps running). For a **new** adapter kind it
leaves the proxy without the adapter and any instance placed there sits FAILED with an empty
status message. A stop/start does not re-sync. What does trigger a re-sync (re-install of the
pak, collector restart, a later Update Adapters) was not tested.

## 2. 9.0.2 proxy: instance f8ae0aaa-... log scan

| Fact | Value | Source |
|---|---|---|
| Pak files | `plugins/inbound/vcfcf_vsanperf/` (conf, doc, lib/`vcfcf-adapter-base.jar` 21:27) + `vcfcf_vsanperf.jar` 92,876 bytes 21:42; `conf/version.txt` Implementation-Version 0.7, Adapter-Version-Ref 2.2 | ls, cat |
| Collector JVM | OpenJDK 17.0.16 LTS (2025-07-15) | java -version |
| Log dir | `/storage/log/vcops/log/adapters/VsanPerfAdapter/`: `VsanPerfAdapter_7083.log` (16 lines), `_7084.log` (180), `_7086.log` (79) | ls, wc |
| Which file is f8ae0aaa | The UUID appears in no log. **7083** is the only vsanperf instance still started (Start monitoring 03:29Z, restarted 03:42:42Z/03:44Z, auto-discover plus Start monitoring every 5 min through 04:19Z). 7084 was stopped and removed 03:35Z; 7086 stopped and removed 03:53Z. Mapping 7083 = f8ae0aaa is INFERRED | collector.log |
| `session[` | 0 / 0 / 0 (7083 / 7084 / 7086) | grep -c |
| `vmware-api-session-id` (ci) | 0 / 0 / 0 | grep -ci |
| `password` (ci) | 0 / 0 / 0 | grep -ci |
| 32+ char hex | 2 / 1 / 0, every one is the `vcfcf-adapter-base 1.0.24 (source <commit>)` build-hash line, not a credential | grep -c, context |
| 32+ char base64-like | 2 / 1 / 0, the same lines as the hex hits | grep -c |
| `PERF ` lines | 0 in all three files and 0 in collector.log | grep -c |
| Cycle summary INFO line | **None exists.** The adapter has no INFO cycle summary: the only per-cycle lines in source are the `perf("PERF ...")` calls in `CycleEngine.java`, gated by `perfTimingLogging`. 7083's last line of any kind is 03:49:06Z | grep, source |
| WARN/ERROR in 7083 since 03:40Z | 0 | grep |
| WARN/ERROR in other vsanperf instances since 03:40Z | 7086: 2 WARN. Collector side: 1 ERROR (the race above), 1 WARN (stop of 7083 with no work item) | grep |

7083's most recent INFO lines (verbatim, hash redacted):

```
2026-11-07T03:44:04.904Z INFO  VsanPerfAdapter 9902 [ops@4413 threadId="514534" threadName="TasksManager-TaskHandler-33941" instanceId="7083"] [(7083) com.vcfcf.adapters.vsanperf.VsanPerfAdapter.logInfo] - VsanPerfAdapter configured: vcenter=vcf-lab-vcenter-mgmt.int.sentania.net include=(all) exclude=(none) workers=4 callTimeout=30s cycleDeadline=interval-60s perfTimingLogging=false releaseId=8.0.3
2026-11-07T03:49:06.351Z INFO  VsanPerfAdapter 9902 [ops@4413 threadId="320" threadName="Collector worker thread 13" instanceId="7083"] [(7083) com.vcfcf.adapters.vsanperf.VsanPerfAdapter.logInfo] - VcfCfAdapter.openPlatformConnection: Suite API transport mode=non-FIPS (signal: environment variable IS_FIPS is not true). Trust-all, hostname ignored, as the vendor SuiteAPIClient. Diagnostic only, no ...
```

WARN/ERROR since 21:40 local for vsanperf on this proxy (up to five, verbatim, line ends cut):

```
2026-11-07T03:42:42.118Z ERROR collector 9902 [ops@4413 threadId="514353" threadName="TasksManager-TaskHandler-33932"] [com.integrien.alive.collector.Collector.startMonitoring] - Unknown adapter type is specified in collector configuration. (Type = vcfcf_vsanperf)
2026-11-07T03:43:59.330Z WARN  collector 9902 [ops@4413 threadId="514533" threadName="TasksManager-TaskHandler-33940"] [com.integrien.alive.collector.Collector.stopAdapter3] - No work item for adapter instance resource '7083' to stop monitoring.
2026-11-07T03:49:23.900Z WARN  VsanPerfAdapter 9902 [ops@4413 threadId="85" threadName="Collector worker thread 4" instanceId="7086"] [(7086) com.vcfcf.adapters.vsanperf.VsanPerfAdapter.logWarn] - onCollect: error collecting VsanPerfCollector/VCF Content Factory vSAN Performance Collector: vCenter login or ServiceInstance read failed: Login: ConnectException
2026-11-07T03:49:23.902Z WARN  VsanPerfAdapter 9902 [ops@4413 threadId="85" threadName="Collector worker thread 4" instanceId="7086"] [(7086) com.vcfcf.adapters.vsanperf.VsanPerfAdapter.logWarn] - onCollect: adapter instance set to RESOURCE_STATUS_DOWN: Collection failed for all 1 resource(s): IOException: vCenter login or ServiceInstance read failed: Login: ConnectException
```

Earlier (before 21:40, for context): 7084 logged the same `Login: ConnectException` twice (03:29Z,
03:34Z) and, at its removal, `ERROR ... VsanPerfAdapter configuration is invalid: the vCenter user
name is empty` (03:35:16Z).

## 3. What remains unknown

- That 7083 is f8ae0aaa: inferred from it being the only live vsanperf instance; a Suite API
  lookup of the instance's internal id would settle it (not done, SSH-only brief).
- Whether 7083 is actually collecting: it gets Start monitoring every 5 min, but with timing
  logging off and no INFO cycle line in the adapter, its log is silent by design. The log cannot
  prove collection; metric timestamps on resource 7085 in Ops can.
- 7083 ran 03:29Z to 03:35Z with `perfTimingLogging=true` yet wrote 0 `PERF ` lines. Either no
  collection cycle completed in that window or the perf lines go elsewhere; not determined.
- What re-triggers a Sync Adapters on an 8.18 proxy after a timeout (pak reinstall, collector
  restart, or a later update) and whether the 30 s wait is configurable: not tested.
- 8.18 analytics node JVM today: not re-read (host key not known to this workstation); 10-24
  record says OpenJDK 11.0.30, same as the proxy.
- 7086's target that refused the connection (ConnectException): not investigated.

Superseded in part (2026-11-06, later): the missing cycle summary and the
missing `PERF` lines were explained by factory issue #313 (lines written
through per-class component loggers never reach the instance log) and fixed
in vsanperf build 9; the proof is `knowledge/context/reviews/vsanperf-t5-devel-9.0-build-9.md`.
The sync-timeout sentence "routinely takes 12 to 150 s" should read: 4 of 14
syncs since 10-23 exceeded the 30 s wait (range 12 to 149 s).
