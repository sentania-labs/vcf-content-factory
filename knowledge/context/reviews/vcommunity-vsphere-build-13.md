# sdk-adapter-reviewer — vcommunity-vsphere build 13

- **Adapter:** `content/sdk-adapters/vcommunity-vsphere`
- **Branch / commit:** `fix/distribution-views-discrete-sweep` @ `e9fce12`
- **Build reviewed:** dev-preview `0.0.0.13` (release line `1.0.0.13`)
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 2 NIT
- **Date:** 2026-07-14

## Scope

DEF-012 remediation sweep. **No Java changed** — the delta is 17 view YAMLs
(+3 fields each), `adapter.yaml` build bump, `CHANGELOG.md`, and two doc
version lines. Confirmed via `git diff --name-only 76b090c e9fce12`: only
`views/*.yaml` (17), `adapter.yaml`, `CHANGELOG.md`, `docs/README.md`,
`docs/inventory-tree.md`. No adapter Java, describe.xml, profile, or
collector code touched.

## Claims check (independently re-run)

- **validate-sdk:** CONFIRMED. `python3 -m vcfops_managementpacks validate-sdk`
  → "valid Tier 2 SDK adapter project" (javac 8 files, 1 benign `-source 11`
  warning).
- **build-sdk:** CONFIRMED. Built `dist/vcfcf_sdk_vcommunity_vsphere.0.0.0.13.pak`
  clean. (The author's `0.0.0.13.pak` was not present in the adapter's `dist/`
  in this working tree — expected, dist is gitignored and the author built in
  their own checkout. I rebuilt from `e9fce12` source and verified against my
  own artifact.)
- **pak-compare:** CONFIRMED. `0.0.0.13` vs `0.0.0.12` → **0 BLOCKING, 0
  WARNING, 0 INFO** ("No structural divergences found").

## Vendor ground-truth verification (all 17, per-attribute, by UUID)

Matched each view's UUID to its vendor original in
`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/View - Set {1..4}.xml`,
then correlated the port's chosen attribute to the vendor `<Item>` carrying
that same `attributeKey` (vendor ViewDefs bundle multiple columns; the port
uses one). **All 17 match vendor per-attribute** on `isProperty=true`,
`isDynamic=true`, `dynamicCalcFunction=DISCRETE`, no numeric histogram, and
per-view `isStringAttribute`:

- 15 string properties → `isStringAttribute=true` (vendor: true). ✔
- **2 exceptions → `isStringAttribute=false`, both vendor-correct:**
  - `vSphere Cluster Admission Control Policy` / `configuration|dasConfig|admissionControlPolicyId`
    → vendor `isProperty=true, isStringAttribute=false`. ✔
  - `vSphere Cluster DRS Automation Level` / `configuration|drsconfig|vmotionRate`
    → vendor `isProperty=true, isStringAttribute=false`. ✔ (Also the known
    heuristic false-negative in the validate-time guard — the port carries the
    correct explicit shape, so the guard is not relied on here.)

## Built-pak render verification (extracted `0.0.0.13.pak`)

- **All 17** `content/reports/<view>/content.xml` ViewDefs carry
  `isProperty=true`, `isDynamic=true`, `dynamicCalcFunction=DISCRETE`, no
  `minValue`/`maxValue`/`bucketCount` numeric histogram, and per-view
  `isStringAttribute` exactly as authored (both `false` exceptions present).
- **Rendered ViewDef UUIDs == source YAML UUIDs** for all 17 (no UUID drift).
- **5 previously-fixed views unmodified** and still render DISCRETE:
  `ESXi_Host_{Hardware,Maintenance_Mode,Power_State,Versions}_vCommunity`
  (UUID `8a6d966f` etc.) + `nfnic_VIB_Vendor_Distribution` — all
  `isProperty=true` + `DISCRETE`, UUIDs intact. Not in the diff; rebuild
  preserved them.

## Corpus enumeration (author's "51 / 5 / 17 / rest numeric")

CONFIRMED. `views/*.yaml` holds **51** `data_type: distribution` views:
**22** now property+DISCRETE (**5** previously fixed + **17** this round),
**29** left numeric. The 17 fixed exactly equal the set changed by `e9fce12`.

## Left-alone set — assessed, reasoning holds

