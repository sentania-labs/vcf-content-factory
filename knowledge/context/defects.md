# Defect registry

The declared registry of **known defects that must converge**. A review
verdict records findings; this file is where a finding that survives
acceptance stops being prose and becomes something a release mechanically
refuses over. Design of record: `knowledge/designs/defect-registry-v1.md`. Gate
rule: `knowledge/rules/release-gate-defects.md` (RULE-012).

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
`knowledge/context/managed_paks.md`).

| Field | Values / meaning |
|---|---|
| `Title` | One line; refusal messages quote it. |
| `Severity` | `blocking` (gates releases of affected artifacts) or `tracked` (must converge, re-asserted every review, but ships). |
| `Status` | `open` or `closed`. **No `waived`.** A conscious decision to ship is a severity downgrade with a dated note — the diff is the audit trail. |
| `Affects` | Exactly one artifact scope per entry: a managed pak name from `knowledge/context/managed_paks.md` (e.g. `synology`), a content item as `<type>/<slug>` (e.g. `dashboard/demand_driven_capacity_v2`), or `factory:<area>` for framework code. One issue on N artifacts = N entries, cross-linked via `Related:`. |
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
- **Source:** `knowledge/context/reviews/synology-build-14.md` (WARNING-2)
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
  `sdk-adapter-reviewer`: `knowledge/context/reviews/synology-build-19.md` (APPROVE,
  0 BLOCKING). Rule: `knowledge/rules/no-secrets-on-disk.md`.
- **Summary:** `SynologyApiClient.callRaw` throws `"HTTP <code> from <path>"`
  where the path carries `_sid=` on every call and `account=` /
  `passwd=<URL-encoded plaintext password>` on the login call; the
  framework logs exception messages to the on-disk adapter log and
  surfaces them on Test-connection, and v14's `componentLogger` swap
  newly lands the `_sid`-bearing logout WARN on disk
  (`knowledge/rules/no-secrets-on-disk.md`). Smallest correct fix: redact
  `_sid` / `account` / `passwd` from every thrown message — build the
  message from `api`/`method`, never the full path. Hand-back issued at
  build 14; not yet executed.

### DEF-002

- **Title:** UniFi: full-set `setRelationships` onto foreign VMWARE HostSystem unproven on devel (LLDP stitch never exercised)
- **Severity:** blocking
- **Status:** closed
- **Affects:** unifi
- **First-seen:** build 3 (2026-06-10)
- **Source:** `knowledge/context/reviews/unifi-build-3.md` (WARNING-1)
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
- **Closing-evidence:** Devel proof, unifi build 9 (`0.0.0.9`, commit
  `3bb262a`), 2026-07-06. First build whose stitch ever matched a host
  (builds ≤8 matched zero: the controller-side per-port `lldp_table`
  does not exist on Network App 10.2.105 — see
  `knowledge/context/investigations/unifi-lldp-switchport-esxi-2026-07-05.md`;
  build 9 inverted the join to vCenter-side
  `net:vmnic*|discoveryProtocol|lldp` properties per
  `knowledge/designs/managementpacks/unifi-switchport-host-stitch-v2.md`). Post-
  install collect: all 8 VMWARE HostSystems gained UniFiSwitchPort
  children (15 vmnic edges) via additive `parentForeign` →
  `addRelationships`, and every host retained its pre-existing VMWARE
  children — Datastore/StoragePool counts exact vs. baseline; mgmt-host
  VM children total 30 before and after (15+4+2+9 → 12+4+4+10, DRS
  drift between hosts, not loss). Write verb had already moved from
  full-set to additive in build 8 (`knowledge/context/reviews/unifi-build-8.md`);
  build 9 supplied the live exercise. Residual: 9.1 unverified (same as
  DEF-003).
- **Related:** DEF-003, `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`

### DEF-003

