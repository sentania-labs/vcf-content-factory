# Defect registry

The declared registry of **known defects that must converge**. A review
verdict records findings; this file is where a finding that survives
acceptance stops being prose and becomes something a release mechanically
refuses over. Design of record: `designs/defect-registry-v1.md`. Gate
rule: `rules/release-gate-defects.md` (RULE-012).

## How it works

- **Graduation.** Any review finding of **WARNING or worse** that
  survives build acceptance unfixed MUST be registered here before the
  next build of that artifact is briefed. NITs do not enter the
  registry — they live in the review docs.
- **The gate consumes this file.** `python3 -m vcfops_packaging
  defect-gate` parses the entries; `release` and `publish` refuse, and a
  v* tag must not be pushed, while an **open blocking** defect affects
  the artifact (RULE-012). Refusals name defect ids.
- **The reviewer re-asserts.** `sdk-adapter-reviewer` reads this file
  every review and re-asserts each open defect affecting the pak under
  review; if a build resolves one, the verdict *proposes* closure with
  evidence. The reviewer never edits this file.
- **Only the orchestrator (or the user) writes here.** Agents propose;
  this file changes only via the orchestrator, in a diff.

## Schema

One `### DEF-NNN` section per entry. Ids are sequential and never
reused. Field lines are `- **Field:** value` (parsed by
`vcfops_packaging` — keep the shape exact, same convention as
`context/managed_paks.md`).

| Field | Values / meaning |
|---|---|
| `Title` | One line; refusal messages quote it. |
| `Severity` | `blocking` (gates releases of affected artifacts) or `tracked` (must converge, re-asserted every review, but ships). |
| `Status` | `open` or `closed`. **No `waived`.** A conscious decision to ship is a severity downgrade with a dated note — the diff is the audit trail. |
| `Affects` | Exactly one artifact scope per entry: a managed pak name from `context/managed_paks.md` (e.g. `synology`), a content item as `<type>/<slug>` (e.g. `dashboard/demand_driven_capacity_v2`), or `factory:<area>` for framework code. One issue on N artifacts = N entries, cross-linked via `Related:`. |
| `First-seen` | Build (or commit) + date where the defect first appeared. |
| `Source` | The review / lesson / investigation that found it, by path (+ finding label). |
| `Summary` | 2–4 lines: what it is, why it matters, smallest correct fix. Enough for a reviewer to re-assert without re-reading the source. |
| `Closing-evidence` | **Required when `Status: closed`** — concrete proof (fix commit/build, devel proof, lesson), not assertion. Omitted while open. A close without evidence is invalid. |
| `Related` | Optional cross-links to sibling entries / lessons. |

## Defects

### DEF-001

- **Title:** Synology: plaintext password and `_sid` reachable from the on-disk adapter log via exception paths
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 14 (2026-06-10)
- **Source:** `context/reviews/synology-build-14.md` (WARNING-2)
- **Closing-evidence:** synology build 19 (`1.0.0.19`), 2026-06-26.
  `SynologyApiClient.callRaw` now wraps `http.get(path,…)` in try/catch and
  rethrows a **standalone** `IOException` built from the `endpoint` label +
  `redact(e.getMessage())` — no chained cause (so `getCause().getMessage()`
  cannot resurface the URI), and `redact()` strips `_sid`/`account`/`passwd`.
  The HTTP-status throw and the `_sid`-bearing logout WARN were redacted in
  build 18; the login/collect **transport-exception** path (connect/SSL/timeout
  — the plaintext-password carrier) was the last gap, now closed. Full-adapter
  grep confirms no throw / log / Test-connection path emits a raw path or
  secret. Statically provable (no live trigger owed). Certified by
  `sdk-adapter-reviewer`: `context/reviews/synology-build-19.md` (APPROVE,
  0 BLOCKING). Rule: `rules/no-secrets-on-disk.md`.
- **Summary:** `SynologyApiClient.callRaw` throws `"HTTP <code> from <path>"`
  where the path carries `_sid=` on every call and `account=` /
  `passwd=<URL-encoded plaintext password>` on the login call; the
  framework logs exception messages to the on-disk adapter log and
  surfaces them on Test-connection, and v14's `componentLogger` swap
  newly lands the `_sid`-bearing logout WARN on disk
  (`rules/no-secrets-on-disk.md`). Smallest correct fix: redact
  `_sid` / `account` / `passwd` from every thrown message — build the
  message from `api`/`method`, never the full path. Hand-back issued at
  build 14; not yet executed.

### DEF-002

