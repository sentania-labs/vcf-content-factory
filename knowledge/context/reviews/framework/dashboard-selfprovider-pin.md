# Framework review — dashboard self-provider pin wire format

- **Branch:** `fix/dashboard-selfprovider-pin-wire-format`
- **Commit:** `b1b044b` (off `main` @ `5b61f2d`)
- **Area:** `src/vcfops_dashboards/render.py`
- **Date:** 2026-07-13
- **Reviewer:** `framework-reviewer` (read-only, pre-PR gate)
- **Verdict:** **APPROVE** (0 BLOCKING; 3 WARNING, 1 NIT)

## What changed

1. **FIX (unconditional):** `_health_chart_widget` no longer hard-codes
   `"resource": []`. For a `self_provider: true` HealthChart it derives a
   container via new `_self_provider_pin_container()` (explicit `w.pin`
   preferred, else the widget's own `adapter_kind`/`resource_kind`), emits
   `resource: [{name, id: resource:id:N_::_}]`, and registers the container
   in the shared `resource_index` so `entries.resource` carries it. Signature
   gained a `resource_index` param; `_build_dashboard_obj` and the
   `resource_index` build loop updated to include HealthChart.
2. **OPTIONAL ENRICHMENT:** new `_VIEW_PIN_TRAVERSAL_SPEC` table
   (`(VMWARE, vSphere World) → "vSphere Hosts and Clusters-VMWARE-vSphere World"`)
   consulted for self-provider pinned View/ProblemAlertsList. When mapped,
   emits the spec at both `config.resource.traversalSpecId` and top-level
   `config.traversalSpecId`; when unmapped, silently keeps `""`/`null`.

## Checks re-run (independently)

| Check | Result |
|---|---|
| 7-package `validate` chain | all exit 0 |
| Targeted `tests/test_selfprovider_pin_wire_format.py` | 8 passed |
| Full suite, not-slow subset (`-m "not slow"`) | **549 passed / 4 skipped / 162 deselected** (independently reproduces tooling's claim) |
| Full suite, slow subset (162) | NOT run to completion — these are `test_publish_phase3` / `test_cli_phase4` git-heavy publish/packaging CLI tests (>9 min, timed out). **Out of the changed code path** (no `render.py` coverage). Render-relevant coverage is fully green above. |
| Render-regression (main vs HEAD, seed-pinned) | **clean — only the two intended change classes** |
| pak-compare | n/a (no builder/template change) |

### Render-regression detail

Rendered the whole repo dashboard corpus (`content/dashboards`) and the
`vcommunity` pak corpus main-vs-HEAD, `PYTHONHASHSEED=0` to suppress the
pre-existing `extModel` hash noise. Every changed byte is attributable to
exactly one of the two fixes:

- **View pins:** `traversalSpecId: ""` → `"vSphere Hosts and
  Clusters-VMWARE-vSphere World"` (and top-level `null` → same) on
  self-provider Views pinned to `VMWARE/vSphere World`. Applies on BOTH the
  standalone `content/dashboards` path and the pak path.
- **HealthCharts:** `resource: []` → `resource:[{name,id}]` plus new
  `entries.resource` slots (`vSphere World@0`, `Enterprise@1`,
  `BusinessService@2` in the vcommunity bundle).

No other diffs. The `vcommunity-vsphere` corpus fails to load identically on
BOTH base and HEAD (`unknown view 'Windows Services vCommunity'` — a
pre-existing content issue, not a regression).

## Anchor / dimension findings

### Anchor `00d3382` (global-default / pak-specific leak) — CLEAR
The `_VIEW_PIN_TRAVERSAL_SPEC` default and the HealthChart pin logic are
**unconditional** (no `owning_adapter_kind` gate, no pak flag) and were
verified to apply identically on the standalone `content/dashboards` path.
This is *not* a leak, because the injected value is not pak-specific: the
key `(VMWARE, vSphere World)` is a universal container and the spec string
is a built-in OOTB traversal spec confirmed present on any instance with the
VMWARE adapter (evidence doc §"Prerequisite check 1", `/api/auth/traversalspecs`).
`""` was itself the vendor-proven historic working shape; changing it to a
valid built-in spec string is additive and low-risk on every path.

### Anchor `6c59f6b` (key/slot collision) — CLEAR
The concern was that walking HealthChart widgets in the `resource_index`
build loop could shift `resource:id:N` references for existing View-only
dashboards. Disproven:
- The seed-pinned diff shows all `resource:id:N` / `internalId` lines are
  **pure additions** — no existing reference changed value.
- Programmatic cross-check on the HEAD vcommunity bundle: **every** widget
  resource reference (View `resourceId` and HealthChart `resource[].id`)
  resolves to a matching `entries.resource` internalId; zero dangling.
- `entries.resource` is built from the same `resource_index` the widget
  configs consume, so even if a slot's integer shifts under a different
  widget ordering, the reference and the entry move together (and the integer
  is a symbolic placeholder Ops reassigns on import). Consistency holds
  across the multi-dashboard bundle.

### Wire-format conformance — CONFORMS
Emitted HealthChart shape (`selfProvider:{selfProvider:true}` +
`resource:[{name,id}]`) and `entries.resource` block match the vendor export
values quoted in the evidence doc §HealthChart and
`widget_types_survey.md §HealthChart`.

## Findings

### WARNING 1 — the fix does NOT reach CP2's live-broken View widget
`[render.py:981-1001, _view_widget external-UUID passthrough]`
The evidence doc's hypothesis 1 target — Cluster Performance 2.0's
"vSphere Clusters" View showing "Select the widget source" — is authored as
`view: 'd8a3767e-...'` (an **external UUID**) with `self_provider: true` and
`pin: {VMWARE, vSphere World}`. `_view_widget`'s `isinstance(view, str)`
passthrough branch returns FIRST with `selfProvider:false`, `resource:None`,
`traversalSpecId:None` — silently discarding the declared `self_provider`
and `pin`. Verified against the HEAD render: that widget still emits
`selfProvider=False, resource=None`. So **this PR fixes only CP2's two
HealthCharts**; the CP2 View half remains unbound. This is pre-existing
renderer behavior (the passthrough branch predates this change), not a
regression introduced here — but the orchestrator must not label CP2 "fixed",
and the required qa-tester Playwright pass will still show that View widget
broken. Smallest correct fix (separate change): teach the external-UUID
passthrough branch to honor `self_provider`+`pin` (emit the resource object +
`entries.resource` slot even for a UUID `viewDefinitionId`), or blocked as a
content-design decision. Dimension 8 (silent capability drop, pre-existing).

### WARNING 2 — latent, uncovered self-provider HealthChart pin matrix
`[render.py:133-152 _self_provider_pin_container; 1268-1278 _health_chart_widget]`
`_self_provider_pin_container` falls back to the widget's own
`adapter_kind`/`resource_kind` and runs it through `_resolve_view_pin`, which
would **redirect a VMWARE leaf kind** (e.g. `ClusterComputeResource`,
`HostSystem` — all in `_VIEW_PIN_CONTAINER`) to `vSphere World`. It also pins
**regardless of `cfg.mode`** ("all" vs "resource"). There is no vendor
evidence for leaf-kind or `mode:"all"` HealthChart world-pinning, and no test
covers it. Not exercised by the current corpus (all self-provider HealthCharts
use `mode: resource` on already-singleton kinds — `vSphere World`,
`Enterprise`, `BusinessService` — so `_resolve_view_pin` returns them
unchanged). Not a regression (the old `resource:[]` was itself the
documented-broken shape), but a latent trap: a future self-provider HealthChart
authored on a VMWARE leaf kind, or with `mode:"all"` ("list all resources of
the kind"), would silently become world-pinned with no basis. Smallest fix:
gate the HealthChart fallback so it pins only when the config kind resolves to
itself (a world/singleton) or an explicit `w.pin` is set — keep `resource:[]`
otherwise — and add a leaf-kind / `mode:"all"` test. Dimensions 2/8/10.

### WARNING 3 — stale dist zips not flagged
`render.py` was modified, which per CLAUDE.md "After tooling changes" makes
**all distribution zips containing self-provider dashboards stale** (the
dashboard JSON wire output genuinely changed — verified in the render
regression: the vcommunity bundled dashboards now emit different
`traversalSpecId` and HealthChart `resource`). The commit message does not
flag a `content-packager` rebuild. Fix: before shipping, the orchestrator
delegates `content-packager` to rebuild every affected bundle in `bundles/`.
Dimension 9.

### NIT — nondeterministic `extModel` widget-item ids
`[render.py:1095]` `id: f"extModel{abs(hash(widget_id)) % 100000}-{seq}"` uses
Python's `hash()` (PYTHONHASHSEED-randomized), so widget-item ids differ
run-to-run. Pre-existing (present on base), out of scope for this change, but
contradicts the deterministic-envelope-uuid intent one function over. Noted
only.

## If shipped as-is
The two HealthCharts on Cluster Performance 2.0 (and the self-provider View
pins across the vcommunity + factory-native corpus) gain their container
binding — but **CP2's "vSphere Clusters" View widget still shows "Select the
widget source"** because it is an external-UUID passthrough the fix cannot
reach (WARNING 1); and any bundle shipped without a `content-packager` rebuild
carries stale dashboard JSON (WARNING 3). No regression to existing
content: View-only dashboards render byte-identical apart from the intended
`traversalSpecId` enrichment.

---

## ADDENDUM — 2026-07-13 — review of follow-up commit `d72690a`

- **Commit reviewed:** `d72690a` (child of `b1b044b`) — "honor self_provider+pin
  on external-UUID View passthrough; gate HealthChart implicit leaf-kind pin".
- **Claims:** resolves WARNING 1 (external-UUID passthrough silently dropped
  self_provider+pin) and WARNING 2 (implicit leaf-kind HealthChart world-pin).
- **Scope of diff:** `src/vcfops_dashboards/render.py` (only
  `_self_provider_pin_container` + `_view_widget`) and
  `tests/test_selfprovider_pin_wire_format.py` (+5 cases). Nothing else touched —
  confirmed the diff does what it claims and no more.

### Checks re-run (independently)

| Check | Result |
|---|---|
| 7-package `validate` chain | all exit 0 |
| `tests/test_selfprovider_pin_wire_format.py` | 13 passed |
| Buildkit isolated-build (`tests/managementpacks/test_buildkit_isolated_build.py`) | 4 passed |
| Full suite, not-slow (`-m "not slow" -n auto --dist=loadgroup`) | **554 passed / 4 skipped** (= prior 549 + 5 new) |
| Full CI-style suite (`-m "" -n auto`) | timed out >9m40 on the slow publish/packaging CLI tests — same out-of-path set the prior review hit; render-relevant coverage fully green above |
| Render-regression, factory-native corpus (`content/dashboards`), base `b1b044b` vs HEAD `d72690a`, `PYTHONHASHSEED=0` | **byte-identical** (0 diff) — no drift on the standalone content-import path |
| Render-regression, vcommunity CP2, base vs HEAD | exactly one intended delta (below) |
| Byte-compare CP2 "vSphere Clusters" widget, HEAD vs vendor export | binding fields match; 2 secondary fields deviate (WARNING A) |

### Per-warning verdict

**WARNING 1 — RESOLVED.** The `isinstance(view, str)` early-return that emitted
`selfProvider:false`/`resource:None` is gone; both branches now share one
pin-resolution path (`view_def_id = view if isinstance(view, str) else view.id`,
then the common `if w.self_provider and w.pin` block). Independently rendered the
actual `content/sdk-adapters/vcommunity-vsphere` CP2 dashboard and byte-compared
its "vSphere Clusters" widget (`view: d8a3767e`, self_provider, pin VMWARE/vSphere
World) to the vendor export
(`reference/references/vmbro_vcf_operations_vcommunity/.../Cluster Performance 2.0.json`).
All **load-bearing binding fields match the vendor exactly**:
`selfProvider.selfProvider:true`; `resource.resourceId "resource:id:0_::_"`;
`resource.traversalSpecId "vSphere Hosts and Clusters-VMWARE-vSphere World"`;
`resource.resourceName "vSphere World"`;
`resource.resourceKindId "002006VMWAREvSphere World"`;
`viewDefinitionId d8a3767e`; and `entries.resource[0]` byte-for-byte. The
`resource.id "Ext.vcops.chrome.model.Resource-1"` (vendor: `-140`) is the
placeholder Ops reassigns on import (per the render.py comment, any positive int).
The base-vs-HEAD CP2 delta is exactly this one widget going
`selfProvider:false/resource:null` → the vendor-shaped pin; `entries.resource` is
**unchanged** (the View reuses the vSphere World slot the two HealthCharts already
registered — no slot shift; anchor `6c59f6b` clear).

**WARNING 2 — RESOLVED.** `_self_provider_pin_container` now returns the implicit
fallback only when `resolved_kind == cfg_resource_kind` — i.e. the declared kind
already resolves to itself (a world/singleton). Verified against
`_VIEW_PIN_CONTAINER` (render.py:69-77): it holds only VMWARE **leaf** kinds
(HostSystem, VirtualMachine, Datastore, ClusterComputeResource, Datacenter) → all
redirected to vSphere World, so the gate now suppresses their implicit world-pin;
`vSphere World`/`Enterprise`/`BusinessService` are absent from the table, fall to
the singleton convention `(kind,kind,kind)`, so `resolved_kind == cfg_resource_kind`
and the gate passes. Confirmed the corpus self-provider HealthCharts still pin: the
two CP2 vSphere-World HealthCharts render **byte-identical** at base and HEAD
(`resource:[{name:"vSphere World", id:"resource:id:0_::_"}]`). New tests cover
leaf-kind `mode:resource` no-pin (stays `resource:[]`), leaf-kind `mode:all` no-pin
(mode-independent), and leaf-kind WITH explicit pin (still binds) — all green.
Anchors `00d3382`/`6c59f6b` clear on the standalone path: the factory-native
corpus is byte-identical base-vs-HEAD, so the gate is inert everywhere except the
one intended vcommunity widget.

### New finding

**WARNING A — the fixed widget deviates from the vendor known-good on two
secondary fields; the new test mislabels the deviation as "vendor shape".**
`[render.py:1029,1037-1039,1058 _view_widget; tests/test_selfprovider_pin_wire_format.py:test_external_uuid_passthrough_with_pin_emits_vendor_shape]`
Byte-compare of the emitted "vSphere Clusters" config vs the vendor CP2 export
shows two fields that do NOT match the known-good reference:

| field | renderer (HEAD) | vendor CP2.json |
|---|---|---|
| `config.traversalSpecId` (top-level) | `"vSphere Hosts and Clusters-VMWARE-vSphere World"` | **`null`** |
| `config.refreshContent.refreshContent` | `true` | **`false`** |

(A third, `config.selectFirstRow.selectFirstRow` renderer `true` vs vendor `false`,
is a **pre-existing global** renderer convention on every View widget — out of
scope for this commit; noted as NIT below.) These two deltas are **inherited from
the already-approved `b1b044b` internal-ViewDef path**, not newly invented here —
`d72690a` merely routes the external-UUID widget through the same block. They are
**not proven to corrupt import/render**: the *binding* field is the nested
`resource.traversalSpecId`, which matches the vendor exactly, and the wire-format
doc reports the vendor format imports FINISHED. So this is a fidelity gap, not a
break — **WARNING, not BLOCKING.** Two concrete problems remain to hand back:
  1. The wire-format doc
     `knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md`
     lines 60-71 is **factually wrong**: it shows the vendor top-level
     `traversalSpecId` as the spec string ("at both sites"); the actual vendor
     JSON has top-level `traversalSpecId: null`. `b1b044b` implemented to the
     wrong doc claim.
  2. `test_external_uuid_passthrough_with_pin_emits_vendor_shape` asserts
     top-level `traversalSpecId == "vSphere Hosts and Clusters-..."` and its
     docstring claims "the vendor's own CP2 export does exactly this" — **false**
     for the top-level field and for `refreshContent`. The test therefore codifies
     non-vendor bytes AS the vendor shape and will actively defend the drift.

Smallest correct fix (a follow-up, does not block this commit's two RESOLVED
verdicts): for a self-provider View, emit top-level `config.traversalSpecId: null`
and `refreshContent: false` to match the vendor (the nested `resource.traversalSpecId`
carries the binding); correct the two test assertions + docstring; and fix
wire-format doc lines 60-71 so the vendor column reads `null` top-level. Dimension 3
(wire-format drift from known-good reference) + Dimension 10 (test asserts a false
ground truth).

### Carry-forward

**WARNING 3 (stale dist zips) — STILL OPEN.** `render.py` changed again and the
vcommunity CP2 dashboard wire output genuinely changed (the vSphere Clusters
widget now emits a pin). Per CLAUDE.md "After tooling changes", any dist bundle
containing vcommunity-vsphere dashboards is stale. The commit message does not
flag a `content-packager` rebuild. Orchestrator must rebuild affected bundles
before shipping. Dimension 9.

**NIT (carried) — `selectFirstRow: true`** is emitted on every View widget while
the vendor CP2 uses `false` throughout; and `extModel` widget-item ids remain
`hash()`-nondeterministic. Both pre-existing, global, out of scope for this commit.

### Addendum verdict

**APPROVE** (0 BLOCKING). WARNING 1 RESOLVED, WARNING 2 RESOLVED. One new
non-blocking **WARNING A** (secondary-field wire drift + a test/doc that
misrepresent the vendor bytes) and carry-forward WARNING 3 (stale zips) to hand
back to the orchestrator.

**If shipped as-is:** CP2's "vSphere Clusters" widget now binds to vSphere World
(the "Select the widget source" symptom is addressed) and the corpus HealthCharts
keep their pins — but the widget's top-level `traversalSpecId`/`refreshContent`
carry non-vendor values (harmless-but-unproven, and the guard test falsely calls
them vendor-shaped), and any vcommunity dist zip shipped without a
`content-packager` rebuild carries stale dashboard JSON.

---

## ADDENDUM 2 — 2026-07-13 — review of follow-up commit `8e44ba9`

- **Commit reviewed:** `8e44ba9` (child of `d72690a`) — "View widget pin
  traversalSpecId only lives at the nested resource site, not top-level".
- **Claim:** resolves the new WARNING A from ADDENDUM 1 — top-level
  `config.traversalSpecId` unconditionally `null` and `refreshContent`
  unconditionally `false` on every View branch (spec-string enrichment retained
  at the nested `config.resource.traversalSpecId` only); the 5 tests corrected to
  real vendor values; the wire-format doc corrected with a dated CORRECTION block.
- **Diff scope (verified):** `src/vcfops_dashboards/render.py` (`_view_widget`
  only — `refresh_content` / `top_level_traversal_spec_id` locals removed,
  top-level `traversalSpecId: None` + `refreshContent: false` hardcoded; plus a
  `_VIEW_PIN_TRAVERSAL_SPEC` comment update), the wire-format doc, and the test
  file. Nothing else. Confirmed no dangling variable references after the removals
  (only `resource` + `self_provider_flag` remain in scope).

### Checks re-run (independently)

| Check | Result |
|---|---|
| 7-package `validate` chain | all exit 0 |
| `tests/test_selfprovider_pin_wire_format.py` + `test_external_view_passthrough.py` + buildkit isolated-build | **23 passed** (13 + 6 + 4) |
| Full suite, not-slow (`-m "not slow" -n auto --dist=loadgroup`) | **554 passed / 4 skipped** |
| CP2 "vSphere Clusters" re-render vs vendor bytes | top-level + refreshContent now MATCH vendor (below) |
| Render-regression, factory-native corpus (`content/dashboards`), `d72690a` vs HEAD `8e44ba9`, `PYTHONHASHSEED=0` | 4 self-provider Views changed exactly as intended (below); nested binding preserved |

### Per-item verdict

**Item 1 — top-level `config.traversalSpecId` → `null` unconditionally: RESOLVED.**
Independently re-rendered the actual vcommunity CP2 "vSphere Clusters" widget:
top-level `traversalSpecId` is now `null`, while the nested
`config.resource.traversalSpecId` retains the spec string
`"vSphere Hosts and Clusters-VMWARE-vSphere World"` — byte-matching the vendor
export. The binding field (nested) is preserved; only the erroneous top-level
duplicate was removed.

**Item 2 — `refreshContent` → `false` unconditionally: RESOLVED.**
The re-rendered CP2 widget now emits `refreshContent.refreshContent: false`,
matching the vendor. Applies to both branches (self-provider+pin and not).

**Item 3 — test assertions/docstrings corrected to vendor: RESOLVED.** Verified
the diff genuinely flips the assertions (not merely re-passes): the with-pin test
now asserts `config.traversalSpecId is None` and
`refreshContent.refreshContent is False` (was `== spec-string` / `is True`), and
still asserts the nested `config.resource.traversalSpecId == "vSphere Hosts and
Clusters-VMWARE-vSphere World"` (line 257) so the binding remains guarded.
Docstrings rewritten to cite the real vendor bytes (widget id
`46a74d94-9562-4532-b54b-9a7274406b8f`). 13/13 green.

**Item 4 — wire-format doc corrected: RESOLVED.** `dashboard_selfprovider_pin_wire_format.md`
now carries a dated **CORRECTION (post-framework-review, 2026-07-13)** block:
vendor "working" top-level `traversalSpecId` changed `spec-string` → `null`, the
old "two places" prose retained but explicitly marked "Original (incorrect
characterization — superseded", pointing at the actual JSON. Reviewable and
non-destructive (codify, don't accumulate).

### Render-regression characterization (`d72690a` → `8e44ba9`)

Factory-native corpus: **4 self-provider pinned Views** each change on exactly two
lines — top-level `traversalSpecId: "vSphere Hosts and Clusters-..." → null` and
`refreshContent: true → false`. The nested `config.resource.traversalSpecId`
spec-string survives in all 4 (grep-confirmed, 4 occurrences) — binding intact.
No other bytes move. Same delta on the vcommunity CP2 widget. This is the intended
fix and matches the vendor on both the standalone content-import path and the pak
path (anchor `00d3382` clear — the change is unconditional and global, a correction
toward vendor truth, not a pak-specific leak).

### Carry-forward / still open

**WARNING 3 (stale dist zips) — STILL OPEN, now BROADER.** This commit changes the
rendered wire output of **4 factory-native `content/dashboards` dashboards** (the
self-provider pinned Views) in addition to vcommunity CP2. Any dist bundle
containing those dashboards is stale. The commit message does not flag a
`content-packager` rebuild. Orchestrator MUST rebuild affected `bundles/` before
the PR ships. Dimension 9.

**NIT (carried) — `selectFirstRow: true`** still emitted on every View widget while
vendor CP2 uses `false` throughout. Pre-existing global renderer convention,
explicitly out of scope for this fix (WARNING A only cited the two now-fixed
fields). Noted for a future sweep, not a blocker.

### Addendum 2 verdict

**APPROVE** (0 BLOCKING). All four items of the WARNING A fix are RESOLVED and
independently verified against the vendor bytes; the wire-format doc and tests no
longer assert a false ground truth. Only carry-forward WARNING 3 (stale zips —
now broader) and the pre-existing `selectFirstRow` NIT remain to hand back.

**If shipped as-is:** CP2's "vSphere Clusters" widget and the 4 factory-native
self-provider Views now emit the exact vendor wire shape (top-level
`traversalSpecId: null`, `refreshContent: false`, spec string only at the nested
resource site) — the pin binds and the config matches the known-good export. The
only outstanding action before the PR is a `content-packager` rebuild of every
bundle that carries these dashboards, since their JSON changed.
