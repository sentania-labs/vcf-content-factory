# Review — vcommunity-vsphere build 1

- **Adapter:** `content/sdk-adapters/vcommunity-vsphere` (repo HEAD f1dd9ca)
- **Pak reviewed:** `dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.1.pak`
- **Reference:** unified `dist/vcfcf_sdk_vcommunity.1.0.0.11.pak`
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 1 NIT
- **Date:** 2026-06-23

## Claims check (re-run independently)

- `validate-sdk`: **CONFIRMED clean** — compiles 8 source files, "OK: valid
  Tier 2 SDK adapter project" (1 benign `-source 11` javac warning).
- `pak-compare` vs unified build-11: **CONFIRMED — 0 BLOCKING / 3 WARNING /
  18 INFO**, exactly matching the author's claim. Every WARNING/INFO traced
  to the Windows strip (enumerated below).
- Source repo `content/sdk-adapters/vcommunity/`: **CONFIRMED at HEAD
  63ac66e, clean working tree** — the fork did not mutate the unified pak
  (claim 7).

## Registry check (`context/defects.md`)

- No open defect names `vcommunity-vsphere` (or `vcommunity`) in `Affects:`.
  DEF-001 (synology), DEF-002 (unifi), DEF-003 (synology, closed) — none
  affect this pak. **Nothing to re-assert.**

## Independent verification of each delta

Every `pak-compare` WARNING/INFO maps to dropping the Windows/guest-ops
surface — none is unexplained:

- **W1** CredentialField 2 vs 4 — vCenter `user`/`password` only; Windows
  `winUser`/`winPass` dropped. Expected.
- **W2** instance identifier 7 vs 11 — dropped Windows credential ref,
  Windows Monitoring enum, and the 2 Windows config-file names (4 fewer).
  Expected.
- **W3** vCommunityWorld group attrs 6 vs 9 — verified the 3 dropped attrs
  are exactly the guest-ops telemetry `guest_vms_attempted`,
  `guest_vms_degraded`, `events_as_properties` (nameKeys 26/27/28). All
  vSphere anchor attrs retained. No Java still writes the dropped attrs
  (grep clean — no dead writes to nonexistent describe attributes).
- **I1–I6** Windows alert/symptom/view/report + 2 Windows config XMLs
  stripped. Expected.
- **I7–I9** name/description/display_name fork identity deltas. Expected.
- **I10–I14** icon rename old kind → `vcfcf_vcommunity_vsphere`. Expected.
- **I15–I17** the 3 `.ps1` scripts (`getWindowsEventLogs`,
  `getWindowsOSInformation`, `getWindowsServices`) stripped. Expected.
- **I12/I18** jar rename. Expected.

## Dimension findings

1. **Cardinal correctness (unreadable ≠ compliant)** — PASS. This pak pushes
   properties/stats; it has no scoring/denominator surface. Every reader
   pushes a key only when the value is present and non-empty:
   `VmCollector.collectConfig` skips each OS field whose map entry is absent
   (`:131–135`); `vmGuestOsInfo` (`VSphereClient:597–633`) builds the map by
   null-skip on each `detailedData` entry and on `runtime.bootTime`. No
   failed/missing read folds to a sentinel or a pass.

2. **Reflection-tolerant vim25 reads** — PASS. `vmGuestOsInfo` and the
   guest-tools reads (`:545–569`) walk the DOM via `walkToNode` /
   `childText` / `childrenByLocalName` with no cast to a concrete vim25
   subclass, no assumption of a single accessor shape; absent fields return
   null → skip, never throw.

3. **Exception / failure granularity** — PASS. `VmCollector.collect`
   (`:44–62`) wraps each VM in a per-resource try/catch that logs at warn
   with VM name + exception class/message and continues — a single VM's
   failed read cannot abort the collection cycle. No empty catch, no broad
   swallow-to-pass.

4. **Canonical loader contract** — N/A surface unchanged from unified;
   config-file parsing untouched by the fork (the central-store fetch is
   scoped to the 4 vSphere files at `VCommunityAdapter:140–143`; no Windows
   file is fetched, so no spurious fetch-error logging).

5. **Stitch identity (the MOID trap) — load-bearing, the #1 confirm** —
   PASS. The build-2 `VMEntityVCID` vCenter-scoping fix survived **verbatim**
   (`VCommunityStitcher:115–146`) with the correct degrade-not-drop
   semantics: a foreign resource is skipped only when the owning UUID is
   known AND the row's `VMEntityVCID` is known AND mismatched (`:129–133`);
   any row lacking the discriminator, or any cycle where the owning UUID is
   unknown, falls back to unscoped and keeps the resource. Wired each cycle
   at `VCommunityAdapter:326` —
   `stitcher.setOwningVcUuid(vsphere.getVCenterInstanceUuid())`. Matches
   `lessons/stitch-moid-not-unique-across-vcenters.md` and the skill's
   *ARIA_OPS stitching identity* rule. No regression.

