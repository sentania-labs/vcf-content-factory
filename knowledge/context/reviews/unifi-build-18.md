# UniFi build 18 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/unifi` (repo `sentania-labs/vcf-content-factory-sdk-unifi`)
- **Branch reviewed:** `build-18`, commits `d25e8e8` and `814548b` on `origin/main` `79e5430` (build 17)
- **Built pak (reviewer build, from the branch):** `vcfcf_sdk_unifi_controller.0.0.0.18.pak`
- **Reference pak (reviewer build, `git archive 79e5430`):** `vcfcf_sdk_unifi_controller.0.0.0.17.pak`
- **Scope:** #39 (NVR storage), #15 (uplink tree + traversal), #27 item 4 (parent-qualified names + rename opt-in), #17 (UniFi OS only), #32 (Integrations paths)
- **Date:** 2026-10-28
- **Verdict: APPROVE** (0 BLOCKING, 4 WARNING, 3 NIT)

No `SDK ADAPTER RESULT` block was supplied with the brief; the claims checked
below are the ones in `CHANGELOG.md` 0.0.0.18 and the commit messages.

## Bottom line

Identity is safe. I checked it against the SDK bytecode, not the
CHANGELOG's word: `ResourceKey.compareTo`, `equals` and `hashCode` (9.1.1.0100
SDK) use the resource name only when a key has zero uniqueness identifiers,
and every key this pak builds (`rcOf`, `rb.resource`) carries exactly one
identifier with `isPartOfUniqueness=true`. The renamed objects keep their
ResourceKey and so their history. The rename mechanism is as described:
`AdapterBase.getMonitoringResource(ResourceKey)` calls
`checkIfResourceRenamed` only when `isResourceRenameAllowed(key)` is true
(default `iconst_0`). That method compares the cached name with the
reported one and queues the new name, and `finalizeCollectResult` sends it
via `DiscoveryResult.addRenamedResource` and updates the cached name, so the
next cycle compares equal and nothing churns. Every name is built from the
same snapshot fields in enumerate, relationships and the stitch (the
device's own `deviceDisplayName`, a port/radio/WAN label and a site `desc`).
None of them depends on the uplink parent, so uplink flaps cannot rename
anything. The vmnic stitch edge is intact: the join aliases still use the
bare `dev.name` and port label, and the edge key is `port_key`, unchanged.

`UplinkTree` cannot produce a cycle or an orphan. Parent edges exist only
for pairs that `nests()` allows, so a loop can only be all-switch or
all-AP. The two-state walk cuts every node on a loop. A device below a loop
keeps its parent, which now reaches the Site, and every registered device
gets exactly one `rb.parent` (its uplink device or its Site).

The `::child/recursive` grammar is not invented. The citation checks out
against `knowledge/context/cleanroom-spec/analysis/per-adapter/vmwarevi_adapter3.md:129`
(`VMWARE::HostFolder::child/recursive/preferred`) and the grammar table in
`cleanroom-spec/spec/07-relationships-cross-mp.md:208`. The one gap: the only
captured vendor use pairs it with `/preferred`. No artifact in the repo shows
bare `/recursive`, and none shows whether it means one-or-more or
zero-or-more. The author handled the second point well by enumerating every
optional level as its own path (correct under either meaning). Still, how
it installs and renders is a devel item (W3).

Build 17's alerts and symptoms are byte-identical in the built pak.
describe.xml differs from build 17 only in the traversal block, so every
metric key the content references still exists.

The four WARNINGs are docs and live proof. None is a correctness defect in
the Java.

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass: 12 Java (incl. new `UplinkTreeTest`, `UniFiValuesTest.nvrStorage`, `UniFiIdsTest.childName`, `FailureMappingTest.unifiOsRequired`) and 13 Python (incl. new `test_build18_wiring`). `tests/ci` unittest: 24 OK. |
| Test strength | Mutation-checked in scratch copies, 4/4 killed: loop cut removed from `UplinkTree.resolve` (`twoNodeLoop`); `nests()` letting a switch sit under an AP (`unsupportedNesting`); `nvrStorage` mixing volume total with recording used (`nvrStorage`); `isResourceRenameAllowed()` returning `false` (`test_build18_wiring`). |
| validate-sdk | **Confirmed** `OK`. SDK compat compile ran against 9.0 (`vrops-adapters-sdk-2.2.jar`) and, with the jar supplied from `/mnt/holding/vendor`, **8.18.7: clean**. 9.1.1.0100 could not run (jar is Java 25 class files, local javac 17); javap of that jar confirms `isResourceRenameAllowed()`, `isResourceRenameAllowed(ResourceKey)` and `getMonitoringResource(ResourceKey)` are public there, and also in 8.18.7. |
| build-sdk | Reproduces from the branch; adapter tree left clean (generated `docs/README.md`, `docs/inventory-tree.md` and the SVG regenerate byte-identical to what is committed). |
| pak-compare 18 vs 0.0.0.17 (reviewer-built from `79e5430`) | **0 BLOCKING, 0 WARNING, 1 INFO** (manifest description: the UniFi OS wording). No kind, attribute or identifier changes. |
| Content regression | `content/` (8 alertdefs, 14 symptomdefs, resources.properties) identical between the 17 and 18 paks. describe.xml diff is the traversal block only. Dimension 13 parse of the built pak: 0 single-child `<SymptomSets>`, all `waitCycles`/`cancelCycles` integers. |
| Rename / identity claims (CHANGELOG #27) | **Confirmed against SDK bytecode** (9.1.1.0100 `ResourceKey`, `AdapterBase.getMonitoringResource`, `checkIfResourceRenamed`, `finalizeCollectResult`, `updateRenamedResource`; `AdapterCache.getMonitoringResource` is a map lookup). The javap claims about the vSphere/vSAN/NSX-T plugins could not be re-run (they need the appliance, which a reviewer does not touch). They are corroborated in part by `cleanroom-spec/analysis/per-adapter/vim.md:82,104` (vim overrides `isResourceRenameAllowed(ResourceKey)`). |
| Traversal citation (#15) | **Confirmed** (see Bottom line); the describe comment quotes the vendor form without `/preferred` (N1). |
| defect-gate | `no open blocking defects affecting unifi`. |

## Per-issue walk

### #39 NVR storage
`UniFiValues.nvrStorage` returns the volume pair (`systemInfo.storage.size/used`)
when usable, else the recording pair (`storageStats.recordingSpace.total/used`),
else null. A half-present volume pair falls through to the recording pair as
a whole, so the two sources are never mixed. The three metrics publish
together, only from one usable pair (total > 0, used >= 0). An absent read
publishes nothing, never a 0 or a sentinel (skill: *Unreadable is NOT
compliant*). `SimpleJson.get` chains are null-safe, so a missing subtree
cannot throw into the cycle. Correct. See N3 for two small gaps.

### #15 Uplink tree and traversal
`UplinkTree` has no SDK dependency, so the logic the tests drive is the
logic that runs. A gateway is always under its Site. An unknown uplink, a
loop or an unsupported nesting falls back to the Site and logs once at INFO,
keyed `site|mac|reason` (bounded by the device count, no per-cycle spam).
The six `/recursive` paths cover every shape `nests()` allows: switch
parent is in {Site, Gateway, Switch}, AP parent is in {Site, Gateway,
Switch, AP}. `uplink_mac` is matched raw against the raw MAC
(`UniFiIds.mac` does not normalise), the same as build 17. Devel nests five
deep, which shows the formats agree there.

### #27 item 4 Names and rename
Covered in the Bottom line. `renameIfChanged` runs on every enumerated key,
in both the collect-path and the `onDiscover` paths. It catches
`RuntimeException` only, so a failed lookup costs the rename and never the
resource. Upgrade effect: on the first build-18 cycle every switch port, WAN
interface, radio and Wireless Summary takes a new name. That is the most
operator-visible change in this build (W2).

### #17 UniFi OS only
`UniFiFailures.unifiOsRequired` walks the cause chain with an identity set
(cycle-safe) for a typed `UniFiHttpException` with status 404, so it reaches
through the framework's `SessionCookieAuth` RuntimeException wrapper. It
picks the login or Network wording from `isLogin()`. The rethrow keeps the
cause. The message carries no host credentials or tokens. A non-404 is
rethrown unchanged. The collect path is untouched, which is in scope.

### #32 Integrations paths
README and docs/installing.md agree (9.1.1: Operate > Administration >
Integrations; 9.0.2/8.18.7: Administration > Integrations; Repository vs
Accounts tabs). No stale "Data Sources" or "Integrations > Repository" for
instance creation remains. The UI check itself is the author's 2026-10-28
claim; a static reviewer cannot re-verify a UI.

## Findings

### BLOCKING
None.

### WARNING

- **W1** `docs/overview.md:37-48`. Authority: dimension 11 (docs parity;
  the shipped docs must render what the pak does). The new two-paragraph
  note is inserted *inside* the Resource kinds table, between the
  `UniFi Wireless Summary` row and the `UniFi NVR` row. The table now ends
  at Wireless Summary, and the NVR and Camera rows render as stray pipe
  text after the paragraph, so two of the eleven kinds drop out of the
  table. Fix: move the paragraph below the `UniFi Camera` row.

- **W2** `README.md`, `docs/README.md` (via `docs/_index_extra.md`).
  Authority: dimension 11 (buried-but-present). The upgrade renames every
  existing switch port, WAN interface, radio and Wireless Summary on its
  first cycle, and later controller-side renames carry over. That breaks
  anything an operator keyed on the old names: saved searches, custom
  groups or views filtered by name, notification rules. It is stated only in
  CHANGELOG, REFERENCE.md and overview.md. Neither landing page mentions
  it. Fix: one "Upgrading to build 18" note in README.md, plus a line in
  `docs/_index_extra.md` so the generated docs/README.md carries it.

- **W3** `describe.xml:443-464`; `UniFiAdapter.java:689-712`. Authority:
  `knowledge/rules/validate-before-install.md` and the reviewer doctrine's
  skeptic default; skill § *describe.xml alert shapes Ops rejects at
  install* ("validate-sdk, pak-compare ... do not catch it"). Live proof is
  owed on devel **before the `v1.1.0.18` tag**, because neither the static
  gate nor pak-compare checks it:
  (a) Ops accepts the six bare `/recursive` ResourcePaths at install (the
  only vendor example is `/recursive/preferred`), and the "UniFi Controller
  Infrastructure" tree shows the five-deep chain and the AP behind the
  in-wall AP, each once.
  (b) On the upgraded instance, existing ports, WANs, radios and the
  Wireless Summary take the `<label> (<parent>)` names, keep their metric
  history (same resource IDs, no duplicate objects), and do not rename
  again on the following cycle.
  (c) The vmnic stitch still reports the same edge count and the
  HostSystem > UniFiSwitchPort children persist after the rename.
  The CHANGELOG is honest that (b) has not been seen yet. If (a) fails, the
  whole describe is rejected and the install rolls back, which is why it
  is not optional.

- **W4** `docs/inventory-tree.md` (generated), `docs/inventory-tree.svg`.
  Authority: dimension 11; `vcfops-project-conventions` § TOOLSET GAP. The
  docs generator reads each path segment once and ignores `/recursive`.
  The generated tree now shows Switch only under Gateway and AP only under
  Switch: the Site > Switch, Site > AP, Gateway > AP, Switch > Switch and
  AP > AP shapes are missing. The per-kind Parents column omits `UniFi
  Switch` for UniFiSwitch and `UniFi Access Point` for UniFiAccessPoint,
  which on devel are the most common parents. The author disclosed this and
  cannot hand-edit a generated file; REFERENCE.md has the correct tree.
  This is a factory TOOLSET GAP for `tooling`: render `/recursive` levels
  and include self-parents in the Parents column.
  **Registration candidate** (`factory:docs-generator` or a tooling issue)
  if it is not fixed before the tag.

### NIT

- **N1** `describe.xml:443-450`, REFERENCE.md "Object names"/tree note. The
  comment says VMWARE uses `HostFolder::child/recursive`; the captured form
  is `HostFolder::child/recursive/preferred`. Quote it exactly and say
  `/preferred` is dropped on purpose (each resource has one parent, so there
  is nothing to prefer).
- **N2** `UniFiAdapter.java:703-712`. `renameLookupFailed` is a
  warn-once for the lifetime of the instance. After the first failure (for
  example an early `onDiscover` call), a later cycle where renames stop
  working leaves no trace. Reset it in `onCycleStart()` (skill § *Per-cycle
  state*) or log later failures at DEBUG.
- **N3** `UniFiValues.java:209-222`, `UniFiAdapter.java:1395-1411`. The
  source can switch between the volume and Protect's recording share from
  cycle to cycle, and the two mean different things. Nothing records which
  one fed a given point, so a step in `Storage|total_bytes` is
  unexplainable from Ops. Also, `used > total` is not rejected, so
  `usage_pct` can exceed 100. Optional: a `Storage|source` property, and
  `used <= total` in `usablePair`.

## Registry check (`knowledge/context/defects.md`)

No `defects.local.md` exists, so the factory registry is the one that
applies. Every entry with `Affects: unifi` is closed:

- DEF-002 (foreign HostSystem relationship unproven): closed. The stitch
  edge path (`emitVmnicHostStitch`, `rb.parentForeign`) is unchanged apart
  from the port's display name, and that does not affect identity. W3(c)
  re-proves it live.
- DEF-007 (CP collect stall): closed. Not touched by this build.

There are **no open defects affecting this pak** and nothing to propose
for closure. `defect-gate --pak unifi` is clean. Registration candidate:
W4 (factory docs generator), if it is still open at tag time.

## If shipped as-is

The pak installs and collects correctly, provided Ops accepts bare
`/recursive` (W3a). Existing per-parent objects are renamed on the first
cycle with their history intact, and operators get no landing-page warning
that name-keyed searches and filters will stop matching. The overview page
shows a broken kinds table, and the generated inventory tree under-draws
the nesting.

---

# Round 2 (sdk-adapter-reviewer, 2026-10-28)

- **Commits reviewed:** `7879373` (round 1 fixes), `87b9171` (traversal root
  at UniFiWorld), `d5d1d7e` (#20 NOT_EXISTING opt-in, `ReadKinds`),
  `f2db412` (#20 relationship hold, `ProtectEdgeHold`), on `build-18`
  (ahead of `origin/main` by 6).
- **Framework read against:** factory `main` (`VcfCfAdapter.java`, buildkit
  1.0.22 `markVanished`, `markable`, `restoreReappeared`).
- **Verdict: CHANGES REQUESTED** (1 BLOCKING, 4 WARNING, 4 NIT). This
  supersedes the round 1 verdict.

## Bottom line

The opt-in is mostly careful, and it does what the brief asked in the cases
the author thought about. A failed or cooling-down site leaves every device
kind out. So does the connect-failure skip, because it puts the rest of the
sites in `failedSites`. Every site failing throws, and nothing is counted. A
Protect outage leaves NVR and Camera out. MAC-less gateways, switches and
APs, MAC-less cameras, port rows with no index and radio rows with no code
each leave their kind out. A disconnected switch, AP or gateway leaves its
child kind out. `kindsReadThisCycle()` answers only for the thread that ran
the enumeration. The framework calls `enumerateResources` and later
`kindsReadThisCycle` on the same `onCollect` thread
(`VcfCfAdapter.java:1063-1071`, `markVanished`). A concurrent `onDiscover`
enumeration clears `lastRead` or replaces it with a record for another
thread, and either way that collect cycle marks nothing. That fails safe:
the framework counts no miss and resets no count. Renamed objects are not
counted missing: `Enumerated.keys.contains` uses `ResourceKey` equality,
which ignores the name when a uniqueness identifier is present (round 1
bytecode check).

**One path breaks it.** A `/self/sites` answer of `200 {"data":[]}`
declares every network kind read in full, and the UniFi World object
defeats the framework's "delivered nothing" guard. Twelve such cycles in a
row mark every Site, Wireless Summary, gateway, WAN, switch, port, AP and
radio Not Existing, and the retention window deletes them with their
history (R2-B1). That is exactly the failure mode the brief named. The fix is
one guard and one test.

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | All pass: 16 Java (new `ReadKindsTest`, `ProtectEdgeHoldTest`, `StreakLogTest`, plus `UniFiValuesTest` additions) and 14 Python (new `test_vanished_wiring.py`). |
| Test strength | Mutation-checked in scratch copies, 5 of 6 killed: `camerasNoMac` ignored, the `informing` guard dropped from `switchPorts`, the `deviceWithoutIdentity` guard dropped, the hold treating an unreadable platform list as "no NVR", and grace `<=` changed to `<`. **Survived:** dropping `failed \|\|` from `ReadKinds.site` (R2-N1). |
| validate-sdk | **Confirmed** `OK`. The SDK compat compile against 8.18.7 (jar from `/mnt/holding/vendor`, `--sdk-compat-jar`) is clean. 9.1.1.0100 was skipped (needs JDK 25). |
| build-sdk | Reproduces. The adapter tree is clean afterwards: the generated docs regenerate byte-identical to what is committed. |
| pak-compare 18 vs 0.0.0.17 (`u18r-455409/ref`) | **0 BLOCKING, 1 WARNING, 1 INFO.** W1 is the `UniFiNvr` attribute count +1, exactly `Storage\|source` (R1 N3, expected). I1 is the manifest description (the UniFi OS wording, as in round 1). |
| Content / dimension 13 | `content/alertdefs` and `content/symptomdefs` are byte-identical to the 17 pak. The only content change is `resources.properties` (+`245=Source`). The describe.xml diff is the `source` attribute, the traversal root and its comment. No alert structure changed, so the composite-set rules are untouched. |
| Traversal root (`87b9171`) | Matches `knowledge/lessons/traversal-spec-root-must-be-reachable.md`: `rootResourceKind="UniFiWorld"`, and all nine paths start `unifi_controller::UniFiWorld\|\|`. Seen rendering on devel 2026-10-28, per the brief (not re-verified; a static reviewer does not touch the lab). |
| Buildkit dependency | `sdk-buildkit-v1` points at **1.0.20** (local tags and `gh release list`). The 1.0.22 hooks are not published (R2-W2). |
| defect-gate | `no open blocking defects affecting unifi`. |

## Kind-by-kind walk (ReadKinds vs enumerateResources)

| Kind | Declared when | Enumeration path | Verdict |
|---|---|---|---|
| Site, Wireless Summary | `sitesRead()`, unconditionally after the snapshot | every `/self/sites` entry emits a Site and an Aggregate, failed sites included (`UniFiAdapter.java:637-641, 723`) | Safe for a non-empty list. **Unsafe for an empty list** (R2-B1). |
| Gateway, Switch, AP | every listed site read, none failed or cooling, every payload a list, no MAC-less gw/usw/uap | `read.site(failedSites.containsKey, devicesBySite.containsKey && isList)`. Cooled sites are in `failed` (`SiteReads.readAll`), and so are connect-skipped sites. All sites failing throws. | Safe. Edge cases in R2-W1 (empty list, no `meta.rc` check) and R2-N2 (record with a MAC and no type). |
| WAN | as gateway, and every gateway informing | `wan1`/`wan2` present-gated. An unused WAN2 is still sent (`up=false`, build 17 CHANGELOG, REFERENCE.md:130) | Safe: an unplugged WAN is not dropped. |
| Port | as switch, every switch informing, `port_table` a list, every row indexed | matches | An empty `port_table: []` on an informing switch (states 4, 5, 7 count as informing) is a complete read (R2-W1). |
| Radio | as AP, every AP informing, `radio_table_stats` a list, every row coded | matches | Same empty-list gap (R2-W1). A radio disabled in config is undocumented (R2-N3). |
| NVR | Protect read, NVR present with a MAC | matches | Safe. |
| Camera | Protect read, NVR present, `cameras` a list, every camera with a MAC | matches | `cameras: []` with an NVR present marks every camera (R2-W1). |
| World | excluded (`notExistingExcludedKinds`) | always delivered | Safe, but its constant delivery is what makes R2-B1 reachable. |
| Pending adoption | not registered (`isDiscovered`) | a previously registered pending device is counted | As documented. |
| Foreign HostSystem | `markable` rejects other adapter kinds | n/a | Safe. |

## Hold logic vs failed sites (`ProtectEdgeHold`, `holdNvrSite`)

| Site 0 | Protect | Result | OK? |
|---|---|---|---|
| read | read | PUBLISH; Site > NVR built (`nvrParentSite` = site 0) | yes |
| read | not read | HOLD; site 0 skipped, NVR edge kept, World > Site 0 still sent | yes |
| failed | read | PUBLISH; site 0 skipped by `SiteIsolation`; no Site > NVR (`nvrParentSite` null), old edge kept | yes |
| failed | not read | HOLD counted; site 0 skipped anyway | yes |
| any | not read for more than 12 cycles | EXPIRED; site 0 published without the NVR (unless failed) | yes |

The counter advances once per `buildRelationships`, which only runs for the
World's `collectRelationships`, so it advances once per cycle. Cost,
documented in REFERENCE "Relationships when a read fails": during a hold, all
of site 0's edges are frozen. On a single-site controller that is the whole
topology, for up to an hour. See R2-N4 for a leftover NVR.

## Findings (round 2)

### BLOCKING

- **R2-B1** `ReadKinds.java:69,79,144-157`; `UniFiAdapter.java:632`; the
  contract it breaks is `UniFiAdapter.java:2055-2058`. Authorities:
  skill § *Unreadable is NOT compliant* (a success-shaped empty payload is
  unreadable, not a pass); the framework's `kindsReadThisCycle` contract
  ("Leave a kind out whenever any part of its read failed");
  `knowledge/context/sdk/vanished_object_lifecycle.md` §4 item 2 (every
  Broadcom adapter guards; the Dockerized wrapper skips empty results).
  - `Snapshot.build` rejects only a `data` that is absent or not a list. The
    code's own comment says "A controller always carries at least the default
    site, so a missing/unreadable site list is unreadable, not 'no sites'",
    but `{"data":[]}` passes.
  - With zero sites, `sitesRead()` is called, `site()` never is,
    `everySiteRead` stays `true`, and nothing sets the child flags.
    `kinds()` returns all ten kinds. Proven with a driver against the real
    class:
    `[UniFiSite, UniFiWirelessAggregate, UniFiGateway, UniFiSwitch, UniFiAccessPoint, UniFiWanInterface, UniFiSwitchPort, UniFiRadio, UniFiNvr, UniFiCamera]`.
  - The framework's "delivered nothing" guard
    (`VcfCfAdapter.java:3739`, `enumerated.keys.isEmpty()`) does not fire,
    because UniFiWorld is always delivered.
  - The "every object failed" guard does not fire either: World's collect
    is a keepalive, and absent objects log "absent from snapshot" and
    return normally (`UniFiAdapter.java:1072` etc.).
  - Twelve such cycles in a row mark the whole network inventory, and the
    retention window deletes it with its history: 6 hours on 9.0 devel.
    Nothing shows that UniFi OS never answers this way. A Network app
    mid-restore, an account whose site access was emptied, or a proxy
    returning a stub would each do it. The burden is on the code.
  - **Fix:** declare nothing when the site list is empty. Smallest diff:
    have `sitesRead` take the site count and have `kinds()` return the empty
    set at 0, with a `ReadKindsTest` case for it. Alternatively, throw in
    `Snapshot.build` as the comment already claims. That also changes
    collection behaviour, so prefer the `ReadKinds` guard.

### WARNING

- **R2-W1** `UniFiApiClient.java:84-92`; `ReadKinds.java:114-140`;
  `UniFiAdapter.java:644-645, 681-735, 742-758`. Authority: as R2-B1, a
  weaker form. A list that is present but empty counts as a complete read
  in four more places:
  - (a) a site's `stat/device` `{"data":[]}`. `get()` checks only the HTTP
    status, never `meta.rc`. The API map's error probes all came back
    non-200 (`unifi-network-api.md:630-648`), which lowers the risk but
    does not prove it for `stat/device` under a permission change.
  - (b) `cameras: []` with an NVR present.
  - (c) `port_table: []` on a switch in state 4, 5 or 7. An adoption loop
    (state 7) can last hours.
  - (d) `radio_table_stats: []` on an informing AP.

  The 12-cycle debounce covers blips. A persistent state is not proven
  impossible, and the cost is irreversible. **Fix:** declare a site read
  only when `meta.rc` is `ok` (when `meta` is present). Treat an empty
  `port_table` or `radio_table_stats` on a registered switch or AP as
  incomplete; every switch has ports and every AP has a radio. For (b),
  consider "NVR present but zero cameras while the platform holds cameras"
  to be incomplete. **Registration candidate** if any part ships unfixed.

- **R2-W2** `CHANGELOG.md` 0.0.0.18 header; `.github/workflows/build-pak-on-tag.yml:53`
  (`BUILDKIT_TAG: sdk-buildkit-v1`). Authority:
  `knowledge/rules/validate-before-install.md`, release gate.
  `sdk-buildkit-v1` points at 1.0.20, and 1.0.21 and 1.0.22 are not
  published. A `v1.1.0.18` tag cut now fails CI at compile (`@Override` of
  hooks that do not exist). That failure is loud, not silent, and the
  CHANGELOG states the precondition. **Fix (orchestrator):** publish
  buildkit 1.0.22 or later and move `sdk-buildkit-v1` before tagging.

- **R2-W3** (round 1 W3, carried and extended). Authority:
  `knowledge/rules/validate-before-install.md`; reviewer doctrine.
  Live proof still owed before the tag:
  - (a) Tree rendering: discharged by the orchestrator's 2026-10-28 devel
    observation (not re-verified here).
  - (b) Renames: the CHANGELOG reports them seen on devel ("udm" became
    "Bentwood"). That the same resource IDs and history were kept, with no
    duplicates, is not stated. Confirm it.
  - (c) The vmnic stitch edge count and the HostSystem > Switch Port
    children after the rename: no evidence yet.
  - (d) New for #20: about 12 cycles after install, list `resourceState=NOT_EXISTING`
    for `unifi_controller` and check that it is exactly the expected
    orphans (`<mac>_0` ports, the Backyard camera `18E829CFAE3F`, the old
    gateway with its WANs, any `<mac>_` radio) and nothing live. **Do this
    before the 9.0 devel retention (6 h) deletes them.**
  - (e) One Protect blip keeps Site > NVR.

  **Note for the orchestrator:** installing build 18 on devel is itself
  an irreversible deletion of those orphans and their history within
  about 7 hours. Under the "lab is not disposable" rule that needs
  Scott's explicit go-ahead, and an export first if anyone wants the
  Backyard history.

- **R2-W4** (round 1 W4, carried) `docs/inventory-tree.md` (generated).
  The docs generator still ignores `/recursive`, so Site > Switch,
  Switch > Switch, AP > AP and the like are not drawn, and the Parents
  column omits self-parents. The new root renders correctly. This is a
  factory TOOLSET GAP for `tooling`. **Registration candidate** if it is
  not fixed before the tag.

### NIT

- **R2-N1** `tests/.../ReadKindsTest.java:140-166`. No case drives
  `site(true, true)`, so the mutant that drops `failed ||` from
  `ReadKinds.site` survives. Today it is equivalent in production
  (`SiteReads` keeps `bySite` and `failed` disjoint), but the guard that
  matters most is untested. Add one assertion.
- **R2-N2** `UniFiAdapter.java:651-660`. A record with a MAC but a
  missing or unknown `type` is skipped silently. If it was a registered
  switch, that switch takes a miss. A missing `type` is a partial record:
  call `deviceWithoutIdentity()` when `type` is empty.
- **R2-N3** `README.md` "Upgrading to build 18"; REFERENCE.md "Removed
  objects". Say that removal follows what the controller lists, so a
  config or permission change counts too. Narrowing the account's site
  access deletes those sites and their devices, and a radio the controller
  stops reporting (for example a disabled band, if UniFi drops it from
  `radio_table_stats`; unverified) is deleted. If it comes back, it
  returns as a new object with no history.
- **R2-N4** `ProtectEdgeHold`; `UniFiAdapter.java:1778-1823`. A leftover
  NVR (Protect uninstalled) is never marked, because the NVR kind is never
  declared without Protect. `platformKnowsNvr()` therefore stays true for
  good. After every collector restart the in-memory counter starts at 0,
  site 0's edges freeze for another 12 cycles, and the INFO/WARN pair
  repeats. This is acceptable and fails safe; one sentence in REFERENCE
  "Relationships when a read fails" would cover it.

## Round 1 findings, status

| Finding | Status |
|---|---|
| W1 overview table | **Fixed** (`docs/overview.md`, NVR and Camera rows back in the table). |
| W2 landing-page rename warning | **Fixed** (README "Upgrading to build 18", `docs/_index_extra.md` and the generated docs/README.md). |
| W3 live proof | Partly discharged; the rest is carried as R2-W3. |
| W4 docs generator `/recursive` | Open, carried as R2-W4. |
| N1 traversal citation | **Fixed** (describe comment, REFERENCE.md, CHANGELOG quote `/recursive/preferred` exactly). |
| N2 rename warn-once | **Fixed** (`StreakLog`, re-armed in `onCycleStart`; `StreakLogTest`). |
| N3 storage source / used over total | **Fixed** (`Storage\|source`, `usablePair` requires `used <= total`, WARN once per streak; `UniFiValuesTest.nvrStorageUsedOverTotal`). |

## Upgrade-warning accuracy (README, `_index_extra.md`, CHANGELOG)

These are accurate against the code and the framework:
- the 12 consecutive complete cycles, about an hour at 5 minutes;
- the retention of 168 h by default and 6 h on 9.0 devel
  (`vanished_object_lifecycle.md` §3 table);
- that it cannot be undone;
- the orphan list: `<mac>_0` ports, the Backyard camera, the old gateway
  with its WANs (WAN is declared when every remaining gateway is informing),
  pending-adoption devices and `<mac>_` radios;
- that counting resumes after a partial cycle without resetting
  (REFERENCE.md matches `markable` and `restoreReappeared`);
- that the return path is unverified live.

Two gaps: the warnings do not say the deletion also follows permission and
config changes (R2-N3), and they cannot warn about R2-B1 because it is a
bug, not behaviour.

## Registry check (`knowledge/context/defects.md`)

There is no `defects.local.md`, so the factory registry applies. Every entry
with `Affects: unifi` is closed, unchanged from round 1:
- **DEF-002** (foreign HostSystem relationship) is closed. The stitch code
  path is unchanged in these commits (`test_vanished_wiring.py` pins
  `rb.parentForeign` as the only foreign call). R2-W3(c) re-proves it live.
- **DEF-007** (CP collect stall) is closed and not touched.

No open defects affect this pak, and nothing is proposed for closure.
`defect-gate --pak unifi` is clean. Registration candidates: R2-W1 and R2-W4
if either ships unfixed.

## If shipped as-is (round 2)

Normal operation behaves as documented: the leftovers are removed and
outages are tolerated. But a console that answers `/self/sites` with an
empty list for an hour would have its entire UniFi inventory marked Not
Existing, then deleted with its history at the end of the retention window,
and there is no way back.

---

# Round 3 (commit `b5b3a16` on `f2db412`, branch `build-18`)

**Verdict: CHANGES REQUESTED.** 2 BLOCKING / 1 WARNING / 3 NIT, plus the
carried R2-W2, R2-W3 and R2-W4.

All of the round 2 findings in the commit's scope are fixed and proven: R2-B1,
R2-W1 (a) to (d), and R2-N1 to N4. One gap is left: an empty *device* list.
The build's new rule says an empty answer is never proof that something is
gone. It applies that rule to sites, cameras, ports and radios, but not to
the device list itself. The docs state the rule as universal, so they now
contradict the code.

## Claims check (round 3)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 15 Java suites and 14 Python wiring scripts all pass. |
| validate-sdk | **Confirmed** `OK`. The 8.18.7 compat compile is clean (`--sdk-compat-jar /mnt/holding/vendor/vcf-ops-8.18.7/...`). 9.1.1.0100 was skipped (needs JDK 25). |
| build-sdk | Reproduces `vcfcf_sdk_unifi_controller.0.0.0.18.pak`. The adapter tree is clean afterwards. |
| pak-compare 18 vs 0.0.0.17 (`u18r-455409/ref`) | **0 BLOCKING, 1 WARNING, 1 INFO**, the same as round 2: `UniFiNvr` group attribute count off by one (`Storage\|source`), and the manifest description. The commit touches no describe, alert or symptom file, so dimension 13 is not triggered. |
| defect-gate | `no open blocking defects affecting unifi`. |
| `build_number` / CHANGELOG | Still 18. The round fix is recorded under the 0.0.0.18 entry (two lines), which is correct for an in-review build. |

## Zero-site driver, re-run (`scratchpad/u18r3/zs/`)

This is the round 2 driver, updated to the new signatures and extended to
cover the new shapes. It runs against the real `ReadKinds` class.

```
zero sites + protect            -> []
1 site, rc=error                -> [UniFiSite, UniFiWirelessAggregate]
1 site, no meta                 -> [UniFiSite, UniFiWirelessAggregate]
1 site, rc=' OK '               -> [all ten minus NVR/Camera]
empty port+radio tables         -> [... no UniFiSwitchPort, no UniFiRadio]
cameras []                      -> [... UniFiNvr, no UniFiCamera]
1 site, zero devices (rc ok)    -> [UniFiSite, UniFiWirelessAggregate, UniFiGateway,
                                    UniFiSwitch, UniFiAccessPoint, UniFiWanInterface,
                                    UniFiSwitchPort, UniFiRadio]      <-- R3-B1
```

R2-B1 is closed: an empty site list declares nothing, even when Protect was
read.

## Mutation run (`scratchpad/u18r3-tools/mutate.py`)

There were 18 mutants: every new guard, the round 2 set, and four
adapter-wiring mutants. **All 18 were killed** by the test that owns them.
- **`ReadKinds` mutants**, killed by `ReadKindsTest`: dropping `failed`,
  dropping `rcOk`, `rcOk` always true, `rcOk` accepting null or empty,
  `siteCount > 0` changed to `true` or to `>= 0`, dropping `portRows`,
  `radioRows` or `cameraRows`, dropping `camNoMac`, `informing` or
  `noIdentity`.
- **`ProtectEdgeHold` mutants**, killed by `ProtectEdgeHoldTest`:
  `holdNull` and `grace`.
- **Adapter wiring mutants**, killed by `test_vanished_wiring.py`: the
  typeless call removed, the rc argument hardcoded `true`, the site count
  hardcoded 1, and the port rows hardcoded 1.

The R2-N1 mutant (`failed ||` dropped) is now killed by
`failedSiteWithAListIsNotRead`.

Harness note: the wiring test is a plain script, not pytest. Run under
`pytest` it collects nothing and exits 5. My first pass counted that exit as
"killed" and was discarded; the numbers above come from running the script
directly.

## Round 2 findings, status

| Finding | Status |
|---|---|
| R2-B1 empty site list | **Fixed** (`ReadKinds.java:93`, `UniFiAdapter.java:635`; test `emptySiteListNamesNothing`, 30 cycles; driver above). |
| R2-W1(a) `meta.rc` | **Fixed** (`ReadKinds.rcOk`, `site(..., rcOk)`). An absent `meta` counts as not read, which fails safe. The API map (`unifi-network-api.md:111`) confirms every classic response carries `meta.rc`. |
| R2-W1(b) `cameras: []` | **Fixed** (`cameraRows > 0`). |
| R2-W1(c, d) empty `port_table` / `radio_table_stats` | **Fixed** (`portRows`/`radioRows <= 0` are incomplete in any state). |
| R2-W2 buildkit tag | **Open, carried.** `sdk-buildkit-v1` still resolves to v1.0.20. v1.0.21, 1.0.22 and 1.0.23 are merged on main but have no tag or release. A `v1.1.0.18` tag still fails CI at compile. |
| R2-W3 live proof | **Open, carried** (b to e unchanged). This includes the note that installing build 18 deletes the orphans irreversibly and needs Scott's go-ahead. |
| R2-W4 docs generator `/recursive` | **Open, carried.** No factory `src/` commit since round 2 touches the generator. |
| R2-N1 `site(true, true)` test | **Fixed** (`failedSiteWithAListIsNotRead`; mutant killed). |
| R2-N2 typeless record | **Fixed**, and broader than asked: any record with an empty `type`, MAC or not, calls `deviceWithoutIdentity()` before the MAC check (pinned by wiring order). |
| R2-N3 removal follows the listing | **Fixed** in README, REFERENCE, `_index_extra.md`, generated `docs/README.md` and `overview.md`. |
| R2-N4 leftover NVR refreezes | **Fixed** (REFERENCE, "Relationships when a read fails"). |

## Hunt: remaining partial, empty or failed reads that count a miss

| Path | Verdict |
|---|---|
| `/self/sites` `{"data":[]}` | Safe (R2-B1 fix). |
| `/self/sites` 200 with no list | Safe: `Snapshot.build` throws, `lastRead` stays null. |
| `/self/sites` 200 `rc:error` with rows | Not checked. Implausible shape; see R3-N1. |
| site `stat/device` non-200 | Safe: the site is failed, so no device kind. |
| site in cooldown (401/403/429, 15 min; other errors, 60 s) | Safe: it is in `failedSites`, so `everySiteRead=false` (mutant `failedSite` killed). |
| site `stat/device` `rc:error` or no `meta` | Safe. |
| **every site `stat/device` `rc:ok`, `data:[]`** | **Counts a miss for every device, WAN, port and radio. R3-B1.** |
| one site of many `rc:ok`, `data:[]` | Counts a miss for that site's devices. A site can legitimately be empty, so I accept this residual; it needs a per-site history to guard. |
| a device record with no `type` or no MAC | Safe: no device kind. |
| a registered switch or AP with an empty or missing table | Safe in any state. |
| **an informing gateway whose record has no `wan1`** | **Counts a miss for WAN 1. R3-W1.** |
| device mid-adoption, state 7 with `adopted` true | It is emitted. State 7 is "informing", but an empty `port_table` or `radio_table_stats` now fails safe, and a gateway in state 7 hits R3-W1. |
| device that went back to `adopted:false` (reset or forgotten, re-adoption pending) | Skipped, counts a miss. The controller does not manage it; this is the documented "removal follows the listing". It is lost only if re-adoption takes longer than 12 cycles plus the retention window (168 h by default, 6 h on 9.0 devel). Accepted. |
| `adopted` absent | It is treated as discovered (registered), so it takes no miss. Safe. |
| Protect bootstrap failure or no NVR | Safe: no Protect kind. |
| Protect `cameras: []` | Safe. |
| site list shrinks (account scope) | See the judgement below. |

### Judgement: a site list that shrinks because of account scope

I think intended removal is the right call, and it does not need a guard.
`/self/sites` is the inventory the configured account can see. Under the
API, narrowing the account's access cannot be told apart from deleting the
site. A guard that held vanished sites would mean a deleted site is never
removed, which is the same cost the build already accepts for the last
site, but for every site. The change is a deliberate admin action, and it
must persist for 12 cycles before anything is marked. Deletion waits for
the retention window after that (168 h by default), and the docs now say
all of this.

What is missing is a signal: the framework logs only when it marks
(`VcfCfAdapter.java` "marked NOT_EXISTING this cycle"). A whole site and
its device tree, the largest removal this pack can make, starts counting
silently. R3-N3 asks for one WARN when it starts. A Network-app reinstall
on a UDM, where the console's own gateway is listed again but nothing else
is, also falls under "removal follows the listing". The R3-B1 guard would
not catch that, and that is acceptable for the same reason.

## Findings (round 3)

### BLOCKING

- **R3-B1** `ReadKinds.java:183-195` (`kinds()`); `UniFiAdapter.java:646-650`.
  Authorities: skill § *Unreadable is NOT compliant* (an empty payload
  shaped like a success is unreadable, not a pass); the framework's
  `kindsReadThisCycle` contract; R2-B1 precedent; and this build's own
  rule at `ReadKinds.java:169-180` ("0 is not proof none exist").
  - If every site answers `stat/device` with
    `{"meta":{"rc":"ok"},"data":[]}`, every device kind is declared read.
    `wansIncomplete`, `portsIncomplete` and `radiosIncomplete` are never
    set because no device was walked, so WAN, port and radio are declared
    too. The driver proves it (output above).
  - Twelve such cycles mark every gateway, switch, AP, WAN, port and radio
    Not Existing. Retention then deletes them with their history.
  - This is R2-B1 one level down, and it is the case the R2-B1 analysis
    named: a Network app mid-start or a proxy stub. The `meta.rc` fix
    guards an error answer, but not an *ok* answer that is empty.
  - On a UniFi OS console with an integrated gateway, the console itself
    is always in its site's device list. Zero devices across every site is
    therefore anomalous, not an inventory.
  - The build already treats `cameras: []` under a present NVR as
    incomplete. The same logic applies here with more at stake.
  - **Fix:** count device records seen across all read sites (any record
    in `data`, or the discovered gateway/switch/AP records). When the
    count is 0, `kinds()` leaves out all six device-derived kinds. Add a
    `ReadKindsTest` case (one site, `rc:ok`, zero devices, 30 cycles, no
    device kind) and a wiring assertion. The cost is that the last
    device on the controller is removed by hand, as for the last camera.

- **R3-B2** `README.md:90`; `REFERENCE.md:555-561`; `docs/_index_extra.md:19`;
  generated `docs/README.md:48`; `docs/overview.md:298`. Authority:
  review dimension 11, docs parity (docs that contradict behaviour are
  BLOCKING).
  - The docs say "An empty answer is never taken as proof that
    everything is gone" and "the last object of a kind is never removed
    automatically".
  - Both are false for this build. An empty device list removes every
    gateway, switch, AP, WAN, port and radio (R3-B1).
  - Even with R3-B1 fixed, the "last object of a kind" claim is false in
    normal operation. Remove the only switch while a gateway or AP is
    still listed, and the switch kind is declared: that switch and its
    ports are marked and removed automatically, which is correct
    behaviour. Likewise, removing the second gateway removes its WANs.
  - An operator who trusts the sentence will not expect it.
  - **Fix:** after R3-B1, scope the claim to what is guarded: the last
    site, the last camera under an NVR, a listed switch's ports and a
    listed AP's radios when the table is empty, and (with R3-B1) the last
    device on the controller. Say plainly that the last device *of a
    type* is removed when other devices are still listed. Regenerate
    `docs/README.md`.

### WARNING

- **R3-W1** `ReadKinds.java:132` (`gateway(boolean informing)`);
  `UniFiAdapter.java:674-686`. Authority: as R2-W1(c, d), the same class.
  - An informing gateway whose record has no `wan1` emits no WAN 1, but
    `wansIncomplete` stays false. WAN 1 therefore takes a miss.
  - Every gateway has a WAN 1, just as every switch has ports, the rule
    this build adopted for port and radio tables.
  - A partial record during provisioning (state 5) or adoption (state 7)
    is unproven not to drop it. The API map (`unifi-network-api.md:490`)
    documents `wan1` and `wan2` as top-level objects on the UDM, so a
    missing `wan1` is an unexpected shape.
  - An absent `wan2` can be a real configuration, so leave it as is.
  - **Fix:** `gateway(informing, hasWan1)`, which sets `wansIncomplete`
    when `wan1` is null, plus a test and a wiring assertion.
  - **Registration candidate** if it ships unfixed.

### NIT

- **R3-N1** `UniFiAdapter.java:635` / `Snapshot.build`. `/self/sites`
  `meta.rc` is not checked, while `stat/device` now is. With the count
  guard the remaining risk is a `rc:error` answer that still carries
  rows, which is implausible. For consistency, pass
  `rcOk(s.sites.get("meta")...)` into `sitesRead`.
- **R3-N2** `UniFiAdapter.java:573` / `ReadKinds`. Nothing logs *why* a
  kind was left out. A persistently typeless record, a missing `meta`, or
  a switch stuck with an empty table turns removal off for that kind for
  good, silently. The operator cannot tell "nothing vanished" from
  "removal is suspended". One INFO per streak naming the kinds left out
  and the reason would be enough (`StreakLog` exists for this).
- **R3-N3** (scope-shrink judgement above). When a site that was listed
  last cycle is missing, log one WARN naming it and saying that its
  objects are marked after 12 cycles. This needs a small per-config set
  of the last listed site names.

## Registry check (`knowledge/context/defects.md`), round 3

This is unchanged from round 2. There is no `defects.local.md`, so the
factory registry applies. Every entry with `Affects: unifi` is closed:
- **DEF-002** is closed. The stitch path is untouched by `b5b3a16`;
  `test_vanished_wiring.py` still pins `rb.parentForeign`.
- **DEF-007** is closed and not touched.

No open defects affect this pak, and none is proposed for closure.
`defect-gate --pak unifi` is clean. Registration candidates: R3-W1, R2-W4,
and R3-B1 if it is somehow waived.

## If shipped as-is (round 3)

Normal operation behaves as documented. But if a console answers every
site's device list with an empty "ok" for an hour, every gateway, switch,
AP, port, radio and WAN is deleted with its history after the retention
window. Meanwhile the README tells the operator an empty answer can never
cause that.

---

# Round 4 (commit `90b975b` on `b5b3a16`, branch `build-18`)

**Verdict: APPROVE.** 0 BLOCKING / 3 WARNING (all carried: R2-W2, R2-W3,
R2-W4) / 1 NIT (new, pre-existing code).

Every round 3 finding is fixed and proven: R3-B1, R3-B2, R3-W1 and R3-N1
to N3. The zero-device case now declares no device kind, the docs list
exactly the guarded empty answers and say plainly what is not guarded, and
every new guard is killed by a mutant. Nothing in the hunt below turns an
empty, partial, contradictory or failed read into a miss, apart from one
implausible shape (R4-N1) that predates this build.

## Claims check (round 4)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 16 Java suites (new: `SiteListWatchTest`) and 14 Python wiring scripts. |
| `tests/test_vanished_wiring.py` run as a script | **Pass**, exit 0 (new `gap_logging()` section included). |
| validate-sdk | **Confirmed** `OK`. All three compat legs ran this time and are clean: 9.0 (`vrops-adapters-sdk-2.2.jar`, --release 17), 8.18.7 (--release 11) and 9.1.1.0100 (JDK 25, --release 25). Only the framework's existing deprecation note. |
| build-sdk | Reproduces `vcfcf_sdk_unifi_controller.0.0.0.18.pak` (`scratchpad/u18r4/dist/`). Adapter tree clean afterwards. |
| pak-compare 18 vs 0.0.0.17 (`scratchpad/u18r4/ref17/`, 17 only) | **0 BLOCKING, 1 WARNING, 1 INFO**, unchanged since round 2: `UniFiNvr` group attribute count 11 vs 10 (`Storage\|source`), manifest description. No describe, alert or symptom file touched, so dimension 13 is not triggered. |
| docs-gen on a scratch copy | Generated `docs/README.md` and `docs/inventory-tree.md` match the committed ones except the dev/release version stamp (0.0.0.18 vs 1.1.0.18). `_index_extra.md` and `docs/README.md` are in sync. |
| defect-gate | `no open blocking defects affecting unifi`. |
| `build_number` / CHANGELOG | Still 18; two round 3 lines added under 0.0.0.18 (fix + docs). Correct for an in-review build. |

## Zero-site driver, re-run (`scratchpad/u18r4/zs/`)

Updated to the new signatures (`sitesRead(count, rcOk)`,
`site(failed, list, rcOk, rows)`, `gateway(informing, hasWan1)`) and run
against the real `ReadKinds`, printing `leftOut()` too:

```
zero sites + protect                  -> []                         leftOut=[sites]
sites rc=error with rows + protect    -> []                         leftOut=[sites]
1 site, rc=error                      -> [Site, Aggregate]          leftOut=[devices-site, protect]
1 site, no meta                       -> [Site, Aggregate]          leftOut=[devices-site, protect]
1 site, zero devices (rc ok)  R3-B1   -> [Site, Aggregate]          leftOut=[devices-none, protect]
2 sites, zero devices each            -> [Site, Aggregate]          leftOut=[devices-none, protect]
site A zero, site B failed (stale 4)  -> [Site, Aggregate]          leftOut=[devices-site, protect]
1 site, data not a list               -> [Site, Aggregate]          leftOut=[devices-site, protect]
deviceRows negative                   -> [Site, Aggregate]          leftOut=[devices-none, protect]
informing gateway, no wan1    R3-W1   -> [... Gateway, Switch, AP, Port, Radio; no WAN]   leftOut=[wan, protect]
informing gateway, wan1               -> [... WAN included]         leftOut=[protect]
empty port + radio tables             -> [... no Port, no Radio]    leftOut=[port, radio, protect]
cameras []                            -> [... NVR, no Camera]       leftOut=[camera]
typeless record                       -> [Site, Aggregate]          leftOut=[devices-identity, protect]
```

`kinds()` and `leftOut()` come from one `evaluate()`, so they cannot
disagree; every left-out kind has a reason, and a complete read has none
(`leftOutMatchesKinds`).

## Mutation run (`scratchpad/u18r4-tools/mutate.py`)

28 mutants, **all 28 killed**, each by the test that owns it (wiring
mutants by running `test_vanished_wiring.py` as a script, exit code
checked, not under pytest).
- **New `ReadKinds` guards** (killed by `ReadKindsTest`): device-count
  check removed, `<= 0` weakened to `< 0`, the sum replaced by a constant,
  the sum replaced by last-site-wins, the `wan1` guard removed, the site
  list `rc` dropped, the site list count dropped.
- **`SiteListWatch`** (killed by `SiteListWatchTest`): no diff against the
  last list, last list never refreshed.
- **New wiring** (killed by the wiring script): device rows hardcoded 1,
  `wan1` presence hardcoded true, site list `rc` hardcoded true,
  `logVanishedReadGaps` call removed, the `siteListRead()` guard on the
  watch removed, `listedSites` not fed.
- **Round 3 set, re-run**: `failedSite`, `dropRc`, `rcAlways`, `portRows`,
  `radioRows`, `camRows`, `noIdentity`, `everySite` (ReadKindsTest);
  `holdNull`, `grace` (ProtectEdgeHoldTest); `wTypeless`, `wRcArg`,
  `wPortRows` (wiring).

## Round 3 findings, status

| Finding | Status |
|---|---|
| R3-B1 zero devices on every site | **Fixed.** `ReadKinds.site(..., deviceRows)` sums every record in `data`, registered or not (`ReadKinds.java` `site`, `evaluate` `devices-none`); the adapter passes `siteDevices.isList() ? size : 0` before any skip (`UniFiAdapter.java:657-661`). Tests: `zeroDevicesNamesNoDeviceKind` (one and two sites, 30 cycles, no miss, no mark), `oneEmptySiteAmongOthersIsRead`; wiring asserts the argument and that `read.site(` is called once. Driver and mutants above. |
| R3-B2 doc absolutes | **Fixed.** README, REFERENCE (Removed objects), `_index_extra.md`, generated `docs/README.md` and `overview.md` no longer claim "never proof" or "last object of a kind is never removed". They list the guarded empty answers, matching the code one for one (empty or `rc`-failed site list; no device on any site; `cameras: []` under a listed NVR; empty or missing port or radio table on a listed device; no `wan1` on a listed gateway), and say the last device *of a type* is removed while others are listed, with the switch, gateway and empty-site examples. Checked against the framework: misses count only in cycles that declare the kind, and a sighting in any cycle clears the tracker (`restoreReappeared`), so "12 consecutive complete cycles" is accurate. |
| R3-W1 no `wan1` | **Fixed.** `gateway(informing, hasWan1)`; `!dev.get("wan1").isNull()` is true for an absent key and for JSON null (`SimpleJson.isNull`). `wan2` is asserted not to gate the kind. Test `gatewayWithoutWan1KeepsWans`. |
| R3-N1 site list `meta.rc` | **Fixed.** `sitesRead(count, rcOk)`; the API map confirms `/proxy/network/api/self/sites` carries `meta.rc` (`unifi-network-api.md:159`). Test `siteListRcNotOkNamesNothing`. |
| R3-N2 silent removal-off | **Fixed.** `logVanishedReadGaps` logs each `leftOut()` reason at INFO, once per streak (`StreakLog` key `not-read|<reason>`, closed in `onCycleStart`). Bounded key set, no secrets, no per-resource spam. |
| R3-N3 site leaving the list | **Fixed.** `SiteListWatch`, one per `Configured`, fed only when `siteListRead()` (an empty or `rc`-failed list neither warns nor forgets). WARN names the site and the 12-cycle consequence. Synchronized for the discovery thread. Test `SiteListWatchTest`. |
| R2-W2 buildkit tag | **Open, carried.** `git ls-remote`: `sdk-buildkit-v1` still points at the v1.0.20 commit. A `v1.1.0.18` tag fails CI at compile until the tag moves to 1.0.22 or later. |
| R2-W3 live proof | **Open, carried**, folded into the devel proof list below. |
| R2-W4 docs generator `/recursive` | **Open, carried.** No factory `src/` change to the generator; the regenerated inventory tree is byte-identical bar the version stamp. |

## Hunt, round 4: empty, partial, contradictory or failed reads

| Path | Verdict |
|---|---|
| `/self/sites` empty, `rc` not ok, no `meta`, no list | Safe: nothing declared (or `Snapshot.build` throws). |
| every site `stat/device` `rc:ok`, `data: []` | Safe (R3-B1 fix). |
| `data: [null]` or records with no `type` | Safe: counted, but `deviceWithoutIdentity()` leaves device kinds out. |
| one site of many empty | Counts a miss for that site's devices. Accepted residual (a site can be empty; documented). |
| failed site carrying stale rows into the sum | No effect: `everySiteRead` is already false. |
| only pending-adoption records listed | Counted as records, so device kinds are declared. Accepted: on a UniFi OS console (the only supported platform, #17) the console's own gateway is always adopted, and a device that leaves adoption is the documented "removal follows the listing". |
| a type the pack does not know (or a type string that changes) | Not registered, not guarded. Accepted: an unknown type was never monitored; a relabel is a controller listing change. Speculative. |
| partial port, radio or camera list (fewer rows, not empty) | Missing rows count misses. Accepted: a transient partial answer must persist 12 declared cycles; a persistent one is what the controller reports. |
| gateway with `wan1` but no `wan2` | `wan2` counts a miss. Accepted and documented (a real configuration). |
| informing state, `adopted` absent | Treated as registered; no miss. Safe. |
| Protect bootstrap failure, no NVR, `cameras: []` | Safe. |
| a gap reason that persists | Now logged once at INFO per streak. |
| a miss count across a non-declared cycle | Framework: not counted, not reset; any sighting clears it. No path to a non-consecutive mark. |
| site leaves the list during a collector restart | The watch's first read only records, so no WARN, and the framework's in-memory tracker also restarts the count. Marking then happens 12 cycles later with only the framework's INFO. Accepted: R3-N3 asked for a WARN against the previous cycle, and there is none after a restart. |
| **a `/self/sites` row with no `name`** | **Site and Wireless Summary are declared, but the real site's key is not emitted, so it counts a miss. R4-N1.** |

## Findings (round 4)

### BLOCKING

None.

### WARNING

Carried, unchanged: **R2-W2** (buildkit tag), **R2-W3** (live proof; see
the devel proof list), **R2-W4** (docs generator `/recursive`, factory
TOOLSET GAP for `tooling`).

### NIT

- **R4-N1** `UniFiAdapter.java:646-650` (pre-existing, not in this
  commit's delta). Authority: skill § *Unreadable is NOT compliant*; the
  same identity rule this build applies to devices (`deviceWithoutIdentity`,
  R2-N2). A `/self/sites` row with no `name` emits a `UniFiSite` with a
  null `site_name` (probed: the SDK `ResourceKey` accepts a null
  identifier and does not throw, so enumeration completes), while
  `sitesRead` has already declared Site and Wireless Summary. The site
  whose row lost its name is not enumerated under its real key and counts
  a miss. The device kinds stay safe (the null site fails its
  `stat/device`, so `everySiteRead` is false). The shape is implausible
  (`name` is the key every site URL is built on) and would have to persist
  for 12 cycles, so this is a NIT. **Fix:** a `ReadKinds.siteWithoutIdentity()`
  that leaves Site and Wireless Summary out, called when `siteName` is null
  or blank, and skip emitting that row; plus a test and a wiring assertion.

## Registry check (`knowledge/context/defects.md`), round 4

There is no `defects.local.md`, so the factory registry applies. Both
entries with `Affects: unifi` are closed:
- **DEF-002**: closed. The stitch path is untouched by `90b975b`;
  `test_vanished_wiring.py` still pins `rb.parentForeign`.
- **DEF-007**: closed, not touched.

No open defects affect this pak; none proposed for closure.
`defect-gate --pak unifi` is clean. Registration candidates if they ship
unfixed: R2-W4 (and R2-W2 only if the tag is cut without moving the
buildkit tag, where CI would fail loudly rather than ship).

## What the devel proof must show

Before any of this: installing build 18 deletes the legacy orphans and
their history irreversibly, within about 7 hours on 9.0 devel (12 cycles
plus the 6 h retention). That needs Scott's explicit go-ahead, and an
export first of anything worth keeping (the Backyard camera). Then:

1. **Buildkit.** `sdk-buildkit-v1` moved to 1.0.22 or later, and the
   repo's tag CI builds `v1.1.0.18` green. The official CI pak, not the
   local build, is what gets installed for the proof.
2. **Steady state is quiet.** In the first cycles' adapter log, the only
   "Removal of vanished objects is off for ..." INFO lines are ones devel
   explains (for example `protect` if Protect is absent, `camera` if the
   camera list is empty). No `devices-site`, `devices-identity`,
   `devices-none`, `wan`, `port` or `radio` reason in steady state. If one
   appears, find out why before the 12 cycles run out: it means that kind
   will never be cleaned up.
3. **Exactly the orphans are marked** (R2-W3 d). About 12 cycles after
   install, the framework INFO "marked NOT_EXISTING this cycle" appears,
   and listing `resourceState=NOT_EXISTING` for `unifi_controller` gives
   exactly the expected set: `<mac>_0` switch ports, the Backyard camera
   `18E829CFAE3F`, the old gateway and its WANs, any `<mac>_` radio, any
   device registered while pending adoption. Nothing the controller still
   lists. Capture this before the 6 h retention deletes them.
4. **Live objects stay live.** Every site, gateway, switch, AP, WAN, port,
   radio, NVR and camera the controller lists is still `DATA_RECEIVING`
   after cycle 13, with continuous metrics.
5. **Renames kept identity** (R2-W3 b). The renamed objects ("udm" to
   "Bentwood", the `<label> (<parent>)` children) kept their resource IDs
   and history, with no duplicates.
6. **Stitch and children** (R2-W3 c). The vmnic to Switch Port stitch edge
   count and the HostSystem > Switch Port children match the pre-upgrade
   count.
7. **Protect blip** (R2-W3 e). One cycle without Protect keeps Site > NVR,
   logs the `protect` reason once at INFO, and marks no camera.
8. **Tree.** "UniFi Controller Infrastructure" shows World > Site > devices
   (round 1 a, already observed by the orchestrator; confirm on the CI
   pak).
9. Optional, only if it can be done harmlessly: no `WARN` "is no longer in
   the controller's site list" appears during the proof; if a test site is
   removed on purpose, the WARN names it once.

## If shipped as-is (round 4)

The pack removes what the controller stops listing, after an hour of
complete reads. An empty, failed or `rc`-error answer, a missing table or
`wan1`, or an unidentifiable record never counts toward removal; the one
exception is a site row with no name (R4-N1), which UniFi does not produce.
A list that is partial but not empty does count, and only matters if it
stays partial for the full hour. When removal is off for a kind, the log says why;
when a site leaves the list, the log says so. The upgrade itself deletes
the legacy orphans, as the README warns.

## Round 5 (fix round for R4-N1, 2026-10-28)

- **Commit reviewed:** b49ce78 on 90b975b (adapter branch `build-18`). Changed: `ReadKinds.java` (`siteWithoutIdentity()`, reason `site-identity`), `UniFiAdapter.java` (enumeration skip at 646-654, relationship skip at 1691-1692), ReadKindsTest, test_vanished_wiring.py, CHANGELOG, README, REFERENCE.md.
- **Verdict: APPROVE** (0 BLOCKING / 0 new WARNING, 3 carried / 2 NIT). R4-N1 is resolved on the paths it named. Two residual edges of the same implausible shape remain, both NIT.

### Independent re-runs

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass**, rc 0: 29 suites report all assertions passed (Java plus Python wiring), including `ReadKindsTest.siteWithoutNameLeavesSiteOut` and the `site-identity` case in `leftOutMatchesKinds`. The only other output is an existing Python DeprecationWarning in `test_build18_wiring.py:95`. |
| Test strength | 3 mutations in scratch exports of HEAD, **3 killed**: `siteWithoutIdentity()` made a no-op (ReadKindsTest: Site declared); the device-kind short-circuit replaced by `if (false)` (ReadKindsTest: Gateway declared); `read.siteWithoutIdentity()` removed from the enumeration guard (test_vanished_wiring fails on the pinned guard). |
| `validate-sdk` | OK. `VCFCF_SDK_COMPAT_REQUIRED=1`, javac 25, both `--sdk-compat-jar`: 9.0 (`--release 17`), 9.1.1.0100 (`--release 25`), 8.18.7 (`--release 11`) all clean. |
| pak-compare / dimension 13 | Not re-run: no describe, alert or symptom file is in the delta, so Round 4's result (0 BLOCKING) stands. |
| `defect-gate --pak unifi` | `no open blocking defects affecting unifi` |

### R4-N1

**Resolved** for what it named.
- `UniFiAdapter.java:646-654`: a null or blank `name` calls `read.siteWithoutIdentity()` and `continue`s before any `UniFiSite` is emitted, before `listedSites` is filled and before the site's devices are walked. test_vanished_wiring pins the guard's position ahead of `rcOf("UniFiSite"` and `read.site(`.
- `ReadKinds.evaluate`: with the flag set, Site, Wireless Summary and all six device kinds are left out, with one `site-identity` reason (logged once per streak at INFO by the existing `logVanishedReadGaps`). Protect is unaffected, which is right: NVR and cameras do not hang off a site's reads.
- `buildRelationships` (`UniFiAdapter.java:1691-1692`) skips the row in the site loop, so the World > Site, Site > device and Wireless Summary edges are never built on a null key.
- `ReadKinds` is new per cycle (`UniFiAdapter.java:626`), so the flag cannot stick.
- Docs: README:97-98, REFERENCE.md Removed objects table and bullet list, CHANGELOG line. All match the code.

### NIT

- **R5-N1. The Protect path still builds a Site key from row 0 without the name check.**
  - **Where:** `UniFiAdapter.java:1682-1684` (`nvrSite` from `data[0].name`) and `1796-1815` (the NVR's parent `siteKey` from `firstSite`).
  - **Authority:** the same as R4-N1 (skill § *Unreadable is NOT compliant*; no key without identity).
  - If the nameless row is the first one and Protect has an NVR: `nvrParentSite` returns `null` whether or not the null site is in `failedSites` (it is first, or it is failed), and `Objects.equals(null, null)` is true, so `rb.parent(siteKey, nvrKey)` puts the NVR under a `UniFiSite` with a null `site_name`. Round 4 established that the SDK accepts a null identifier, so this does not throw; it is a phantom parent edge. The snapshot also still asks `stat/device` for site `null` (`UniFiAdapter.java:2140-2147`), which fails and logs one WARN per cycle naming site `null`.
  - **Fix:** skip the NVR parent edge when `siteName` is null or blank (the NVR keeps its stored edge, as for an unread site), and leave nameless rows out of `siteNames` in the snapshot. Same implausible shape as R4-N1, so NIT.
- **R5-N2. A nameless row can produce a misleading "no longer in the site list" WARN.** `listedSites` skips the nameless row, but `logVanishedReadGaps` still calls `siteWatch.update(listedSites)` because `siteListRead()` is true. If the row that lost its name was a known site, the WARN says its objects are marked after 12 cycles, which they are not while `site-identity` holds. Skip the `siteWatch` update in a cycle with a nameless row (`UniFiAdapter.java:825-826`).

### WARNING (carried, unchanged)

**R2-W2** (buildkit tag), **R2-W3** (live proof; Round 4's devel proof list stands unchanged), **R2-W4** (docs generator `/recursive`, factory TOOLSET GAP for `tooling`).

### Registry check (`knowledge/context/defects.md`), round 5

No `defects.local.md`; the factory registry applies. Both entries with `Affects: unifi` are closed:
- **DEF-002**: closed. The stitch path is untouched by b49ce78.
- **DEF-007**: closed, not touched.

No open defects affect this pak; none proposed for closure. `defect-gate --pak unifi` is clean. Registration candidates unchanged from Round 4 (R2-W4; R2-W2 only if the tag is cut without moving the buildkit tag).

### If shipped as-is (round 5)

As Round 4, without its one exception: a site row with no name now counts nothing toward removal for sites or devices. If that row were ever the first one with Protect installed, the NVR would also get a parent edge to a nameless phantom site, and a known site might be named in a WARN that overstates what happens next. UniFi does not produce that shape.
