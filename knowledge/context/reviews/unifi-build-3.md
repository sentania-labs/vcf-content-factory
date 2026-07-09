# SDK Adapter Review — unifi build 3

- **Adapter:** `content/sdk-adapters/unifi`
- **Build reviewed:** 3 (commit `9e0ee81`, "feat(adapter): framework v2 migration
  (build 3)") — the **full v1→v2 framework migration** delta over the extraction
  commit `7ad709c` (v1-on-v2, the 71-error pre-migration state).
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 2 WARNING / 2 NIT
- **Date:** 2026-06-10
- **Authority baseline:** synology build-16 review
  (`knowledge/context/reviews/synology-build-16.md`, the multi-resource + stitching exemplar
  this port followed), v1 source (`7ad709c:src/.../UniFiAdapter.java`), golden
  baseline (`knowledge/context/investigations/unifi_v1_golden_baseline_devel.md` — NO
  configured instance on devel; acceptance is clean-install/clean-collect, no
  parity diff), framework source under `vcfops_managementpacks/adapter_framework/`,
  spec/19 §3 relationship contract, `knowledge/lessons/controller-describe-bare-instantiation.md`,
  `knowledge/lessons/foreign-resource-property-push.md`, `knowledge/rules/no-secrets-on-disk.md`,
  skill *Unreadable is NOT compliant* / *ARIA_OPS stitching identity*.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean; factory's 71 pre-existing errors GONE | **CONFIRMED by direct run.** `validate-sdk content/sdk-adapters/unifi` → "OK: … is a valid Tier 2 SDK adapter project." **4** source files compile (`UniFiAdapter`, `UniFiApiClient`, `UniFiConfig`, `UniFiStitcher`), only the benign `-source 11` system-modules warning. Zero errors — the v1-on-v2 `addProperty()`/`com.vmware.tvs.*` breaks are resolved. |
| `pak-compare` vs v1 unifi = 0/0, 3 INFO | **CONFIRMED exactly.** Built HEAD pak, compared against `dist/vcfcf_unifi_controller.1.0.0.2.pak` (the v1 golden-baseline version) → **0 BLOCKING / 0 WARNING / 3 INFO.** The 3 INFOs are benign C2-shape deltas: `overview.packed` present in factory; `lib/aria-ops-core-8.0.0.jar` and `lib/vrops-adapters-sdk-2.2.jar` dropped from lib/ (the whole point of the v2 re-home). |
| `pak-compare` vs synology-16 = 0/0, 30 INFO | **CONFIRMED exactly.** Compared against `dist/vcfcf_sdk_synology_diskstation.1.0.0.16.pak` → **0 BLOCKING / 0 WARNING / 30 INFO.** All 30 are expected adapter-identity differences between two distinct adapters sharing the C2 framework shape (display/name/description, per-adapter icons, jar names, `data kind count: 11 vs 9`). No structural divergence. |
| C2 single-jar pak shape | **CONFIRMED.** `adapters.zip`: `unifi_controller/lib/` = exactly one `vcfcf-adapter-base.jar`; adapter jar at root; all 7 classes `com.vcfcf.adapters.unifi.*` (incl. `UniFiAdapter$Snapshot`, `UniFiStitcher$SuiteApiHostBridge`); **no `com.vmware.tvs`, no `.java` source, no aria-ops-core.** Build log confirms "aria-ops-core NOT required … omitting." |
| `build_number` bump + CHANGELOG | **CONFIRMED.** `adapter.yaml` `build_number: 3`; CHANGELOG `1.0.0.3 (2026-06-10)` entry present, accurate, thorough (4 bullets covering the re-home, snapshot idiom, cross-link rewire, unreadable-is-loud + redaction). `describe.xml` **not in the build-3 diff** — byte-unchanged, as the brief stated. |

`build-sdk` was run once for the pak-compare; **CHANGELOG.md / REFERENCE.md
restored** (`git checkout --`), all `/tmp` artifacts removed. **unifi tree clean
(`git status --short` empty, HEAD `9e0ee81`); factory tree clean** (`dist/` is
gitignored).

---

## Priority 1 — lesson compliance (automatic-respin items): all clean

- **Keyed constructors** — `super(ADAPTER_KIND)` and
  `super(ADAPTER_KIND, adapterDir, adapterInstanceId)` (`UniFiAdapter.java:96-102`).
  No `getAdapterKind()`-at-construction trap. ✔
- **No `onDescribe` override** — only an explanatory comment block
  (`:104-109`) citing `knowledge/lessons/controller-describe-bare-instantiation.md`; no
  method. Framework default resolves describe.xml from the stored kind. ✔
- **`componentLogger` only; no shadow logger** — every helper logger is
  `componentLogger(X.class)` (`:122,135,137,169,211`). No `private … Logger`
  field on the adapter (it uses inherited `logInfo`/`logWarn`). `java.util.logging`
  appears only inside a "never use" doc comment in `UniFiApiClient`. ✔
- **No SDK-constant paths** — endpoints are literal UniFi REST paths in
  `UniFiApiClient`; no `com.vmware.tvs.*` constant references. ✔
- **C2 single-jar pak** — verified above. ✔
- **Self-contained tester** — `getTester()` (`:198-224`) builds a throwaway
  `UniFiConfig`/`ManagedHttpClient` from the `TestParam`'s `ResourceConfig`
  (via `testResourceConfig`), never touching `this.api`/`this.config` (both null
  on a bare controller-side Test instance), and discards the test client in a
  `finally`. Throws a descriptive error when no `ResourceConfig` is present. ✔

## Priority 2 — snapshot idiom (§18): correct, failed-refresh is loud

**Thread-safety.** `snapshot` is `volatile`; `currentSnapshot()` is
`synchronized` (`:389`) so the null/staleness check-then-refresh is atomic and
only one thread performs the API pull per cycle. The published `Snapshot` is
effectively immutable after `build()` returns (all maps populated before
publication). ✔

**Critical-endpoint assert — both failure shapes surface ERROR for all
dependents.** `Snapshot.build` (`:1103`) calls `api.listSites()`; the
`UniFiApiClient.get` non-200 path **throws `IOException`** (`UniFiApiClient.java:65`),
and a **hollow-but-200** `/self/sites` (no readable `data` list) throws
`IOException` at `:1114`. Both propagate out of `currentSnapshot()` → out of
**every** `collect(rc)` (each calls `currentSnapshot()` first, `:352`) → the
framework marks every dependent resource ERROR/DOWN. There is no path where an
unreadable site list becomes a silent empty snapshot or a `0.0` sentinel — the
SimpleJson null-tolerance trap (`asDouble()→0.0`) is explicitly closed by the
assert. This is the skill *Unreadable is NOT compliant* contract, met. ✔

**Protect-optional cannot mask a real Protect failure as a false pass.** Protect
is fetched in a try/catch (`:1144-1158`); a failure (no NVR, transient 500,
timeout) logs **INFO** and leaves `protect == null`. Crucially this never
fabricates data: when `protect == null`, the NVR/camera resources are simply not
discovered (`:308`) and, if previously discovered, `collectNvr` finds
`s.protect == null` and logs **WARN** then returns **with no metrics**
(`:765-767`) — no sentinel, no `0.0`. So a genuine Protect outage degrades to
"no data on the Protect sub-tree" (honest), not "Protect healthy." This matches
v1 exactly (v1 `logInfo("Protect not available")`, optional sub-tree). The one
honesty nuance — INFO at the snapshot level vs WARN at the resource level — is
acceptable: an already-discovered NVR whose Protect fails gets a WARN, which is
the right level to distinguish "couldn't read" from "absent." ✔ (see WARNING-2
for the `stat/health` analogue, which is a *behavior change* from v1, not a
false-pass.)

**Staleness window.** `MIN_REFRESH_INTERVAL_MS = 60_000` — a snapshot is reused
for ≤60s across the per-resource collects of one cycle, then rebuilt. Bounded,
no unbounded staleness; `onDiscard` nulls it. ✔

## Priority 3 — LLDP stitching (UniFiStitcher): MOID-trap satisfied, v1-faithful

- **Resolves by `VMEntityName`, never bare MOID.** `matchHostByName`
  (`UniFiStitcher.java:56`) → `resolver.findByIdentifier("VMWARE","HostSystem",
  "VMEntityName", systemName)`. `ForeignResourceResolver.findByIdentifier`
  (`ForeignResourceResolver.java:163`) indexes by **identifier value**
  (`index.get(identifierValue)`), never by MOID. Byte-identical to v1
  (`7ad709c:UniFiAdapter.java:916-918`). Satisfies skill *ARIA_OPS stitching
  identity* / `knowledge/lessons/foreign-resource-property-push.md`. ✔
- **sysName normalization — none, and v2 preserves that.** v1 passed `sysName`
  to `findByIdentifier` **raw** (no `toLowerCase`/`toUpperCase`/FQDN-vs-short
  transform; only a `sysName.isEmpty()` skip). v2 passes `systemName` straight
  through, with the empty/null skip folded into `matchHostByName` (returns null on
  empty). **No transform existed in v1, so there is nothing to preserve and
  nothing newly introduced** — exact behavioral parity. ✔ (Consequence: if a real
  LLDP `lldp_system_name` is a short name and the VMWARE `VMEntityName` is an FQDN
  — or vice-versa — neither v1 nor v2 matches; that is a same-as-v1 miss that
  *drops* the edge, never a mis-stitch.)
- **Edge direction matches v1 (not inverted).** v1: `portRes.addParent(hostRes)`
  — host is the **parent** of the port. v2: `rb.parentForeign(host, portKey)`,
  and `RelationshipBuilder.parentForeign(foreignParent, child)` registers
  `host` as parent with `portKey` in its child set (`RelationshipBuilder.java:164`).
  Same direction. ✔
- **WARN-and-skip degradation traced.** Three paths: (a) Suite API unavailable →
  `configureAdapter` catch (`:138-144`) nulls the stitcher, emits **one** WARN;
  `emitLldpHostCrossLink` early-returns on `st == null` (`:964`), no second WARN,
  all UniFi resources still collect. (b) Suite API reachable but the
  `/api/resources` query throws → `ForeignResourceResolver.fetchAndCache`
  (`:258`) catches **all** exceptions, WARNs, returns an empty index → zero
  matches, no edge — never throws. (c) Belt-and-braces: the whole
  `emitLldpHostCrossLink` body is `try/catch (Exception)` (`:992`) so a cross-link
  fault is WARNed and the **already-built internal topology is still returned**
  (`return rb.build()` runs after `emitLldpHostCrossLink`). ✔
- **VMEntityName collisions.** A non-matching sysName drops the edge (no edge),
  it never redirects onto the wrong host. Two real HostSystems sharing a
  `VMEntityName` would be a platform identity violation (last-wins in the index,
  same as synology-16's path-identity map). No NEW ambiguity over v1. ✔
- **Discard lifecycle.** `onDiscard` (`:1069`) calls `suiteStitcher.discard()`,
  nulls `suiteStitcher`/`stitcher`/`snapshot`, then `super.onDiscard()` — the
  compliance/synology pattern. ✔

## Priority 4 — secrets: redaction complete, no API-key half-wiring

Every throw/log site in `UniFiApiClient` audited:
- **`get` non-200 throw** (`:66`) — `"UniFi GET " + redact(path) + " returned
  HTTP " + code`. Paths carry no secret query string, but `redact()` is applied
  regardless; no response body echoed. ✔
- **`login` non-200 throw** (`:82`) — `"UniFi login failed: HTTP " + code` —
  **status code only**, the plaintext-password request body is never echoed.
  Exactly the brief's requirement. ✔
- **`login` no-cookie throw** (`:88`) and **session-acquired INFO** (`:90`) —
  static strings, no token value. ✔
- **`redact()`** (`:114`) masks `TOKEN=`, `unifises=` (cookie values, terminated
  on `;&\s`), and both `"password":"…"` (JSON body) and `password=` (query) forms,
  case-insensitive. Covers the session-cookie and login-password classes the
  brief named. ✔ The body-form `"password"` branch is currently defensive (no
  live call feeds the login body to a log — login throws status-only), which is
  the safe direction.
- **Transport exceptions** (`IOException`/`InterruptedException` from
  `http.get`/`http.post`) propagate uncaught to the framework. The password lives
  only in the POST **body** (never the URL); the TOKEN cookie is managed inside
  `SessionCookieAuth`/`ManagedHttpClient`, not in any `UniFiApiClient` string — so
  a transport exception message (host/port, "connection refused") carries no
  credential. ✔ (I cannot statically prove the framework's HttpClient never logs
  a request body on transport failure, but no adapter-authored path does — see
  NIT-2.)
- **`UNIFI_API_KEY` half-wiring** — a repo-wide grep (`*.java/*.xml/*.yaml/
  *.properties`) returns **zero** matches for `api_key`/`apikey`/`UNIFI_API_KEY`.
  Nothing half-wired; v1 had no API-key path either. ✔

## Priority 5 — JSON extraction vs UniFi response nesting: consistent, v1-faithful

UniFi Network (classic) endpoints wrap payloads in `{meta, data[]}`; the walkers
consistently unwrap via `.get("data").asList()` for sites (`:249,847,1113`),
per-site devices (`:255,857`), and health (`:751`). Protect `bootstrap` is a
**flat** object (`nvr`, `cameras` at the root, no `{meta,data}` wrapper) and the
code reads `protect.get("nvr")` / `protect.get("cameras")` directly (`:309,
769,919`) — correct, and byte-identical to v1 (`7ad709c:184-185`). The
deep-vs-direct distinction is respected per endpoint family. Spot-checked the
site/device/port walkers against v1's field reads (`system-stats` string-coerce,
`port_table`/`radio_table_stats` iteration, `wan1`/`wan2`, temperatures) — same
fields, same coercions. ✔

## Priority 6 — gates: all re-run, all confirmed

See the claims-check table. `validate-sdk` clean (71 errors gone); pak-compare
**0/0 + 3 INFO vs v1**, **0/0 + 30 INFO vs synology-16** — both exactly as the
author claimed.

---

## Findings

### WARNING

- **[UniFiAdapter.java emitLldpHostCrossLink :986 `rb.parentForeign(host,
  portKey)` → `RelationshipBuilder.build`/`doBuild` :292 → spec/19 §3]** —
  *Full-set `setRelationships` onto a **foreign** VMWARE HostSystem — devel-
  provable, not static-provable.* `build()` emits
  `setRelationships(host, {switchPort})` for the foreign HostSystem parent, which
  spec/19 §3 documents as a **FULL replacement of that parent's child set
  (platform diffs against current state).** This is a **semantic change from v1**:
  v1 used the old aria-ops-core `portRes.addParent(hostRes)` (child-declares-parent,
  **additive**); v2 uses the SDK-native full-set-on-parent form against a
  **VMWARE-owned** HostSystem. This is the *identical* residual risk that
  synology build-16 WARNING-1 carried and was APPROVEd with — I **cannot prove
  from the code alone** that the platform scopes the HostSystem's child set
  per-reporting-adapter rather than letting unifi's `setRelationships(host,
  {switchPort})` clobber the host's VMWARE-collected VM/datastore children. It
  does **not** gate: the edge direction matches v1, the design is
  orchestrator-approved, the idiom is the APPROVEd synology-16 idiom, and it lands
  on an *informational* cross-link (a mis-scope drops/replaces an edge, it never
  redirects onto a wrong host or fabricates a pass). → **Smallest fix / hand-off:**
  make the live devel proof an explicit acceptance criterion — after a build-3
  collect against a controller with an LLDP-reachable ESXi host, confirm the
  matched HostSystem retains **both** its pre-existing VMWARE child set **and**
  the new UniFiSwitchPort child. If VMWARE children are clobbered, switch the
  foreign-parent emission to a labeled/generic edge
  (`rb.generic(host, {port}, label, namespace)` → `setGenericRelationships`)
  rather than full-set `setRelationships`. Static review cannot close this; the
  devel collect must. **Note:** the unifi golden baseline records *no configured
  instance and no LLDP stitching ever exercised on devel*, so this path is
  entirely unproven in practice — the devel collect is the first real exercise.

- **[UniFiAdapter.java Snapshot.build :1135-1140 `stat/health` try/catch vs v1]**
  — *`stat/health` failure is downgraded from v1's loud propagation to WARN-and-
  empty.* In v1, `collectWirelessAggregate` called `api.statHealth(siteName)`
  **directly** (`7ad709c:615`); a non-200/transport failure there would throw and
  surface. In v2 the health pull is wrapped per-site in a try/catch that WARNs and
  omits the site from `healthBySite`; `collectWirelessAggregate` then finds
  `health == null`, WARNs, and emits **no metrics** (`:745-750`). This is a real
  behavior change (quieter than v1) but is **not** a false-pass: the
  WirelessAggregate resource publishes no `0.0` sentinel and no fabricated value —
  it simply has no data that cycle, which the platform surfaces as missing/stale.
  It does not gate (no sentinel, no wrong data; WARN-logged with site context).
  → **Fix / hand-off:** confirm this is the intended degradation (a transient
  `stat/health` blip should not ERROR the whole cycle — reasonable). If parity
  with v1's louder behavior is wanted, let the `stat/health` failure propagate
  (drop the try/catch) so the cycle goes ERROR rather than silently dropping the
  wireless summary. Recommend deciding at the devel-collect gate.

### NIT

- **[UniFiApiClient.redact :119]** — the `"password":"…"` replacement keeps `$1`
  (the opening `"password":"`) and substitutes `<redacted>` but does **not**
  re-emit the closing `"`, so a redacted body reads `"password":"<redacted>` (no
  trailing quote). Cosmetic only — the secret **is** masked; the message is just
  slightly malformed JSON. No live call feeds the login body to a log today
  anyway. Documentation/tidiness only.

