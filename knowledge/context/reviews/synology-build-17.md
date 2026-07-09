# SDK Adapter Review — synology build 17

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 17 (commit `5a87337`, "§22 collect-path discovery + pick up
  framework d59785a") — scoped to the delta over build 16 (`e4f4465` = build-16
  commit `306e678` + two CI-only commits `e777189`/`e4f4465`).
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 1 NIT
- **Date:** 2026-06-10
- **Authority baseline:** build-16 review (`knowledge/context/reviews/synology-build-16.md`),
  build-14 review (`knowledge/context/reviews/synology-build-14.md`), sibling reviews this
  round (`compliance-build-50.md`, `unifi-build-5.md`) for the §22 framework
  contract and the bytecode-verified framework jar, framework §22
  (`knowledge/context/framework_v2_migration.md`), investigation
  `knowledge/context/investigations/unifi_401_and_relationship_persistence_2026_06_10.md`,
  golden baseline (`knowledge/context/investigations/synology_v1_golden_baseline_devel.md`),
  skill *Unreadable is NOT compliant*, `knowledge/lessons/synology-dsm-client-side-joins.md`,
  `knowledge/lessons/foreign-resource-property-push.md`, `knowledge/rules/no-secrets-on-disk.md`,
  `knowledge/rules/no-fabricated-metrics.md`.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| 1. Framework jar pickup = the three d59785a fixes only | **Confirmed by sha256 + bytecode.** Bundled `vcfcf-adapter-base.jar` = `0e873aec…b0a8f15`, **byte-identical** to the jar the sibling `unifi-build-5` / `compliance-build-50` reviews disassembled this round (and to the runtime reference `adapter_runtime/vcfcf-adapter-base.jar`). I additionally disassembled `ForeignResourceResolver` from THIS pak's jar: `new ResourceKey(entry.name, entry.resourceKind, entry.adapterKind)` — the **corrected** arg order (fix #2). RelationshipBuilder swap (fix #1), Host-header removal + 401-retry (fix #3) are cited from the byte-identical sibling disassembly. No adapter source carries these — `SynologyApiClient.java`/`SynologyConfig.java` byte-unchanged this build. |