- **Title:** Synology: full-set `setRelationships` onto foreign VMWARE Datastore — clobber risk
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 16 (2026-06-10)
- **Source:** `knowledge/context/reviews/synology-build-16.md` (WARNING-1)
- **Summary:** Same idiom as DEF-002: full-set `setRelationships` emitted
  by the synology adapter onto a foreign VMWARE-owned Datastore, with
  the same static-unprovable clobber risk against the owning adapter's
  child edges.
- **Closing-evidence:** Devel 9.0.2 proof, synology build 16,
  2026-06-10: wld01 iSCSI Datastore retained its 22 VMWARE children and
  gained the LUN child — the platform scopes `setRelationships`
  per-reporting-adapter. Codified in
  `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`. Residual: 9.1
  unverified (re-open or re-prove at the first 9.1 target).
- **Related:** DEF-002

### DEF-004

- **Title:** vcommunity-os: in-guest collection (services / event logs / CSV OS-info) returns empty — primary surface non-functional on devel
- **Severity:** blocking
- **Status:** open
- **Affects:** vcommunity-os
- **First-seen:** build 11 / split fork (2026-06-23)
- **Source:** `knowledge/context/investigations/vcommunity-windows-services-empty-2026-06-23.md`
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
- **Related:** `knowledge/designs/managementpacks/vcommunity-three-adapter-split.md`,
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
  Reviews: `knowledge/context/reviews/framework/bc-mirror-transport-v1.md`/`-v2.md`.
  Residual (FIPS cluster-truststore parity) documented as TODO in
  `VcfCfAdapter.openPlatformConnection()`. The remaining CP-resident
  gap is a distinct defect → DEF-006.
- **Affects:** synology
- **First-seen:** build 23 devel install (2026-07-01) — latent in every
  build ≥ 20 (first live install since the transport rework; builds
  20–22 were local-only)
