# vsanperf build 11 review (Build 2 complete: host, cluster, disk and VM tiers, streaming parse)

- **Adapter:** `content/sdk-adapters/vsanperf` (branch `build-10-host-cluster-tiers`, uncommitted tree, diffed against `main` = v1.0.0.9)
- **Reviewer:** `sdk-adapter-reviewer`, 2026-11-07
- **Design:** `knowledge/designs/vsanperf-mp-v2.md` (body plus its one dated addendum, "P2 measured"; the brief mentions three addenda, the file has one), `vsanperf-mp-v1.md` where v2 is silent
- **Verdict:** **CHANGES REQUESTED**. 1 BLOCKING, 3 WARNING, 6 NIT

The build is careful work. Keys, identity, the streaming parser, the bucket rule, and the W1 failure isolation all hold up under an independent check. The one BLOCKING finding is in the VM tier: the build dropped the design's periodic re-read of the VM device list. A virtual disk moved between two VMs therefore keeps landing on the old VM with no end.

## Independent re-runs

| Claim | Re-run | Result |
|---|---|---|
| validate-sdk passes, 9.0 and 8.18.7 | `validate-sdk` with `--sdk-compat-jar` set to the 8.18.7 and 9.1.1.0100 jars in `/mnt/holding/vendor/` | **Confirmed.** `OK`. 9.0 leg: javac 17, --release 17. 8.18.7 leg: --release 11. The 9.1.1.0100 leg is skipped because it needs JDK 25 and only 17 is installed. That leg is CI's job (RULE-019). |
| build-sdk `vcfcf_sdk_vsanperf.0.0.0.11.pak` | rebuilt into the scratchpad | **Confirmed.** `adapters.zip` is 249,742 bytes, and its entry list and sizes match the author's `dist/` pak exactly. All 75 classes are class-file version 55 (Java 11). The adapter tree was unchanged after every run (checked by hashing status and diff). |
| pak-compare 0 BLOCKING / 1 WARNING against a rebuilt 0.0.0.9 | 0.0.0.9 rebuilt from `git archive main`, then compared | **Confirmed.** `0 BLOCKING, 1 WARNING, 1 INFO`. W1: identifier count 13 vs 7 (the six new settings, expected). I1: manifest description. |
| `ci/run_java_tests.sh`, 13 classes pass | re-run, then each class run on its own | **Differs (environment).** 12 of 13 pass. `ClientFakeServerTest` failed 7 of 7 runs at `oneDeadlineAcrossRetries` ("slowNotAuthOnce: the repeat was attempted: want <2> got <1>") with load average ~26 on 4 cores. The script stops at that class. Its four later methods (`clusterTierCallAndEcho`, `vmReadTwoPages`, `queryDisksForVsan`, `truncatedStreamNotRetried`) pass when called directly. Verdict on the flake: N1. |
| 451 keys against the design tables | my own script: the v2 "Metric tables" parsed (label, Ops key, per-mille) and compared with `EntityType.java` (group, IdForm instancing, leaf, per-mille) | **Confirmed.** 30 types, 390 rows, 0 differences. 33 types and 451 keys in all (core 61, host 149, cluster 189, disk 31, vm 21). |
| Build 1 keys unchanged | the 61 `m(...)` rows of `main:EntityType.java` against the first 61 now; `ROOT`, `statKey`, group names and pNIC instancing | **Byte-identical.** The only difference is the enum terminator `)))` changing to `));` on the last core row. |
| Account and collector identity unchanged | `describe.xml` of the built 11 and 9 paks, parsed | **Confirmed.** `vcenter_host` and `cluster_include` are identical, and so are the collector's `vcenter` and `cluster_scope`. The six new settings are `identType 2`, with defaults true / true / "" / false / false / 3, and labels as in the design's Settings table. No `<SymptomSets>` (dimension 13 does not apply). |
| 38 new fixtures match provenance | `cmp` of every fixture against `reference/docs/extracted/vsan-perfsvc-json/`; every name grepped in the PROVENANCE files; sha256 prefixes in `tests/fixtures/README.md` recomputed | **Confirmed.** 46 of 46 fixtures byte-identical (8 from Build 1, 38 new), all listed, 46 of 46 sha prefixes match. |
| Calls 26/23 default; 33/28 all tiers on the VM cycle | `TiersEngineTest`, `DiskVmEngineTest` output | **Confirmed in the tests.** All tiers at N=3: `[30, 30, 33, 25, 25, 28, ...]`. Default tiers: 26, 26, 26, 23. Not live. |
| Compact marks ~716 KB, VM tier 21.2 MB | `WatermarksTest` | **Confirmed.** Default: measured 714,784 B (the estimate is 705,400 B). VM tier: measured 21,211,648 B, but the estimate is 14,588,448 B (see N4). |
| Streaming and tree parses identical on four captures | my own probe: both parsers on **every** perf capture; the gzip stream and the plain text cut at ~400 offsets each; 20 constructed edge cases | **Identical on all 29 perf captures**, not just four. No cut ever returned a result. Edge cases are in the hunt section. |

