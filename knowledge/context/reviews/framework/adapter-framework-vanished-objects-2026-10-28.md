# Framework review: vanished objects (unifi#20) + Cloud Proxy ambient credential (compliance#58), buildkit 1.0.22

- **Branch:** `vanished-objects-notexist` (worktree `.claude/worktrees/agent-a2a3f92fea84a47a7`), commits e833918, 8e62a20, 68207d3 on 12fcb4a
- **Area:** `src/vcfcf_managementpacks/adapter_framework` (`VcfCfAdapter`, `stitch/AmbientCredential`, `stitch/SuiteApiStitcher` Javadoc), `buildkit.py` version
- **Reviewer:** framework-reviewer, 2026-10-28
- **Verdict: CHANGES REQUESTED** (1 BLOCKING, 4 WARNING, 4 NIT)

## Checks re-run

| Check | Result |
|---|---|
| Merge with current main (c1986ef) | `git merge-tree`: clean |
| Merge with open PR #281 (1.0.21) | conflicts in `buildkit.py` (`BUILDKIT_VERSION`) and `tier2_architecture.md`; expected, whoever lands second rebases |
| Framework compile, `javac --release 11` against 2.2 | clean |
| Java tests, all `adapter_framework/test` mains (2.2 runtime) | VanishedResourceTest 51/51, AmbientCredentialTest 46/46, AdapterInstanceStatusTest 178/178, VcfCfAdapterTest 79/79 (from a jar with the build manifest), CertificateReview 183, CertificateNames 235, HttpClientBuilder 13, ManagedHttpClientCopy all pass (with `jdk.httpclient.allowRestrictedHeaders`), the stitch suites 165/18/8/81 |
| VanishedResourceTest + AmbientCredentialTest on the 8.18.7 and 9.1.1.0100 SDK jars at runtime | 51/51 and 46/46 on both (9.1.1 on JDK 25.0.5) |
| Compat pass, `build-framework.sh --compat-only`, `VCFCF_SDK_COMPAT_REQUIRED=1` | rc 0. 9.0 (2.2, javac 17, `--release 17`), 8.18.7 (javac 17, `--release 11`), 9.1.1.0100 (javac 25.0.5, `--release 25`) |
| pytest, CI flags, on a copy of the branch with the pak clones linked | 3210 passed, 8 skipped, 0 failed. In the bare worktree: 12 failures, all "artifact source not found: content/sdk-adapters/..." (no pak clones there), environmental |
| Seven-package validate chain | all rc 0 |
| `validate-sdk` unifi, synology, compliance against the branch framework | all OK (no hook-name collisions) |
| SDK bytecode, all three jars | `ResourceKey`, `ResourceIdentifierList`, `ResourceIdentifierConfig` identical; `StateChangeEnum` same five values; `AdapterCache.getMonitoringResources/getStoppedResources`, `AdapterBase.changeResourceState`, `adapterCache` field, `getAdapterInstResource` present on all three |

## Claims checked against the evidence doc (`knowledge/context/sdk/vanished_object_lifecycle.md`)

| Claim | Verdict |
|---|---|
| `changeResourceState(rc, NOTEXIST)` from `onCollect` with the platform's own `ResourceConfig` (§1, §4) | Supported. Only platform copies with a resource id reach `changeStateSafe`. |
| Diff against monitoring + stopped (§4.1) | Supported. |
| Presence by `ResourceKey` equality | **Proven safe** from bytecode, beyond the doc: equality and hash are adapter kind + resource kind (ignore case) + the uniqueness identifiers only, positional, and `addIdentifier` insertion-sorts by (key, value), so order of construction does not matter; name and non-unique identifiers are ignored. Same bytecode in all three jars. |
| 12-cycle default (§2 Dockerized `implicitNotExistingMissedCycles`) | Supported. Note it is cycles, not time: 12 minutes on a 1-minute pak. |
| Empty-enumeration guard (§2 Dockerized) | Supported, but effectively never fires for unifi or synology: both always deliver a World first. |
| "Mark only on a complete, successful read" (§4.2) | **Not met by the default.** See B1. |
| "Mark only the adapter's own source-backed kinds" (§4.3) | Met only with per-pak `notExistingExcludedKinds()`; the default is none. |
| START on reappearance | **Not supported**, and SDK bytecode the doc does not cite argues it is inert. See W1. |

## BLOCKING

### B1. The default treats "a kind was delivered somewhere" as "that kind was read in full", so the current unifi and synology paks mark live objects NOT_EXISTING after a partial read, with no pak change

`VcfCfAdapter.java:640` (`kindsReadThisCycle()` returns null) and `:3699` (`read = declared != null ? declared : enumerated.kinds`).