- **[UniFiApiClient transport-exception logging — framework boundary]** — a
  transport `IOException` from `ManagedHttpClient.post("/api/auth/login", body…)`
  propagates with the framework potentially logging the call. No adapter-authored
  string leaks the password (it lives only in the body, and the adapter never logs
  the body), but a future framework change that logged request bodies on transport
  failure would bypass `redact()`. Worth a one-line note in REFERENCE.md that the
  password-body redaction depends on the framework not echoing POST bodies. Not a
  current defect.

## Build hygiene (priority 9) — clean

`build_number` 2→3 in `adapter.yaml`; CHANGELOG `1.0.0.3` entry present, accurate,
thorough. `describe.xml` byte-unchanged (not in the build-3 diff — confirmed via
`git diff 7ad709c 9e0ee81 --stat`), so all resource kinds / identifiers / metric
keys / 11 data kinds are preserved exactly; pak-compare vs v1 shows zero
structural divergence beyond the intended C2 lib/ shape. The migration is a
genuine re-home, not a drive-by refactor: the per-kind collector value semantics,
display-name helpers, string-coercions, and Protect heuristics are transcribed
faithfully from v1 (spot-checked against `7ad709c`). The one generalization (whole-
topology pass → per-resource snapshot dispatch) is proven behavior-preserving by
the unchanged describe.xml + the 0/0 pak-compare and traced field-by-field above.

