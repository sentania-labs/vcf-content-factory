# devel_8_18 SDK jar, collector Java, and Cloud Proxy compliance log (2026-10-24)

Issue #212 step 1. Read-only SSH evidence from the devel_8_18 appliance (Aria Operations
8.18.7 build 25423534: one node `vcf-lab-operations-devel-8`, one Cloud Proxy
`vcf-lab-operations-devel-8-collector`), run 2026-10-24 around 00:15 to 00:40
America/Chicago. Only reads, one scp pull of the jar, and local javac/javap in scratch.
Nothing was changed on either node. Scott confirmed SSH is enabled on all appliances.

Access: key auth was refused on the node (`Permission denied (publickey,password,keyboard-interactive)`).
No ssh_password is stored for `devel8`; the one stored for `devel` also works as root
on both devel8 nodes (piped through `sshpass -e`, never on argv, never printed). Side
effect: both host keys were added to the workstation's known_hosts.

## 1. Facts

| Fact | Value | Source |
|---|---|---|
| SDK jar path (node) | `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`; a second file `vrops-adapters-sdk-1.0.jar` sits beside it | find on node |
| Size, mtime | 965,383 bytes, 2026-05-12 (node 23:19, proxy 23:21) | ls -l |
| sha256 | `45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea` | sha256sum |
| Same bytes elsewhere | `-1.0.jar` on the node, the same jar on the Cloud Proxy, and the copy under `user/plugins/inbound/NSXTAdapter3/lib/` are all this hash. Other copies (tomcat webapps, controller plugins, CaSA) are named `-1.0.jar` and were not hashed | sha256sum |
| Copy off | `/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/vrops-adapters-sdk-8.18.7.jar`; sha256 after copy identical to the node's | scp, sha256sum |
| Class files in jar | 471 classes, every one major 55 (Java 11). `AdapterBase.class` header `cafe babe 0000 0037` | python zipfile scan, xxd |
| Comparison jars | 9.0.2 "2.2" jar: major 61 (Java 17), 480 classes. 9.1.1.0100: major 69 (Java 25) | xxd |
| Collector Java, node | `/usr/java/jre-vmware-11/bin/vcops-collector` (process 5804, wrapper `wrapper.conf.vcops`), OpenJDK 11.0.30+9 LTS, build date 2026-01-20 | ps -ef, java -version |
| Collector Java, Cloud Proxy | `/usr/java/jre-vmware/bin/vcops-collector`, OpenJDK 11.0.30+9 LTS (identical build string) | ps -ef, java -version |
| SDK jar on the collector classpath | `wrapper-classpath.conf` line 63: `common/lib/vrops-adapters-sdk.jar` | grep |
| OS | VMware Photon OS 5.0 | /etc/os-release |

Platform-to-Java ladder now known for all three SDK lines: 8.18.7 runs Java 11, 9.0.2 runs
Java 17, 9.1.1.0100 runs Java 25.

## 2. Public API delta, 8.18.7 jar vs 9.0.2 "2.2" jar

The 22 classes are the distinct `com.integrien.*` and `com.vmware.*` imports across
`src/` and `content/sdk-adapters/` (the tier2_architecture.md section names the count,
not the list; this is the list). `javap -public`, JDK 17.0.20, nested class compared as
`CommonConstants$ResourceStatusEnum`.

| Result | Classes |
|---|---|
| Identical (19) | AdapterStatus, DiscoveryParam, DiscoveryResult, Logger, MetricData, MetricDataCache, MetricKey, Relationships, ResourceKey, ResourceStatus, TestParam, config.AdapterConfig, config.AdapterCredentialConfig, config.CredentialConfig, config.CredentialFieldConfig, config.ResourceConfig, config.ResourceIdentifierConfig, security.Crypt, util.CommonConstants.ResourceStatusEnum |
| AdapterBase | 8.18 lacks `getCertificateRenewalUrls()` and `final registerInterface(Class, Object)` (2 methods removed relative to 2.2) |
| CustomTrustManager | 8.18 is `implements X509TrustManager`; 2.2 is `extends X509ExtendedTrustManager`. 8.18 lacks the two constructors taking an `AdapterLoggerFactory`, `isAdapterInfoAvailable()`, and the four Socket/SSLEngine `check*Trusted` overloads (7 members removed). The nested `CustomCertificateException` is present in both |
| describe.AdapterDescribe | 8.18 lacks `getLiQueryConfigs()` / `setLiQueryConfigs(List)` (2 removed). 8.18 has nothing 2.2 lacks |