## Registry check (`knowledge/context/defects.md`)

No open defect names vsanperf in `Affects:`. The open defects are DEF-004 (vcommunity-os), DEF-019 (factory:extractor) and DEF-025 / DEF-026 (compliance). There is nothing to re-assert and nothing to propose for closure.

**Registration candidates** if they survive acceptance: B1, and W2.

## Build 10 findings: verified

| Finding | Status |
|---|---|
| B1: `docs/overview.md` described Build 1 | **Fixed.** Rewritten: five tiers, 33 types and 451 keys, all three stitch targets with their join keys, unresolved counters, optional-type isolation, learned-empty rules, limitations. Nothing in it contradicts the code. |
| W1: an optional-type failure failed the cluster and the cycle | **Fixed, with a test.** A cluster is FAILED only on a core-type failure, on `ManagedObjectNotFound`, or when every call failed. Optional failures go to `optional_calls_failed`, `PERF tier failed=`, `last_error`, and one WARN per (cluster, type) per host-map refresh. `DiskVmEngineTest.optionalFailureDoesNotFailTheCycle` covers the one-cluster case, and shows that a core failure still fails the cluster and the cycle. The "every call failed" branch is reachable only when `exclude_types` removes the core types. The code is correct there; it has no test of its own. |
| W2: `docs/installing.md` was missing the settings | **Fixed.** Six rows, plus the upgrade note. |
| W3: the generated landing page names no stitch target | **Open, carried.** It is the tooling generator gap, tracked as factory issue #310. See W3 below. |
| N1: fault-learned types re-probed without the spread | **Fixed.** `LearnedTypes.learn` adds `offsetMs`. |
| N2: back-to-back cluster-map reads; misleading WARN | **Fixed.** Every successful read sets `opsClustersMissRefreshCycle = cycle`. When the list read failed, the WARN names that as the cause. |
| N3: "assumed, unread" wording | **Fixed.** The OpsHostMap doc, README and REFERENCE say "read in P2, live read-back at T5". The remaining CHANGELOG line is historical. |
| N4: describe comment typo; stale README line | **Fixed.** A new stale class doc is N5 below. |
| N5: the malformed-id WARN was not rate-limited | **Fixed.** `malformedWarn`, once per type per day, carrying only a count and the part count. |

## BLOCKING

### B1. The VM device list is never re-read on a schedule, so a disk moved between two existing VMs keeps landing on the old VM (`CycleEngine.java` 830-845, `plan()`)

The VM read is triggered only when:
- `st.vms == null`;
- devices are needed and the cached read has none;
- or there is an instanceUuid or path miss, at most once per 12 cycles.

v2 §VirtualMachine, "Device-list caching", requires trigger **(b)**: "again for that cluster every 12th VM-tier run of that cluster". The build leaves it out. `README.md` and `REFERENCE.md` describe the narrower behaviour ("re-run only after a miss"), but the CHANGELOG does not name it as a deviation from the design.

**Probe.** All tiers, N=1, `virtual-disk` answers limited to paths the device pages place, 40 cycles: cumulative VM reads `[1, 1, 1, ..., 1]`. One read, never repeated. In the same run the disk map re-read at cycles 13, 25 and 37, as designed.

**Consequence.** Some changes produce no miss at all, so the stale map stands until the account is reconfigured or the collector restarts:
- **A VMDK detached from VM A and attached to VM B**, both VMs still in the cluster map:
  - its perf path is unchanged and still maps to A;
  - B's `virtual-machine` and `vscsi` ids resolve, so they trigger nothing.
  - Result: B's `virtual-disk` metrics are pushed onto **VM A's** VirtualMachine, under A's old bus position.
