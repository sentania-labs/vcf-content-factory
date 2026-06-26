# synology — build 18 (`1.0.0.18`) review

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 18 (`1.0.0.18` RC, pre `v1.0.0.18` tag)
- **Reviewed against:** prior release `v1.0.0.17` (working-tree diff)
- **Verdict:** CHANGES REQUESTED
- **Findings:** 1 BLOCKING / 0 WARNING / 3 NIT
- **Reviewer:** sdk-adapter-reviewer

## Claims check (independently re-run)

| Gate | Result |
|---|---|
| `validate-sdk` | **confirmed** — clean compile (4 source files, 1 benign `-source 11 system modules` warning). Run with the repo's `4eabad…` base jar + `vrops-adapters-sdk-2.2.jar`. |
| `build-sdk` | **confirmed** — builds `vcfcf_sdk_synology_diskstation.1.0.0.18.pak`, adapters.zip 101,704 bytes. |
| `pak-compare` vs compliance ref | **confirmed** — 2 WARNING, 0 BLOCKING (install gate passed), matches author. |
| `pak-compare` vs prior release `1.0.0.17` | **confirmed** — "No structural divergences found" (0/0/0). No regression to the internal resource tree, kinds, identifiers, or metrics. |
| `defect-gate --pak synology` | **confirmed** — refuses release: DEF-001 open blocking. |

`build_number` bumped 17 → 18 (`adapter.yaml`); `CHANGELOG.md` carries a matching `1.0.0.18` entry. Minimal diff — no drive-by refactors in the internal collect tree (pak-compare vs 17 is clean).

## Registry check (`context/defects.md`)

- **DEF-001** (synology, blocking, **open**) — **STILL PRESENT. Do NOT close.**
  The build fixes the *primary registered* path (the `callRaw` `"HTTP <code> from <path>"`
  throw, which fired on every non-200 and carried `_sid` on every call + `passwd` plaintext
  on login). But a **residual leak path survives**: the transport exception thrown by
  `http.get(path,…)` inside `callRaw` is uncaught, and on the login call `path` carries
  `passwd=<plaintext>` / `account=`. See BLOCKING-1. `defect-gate` correctly still refuses the
  release. Closure not proposable.
- **DEF-003** (synology, blocking, **closed**) — **re-asserted, remains correctly closed.**
  Build 18's `parentForeign(ds, child)` for both iSCSI LUN and NFS Export is exactly the
  full-set `setRelationships(ds,{child})`-onto-foreign-Datastore idiom proven adapter-scoped-safe
  on devel 9.0.2 (build 16; `lessons/setrelationships-foreign-adapter-scoped.md`). Verified the
  write is still adapter-scoped (`RelationshipBuilder.parentForeign` → one `setRelationships`
  per foreign parent in `doBuild`). **Residual stands: 9.1 unverified** — re-prove at the first
  9.1 target. The 0.0.0.21 `childForeign` experiment is correctly reverted.
- **DEF-002** (unifi), **DEF-004** (vcommunity-os) — do not affect synology.

## BLOCKING

### BLOCKING-1 — DEF-001 not fully closed: login/collect transport-exception path is unredacted (plaintext password reachable)

- **Where:** `src/com/vcfcf/adapters/synology/SynologyApiClient.java:195-202` (`callRaw`),
  reachable via `SynologyAdapter.java:207` (`getTester` → `testApi.login()`) and the collect
  path (`ensureSession()` → `login()`).
