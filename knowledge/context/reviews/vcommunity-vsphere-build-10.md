# Build review — `vcommunity-vsphere` build 10 (0.0.0.10), parity-closeout delta

**Reviewer:** `sdk-adapter-reviewer` (read-only, static, pre-release gate)
**Date:** 2026-07-11
**Adapter:** `content/sdk-adapters/vcommunity-vsphere/`
**Review unit:** branch `fix/localization-raw-keys-build-2`, commits `1db9ebd`
(build-4 localization fix) → `2003a1f` (build-10). Ships as the next `v*` release.
**Design of record:** `knowledge/designs/managementpacks/vcommunity-vsphere-parity-closeout.md`
**Baseline:** `knowledge/context/reviews/vcommunity-vsphere-parity-vs-source.md`
**Vendor reference (RULE-016, read-only):** `reference/references/vmbro_vcf_operations_vcommunity/`

## Verdict: CHANGES REQUESTED — 2 BLOCKING / 1 WARNING / 0 NIT

> **Superseded by the 2026-07-11 addendum below — both BLOCKINGs cleared; net verdict APPROVE.**

The content authoring in this delta is correct, faithful, and complete — the
license symptoms honor no-metric-no-fire, the Top Talkers filter is real, the
reports are UUID-faithful, and `bundled_content` is complete both directions.
Two blockers stand between this branch and a shippable `v*` release: (1) an
open blocking registry defect (DEF-009) whose defect-gate refuses the release,
and (2) a shipped-doc section that now contradicts the pak's actual behavior.

## Claims check (independently re-run)

- **Java untouched (author claim): CONFIRMED.** `git log 1db9ebd..2003a1f --
  '**/*.java'` is empty; `git diff 1db9ebd..HEAD -- src/com/` is empty. No
  collector Java changed across builds 5–10. Delta is content + docs + adapter.yaml only.
- **validate-sdk: CONFIRMED.** `OK: ... valid Tier 2 SDK adapter project`
  (8 source files compile; one benign `-source 11` javac warning).
- **build-sdk: CONFIRMED.** Builds `vcfcf_sdk_vcommunity_vsphere.0.0.0.10.pak`.
  Dev-preview version line `0.0.0.10` (no `--release`). Structure matches the
  verified devel build: 11 VOA reports as `content/reports/<slug>/content.xml`
  subdirs (0 flat XMLs), 120 report subdirs total (109 view-only + 11
  ReportDef+co-ViewDef), 5 symptomdefs, 2 alertdefs, four-tier alert.
- **pak-compare:** reference dir absent in this checkout (`tmp/reference_paks`)
  so build-time compare skipped; author's build-9 pak-compare (0 BLOCKING vs
  compliance 1.0.0.49) not independently reproduced here — not load-bearing for
  this content delta.

## Registry check (`knowledge/context/defects.md`)

- **DEF-008** (instanced attribute dropped from content-import XML) — **RESOLVED,
  still resolved in build 10.** My extracted pak shows all five symptomdefs carry
  `instanced="true" thresholdType="static" valueType="numeric|string"`:
  `ESXi Host NIC Disconnected.xml` → `instanced="true" ... valueType="string"`;
  the four `ESXi Host License Remaining Days *.xml` → `instanced="true" ...
  valueType="numeric"` (values 30/60/90/160). Status already `closed`; no action.
- **DEF-009** (multi-tier alert collapses to last symptom set only) — **OPEN,
  BLOCKING, affects this pak.** `python3 -m vcfops_packaging defect-gate --pak
  vcommunity-vsphere` → *"1 open blocking defect(s) block release... Refused by
  RULE-012."* See BLOCKING-1. Propose-close is **not yet warranted**: the closing
  criterion (release from a *regenerated published sdk-buildkit* on a `v*` tag +
  live 4-tier proof) is not met by a dev-preview `0.0.0.10` built from the factory
  checkout.
- The line-138 vCommunity defect `Affects: vcommunity-os` only — out of scope.

## BLOCKING

- **[knowledge/context/defects.md DEF-009 / RULE-012 `knowledge/rules/release-gate-defects.md`]**
  DEF-009 is OPEN and blocking against `vcommunity-vsphere`; `defect-gate --pak
  vcommunity-vsphere` **refuses the release**. The content and the *factory*
  renderer are fixed — `src/vcfops_alerts/render.py:413` emits the compound
  `<SymptomSets operator="or">` wrapper, and my local build-10 pak renders the
  alert as a single `<State severity="automatic">` over four `<SymptomSet>` refs
  (Critical/Immediate/Warning/Info), exactly the correct shape. **But the risk
  this defect tracks is field state, and official SDK-pak CI builds from the
  *published* `sdk-buildkit` tarball, not this checkout.** If that tarball was not
  regenerated to carry `3d5ba94`, the CI-built `v*` pak will still collapse the
  alert to Info-only — a silent false-pass my local build cannot rule out.
  → **Handed to the orchestrator (not the author):** before tagging, (a) confirm
  the published `sdk-buildkit` carries `3d5ba94`; (b) extract the CI-built `v*`
  pak and confirm the `<SymptomSets operator="or">` wrapper survives; (c) confirm
  all four tiers live on devel/prod from that pak; (d) close DEF-009 in the
  registry. `defect-gate` must go green before the tag.

