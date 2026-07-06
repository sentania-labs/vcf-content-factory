# vCommunity port — like-for-like parity plan

Design of record for the goal: **iterate on devel until the `vcfcf_vcommunity`
Tier-2 Java SDK pak is a like-for-like replacement of the original
`VCFOperationsvCommunity` MP** — metrics, super metrics, views, dashboards,
reports, symptoms, alerts — verified against the original running on prod as
the parity reference.

Set 2026-06-16 with Scott. Companion to `designs/managementpacks/vcommunity.md`
(decisions) and `designs/managementpacks/vcommunity-sdk.md` (object model + gap
list). Reference recon: `context/investigations/recon_log.md` (2026-06-16
devel-vs-prod parity entry).

## The parity bar (prod original = reference)

Original `VCFOperationsvCommunity` (pak `iSDK_VCFOperationsvCommunity` v0.2.8,
DOCKERIZED), collecting on prod. It creates only its own adapter-instance kind
and pushes `vCommunity|` keys onto VMWARE Cluster / HostSystem / VirtualMachine
via ARIA_OPS stitching — same shape as the port.

- **Metric keys:** 13 Cluster / **73 Host** / **19 VM**.
- **Content:** ~55 super metrics, ~9 views, 13 dashboards, ~22 reports,
  2 symptoms, 3 alerts (full inventory + GAP list in `vcommunity-sdk.md`).

## Current state (2026-06-16, post build-3)

Collector WORKS on devel — both instances (mgmt + wld01) DATA_RECEIVING/GREEN,
`vCommunityWorld` anchor populated (`hosts_stitched=4`, `vms_stitched=36`).
Build 1.0.0.3 installed in-place; SolutionConfig store now 200 (builder fix).

Live key counts vs prod original: **Cluster 12/13**, **Host 18/73**, **VM
10/19**. Build-3 closed Host Licensing (10) and VM `Config|SCSI Controllers|*`
alias (4). **But the raw "X/73" shortfall is mostly NOT a pak defect** — once
classified correctly, pak-level collector parity is essentially reached:

- **SolutionConfig working-file gated (~54 keys):** Host Advanced System
  Settings (~15) + Packages (~5) + VM Advanced Params (2) + Options (2). The
  HTTP 400 was the builder dropping `content/files/**` (fixed); all 6 XMLs are
  200 now. BUT the shipped XMLs are the original's **all-commented reference
  files** ("DO NOT EDIT, CLONE IT"). The original's design: admin clones the
  reference to a **working file**, uncomments the settings they want, and points
  the instance at it via the `esxi_adv_settings_config_file` (+5 sibling)
  override params. Our pak ships the byte-identical reference + the same 6
  override params → **at parity with the original at the pak level.** Prod's 54
  keys come from an admin-provisioned working file, NOT from the pak. A fresh
  install of the *original* on a clean instance would also land 0 until that
  admin step. To *demonstrate* the keys on devel = replicate prod's working-file
  config (lab action), not a pak change.
- **Eval-license env-data (5 host keys):** devel hosts run VCF subscription
  licensing only; no Evaluation Mode license exists. Prod has ≥1 eval host. Not
  a bug, not reproducible on devel without an eval license.
- **Windows-CSV gated (5 VM OS keys):** the original emits `OS Name / OS Version
  / OS BuildNumber / OS Architecture / OS Last Boot Up Time / OS Release ID`
  **only** through the in-guest Windows CSV path (`vmOSInformation.py`). Phase 3
  (blocked on a Windows VM + guest cred).
- **One real code item — VM Guest OS tools path (FORK):** build-3 added a
  VMware-Tools `guest.detailedData` OS read that the *original does not have*.
  It emits inconsistent, non-parity key names (`Name`, `BuildNumber`, `Release
  ID`, `Version`, `Last Boot Up Time` unprefixed; only `OS Architecture`
  prefixed). Decision needed: **align** the path to the original's six
  `OS `-prefixed names (keep as a benign non-Windows superset, content-parity
  safe) **or remove** it for strict like-for-like (OS info then Windows-only,
  Phase 3). Pending Scott's parity-strictness call.
- **Cluster `Scale Descendants Shares` (1 key):** ClusterCollector emits it
  conditionally on `configuration.drsConfig.scaleDescendantsShares` being
  readable (line 97-98); devel clusters don't have it set → not emitted.
  Classified **env-data** (same class as eval license); 1-line prod confirm
  outstanding.

Content: **none ported** (pak `content/` has only the 6 SolutionConfig XMLs).

## Architecture decision — single pak vs vSphere/OS split

Scott raised splitting into `vcommunity-vsphere` + `vcommunity-os`.
**Recommendation: stay UNIFIED for v1.** Reasoning:

1. OS data lands on the *same* VM resource → a split means two adapters
   co-pushing `vCommunity|` onto one foreign VM (overlapping `pushProperties`
   coexistence is unproven; reopens the clobber question).
2. The OS pak can't stand alone — Windows guest-ops runs *through* vCenter's
   GuestOperationsManager, so it still needs the full vCenter connection +
   vim25 client + stitcher (duplicate, or couple to the vSphere pak).
3. It diverges from "like-for-like" (the original is one pak).
4. The optional-OS benefit a split would buy **already exists**: the
   `Windows Monitoring` enum (Disabled / Services / Event Logs / Both).

Revisit only as a **v2** consideration, and prefer **internal modules in one
pak** over two co-stitching packs. A split would only be right if OS monitoring
used a different connection (direct-to-Windows / agent) — it doesn't.

## The iteration loop

