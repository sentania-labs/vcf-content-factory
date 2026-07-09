# Review: vcommunity-os — build 1

- **Adapter:** `content/sdk-adapters/vcommunity-os`
- **Build reviewed:** 1 (`dist/vcfcf_sdk_vcommunity_os.1.0.0.1.pak`)
- **Reference for pak-compare:** `dist/vcfcf_sdk_vcommunity.1.0.0.11.pak` (unified build 11)
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT
- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-06-23

## Claims check (re-run independently)

- **validate-sdk:** CONFIRMED clean. `OK: content/sdk-adapters/vcommunity-os is a valid
  Tier 2 SDK adapter project` (only the benign `-source 11` system-modules javac warning).
- **pak-compare vs unified build 11:** CONFIRMED `Score: 0 BLOCKING, 2 WARNING, 266 INFO`
  — matches the author's "0 BLOCKING / 2 expected WARNING" claim.
  - `[W1] adapter instance identifier count: factory=7, reference=11` — EXPECTED: the four
    vSphere config-file identifiers (`esxi_adv_settings_config_file`,
    `esxi_vib_driver_config_file`, `vm_adv_settings_config_file`,
    `vm_configuration_config_file`) were dropped per design §4. 11 − 4 = 7. Confirmed absent
    from describe.xml.
  - `[W2] data kind vCommunityWorld: group attribute count: factory=7, reference=9` —
    EXPECTED: the two vSphere stitch-anchor attrs (`clusters_stitched`/`hosts_stitched`)
    were dropped; the os pak only stitches VMs. 9 − 2 = 7. Confirmed.
  - The 266 INFO lines are all the stripped vSphere collectors/content (cluster/host
    reports, SMs, symptoms) and the expected kind/name/icon/jar rename
    (`vcfcf_vcommunity` → `vcfcf_vcommunity_os`). Every diff traces to the strip; no
    unexplained delta.
- **Identity completeness:** CONFIRMED. Zero occurrences of the old kind `vcfcf_vcommunity`
  (not `_os`) anywhere in `*.java / *.xml / *.yaml / *.properties`. describe.xml key,
  adapter.yaml `adapter_kind`, entry_class, jar name, and both icons all read
  `vcfcf_vcommunity_os`. No half-rename / split-brain risk. Kind regex compliant
  (`^[a-z][a-z0-9_]*$`).

## Registry check (knowledge/context/defects.md)

- **DEF-001 (synology)** — does not affect this pak.
- **DEF-002 (unifi)** — does not affect this pak.
- **DEF-003 (synology, closed)** — does not affect this pak.
- **No open defect names `vcommunity-os` (or `vcommunity`) in `Affects:`.** Nothing to
  re-assert or propose closing.

## Review dimensions

### 1. Stitch identity — the MOID trap (THE load-bearing check) — PASS

`knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`; SKILL § *ARIA_OPS stitching identity*.
The build-2 `VMEntityVCID` per-cycle vCenter-scoping fix survived the fork **verbatim and
wired**:

- `VCommunityStitcher.setOwningVcUuid(...)` (stitcher:65) + VMEntityVCID-scoped load
  (stitcher:121–133): a loaded foreign resource whose `VMEntityVCID` ≠ the owning vCenter
  UUID is skipped, so a bare MOID can only resolve within this instance's vCenter.
- **Degrade-never-drop** preserved: a row with no `VMEntityVCID`, or an unknown owning UUID,
  is kept (unscoped fallback) — single-vCenter safe (stitcher:129, comment + guard).
- **Wired from the live SOAP session:** `stitcher.setOwningVcUuid(vsphere.getVCenterInstanceUuid())`
  (VCommunityAdapter:372), called once per cycle BEFORE `loadVmResources` (VCommunityAdapter:377).
  The UUID originates from `ServiceContent.about.instanceUuid` (VCommunityVSphereClient:119,187).
- Scope-visibility log line retained (stitcher:141–146): a silently-unscoped cycle is
  visible in the adapter log.
- Count: 6 substantive `VMEntityVCID` code refs + `setOwningVcUuid` wired — matches the
  author's "6 refs + setOwningVcUuid wired" claim.
- The stitcher pushes only properties/stats; it emits NO relationships onto foreign VMWARE
  resources (stitcher:37–39) — no `setRelationships` clobber surface (DEF-002/DEF-003 idiom
  absent by construction).

### 2. Unreadable is NOT compliant — PASS

SKILL § *Unreadable is NOT compliant*. The kept guest-ops path never converts a failed/empty
read into a pass or a fabricated row:

- Service/OS/event data is populated **only** from real `GuestOpsClient` reads
  (`collectServices` / `collectOsInfo` / `collectEvents`). No invented service rows, no
  hardcoded data masquerading as collection (VmCollector:267–344).
- Empty service rows, null OS-info, or a failed collector set `degraded=true` and emit an
  explicit `vCommunity|Guest OS|Collection Status = DEGRADED …` property (VmCollector:346–351)
  — an honest "couldn't read," not a fake value.
- A VM that yields nothing produces no props and is **not** counted as `stitched`
  (VmCollector:198–201) — no fold of unreadable-into-a-score.
- A total vCenter connect failure (NXDOMAIN / refused / timeout / login fault) is **rethrown**
  with a secret-free message and propagated to turn the instance DOWN, rather than a silent
  DATA_RECEIVING-with-zero-metrics cycle (VCommunityAdapter:343–366).

### 3. Reflection-tolerant vim25 / crash-the-cycle isolation — PASS

SKILL § *vim25 over JAX-WS*. No casts to concrete vim25 subclasses; reads walk the DOM with
local-name lookups and null-skip on absence. Guest-ops is wrapped at **two** layers so one
VM or one missing field can never abort the cycle:

- Per-VM `try/catch` around the whole VM block (VmCollector:182–205).
- The guest-gate read (`vmGuestToolsStatus`/`vmGuestFamily`) is independently wrapped
  (VmCollector:230–239) → records `READ_FAILED`, continues.
- Each collector (services / OS-info / events) is independently wrapped (VmCollector:283,
  308, 339) → sets `degraded`, continues.
- `loadVmResources` is wrapped in `safe(...)` (VCommunityAdapter:377,469) → degrades, does
  not abort.

### 4. Exception & failure granularity / observability — PASS

The previously-swallowed guest-ops SOAP fault is now surfaced: `GuestOpsClient.post()`
extracts the vim25 faultstring on HTTP 5xx, logs it at WARN with operation + VM, and captures
it for the world anchor (`guestops_last_error`) — bounded to 5 entries
(GuestOpsClient:500–522; VmCollector:116–144,357). Return value is unchanged (still null) so
collection behavior is identical; this only makes the swallowed fault visible. The build-9
decision diagnostics (`guestops_ready` / `guestops_vms` / `guestops_skips`) are bounded
(MAX_SKIP_DETAIL=10) so the anchor never floods. This is the correct shape: an operator can
tell "evaluated and passed" from "couldn't read."

### 5. Shelved-blocker honesty — PASS

SKILL § *Gaps — name them, never hide them*; `knowledge/rules/no-fabricated-metrics.md`. The KNOWN-OPEN
guest-ops blocker is documented prominently in README (`## KNOWN-OPEN BLOCKER — guest-ops
collection is shelved`, lines 11–29) and CHANGELOG (build-1), citing **both** investigation
files, which exist:
`knowledge/context/investigations/vcommunity-windows-services-empty-2026-06-23.md` and
`…-guestops-execution-divergence-2026-06-22.md`. Nothing is rigged to fake success: zero-rows
→ DEGRADED property, never an invented service. The leading-theory fix site is honest —
`GuestOpsClient.runPowershell` builds `args = "-Command \"…\""` with **no** `-ExecutionPolicy
Bypass -NonInteractive` flag (GuestOpsClient:383), exactly the state the design records as the
un-shelve fix. Not faked-compliant.

### 6. Logging quality / no secrets — PASS

`knowledge/rules/no-secrets-on-disk.md`. No `password`/`winPass`/`passwd`/`token` value is interpolated
into any log statement (grep clean). The `auth()` block builds `NamePasswordAuthentication`
into the SOAP body but is never logged. Connect-failure and fault messages carry
operation/faultstring/host only — no credential material. Skips/null-reads are at WARN with
resource context; no log spam in the per-VM loop (bounded summaries).

### 7. Memory / resource hygiene — PASS

`VCommunityVSphereClient.disconnect()` issues a vim25 `Logout` and nulls cached session state
(client:146–162); connect/collect paths route through `disconnect()` on failure
(client:178,182). HTTP connections `disconnect()` after drain (GuestOpsClient:499; client:936).
Guest-ops temp dirs are cleaned (`deleteDirQuietly`). Anchor diagnostic builders are bounded
(skip 10 / fault 5) — no unbounded growth across cycles or with VM count.

### 8. Surface allocation correctness (design §1, brief dim 3) — PASS (1 NIT)

