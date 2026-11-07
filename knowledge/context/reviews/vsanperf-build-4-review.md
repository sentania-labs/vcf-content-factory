# vsanperf build 4 review (design Build 1)

- **Adapter:** `content/sdk-adapters/vsanperf/` (repo
  `sentania-labs/vcf-content-factory-sdk-vsanperf`, uncommitted working tree
  on the template's `e785ac5`)
- **Build reviewed:** 4 (`adapter.yaml` version 0.1.0, dev-preview pak
  `vcfcf_sdk_vsanperf.0.0.0.4.pak`)
- **Design:** `knowledge/designs/vsanperf-mp-v1.md` with its 2026-11-06
  Addendum
- **Reviewer:** `sdk-adapter-reviewer`, 2026-11-06
- **Verdict:** **CHANGES REQUESTED**: 2 BLOCKING, 3 WARNING, 8 NIT

## Claims check (independent re-runs)

| Claim | Re-run | Result |
|---|---|---|
| `ci/run_java_tests.sh` exit 0, eight classes | ran, JDK 17 | **confirmed**: exit 0; ClientFakeServerTest, ConfigTest, EngineTest, EntityTypeTest, FaultAndRequestTest, InventoryTest, OpsHostMapTest, PerfParserTest "all assertions passed" |
| validate-sdk clean on 9.0 and 8.18.7, 9.1.1 skipped | `validate-sdk` with `--sdk-compat-jar` for 8.18.7 and 9.1.1.0100 (`/mnt/holding/vendor/...`) | **confirmed**: `OK`; main compile `--release 11`; 9.0 leg (2.2 jar, `--release 17`) and 8.18.7 leg (`--release 11`) compile; 9.1.1.0100 leg SKIPPED (needs JDK 25, only JDK 17 here) |
| build-sdk produced `dist/vcfcf_sdk_vsanperf.0.0.0.4.pak` | rebuilt into the scratchpad | **confirmed**: builds; adapter classes byte-identical to the author's pak (`diff -r` of the unpacked jars); class files are major version 55 (Java 11) |
| pak-compare 0 BLOCKING / 1 WARNING vs compliance | `pak-compare <rebuilt pak> dist/vcfcf_sdk_compliance.0.0.0.104.pak` | **confirmed**: `0 BLOCKING, 1 WARNING, 56 INFO`; the WARNING is `[W1] describe.xml: adapter instance identifier count: factory=7, reference=3` (expected: the design's seven settings) |
| no vSAN jar in the pak | unpacked `adapters.zip` | **confirmed**: `lib/` holds only `vcfcf-adapter-base.jar` (buildkit 1.0.24); no vSAN, vim25 or SimpleJson stub classes ship |
| `tests/stubs/SimpleJson` is a verbatim copy, recorded | `diff` against the framework source; `sha256sum` | **confirmed**: identical; `tests/stubs/README.md` records path and sha256 prefix `501451fe843d426a` (matches) |

Side effect to disclose: `build-sdk` regenerates the adapter's generated
docs in place (`docs/README.md`, `docs/inventory-tree.{md,svg,excalidraw}`,
`REFERENCE.generated.md`, `CHANGELOG.generated.md`). My rebuild rewrote them
from the same describe.xml and adapter.yaml with the same buildkit, so the
output is the author's; no hand-written file was touched.

## Registry check (`knowledge/context/defects.md`)

No open defect names `vsanperf` (open entries: DEF-004 `vcommunity-os`,
DEF-019 `factory:extractor`, DEF-025 and DEF-026 `compliance`). Nothing to
re-assert or close. Registration candidates if they survive acceptance:
W1, W2, W3 below.

## Author's deviations: verdicts

1. **JDK `HttpClient` on `getPlatformSslContext(vcenter_host)` instead of
   `HttpClientBuilder`. Accept.** The skill (§Target-system TLS) names
   `getPlatformSslContext(dialledHost)` as the sanctioned way to get a
   name-checking context of one's own, so certificate behaviour equals the
   framework's. The reasons hold: the template's bounded body cancels every
   non-200 body unread, and the design (§Response handling) requires reading
   the HTTP 500 fault body and never re-sending a fault. The framework itself
   runs on `java.net.http` on 8.18, so the module is there. See N4 for one
   place where the retry rule leaks.
2. **Whole cycle in `rediscover`. Accept, with W1.** It is **not** the
   established pattern: compliance discovers a `ComplianceWorld` resource
   and runs its cycle in `collect()` for it; no pak in this repo has pushed
   self-metrics onto its own adapter instance. It does not break on 8.18
   (the hook is framework-driven and the source compiles against 8.18.7 at
   `--release 11`). What a failed cycle looks like on the account row
   depends on a fact the repo does not establish (W1).
3. **Ops map not re-read every cycle for a host still missing after a
   refresh. Accept.** Bounded and sensible at scale: a new (MoRef, VCID) miss
   still forces a refresh (`CycleEngine.java:645`), a host-set change forces
   one (`:354`), and a stuck miss is retried on the 12-cycle cadence. The
   operator-facing latency (up to an hour) is undocumented (N7).
4. **Per-sample duplicate suppression. Accept.** Equivalent to the design's
   per-series rule: a sample is pushed iff its own time is newer than the
   entity's mark, and the mark is the newest pushed (`CycleEngine.java:579-592`).
   A lagging metric whose newest value is older than the mark was either
   already pushed or is older data. See N5.
5. **Failure cause preserved, Stop Collecting ends the cycle like the
   deadline. Accept for the stop path; the DOWN claim is unproven (W1).**
   The cause chain survives (`VsanJsonClient.java:557-559`,
   `CycleEngine.java:308`, `VsanPerfAdapter.java:301`) and
   `Failures.isUnreachable` walks it, but DOWN reaches the account row only
   if the platform collects the instance resource.

## BLOCKING

### B1. A `VirtualMachineError` (or any throwable outside the caught set) in a worker is swallowed and the cluster is counted OK

- **Where:** `CycleEngine.java:490-499` (tasks go through `pool.submit`; no
  `Future.get()` ever runs) and `CycleEngine.java:654-753` (`clusterTask`
  catches `VsanFault`, `HttpTimeoutException`, `InterruptedException`,
  `IOException | RuntimeException`; the outer `finally` posts
  `ClusterDone(outcome)` with `outcome` still `OK`).
- **Authority:** design §Failure handling, last line ("A thread kill or
  `VirtualMachineError` is rethrown, never swallowed (framework convention,
  `tier2_architecture.md` 2026-10-24 entry)"); reviewer dimension 3 (a
  swallowed error that yields a pass is dimension 1 in disguise).
- **Proof (probe, not a guess):** an engine run against the lab fixtures
  with `queryPerf` throwing `OutOfMemoryError` for `host-domowner` returned
  normally with `ok=1 failed=0 timedOut=0 perfCalls=1 seriesPushed=0
  failure=null lastError=null`. The `FutureTask` holds the error; nobody
  reads it.
- **Operator impact:** the collector runs out of heap mid-cycle (risk R5,
  the 65 MB budget is unproven on Cloud Proxies), the cluster's data is
  silently missing, and `Collection|clusters_ok` and `last_error=none` say
  the cycle was healthy. The same path hides any `RuntimeException` thrown
  between the inner `try` and the outer `finally` (`rows()`, `put`).
- **Fix:** catch `Throwable` at the task level in `clusterTask`. For a
  `VirtualMachineError` or thread kill, carry it in `ClusterDone` (a
  `Throwable fatalError` field) with outcome `FAILED`, and have `handle()` on
  the caller thread rethrow it after the pool is shut down (the framework
  then ends the cycle). Any other throwable sets outcome `FAILED` with a
  credential-free warn. Add an `EngineTest` case: an OOM in `queryPerf`
  makes `run()` throw it, and a `RuntimeException` in the post-call path
  counts the cluster as failed.

### B2. The ContainerView moId (vpxd session key) can reach the account row, the `last_error` property and the cycle log

- **Where:** `VsanJsonClient.java:333-339`. On the second view-read fault
  (`mayRecreateView=false`) the original `VsanFault` is rethrown. Its message
  is built from the server's `faultstring` (`VsanFault.java:101-106`, up to
  200 chars). From there it goes to `CycleEngine.java:338`
  (`res.failure = "vSAN cluster inventory read failed: " + e.getMessage()`),
  then the INFO summary line (`:411`), `Collection|last_error`
  (`VsanPerfAdapter.java:296`, a persisted property on the instance) and the
  exception thrown to the framework (`:301`), which shows it on the account
  row.
- **Authority:** design §Logging, `PERF inventory` row ("Never log the
  ContainerView moId: it embeds the vCenter session key (MAP)"); design
  §Failure handling ("the fault text is logged without the view moId"); skill
  §Pushing data ("`collect()` must throw messages free of credentials,
  session ids and tokens; the framework's redaction is only a backstop");
  RULE-008 spirit. The repo's own `REFERENCE.md` §Logging claims "No line
  carries a password, session id or the ContainerView id", which this path
  contradicts (dimension 11: docs that contradict behaviour).
- **Why it is real:** vim25 JSON faults echo the requested object in
  `faultstring` (MAP "vim25 inventory over JSON": `"faultstring":"Managed
  object type 'HostSystem' doesn't have a '...' property."`). The view moId
  is `session[<uuid>]<uuid>` (MAP line 262), so a view fault naming its
  object puts the session key in the text. The framework's
  `redactCredentials` patterns do not match `session[...]`. The fake-server
  test uses the faultstring `"The object has already been deleted"`, which
  carries no moId (`ClientFakeServerTest.java:152`), so the suite cannot catch
  it. The first fault is handled correctly (WARN with `faultClass` only,
  `:335`).
- **Note on severity:** the session key is not the 40-char
  `vmware-api-session-id` login token. It is still a session identifier the
  design forbids in logs, and here it lands in the account row and a
  persisted property readable by anyone with Integrations access.
- **Fix:** never propagate a view-path fault's `faultstring`. In
  `readInventory`, rethrow
  `new VsanFault(f.faultClass, "the inventory read on the cluster view failed", f.keys, f.httpStatus)`.
  As a belt, scrub `session\[[^\]]*\][0-9A-Za-z-]*` in
  `VsanFault.describe`. Add a fake-server case whose view fault's
  faultstring contains `vim.view.ContainerView:session[x]y`, faulting twice,
  and assert that neither the log, the thrown message nor
  `Result.lastError` contains `session[`.

## WARNING

### W1. The account-row outcome and the self-metric delivery rest on an unproven platform fact

- **Where:** `VsanPerfAdapter.java:240-303`; framework `VcfCfAdapter.java:1038-1050`
  and `adapterInstanceStatus` (`:3306-3316`).
- **Authority:** `tier2_architecture.md` §Adapter instance status (#223);
  skill §Pushing data; reviewer doctrine (unproven is a finding).
- **What:** `rediscover` throwing is logged by the framework as
  `rediscovery failed (non-fatal)` **with the full stack trace at WARN on
  every failing cycle** (no streak suppression on that path). Then:
  - if the platform's `resources` list holds the adapter instance,
    `collect()` rethrows the failure, `mapCollectException` maps it, and the
    account row shows DOWN or ERROR as the author claims;
  - if it does not, `attempted == 0` and the row shows **ERROR** (never
    DOWN) with the text "Resource discovery failed and there was nothing to
    collect: IOException: ...". That is misleading for an unreachable
    vCenter.

  The author's own Javadoc hedges ("if the platform lists it"). Nothing in
  `knowledge/` records which case holds, and no pak in this repo has
  delivered `Collection|*`-style self-metrics onto its own instance through
  the collect result, so the design's Q4 delivery is unproven too.
- **Fix:** make both checks explicit T5 acceptance criteria on all three
  platforms: (a) `Collection|*` and `last_error` read back on the instance
  resource; (b) the account row status and text with vCenter unreachable,
  and with wrong credentials. If (b) shows ERROR or "Resource discovery
  failed", either run the cycle from `collect()` on the instance resource
  (when it is listed) or adjust the docs and the DOWN claim. Record the
  per-cycle WARN stack trace as a framework follow-up (streak suppression
  on the rediscover path), not a pak change.

### W2. The landing `docs/README.md` and the inventory tree say nothing about the HostSystem stitch

- **Where:** `docs/README.md` (generated: "Resource kinds: 0", no stitch
  section) and `docs/inventory-tree.md` (empty tree). The stitch is stated
  only in `docs/overview.md`, the repo `README.md` and `REFERENCE.md`.
- **Authority:** reviewer dimension 11 (buried-but-present is a WARNING;
  unifi v1.1.0.11 origin).
- **What:** the pak's only user-visible output is keys on VMWARE HostSystem,
  and the docs landing page reads as a pak that does nothing. The
  `cross_mp_edges` generator section (compliance, synology) is for
  relationship edges, not ARIA_OPS metric stitching, so the author has no
  supported way to express this. That is a TOOLSET GAP.
- **Fix:** route a TOOLSET GAP to `tooling`: an `adapter.yaml` section for
  stitched keys (foreign kind, key prefix, identity) rendered in
  `docs/README.md` and the inventory tree. Re-generate once it lands.

### W3. Design T3 (replay harness) and T4 (heap budget gate, "CI, on every change") are not delivered, and the build does not name the gap

- **Where:** `tests/` (T1 and T2 only); `CHANGELOG.md` 0.1.0.4 entry says
  "T1 and T2 of the design" without saying T3 and T4 are outstanding;
  `README.md` and `docs/overview.md` Known Limitations are silent.
- **Authority:** design §Test plan T3, T4 and D6 (65 MB budget), risk R5;
  skill §Gaps (name them, never hide them).
- **What:** the heap budget is the design's scale safety claim (70 clusters)
  and nothing verifies it. At Build 1 scope on the lab it is not a
  correctness issue, so this is a WARNING rather than a block.
- **Fix:** either add T4 (a fake-vCenter run at 70 synthetic clusters x 6
  hosts x 2 pNICs asserting the heap delta and the series count) before the
  first `v*` tag, or name T3 and T4 as open in the CHANGELOG and README Known
  limitations, and record the decision in the design.

## NIT

- **N1** `CycleEngine.java:513-549`: Stop Collecting takes the deadline
  path, so the WARN says "cycle deadline reached" and the unfinished
  clusters count as `clusters_timed_out`. Say "stopped" when
  `stop.getAsBoolean()` caused the cut.
- **N2** `CycleEngine.java:481, 567-570, 679, 725`: `callStart`/`callEnd`
  are engine fields reset per cycle, but a straggler worker from a cut
  cycle (not awaited after `shutdownNow`) can still update them during the
  next cycle and skew `perf_calls_per_second`. Make them per-cycle objects
  passed to the task.
- **N3** `PerfParser.java:162-172`: "newest" is the last CSV index, which
  holds because `sampleInfo` is ascending in every capture (MAP line 140).
  Choosing the maximum timestamp would not depend on the order.
- **N4** `VsanJsonClient.java:443-451, 495-511`: the parse runs inside
  `retryTransport`, and `isTransport` accepts any plain `IOException`, so a
  deterministic "not valid JSON" or "returned no body" answer is re-sent
  once. The class Javadoc says only a no-answer failure is re-sent. Throw a
  non-transport subclass for parse failures, or parse outside the retry.
- **N5** `CycleEngine.java:591`: the dedup mark is recorded before the push
  result is known, so a bucket in a failed batch is never re-sent. That is
  acceptable for 5-minute data; say so in REFERENCE.md.
- **N6** `OpsHostMap.java:288-291`: every VMWARE HostSystem in Ops is read
  (5000 per page, up to 40 pages) and filtered on the client. The design
  call plan says "filtered to this vCenter by VMEntityVCID". The cost grows
  with the whole Ops estate every 12 cycles; consider a server-side filter.
- **N7** README/REFERENCE: a host the vCenter adapter starts collecting
  later is picked up on the next 12-cycle refresh (up to an hour at 5
  minutes) unless the host set changes. State that next to
  `hosts_unresolved`.
- **N8** `CycleEngine.java:304-341`: the caller-side steps catch only
  `IOException`. A `RuntimeException` there (for example `URI.create` on a
  malformed server moref) escapes `run()` before the self-metrics are
  pushed, and the framework shows the raw message. Catch it into
  `res.failure` with a fixed text.

## Hunt list (asked in the brief): result per item

| Item | Result |
|---|---|
| MoRef resolving under the wrong vCenter | Safe. `OpsHostMap` indexes only rows whose `VMEntityVCID` equals this vCenter's `about.instanceUuid`; VCID-less, id-less and ambiguous MoRefs are never matched, with no name fallback (`OpsHostMap.java:339-359`). The node map comes from this vCenter's inventory; a uuid change clears the map, marks and learned types (`CycleEngine.java:318-324`). Tested (`OpsHostMapTest`). |
| Empty instanceUuid still pushing | Safe. Empty or blank fails the cycle before inventory or push (`CycleEngine.java:311-317`); `OpsHostMap.load` refuses it too. |
| Pushed key names vs the design's 61-key table | Match. Scripted comparison of `EntityType` against the design tables: all 61 (type, label, key, per-mille) tuples equal. `EntityTypeTest` pins it against the copied table. |
| Self-metric names | Match `describe.xml` `Collection` group (11 metrics, `last_error` as property). |
| Instanced key format | `vSAN Perf\|pNIC:<nic>\|<leaf>` (`EntityType.java:171-175`); a pNIC id that does not split into exactly two non-empty parts, or any `*`, is skipped and counted (`EntityRef.java`). |
| One cluster fault or timeout failing the cycle | Safe. Per-cluster outcome; the cycle fails only when every in-scope cluster failed, on NotAuthenticated after re-login, or on login, inventory or Ops-map failure, per the design table. |
| `VirtualMachineError` swallowed | **Found: B1.** |
| Unbounded response body | Safe. 4 MB wire, 8 MB decoded, 64 KB fault cap; a declared over-cap Content-Length is cancelled before reading (`CappedBody`). |
| Pool that never shuts down | Safe. `shutdown()` after submit; `shutdownNow()` plus cancel on cut, fatal or abnormal exit; daemon threads (`CycleEngine.java:501, 526-535, 885`). Straggler side effect: N2. |
| ContainerView session key in a log or exception | **Found: B2** (double-fault path). The single-fault path and the PERF lines are clean. |
| Secrets (RULE-008) | Clean. The password is private in `VsanPerfConfig`, only in the Login body, and `toString` omits it and the principal. The token is only in a header. No config message echoes a value. Fixtures were scanned (no `session[`, password or session header). |
| `None` token, all-None series | Correct. A series with no number yields no sample (never 0); blanks, junk and non-finite numbers are skipped; tested (`PerfParserTest.noneTokens`). |
| Per-mille conversion | Correct. raw/10 on exactly the 10 pNIC labels, all of them in PY `PERMILLE` (`vsanhostmetrics/app/perfsvc.py:907`); no DOM label is converted. |
| NotAuthenticated retry bounded to one | Correct. One re-login and one re-run per call; a second NotAuthenticated is thrown and ends the cycle as fatal (`VsanJsonClient.java:468-488`, `CycleEngine.java:690-694`); concurrent workers share one re-login (`relogin` compares the stale session). |
| 8.18 compile target | Correct. Main compile `--release 11`, class files version 55, 8.18.7 compat leg compiles at `--release 11`. |
| describe.xml vs the design Settings table | Match: keys, labels (resources.properties), defaults (4, 30, 0, false), `cluster_include` `identType="1"`, `vcenter_host` identity (no `identType` = 1), the rest `identType="2"`; enum false/true. |
| RULE-016/017 provenance of fixtures | Correct. Eight files byte-identical to the committed `reference/docs/extracted/vsan-perfsvc-json/`; `tests/fixtures/README.md` cites the folder's README and PROVENANCE, and its sha256 prefixes match. |
| SimpleJson stub recorded, no vSAN jar | Correct (claims table). |

## If shipped as-is

An operator would see a healthy-looking instance (`clusters_ok`,
`last_error=none`) while a worker out-of-memory silently drops a cluster's
data. A vCenter view fault that hits twice would put the vpxd session key
on the account row and in a stored property.