recon devel → diff `vCommunity|` keys + content vs prod original → close the gap
(collector fix or content port) → re-recon → repeat until devel == prod
(modulo explicitly-deferred items). The parity recon is the gate, not a vibe.

## Phases

**Phase 1 — Collector (metric) parity** (task #13). **Essentially DONE at the
pak level** as of build-3 (see Current state). Residual:
- 1a. ✅ SolutionConfig 400 root-caused (builder dropped `content/files/**`) and
  fixed in `sdk_builder.py`; all 6 XMLs 200 on devel. Pak ships the original's
  reference files + override params = parity. (Builder fix reviewed by
  framework-reviewer; PR pending Scott's factory-branch coordination.)
- 1b. ✅ Build 3 landed Host Licensing (10) + VM `Config` alias (4) + F2
  diagnosability. Reviewed (`context/reviews/vcommunity-build-3.md`), installed.
- 1c. ⏳ **Build 4 (Scott chose ALIGN, 2026-06-16):** keep the VMware-Tools Guest
  OS path but rename its keys to the original's six `OS `-prefixed names
  (`OS Name / OS Version / OS BuildNumber / OS Architecture / OS Last Boot Up
  Time / OS Release ID`). Benign non-Windows superset, content-parity safe.
  Only outstanding collector-code item.
- 1d. (optional, lab) demonstrate the ~54 SolutionConfig-gated keys on devel by
  replicating prod's working-file config — validation, not a pak change.

**Phase 2 — Content port** (bottom-up; prod content = per-artifact reference).
super metrics (55, resolve UUID→name) → views (~9) → symptoms (2) → alerts (3)
→ dashboards (13, RULE-011 wireframe-gated each) → reports (~22) last. Render
into the pak `content/` tree; validate; verify each against the keys now
landing on devel + cross-check vs the original on prod. Expect TOOLSET GAP →
`tooling` at GAP #2 (SM UUID rewrite), #3 (dashboard JSON→YAML), #4 (report/view
XML + four localization bundles).

**Phase 3 — Windows/OS surface (BLOCKED ON SCOTT).** Enable Windows monitoring
on a devel instance — needs a **Windows-enabled VM target + a Windows guest
credential**. Then recon the OS keys (services, event logs, full Guest OS) on
devel, close guest-ops collector gaps, verify "Windows Service Down"
symptom/alert + OS content have data. Until enabled, the Windows corner is an
explicit known-incomplete in the parity ledger (we can see the original's 6
Guest-OS props on prod, but services/event-logs are unexercised).

**Phase 4 — Sign-off + release.** Final devel-vs-prod parity recon (metrics +
content) → `pak-compare` → `build-sdk` → `qa-tester` acceptance → the RULE-012
defect gate checks before a `v*` tag → v1 ships at like-for-like.

## Blockers / dependencies

- **Windows guest credential + a Windows-enabled VM** (Scott) — gates Phase 3.
- **SolutionConfig 400** root cause — gates ~54 keys; investigate first.
- Content cross-refs resolve at author time → the Phase 2 ordering is strict.
- A real collector defect that survives a build acceptance graduates to a
  `DEF-` entry per RULE-012 (none yet — the NXDOMAIN bug was config, not code).

## Connection / UX parity gaps (captured 2026-06-24, Scott)

Surfaced while reviewing the devel install's **Accounts → adapter config**
screen. These are describe/localization/structure gaps, distinct from the
metric-key parity above. **Prod `VCFOperationsvCommunity` is the reference for
the desired labels and basic-vs-advanced split.**

1. **Pak/instance display name shows the raw kind key.** Accounts lists the
   adapter as `vcfcf_vcommunity_vsphere` instead of a friendly name. NOTE: the
   in-tree source is already correct — `resources/resources.properties` maps
   `1=` / `5=` → "VCF Content Factory vCommunity vSphere", and that file landed
   in **build 1**, which is the build installed on devel. So this is NOT a
   source-authoring gap and NOT a stale install — the built `.pak` is not
   surfacing the localization (likely a packaging/layout issue: where
   `build-sdk` places `resources.properties` vs where VCF Ops reads it).
   → investigation (api-explorer/tooling), then rebuild — not a re-author.

2. **Connection parameter labels show raw keys.** Fields render as `host`,
   `esxi_adv_settings_config_file`, `esxi_vib_driver_config_file`,
   `vm_adv_settings_config_file`, `vm_configuration_config_file`, etc., instead
   of the friendly strings already present in `resources.properties`
   (`6=vCenter Server`, `8=ESXi Advanced System Settings Config File`, …). Same
   root cause as #1 — the nameKey→string mapping isn't resolving in the built
   pak. One fix clears both.

3. **Config-file params should be Advanced Settings, not basic.** The four
   SolutionConfig file-name fields (`esxi_adv_settings_config_file`,
   `esxi_vib_driver_config_file`, `vm_adv_settings_config_file`,
   `vm_configuration_config_file`) already ship sane `default=` values and are
   `required="false"` — they should live under the collapsible **Advanced
   Settings** section so the basic connect form is just vCenter Server +
   credential, matching prod. OPEN QUESTION: a grep of every reference
   `describe.xml` finds NO functional "advanced" attribute — only section
   *comments*. The legacy prod pak is Python Integration SDK (declares advanced
   flags in adapter.py), a different mechanism than Tier-2 describe.xml. So
   whether Tier-2 describe can push identifiers into the Advanced Settings
   collapsible is UNKNOWN → candidate TOOLSET GAP; determine the SDK mechanism
   (api-cartographer/api-explorer) with prod's UX as the behavioral target
   before authoring.