Direction: every difference is something the older 8.18 jar does not have. Nothing was added
in 8.18. Whole-jar class set: 1 class only in 8.18, 10 only in 2.2 (log-insight query
describe classes, `AdapterLoggerConfig`, `INonDisruptiveCertificate`, and others).

Does the factory call any of the missing members? Main sources: no. A real compile settles it.

| Compile (JDK 17, `-source 11 -target 11`, SDK jar only on classpath) | Result |
|---|---|
| Framework main sources (21 files) vs the 8.18 jar | OK, 0 errors (deprecation note only, same as vs 2.2) |
| Seven Java paks (compliance, unifi, synology, template, vcommunity, vcommunity-os, vcommunity-vsphere) vs 8.18 jar plus the framework built against it | OK, 0 errors each |
| Framework unit tests | Not compiled (no JUnit run). By grep, `CertificateReviewTest` calls `AdapterBase.getCertificateRenewalUrls()` and reflects on it, so that one test file would not compile against 8.18 as written. Test-only, not shipped |

Build outputs went to the session scratchpad, not the repo.

## 3. Cloud Proxy compliance adapter log

File: `/storage/log/vcops/log/adapters/ComplianceAdapter/ComplianceAdapter_447.log`. It is the
only file in that directory (6,852,118 bytes, 27,577 lines; `447` is the adapter instance id).
First line 2026-10-15 13:41:57 CDT (the install day), last line 2026-10-17 11:25:54 CDT, file
mtime 2026-10-17 11:25. The adapter has logged nothing since, consistent with the instance
having been stopped or removed after the 2026-10-17 proof runs (INFERRED; not checked here).
Timestamps below are verbatim log stamps (UTC, `+0000`); subtract 5 hours for Chicago.

Stitch logger name: **`com.vcfcf.adapter.stitch.SuiteApiStitcher.build`** (the client's
construction log); the compliance side logs as `com.vcfcf.adapters.compliance.ComplianceStitcher.*`
and `com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo/logWarn`. 11,245 lines match
"stitch". Level counts: 0 ERROR, 2 WARN, rest INFO. Build in the log: dev-preview 0.0.0.95.

Excerpt (18 lines; long lines cut with `...`; principal id shortened):

```
2026-10-15T18:41:57,395+0000 INFO  [TasksManager-TaskHandler-113] (447) com.vcfcf.adapter.stitch.SuiteApiStitcher.build - SuiteApiStitchClient: credential mechanism=ambient file=instance principal=dc959326-... endpoint=https://localhost/suite-api
2026-10-15T18:41:57,396+0000 INFO  [TasksManager-TaskHandler-113] (447) com.vcfcf.adapter.stitch.SuiteApiStitcher.build - SuiteApiStitchClient: transport=openPlatformConnection loopback (BC-mirror: trust-all + ignore-hostname, non-FIPS) mechanism=ambient principal=dc959326-...
2026-10-15T18:41:57,442+0000 INFO  [TasksManager-TaskHandler-113] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - ComplianceAdapter configured: vcenter=vcf-lab-vcenter-mgmt.int.sentania.net profile=Auto (by version) readApplianceSettings=false overridesFile=(none) stitcher=true
2026-10-15T18:41:57,900+0000 INFO  [Collector worker thread 18] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - ComplianceAdapter enumerate: registering ComplianceWorld
2026-10-15T18:46:58,321+0000 INFO  [Collector worker thread 2] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - Bulk shadow mode: dev-preview build 0.0.0.95: on
2026-10-15T18:46:58,413+0000 INFO  [Collector worker thread 2] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - stitcher=true
2026-10-15T18:46:58,533+0000 INFO  [Collector worker thread 2] (447) com.vcfcf.adapters.compliance.ComplianceStitcher.loadResourcesForKind - ComplianceStitcher: HostSystem - processing 10 resource(s)
2026-10-15T18:47:02,142+0000 INFO  [Collector worker thread 2] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - Bulk shadow Host: 240 control(s) compared on 6 object(s), 0 disagreeme...
2026-10-15T18:47:07,097+0000 INFO  [Collector worker thread 2] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - Bulk shadow VM: 924 control(s) compared on 42 object(s), 0 disagreemen...
2026-10-17T08:38:01,976+0000 WARN  [Collector worker thread 11] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn - Host vcf-lab-mgmt-esx03.int.sentania.net: connectionState='notResponding': host not fully connected to vCenter; ALL compliance controls marked UNREADABLE this cycle (no partial score emitted)
2026-10-17T08:38:10,631+0000 WARN  [Collector worker thread 11] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn - 48 control instance(s) could not be read this cycle (declared-but-unreadable). They were not pushed (their last values stay), they are outside each object's score and the pass rates, each affected object has has_unreadable = 1 with its reason, and its "Compliance data not collected" alert fires after two cycles.
2026-10-17T16:25:54,468+0000 INFO  [Collector worker thread 4] (447) com.vcfcf.adapters.compliance.ComplianceStitcher.loadResourcesForKind - ComplianceStitcher: DistributedVirtualPortgroup - processing 58 resource(s)
2026-10-17T16:25:54,483+0000 INFO  [Collector worker thread 4] (447) com.vcfcf.adapters.compliance.ComplianceStitcher.loadResourcesForKind - ComplianceStitcher: loaded 12 DistributedVirtualPortgroup by name, 12 by MOID (scoped to vCenter 4ff53df1-...
2026-10-17T16:25:54,486+0000 INFO  [Collector worker thread 4] (447) com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo - Stitcher loaded: 12 DVPG
```