The 8 numeric ESXi Configuration 2.0 siblings (CPU cores/GHz/sockets/speed,
memory size, NIC speed/count, active storage paths) are **genuinely
numeric-range** attributes; a numeric histogram is the correct model. The
2026-07-14 comparison report's widget-by-widget table classifies all 8 as
"no delta — populate on both" (live-verified prod+devel). None is a
string/enum/boolean property masquerading as numeric. Scanned the full 29
left-numeric views: all are counts / sizes / GHz / percentages / rates /
reservations / limits / latencies / SM references — no string-property view
was wrongly left in the numeric class. The complete blast radius named in
`esxi-configuration-20-dashboard-comparison.md` (Switch Version, all Cluster
DRS/HA/DPM/Admission views, 3 Port Group security policies) is fully covered
by the fixed-17. No broken-class view is hiding in the left-alone set.

## Registry check (`knowledge/context/defects.md`)

- **DEF-010** (tracked, open, vcommunity-vsphere — Bad Network Packets SM
  divides by never-collected `net|packetsRx/Tx_summation_sum`): **still
  present, unchanged.** This build touches no super metrics; the defect lives
  in `supermetrics/`, outside this delta. Correctly untouched (tracked, ships).
- **DEF-012** (blocking, open, vcommunity-vsphere — string-property
  distributions ship as numeric histograms): **content-side shape RESOLVED by
  this build.** All 17 remaining broken views remediated and statically
  verified end-to-end (source → render → extracted pak), matching vendor
  ground truth; the full 51-view corpus is swept (22 property-DISCRETE + 29
  genuinely numeric). **Propose closure conditions — do NOT close yet.**
  DEF-012's closing criterion is *"a build carrying the fixed views renders
  live data in all previously-empty distribution widgets on devel"* — a
  browser/Playwright render proof. Per `distribution_view_no_data.md` Q1 the
  internal export endpoint **cannot** compute DISCRETE buckets for anyone, so
  static XML proof (done here) is necessary but **not sufficient**; the live
  devel render has NOT happened. Closure owes: install `0.0.0.13`/CI-built
  `1.0.0.13` on devel + Playwright pass confirming the six ESXi Configuration
  2.0 widgets and the sibling distribution widgets populate.
- No other open defect names this pak (DEF-008/009/011 closed; DEF-004 affects
  vcommunity-os).

## Findings

### WARNING
- **[CHANGELOG.md build-13 header]** gap-honesty / DEF-012 closing criterion —
  the entry states "Closes DEF-012." The criterion requires a **live devel
  render proof** that has not occurred; the content-side shape is fixed but the
  export endpoint cannot validate DISCRETE buckets. Reading "Closes" could lead
  a downstream decision to treat the blocking defect as satisfied. (Practical
  release risk is bounded: `defect-gate` reads `defects.md`, not the CHANGELOG,
  so it still refuses a `v*` tag while DEF-012 is open.) → Soften to
  "Addresses/Remediates DEF-012 (content-side shape); closure pending live
  devel render proof per the DEF-012 criterion."

### NIT
- **[views/VM Memory Limit.yaml]** pre-existing, out of this delta — attribute
  is `config|cpuAllocation|limit` (looks copy-pasted from VM CPU Limit; a
  Memory Limit distribution would show CPU limit). Numeric, not the DEF-012
  class; flagged only as an observation for a future pass, not this build.
- **[several fixed view YAMLs]** `display_name` values are attribute keys or
  `"."` (e.g. `cpu|cpuModel`, `hardware|powerManagementPolicy`, `.`) where the
  vendor uses friendly labels ("Build Numbers", etc.). Pre-existing, not
  introduced here, cosmetic — outside the shape fix.

## Build hygiene / RULE-014

- `adapter.yaml`: `version: "1.0.0"` unchanged (release line), `build_number`
  12 → 13 only. RULE-014 compliant (build-number bump, no version-line drift).
- `docs/README.md` / `docs/inventory-tree.md`: version strings 0.0.0.12 →
  1.0.0.13 — consistent with the corrected 1.0.0 release line (the prior
  "0.0.0.x" doc string was itself DEF-011 residue). No resource-kind / traversal
  change, so nothing else in the generated docs needed updating.
- CHANGELOG: accurate and thorough — lists all 17, both `isStringAttribute=false`
  exceptions, and the deliberately-left-alone 8 with a cited rationale. Only
  defect: the "Closes DEF-012" overstatement above.
- Docs parity (dim. 11): this build adds no cross-MP relationship / new
  user-visible capability — it corrects rendering of existing distribution
  views. No doc surface contradicts behavior. OK.

## If shipped as-is

The six ESXi Configuration 2.0 property-distribution widgets, `vSphere Switch
Version`, the Cluster DRS/HA/DPM/Admission distributions, and the three Port
Group security-policy distributions carry the vendor-correct DISCRETE
string/property shape and should render live data instead of "No data /
Metrics displaying 0 of N" — pending the live devel render proof that DEF-012
still requires before the defect can close and a `v*` tag can be cut.
