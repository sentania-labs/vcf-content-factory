# vsanperf build 10 review (Build 2 round 1: host and cluster tiers)

- **Adapter:** `content/sdk-adapters/vsanperf` (branch `build-10-host-cluster-tiers`, uncommitted tree, diffed against `main` = v1.0.0.9)
- **Reviewer:** `sdk-adapter-reviewer`, 2026-11-07
- **Design:** `knowledge/designs/vsanperf-mp-v2.md` (with the P2 addendum), `vsanperf-mp-v1.md` where v2 is silent
- **Verdict:** **CHANGES REQUESTED**. 1 BLOCKING, 3 WARNING, 5 NIT

The code is in good shape. Stitch identity, key names, the bucket rule, learned-empty and fatal-error handling all hold up under an independent check. The one BLOCKING finding is in the docs: the shipped `docs/overview.md` still describes Build 1 and contradicts what this build does.

## Independent re-runs

| Claim | Re-run | Result |
|---|---|---|
| validate-sdk passes, 9.0 and 8.18.7 legs | `validate-sdk` with `--sdk-compat-jar` set to the 8.18.7 and 9.1.1.0100 jars from `/mnt/holding/vendor/` | **Confirmed.** `OK`. 9.0 leg: javac 17, --release 17. 8.18.7 leg: --release 11, no warnings. 9.1.1.0100 leg skipped (needs JDK 25; only 17 is installed here), so it was not part of the claim either. Without the flag, 8.18.7 is skipped because its jar is not in `adapter_runtime/`. |
| build-sdk produced `vcfcf_sdk_vsanperf.0.0.0.10.pak` | rebuilt into the scratchpad | **Confirmed.** `adapters.zip` is 222,685 bytes and its entry list matches the author's `dist/` pak. The adapter tree was unchanged after the build. |
| pak-compare 0 BLOCKING / 1 WARNING against 0.0.0.9 | rebuilt pak vs `dist/vcfcf_sdk_vsanperf.0.0.0.9.pak` | **Confirmed.** `0 BLOCKING, 1 WARNING, 1 INFO`. W1: identifier count 10 vs 7, the three new settings, expected. |
| pak-compare 0 BLOCKING / 1 WARNING against compliance | rebuilt pak vs `dist/vcfcf_sdk_compliance.0.0.0.104.pak` | **Confirmed.** `0 BLOCKING, 1 WARNING, 56 INFO` |
| `ci/run_java_tests.sh`: 11 classes pass | re-run | **Confirmed.** 11 classes pass. `WatermarksTest`: compact marks estimate 705,400 B, measured 714,784 B; Build 1 String-keyed marks 13,614,856 B |
| 338 new keys match the design tables row by row | my own script: design v2 "Cluster tier" and "Host tier" tables parsed against `EntityType.java` (label, group, leaf, per-mille flag, instanced form) | **Confirmed.** 338 rows, 23 types, 0 differences. `tests/fixtures/design-build2-metrics.md` has the same rows as the design. |
| Build 1 keys unchanged | the 61 `m(...)` rows of `main:EntityType.java` vs the first 61 now | **Byte-identical.** `ROOT`, `statKey` grammar, core groups `DOM Owner` / `DOM Client` / `pNIC` (TWO form) unchanged |
| 19 new fixtures match provenance | `cmp` against `reference/docs/extracted/vsan-perfsvc-json/`; sha256 prefixes recomputed; entity and series counts recounted against the `PROVENANCE-2026-11-06-build2.md` table | **Confirmed.** 19 byte-identical, 24 of 24 README sha256 prefixes match, every entity and series count matches |
| 26 then 23 calls per cycle, default tiers | `TiersEngineTest.labDefaultTiers` (vendor captures, fake vCenter) | **Confirmed in the test.** 26 calls on cycles 1 to 3, 23 from cycle 4, `ioinsight` still queried, core never learned. Not live. |
| Java 11 bytecode | class-file major version of every class in the built `vcfcf_vsanperf.jar` | **Confirmed.** All 63 classes are version 55 |
| describe.xml settings | parsed from the built pak | `tier_host` / `tier_cluster`: enum true/false, default `true`, identType 2. `exclude_types`: string, default empty, identType 2. Labels match the design's Settings table. `vcenter_host` / `cluster_include` identity unchanged. No `<SymptomSets>`. The enum-identifier shape is the one `perf_timing_logging` has had since build 5, installed on 8.18.7 at build 7 (`vsanperf-t5-devel-8.18-build-7.md`). |

