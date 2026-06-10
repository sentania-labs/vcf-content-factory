# SDK Adapter Review — synology build 14

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 14 (commit `554c571`, "framework v2 migration") vs v1 build 13 (`12fe1ff`)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 2 NIT
- **Date:** 2026-06-10
- **Scope:** first multi-resource v2 framework port (compliance build-48 is the
  precedent chain). Full v1→v2 SPI reshape of `SynologyAdapter.java` + logger
  swap in `SynologyApiClient.java`; `describe.xml` byte-unchanged; parity bar
  = golden baseline (25 resources / 136 metrics).

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed by direct run.** `validate-sdk content/sdk-adapters/synology` → "OK: … is a valid Tier 2 SDK adapter project." 3 sources compiled, only the benign `-source 11` system-modules warning. |
| `pak-compare` vs v1 build-13 = 0/0/4-INFO | **Confirmed by direct run** on the author's `dist/vcfcf_sdk_synology_diskstation.1.0.0.14.pak` vs `dist/vcfcf_synology_diskstation.1.0.0.13.pak`: **0 BLOCKING / 0 WARNING / 4 INFO**. The 4 INFO are all expected: I1 `overview.packed` (cosmetic), I2 description wording (`stitch`→`merge`), I3 `aria-ops-core-8.0.0.jar` + I4 `vrops-adapters-sdk-2.2.jar` absent from factory — the **point** of the C2 shape. |
| `pak-compare` vs compliance 48 = 0/2W/35-INFO | **Confirmed by direct run.** **0 BLOCKING / 2 WARNING / 35 INFO** — matches the author exactly. The 35 INFO are all cross-adapter content/profile/image/jar-name differences (compliance ships dashboards/reports/profiles/views; synology ships its 9 ResourceKind icons + traversal). |
| The 2 WARNINGs are legitimate domain differences | **Confirmed benign** (see below). |
| C2 pak shape: lib/ = `vcfcf-adapter-base.jar` only | **Confirmed.** Inside `adapters.zip`: `synology_diskstation/lib/` holds exactly one jar (`vcfcf-adapter-base.jar`); the adapter jar `synology_diskstation.jar` sits at the adapters root (correct C2 layout). No `aria-ops-core` / `vrops-adapters-sdk` bundled. |
| framework jar = runtime reference | **Confirmed by sha256.** Embedded `vcfcf-adapter-base.jar` = `5b570289bf48ec7e…`, **byte-identical** to `vcfops_managementpacks/adapter_runtime/vcfcf-adapter-base.jar`. |
| no `com.vmware.tvs.*`, no `.java` leak | **Confirmed.** Adapter jar = 5 classes, all `com.vcfcf.adapters.synology`; no class references `com/vmware/tvs`; no `.java` in the pak. |

No `build-sdk` run by this review — the author's pre-built v14 pak was sufficient
for all pak-compare/structure checks; CHANGELOG.md / REFERENCE.md untouched;
synology and factory trees left clean.

## The 2 compliance-48 WARNINGs — judged benign

- **W1 (adapter-instance identifier count: synology 3 vs compliance 4).**
  Synology's instance identifiers are `host` / `port` / `allowInsecure` (3) —
  **identical to the v1 golden baseline** (baseline §2.1 line 60) and byte-
  unchanged in `describe.xml`. Compliance carries a 4th (vCenter-specific).
  This is a per-adapter connection-param difference, not a defect.
- **W2 (TraversalSpecKind count: synology 1 vs compliance 0).** Synology owns a
  real internal resource tree (World>Diskstation>Pool>Volume>{LUN,NFS,SSDCache,
  Disk}) and declares one `GENERIC_RELATION` traversal for it; compliance owns no
  tree (it stitches onto foreign HostSystem). The synology traversal is **byte-
  identical to v1** (`describe.xml` diff v13→v14 is empty). Correct domain
  difference, benign.

Both WARNINGs are structural artifacts of comparing a self-contained storage-tree
adapter against a foreign-stitching compliance adapter — neither indicates a
synology defect.

