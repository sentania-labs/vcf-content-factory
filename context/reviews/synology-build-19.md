# synology — build 19 (`1.0.0.19`) review

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 19 (`1.0.0.19` RC, pre `v1.0.0.19` tag)
- **Reviewed against:** prior release `1.0.0.18` (the build-18 RC) — working-tree delta
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT
- **Reviewer:** sdk-adapter-reviewer
- **Re-spin of:** `context/reviews/synology-build-18.md` (1 BLOCKING on DEF-001)

## Claims check (independently re-run)

| Gate | Result |
|---|---|
| `validate-sdk` (schema) | **confirmed** — valid Tier 2 project. |
| `validate-sdk` (compile, `VCFCF_SDK_JAR` set) | **confirmed** — clean compile of all 4 sources against the framework base jar + `vrops-adapters-sdk-2.2.jar`; 1 benign `-source 11 system modules` warning. |
| `build-sdk` | **confirmed** — builds `vcfcf_sdk_synology_diskstation.1.0.0.19.pak`, adapters.zip 101,998 bytes. |
| `pak-compare` vs compliance ref (`1.0.0.51`) | **confirmed** — 2 WARNING, 0 BLOCKING (install gate passed), matches author. |
| `pak-compare` vs prior release `1.0.0.18` | **confirmed** — "No structural divergences found" (0/0/0). No regression to the internal resource tree, kinds, identifiers, metrics, or describe paths. |
| `defect-gate --pak synology` | **confirmed** — still refuses (DEF-001 open in the registry). Expected: the gate releases only after the orchestrator records the closure this review certifies. |

`build_number` bumped 18 → 19 (`adapter.yaml`); `CHANGELOG.md` carries a matching `1.0.0.19` entry describing exactly the two delta items (DEF-001 transport-path redaction + NFS dedup). Minimal diff — the Java delta is confined to the two reported changes; pak-compare vs 18 is structurally empty.

## DEF-001 closure — DEFINITIVE: **YES, closeable.**

The single residual leak vector flagged in build-18 BLOCKING-1 is closed. Concrete evidence:

1. **The transport-exception leak is now caught and scrubbed.**
   `SynologyApiClient.callRaw` (`src/com/vcfcf/adapters/synology/SynologyApiClient.java:195-215`)
   now wraps `http.get(path, …)` in `try { … } catch (IOException e)` and rethrows a
   **standalone** `IOException`:
   ```java
   throw new IOException("transport error calling " + endpoint + ": "
           + redact(String.valueOf(e.getMessage())));   // no chained cause
   ```
   - **(a) No chained cause** — confirmed: the rethrow is `new IOException(msg)`, not
     `new IOException(msg, e)`, so `getCause().getMessage()` cannot resurface the URI to
     the framework logger. Matches the fix the build-18 review specified verbatim.
   - **(b) `redact()` strips secrets** (`SynologyApiClient.java:226-232`): three
     case-insensitive replacements scrub `_sid=`, `passwd=`, and `account=` values up to
     the next `&`. Because `urlEncode` percent-encodes `&`/`=` inside the credential
     (→ `%26`/`%3D`), the entire URL-encoded password is captured by `[^&]*` and replaced —
     passwords with special characters are fully redacted. Even in the worst case where
     `e.getMessage()` is the full login URI, no `passwd`/`account`/`_sid` value survives.
   - **(c) No other unguarded `http.get` / path-bearing throw exists.** Full-adapter grep:
     the only throws are `login():58` (error-code only), `call():178`
     (`api+method+resp.asString()` — the API JSON body, never a secret; pre-existing and
     accepted at build 18), `callRaw:212` (endpoint label only), and the new `callRaw:208`
     (endpoint label + redacted message). `logout():73` already redacts. A grep across the
     whole adapter for any throw/log statement embedding a path or `passwd`/`account`/`_sid`
     token returns **only explanatory comments** — no code path.

2. **All realistic transport failures land in the catch.** `ManagedHttpClient.get`
   (base jar) declares `throws IOException, InterruptedException` and internally turns
   `ConnectException` into a DNS round-robin that rethrows `ConnectException`/`IOException`.
   `ConnectException`, `SSLHandshakeException`, `HttpConnectTimeoutException`, and generic
   `IOException` are all `IOException` subclasses → all caught by `callRaw`. The framework's
   own `java.util.logging` round-robin WARN (`ManagedHttpClient:308`) logs only
   `ce.getMessage()` ("Connection refused", no URI) and per the class contract does not
   reach the adapter log.

**Authority:** `rules/no-secrets-on-disk.md` (RULE-008); skill § *Gaps / secrets*; DEF-001.