## Registry check (`knowledge/context/defects.md`)

No open defect names vsanperf in `Affects:`. The open ones are DEF-004 (vcommunity-os), DEF-019 (factory:extractor) and DEF-025 / DEF-026 (compliance). Nothing to re-assert and nothing to propose for closure. **Registration candidate:** W1, if it survives acceptance.

## BLOCKING

### B1. `docs/overview.md` contradicts build 10 (review dimension 11)

`docs/overview.md` was not touched in this build. It is the hand-written doc linked from the generated landing `docs/README.md`, and it states:

- line 5-9: data is pushed "onto the vCenter adapter's VMWARE HostSystem objects". Cluster-tier keys now land on ClusterComputeResource.
- lines 20-22, "Metrics scope": "Build 1: 61 key definitions ... Up to 390 series per cycle". The lab is now 399 keys and 1,186 series.
- lines 26-31, "Cross-Adapter Behavior": only the HostSystem stitch. There is no ClusterComputeResource stitch, no (VMEntityObjectID, VMEntityVCID) cluster match, no `clusters_unresolved`.
- line 39: only fault learning. Empty-echo learning is missing.
- line 45: "Build 1 covers hosts only: **no cluster**, disk or VM tier yet". This is false for this build.

Dimension 11 makes documentation that contradicts behaviour BLOCKING. A cross-MP stitch above all, because it never appears in describe.xml. An operator reading the pak's docs would be told the cluster tier does not exist while ClusterComputeResource is gaining `vSAN Perf|*` keys.

**Fix:** update `overview.md`:
- What's in the Pack and Metrics scope: core plus host tier plus cluster tier, 399 keys, 1,186 lab series.
- Cross-Adapter Behavior: add the ClusterComputeResource stitch and its key; the three landing types decided per entity.
- Notable Behaviors: the every-bucket rule; learned-empty, with core and `ioinsight` exempt.
- Known Limitations: disk and VM tiers not in this build; streaming parse deferred.

Root `README.md` and `REFERENCE.md` already describe all of this and can be the source.

## WARNING

### W1. One failing optional-tier type fails the cluster, and with it the whole cycle (`CycleEngine.java` ~1013-1037 and ~479)

Any type failure that is not "type unavailable" sets the cluster's outcome to FAILED: a `VsanFault`, an `IOException`, `Unreadable`, or a body over the cap. That holds for each of the 23 new optional types. `run()` then fails the cycle when `clustersFailed == clustersInScope`.

Scratch probe, using the author's fakes with one `IOException` on `vsan-file-service` on the lab's only cluster:

`clustersOk=0 clustersFailed=1 seriesPushed=2372 failure=every vSAN cluster in scope failed (1); first: cluster domain-c6004: vsan-file-service: ...`

Every value was pushed, but `CycleReport` throws. The collector object and the account show DOWN or error every cycle.

**Authority.**
- v1 §Failure handling: "One cluster faults → cycle succeeds" and "Response over the size cap → treated as a failed call for that cluster/type → cycle succeeds".
- v2 §Failure handling deltas adds no rule for a fault on a tier type.

The behaviour already existed for the 3 core types. Build 10 raises the exposure to 26 calls per cluster, and a single-cluster scope (the lab, or a sharded account) has no headroom at all. A type whose response shape changes across the fleet after a vSAN upgrade would turn every 70-cluster account DOWN while data keeps flowing.