Authority: the evidence doc §4 point 2, "Mark only on a complete, successful read". Every Broadcom adapter it cites guards partial reads explicitly: vSAN adds failed-vCenter keys to the present set, NSX skips when the instance is down. The doc names the UniFi optional sub-tree as the case a naive diff gets wrong. RULE "unreadable is not invisible", which both paks state in their own Javadoc.

What regresses. The default covers only a sub-tree that fails *completely* (no object of the kind at all). It does not cover a read that fails for one parent while the same kind arrives from another. Both shipping paks swallow such failures and return normally from `enumerateResources`:

- **unifi, multi-site controller.** `SiteReads.readAll` records a per-site `stat/device` failure in `failedSites` and the snapshot build continues (`UniFiAdapter.java` ~1781-1797, "the build fails only when every site fails"). `devicesForSite` then returns `{"data":[]}` (`:1955-1958`). The enumeration still delivers `UniFiSite` for that site plus gateways, switches, ports, APs, radios and WANs from the other sites, so every one of those kinds counts as read and every device of the unreadable site takes a miss. A 401/403/429 site is not asked again for 15 minutes and stays failed. One site losing permissions for the View Only account, or one site's API erroring for an hour (12 cycles at 5 minutes), marks every device of that site NOT_EXISTING. The platform then deletes them after `DELETED_OBJECTS_RETENTION_IN_HOURS`, which is **6 hours on 9.0 devel** (evidence doc §3). History, alerts and group membership go with them. The same shape applies, unverified, to per-device child lists: `port_table` and `radio_table_stats` absent for one switch or AP while the kind arrives from others.
- **synology, per-share NFS probe.** A share whose NFS rule probe fails with a non-auth, non-unreachable error is recorded in `nfsProbeFailed` and is not in `nfsRulesByShare` (`NfsProbes.java` ~175, `SynologyAdapter.java:1822-1823`). The enumeration (`:623-631`) skips it while other exports are delivered, so `SynologyNfsExport` counts as read and that export takes a miss each cycle until it is marked.

Why the framework, not the paks. All three paks float on `BUILDKIT_TAG: sdk-buildkit-v1` (`*/.github/workflows/build-pak-on-tag.yml:53`). The next `v*` tag of unifi or synology picks up 1.0.22 and turns marking on, and no one has to read the release notes first. The release notes say "No pak source change is required" (`.github/release-notes-buildkit.md:177`), and the adoption note in `tier2_architecture.md` reviews unifi and synology without finding either case. A destructive default, keyed to a heuristic two of the three in-tree paks already break, is the global-default leak class (anchor 00d3382): a choice made for one pak's case (UniFi Protect, all or nothing) applied to every pak.

Smallest correct fix. Make marking opt-in on an explicit, per-cycle declaration. With `kindsReadThisCycle()` returning null, mark nothing (counts may still be kept or skipped). A pak gets marking only by returning the kinds it read in full this cycle. Update the hook Javadoc, release notes, skill and `tier2_architecture.md` to match. Add a test: two "sites", one site's children missing and the kind still delivered by the other, then 12+ cycles, then nothing marked under the default. Alternatively, default `notExistingMissedCycles()` to 0. The unifi and synology overrides (failedSites kinds left out, `nfsProbeFailed` left out) then land in those paks with their opt-in.

## WARNING

### W1. The START reappearance path almost certainly never fires, silently, and the docs claim the opposite

`VcfCfAdapter.java:3654-3680`; `tier2_architecture.md:645` ("Marks are kept after the platform stops listing the object, so a return can still be answered").

Authority: SDK bytecode, all three jars. `AdapterCache.update(AdapterConfig)` hands a config's `getAutoDiscoveryResponse()` to `processAutoDiscoveryResponse`, which calls `processNotExistingResponse`. For every `StateChange` of `NOTEXIST`, that method calls `removeMonitoringResource` / `removeStoppedResource`. The adapter-side cache is built to drop a resource once the platform echoes the NOTEXIST back. When it does, `platformKnown()` no longer has the id, `known.get(id)` is null (`:3673`) and nothing is sent. The tracker entry is already removed (`:3666`), so no later cycle retries. Whether the collector sends that echo is not verified, but the method exists for it. The evidence doc does not mention it.

Consequence: recovery from a mark rests entirely on `addNewResource` re-registration, which the evidence doc lists as UNKNOWN. Combined with B1, a false mark is probably permanent until deletion. A real return also logs nothing.

Fix: record `processNotExistingResponse` in the evidence doc. Log at INFO when a marked object reappears and the platform no longer lists it, so the operator sees it. Correct the "marks are kept so a return can be answered" text. Before tagging a pak, run the live devel check the doc already owes: mark one throwaway object, re-deliver it, and watch both START and `addNewResource`.

### W2. Marked tracker entries are never released (memory)