## If shipped as-is

An operator installs build 3 and gets a clean v2 UniFi adapter: it installs as a
C2 single-jar pak (no aria-ops-core / vrops-adapters-sdk in lib/), creates an
instance, discovers the full sites→gateways/switches/APs/ports/radios/NVR/cameras
tree, and collects per-resource metrics with v1-identical values. An unreadable
`/self/sites` (non-200 or hollow 200) loudly ERRORs every resource — never a
`0.0` sentinel. Session cookies and the login password cannot reach the adapter
log. On a collector with the ambient Suite API, each switch port whose LLDP
neighbour names a real ESXi host gains v1's informational `HostSystem → port`
cross-link (resolved by `VMEntityName`, never MOID); on a remote collector that
cross-link is skipped with one WARN and everything else collects. **The single
thing the live devel collect must still confirm** (WARNING-1): that the full-set
`setRelationships` onto the foreign HostSystem is additive in the platform's view
and does not replace the host's VMWARE-collected VM/datastore children — a
question static review cannot close, and one this adapter has never exercised on
devel (no configured instance in the golden baseline). Nothing in this review
blocks promotion to that devel / `qa-tester` gate.

## Verification artifacts

- `validate-sdk content/sdk-adapters/unifi` → OK, 4 sources compiled, 1 benign
  `-source 11` warning (direct run). 71 pre-existing v1-on-v2 errors gone.