**Fix:**
- Mark a cluster FAILED only when a core type failed, or when every call failed.
- Count a host-tier or cluster-tier type failure separately: WARN once per (cluster, type) per refresh, record it in `last_error`, and keep it out of `clusters_failed`.
- Add an engine test: one tier type faults on a one-cluster scope, and `failure` stays null.

### W2. `docs/installing.md` §Configuration Fields is missing the three new settings (dimension 11)

`tier_host`, `tier_cluster` and `exclude_types` are not listed. They are present in `REFERENCE.md` §Settings.

**Fix:** add three rows: labels, defaults (`true` / `true` / empty), Advanced. Add one line saying an account upgraded from 1.0.0.9 gets both tiers on.

### W3. The landing `docs/README.md` and `docs/inventory-tree.md` do not mention any stitch target (dimension 11)

Both files are generated from describe.xml, so they cannot show ARIA_OPS stitches. HostSystem has been missing since Build 1, and ClusterComputeResource is now missing too. This is the unifi v1.1.0.11 gap again.

**Fix:**
- B1 makes `overview.md` carry it.
- The generator gap belongs to `tooling` as a TOOLSET GAP: the generated landing page needs a "Stitched onto" section from adapter metadata. The author cannot fix that inside the pak.

## NIT

- **N1. `LearnedTypes.java:118-122`: fault-learned types re-probe without the spread.** A fault-learned type re-probes at exactly 24 h, with no per-(cluster, type) offset. v2 §Per-cycle call plan, "Re-probe spread", applies the offset to learned types. Faulting calls cost 0.04 to 0.07 s (MAP §"Does GetSupportedEntityTypes replace probing?"), so a clustered re-probe costs seconds, not the 260 s case. **Fix:** add `offsetMs(clusterMoid, type)` in `learn()`.
- **N2. `CycleEngine.refreshClusterMap`: double refreshes and a misleading WARN.**
  - The miss-trigger rate limit (`opsClustersMissRefreshCycle`) is not reset by a scheduled refresh. A cluster that is permanently missing therefore gets back-to-back reads: cycles 14 and 15, 27 and 28, and so on. Each read is one page.
  - **Fix:** set `opsClustersMissRefreshCycle = cycle` on every successful load.
  - When the list read itself failed (`opsClusters == null`), the miss WARN still asks "is the vCenter adapter collecting them?".
- **N3. Stale "assumed, unread" wording on ClusterComputeResource identifiers.** `OpsHostMap.java` class doc, `CHANGELOG.md` and README acceptance check 5 still call the identifiers assumed and unread. The v2 P2 addendum confirmed `VMEntityObjectID` + `VMEntityVCID` on ClusterComputeResource, both part of uniqueness, and a test push read back. T5 still owes the live readback, so keep that part.
- **N4. Typos and stale lines.**
  - `describe.xml:11`: "HostSystem objects (and, since build 10, VMWARE ClusterComputeResource) objects" has a doubled noun.
  - README file list: "PerfParser.java ... newest-sample selection" is stale; it now selects every bucket.
- **N5. `CycleEngine.java` ~1076: the malformed-id WARN is not rate-limited.** It fires every cycle per (cluster, type), inherited from the Build 1 pNIC path. It now covers 16 non-landing types times the number of clusters if a vSAN release changes an id form. **Fix:** rate-limit it like `landingWarn`, once per type per day.

## Author's deviations: verdicts

1. **No streaming parser yet: accepted for this round.**
   - The design's heap table puts in-flight non-VM responses under 3 MB whichever parser is used.
   - `PERF call` honestly says `parse=tree`.
   - Requirement 3 under v2 §Sizing (streaming for every perf call, T4 measuring one parser) still gates the VM tier round and the scale release.
2. **Summary and `calls_by_tier` leave out tiers that are off: accepted.**
   - An off tier printed as `0` would read as "ran, pushed nothing", the unreadable-vs-zero confusion.
   - Tiers that are on print their zeros.
   - The design's sample line lists disk and vm only because they exist in the design.
   - `PERF cycle` prints `calls_core/host/cluster` always. That is harmless but inconsistent.