| 2. §22 adoption, snapshot-served enumeration == build-16 discoverer output | **Confirmed equivalent per kind** (full table below). `getDiscoverer()` deleted, `discoverOnCollect()=true` (`:269`), `enumerateResources(ResourceSink)` (`:271`) serves entirely from `currentSnapshot()` — no new API calls. NFS gate `s.nfsRulesByShare.containsKey(name)` and UPS gate `s.ups != null` reduce to the **same probe + same predicate** the old discoverer ran inline. No resource kind can appear/disappear vs build 16. |
| 3. rcOf untouched → keys byte-identical → 25 devel resources de-dup, no duplication | **Confirmed.** `rcOf` is not in the diff hunk (body unchanged). describe.xml byte-unchanged (pak-compare 0 descriptor divergences). Same kinds/id-keys/id-values/emission order → platform de-dups by identifying identifier. |
| 4. No-double-retry; 401 path framework-side and inert for synology | **Confirmed.** Synology wires **no AuthStrategy** (DSM session is a `_sid` query param, not the framework's cookie/header auth) — verified `SynologyApiClient` unchanged, no AuthStrategy attach anywhere. The framework 401-retry is therefore inert for synology; DSM session recovery stays client-side (JSON codes 106/107/119, single re-auth in `call()`). DSM returning HTTP 200 for expired sessions means the framework HTTP-status retry can't see it. No double-retry path. |
| 5. pak-compare 17-vs-16 = 0/0/1 INFO (manifest wording) | **Confirmed by direct run.** `pak-compare 17 16` → **0 BLOCKING / 0 WARNING / 1 INFO**. The lone INFO is the `manifest.txt` description: build 17 drops `VcfCfDiscoverer` from the SPI list and adds the §22 collect-path-discovery note. describe.xml / all 9 kinds / 103 keys / identifiers / traversal byte-unchanged. |

`validate-sdk` → OK, 4 sources compiled, only the benign `-source 11` warning.
`build-sdk` run (build 17 + build 16 already present in factory `dist/`);
synology repo tree left **clean** (HEAD `5a87337`, `git diff` empty — no
CHANGELOG/REFERENCE side effects); factory `dist/` paks are gitignored; only the
review `.md` files are untracked in the factory tree.

## §22 equivalence — old discoverer vs new snapshot-served enumeration (claim 2, hard)

Diffed the deleted `getDiscoverer()` body against the new `enumerateResources`
for **every** resource kind. The snapshot fields are populated by the **same API
calls with the same predicates** as the old standalone probes:

| Kind | Old discoverer (standalone probe) | New enumerate (snapshot field) | Source-of-truth | Equivalent |
|---|---|---|---|---|
| World | unconditional `dr.addResource` | unconditional `sink.accept` | — | YES |
| Diskstation | `api.dsmInfo()` serial/model | `s.dsmInfo` (`Snapshot.build:1064`, same call) | identical call | YES |
| StoragePool / Volume / Disk / SsdCache | `api.storageLoadInfo()` lists | `s.storage` (`:1069`) | identical call | YES |
| IscsiLun | `api.iscsiLunList()` luns | `s.lunList` (`:1070`) | identical call | YES |
| NfsExport | per-share `api.nfsSharePrivilege(name)`, gate `rule.size()>0` | `s.nfsRulesByShare.containsKey(name)` | `buildLookups:1160-1171` runs **the same probe with the same `rule.size()>0` gate**; `containsKey` true iff old would have added | YES |
| Ups | `api.upsGet()`, gate `usb_ups_connect` | `s.ups != null` | `Snapshot.build:1095-1099` sets `s.ups` iff `upsGet()` succeeds AND `usb_ups_connect==true` | YES |

**Probe-failure behavior also preserved.** A per-share NFS probe failure: old
discoverer `catch`→`logWarn`, share not added; new path — `buildLookups` `catch`
→`logWarn`, share absent from `nfsRulesByShare`→`containsKey` false→not added.
UPS unavailable: old `catch`→`logInfo`, skip; new — `Snapshot.build` `catch`
→`logInfo`, `s.ups` stays null→skip. **No kind can appear/disappear vs build 16.**

**One intentional, safe-direction divergence (recorded, not a finding):** the old
discoverer made its probes in isolated try/catch scopes and never asserted
`model`/`cpu`; the new path folds enumeration onto `Snapshot.build`, which carries
the build-15 hard-fail on a hollow-but-200 `dsmInfo`/`utilization` payload
(`:1084-1093`). So a hollow DSM payload that the old *discoverer* would have
tolerated (it would still have enumerated the static tree) now throws during
enumeration. This is **louder**, not quieter — it cannot produce a silent empty
or a fabricated resource (skill *Unreadable is NOT compliant*), so it is an
improvement, not a regression. Noted for the operator-impact line.

## Cardinal correctness — unreadable-is-NOT-invisible (the primary hunt) — PASS

Traced the full enumeration failure path for THIS adapter:

- `enumerateResources` (`:271`) calls `currentSnapshot()` and serves from it. On
  a session/REST/contract failure, `Snapshot.build` **throws a checked Exception**
  (`call()`/`callRaw` throw on `!isSuccess()`/non-200; the build-15 asserts throw
  on hollow `model`/`cpu`), which propagates out of `currentSnapshot()` (`:399`)
  and out of `enumerateResources`.
- `currentSnapshot()` (`:399-408`) assigns `this.snapshot` **only after**
  `Snapshot.build` returns (`:404-405`); a failed build never installs an empty
  snapshot and never returns null (it builds or throws).
- Per the framework §22 contract (same jar, bytecode-traced in `unifi-build-5`):
  the `discoverOnCollect()=true` path (`onCollect`) catches a thrown enumeration
  → WARN, registers **nothing**; the `onDiscover()` path catches → setErrorMsg.
  Both are loud; neither fabricates an empty resource set.

**`enumerateResources` can NOT silently emit zero resources on a partial/failed
snapshot** — a partial snapshot throws before the first `sink.accept`. The brief's
silent-zero-registration BLOCKING scenario does not exist.

## Bare-instantiation safety (same trace as unifi) — PASS

- Synology **overrides** `enumerateResources` (`:271`), so the framework default
  `discoverOnCollect()=true`-without-override `UnsupportedOperationException`
  never fires.
- `currentSnapshot()` on a fresh instance (`this.snapshot==null`) **builds** — it
  never returns null and never NPEs on a null field; a build failure throws.
- Per the framework bare-instantiation-safety contract (`VcfCfAdapter` javadoc,
  bytecode-confirmed in `unifi-build-5`), **describe/install never calls
  `enumerateResources`** — the NPE-kills-describe scenario cannot occur.

Net for a fresh synology instance: either build+enumerate, or fail loudly
(WARN/error, zero resources that attempt, retry next cycle). **No silent empty,
no describe-killing NPE.**

## Stitch corruption — the ForeignResourceResolver-fix interaction — PASS (no NEW vector)

`SynologyStitcher.java` is **byte-unchanged** this build (confirmed by diff). The
build-16 cross-link logic — path-identity match (`datastoresByPath.get(path)`),
byte-identical NAA / `ip/volPath/share` keys to v1, **never bare MOID** — is
exactly as APPROVEd in build 16 (`knowledge/lessons/foreign-resource-property-push.md`,
skill *ARIA_OPS stitching identity*).

The framework `ForeignResourceResolver` ResourceKey-swap fix (verified in this
pak's bytecode: `new ResourceKey(name, resourceKind, adapterKind)`) **activates**
a previously-inert path: the build-16 cross-link's VMWARE/Datastore foreign keys
now `compareTo`-match and the edges **actually persist for the first time**. This
makes *correct* (path-identity) matches land — it **cannot** make a wrong-host
match land that path identity wouldn't already permit. A non-matching key still
drops the edge (no redirect). **No new mis-stitch vector.**

It does, however, move the two build-16 WARNINGs from *latent* (edges emitted but
never persisted) to *live* (edges now persist). They carry forward below — both
remain devel-provable degradation, never a false-pass or wrong-host stitch, so
neither gates.

## Findings

### WARNING

- **[carry-forward from build-16 WARNING-1 — now live] SynologyStitcher /
  RelationshipBuilder.build → spec/19 §3 full-set `setRelationships` on a FOREIGN
  parent.** The cross-link emits `setRelationships(Datastore, {synologyLun/export})`
  on a **VMWARE-owned** Datastore, which spec/19 §3 documents as a FULL
  replacement of that parent's child set. Static review cannot prove the platform
  scopes the Datastore's child set per-reporting-adapter rather than letting
  synology's full-set replace the Datastore's VMWARE-collected HostSystem/VM
  children. **Build 16 deferred this to the devel collect; build 17's framework
  fix makes the edge actually persist, so the devel proof is now REQUIRED, not
  optional.** → **Hand-off:** after a build-17 collect against devel, confirm
  `vcf-lab-wld01-cl01-iscsi` shows **both** its pre-existing VMWARE child set
  **and** the new SynologyIscsiLun child. If VMWARE children are clobbered, switch
  the foreign parent to a delta/labeled emission (`addRelationships` /
  `setGenericRelationships(parent,…,label)`). Does not gate (no false-pass, no
  wrong-host stitch — at worst a foreign parent loses informational children,
  surfaced by the devel proof).

- **[carry-forward from build-16 WARNING-2 — now live] SynologyStitcher
  SuiteApiDatastoreBridge.listResources — hardcoded `isUnique="true"`.** The
  bridge marks every resolved Datastore identifier unique regardless of VMWARE's
  actual describe. If a non-unique identifier is mis-marked unique, the platform's
  identity de-dupe may fail to match the real Datastore and the cross-link edge
  **silently does not land**. With the resolver fix now making matches persist,
  this is the live gate on whether real edges appear. **Degradation only**
  (missing informational edge), never a wrong-host stitch. → **Hand-off:** in the
  same devel proof, confirm matched edges land on real Datastores; if any expected
  edge is missing, carry the Datastore's true per-identifier uniqueness instead of
  a blanket `"true"`. Does not gate.

### NIT

- **[SynologyAdapter.java class javadoc / CHANGELOG 1.0.0.17 — "visible from the
  cycle they are first seen"]** — resources *register* into the first collect
  cycle's embedded DiscoveryResult, but their **metrics** arrive on the **next**
  cycle (the per-resource collect loop iterates the inbound `resources` set, empty
  on cycle 1). This is the framework's standard one-cycle discover→collect
  latency, identical to the `unifi-build-5` NIT. → **Fix (optional):** reword to
  "resources appear on the first collect; metrics follow on the next cycle" so a
  fresh-instance acceptance test doesn't flag an empty-metrics first cycle as a
  regression. Non-blocking.

## Hunts cleared (verified safe)

- **Unreadable-is-NOT-invisible:** PASS. A partial/failed snapshot throws before
  the first `sink.accept`; enumeration never silently emits zero resources.
- **Crash-the-cycle / bare-instantiation:** PASS. `enumerateResources` overridden
  (no default-throw); `currentSnapshot()` builds-on-null / throws-on-fail (no
  NPE); describe/install never calls it.
- **Stitch corruption:** PASS — stitcher byte-unchanged; framework fix activates
  correct path-identity matches only; no new mis-stitch vector. Two build-16
  WARNINGs carry forward as now-live devel-provable degradation.
- **No-double-retry / 401:** PASS. No AuthStrategy wired; framework 401 path inert;
  DSM session recovery client-side, single retry; DSM 200-on-expired means the
  HTTP-status retry can't see it.
- **Redaction (_sid/passwd/account):** PASS. `SynologyApiClient` byte-unchanged;
  the build-15 `redact()` at `callRaw` throw (`:186`) and `logout` WARN (`:73`)
  intact. The one new log line (`logInfo("Synology enumerate: …")`) emits counts
  only — no secret. `knowledge/rules/no-secrets-on-disk.md` clean.
- **Build hygiene:** PASS. `build_number` 16→17 in `adapter.yaml`; matching
  1.0.0.17 CHANGELOG entry, accurate and thorough; minimal diff (one Java file =
  §22 refactor, + version/docs); no drive-by refactor. The generalization
  (one enumeration body, two framework callers) is proven behavior-preserving by
  the per-kind equivalence table + pak-compare 0/0/1.

## If shipped as-is

An operator installs build 17 on VCF Ops 9.0.2 and, for the first time, gets a
**fresh** Synology instance that actually discovers its 25 resources: build 16
relied on `onDiscover()`, which 9.0.2 never invokes for adapter3-path collectors,
so a fresh instance would heartbeat GREEN yet sit at zero resources forever — §22
collect-path discovery fixes that, enumerating from the top of every collect
cycle with the identical resource set (no duplication of the 25 devel resources;
keys byte-identical). Three framework fixes ride entirely in the refreshed
bundled jar with no adapter-code change: (1) the v2 relationship edges synology
was emitting now **persist** (RelationshipBuilder ResourceKey swap fixed);
(2) the build-16 Datastore cross-link's VMWARE/Datastore foreign keys are now
**matchable** (ForeignResourceResolver swap fixed — verified in this pak's
bytecode); (3) the JDK-forbidden Host header that crashed Synology 3036 on
multi-homed NAS paths since ~06-07 is gone. A fresh instance with no snapshot
fails **loudly** (WARN/error, zero resources that attempt, retry next cycle)
rather than NPE-ing describe or silently enumerating empty. The two things the
**live devel proof must now confirm** (both WARNINGs, now live because the edges
persist): that the full-set `setRelationships` onto the foreign Datastore is
*additive* and does not clobber its VMWARE HostSystem/VM children, and that the
matched LUN/NFS→Datastore edges actually land. Both are degradation-at-worst, not
false-passes; nothing in this static review blocks promotion to that
devel/`qa-tester` gate.

## Verification artifacts

- `validate-sdk content/sdk-adapters/synology` → OK, 4 sources, 1 benign
  `-source 11` warning (direct run).
- `build-sdk` → `dist/vcfcf_sdk_synology_diskstation.1.0.0.17.pak`
  (adapters.zip 100,210 B) from clean `5a87337` tree (direct run).
- `pak-compare 17 vs 16` → **0 BLOCKING / 0 WARNING / 1 INFO** (manifest
  description wording: drops `VcfCfDiscoverer`, adds §22 note) — direct run.
- Bundled `vcfcf-adapter-base.jar` sha256 `0e873aec…b0a8f15` == sibling-verified
  jar (`unifi-build-5` / `compliance-build-50`) == runtime reference jar.
- `ForeignResourceResolver` bytecode (direct `javap` on THIS pak's jar):
  `new ResourceKey(entry.name, entry.resourceKind, entry.adapterKind)` — corrected
  arg order (fix #2).
- C2 pak shape: single `vcfcf-adapter-base.jar` in `lib/`; adapter jar
  `synology_diskstation.jar` at adapters root, 7 classes all
  `com.vcfcf.adapters.synology` (incl. `SynologyStitcher`, no `VcfCfDiscoverer`
  lambda); no `com/vmware/tvs`, no `.java`.
- Diff scope (`e4f4465`→`5a87337`): `SynologyAdapter.java`, `adapter.yaml` (16→17),
  `CHANGELOG.md` only. `SynologyStitcher.java` / `SynologyApiClient.java` /
  `SynologyConfig.java` / `describe.xml` / `conf/` byte-unchanged.
- §22 per-kind equivalence: World/Diskstation/Pool/Volume/Disk/SsdCache/Lun via
  same snapshot calls; NfsExport via `nfsRulesByShare` (same probe+`rule.size()>0`
  gate, `buildLookups:1160-1171`); Ups via `s.ups` (same `usb_ups_connect` gate,
  `Snapshot.build:1095-1099`). No kind can appear/disappear vs build 16.
- synology tree clean (HEAD `5a87337`, `git diff` empty); factory `dist/` paks
  gitignored; only review `.md` files untracked.

## Report
`knowledge/context/reviews/synology-build-17.md`