`VcfCfAdapter.java:3719` keeps every `marked` entry after the platform stops listing it, for the life of the adapter instance. Under W1 such an entry can never be used: START needs the platform's `ResourceConfig`. So it is a pure leak of one `VanishEntry` plus a `ResourceKey` per object ever marked, in the collector JVM every adapter shares. It is small for UniFi and unbounded for any churny source.

Fix: drop marked entries whose id the platform no longer lists, or cap them. Test it.

### W3. A first rollout marks every legacy-keyed orphan at once, and the release notes don't say so

Every object in the platform cache whose key no current enumeration produces is counted from the first cycle on 1.0.22. That covers synology objects from before build 34's `diskstation_id` re-key, unifi `<mac>_0` ports from before #23, and similar orphans. All of them are marked about an hour after upgrade and deleted after retention. That is the right outcome, but it is a visible, irreversible sweep. Fix: say so in the release notes and in each pak's adoption note.

### W4. Test coverage misses the partial-read case the feature most needs to refuse

`VanishedResourceTest` has 51 checks, and all cover kind-level absence. No test has the same kind arriving from one parent and missing from another, which is B1. No test covers marked entries after the platform drops the id (W2), or START when the platform no longer lists the object (W1). These are the cases to add with the fixes.

## NIT

- **N1.** `AmbientCredential.isCloudProxy` (`AmbientCredential.java:199-200`) ORs `httpRelayEnabled`, so it overrides an explicit `isUnifiedCloudProxy=false`. `isUnifiedCloudProxy` is the key `CollectorProperties` itself reads, and it is present and false on both 9.x nodes. Let an explicit `false` win, and use `httpRelayEnabled` only when `isUnifiedCloudProxy` is absent (8.18). A false positive on an analytics node only costs the file fallback when no injected credential exists (Test Connection), but the tighter rule costs nothing. I found no other false-positive path. The three analytics nodes in `cloud_proxy_detection.md` read `false`/absent, and a missing or unreadable file keeps the old path.
- **N2.** The `AmbientCredential` class Javadoc still says automation "works on every node role including CP" (`:39`) and is "RBAC-bearing on both primary and Cloud Proxy nodes" (`:66`). That contradicts DEF-006, the CP identity lesson and this change. The `@throws RuntimeException if Crypt decryption fails` at `:373` and `:414` is also stale now that a null decrypt is an `IOException`. The branch touches the file, so fix them here.
- **N3.** `markable` compares `excludedKinds.contains(kind)` case-sensitively, while `ResourceKey` compares kinds ignoring case (`VcfCfAdapter.java:3775`). A casing mismatch fails unsafe: the exclusion is skipped. Compare ignoring case.
- **N4.** The 12-cycle threshold is in cycles, not time. Say so in the hook Javadoc and the release notes (12 minutes on a 1-minute pak). Also sequence the merge with PR #281: both bump `BUILDKIT_VERSION`, and whichever lands second must not move `sdk-buildkit-v1` backwards.

## Proven safe (no finding)

- Guards against a failed or optional read at the cycle level: the enumeration or `rediscover` threw (`discoveryFailure`), a cut or interrupted cycle, the adapter instance failing (`adapterInstanceStatus != null`), the platform list unreadable (a CME from copying the live `HashMap` values view is caught and fails closed), or a hook throwing. Each one skips both counting and marking. The adapter instance, its kind and foreign adapter kinds are never marked.
- Interaction with NO_DATA_RECEIVING and #223/#245: a resource that is enumerated but fails `collect()` is never counted. Objects skipped as marked do not count toward `attempted`, so they cannot trip or mask the all-failed instance rule.
- The skip-collect path only fires for objects this instance marked and has not seen since. A sighting clears the entry before the collect loop, so a returning object is collected that same cycle.
- compliance enumerates only `ComplianceWorld`, which is always delivered. No change there.
- Cloud Proxy change: the check runs only when no override is set and no injected credential exists, before any file read or `Crypt` call. Collection, which carries the injected credential, is unchanged. A null decrypt now throws inside `loadFromPath` and does not fall through to maintenance, so the identity choice is unchanged.
- Stale-zip discipline: there is no `templates/`, `builder.py`, `assembly.py` or `render.py` change, so `CURRENT_TEMPLATE_VERSION` is not in play. `BUILDKIT_VERSION` 1.0.22 is the signal for the paks, and it is bumped.

## If shipped as-is

The next unifi or synology tag silently picks up 1.0.22. One site with an unreadable device list (UniFi), or one NFS share whose probe keeps failing (Synology), for about an hour gets its live objects marked NOT_EXISTING. The platform then deletes them after retention: 6 hours on 9.0 devel, 7 days by default. The START path meant to undo a false mark very likely never runs.