3. **CHANGELOG heading `1.0.0.10 (Unreleased)` with `version: "1.0.0"`: accepted.**
   - It is consistent with `adapter.yaml` (1.0.0 + build 10).
   - The local build is on the RULE-014 `0.0.0.10` line.
   - When the orchestrator sets 1.1.0, rename the heading in the same commit.

## Hunt list: proven safe

- **Cluster MoRef under the wrong vCenter.** `OpsHostMap.load(.., CLUSTER)` indexes only rows whose `VMEntityVCID` equals `about.instanceUuid`. Rows with no VCID are not indexed, and a MoRef that appears twice for one vCenter is dropped as ambiguous. `TiersEngineTest.sameMorefTwoVcenters` covers both vCenters.
- **Cluster rows on a host, or the reverse.**
  - A `Target.CLUSTER` row lands only when its uuid equals the queried cluster's `vsanUuid()`. Otherwise it goes to `clusters_unresolved`, never to a host.
  - A `Target.HOST` row resolves only through `nodeToHost`. A cluster uuid misses and is dropped.
  - Landing types go to the cluster only on the exact cluster uuid, and to a host only when exactly one member of that cluster has the node uuid. Anything else is `entities_unparsed`.
- **Instance position.** Every fixture's part count matches its form:
  - `vsan-tcpip-stats` is 2 parts, instance = stack.
  - `vsan-vnic-net` is 3 parts, instance = vmk, stack dropped.
  - `vnic-rdt-network-latency` is 2 parts, instance = vmk.
  - Empty parts and `*` are rejected.
- **Unparsed ids in logs.** The landing WARN carries the type and part count only, and the test asserts the id is absent. The malformed WARN carries only a count. The only server values logged are well-formed node and cluster uuids, as in Build 1.
- **Bucket rule.**
  - Marks are committed only in `flush()`, after every `pushStats` of the cycle came back clean. A failed push skips the commit.
  - A cut cycle pushes what completed, then commits under the same rule. A fatal error throws before `flush`.
  - Dedup compares per (entityRefId hash, catalog position) on the caller thread only.
  - `labDefaultTiers` cycle 2 pushes 0.
  - Hash collisions: same-width collisions share marks, which the design accepts (~10^-10); different-width collisions reset the slot, never skip. The marks measure ~0.7 MB at the 70-cluster example.
- **Learned-empty.**
  - `isEmptyEcho()` requires an echo with no entities and no malformed ids. Faults, caps and unreadable bodies never reach `empty()`, and reset the count.
  - Core types are exempt through `learnsEmpty()`. `ioinsight` is exempt from both kinds of learning and logs its unavailable fault once.
  - An empty re-probe re-learns at once (count held at 3).
  - The offset is per (cluster, type).
  - A reconfigure builds a new `CycleEngine`, so learned state never outlives a settings change.
- **Crash-the-cycle.**
  - `VirtualMachineError` and thread-kill handling are unchanged from main; only constructor arguments were added.
  - A cluster-map read failure is caught and degrades to "no cluster rows this cycle". `SimpleJson` is null-safe, so the new parse paths have no `RuntimeException` route.
  - Pool shutdown, deadline cut and rotation are unchanged.
  - The cap stays 4 MB wire / 8 MB decoded. The largest new body on the lab is 64 KB decoded (W1 is the remaining gap here).
- **Secrets (RULE-008).**
  - No new log path touches credentials, the session header or the view id.
  - The `exclude_types` WARN echoes only id-shaped tokens.
  - The new `toString` fields are tier flags and a count.
- **Build 1 identity.** The collector kind (`vcenter`, `cluster_scope`) and account identity (`vcenter_host`, `cluster_include`) are untouched in describe.xml and in the adapter.
- **Uniqueness-flag trap.** It does not apply: no foreign `ResourceKey` is built, and pushes go by resource id.

## If shipped as-is

Data lands correctly on hosts and clusters. The pak's own overview tells operators there is no cluster tier. A single misbehaving optional type on a one-cluster account shows the account DOWN every cycle while its metrics keep arriving.