**Proposed closing-evidence for `context/defects.md` (orchestrator to record):**
> Fixed in synology build 19 (`1.0.0.19`), 2026-06-26,
> `src/com/vcfcf/adapters/synology/SynologyApiClient.java:195-215`. `callRaw` wraps
> `http.get` in try/catch and rethrows a standalone `IOException` built from the `endpoint`
> label only, with `redact()` applied to the message and no chained cause; `redact()`
> (lines 226-232) strips `_sid`/`passwd`/`account`. Verified statically: validate-sdk
> compile-clean; full-adapter grep shows no throw/log emits a raw path or secret token
> (comments only); pak-compare vs `1.0.0.18` = 0/0/0 (no regression). This is a
> statically-provable secret-on-disk capability — no live devel collect is owed for closure
> (the same static basis on which DEF-003's secret half was treated). Residual is
> framework-scoped only (see NIT-1), not adapter-fixable and unreachable in practice.

## NFS fan-out dedup — correct, drops no legitimate edge

`SynologyAdapter.java:970-996`. The per-export `Set<ResourceKey> linkedDs` is declared
**inside** the `for (SimpleJson share …)` loop (`:979`), so each export gets a fresh set.
`if (!linkedDs.add(ds)) continue;` skips emitting `parentForeign(ds, exportKey)` only when
the **exact same** `ResourceKey` was already linked for **this** export.

- `ResourceKey` overrides `equals`/`hashCode` (verified via `javap` on
  `com.integrien.alive.common.adapter3.ResourceKey`) — value-based over
  name/kind/adapterKind + identifiers, consistent with the build-18 foreign-key
  uniqueness analysis (the 4-tuple-vs-2-tuple binding fix relies on exactly this).
- **Distinct datastores are never collapsed:** N vCenter copies of a shared datastore carry
  distinct `(VMEntityObjectID, VMEntityVCID)` identifiers → distinct keys → both retained
  (matches `matchByPath` returning all copies). Different exports → separate sets → never
  merged.
- **Only** the same datastore reached via two NAS IPs (the intended scope) is deduped, so
  the platform no longer receives `setRelationships(ds, {export, export})` with a duplicate
  child. The iSCSI loop is single-pass and correctly untouched.

This precisely resolves the build-18 NIT (`SynologyAdapter.java:986-988`). The
`nfsMatches++` counter now sits inside the dedup guard — a cosmetic, correct change to the
INFO count only.

## Registry check (`context/defects.md`)

- **DEF-001** (synology, blocking, open) — **RESOLVED in build 19. Propose CLOSE** with the
  concrete evidence above. The build-18 BLOCKING is genuinely fixed; the registered
  capability (a path/`_sid`/`passwd`/`account`-bearing message reaching the on-disk log or
  Test-connection) is no longer reachable from any adapter code path. `defect-gate` still
  refuses only because the registry entry is still `open` — that flips once the orchestrator
  records the closure.
- **DEF-003** (synology, blocking, closed) — **re-asserted, remains correctly closed.** The
  `parentForeign(ds, child)` full-set `setRelationships`-onto-foreign-Datastore idiom is
  unchanged for both iSCSI LUN (`SynologyAdapter.java:961`) and NFS Export (`:992`);
  pak-compare vs 18 = 0/0/0 confirms no change to the relationship shape. Residual stands:
  9.1 unverified — re-prove at the first 9.1 target.
- **DEF-002** (unifi), **DEF-004** (vcommunity-os) — do not affect synology.

## NIT

- **NIT-1 — [`ManagedHttpClient.get` / base jar, out of adapter scope]** — A malformed URI
  would make `URI.create(baseUrl + path)` throw `IllegalArgumentException` (a
  `RuntimeException`, *not* caught by `callRaw`'s `IOException` catch), whose message would
  carry the raw URI. This is **(a)** framework/base-jar code the adapter author cannot edit,
  **(b)** effectively unreachable — `urlEncode` produces a valid query string, so normal
  credentials never trip it, and **(c)** identical in every prior build, not a regression.
  Not blocking. The belt-and-suspenders tester-surface redaction the build-18 review
  suggested (scrub at `getTester`'s thrown message) would also neutralize this and any
  future framework-side path leak; worth tracking as defense-in-depth if the orchestrator
  wants it registered, but it does not gate the `v1.0.0.19` tag.
- **NIT-2 — [`SynologyStitcher.java:116-117`]** — `logger.warn("… load failed: " +
  ex.getMessage())` on the Suite API Datastore load is unredacted. This is the
  Suite-API/stitch side — no Synology DSM `_sid`/`passwd` flows here, so it is outside
  DEF-001's secret scope (same low-risk note as the build-18 NIT on
  `SynologyAdapter.java:378`); an unredacted `getMessage()` could at most surface a
  Suite-API/local-file detail. Consider routing through a redactor for consistency.

## Verified correct (no finding)

- **No regression to build-18 work** — pak-compare `1.0.0.19` vs `1.0.0.18` = 0 BLOCKING /
  0 WARNING / 0 INFO. The foreign-key uniqueness fix (`SuiteApiDatastoreBridge` propagates
  the real `isPartOfUniqueness`, `SynologyStitcher.java:246-247`), the
  `parentForeign(datastore, child)` direction for both storage types, the multi-datastore
  fan-out (`matchByPath → List<ResourceKey>`, per-copy emit loops), and the symmetric
  describe paths are all intact and unchanged.
- **Cardinal correctness (unreadable ≠ compliant)** — unchanged and safe: `loadDatastores`
  still wraps the bridge call in try/catch → empty index + WARN, never throws out of the
  relationship pass; a missing match → `continue`, never a fabricated edge.

## If shipped as-is

An operator hitting a connect/SSL/timeout failure during Synology login (wrong host, cert
mismatch, NAS unreachable) now gets a Test-connection / log message identifying the failing
endpoint with **no** plaintext password, account, or `_sid` — the build-18 leak is closed.
Cross-MP datastore stitching is unchanged and no longer double-emits an NFS export child
when a NAS is multi-homed. Safe to tag `v1.0.0.19` once the orchestrator records the DEF-001
closure (which flips `defect-gate` green).