- **Title:** UniFi: full-set `setRelationships` onto foreign VMWARE HostSystem unproven on devel (LLDP stitch never exercised)
- **Severity:** blocking
- **Status:** open
- **Affects:** unifi
- **First-seen:** build 3 (2026-06-10)
- **Source:** `context/reviews/unifi-build-3.md` (WARNING-1)
- **Summary:** `emitLldpHostCrossLink` emits full-set
  `setRelationships(host, {switchPort})` onto a VMWARE-owned
  HostSystem — a semantic change from v1's additive `addParent`. The
  per-reporting-adapter scoping that makes this safe is proven on devel
  9.0.2 only via synology (see DEF-003); unifi's LLDP path has **never
  once run on a live instance** (golden baseline: no configured devel
  instance), and 9.1 is unverified. Closes when a unifi devel collect
  against an LLDP-reachable ESXi host shows the matched HostSystem
  retains its pre-existing VMWARE children AND gains the UniFiSwitchPort
  child. If children are clobbered, switch to a labeled generic edge
  (`setGenericRelationships`).
- **Related:** DEF-003, `lessons/setrelationships-foreign-adapter-scoped.md`

### DEF-003

- **Title:** Synology: full-set `setRelationships` onto foreign VMWARE Datastore — clobber risk
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 16 (2026-06-10)
- **Source:** `context/reviews/synology-build-16.md` (WARNING-1)
- **Summary:** Same idiom as DEF-002: full-set `setRelationships` emitted
  by the synology adapter onto a foreign VMWARE-owned Datastore, with
  the same static-unprovable clobber risk against the owning adapter's
  child edges.
- **Closing-evidence:** Devel 9.0.2 proof, synology build 16,
  2026-06-10: wld01 iSCSI Datastore retained its 22 VMWARE children and
  gained the LUN child — the platform scopes `setRelationships`
  per-reporting-adapter. Codified in
  `lessons/setrelationships-foreign-adapter-scoped.md`. Residual: 9.1
  unverified (re-open or re-prove at the first 9.1 target).
- **Related:** DEF-002

### DEF-004

- **Title:** vcommunity-os: in-guest collection (services / event logs / CSV OS-info) returns empty — primary surface non-functional on devel
- **Severity:** blocking
- **Status:** open
- **Affects:** vcommunity-os
- **First-seen:** build 11 / split fork (2026-06-23)
- **Source:** `context/investigations/vcommunity-windows-services-empty-2026-06-23.md`
- **Summary:** The guest-ops half of the vCommunity split — services,
  in-guest CSV OS-info, and event logs collected via vCenter
  GuestOperationsManager — returns empty on the hardened devel DCs, so
  the pak's primary surface does not function. Privilege/logon was
  ELIMINATED as the cause (domain-admin swap changed nothing); leading
  theory is in-guest PowerShell execution-policy / ConstrainedLanguage on
  the hardened hosts. The pak is intentionally parked (installed,
  uninstanced) pending diagnosis. Gates any `v*` release of
  `vcommunity-os` (RULE-012): the pak must not ship while its core
  collection is non-functional. Closes when a devel collect against a
  representative Windows guest returns non-empty service/event/OS-info
  data and the root cause is codified.
- **Related:** `designs/managementpacks/vcommunity-three-adapter-split.md`,
  vcommunity-os pak README

### DEF-005

- **Title:** Framework stitcher: strict-TOFU loopback Suite API transport
  PKIX-fails every cycle — cross-MP stitch reads zero datastores
- **Severity:** blocking
- **Status:** closed
- **Closing-evidence:** build 24 (BC-mirror transport), 2026-07-02.
  Devel (9.0.2 analytics): 7+ consecutive clean cycles, `loadDatastores`
  "loaded 10 VMWARE Datastores", zero PKIX (00:18–00:49Z log capture).
  Prod (9.1 primary): identity line `mechanism=ambient
  principal=automationAdmin`, 10 datastores loaded, 5 foreign
  Datastore edges live via API, no clobber; pre-install baseline on
  the same box failed every cycle with `certificate_unknown(46)`.
  Reviews: `context/reviews/framework/bc-mirror-transport-v1.md`/`-v2.md`.
  Residual (FIPS cluster-truststore parity) documented as TODO in
  `VcfCfAdapter.openPlatformConnection()`. The remaining CP-resident
  gap is a distinct defect → DEF-006.
- **Affects:** synology
- **First-seen:** build 23 devel install (2026-07-01) — latent in every
  build ≥ 20 (first live install since the transport rework; builds
  20–22 were local-only)
