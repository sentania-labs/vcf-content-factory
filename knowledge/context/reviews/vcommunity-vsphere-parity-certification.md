# Parity re-review certification — `vcommunity-vsphere` (vSphere scope)

**Reviewer:** `sdk-adapter-reviewer` (read-only, static)
**Date:** 2026-07-12
**Adapter:** `content/sdk-adapters/vcommunity-vsphere/` — branch
`fix/localization-raw-keys-build-2`, build_number 10, doc commit `58a5304`.
**Source reference (RULE-016, read-only):**
`reference/references/vmbro_vcf_operations_vcommunity/` (HEAD `5959b94`,
last commit 2026-03-08 — pre-review; **no source changes since the 2026-07-09
original**).
**Baseline / checklist:** `knowledge/context/reviews/vcommunity-vsphere-parity-vs-source.md`
**Design of record:** `knowledge/designs/managementpacks/vcommunity-vsphere-parity-closeout.md`
**Build review (not re-litigated):** `knowledge/context/reviews/vcommunity-vsphere-build-10.md`
**Type:** parity LEDGER certification. Content spot-check, not build mechanics.
No install, no live calls.

## Verdict: PARITY CERTIFIED (with documented deferrals)

Every gap on the original review's checklist is closed or deferred-by-design
with a citation. One NEW residual (a source multi-ViewDef file the original
review under-counted) and one documentation NIT are handed back for a future
pass; neither is a closeout failure and neither blocks certification. DEF-009
remains open as an independent release-gate (field-state) matter, not a parity
content gap.

## Ledger — original gap list

| # | Original gap (rank) | Status | Evidence |
|---|---|---|---|
| 1 | ESXi Host License Expiring alert (HIGH) | **CLOSED** | 4 instanced symptoms + alert, faithful + improved |
| 2 | 16 VOA reports (MED-HIGH) | **CLOSED w/ deferral** | 11 CSV ported; 5 PDF + Input-dashboards deferred, documented |
| 3 | nfnic VIB Vendor Distribution view (MED) | **CLOSED as framed** | UUID-verbatim; but source file had 5 ViewDefs → NEW residual |
| 4 | VM Network Top Talkers / VM Memory Allocation Trend / Distributed Port Groups (MED) | **CLOSED** | all 3 present, UUIDs verbatim, Top-Talkers filter faithful |
| 5 | Windows Services vCommunity / OPEN-B1 (LOW) | **DEFERRED by design** | recorded REFERENCE.md 183-185, design §Out-of-scope, CHANGELOG |
| + | Previously-broken licensing view (task item 5) | **CLOSED** | now instanced-group, vendor UUID kept |
| + | BY-DESIGN classifications hold (task item 4) | **HOLD** | Java untouched since build 4; OPEN-B1 recorded |

**Score: 5 of 5 original gaps closed or deferred-by-design; 1 previously-broken
view repaired; all BY-DESIGN divergences hold.**

### 1 — ESXi Host License Expiring (HIGH) — CLOSED, faithful + improved
`alerts/esxi-host-license-expiring.yaml` + 4 `symptoms/esxi-host-license-
remaining-days-{critical,immediate,warning,info}.yaml`. Verified:
- **Instanced, not hardcoded:** every symptom `condition.key:
  "vCommunity|Licensing:Any|Remaining Days"` with `instanced: true` — the
  source's hardcoded 8.x SKU string is correctly dropped.
- **Monotonic tiers:** crit LT 30 / immediate LT 60 / warning LT 90 / info LT
  160 — source's 4 threshold *values* kept verbatim, severities re-ordered
  monotonically (source was non-monotonic; documented in the alert description).
- **No-metric-no-fire:** all `metric_static`, `operator: LT`, no sentinel/no
  "missing"/"no-expiry" firing branch. 8.x perpetual licenses emit no Remaining
  Days metric ⇒ structurally cannot fire. Documented + structural. (Build-10
  review already verified the built `<SymptomSets operator="or">` shape.)

### 2 — VOA reports (MED-HIGH) — CLOSED with documented by-design deferral
`reports/` holds exactly the 11 CSV-export ReportDefs the source ships
(Datastore, Distributed Port Groups, Distributed Switch, ESXi Hosts, Namespace,
Supervisor Cluster, Virtual Machines, vCenter, vSphere Clusters, vSphere Data
Center, vSphere Pod). The 5 PDF reports (Capacity, Configuration, Executive
Summary, Inventory, Performance) + the 34-dashboard "Input dashboards" template
are **deferred by design**, recorded in `REFERENCE.md:207-211` and
`CHANGELOG.md` (build-7/8 "Still deferred") — **not silent**
(`knowledge/rules/no-fabricated-metrics.md` satisfied). *NIT:* the deferral is
NOT captured in the design-of-record doc, which is a pre-execution vision doc
still framing all 16 as target — see residuals.