6. **Logging quality / no secrets** — PASS. Per-VM failures logged with
   resource context; stitcher load logs the scope (`scoped to vCenter
   <uuid>; skipped N` vs `unscoped — owning vCenter UUID unknown`) so a
   silently-unscoped cycle is visible. No credential/token in any log path
   reviewed.

7/8. **Resource hygiene / API discipline** — unchanged from the unified
   build-11 (fork is a pure strip, no new read paths); no regression
   introduced.

9. **Build hygiene** — PASS. `build_number: 1` (fresh lineage) with a
   matching `CHANGELOG.md` build-1 entry. The diff is a clean strip — no
   drive-by refactor of the kept collectors.

10. **Gap honesty** — PASS. The guest-ops surface is named as belonging to
    `vcommunity-os` in javadoc and the manifest description; no control is
    silently mapped onto a stripped path. The passive Tools-path OS keys are
    documented as the sole writer while os is shelved (design 2026-06-23
    OPEN-A refinement).

## Specific brief checks

- **Identity completeness (claim 2):** grep for the old kind `vcfcf_vcommunity`
  (excluding `_vsphere`/`_os`) across xml/yaml/java/properties/py returned
  **zero** hits. `adapter.yaml` and `describe.xml` both
  `vcfcf_vcommunity_vsphere`; kind is regex-compliant
  (`^[a-z][a-z0-9_]*$`). No half-rename / split-brain risk.
- **Passive-OS-reader liveness (claim 4):** `vmGuestOsInfo`
  (`VSphereClient:597`) is KEPT **and** LIVE-CALLED by
  `VmCollector.collectConfig:131` → pushes `vCommunity|Guest OS|Operating
  System|*`. Unlike the os fork (where this reader is correctly dead), here
  it is wired. The vsphere pak does NOT silently drop OS-info keys.
- **Surface allocation (claim 3):** KEPT = Cluster/Host/Vm collectors,
  `VCommunityVSphereClient`/`Stitcher`/`SolutionConfigStore`, vCenter
  credential, the 4 vSphere config XMLs, the passive Tools OS keys. STRIPPED
  = `GuestOpsClient` (no such file), guest-ops `VmCollector` branches,
  Windows credential, Windows Monitoring enum, 2 Windows XMLs, 3 `.ps1`.
  All confirmed.

## WARNING

- **[dashboards/VM Details.yaml:606 → built `VM_Details/dashboard.json`]**
  design OPEN-B/B1 (`vcommunity-three-adapter-split.md`) — the `VM Details`
  dashboard ships a view widget referencing `Windows Services vCommunity`
  **by name string**, but that view is intentionally not shipped in this pak.
  The SDK builder did **not** hard-fail (build clean, pak-compare 0
  BLOCKING), so this is a lazily-resolved name reference, not a build-time
  link error — consistent with the accepted B1 "degrade to no-data" idiom
  and with the already-APPROVED os pak. **This is the design-accepted
  watch-item, not a static-gate blocker.** It is recorded as WARNING because
  the runtime behavior (dashboard loads with an empty widget vs. a hard
  dashboard-load error) **cannot be proven from the code** and is outside a
  static gate — it must be confirmed live by `qa-tester` / the orchestrator's
  devel proof before release. → No source change required at this build;
  hand to qa-tester to confirm degrade-to-no-data (and, per design, to
  document the dependency in the dashboard description).
  *(The brief also named `Critical Business Applications` as carrying this
  embed; the actual dangling embed in this build is in `VM Details`, not
  `Critical Business Applications` — grep of the latter finds no Windows/
  Services view reference. Noting the discrepancy for the record; immaterial
  to the verdict.)*

## NIT

- **[manifest description]** The fork description (I7) is a long single
  paragraph duplicating much of the README runbook prose. Cosmetic; trim if
  desired. No action required.

## If shipped as-is

An operator installs a vSphere-only pak that shows only vCenter credentials
(no Windows fields), collects clusters/hosts/VMs over vim25, correctly scopes
stitch identity per vCenter, and populates basic Guest-OS inventory via the
passive Tools path. The one rough edge: the bundled `VM Details` dashboard
contains a Windows-Services widget that will show no data until/unless the
`vcommunity-os` pak is installed — accepted design behavior, pending a live
confirmation it degrades rather than erroring the dashboard load.

## Registration candidates (RULE-012)

- The dangling-view WARNING is **conditional** — it only graduates to the
  registry if the live degrade-to-no-data check fails (i.e. if it turns out
  to error the dashboard load). If qa-tester confirms graceful degradation,
  it stays a review WARNING and does not enter `context/defects.md`. Flag to
  the orchestrator to decide after the devel proof.
