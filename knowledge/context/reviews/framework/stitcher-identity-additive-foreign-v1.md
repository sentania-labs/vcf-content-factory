# Framework Review — stitcher identity + additive foreign-parent write-verb

- **Area:** `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/`
  (`AmbientCredential`, `RelationshipBuilder`, `SuiteApiStitchClient`, `SuiteApiStitcher`)
- **Change:** (1) ambient credential selection now prefers
  `automationuser.properties` (automationAdmin) with soft-fallback to
  `maintenanceuser.properties`; (2) foreign-parent relationship edges emit via
  additive verbs (`addRelationships`/`addGenericRelationship`) instead of
  full-set `setRelationships`.
- **Verdict:** APPROVE
- **Date:** 2026-07-01
- **Design-of-record:** `knowledge/designs/stitcher-identity-and-additive-foreign-v1.md`

## Checks re-run (independently, this reviewer)

- **validate-chain:** `python3 -m vcfops_managementpacks validate` — **PASS**.
  5 Tier 1 defs valid; 6 Tier 2 adapters (compliance, synology, unifi,
  vcommunity, vcommunity-os, vcommunity-vsphere) all recompile against the
  modified framework source.
- **build-framework.sh:** clean — SDK-only classpath, no aria-ops-core /
  TVS residue.
- **tests:** re-compiled + ran all three suites against the real
  `vrops-adapters-sdk-2.2.jar` + freshly-built `vcfcf-adapter-base.jar`:
  - `AmbientCredentialTest` — **13/13** (encrypted round-trip SKIPs, as
    tooling reported: platform `Crypt` `NoClassDefFoundError` in sandbox — the
    unencrypted path exercises the same plumbing).
  - `RelationshipBuilderTest` — **8/8**.
  - `SuiteApiStitchClientTest` — **18/18** (re-run because its source changed).
- **render-regression:** n/a (no renderer/template/builder touched).
- **pak-compare:** n/a (no pak structure changed this round; downstream
  republish obligation noted below).
- **scope check:** only the 4 stitch `.java` files + 2 new test files moved
  under `vcfops_*/`. The other working-tree changes (`recon_log.md`,
  `designs/`, `.claude/agents/sdk-adapter-author.md`, new `context/` notes)
  are pre-existing investigation artifacts, out of scope for this verdict.

## Findings

**0 BLOCKING / 0 WARNING / 2 NIT**

### Verified safe (the review-focus items)

1. **Fallback preserves today's behavior on boxes without the automation
   file.** `buildCandidates()` returns `[automation, maintenance]`; a node
   lacking `automationuser.properties` hits `!Files.exists → continue`, then
   loads `maintenanceuser.properties` via the identical `loadFromPath` — the
   exact pre-change code path. Byte-for-byte preserved.
2. **Crash-the-cycle guarantee holds (synology build 21/22).** The change
   *reduces* hard-throws on the ambient production path: an unreadable
   automation file now soft-falls-through to maintenance (old code threw on
   *any* unreadable candidate). Exception propagation out of
   `SuiteApiStitchClient.Builder.build()` (IOException → IllegalStateException,
   only when neither ambient nor explicit resolves) is unchanged. No new
   escape into the collection cycle.
3. **Silent-downgrade is now observable.** `SuiteApiStitchClient` INFO log
   adds `file=<sourceLabel>`; a CP that falls back to maintenance and resolves
   `cloudproxy_<uuid>` now logs `file=maintenance principal=cloudproxy_<uuid>`
   — the misconfiguration is signalled, not silent. No secret leaked:
   `getPassword()` is never logged; only sourceLabel + principal + endpoint.
4. **Verb-split correctness verified against the real SDK.**
   `RelationshipBuilderTest` proves, live against `vrops-adapters-sdk-2.2.jar`,
   that `setRelationships → isClearFirst()==true` (own parents) and
   `addRelationships → isClearFirst()==false` (foreign parents), on both plain
   and generic child paths, including the mixed local+foreign cycle (2
   clear-first + 1 additive). `javap` on `Relationships$RelationshipItem`
   confirms `isAdd()`/`isClearFirst()` are the real public API. `childForeign`
   keeps its internal parent full-set. Additive never issues clear-first.
5. **No cross-entry / cross-instance leak.** `foreignParent` is a per-`ParentEntry`
   instance field; `parentMap`/`keyCache` are per-builder instances; `Candidate`
   has final fields; `buildCandidates()` reads `System.getProperty` fresh each
   call. No mutable static, no shared-builder reuse. The
   own-vs-foreign-same-key concern is structurally impossible: `ResourceKey`
   embeds `adapterKind`, so an owned parent and a foreign parent can never
   collide on the same `parentMap` key.
6. **Invariants intact.** `SuiteApiDatastoreBridge` (`DataStorePath`,
   `isPartOfUniqueness`) not in the diff; `VcfCfAdapter` base/transport/SSL not
   in the diff; the explicit-credentials branch (build 21/22 hardening) is
   byte-for-byte unchanged; `SuiteApiStitcher.java` is javadoc-only (confirmed
   line-by-line). No new jars / no aria-ops-core reintroduced.

### NIT

- **[AmbientCredential.java:279-288] Override-absent path is a behavior delta
  (documented, non-production).** Old code, when the
  `vcfcf.suiteapi.credential.path` sysprop was set but the file *did not
  exist*, fell through to the maintenance default; new code returns
  `[override]` only, so an absent override now hard-exhausts to `IOException`
  with no maintenance fallback. This is intentional and documented (class
  javadoc + design-of-record), and the sysprop is test-harness-only — `grep`
  confirms no production adapter sets it. No production path regresses. Raised
  only so the delta is on record.
- **[downstream] Buildkit republish obligation.** This is framework Java that
  every Tier 2 adapter compiles in via the buildkit; it is inert until the
  buildkit tarball is republished and each adapter re-pulls (design already
  captures "one buildkit republish"). Not a `bundles/` dist-zip staleness case
  (no `vcfops_packaging/templates`, `builder.py`, or `render.py` touched), so
  the CLAUDE.md dist-zip rebuild rule does not fire — but the fix does not
  reach any live adapter until the republish + re-pull happens.

## If shipped as-is

Correct and low-risk. On a Cloud Proxy the stitcher will authenticate as the
RBAC-bearing `automationAdmin` (fixing the CP-403 Synology stitch failure) and
its identity is now visible in the INFO log; foreign-parent edges become
clobber-safe additive writes matching the vendor TVS corpus. Older nodes
without the automation file behave exactly as before. No operator-visible
regression on any path. Takes effect only after the buildkit is republished
and adapters re-pull.