### 3 — nfnic VIB Vendor Distribution (MED) — CLOSED as framed; NEW residual
`views/nfnic VIB Vendor Distribution.yaml` id `189af936-…fcbe` matches source
verbatim; reads `config|Software Packages|nfnic|Vendor` (native vCenter
attribute, matching source). **But** the source file `View - Cluster nenic nfnic
VIBs.xml` is a `<Views>` container of **5** ViewDefs; only this one was ported.
The original review named the gap as a single "nfnic VIB Vendor Distribution"
view and under-counted. See NEW residual R1.

### 4 — three SM-consuming views (MED) — CLOSED
All present, source UUIDs verbatim: VM Network Top Talkers `fc20d8a6-…d877e9`,
VM Memory Allocation Trend `8f46e7de-…c96da3`, Distributed Port Groups
`9e7dc458-…e061b`. Top Talkers `subject.filter` faithful: `net|usage_average
GREATER_THAN 12, transform AVG, business_hours false` (vendor Collection01,
byte-for-byte).

### 5 (task item) — previously-broken licensing view — CLOSED
`views/ESXi Host License Information vCommunity.yaml` id `810958f4-…8daf`
(vendor UUID kept). Now uses `instanced_group` columns (`name: GROUP_vCommunity`,
prefix `vCommunity|Licensing`, per-suffix Edition/Key/Expiration/Remaining Days)
— no longer hardcodes `Licensing:Evaluation Mode` as a filter (`sample_instance`
is pattern-ID only, documented as UNVERIFIED pending a live verify). Matches the
source's `isInstancedGroup` / `GROUP_vCommunity` idiom.

### 4 (task item) — BY-DESIGN classifications hold
Collector Java untouched since build 4 (build-10 review confirmed `git log
1db9ebd..2003a1f -- '**/*.java'` empty). Guest-OS surface → `vcommunity-os`,
scoped-MOID stitch improvement, install-date degraded-to-property — all
collector-level, unchanged, hold. OPEN-B1 (Windows Services view substitution)
unchanged and recorded (`REFERENCE.md:183-185`, design §Out-of-scope,
`CHANGELOG.md`).

## Item 6 sweep — new source surface
Source repo HEAD `5959b94` dated 2026-03-08, **no commits after 2026-07-09**;
the original review already ran against this exact source. No new source content
from upstream updates.

**One under-counted source item surfaces on close read → R1 below.**

## Residual / NEW findings (do not block certification)

- **R1 — NEW, LOW.** `views/nfnic VIB Vendor Distribution.yaml` ports 1 of the
  5 ViewDefs in source `View - Cluster nenic nfnic VIBs.xml`. Absent (verified by
  id, all ABSENT from our 109 views): `nenic VIB Vendor Distribution`
  (`ebf5961e-…d450f4`), `nenic VIB Version Distribution` (`ada5a50b-…e2bf`),
  `nfnic VIB Version Distribution` (`9599d437-…82dfd1`), `VIB Info`
  (`b4c1708e-…2b0b`, nfnic Version). These read native `config|Software
  Packages|{nenic,nfnic}|{Vendor,Version}` (VMware-adapter data, low dependency
  on our collector). Not a closeout failure — the closeout ported exactly what
  the original checklist named — but the original review under-counted a
  multi-ViewDef file. → Optional future port of the 4 sibling distributions.

- **R2 — NIT, doc hygiene.** The design-of-record closeout doc
  (`vcommunity-vsphere-parity-closeout.md`, 65 lines) is the pre-execution
  vision only; it has no executed-state closeout section and still frames all 16
  VOA reports as target. The 5-PDF + input-dashboards deferral IS recorded in
  `REFERENCE.md` + `CHANGELOG.md` (so gap honesty is satisfied), but the design
  doc the task named as a deferral-of-record surface does not carry it. →
  Orchestrator: add a one-line "EXECUTED — 11/16 shipped, 5 PDF + input-dash
  deferred" closeout to the design doc, as done for reorg-v2.

## Registry check (`knowledge/context/defects.md`)

- **DEF-009 — OPEN, blocking, Affects: vcommunity-vsphere. STILL PRESENT.**
  `python3 -m vcfops_packaging defect-gate --pak vcommunity-vsphere` re-run
  2026-07-12: *"1 open blocking defect(s) block release of 'vcommunity-vsphere'.
  Refused by RULE-012."* This is a **field-state** release gate (multi-tier alert
  collapse on the XML import path), not a parity content gap — the alert content
  in-tree is faithful and the factory renderer + published buildkit carry the fix
  (`3d5ba94`, per build-10 addendum). Closes only on a `v*` release from the fixed
  buildkit + live 4-tier proof (per its registry closing criterion). **Not a
  parity ledger item; re-asserted here, unchanged.** No propose-close (live
  4-tier proof not yet on record).
- **DEF-008** — closed, still resolved in build 10 (build-10 review verified);
  no action.
- No other open defect names `vcommunity-vsphere`.

## Bottom line
Parity closeout closed what the original review found: **5/5 checklist gaps
closed or deferred-by-design, the broken licensing view repaired, all BY-DESIGN
classifications intact.** Certification granted with two handed-back residuals
(R1 new/LOW, R2 doc NIT) and the standing DEF-009 release gate, none of which
impeach the vSphere-scope content faithfulness.
