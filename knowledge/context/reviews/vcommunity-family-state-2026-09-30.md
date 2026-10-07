# vCommunity SDK adapter family: static state assessment

- **Reviewer:** sdk-adapter-reviewer (read-only, static; no install, no live Ops calls)
- **Date:** 2026-09-30 (America/Chicago)
- **Scope:** `content/sdk-adapters/vcommunity` (unified, build 11), `vcommunity-vsphere` (build 13, main `5981c3c`), `vcommunity-os` (build 1, checkout on `ci-tag-guard` `6789f09`)
- **Upstream source of record (RULE-016, read-only):** `reference/references/vmbro_vcf_operations_vcommunity/` HEAD `9e27d7d` (2026-08-07 08:04 local). Prior certification ran against `5959b94`.

## Verdict: CHANGES REQUESTED (family is not releasable as-is)

No pak in the family can ship today. `vcommunity-vsphere` main is content-correct
for its two open blockers (DEF-020, DEF-021 fixed in code and verified in a build
from the published buildkit), but the registry still holds them open and their
close conditions are circular against RULE-012. `vcommunity-os` is blocked by
DEF-004 with no progress since 2026-06-23. The unified pak is retired by design
but its gate is green and its CI is live.

New findings from this review: **0 BLOCKING / 5 WARNING / 4 NIT.** The verdict is
CHANGES REQUESTED because the RULE-012 gate refuses both shippable paks, not because
of a new BLOCKING code finding.

## Independent verification (commands re-run 2026-09-30)

| Check | Result |
|---|---|
| `validate-sdk` vcommunity | OK (plus DEF-012-class loader warnings on its unfixed distribution views) |
| `validate-sdk` vcommunity-vsphere | OK |
| `validate-sdk` vcommunity-os | OK |
| `build-sdk` vsphere main (factory checkout, to scratchpad) | Built `0.0.0.13.pak` |
| `build-sdk` vsphere main via published `sdk-buildkit-1.0.10` (the CI path, no `--release`) | Built `0.0.0.13.pak`; built-in pak-compare 0 BLOCKING, 1 WARNING |
| `pak-compare` vsphere main vs released `v1.0.0.12` asset | 0 BLOCKING / 0 WARNING / 0 INFO (structural only) |
| `build-sdk` vcommunity-os | Built `0.0.0.1.pak` |
| `defect-gate --pak vcommunity` | exit 0, no open blocking defects |
| `defect-gate --pak vcommunity-vsphere` | exit 2, DEF-020 + DEF-021 |
| `defect-gate --pak vcommunity-os` | exit 2, DEF-004 |

Extracted-pak check (kit-built vsphere `0.0.0.13`): the Distributed Switch CSV view
now resolves all four columns to `Super Metric|sm_<uuid>` keys (DEF-021 fixed), and
the VM Details widget carries `ae751947-1782-466f-b560-9a950be3c1f9` with no
bare-name `Windows Services vCommunity` anywhere in the pak (DEF-020 fixed). That
UUID matches `vcommunity-os/views/Windows Services vCommunity.yaml:1`.

## Q1. Port-to-port drift

**Java: no drift.** Every difference in the three non-identical files is surface
allocation per the split design (section 1 and 4) or comments.

- `VCommunityConfig`: vsphere drops the Windows credential fields, the
  `WindowsMonitoring` enum, and the two Windows config-file names; os drops the
  four vSphere config-file names. Nothing else.
- `VCommunityAdapter`: vsphere drops guest-script loading, `buildGuestOps()`, the
  guest-ops anchor metrics and the build-9/10 diagnostics
  (`guestops_ready/vms/skips/last_error`); os drops cluster/host loads, the four
  vSphere check-list fetches, and `clusters_stitched/hosts_stitched`. Adapter kind
  constants are correct per pak.
- `VmCollector`: vsphere keeps `collectConfig` (byte-identical body to unified,
  comments aside); os keeps the guest-ops block, whose text from
  `collectGuestOps` to end of file hashes identical to unified
  (`b0b9effb...`). The os pak only counts a VM as stitched when it pushed guest
  data (`vcommunity-os/.../VmCollector.java:198-201`), which is correct for a pak
  with no passive surface.
- Build-2 `VMEntityVCID` scoping: `VCommunityStitcher.java` byte-identical in all
  three (md5 `e08070ed...`). Build-9/10 guest-ops diagnostics: present in unified
  and os (identical `GuestOpsClient`, md5 `3b4d038d...`), stripped from vsphere by
  design.