- **A disk moved to another controller or unit on the same VM**: it keeps the old `Virtual Disk:scsiN:M` instance. If two disks swap positions, each one's data is labelled with the other's position.
- **A path seen on two VMs at read time** (for example a backup proxy's HotAdd during the read) becomes `UNPLACEABLE`. `UNPLACEABLE` never sets `vmMiss`, so that disk stays in `vdisks_unresolved` indefinitely.

Data that lands on the wrong foreign object and stays there is the dimension 5 failure (skill §"ARIA_OPS stitching identity", "silent data corruption"; `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`, "never pushed under a guess"). Trigger (b) is the design's bound on it.

**Fix:**
- Add a per-cluster VM-run counter (or `vmReadCycle`) to `ClusterState`.
- In `plan()`, set `p.vmTrigger = "refresh"` when `p.vmRun` and the cluster has had 12 VM runs since its last read. Count from the attempt, as `diskReadCycle` does.
- Add a `DiskVmEngineTest` case: N=1, a fixture with no misses, assert a second VM read at cycle 13.
- Optional: also let an `UNPLACEABLE` path set `vmMiss`, so an ambiguity from HotAdd clears at the next rate-limited read.

## WARNING

### W1. VM reads run on up to every worker at once, outside the one-VM-call permit (`CycleEngine.readVmInventory` ~1600; `VsanJsonClient.readVms`)

`vmPermit` covers only the VM-type `queryPerf`. The lazy VM read runs on whichever worker reaches it.

**Probe.** 4 clusters, 4 workers, all VM runs, VM tier on: `max concurrent VM reads=4`.

Each read holds one RetrievePropertiesEx page as a full `SimpleJson` tree: 50 VMs, ~1.2 to 1.6 MB decoded, 5 to 10x as a tree.

v2 §Heap budgets "VM read page ... 6 to 12 MB, **one page at a time**" (Sizing requirement 5). That line is inside the "+ VM ~44 to 50 MB" total against the 65 MB budget (D6). Four pages at once add 18 to 36 MB, which goes past the budget. This happens exactly when every cluster reads at once: the first VM runs after a start, and a reconfigure.

**Fix:** take the VM permit (or a second one-permit semaphore) around `readVms`. Wait time goes into `vm_permit_wait_ms_max`. Add a probe-style test like `oneVmCallInFlight`.

### W2. A disk map whose every host call fails is re-read every cycle (`CycleEngine.plan()` 806-807; `readDisks` returns `null`)

`plan()` triggers "refresh" whenever `st.disks == null`, and that check comes before the rate limit. When every host's `QueryDisksForVsan` fails, `readDisks` returns `null` and `st.disks` stays `null`. The comment at 817 ("a host that always faults cannot drive a read every cycle") is therefore false for the all-fail case.

**Probe.** Every host faulting, 14 cycles: cumulative calls `[5, 10, 15, ..., 70]`, 5 per cycle. Only one WARN was written (good). At the 70-cluster example this is 420 calls per cycle. Under the per-vCenter ~7 calls/s hypothesis (MAP test 7) that is ~60 s added to every cycle, which pushes the default tiers past the 240 s deadline. A privilege the read-only role lacks, or vsan-health being down, would cause it.

**Authority:**
- v2 §Failure handling: "`QueryDisksForVsan` faults ... retried at the next refresh".
- §HostSystem disk-map cadence: "at most once per 12 cycles per cluster, so a permanently unmappable disk cannot drive a refresh every cycle".

The VM read has the same shape (`st.vms == null` means a read on every VM run). It is bounded by N and costs one call per cluster, so it matters less.

**Fix:**
- On total failure, store an empty map, or gate the `st.disks == null` trigger on `cycle - st.diskReadCycle >= OPS_REFRESH_EVERY` after the first attempt.
- Keep "change" (host set) as it is.
- Add a test: every host faulting, at most one read per 12 cycles.

### W3. The landing `docs/README.md` and `docs/inventory-tree.md` still name no stitch target (dimension 11; carried from build 10)

The pak now stitches onto three foreign kinds, VirtualMachine being new. The generated landing page names none of them; it links `overview.md` only as "cross-adapter notes". That is buried but present. The generator gap belongs to `tooling` and is open as factory issue #310. The author cannot fix it inside the pak.

**Fix:** tooling, #310. No pak change is needed beyond what B1 of build 10 already delivered.

## NIT

- **N1. The `ClientFakeServerTest.oneDeadlineAcrossRetries` flake is a timing tolerance, not a race.** A probe with budgets of 500 / 900 / 1500 ms, at load ~26 on 4 cores:
  - `slowNotAuthOnce`: at 500 ms the deadline is spent during re-login ("ServiceInstance content: no complete answer within 15 ms"), so the repeat is correctly not sent. At 900 ms and 1500 ms it is sent.
  - The client's one-deadline-across-retries behaviour is right in every case.
  - The test leaves only ~150 ms for Login plus ServiceInstance content on the fake server. It predates this build (it is on `main`).
  - Because it aborts the class, it hides four build 11 methods.
  - **Fix:** budget 1,500 ms with the 350 ms sleeps; assert `perfCalls >= 1`, HttpTimeoutException, and `took <= budget + 100`; assert `perfCalls == 2` only for `slowResetOnce`, which needs no login.
- **N2. `VsanJsonClient.queryPerf` 475-478: the `GZIPInputStream` is built outside the try.** A gzip body shorter than the header, or not gzip at all ("Not in GZIP format", `EOFException` on an empty body), escapes as a plain `IOException`. `isTransport()` treats that as a transport failure, so the call is **re-sent once**, against review N4 of Build 1 ("an answer that is not usable is not re-sent"). `last_error` then carries a message with no type, for example `host-domowner: null`. No data is affected.
  - **Fix:** construct the stream inside the `try` and map an `IOException` there to `Unreadable`.
- **N3. `readDisks` never records why a host failed.** The WARN says "QueryDisksForVsan failed on N host(s)", with no fault class (dimension 6, diagnosability).
  - **Fix:** carry the first failure's class (and `faultClass` for a `VsanFault`) into `IdentityDone` and the WARN. The message stays out, since it is server text.
- **N4. `marks_bytes_est` under-reports the VM tier by ~31%.** Estimate 14,588,448 B against measured 21,211,648 B (`WatermarksTest`). v2 §Logging makes `PERF cycle marks_bytes_est` the production twin of T4's heap reading.
  - **Fix:** correct the per-entity constant in `Watermarks.bytesEstimate` so the VM-tier example lands within ~10%.
- **N5. Stale class doc in `VsanPerfAdapter.java` 22-29.** It says "host and cluster tiers since build 10" and "HostSystem and ClusterComputeResource". The disk and VM tiers and VirtualMachine are missing.
- **N6. `OpsHostMap.load`: a row seen on two pages marks its MoRef ambiguous.** Offset paging over a list that changes mid-read can return the same row twice. The VM list is now 34 pages at the example, with VM churn. The result is a VM dropped for up to 12 cycles. Nothing is misplaced.
  - **Fix:** a repeat with the same `identifier` is not ambiguous; only a different id for the same MoRef is.

## Hunt list: proven safe

**Streaming parser** (`JsonStream`, `PerfParser.parse(InputStream)`):
- 29 of 29 perf captures give identical rows, series, samples and timestamp/value bits through both parsers. The author claimed four.
- Every gzip and text truncation threw `Unreadable` (or the probe's own header `EOFException`, which is N2's path in production); none returned a result.
- The result is built only after `]`, then EOF, so a cut stream never leaks a partial response.
- Edge cases:
  - exponents (`1.5e3`, `2E-2`, `-0.5e+2`): same as the tree parser;
  - `None,None`: no sample;
  - nested arrays to depth 64, with depth 70 refused;
  - `|` and `:` inside ids: wrong part count counted as malformed; a path with `:` kept whole;
  - `\u` escapes, duplicate keys (last wins), elements that are not objects: counted as malformed.
- The stream parser is stricter than the tree parser on trailing garbage, `1.2.3`, raw control characters and depth. That is the safe direction, and production uses only the stream.
- One divergence: `"values":7` (a number) gives a sample in the tree parser and none in the stream parser. Vendor output is always a string; the stream's behaviour is the safe one.
- The 16 MB wire cap applies through `CappedBody(okCap)` and surfaces as `OverCapException` with the cap. There is no decoded cap, as the design specifies.

**Bus position** (`VmInventory`):
- A missing `controllerKey`, an unknown controller type, or a bus/unit out of range packs to -1 and becomes `UNPLACEABLE`, counted and never guessed.
- Two disks with the same unit on different controllers or prefixes pack to different values.
- A path on two disks, a 64-bit hash collision inside the map, or an instanceUuid on two VMs becomes ambiguous or is dropped.
- The prefix table matches v2 exactly.

**Disk-to-host map** (`readDisks`):
- A uuid seen on two hosts is dropped.
- A host with no `vsanSystem` is skipped, with no call made.
- A failing host is counted and isolated (`IOException | RuntimeException`), and its disks are unresolved until the next read, as designed.
- Resolution is per cluster: a disk lands only on a member host of the queried cluster, then through the (MoRef, VCID) host map.

**VM tier cadence:**
- `(cycle + hash mod N) mod N` gives each cluster exactly one VM run in every N cycles.
- A change to N rebuilds the engine.
- Empty echoes are counted per VM run, since VM types are called only on runs.
- The permit is acquired with `tryAcquire(left)` and released first thing in the call's `finally`. That covers timeout, interrupt, `VirtualMachineError` and `shutdownNow`.
- The semaphore is per engine.

**Ops VM map:**
- 500 per page, with one retry per page.
- A page that fails twice, or a short list, throws, and the previous map is kept. A partial set is never authoritative.
- A row is indexed only with a VCID equal to this vCenter's `about.instanceUuid`. A row with no VCID is never matched.

**Ops-miss refresh rate limits:**
- cluster: 12 cycles from the last read;
- disk: 12 cycles from the attempt (W2 is the all-fail exception);
- VM vCenter re-read: 12 cycles from the attempt;
- Ops VM list: 12 cycles from the last read. A failed read retries every VM-run cycle, the same posture as the Build 1 host map.

**Stitch identity:**
- A VM MoRef resolves only through this vCenter's (MoRef, VCID) rows. A vCenter UUID change clears the VM, cluster and disk state.
- Cluster rows land only on the queried cluster's uuid.
- A vdisk lands only on the VM the device read names (B1 is the staleness exception).
- No foreign `ResourceKey` is built and pushes go by resource id, so the uniqueness-flag trap does not apply.

**Crash-the-cycle:**
- Optional failures are isolated.
- A core failure still fails the cluster, and on one cluster the cycle (test).
- Every call failing fails the cluster.
- `VirtualMachineError` and `ThreadDeath` are carried to the caller and rethrown after `shutdownNow`.
- A `RuntimeException` in `rows()` fails only that cluster.

**Secrets (RULE-008):**
- The new log lines carry fault classes, counts, MoRefs, uuids and type ids.
- The VM view moId (which embeds the session key) is never logged. The second fault on a recreated view is rewrapped with fixed text, as for the cluster view.
- The `exclude_types` WARN echoes only id-shaped tokens.
- `QueryDisksForVsan` paths carry the `vsanSystem` moId, which is not tied to the session.

**8.18:** the 8.18.7 leg compiled with `--release 11` against the 8.18.7 SDK jar, and the built jar is all version 55. `JsonStream` uses `java.io` only.

**Build hygiene:**
- `adapter.yaml` is version 1.1.0, build 11, with a matching `1.1.0.11 (Unreleased)` CHANGELOG entry.
- Build 10 deviation 3 is resolved.
- The fixtures README lists the new captures with their provenance.

## Not verified here (owed to T3 / T4 / T5)

- A live read-back of ClusterComputeResource and VirtualMachine pushes by this pak.
- The R2 read with `configManager.vsanSystem`: P2 records it, but the shape is not saved verbatim; `InventoryTest` constructs it.
- The non-SCSI bus prefixes and OSA disk ids.
- The 65 MB heap gate (T4).
- The 9.1.1 compile leg (needs JDK 25; CI).

## If shipped as-is

Default tiers behave correctly. The disk and VM tiers are off by default. An operator who turns on the VM tier gets correct data at first. Once a VMDK is moved between two VMs, or onto another controller, that disk's metrics keep landing on the old VM or under the old bus position until the account is reconfigured. With the disk tier on and a vCenter that refuses `QueryDisksForVsan`, every cycle spends one call per host failing.