- **[REFERENCE.md:148-165 — "TOOLSET GAP #2 — `instanced` attribute dropped"] —
  review dimension 11 (docs that contradict actual behavior are BLOCKING).**
  This shipped-doc section states `_add_condition_element` "does not emit the
  `instanced` attribute" and that this "silently downgrades every instanced
  symptom in this pak — `ESXi Host NIC Disconnected` and the 4 new `ESXi Host
  License Expiring` symptoms — to exact-string key matching in the built pak."
  **That is false for the pak this release actually builds.** DEF-008 is closed;
  build 10's extracted symptomdefs all carry `instanced="true"` (verified above).
  The section still cites the stale `1.0.0.2` pak and directly contradicts the
  correct license-alert section 25 lines above it in the same file — an operator
  reading REFERENCE.md is told the flagship new feature of this release is
  non-functional when it verifiably works. → Delete or rewrite GAP #2 to record
  DEF-008 as closed (instanced now emitted with `thresholdType`/`valueType`);
  keep GAP #1 (foreign-event push) which is still real.

## WARNING

- **[REFERENCE.md / README.md / docs/overview.md — review dimension 11 (capability
  absent from all doc surfaces = WARNING).]** The delta adds 11 VOA CSV-export
  reports, the VM Network Top Talkers view, the nfnic VIB Vendor Distribution
  view, VM Memory Allocation Trend, and the Distributed Port Groups report view —
  none appear in any user-facing doc surface. REFERENCE.md and README.md were
  both edited this delta (license section added) but neither gained a Reports or
  new-Views section; overview.md has no mention; the generated `docs/README.md` /
  `docs/inventory-tree.md` are `describe.xml`-only by construction (content never
  shows there). An operator browsing the pak repo cannot discover the 11 reports.
  → Add a short Reports / new-Views section to REFERENCE.md or overview.md.

## What was verified clean (skeptic default discharged from the code)

1. **Unreadable-is-not-compliant / no-metric-no-fire (dimension 1 analog).** All
   four license symptoms are `metric_static`, `operator: LT`, `instanced: true`,
   thresholds 30/60/90/160 — no sentinel, no "missing"/"no-expiry" firing branch.
   Absent `Remaining Days` metric ⇒ no evaluation ⇒ non-firing. Confirmed in
   source YAML and in the built symptomdef `<Condition ... instanced="true">`.
   The version-aware "perpetual licenses never fire" property is structural, not
   a special case. HELD.
2. **Top Talkers cannot silently become all-VMs.** `subject.filter` is present
   and non-empty: `net|usage_average GREATER_THAN 12, transform AVG,
   business_hours false` — **byte-for-byte the vendor Collection01 filter**
   (vendor `value:12`, transform AVG). HELD.
3. **Vendor fidelity (3 spot-checks).** Datastore report: ViewDef id
   `f66bed30-…1ce7` and ReportDef id `82f6005c-…172c` both reused verbatim from
   vendor. Top Talkers: ViewDef id `fc20d8a6-…d877e9` reused; filter + column
   bounds match vendor. Report→view name links: all 11 `view: 'Report: …'`
   references resolve to a view `name:` on disk. UUID uniqueness: 0 duplicate
   `id:` across 132 view/report/dashboard ids.
4. **bundled_content completeness (both directions).** symptoms 5/5, alerts 2/2,
   supermetrics 37/37, views 109/109, reports 11/11, dashboards 12/12 — every
   on-disk file registered, nothing registered missing.
5. **Four-tier alert renders correctly** (single `<State severity="automatic">`
   + compound `<SymptomSets operator="or">`) and **capped localization keys /
   subdir reports** structure present, matching the verified devel build.
6. **Localization** bundles are build-generated from YAML; validate-sdk's
   `_validate_localization_key_contract` passed and the build emitted all
   per-content bundles without a key-absent error. Per
   `knowledge/lessons/pak-content-localization-bundles.md`, integrity is enforced
   at build time and passed.
7. **CHANGELOG accuracy.** build-10 entry (PR #49 report-subdir rebuild, 120
   subdirs, SM `modifiedBy` UUID) and build-9 entry (PR #48 renderer fixes,
   Supervisor filter re-add) match the artifact I built and extracted.

## If shipped as-is

The pak itself would work (license alert fires at all four tiers, 11 reports
generate CSVs) **only if the CI release is built from a buildkit carrying
`3d5ba94`** — unproven from this checkout; if it is not, the alert silently
collapses to Info-only in the field. And any operator reading the shipped
REFERENCE.md is told the license/NIC instanced symptoms are broken when they
work. The release must not be tagged until DEF-009's gate is green and the stale
doc is corrected.

---

## ADDENDUM — re-verification 2026-07-11 (both BLOCKINGs actioned)

**Addendum verdict: APPROVE** (0 BLOCKING / 0 WARNING remaining). Re-brief actions
verified; the release may proceed under one non-negotiable post-tag condition
(below). Content, docs, and the release-gate risk are all cleared.