The principal line shows this build (0.0.0.95) still logged the instance principal id. The
framework fix "no principal in logs" (#248) is later than that build, so the stitch client line
will differ on a rebuilt pak. Stitch client loopback transport is `openPlatformConnection`,
trust-all, non-FIPS; no stitch failure of any kind in 27,577 lines. The only two WARNs are a
disconnected host (esx03) and its follow-on unreadable-controls summary, both data-state
warnings, not SDK or stitch faults. No hostname-embedded credentials appear in the file's
sampled lines.

## 4. What the collector's Java means for the shipped bytecode target

Adapters ship Java 11 bytecode (`-source 11 -target 11`). 8.18.7's collector, on both the
node and the Cloud Proxy, is exactly Java 11 (OpenJDK 11.0.30). So Java 11 bytecode is not
just conservative: it is the **ceiling** for 8.18. Anything compiled to 17 would fail to
load there (`UnsupportedClassVersionError`). This pins the shipped target at 11 for as long
as 8.18 is a supported install target; moving to 17 would drop 8.18. Running on 9.0.2 (17)
and 9.1.1 (25) is unaffected, since newer JVMs load older bytecode. Caveat: the build
uses `-source 11 -target 11`, not `--release 11`, so a call to a JDK 12+ library API would
compile on JDK 17 and fail on the 8.18 collector at run time. Nothing in this step tested for
that (not measured).

## 5. Can the 8.18 jar be the third compile-matrix leg (#211 pattern)?

**Yes, with two differences from the 9.1.1 leg.**

1. It needs no new JDK. The jar is major 55, so the existing JDK 17 javac reads it (the 9.1.1
   leg needs JDK 25 because its jar is major 69). The leg can run on the same
   `ubuntu-latest` JDK 17 the primary build uses.
2. It is a real compat check, not a formality: measured today, framework main and all seven
   Java paks compile clean against it, but 8.18 is the **older** API. It lacks 11 members
   the 2.2 jar has (AdapterBase 2, CustomTrustManager 7, AdapterDescribe 2). The leg would
   catch the factory ever starting to call `getCertificateRenewalUrls`, `registerInterface`,
   the log-insight describe getters, or the extended trust manager. That is exactly the
   regression that would break an adapter on an 8.18 collector.

Constraints for adding it:

- `CertificateReviewTest` (test-only) references `getCertificateRenewalUrls`; the leg should
  compile main sources only, as `build-framework.sh`'s compat pass does.
- The jar lives on the holding share (`/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/`),
  local to this lab like the 9.1.1.0100 jar. CI reach needs the same path as issue #250: upload
  to the private `sentania-labs/vcf-content-factory-sdk-runtime` repo and use
  `SDK_RUNTIME_SSH_KEY`. Until then the leg skips with a notice, same as 9.1.1.
- `PROVENANCE.md` gets a third row (this sha256, 965,383 bytes, Java 11 major 55, platform
  8.18.7 build 25423534, path `common/lib/vrops-adapters-sdk.jar`). Redistribution survey
  (2026-06-09) applies: keep the jar out of the public repo.
- `build-framework.sh` compat pass is written around one named 9.1.1 jar and a JDK 25
  requirement; it would need a per-leg jar and JDK list (tooling change, not done here).
- Not compared: 9.1.1.0100 vs 8.18 directly (not asked); both are expected to be supersets
  of 8.18 given the 2.2 comparison, which is INFERRED.

## 6. Open items

- Whether the compliance instance 447 still exists on the proxy: not checked (no Suite API
  call in this step).
- The tomcat/plugin `vrops-adapters-sdk-1.0.jar` copies were listed but not hashed; only the
  `common/lib` pair and the NSXTAdapter3 copy were. Not needed for the collector, which
  loads `common/lib/vrops-adapters-sdk.jar`.