- **Authority:** `rules/no-secrets-on-disk.md` (RULE-008); skill § *Gaps / secrets*; DEF-001.
- **What's wrong:** `callRaw` only guards the *HTTP-response* branch:
  ```java
  HttpResponse<String> resp = http.get(path, ...);          // <-- can THROW, uncaught
  if (resp.statusCode() != 200) {
      throw new IOException("HTTP " + resp.statusCode() + " from " + endpoint);  // fixed: safe
  }
  ```
  The `http.get(path, …)` call itself can throw `IOException` / `ConnectException` / SSL /
  timeout *before* any response. That exception is **not caught** in `callRaw`, `login`,
  `ensureSession`, or `call`, so it propagates unredacted. On the **login** call,
  `path = /webapi/entry.cgi?...&account=<user>&passwd=<URL-encoded plaintext password>&...`.
  The framework logs collect-path exception messages to the on-disk adapter log and **surfaces
  tester exceptions on Test-connection** (DEF-001's own described surface) — so a transport
  exception whose message embeds the request URI lands the plaintext password on disk / on the
  Test-connection result.
- **Why this is unproven-safe (skeptic default):** the author's *own* logout handler
  (`SynologyApiClient.java:70-74`) guards exactly this possibility —
  `// e.getMessage() may carry the request URL (with _sid) if the underlying transport embeds it`
  — and redacts there. The build applies that guard to the strictly **less** sensitive logout
  variant (`_sid` only) but leaves the **most** sensitive call (login, `passwd` plaintext)
  unguarded. The stated DEF-001 acceptance bar is "NO path/secret *can* reach the on-disk log
  or Test-connection." The capability demonstrably remains. Cannot certify closure.
- **Smallest correct fix:** wrap the `http.get` in `callRaw` so no raw transport message escapes —
  rethrow with the `endpoint` label only and **do not chain the raw cause** (chaining re-exposes
  `getCause().getMessage()`), mirroring the logout handler's `redact(...)` discipline:
  ```java
  try {
      HttpResponse<String> resp = http.get(path, HttpResponse.BodyHandlers.ofString());
      if (resp.statusCode() != 200) {
          throw new IOException("HTTP " + resp.statusCode() + " from " + endpoint);
      }
      return SimpleJson.parse(resp.body());
  } catch (IOException e) {
      throw new IOException("transport error calling " + endpoint + ": "
              + redact(String.valueOf(e.getMessage())));   // no chained cause
  }
  ```
  (Belt-and-suspenders: also redact at the tester surface so any escape is caught before
  Test-connection.) Re-prove DEF-001 closure with a thrown-transport-error test showing the
  message carries no `passwd`/`account`/`_sid`/path.
- **If shipped as-is:** the registered plaintext-password-on-disk defect is only partially
  fixed; a connect/SSL/timeout failure during login (a common real condition: wrong host,
  cert mismatch, NAS unreachable) can still write the operator's NAS password to the adapter
  log and the Test-connection error. `defect-gate` already blocks the tag — correctly.

## NIT

- **[`SynologyAdapter.java:378`]** — `collectRelationships` catch logs
  `logWarn("Relationship build failed: " + e.getMessage())` unredacted. This path is the
  Suite-API/stitch side (no Synology DSM `_sid`/`passwd` flows here), so it is outside DEF-001's
  secret scope, but an unredacted `getMessage()` could surface a `maintenanceuser.properties`
  path or Suite-API detail. Consider routing through `redact(...)` for consistency.
- **[`SynologyAdapter.java:146-151`]** — `catch (RuntimeException e) … e.getMessage()` on the
  Suite-API-client create failure is likewise unredacted; same low-risk note (local file path,
  not a secret).
- **[`SynologyAdapter.java:986-988` / NFS fan-out]** — `RelationshipBuilder.ParentEntry.children`
  is an `ArrayList`. If two `nasIps` resolve to the same `DataStrorePath`, `parentForeign(ds,
  exportKey)` is added twice to the same parent → `setRelationships(ds, {export, export})` with a
  duplicate child. Harmless (platform dedups by `ResourceKey`) but sloppy; a `seen`-set or
  per-export dedup would be cleaner. iSCSI loop is single-pass and not affected.

## Verified correct (no finding)

- **Multi-datastore fan-out** (`SynologyStitcher.matchByPath` → `List<ResourceKey>`): null/empty
  safe (`Collections.emptyList()` on null path and on missing key); both emit loops iterate and
  emit one `parentForeign` per datastore copy. N distinct datastore copies = N distinct
  `ResourceKey` identities = N distinct `setRelationships` parents — no cross-copy clobber.
- **Foreign ResourceKey uniqueness fix:** `SuiteApiDatastoreBridge` now propagates the real
  per-identifier `isPartOfUniqueness` via `…get("isPartOfUniqueness").asBoolean()` (defaults
  **false** when absent — `SimpleJson.asBoolean` returns false on null/missing — so it never
  over-marks). The Stitcher's direct key construction (`loadDatastores`) mirrors
  `ForeignResourceResolver.fetchAndCache` **exactly** — `Boolean.parseBoolean(id[2])` honored as
  element[2], same `ResourceKey(name, kind, adapterKind)` + `addIdentifier(ResourceIdentifierConfig(
  name, value, isUnique))`. The foreign Datastore key is now the correct 2-tuple identity and
  binds. The multimap reuses these corrected flags.
- **Cardinal correctness (unreadable ≠ compliant):** `loadDatastores` wraps the bridge call in
  try/catch → empty index + WARN on failure, never throws out of the relationship pass; a missing
  match → skip (`continue`), never a fabricated edge. No score/`pass` synthesis on read failure.
- **DEF-003 direction:** `parentForeign(ds, child)` for both storage types = full-set
  `setRelationships` onto foreign Datastore (proven adapter-scoped-safe); describe.xml uses the
  inverse `::~child` modifier symmetrically and is UI-navigation only (NFS proven to persist with
  no declarative path).