### BLOCKING-1 (DEF-009 / buildkit propagation) — CLEARED to proceed

The one risk my local dev-preview build could **not** rule out was whether the
*published* `sdk-buildkit` tarball (what official CI builds from — not this
checkout) carries the DEF-009 fix. That gap is now closed:

- Orchestrator downloaded + extracted the published `sdk-buildkit-v1` floating
  asset `sdk-buildkit-1.0.8.tgz` and verified it carries: `alerts_render.py:413`
  `SymptomSets` wrapper (the DEF-009 fix), `_XML_SEVERITY_MAP:171`,
  `sdk_builder.py:1487` `_cap_localization_key`, and the
  `content/reports/<slug>/content.xml` subdir pattern.
- I corroborated against the factory source (the tarball's origin): all three
  anchors sit at exactly those lines — `render.py:413` (`ET.SubElement(state_elem,
  "SymptomSets", {"operator": top_op})` under the `len(ss_elements) >= 2` guard),
  `_XML_SEVERITY_MAP` at render.py:171, `_cap_localization_key` at
  sdk_builder.py:1487. The published 1.0.8's contents are consistent with the
  fixed factory source. *(I could not independently re-extract the floating asset
  — it is not in my checkout — so this half rests on the orchestrator's
  extraction, corroborated by the line-exact factory-source parity.)*

**Assessment of the staging:** the deterministic input to the CI-built `v*` pak
(the buildkit) is now proven to carry the fix, which retires the silent-false-pass
risk BLOCKING-1 was about. The remaining half of my original closing criterion —
extract the CI-built `v*` pak, confirm the `<SymptomSets operator="or">` wrapper
survives, and confirm all four tiers live — is **confirmatory, not risk-bearing**,
and is correctly scheduled as release verification, with DEF-009 closing on that
evidence per its own registry criterion (which requires the `v*` tag to exist as
part of closing — chicken/egg resolved in favor of proceeding now that the
buildkit is proven). **The review gate is satisfied for the release to proceed.**

**Non-negotiable post-tag condition (not optional):** the scheduled release
verification MUST actually run and be green — extract the CI-built `v*` pak,
confirm the four-tier `SymptomSets` wrapper is present, and confirm all four
severity tiers fire live before DEF-009 is marked closed and the release is
announced. If that CI pak comes back Info-only (i.e. the published buildkit did
not in fact take effect on the CI path), the release must be pulled — the buildkit
evidence lowers but does not fully retire the field-state proof DEF-009 tracks.
`defect-gate` mechanics for the tag itself remain the orchestrator's/RULE-012's domain.

### BLOCKING-2 + WARNING (docs) — CLEARED

Commit `58a5304` verified **doc-only and pak byte-identical**: `git show --stat`
touches only `CHANGELOG.md`, `README.md`, `REFERENCE.md`; zero bundled-content /
Java / adapter.yaml files; `build_number` still `10`. The 0.0.0.10 pak is
unchanged, so no rebuild/re-review of the artifact is needed.

- **REFERENCE.md GAP #2 → "RESOLVED — `instanced` attribute (DEF-008, closed)"**
  (REFERENCE.md:149). Now an accurate historical note: records the drop was
  against `1.0.0.2`, fixed in factory PR #46 (`sdk-buildkit` 1.0.7+), and that as
  of build 10 the extracted symptomdefs all carry `instanced="true"` with correct
  `thresholdType`/`valueType` (NIC `valueType="string"`, four license
  `valueType="numeric"`) — matches my build-10 extraction exactly. The NIC section
  (REFERENCE.md:127-129) now states the built pak carries `instanced="true"` and
  cross-refs the RESOLVED note. **No contradiction remains.** GAP #1
  (foreign-event push) correctly kept as still-real.
- **README.md** parallel stale section given the same RESOLVED/DEF-008 treatment
  (README.md:125-138), accurate to build-10 reality; no stale "downgrade to
  exact-string" current-tense claim survives.
- **New doc coverage (clears the WARNING).** REFERENCE.md now has *Bundled views*
  (the 4 ported views, with the Top Talkers filter described as
  `net|usage_average GREATER_THAN 12, transform AVG` — matching the YAML) and
  *Bundled reports* (all 11 VOA reports named, vendor UUIDs kept) sections, plus
  honest **deferred-by-design** notes (the 5 PDF VOA reports + 34-dashboard "Input
  dashboards" template → `dashboard-author` follow-up; `Windows Services
  vCommunity` + in-guest views → `vcommunity-os` OPEN-B1). README.md carries a
  matching summary (README.md:40-50). The `Distributed Port Groups` view is
  correctly characterized as the CSV-export co-view backing the report of the same
  name — resolving the earlier ambiguity honestly.

### Net addendum verdict: APPROVE

All content, docs, and the buildkit-propagation risk are cleared. Release may
proceed. The only remaining item is the scheduled, non-skippable CI-pak + live
four-tier verification on which DEF-009 closes — a release-verification checkbox,
not a content or doc blocker. Handed to the orchestrator; nothing further required
from `sdk-adapter-author` pre-tag.