**Content drift (unified vs vsphere):** the Cluster Performance 2.0 fix landed in
both (unified `95ed99c` #7, vsphere `2ebc967` #19); the dashboard files are now
identical. Unified is behind vsphere on everything else, all fixed only in vsphere:
22 distribution views without the DEF-012 DISCRETE shape, the pre-fix licensing
view, and no license alert, 4 license symptoms, 11 CSV reports, or the 14 views
added by the parity closeout. Unified `VM Details.yaml:606` references
`Windows Services vCommunity` by name, which is valid there because unified bundles
that view.

**Does unified carry anything vsphere + os do not?** Content: no (the union of
vsphere + os is a strict superset). Behavior: one thing. Unified writes the six
`Guest OS|Operating System|OS *` keys from both the Tools path and the in-guest
CSV path into one map per VM, so the CSV value wins deterministically. In the split,
vsphere (Tools path) and os (CSV path) would both write those keys from independent
schedules: last-writer-wins. This is the design's OPEN-A, deferred to os un-shelve,
and still undecided.

**Does vsphere + os carry anything unified does not?** Yes, all of the content
above, plus the fixes.

**Localization drift (cosmetic):** vsphere removed seven `<int>.description`
bundle keys in `db39289` (build 2); os still carries them (7), unified carries 11.
The investigation that motivated the removal later falsified that theory (root
cause was a devel JVM bug, `vcommunity-vsphere-localization-2026-06-24.md` pass 4),
so os is not broken; vsphere simply lost its field tooltips for nothing.

## Q2. Collector functionality vs upstream Python (HEAD 9e27d7d, v0.3.0)

Upstream `docs/metrics-reference.md` documents 139 key patterns across five object
types. Our ports cover 31 of them (Cluster 13/22, Host 14/46, VM 4/51,
Datastore 0/9, vCenter 0/11). Guest-OS keys are outside that doc upstream.

| Upstream module | vsphere | os | unified |
|---|---|---|---|
| `collectors/cluster` + `properties/cluster/{ha,drs,evc}` + `metrics/cluster/drs_metrics` | `ClusterCollector` (13 keys) | none | same as vsphere |
| `properties/cluster/{dpm,cluster_configuration}` (new in v0.3.0) | none | none | none |
| `collectors/host` + `host_{advanced_settings,software_packages,install_date,licensing,uplink}` | `HostCollector` | none | same |
| `properties/host/host_configurations.py` (new: VAAI, time zone, boot time, BIOS vendor, HBA, DHCP, search domain, Max EVC, config status) | none | none | none |
| `host_uplink.py` new 9 PCI/MAC/WoL/duplex fields | none (4 original fields only) | none | none |
| `collectors/vm` + `vmConfig`, `vm_extra_config` | `VmCollector.collectConfig` | none | same |
| `vm_disk.py` SCSI part | `VmCollector` SCSI keys | none | same |
| `vm_disk.py` new vNIC and virtual-disk parts; `vm_configurations.py` (29 new keys) | none | none | none |
| `vmService.py`, `vmOSInformation.py`, `events/vm/*` | stripped by design | `GuestOpsClient` + `VmCollector` | both |
| `collectors/datastore` + `properties/datastore/*` (new) | none | none | none |
| `collectors/vcenter` + `properties/vcenter/*` (new) | none | none | none |

**Surfaces upstream collects that no Java port collects:** Datastore (9 keys,
stitched onto VMWARE `Datastore` by `VMEntityObjectID`) and vCenter (11 keys,
stitched onto VMWARE `VMwareAdapter Instance` by `VMEntityVCID`), plus 9 cluster,
32 host, and 47 VM keys. All are vim25-sourced, so the split's allocation rule puts
them in vsphere. Porting Datastore needs a new stitcher load kind with the same
`VMEntityVCID` scoping (lesson `stitch-moid-not-unique-across-vcenters.md`).

**Behavior differences in ported keys (upstream changed in v0.3.0):**

- HA gating: upstream now keeps real values for `VM Monitoring` and
  `Heartbeat Datastore` when HA is on but host monitoring is disabled; ours pushes
  `"null"` for all HA keys in that case (`ClusterCollector.java:67-68`).
- `DRS|CPU Over-Commitment`: upstream now `"null"` and gated on DRS enabled; ours
  `"N/A"`, ungated (`ClusterCollector.java:100-103`).
- `DRS|DRS Score`: upstream clamps negative to 0; ours pushes the raw value.
- EVC: upstream switched to `summary.currentEVCModeKey` to stop vCenter task noise
  (issue #83). Ours still calls `EvcManager()` (WARNING-1).
- `Snapshot|Count`: removed upstream (`vm_snapshot_metrics.py` deleted); ours
  still emits it. No content in either pak consumes it. Harmless superset.
- Install date: upstream now writes `"null"` on failure; ours writes
  `Install Date|Read Error`. Ours is the better behavior; keep it.
- Config files: upstream `get_config_file_data` now returns `[]` on fetch failure
  and collectors skip. Ours keeps last-good caching plus a degradation notice.
  Stricter; keep it.
- Credential model: unchanged upstream (one `vsphere_user` with optional
  `winUser`/`winPass`). os mirrors it; vsphere drops the Windows fields by design.
- Collection shape: upstream now does one bulk PropertyCollector retrieve per type
  and runs five collectors on a thread pool. Ours reads per object, serially
  (NIT-3).
- Guest ops: upstream changed only copyright headers in the three `.ps1` scripts
  and callers. Still `-Command` with no ExecutionPolicy flag
  (`vmService.py:51`).

## Q3. Upstream drift since certification (5959b94..9e27d7d)

48 commits, 2026-07-21 through 2026-08-07. One substantive one:
`c6b6e2f` (PR #89, v0.2.8 to v0.3.0, merged 2026-07-21, nine days after the
2026-07-12 certification). It closes upstream #11, #77, #78, #83, #84, #85, #86,
#87, #88. The rest are documentation moves, a new `docs/metrics-reference.md`,
and a new `tools/importer/` (bulk adapter-instance importer from CSV, no port
equivalent, out of scope). Several new upstream modules are authored by Scott
Bowe (`host_configurations.py`, `host_install_date.py`, `vm_disk.py`).

**Content: unchanged.** `git diff --name-status 5959b94 9e27d7d -- 'Management
Pack/content'` shows only `.DS_Store` deletions. Upstream counts (excluding
`.gitkeep`/`.xsd`): 54 SM files (37 unique, 17 duplicate-UUID pairs per the port
worklist), 13 dashboards, 32 report-directory files (16 VOA ReportDefs + 16 view
files), 3 alertdefs, 2 symptomdefs, customgroups/policies/recommendations empty.

| Surface | Upstream | Ours (vsphere + os) | Status |
|---|---|---|---|
| Super metrics | 37 unique | 37 | parity |
| Dashboards | 13 | 12 | known deferral: Input dashboards |
| VOA reports | 16 | 11 | known deferral: 5 PDF reports |
| Views | 16 files (plus multi-ViewDef containers) | 109 + 1 | known residual R1 (4 nenic/nfnic siblings); Windows Services view lives in os (OPEN-B1) |
| Alerts | 3 | 2 + 1 | parity |
| Symptoms | 2 | 5 + 1 | parity (license alert re-expressed as 4 instanced symptoms) |
| Custom groups / policies / recommendations | none | none | nothing to port |

**New parity gaps:** all collector-side, from `c6b6e2f` (Q2). **No new content
gaps.** The known deferrals are unchanged. The certification's section 6 line
"no source changes since the 2026-07-09 original" was true on 2026-07-12 and is now
stale for collectors.

## Q4. Release and defect state

| Pak | adapter.yaml | Newest tag / release | State |
|---|---|---|---|
| vcommunity | 1.0.0 build 11, `released: false` | none | retired by design; public repo, not archived; CI live; gate exit 0 |
| vcommunity-vsphere | 1.0.0 build 13, `released: true` | `v1.0.0.12` (commit `6277865`, release published 2026-07-13 17:55 local; a second Draft `v1.0.0.12` also exists) | main is 11 commits past the tag, unreleased; gate exit 2 |
| vcommunity-os | 1.0.0 build 1, `released: false` | none | gate exit 2 |

`build_number: 13` vs tag `.12` is expected: build 13 (`e9fce12`, DEF-012 sweep) and
the later fixes #19 and #21 were merged without a bump, per the #19 commit message
("the bump belongs to whoever cuts the tag"). `released: true` is the
"has ever released" flag set by `76b090c`, not a claim about main.

Registry (`knowledge/context/defects.md`), every entry naming a vcommunity pak:

- **DEF-004** (blocking, open, vcommunity-os): still present. Fix site unchanged,
  `vcommunity-os/src/.../GuestOpsClient.java:383` builds `-Command "..."` with no
  `-ExecutionPolicy Bypass -NonInteractive`.
- **DEF-020** (blocking, open, vsphere): **resolved in code**, `2ebc967` (#19),
  `dashboards/VM Details.yaml:606` now the UUID. Verified in a kit-1.0.10 build.
  Propose close once a devel install of that build shows the widget resolves (it
  renders empty unless vcommunity-os is installed, which is the accepted OPEN-B1
  behavior).
- **DEF-021** (blocking, open, vsphere): **resolved in code**, `5df0011` (#21),
  four quoted refs; verified rendering to `sm_` keys in a kit-1.0.10 build. Propose
  close on a devel render of the Distributed Switch CSV report with populated
  columns.
- DEF-008, DEF-009, DEF-010, DEF-011, DEF-012 (vsphere): closed, no change.
- Nothing open names `vcommunity` (unified).

**Close-condition problem:** DEF-020 and DEF-021 both read "version bump and CI
release". That is the circular wording the DEF-009 criterion amendment (2026-07-13)
already ruled unsatisfiable: CI runs the defect gate, so the gate refuses the tag
the condition requires. They need the same amendment (published-buildkit build plus
a live devel proof), then closure, then the tag.

**vcommunity-os branches:** the checkout is on `ci-tag-guard` (`6789f09`), which is
pushed. Its content already reached `origin/main` as squash-merge `43ac10a` (#6,
2026-08-21). `origin/main` then moved on with `5e06f9c` (#8, 2026-09-24, GitHub-hosted
runner). Local `main` is 2 behind `origin/main`. `ci-tag-guard` is now stale:
diffed against `origin/main`, it would put back the retired self-hosted runner label
and the old README fork guidance. The same stale `ci-tag-guard` exists on the other
two repos.

## Q5. vcommunity-os shelved blocker

**Unchanged; nothing moves it.** The os repo has no code commits after build 1
(`db42568`, 2026-06-23); everything later is CI. In the factory, the last guest-ops
evidence is `recon_log.md` sections dated 2026-06-22 and 2026-06-23 plus the two
2026-06-23 investigation files. Later edits to those files and to the split design
are the 2026-07-09 `knowledge/` reorg and the 2026-09-14 `vcfops_` to `vcfcf_`
rename (`73596c6`, pure substitution). No lesson covers ExecutionPolicy or
ConstrainedLanguage. Upstream offers nothing new: script changes are headers only,
and `docs/system-requirements.md:45-46` says a standard non-admin account suffices
(plus `Event Log Readers` for the Security log). That is consistent with the
already-eliminated privilege hypothesis and says nothing about execution policy.
The leading theory is still unconfirmed and the next step is still the DC-side
`Get-ExecutionPolicy -List` / `LanguageMode` check the README describes.

## Findings

### WARNING

- **W1. [vsphere + unified `VCommunityVSphereClient.java:316-336`, called from
  `ClusterCollector.java:115`] Upstream #83, lessons/skill section "vim25 over
  JAX-WS".** EVC is read by invoking the `EvcManager()` method on every cluster
  every cycle. Upstream reports this creates a "Retrieve EVC" task per cluster per
  poll in the vCenter task list, and fixed it in v0.3.0 by reading
  `summary.currentEVCModeKey`. Ours issues the same vim25 call, so it should
  produce the same noise (static inference, not live-verified). Fix: read
  `summary.currentEVCModeKey` over the PropertyCollector like upstream. That also
  removes one SOAP round trip per cluster and fixes the EVC half of W2.
- **W2. [vsphere + unified client `:951` (fault returns null), `:651`, `:684`;
  `ClusterCollector.java:120`; vsphere `VmCollector.java:79,106`] Skill section
  "vim25 over JAX-WS" ("a missing field is null, skip, never a default"),
  "Unreadable is NOT compliant".** `post()` turns any SOAP fault into `null`, and
  three callers turn that `null` into a definite value: EVC unreadable becomes
  `EVC|Enabled = False`, snapshot unreadable becomes `Snapshot|Count = 0`,
  `config.hardware` unreadable becomes `SCSI Controllers|Count = 0`. A VM that
  vanishes mid-cycle, or one the service account cannot read, is reported as
  "no snapshots / no controllers", and a cluster whose EVC read faults is reported
  as EVC disabled. This predates the split, faithfully mirrors upstream, and
  shipped in v1.0.0.12; prior reviews recorded these paths as skip-on-unreadable,
  which they are not. Not rated BLOCKING because the values are inventory, not
  scores, and are rare in practice; it should not hold the DEF-020/021 release.
  Fix: distinguish fault from absence (`lastFaultString` is already captured)
  and skip on fault. **Registration candidate.**
- **W3. [vsphere REFERENCE.md, certification report] Skill section "Gaps: name them,
  never hide them".** Upstream v0.3.0 added about 108 collector keys and two
  stitch targets (Datastore, vCenter) nine days after certification. No port or
  doc records this; the certification reads as current. Fix: an orchestrator
  decision to port it (vsphere, per the allocation rule) or record it as a named
  deferral in REFERENCE.md and a note on the certification. Include the four
  behavior changes to already-ported keys in Q2.
- **W4. [unified repo `sentania-labs/vcf-content-factory-sdk-vcommunity`] RULE-012
  intent, split design OPEN-D.** The retired pak's repo is public and not archived,
  its README has no "superseded" notice, CI is live, and its defect gate passes.
  A `v1.0.0.11` tag would publish a pak carrying the 22 DEF-012-class views and the
  pre-fix licensing view. OPEN-D says remove it at vsphere+os devel parity, which
  cannot happen while os is shelved. Fix: decide now. Archive the repo plus a README
  pointer (needs Scott's go), or register a defect against `vcommunity` so the gate
  holds.
- **W5. [vsphere `CHANGELOG.md`, `README.md:65-66,83`] Review dimension 11 (docs
  parity).** Main carries two user-visible fixes (#19 Cluster Performance 2.0 tiles
  plus VM Details widget, #21 Distributed Switch CSV columns) with no CHANGELOG
  entry; the next tag would ship them undocumented. The README tells operators to
  install `vcommunity-os` for Windows monitoring, but os has no release and cannot
  get one while DEF-004 is open, so the VM Details Windows Services widget stays
  empty for every operator. Fix: add the CHANGELOG entry at the bump, and say in
  README that os is unreleased.

### NIT

- **N1. [vcommunity-os checkout]** On stale `ci-tag-guard`; local `main` 2 behind.
  Switch to `origin/main` before any os work. Stale local branches in all three
  repos (`ci-tag-guard`, `fix/scoreboard-partial-bounds`,
  `build/build-13-def-012-proof`, `fix/localization-raw-keys-build-2`, and others)
  plus the stray Draft `v1.0.0.12` release on the vsphere repo. Deleting any of them
  needs Scott's go.
- **N2. [os `README.md` links; vsphere `README.md:64`]** Links predate the
  `knowledge/` reorg (`../../../designs/...`, `context/investigations/...`,
  `lessons/...`). The os README's "surface the swallowed StartProgram fault" step is
  already done (build 10 `guestops_last_error`).
- **N3. [client per-object `RetrieveProperties`] Skill section "The bulk-read dynamic
  pattern".** Every VM read is its own SOAP call, and VM Options costs one call per
  enabled check-list key per VM. The default lists ship fully commented out, so the
  cost only appears once an operator enables keys. Upstream now bulk-retrieves per
  type. Worth doing if the W3 port happens.
- **N4. [resources.properties]** `.description` key drift across the three paks
  (Q1). Cosmetic; the removal theory was falsified.

## Registry check (knowledge/context/defects.md)

- DEF-004: open, still present at `vcommunity-os/src/com/vcfcf/adapters/vcommunity/GuestOpsClient.java:383`.
- DEF-020: RESOLVED in code. Propose close: fix `2ebc967` (#19) on vsphere main,
  verified in a published-buildkit-1.0.10 build of `5981c3c`. Owed first: amend the
  circular close condition per the DEF-009 precedent, then a devel install and
  render check.
- DEF-021: RESOLVED in code. Propose close: fix `5df0011` (#21), same build
  verification. Owed first: the same amendment plus a devel render of the report
  columns.
- Registration candidates: W2 (vsphere, silent defaults on faulted reads); W4 if
  Scott chooses to register rather than archive.

## If shipped as-is

Nothing can ship: the gate refuses vsphere (DEF-020/021, already fixed in code) and
os (DEF-004), and the one pak the gate allows is the retired unified pak, which would
publish known-broken views. Operators on v1.0.0.12 today still see the blank VM Details
widget and blank Distributed Switch CSV columns, and very likely a "Retrieve EVC" task
per cluster per cycle in vCenter.