- `pak-compare` build-3 vs `vcfcf_unifi_controller.1.0.0.2` (v1) → **0 BLOCKING /
  0 WARNING / 3 INFO** (overview.packed + 2 dropped lib jars).
- `pak-compare` build-3 vs `vcfcf_sdk_synology_diskstation.1.0.0.16` → **0
  BLOCKING / 0 WARNING / 30 INFO** (adapter-identity differences only).
- Pak C2 shape: single `vcfcf-adapter-base.jar` in lib/; adapter jar carries 7
  `com.vcfcf.adapters.unifi.*` classes; no `com.vmware.tvs`, no `.java`, no
  aria-ops-core. `describe.xml` byte-unchanged from v1.
- `parentForeign(host, portKey)` → host=parent (RelationshipBuilder.java:164),
  matching v1 `portRes.addParent(hostRes)`. `findByIdentifier` matches by
  VMEntityName value, never MOID (ForeignResourceResolver.java:163-174).
- v1 sysName passed raw (no normalization) — `7ad709c:911-918`; v2 preserves.
- `UNIFI_API_KEY`/`api_key` — zero matches repo-wide.
- `build-sdk` run for the comparison; CHANGELOG.md/REFERENCE.md restored, `/tmp`
  cleaned — **unifi + factory trees left clean** (`git status --short` empty,
  HEAD `9e0ee81`).

## Report
`knowledge/context/reviews/unifi-build-3.md`