- **Source:** `knowledge/context/investigations/synology-b23-devel-pkix-2026-07-01.md`
- **Summary:** The TLS/TOFU transport rework (PRs #29/#30) routed the
  loopback Suite API call through the platform's strict
  `CustomTrustManager`, assuming the platform's non-disruptive
  certificate handler would persist unknown certs (TOFU). Live devel
  disproves it: the handler fails every cycle ("Adapter certificate
  renewal url set is empty") because framework adapters declare no
  cert-renewal URL set, so trust never persists and `loadDatastores`
  PKIX-fails forever. Build 19 worked only because it trusted the
  loopback connection outright. Vendor ground truth
  (`knowledge/context/api-surface/casa-injected-vs-raw-client.md` §3): the
  aria-ops-core `SuiteAPIClient` used by every shipping Broadcom pak
  sets `verify("false")` + `ignoreHostName(true)` non-FIPS, cluster
  truststore under FIPS — none use the strict path. Fix: mirror the BC
  behavior exactly, no invention. The same framework transport ships in
  every Tier 2 pak built from current main (unifi, compliance,
  vcommunity*) — verify per pak as each rebuilds. Closes when a devel
  collect under the fixed transport loads datastores and writes the
  stitch.
- **Related:** `knowledge/designs/suite-api-stitcher-tls-auth-cleanup-v1.md`
  (premise contradicted by live evidence),
  `knowledge/lessons/suite-api-stitch-ssl-tofu-vs-java-http.md` (vindicated),
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
  `knowledge/context/api-surface/per-instance-suiteapi-credential-contract.md`;
  live mechanism discovery:
  `knowledge/context/investigations/oracle-stitch-autopsy-2026-07-02.md`;
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
  `knowledge/context/api-maps/tvs-declarative-stitching.md`; binding-value scan
  in flight), (b) CaSA node-certificate door (cleanroom build-spec
  pending). Closes when a collect executed ON the CP results in the
  Synology→VMWARE Datastore edge existing, via either mechanism.
- **Related:** DEF-005, `knowledge/context/api-maps/tvs-declarative-stitching.md`,
  `knowledge/context/api-maps/tvs-cross-mp-stitching.md`,
  `knowledge/context/investigations/cp-auth-door-probe-2026-07-01.md`

### DEF-007

- **Title:** UniFi: collect stalls silently on UNIFIED_CLOUD_PROXY
  collector — resourceState FAILED, empty adapter message, no events
- **Severity:** blocking
- **Status:** closed
- **Affects:** unifi
- **First-seen:** build 11 (`0.0.0.11`), 2026-07-06 — first-ever CP-hop
  collect attempted for this adapter
- **Source:** PROD CP verification run (content-installer report,
  2026-07-06)
- **Summary:** With the unifi adapter instance re-pointed from internal
  collector 6 to "VCF Lab CP Group 1" (UNIFIED_CLOUD_PROXY, collectors
  [3,4]) on PROD, `lastCollected` froze for 30+ minutes while
  `lastHeartbeat` kept ticking; `resourceState: FAILED`,
  `messageFromAdapterInstance` and `statusMessage` empty, no
  events/alerts on the resource — a silent stall, not a thrown adapter
  error. Reverting to collector 6 restored collection within one cycle
  (STARTED/GREEN, fresh collect) and the full 16-edge vmnic stitch works
  there, so the failure is CP-placement-specific. **Not** a framework
  ambient-identity/BC-mirror regression per se: synology proved that
  exact CP path live (DEF-006 closing evidence, same collector 3).
  Candidate causes, unverified: (a) the CP appliance cannot reach
  unifi.int.sentania.net:443 (network/VLAN reachability from the proxy
  segment), (b) a hang (not exception) somewhere in the collect path
  with no effective timeout — crash-the-cycle guards catch throws, not
  hangs, (c) CP-resident Suite API stitch call behaving differently
  than synology's. Diagnosis needs CP collector-side adapter logs
  and/or a reachability probe from the proxy. Closes when a unifi
  collect executed ON a UNIFIED_CLOUD_PROXY collector completes
  (lastCollected advances, resources collected) with the stitch intact,
  or the root cause is identified and fixed/documented as environmental.
- **Update (2026-07-06 retest, user re-pointed instance to collector 3;
  SSH to CP appliances now enabled):** reproduced, and the mechanism is
  narrowed — candidates (a) network reachability and (b) adapter hang
  are both ELIMINATED. CP-side log
  (`/storage/log/vcops/log/adapters/UniFiAdapter/UniFiAdapter_665552.log`
  on 172.27.8.52) shows the adapter executing perfectly on the CP: four
  consecutive on-cadence cycles (19:15-19:30Z), UniFi login OK, full
  enumerate, `vmnic->port stitch: 20 edges (10 hosts, 20 vmnics w/ LLDP,
  0 ambiguous, 0 unmatched, 0 conflicted)`, no errors; the CP's
  `collector.log` confirms each cycle's payload stored to the forward
  file queue (airId 665552 in every batch). Yet the central node never
  ingests: `lastCollected` and live stat timestamps frozen at the
  pre-move value for 19+ minutes, `resourceStatus: NONE`. **The break is
  between the CP's file-queue forwarder and central analytics ingestion,
  not in adapter code.** Separately, yesterday's original stall now has
  a root-cause candidate: the central analytics log shows the 0.0.0.11
  pak reinstall was pushed at 18:13Z while the instance was live on the
  CP; the old build had been collecting fine on the CP (3 clean cycles,
  0 edges — old dead LLDP code), and after the live reload the CP-side
  adapter never emitted another line under the new build — a
  reload-in-place-on-CP silent death, whereas every cold start (revert
  to collector 6 at 18:34Z, CP retest at 19:15Z) came up instantly.
  Possibly relevant contrast: synology's DEF-006 CP proof was on an
  instance *created* on the CP, not *moved* to it — a mid-life collector
  move may leave central-side data routing stale. Benign-noise note:
  `ServiceAccountsService.getServiceAccountCredentials` ERROR for
  unifi_controller fires on both working and broken attempts — weak as
  a culprit. Next candidate diagnostics: stop/start (bounce) the adapter
  instance in place on the CP to force re-registration; or compare
  central-side ingestion routing for airId 665552 vs a working CP
  instance (synology).
- **Update 2 (2026-07-06 deep-dive; adapter exonerated, reframed as
  platform issue):** user's own stop/start of the instance on collector
  3 did NOT restore ingestion (fresh cold start confirmed in CP log at
  19:39:59Z, stitch clean, lastCollected still frozen at 19:14:30Z).
  The killer discriminator: **five unrelated adapter instances on
  collector 4** (synology_diskstation, NSXTAdapter x2, VMSP,
  VirtualAndPhysicalSANAdapter/vSAN) show the IDENTICAL signature
  (STARTED / resourceStatus NONE / empty message / frozen
  lastCollected), all orphaned within a 34-second span at
  **2026-07-04T19:19:10-19:19:44Z** — coinciding with an Analytics
  service shutdown/restart on the central node (ThreadPoolExecutor
  Terminated at 19:24:19Z, "AnalyticsService has been stopped"
  19:25:17Z; the cohort froze minutes before the explicit stop lines).
  Meanwhile the majority of instances on BOTH CP collectors ingest
  fine continuously. Best-supported hypothesis: **VCF Ops platform
  resource-cache / lastCollected-tracking orphaning**, triggered by at
  least two event types — (1) an Analytics engine restart (the 07-04
  collector-4 cohort), (2) adapter-instance (re)assignment onto a CP
  (unifi, both times). The orphaned instance keeps heartbeating and
  collecting locally (CP adapter log rich and clean; forward file
  queue draining healthily at /storage/db/vcops/fq-data) but central
  tracking never updates and never self-heals — adapter-level bounce
  does not clear it; moving unifi back to internal collector 6 did.
  **Not a unifi adapter defect** — adapter code fully exonerated by
  CP-local logs (perfect cycles, 20-edge stitch, 0 conflicted). Open
  question / next diagnostic: whether an Analytics service restart (or
  another cache-reconciliation action) on the central node unfreezes
  the orphaned cohort — restart authority is the user's. Note: the
  collector-4 cohort is a live ~2-day prod monitoring gap independent
  of unifi.
- **Closing-evidence:** PROD proof, 2026-07-06 20:06-20:11Z, after the
  user rebooted both analytics nodes. Root cause was the platform
  resource-cache orphaning documented in Update 2 — NOT the unifi
  adapter (exonerated by CP-local logs: perfect cycles, 20-vmnic/16-edge
  stitch, 0 conflicted, healthy forward queue). Post-reboot, ALL six
  orphaned instances unfroze within one collect cycle: unifi on CP
  collector 3 (`lastCollected` 19:14:30Z frozen → 20:06:36Z, 128
  resources) AND the five collector-4 victims frozen since 07-04
  (synology 20:06:39Z, NSXT wld01/wld02 20:07:17/18Z, VMSP 20:06:42Z,
  vSAN 20:06:55Z). Sustained: Port 9 stat timestamps advanced again at
  20:11:33Z (second CP cycle), 16 unique HostSystem→UniFiSwitchPort
  edges intact. Closing criterion — a collect executed ON a
  UNIFIED_CLOUD_PROXY collector completing with the stitch intact —
  met and sustained. Remediation for recurrence: restart/reboot the
  analytics service/nodes; adapter-level bounces do not clear it.
- **Related:** DEF-006 (CP ambient path, closed via synology),
  `knowledge/context/reviews/unifi-build-11.md`

### DEF-008

- **Title:** Factory renderer: XML content-import path silently drops the
  `instanced` attribute on symptom conditions — every instanced symptom
  downgrades to exact-string key matching in every built pak
- **Severity:** blocking
- **Status:** closed
- **Affects:** vcommunity-vsphere
- **First-seen:** shipped pak `1.0.0.2`
  (`content/sdk-adapters/vcommunity-vsphere/dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak`),
  discovered 2026-07-09/10
- **Source:** sdk-adapter-author pak-extraction evidence — extracting
  `vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak` shows
  `content/symptomdefs/'ESXi Host NIC Disconnected.xml'` with no
  `instanced="true"` on its `<Condition>`, despite the source YAML
  (`content/sdk-adapters/vcommunity-vsphere/symptoms/esxi-host-nic-disconnected.yaml`)
  declaring `condition.instanced: true`.
- **Summary:** `src/vcfops_alerts/render.py::_add_condition_element` (the
  XML content-import path used by every pak build) never read/emitted
  `cond["instanced"]` for `metric_static`/`property` conditions, even
  though the REST-sync path
  (`vcfops_symptoms/loader.py::_condition_to_wire`) always has. Effect:
  every symptom authored with `instanced: true` — meant to match ALL
  instances of a colon-syntax metric group (e.g. any
  `vCommunity|Licensing:<name>|Remaining Days`, any
  `vCommunity|Network|Device:<nic>|Status`) — silently downgrades to
  exact-string single-instance matching in the built pak, with no error,
  warning, or validation failure. Two concrete blast-radius items in
  `vcommunity-vsphere`: the already-shipped `1.0.0.2` pak's `ESXi Host NIC
  Disconnected` symptom only fires for the literal instance name baked
  into its condition key at author time (not "any NIC"), and the new
  `esxi-host-license-remaining-days-{critical,warning,info,immediate}`
  symptoms (not yet released) would ship completely non-functional against
  their designed "any license instance" semantics. Smallest correct fix:
  emit `instanced` (plus vendor-confirmed `thresholdType`/`valueType`) in
  `_add_condition_element`, matching the vendor XML shape exactly.
- **Closing-evidence:** Fixed in `src/vcfops_alerts/render.py` on branch
  `feat/view-instanced-group-columns` (commit follows this entry).
  `_add_condition_element` now emits `instanced` for
  metric_static/property/metric_dynamic conditions, and
  `thresholdType="static"`/`valueType="numeric"|"string"` for
  metric_static/property conditions — verified byte-for-byte against three
  independent vendor symptomdef XMLs (RULE-016 read-only references):
  `reference/references/vmbro_vcf_operations_vcommunity/Management
  Pack/content/symptomdefs/ESXi Host NIC Disconnected Symptom.xml`,
  `.../Windows Service Down Symptom.xml`, and
  `reference/references/vmbro_vcf_operations_hardware_vcommunity/Management
  Pack/content/symptomdefs/Dell EMC Server Physical Disk Life Remaining -
  Critical.xml`. Unit coverage:
  `tests/test_symptom_condition_instanced_attribute.py` (8 tests). **End-to-end
  proof:** rebuilt the vcommunity-vsphere dev-preview pak
  (`python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/vcommunity-vsphere`,
  build `0.0.0.5`, no tag/release) and extracted it — all five
  `content/symptomdefs/*.xml` files (`ESXi Host NIC Disconnected.xml` and
  the four `ESXi Host License Remaining Days *.xml`) now carry
  `instanced="true" ... thresholdType="static" valueType="numeric|string"`
  on their `<Condition>` elements, confirming the fix survives the full
  build pipeline, not just the unit-level renderer call.
- **Related:** `knowledge/context/wire-formats/view_column_wire_format.md`
  (sibling instanced-group discovery, same session)

### DEF-009

- **Title:** Factory renderer: XML content-import path collapses multi-tier
  alerts to their last symptom set only — earlier tiers silently dropped on
  every field install
- **Severity:** blocking
- **Status:** closed
- **Affects:** vcommunity-vsphere
- **First-seen:** shipped dev-preview build `0.0.0.8`
  (`vcfcf_sdk_vcommunity_vsphere.0.0.0.8.pak`, installed on
  vcf-lab-operations-devel), discovered 2026-07-10
- **Source:** `knowledge/context/wire-formats/alertdef_symptomset_import.md`
  (api-explorer, live GET on devel); framework-reviewer's defect-registry
  recommendation in
  `knowledge/context/reviews/framework/import-fidelity-three-fixes.md`
  ("Defect-registry assessment" section).
- **Summary:** `src/vcfops_alerts/render.py::_render_alert_definition` (the
  XML content-import path consumed by pak-bundled `content/alertdefs/` and
  by `content-packager`'s standalone AlertContent.xml zips — see
  `render_alert_content_xml` call sites in `sdk_builder.py`, `buildkit.py`,
  `packaging/builder.py`, `packaging/discrete_builder.py`) emitted one bare
  `<SymptomSet ref=…>` sibling per symptom directly under `<State>`, with no
  `<SymptomSets>` compound wrapper. The platform's content importer keeps
  only the **last** such sibling on import and silently drops the rest — no
  error, no warning. Live-confirmed on devel: the `ESXi Host License
  Expiring` alert (4 severity tiers: Critical/Immediate/Warning/Info)
  imports and shows only its Info tier; the other three never fire. The
  REST sync path (`AlertDef.to_wire()` in `vcfops_alerts/loader.py`, used by
  `vcfops_alerts sync`) is **not** affected — it already emits the correct
  `SYMPTOM_SET_COMPOSITE` shape for multi-set alerts. Fix (already committed
  on this branch, `3d5ba94`, `fix/report-subject-filter-escaping`): groups
  `<SymptomSet>` by set (not by symptom), wraps ≥2 sets in one
  `<SymptomSets operator="…">`, leaves single-set alerts bare (unchanged),
  drops the non-vendor `aggregation="any"` attribute.
- **Empirical affected-artifact check (this entry):** every SDK adapter
  repo's bundled `alerts/` dir was inspected for `>=2`-symptom-set alerts on
  the buggy XML path, and every factory `content/alerts/` multi-set item
  was checked against `bundles/*.yaml` + `bundles/releases/*.yaml` for
  distribution-zip exposure:
  - **vcommunity-vsphere** (`content/sdk-adapters/vcommunity-vsphere/alerts/esxi-host-license-expiring.yaml`,
    4 sets) — pak-bundled, shipped in dev-preview build `0.0.0.8`, live
    collapse confirmed on devel. **Affected, this entry.**
  - **vcommunity** (`esxi-host-nic-disconnected.yaml`, `windows-service-down.yaml`)
    and **vcommunity-os** (`windows-service-down.yaml`) — bundled alerts are
    all single-set (1). Not affected.
  - **compliance**, **synology**, **unifi** — none of these three Tier 2 SDK
    adapter repos bundle an `alerts/` directory at all (no `content/alertdefs/`
    in their pak content today); the review's initial recommendation to
    register entries against "synology pak" and "compliance pak" does not
    hold up empirically and is **not** carried into this registry. The
    `content/alerts/` items targeting `mpb_synology_dsm` /
    `VMWARE` (`synology_disk_health_alert`, `synology_storage_pool_health_alert`,
    `synology_system_temperature_alert`, `synology_volume_space_alert`,
    `vm_cpu_usage_alert`, `host_compliance_score_alert` — all multi-set) are
    factory-authored content intended for direct `vcfops_alerts sync` (the
    unaffected REST path); none of them appear in any `bundles/*.yaml` or
    `bundles/releases/*.yaml` manifest today, so none currently reach a
    live instance via the buggy XML path. **If any of these six is ever
    bundled into a release/dist zip or an SDK pak's `content/alertdefs/`
    before this defect closes, that artifact needs its own DEF-0NN entry at
    that time** (schema: one issue on N artifacts = N entries).
- **Closing criterion (per-pak, per RULE-012):** closes for `vcommunity-vsphere`
  when a release built from the fixed renderer (i.e. **after** the published
  `sdk-buildkit` tarball is regenerated to carry `3d5ba94`, per the
  framework-review WARNING on buildkit propagation — official SDK pak CI
  builds from the published tarball, not the factory checkout) ships on a
  `v*` tag **and** a live devel/prod import shows all four severity tiers
  present (not just Info). Until then this entry gates `v*` tags of
  `vcommunity-vsphere` per `python3 -m vcfops_packaging defect-gate --pak
  vcommunity-vsphere` — intended: the dev-preview build already carries the
  bug in the field, and the fix is merged-pending on a branch, not yet in
  a release. This entry tracks **field state**, not code state — the code
  fix already exists (`3d5ba94`).
- **Closure attempt (2026-07-12, REVERTED — Codex PR #50 P1 upheld):** an
  attempt to close on staged evidence (fix merged #48; published
  buildkit grep-verified; build-10 live four-tier proof) was reverted
  when the criterion's actual test — BUILD from the published tarball —
  failed: `sdk-buildkit-1.0.8`'s `sdk_builder.py:2146` unconditionally
  imports factory-only `vcfops_dashboards.render` in the
  reports-with-embedded-views path, so the real `v*` CI build would
  fail on this adapter today. Grep-level presence of the fix was not
  build-level proof. New blocker: TOOLSET GAP in the buildkit's
  vendoring/import-rewrite (the kit vendors the function locally at
  `dashboard_render.py` but the new import added in PR #49 was never
  rewritten). Sequence to close: tooling fixes the import + adds an
  isolated-build regression exercising the reports path → buildkit
  1.0.9 published → tarball-build + devel install + live four-tier
  proof (the run that caught this) → THEN close with that evidence.
- **Closing-evidence:** Closed 2026-07-13 on the attempt-2 evidence run
  (content-installer, buildkit **1.0.9**), executing the exact sequence the
  reverted closure demanded. (1) **Tarball build, kit-only paths:** downloaded
  the published `sdk-buildkit-1.0.9.tgz` (522,143 bytes) from the floating
  `sdk-buildkit-v1` release (PR #52 fix merged `6c664dc`, republished before
  the run) and built vcommunity-vsphere (`fix/localization-raw-keys-build-2`
  @ `58a5304`, clean before/after) with
  `PYTHONPATH=<kit> python3 -m sdk_buildkit build-sdk … --sdk-jar
  vrops-adapters-sdk-2.2.jar` — the same invocation the pak repo's
  `build-pak-on-tag.yml` CI runs. Build succeeded; `sdk_builder.py:2146` now
  resolves `render_view_def_fragments` from the vendored `.dashboard_render`
  (the 1.0.8 `ModuleNotFoundError` that reverted the first closure is gone).
  Built-in pak-compare: 0 BLOCKING. (2) **Artifact verify:** extracted pak
  (`vcfcf_sdk_vcommunity_vsphere.0.0.0.10.pak`) carries exactly one
  `<State severity="automatic">` with one `<SymptomSets operator="or">`
  wrapping all four `ESXi_Host_License_Remaining_Days_{Critical,Immediate,
  Warning,Info}` SymptomSet refs, plus all 11 VOA report subdirs with
  co-bundled ViewDefs. (3) **Live proof:** installed on devel
  (`isInstalled=true`, 0.0.0.10); Suite API GET on the `ESXi_Host_License_
  Expiring` alertdefinition returns one `SYMPTOM_SET_COMPOSITE`/`OR` with all
  **four** `symptomDefinitionIds` present; all three adapter instances
  DATA_RECEIVING/GREEN, zero new ERROR log lines post-install. Criterion note:
  the literal "ships on a `v*` tag" wording is circular against RULE-012 (the
  gate refuses the tag while this entry is open); equivalent evidence — a
  build from the **published tarball** via the CI invocation plus live
  four-tier import proof — satisfies the criterion's intent, and the release
  runbook keeps a **non-skippable post-tag confirmation** (extract the CI-built
  pak, verify the SymptomSets wrapper, live four-tier check); if that fails,
  pull the release and reopen this entry.
- **Related:** `knowledge/context/wire-formats/alertdef_symptomset_import.md`,
  `knowledge/context/reviews/framework/import-fidelity-three-fixes.md`,
  DEF-008 (sibling XML content-import renderer defect, same pak, same
  session's discovery lineage — instanced-attribute drop, closed)