## Lesson-compliance (priority 1) — all green

- **Keyed constructors** `super(ADAPTER_KIND)` / `super(ADAPTER_KIND, dir, id)`
  (SynologyAdapter.java:77–83). ✔
- **No `onDescribe` override** — framework default; only an explanatory comment
  block at :86. ✔ (`lessons/controller-describe-bare-instantiation.md`)
- **No `adapterLogger()` shadow** — no private `adapterLogger`, no
  `getAdapterLoggerFactory()`; the only mention is a doc-comment in the client.
  Helper logger is `componentLogger(SynologyApiClient.class)` at both call sites
  (configure :103, tester :157). ✔ (`framework_v2_migration.md` §15)
- **No SDK-constant path derivation** — describe resolution is left to the
  framework default. ✔
- **C2 single jar in lib/** — verified in the built pak (above). ✔

## Cardinal correctness (priorities 1/2) — unreadable-is-loud, proven from code

The crux of a first multi-resource port: when the per-cycle snapshot pull fails,
do the 24 keyed resources go stale-as-fresh / empty-as-readable / or honestly
fail? Traced end-to-end:

- **`this.snapshot` is assigned only AFTER `Snapshot.build` returns**
  (`currentSnapshot()` :334–342, assignment at :340). A failed build never
  overwrites the prior snapshot and never installs an empty one.
- **`SynologyApiClient.call()` throws on `!isSuccess()`** (:166–177, after one
  re-auth retry) and `callRaw` throws on non-200 (:183). So a DSM endpoint that
  returns `{success:false}` (the documented failure shape) → `IOException` →
  out of `Snapshot.build` → out of `currentSnapshot()` → out of `collect()`.
  The framework (`VcfCfAdapter.onCollect` :606–612) then calls
  `mapCollectException` → `RESOURCE_STATUS_DOWN` (ConnectException) or `ERROR`.
  Because `this.snapshot` is unchanged, the **next** resource's `collect`
  re-enters `currentSnapshot`, re-attempts the build, throws again — so **all 25
  resources are marked ERROR/DOWN, loudly, on a real API failure.** No silent
  empty result. This is the correct unreadable-is-loud behavior (skill
  § *Unreadable is NOT compliant*).
- **Staleness math is safe.** `MIN_REFRESH_INTERVAL_MS = 60_000` < the 5-min
  (300 s) collection interval, so every scheduled cycle rebuilds the snapshot;
  the 60 s guard only de-dups the ~25 `collect` calls **within** one cycle. No
  cross-cycle stale-data-as-fresh window.
- **Concurrency.** `onCollect` iterates resources single-threaded
  (`VcfCfAdapter.java:556`), so `collect()` is never called concurrently for one
  instance — the author's docstring claim is verified against the framework. The
  `synchronized currentSnapshot()` + `volatile snapshot` correctly guard the one
  cross-path read (World's `collectRelationships` re-entering `currentSnapshot`).
  `collectRelationships` returns non-null only for `SynologyWorld`, so the full
  topology emits exactly once per cycle — no double-emission. No concurrency
  defect.

## Parity surface (priority 5) — keys/identifiers identical, ONE stitch dropped

- **Metric/property keys: byte-identical.** Extracted all `metric(out,…)` /
  `prop(out,…)` keys (v2) and all v1 `addData`/`addProperty` keys: **103 keys
  each, zero added, zero dropped.** Matches the 136-metric baseline intent.
- **Identifier keys: identical** per kind (world_id, serial, pool_id, volume_id,
  disk_id, cache_id, lun_uuid, share_name, ups_model — one per kind, all
  `required=true`), and `describe.xml` is byte-unchanged v13→v14.
- **Resource kinds: identical** (9 data kinds + adapter instance), unchanged
  describe.
- **The "dropped Datastore relationship" claim is only PARTLY accurate** — see
  WARNING-1 below. The author's claim "v1 produced no landing data" is true for
  *foreign VMWARE resources* (baseline §3 confirms no Synology-namespaced data on
  any HostSystem/Datastore) but is **false for the Synology-owned LUN/NFS
  resources**: the v1 `stitchDatastores` path called `exportRes.addParent(new
  Resource(dsKey))`, which DID land as `relationships|Datastore_parent` on at
  least the wld01 iSCSI LUN (golden baseline §2.8, line 635:
  `relationships|Datastore_parent=vcf-lab-wld01-cl01-iscsi`). v14 drops this
  relationship. This is a (small, defensible) parity delta, not a clean "never
  landed."

## Findings

### WARNING

- **[SynologyAdapter.java buildRelationships :709–847 / commit message + design
  note]** — `rules/no-fabricated-metrics.md` gap-honesty adjacency / parity.
  The v1→v2 migration **drops the foreign Datastore parent relationship** that v1
  `stitchDatastores` emitted onto Synology iSCSI-LUN and NFS-Export resources.
  The author/commit/design-note justify this as "v1 produced no landing data
  (golden baseline §3)" — but §3 only certifies no data on *foreign* resources;
  the golden baseline §2.8 (line 635) shows `relationships|Datastore_parent`
  **did land** on the wld01 LUN in v1, and §2.9 notes vcf9/wld01 NFS exports
  referenced Datastores too. So this is a **deliberate behavior drop, not a
  no-op cleanup**, and it is documented under a slightly inaccurate premise. It
  does NOT produce a false-pass or silent corruption (the relationship is purely
  informational; dropping it loses a convenience cross-link, it does not
  mis-stitch anything — the MOID-trap risk is *avoided*, not triggered), so it
  does not gate. → Smallest correct fix: correct the claim to "v1 emitted a
  `Datastore_parent` cross-link on LUN/NFS resources via SuiteAPI
  `ForeignResourceResolver`; that path is intentionally dropped in v2 (no
  `SuiteApiStitcher`), losing the informational Datastore cross-link on iSCSI/NFS
  resources — accepted as out-of-scope for the migration parity bar," and (if the
  cross-link is wanted back) re-add it via the v2 `ForeignResourceResolver` +
  `RelationshipBuilder.parentForeign(...)` in a follow-up. The orchestrator
  should confirm with the user that losing the LUN/NFS→Datastore cross-link is
  acceptable before this ships, since the golden baseline lists it as present.

- **[SynologyApiClient.java callRaw :184 + login :49–63 + logout warn :71]** —
  `rules/no-secrets-on-disk.md`. The session id (`_sid`) and, on the login call,
  the **plaintext URL-encoded password** are embedded in the request `path`
  (`synoUrl` :192–194 appends `_sid`; login appends `account=`/`passwd=`). On a
  non-200 response `callRaw` throws `"HTTP " + statusCode + " from " + path` —
  i.e. an exception message containing `&_sid=…` (any call) or
  `&account=…&passwd=<URL-encoded-password>` (the login call). The framework logs
  that message to the on-disk adapter log (`VcfCfAdapter.onCollect` :609,
  `logWarn(... msg, e)`) and surfaces it on Test-connection. Additionally the
  client's own `logout()` WARN (:71) logs `e.getMessage()` from a `callRaw` whose
  path carries `_sid`. **This leak is byte-identical in v1** (same `callRaw`
  string, same login URL), so the migration does not *introduce* it — but v1
  routed the client's own log lines through `java.util.logging` (which, per the
  author's own §15 note, never reached the adapter log), whereas v14's
  `componentLogger` fix **newly lands the client's `_sid`-bearing logout WARN on
  disk.** Net: a pre-existing password-in-login-exception that the migration
  should not silently carry forward, plus a newly-activated `_sid`-on-disk path.
  Does not gate (no false-pass), but should be handed back. → Smallest correct
  fix: strip query secrets from the thrown message — `callRaw` should throw
  `"HTTP " + statusCode + " from " + redact(path)` where `redact` masks
  `_sid=…`, `passwd=…`, `account=…` (or build the URL message from `api`/`method`
  only, never the full `path`).

### NIT

- **[SynologyAdapter.java collectDiskstation :399–462]** — the diskstation
  singleton (unlike the keyed collectors) does not null-guard its snapshot slices:
  it directly dereferences `s.utilization.data().get("cpu").get("1min_load")
  .asDouble()` etc. Because `SimpleJson` is null-tolerant (`asDouble()`→`0.0`,
  `asString("")`→fallback on a missing key — verified in
  `SimpleJson.java:68–75`), a `{success:true,data:{}}` "success-shaped but empty"
  utilization payload would publish `cpu_load_1m=0.0`, `system_temp=0.0`, …
  **sentinel zeros on a GREEN instance** rather than failing loudly. This is the
  one residual empty-as-readable corner. It is **pre-existing v1 behavior** (same
  SimpleJson, same direct dereference) and depends on DSM violating its own
  `success:false`-on-error contract, so it is latent, not a migration regression
  — hence NIT, not WARNING. → Optional hardening: have `Snapshot.build` assert a
  required field on the critical endpoints (e.g. throw if
  `utilization.data().get("cpu").isNull()` or `dsmInfo.data().get("model")
  .isNull()`) so a hollow-but-200 payload surfaces as ERROR rather than a 0.0
  sentinel. The existing `if (diskCount == 0) logWarn(...)` guard
  (Snapshot.build :954) is the right instinct but only WARNs; it does not change
  status.

- **[CHANGELOG.md 1.0.0.14 / commit message]** — the "v1 produced no landing
  data" wording (also in the design note vision) is imprecise per WARNING-1;
  the `Datastore_parent` cross-link on LUN/NFS resources DID land in v1. Tidy the
  phrasing to "no data landed on foreign resources; the informational
  Datastore_parent cross-link on LUN/NFS resources is dropped." Documentation
  accuracy only.

## Build hygiene (priority 9)

`build_number` bumped 13→14 in `adapter.yaml`; matching `CHANGELOG.md` 1.0.0.14
entry present and accurate (modulo the NIT-2 wording). Minimal diff — the Java
change is a confined SPI reshape (no metric/key/identifier drift, proven above);
no drive-by refactor. The generalization (per-cycle snapshot replacing v1's
single-pull) is behavior-preserving on the 103 keys (byte-identical key set,
identical value derivations spot-checked across all 9 kinds).

## If shipped as-is

An operator installs the v2-rehomed adapter and gets the v1 collection surface
intact: same 25 resources, same 103 metric/property keys, same internal storage
tree, with the C2 single-jar pak (no bundled SDK/aria-ops). A real DSM API
failure now correctly marks every resource ERROR/DOWN (loud), not silently empty.
Two things an operator/author should know before promotion: (1) the
LUN/NFS→Datastore informational cross-link that existed in v1 (visible on the
wld01 LUN in the golden baseline) is **gone** — confirm that's intended; (2) a
failed login or non-200 response can write the DSM password / session id into the
adapter log and Test-connection error — a `no-secrets-on-disk` smell the
migration carried forward and (for `_sid`) newly activated on disk. Neither is a
silent false-pass; the live devel install + golden-collection parity proof
(25 resources / 136 metrics) remains the `qa-tester` / orchestrator acceptance
gate, and nothing in this static review blocks promotion to it.

## Verification artifacts

- `validate-sdk content/sdk-adapters/synology` → OK, 1 benign `-source 11` warning.
- `pak-compare` v14 vs v13: 0 BLOCKING / 0 WARNING / 4 INFO (direct run).
- `pak-compare` v14 vs compliance-48: 0 BLOCKING / 2 WARNING / 35 INFO (direct run).
- framework jar sha256 `5b570289bf48ec7e…` == `adapter_runtime/vcfcf-adapter-base.jar`.
- adapter jar: 5 classes, all `com.vcfcf.adapters.synology`, no `com/vmware/tvs`, no `.java`.
- C2 lib/: single `vcfcf-adapter-base.jar`; describe.xml byte-identical v13→v14.
- metric/property key sets: 103 == 103, zero drift; identifier keys identical per kind.
- No `build-sdk` run by this review; synology + factory trees left clean.

## Report
`context/reviews/synology-build-14.md`
