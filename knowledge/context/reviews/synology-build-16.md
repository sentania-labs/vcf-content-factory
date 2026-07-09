# SDK Adapter Review — synology build 16

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 16 (commit `306e678`, "restore Datastore cross-link via v2
  Suite API transport") — **scoped to the 15+16 delta** over the APPROVEd build 14
  (`554c571`). Build 15 (`ebf9b69`, "redact secrets, contract-assert critical
  endpoints") was un-reviewed and is included in scope.
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 1 NIT
- **Date:** 2026-06-10
- **Authority baseline:** build-14 review (`knowledge/context/reviews/synology-build-14.md`),
  v1 reference source (factory `8e6cea0`), golden baseline
  (`knowledge/context/investigations/synology_v1_golden_baseline_devel.md`),
  spec/19 §3 relationship contract, `knowledge/lessons/synology-dsm-client-side-joins.md`,
  `knowledge/lessons/foreign-resource-property-push.md`, `knowledge/rules/no-secrets-on-disk.md`.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed by direct run.** `validate-sdk content/sdk-adapters/synology` → "OK: … is a valid Tier 2 SDK adapter project." **4** source files now compiled (was 3 in build 14; +`SynologyStitcher.java`), only the benign `-source 11` system-modules warning. |
| `pak-compare` 16-vs-15 = 0/0/0 | **Confirmed by direct run.** Built both paks (`build-sdk` of HEAD and of `ebf9b69` via a throwaway worktree) and ran `pak-compare 16 15` → **"No structural divergences found. Score: 0 BLOCKING, 0 WARNING, 0 INFO."** Matches the author exactly. Builds 15+16 are pure Java + docs; `describe.xml` is byte-unchanged, so all 103 keys / 9 data kinds + adapter instance / identifiers / traversal are untouched. |
| C2 single-jar pak shape preserved | **Confirmed.** v16 `adapters.zip`: `synology_diskstation/lib/` = exactly one `vcfcf-adapter-base.jar`; adapter jar at root; all classes `com.vcfcf.adapters.synology` (now incl. `SynologyStitcher` + `SynologyStitcher$SuiteApiDatastoreBridge`); no `com/vmware/tvs`, no `.java`. |
| `build_number` bumped + CHANGELOG | **Confirmed.** `adapter.yaml` 14→16; CHANGELOG `1.0.0.15` and `1.0.0.16` entries present, accurate, thorough. Minimal diff, no drive-by refactor. |

`build-sdk` was run (twice) for the pak-compare; **CHANGELOG.md / REFERENCE.md
restored** (`git checkout --`), the throwaway worktree removed and pruned, all
`/tmp` artifacts deleted. **synology and factory trees left clean** (verified
`git status --short` empty, HEAD `306e678`).

---

## Build 15 — secret redaction + hollow-payload assert (priorities 1, 6)

### Redaction audit — complete, every secret-bearing site covered

`SynologyApiClient.redact()` (`SynologyApiClient.java:200`) masks `_sid=`,
`passwd=`, `account=` (case-insensitive, `[^&]*` value span). I enumerated
**every** throw/log site that can carry a query string or session id and traced
each:

- **`callRaw` non-200 throw** (`:186`) — `"HTTP " + code + " from " + redact(path)`.
  Covers the WARNING-2 finding from build 14: the login URL's `passwd=`/`account=`
  and every authenticated call's `_sid=` are now masked before the message can
  reach the on-disk adapter log / Test-connection error. ✔
- **`logout` WARN** (`:73`) — `redact(String.valueOf(e.getMessage()))`. Covers
  the newly-activated `_sid`-on-disk path build 14 introduced via
  `componentLogger`. ✔
- **`login` failure throw** (`:58`) — `"… error code " + code` — no secret. ✔
- **`login` success INFO** (`:61`) — `session=` SESSION_NAME constant only. ✔
- **`call` re-auth INFO** (`:171`) — `code=` integer only. ✔
- **`call` non-success throw** (`:177`) — `api + " " + method + " failed: " +
  resp.asString()`. This is the **response body**, not the request path; it
  carries no `_sid`/`passwd`/`account` (DSM does not echo the request URL in the
  error envelope; login failures take the `:58` path, not this one). No leak. ✔

`_sid` terminal-position case checked: for endpoints with no `extra` params
`_sid` is the last query param (no trailing `&`); `(?i)(_sid=)[^&]*` matches to
end-of-string correctly. **No missed site.** `knowledge/rules/no-secrets-on-disk.md`
WARNING-2 from build 14 is **resolved.**

### Hollow-but-200 contract asserts — correct, no false-trip (priority 1)

`Snapshot.build` (`SynologyAdapter.java:947`+) now throws `IOException` when
`dsmInfo.data().get("model").isNull()` or `utilization.data().get("cpu")
.isNull()`. This closes the build-14 NIT-1 empty-as-readable corner: a
`{success:true,data:{}}` payload that previously published `cpu_load_1m=0.0` /
`system_temp=0.0` sentinels on a GREEN instance now surfaces as ERROR (the
throw propagates out of `currentSnapshot` → `collect`, marking all resources
ERROR per the build-14-verified unreadable-is-loud path). The two asserted
fields are the *required* roots of the two endpoints that drive the diskstation
singleton metrics — a legitimate DSM `getinfo` always carries `model` and a
healthy `Utilization.get` always carries `cpu` (golden baseline confirms both
populated). The assert keys on `.isNull()` (absent/null), **not** on emptiness
or value, so it cannot false-trip on a legitimate response that merely has a
benign sub-field missing. Correct, minimal, traces to skill *Unreadable is NOT
compliant*. ✔

---

## Build 16 — Datastore cross-link via SynologyStitcher (priorities 1, 5, 7)

### 2a. Transforms vs the v1 reference — byte-for-byte

Compared against v1 `synologyUuidToNaa` / inline NFS path (factory `8e6cea0`,
`stitchDatastores`):

- **NAA / LUN path** (`SynologyStitcher.lunDataStorePath` :88). v1: split UUID on
  `-`, rejoin parts with `d` separator, `"naa.6001405" + sb.substring(0,
  min(25,len))`; caller wraps `"VMFS:|" + naa + "|"`. Build 16: identical split/
  join, identical `naa` construction, returns `"VMFS:|" + naa + "|"`.
  **Byte-for-byte identical**, plus a null/empty guard (returns `null`). ✔
- **NFS path** (`nfsDataStorePath` :107). v1: `(volPath.startsWith("/") ?
  substring(1) : volPath) + "/" + name`, key = `ip + "/" + serverPath`. Build 16:
  same strip, returns `nasIp + "/" + serverPath + "/" + shareName` →
  `ip + "/" + volPathStripped + "/" + share`. **Identical**, plus null-volPath
  hardening (→ `""`). ✔
- **Connected-NAS-IP extraction** (`connectedNasIps` :122). v1: per-NIC, add `ip`
  iff non-empty and `status=="connected"`. Build 16: identical predicate, plus
  null/list-shape guards on the snapshot slice. ✔ Reads the **cached**
  `Snapshot.networkInterfaces` — no new live call (v1 made a fresh
  `networkInterfaceList()` here; build 16 reuses the per-cycle snapshot, an
  improvement, not a behavior change). ✔
- **NFS rule gate.** v1 probed `nfsSharePrivilege` per share live and `continue`d
  on `rule.size()==0` or probe exception. Build 16 reads
  `Snapshot.nfsRulesByShare` (populated in `Snapshot.build:1143-1154`, which only
  stores shares with `rule.size()>0` and WARN-skips probe failures) and gates on
  `rules==null || rule.size()==0`. **Behavior-equivalent** (non-NFS / failed-probe
  shares yield no edge). ✔

No transform deviation. The NAA OUI comment changed cosmetically (v1 "OUI 001405"
vs build-16 "OUI 6001405") — doc only, the literal `"naa.6001405"` is identical.

### 2b. Mis-stitch risk — no NEW ambiguity (priority 5, the priority)

The resolver loads VMWARE Datastores by `DataStrorePath` and matches by exact
map lookup (`datastoresByPath.get(path)`) — **path identity, never bare MOID**,
satisfying the MOID-trap requirement (`knowledge/lessons/foreign-resource-property-push.md`,
skill *ARIA_OPS stitching identity*). The match keys are **byte-identical to v1**
(NAA for LUNs, `ip/volPath/share` for NFS), so every ambiguity that exists —
NAA collision across two NASes, two NASes exporting the same `volPath/share` on
the same IP — **existed identically in v1**. Per the orchestrator's gate
(same-as-v1 ambiguity acceptable, NEW ambiguity not), there is **no new
mis-stitch vector**: a non-matching key drops the edge (no edge emitted), it
never redirects an edge onto the wrong host. A wrong match would require two
real VMWARE Datastores to share one `DataStrorePath`, which the platform's own
identity model forbids; `loadAll` last-wins on a duplicate key, same as v1's
`Map<String,ResourceKey>`. ✔

### 2c. Degradation honesty — all three paths traced in source

- **Ambient unavailable** → `configure`'s `try { SuiteApiStitcher.create(...) }
  catch (RuntimeException e)` (`SynologyAdapter.java:148`+) catches the
  `IllegalStateException` `create()` throws when `maintenanceuser.properties` is
  absent, sets `suiteStitcher=null` / `stitcher=null`, emits **one** `logWarn`
  ("Datastore cross-link skipped — Suite API unavailable …"). `emitDatastoreCross
  Link` then early-returns on `st==null` (no-op, no second WARN). The 25 keyed
  resources collect on the unrelated per-resource path. ✔ One WARN, stitcher
  null, cross-link no-op, all 25 collect — exactly as claimed.
- **Emission fault** (Suite API reachable, `get`/parse throws) → `loadDatastores`
  delegates to `ForeignResourceResolver.loadAll`, whose `fetchAndCache`
  (`ForeignResourceResolver.java:258`) catches **all** exceptions, WARNs, and
  returns an empty map — `loadAll` never throws. Belt-and-braces: the entire
  `emitDatastoreCrossLink` body is wrapped in `try/catch (Exception)` →
  `logWarn("… internal topology unaffected …")`. Critically, `emitDatastore
  CrossLink(rb, s)` runs **before** `return rb.build()`, and the internal tree
  edges are already in `rb`, so a cross-link fault never costs the cycle its
  relationships. ✔ Caught, WARNed, internal topology preserved.
- **Zero datastores on a working API** → loop finds no matches, `logInfo
  ("Datastore cross-link: 0 datastores loaded, 0 LUN matches, 0 NFS matches")`.
  INFO only, no WARN, no phantom edge. ✔

### 2d. The v1 departure — no phantom keys, and the golden edge is preserved

Build 16 resolves against **real loaded inventory** (`matchByPath` returns a key
only when `datastoresByPath.get(path) != null`) — it never mints a bare
`VMWARE/Datastore` key from a computed path, which is the v1 behavior the
CHANGELOG calls out. Confirmed in source: `matchByPath` (:77) returns `null` on a
miss, and the LUN/NFS loops `continue` on `ds==null`. No edge without a real
Datastore behind it. ✔

**Cannot-drop-a-v1-edge check (the wld01 iSCSI LUN):** golden baseline §2.8
(line 635) records `relationships|Datastore_parent=vcf-lab-wld01-cl01-iscsi` on
`SynologyIscsiLun/vcf-lab-wld01-cl01` (`lun_uuid=d023e190-8940-485a-8bf1-
47f41ae0c0a5`). I walked build-16's logic against that identifier:
`lunDataStorePath("d023e190-8940-485a-8bf1-47f41ae0c0a5")` →
`"VMFS:|naa.6001405d023e190d8940d485ad8bf1d4|"`, which the stitching api-map
(`8e6cea0:knowledge/context/api-maps/synology-vcfops-stitching.md:284`) confirms is the
`DataStrorePath` of the `vcf-lab-wld01-cl01-iscsi` Datastore. So **given a
reachable Suite API, build-16 `matchByPath` resolves this exact Datastore and
emits the edge** — the v1-landed edge is preserved in the baseline scenario, not
dropped. ✔

### 2e. Stitcher lifecycle — clean, no credential material in logs

Created in `configure` with `componentLogger(SuiteApiStitcher.class)` /
`componentLogger(SynologyStitcher.class)` (the framework-instance logger, not
`java.util.logging`). Discarded in `onDiscard` (`SynologyAdapter.java:1001`+):
`suiteStitcher.discard()`, both fields nulled, `super.onDiscard()` called — the
compliance pattern. No credential material in any stitcher log line: the
configure WARN logs the `IllegalStateException` message ("credential file
absent/unreadable" — no secret), and the bridge builds a `/api/resources?
adapterKind=…&resourceKind=…` path with no credentials (ambient token handled
inside `SuiteApiStitchClient`). ✔

---

## Findings

### WARNING

- **[SynologyAdapter.java emitDatastoreCrossLink :931 `rb.parentForeign(ds, …)` /
  RelationshipBuilder.build → spec/19 §3]** — *Full-set `setRelationships` on a
  **foreign** parent — devel-provable, not static-provable.* `rb.build()` emits
  `setRelationships(datastore, {synologyLun/export})` per parent, which spec/19
  §3 (line 190) documents as a **"FULL replacement for a parent's child set —
  platform DIFFS against current state."** v1 made the Datastore the LUN's parent
  via the old aria-ops-core `Resource.addParent` (child-declares-parent,
  additive); build 16 uses the SDK-native full-set-on-parent form against a
  **VMWARE-owned** Datastore. The framework explicitly markets `parentForeign` +
  `build()` as the supported cross-adapter idiom (`RelationshipBuilder` javadoc
  example) and spec/19 line 213–214 endorses a cross-MP `ResourceKey` as parent
  with platform de-dupe by identity — but **I cannot prove from the code alone**
  that the platform scopes the Datastore's child set per-reporting-adapter rather
  than letting synology's `setRelationships(Datastore, {lun})` replace the
  Datastore's VMWARE-collected HostSystem/VM children. This is the one residual
  risk in the cross-link and it lands on a foreign resource. It does **not** gate:
  the edge direction is identical to v1, the design is orchestrator-approved, and
  the only authoritative disproof is a live collect (does the wld01 Datastore
  retain its HostSystem/VM edges *and* gain the LUN child?). → **Smallest correct
  fix / hand-off:** make the live devel golden-collection proof
  (`qa-tester` / orchestrator) an **explicit acceptance criterion** — after a
  build-16 collect against the devel instance, confirm `vcf-lab-wld01-cl01-iscsi`
  shows **both** its pre-existing VMWARE child set **and** the new SynologyIscsiLun
  child. If the VMWARE children are clobbered, switch to a delta/labeled emission
  (`addRelationships` or `setGenericRelationships(parent, …, label)`) for the
  foreign parent rather than full-set `setRelationships`. Static review cannot
  close this; the devel proof must.

- **[SynologyStitcher.java SuiteApiDatastoreBridge.listResources :180–181]** —
  *Resolved Datastore key marks every identifier `isUnique=true`.* The bridge maps
  each Datastore's `resourceIdentifiers` into the resolver's `String[]{name, val,
  "true"}` shape with the uniqueness flag **hardcoded `"true"`** regardless of the
  Datastore's actual identifier uniqueness in VMWARE's describe. The resolver
  (`ForeignResourceResolver.java:244`) then builds the foreign `ResourceKey`
  marking those identifiers unique. If a non-unique VMWARE Datastore identifier is
  mis-marked unique, the platform's identity de-dupe (spec/19 line 214) may fail
  to match the real Datastore and the cross-link edge **silently does not land**.
  This is a *degradation* (missing informational edge), **never a wrong-host
  stitch** — a non-matching key drops the edge, it cannot redirect it. Compliance
  is no precedent here (it resolves foreign resources by UUID and pushes
  *properties*, not relationship edges). Does not gate (informational edge only,
  no false-pass, no corruption). → **Fix / hand-off:** in the same devel proof,
  confirm the matched edges actually land on the real Datastores; if any expected
  edge is missing, have the bridge carry the Datastore's true per-identifier
  uniqueness (from the `identifierType` block) instead of a blanket `"true"`.

### NIT

- **[CHANGELOG.md 1.0.0.16 / commit message]** — the entry says the cross-link
  makes "the Datastore's existing HostSystem/VM edges light up … for free," which
  is the *intent* but presumes the full-set `setRelationships` on the foreign
  Datastore is additive in the platform's view (the open question in WARNING-1).
  Tidy to note the additive-vs-replace behavior is confirmed by the devel collect,
  not asserted. Documentation precision only.

## Build hygiene (priority 9) — clean

`build_number` 14→16 in `adapter.yaml`; both `1.0.0.15` and `1.0.0.16` CHANGELOG
entries present, accurate, and unusually thorough (they document the exact
transform, the optional-semantics degradation, and the phantom-key departure).
Minimal, confined diff: build 15 = redact helper + two asserts; build 16 = one
new `SynologyStitcher` class + the `configure`/`onDiscard`/`buildRelationships`
wiring. No drive-by refactor. The generalization (restoring the cross-link over
the new transport) is proven behavior-preserving on the 103 keys (pak-compare
16-vs-15 = 0/0/0; `describe.xml` byte-unchanged) and on the v1 transform
(byte-for-byte, §2a above). `knowledge/lessons/synology-dsm-client-side-joins.md` (the
charter for this very NAA/NFS-path stitch) is honored, not violated.

## If shipped as-is

An operator installs build 16 and gets the build-14 collection surface intact
(25 resources / 103 keys / internal storage tree, C2 single-jar pak) **plus**
two safety upgrades and one restored cross-link: (1) a failed login / non-200 /
logout can no longer write the DSM password or `_sid` into the adapter log or
Test-connection error (build-15 redaction — the build-14 WARNING-2 is closed);
(2) a hollow-but-200 DSM payload now surfaces as ERROR instead of publishing
`0.0` sentinel metrics on a GREEN instance (build-15 asserts — build-14 NIT-1
closed); (3) on a node co-located with the Suite API, each iSCSI LUN / NFS export
backing a real VMWARE Datastore re-gains v1's informational
`Datastore → LUN/export` cross-link (the build-14 WARNING-1 deferral, now
decided and implemented), resolved by path identity and never minting a phantom
Datastore. On a remote collector without `maintenanceuser.properties` the
cross-link is skipped with one WARN and all 25 resources still collect. **The
single thing the live devel proof must still confirm** (WARNING-1): that the
full-set `setRelationships` onto the foreign Datastore is *additive* in the
platform's view and does not replace the Datastore's VMWARE-collected
HostSystem/VM children — a question static review cannot close. Nothing in this
review blocks promotion to that devel/`qa-tester` gate.

## Verification artifacts

- `validate-sdk content/sdk-adapters/synology` → OK, 4 sources compiled, 1 benign
  `-source 11` warning (direct run).
- `pak-compare` 16-vs-15 → **0 BLOCKING / 0 WARNING / 0 INFO** ("No structural
  divergences found") — both paks built locally (HEAD + `ebf9b69` worktree),
  direct run.
- v16 pak C2 shape: single `vcfcf-adapter-base.jar` in `lib/`; adapter jar at
  root carries `SynologyStitcher` + `SynologyStitcher$SuiteApiDatastoreBridge`;
  all classes `com.vcfcf.adapters.synology`; no `com/vmware/tvs`, no `.java`.
- NAA transform `d023e190-8940-485a-8bf1-47f41ae0c0a5` →
  `VMFS:|naa.6001405d023e190d8940d485ad8bf1d4|` reproduces the golden-baseline
  wld01 edge target (api-map `8e6cea0` line 284) — v1 edge preserved.
- `redact()` covers `callRaw` throw (:186), `logout` WARN (:73); no other
  secret-bearing throw/log site in `SynologyApiClient`.
- `adapter.yaml` build_number 14→16; CHANGELOG 1.0.0.15 + 1.0.0.16 present.
- `build-sdk` run for the comparison; CHANGELOG.md/REFERENCE.md restored,
  worktree removed, `/tmp` cleaned — **synology + factory trees left clean**
  (`git status --short` empty, HEAD `306e678`).

## Report
`knowledge/context/reviews/synology-build-16.md`