- **Source:** `context/investigations/synology-b23-devel-pkix-2026-07-01.md`
- **Summary:** The TLS/TOFU transport rework (PRs #29/#30) routed the
  loopback Suite API call through the platform's strict
  `CustomTrustManager`, assuming the platform's non-disruptive
  certificate handler would persist unknown certs (TOFU). Live devel
  disproves it: the handler fails every cycle ("Adapter certificate
  renewal url set is empty") because framework adapters declare no
  cert-renewal URL set, so trust never persists and `loadDatastores`
  PKIX-fails forever. Build 19 worked only because it trusted the
  loopback connection outright. Vendor ground truth
  (`context/api-surface/casa-injected-vs-raw-client.md` §3): the
  aria-ops-core `SuiteAPIClient` used by every shipping Broadcom pak
  sets `verify("false")` + `ignoreHostName(true)` non-FIPS, cluster
  truststore under FIPS — none use the strict path. Fix: mirror the BC
  behavior exactly, no invention. The same framework transport ships in
  every Tier 2 pak built from current main (unifi, compliance,
  vcommunity*) — verify per pak as each rebuilds. Closes when a devel
  collect under the fixed transport loads datastores and writes the
  stitch.
- **Related:** `designs/suite-api-stitcher-tls-auth-cleanup-v1.md`
  (premise contradicted by live evidence),
  `lessons/suite-api-stitch-ssl-tofu-vs-java-http.md` (vindicated),
  DEF-006 (successor: CP-resident gap)

### DEF-006

- **Title:** CP-resident cross-MP stitch: no credentialed ambient path
  works from a Cloud Proxy — automationAdmin 401s at token acquire
- **Severity:** blocking
- **Status:** closed
- **Closing-evidence:** build 26 (ambient identity v3 — platform-injected
  per-instance credential first), 2026-07-02. Prod: the synology
  instance on the NEW Cloud Proxy (collector 3, `collector01`,
  rebuilt after the original CP crashed) wrote **6** Synology→VMWARE
  Datastore edges from a provably virgin baseline (fresh proxy +
  never-collected instance; 0 edges pre-recovery → 6 post: 2 iSCSI
  LUN + 4 NFS incl. the never-before-stitched `relationship`
  datastore), no clobber (every datastore's VMWARE relationship
  counts unchanged, each +1 synology), sustained 5-min cadence.
  Devel: direct log quote of the identity flip —
  `credential mechanism=ambient file=instance
  principal=816c72ef-84b2-4caf-848c-4b09a6517648` followed by
  `loaded 11 VMWARE Datastores`. Contract:
  `context/api-surface/per-instance-suiteapi-credential-contract.md`;
  live mechanism discovery:
  `context/investigations/oracle-stitch-autopsy-2026-07-02.md`;
  reviews: `context/reviews/framework/ambient-credential-v3-*.md`.
  **Residual (evidentiary, not functional):** the CP-side
  `file=instance` log line is unquoted — the new proxy refuses SSH;
  enable SSH on collector01 + one cycle to capture it. The
  title's premise ("no credentialed ambient path works") was
  corrected by the autopsy: the platform-injected per-instance
  credential IS the working ambient path; our framework simply never
  read it before v3.
- **Affects:** synology
- **First-seen:** build 24 on prod CP (2026-07-02), after the user moved
  the adapter instance to collector 2
- **Source:** prod CP adapter log 2026-07-02 03:03Z: `Suite API POST
  https://localhost/suite-api/api/auth/token/acquire returned 401 —
  token expired or credential invalid mechanism=ambient
  principal=automationAdmin`
- **Summary:** With DEF-005's transport fixed (zero PKIX) and the
  identity fix selecting `automationAdmin` correctly, the CP's local
  `automationuser.properties` secret does not authenticate against the
  cluster (401 at token acquire; the maintenance fallback's
  `cloudproxy_<uuid>` authenticates but 403s on reads — both live-
  proven). No credentialed ambient path works from a CP. This gap is
  industry-wide: aria-ops-core's ambient path reads the maintenance
  file (bytecode) and would 403 identically; no shipping third-party
  pak solves it. The failure mode is loud (WARN per cycle) and
  harmless (additive verb — zero edges pushed, nothing cleared; own-
  adapter collection unaffected). The prod CP instance is deliberately
  left in this state as the standing live repro. Candidate fixes under
  investigation: (a) descriptor-declared traversal + reported
  `relationships|Datastore_parent` property (the mechanism Oracle
  provably uses from this same CP with zero API calls — see
  `context/api-maps/tvs-declarative-stitching.md`; binding-value scan
  in flight), (b) CaSA node-certificate door (cleanroom build-spec
  pending). Closes when a collect executed ON the CP results in the
  Synology→VMWARE Datastore edge existing, via either mechanism.
- **Related:** DEF-005, `context/api-maps/tvs-declarative-stitching.md`,
  `context/api-maps/tvs-cross-mp-stitching.md`,
  `context/investigations/cp-auth-door-probe-2026-07-01.md`