- **KEPT (correct):** `GuestOpsClient` + the guest-ops `VmCollector` branch incl. the in-guest
  CSV OS-info path; its OWN `VCommunityVSphereClient` / `VCommunityStitcher` /
  `SolutionConfigStore` / `SuiteApiStitcher`; the Windows credential fields
  (`winUser`/`winPass`); the two monitoring enums; the vCenter credential; the two Windows
  SolutionConfig XMLs (`windows_service_list.xml`, `windows_event_list.xml`).
- **STRIPPED (correct):** `ClusterCollector.java` / `HostCollector.java` are absent; no
  vSphere VM-config keys remain (grep for `SCSI Controllers` / `Snapshot|Count` /
  `Advanced Parameters` / `Options|` / `Licensing:` / `Cluster Configuration` / `Packages:` /
  `Install Date` → empty); the four vSphere config XMLs and their describe identifiers are
  gone.
- **Note on credential structure vs design §4:** the design framed os as a separate "Windows
  Guest Credential" kind + a `Windows Monitoring` enum. The implementation instead ships ONE
  combined `vsphere_user` credential (user/password/winUser/winPass) and the prod original's
  TWO enums (`serviceMonitoring`/`winEventMonitoring`). This is an *intentional* deviation —
  it mirrors the prod original's single `vsphere_user` type exactly, and an Ops adapter
  instance binds exactly one credential, so a combined kind is the only structure that
  delivers both the vCenter-session and Windows-guest creds through one binding. The
  describe.xml header documents this explicitly (lines 20–36). Not a finding — honest and
  load-bearing.

### 9. Build hygiene — PASS

`build_number: 1`, fresh lineage (single commit `db42568`), matching CHANGELOG build-1 line.
`released: false`. resources.properties nameKey coverage is exact (every describe.xml nameKey
1/2/3/4/5/6/7/12/13/14/15/16/20/21/22/25–31/40/41 resolves; no orphan label, no missing
label). Icons named for the new kind.

### 10. Self-containment (design §2, brief dim 6) — PASS

The os pak opens its OWN vim25 session (`VCommunityVSphereClient.ensureConnected`) and its OWN
stitcher; it references no vsphere-pak class and no shared mutable state. Deliberate
duplication per §2 is realized; nothing couples it to the vsphere pak.

## Findings

### NIT-1 — dead Tools-path OS-info reader left in the forked client

`[VCommunityVSphereClient.java:597 vmGuestOsInfo()]` — minimal-diff / dead-code hygiene. The
passive VMware-Tools `guest.detailedData` OS-info reader that produces the six
`Guest OS|Operating System|OS *` keys was carried over from the unified pak but has **no
caller** (grep: the only occurrence is its own declaration). At the push layer the Tools-path
keys ARE correctly stripped — VmCollector sources `OS *` exclusively from the in-guest CSV
path (`guestOps.collectOsInfo`, VmCollector:295), per the 2026-06-23 OPEN-A refinement — so
there is **no runtime surface leak and no co-push overlap with the vsphere pak.** This is
residual fork cruft, not a correctness issue. Smallest fix: delete `vmGuestOsInfo` (and its
now-unused helpers if any) so the os client carries only what it calls. Defer-safe.

### NIT-2 — `allowInsecure` identifier present but undocumented in the strip rationale

`[describe.xml:99]` — the `allowInsecure` instance identifier is retained (it is connection
config, legitimately kept). Cosmetic only: the describe header enumerates the kept Windows
config files and enums but does not mention `allowInsecure` survived the strip. No behavior
impact; note for documentation completeness. Defer-safe.

## If shipped as-is

An operator installs a structurally-clean OS pak whose stitch identity is multi-vCenter-safe
and whose guest-ops path fails honestly (DEGRADED property + named SOAP fault on the anchor),
never faking a pass. Guest-ops returns zero rows on hardened Server 2025 DCs — but that is the
documented, intentionally-shelved KNOWN-OPEN blocker, surfaced (not hidden) and cited to two
investigation files, not a regression this build introduces. No data-corruption, crash-cycle,
or false-pass risk. The two NITs are cosmetic and defer-safe.

## Verdict

**APPROVE** — 0 BLOCKING. The fork preserved the load-bearing VMEntityVCID stitch-scoping
verbatim and wired; the strip is clean and every pak-compare diff is an explained consequence
of the split; the shelved guest-ops blocker is honestly documented and not faked-compliant.
The 2 NITs do not gate.
