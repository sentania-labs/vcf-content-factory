# Framework review: this branch (4 commits)

- Date: 2026-08-26, framework-reviewer. This branch,
  reviewed at its tip (base: the tooling branch). Diff base for regression: the pre-change base.
- Area: `src/vcfops_dashboards/{loader,render,reverse}.py`,
  `src/vcfops_extractor/{extractor,reverse_local}.py`.
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 3 WARNING, 3 NIT).

## Checks re-run (independently)

| Check | Result |
|---|---|
| `PYTHONHASHSEED=0 .venv/bin/python -m pytest` | 1279 passed, 4 failed, 16 skipped. The 4 failures are all `tests/test_common_doctor.py` and fail identically at the reviewed change (environment, not this change). Matches tooling's claim. |
| Seven-package validate chain | all seven OK |
| Render regression, `PYTHONHASHSEED=0`, HEAD vs the reviewed change worktree: views XML + dashboard JSON for `content/`, `third_party/idps-planner`, a private third-party project, `content/sdk-adapters/{compliance,vcommunity-os}` | byte-identical (`cmp` on the combined JSON). `vcommunity` and `vcommunity-vsphere` clones fail to load identically on both sides (SM scope / cross-clone view refs; pre-existing, not this change). |
| Time-segment Item 0, reverse (`reverse.py`) then render, vs `reference/docs/extracted/view-time-segment/vcf-licensing-overtime-viewdef.xml` | identical after whitespace normalization (the unit test asserts exact bytes). Sibling metric columns differ only in `rollUpCount` 1 vs export 0, a pre-existing renderer choice outside this diff. |
| Full `lic/` export round trip (`reverse_local_port` on `dashboard.json` + `Views/content.xml`, then load + render) | verdict MATCH; `entries.resource[]` identical to export (three rows, display names `License Usage`, `NSX World`, `Automation World`); every View pin re-resolves to the same display name; selectFirstRow/chartViewItems/showDT/refreshContent/roundDecimals (0 and null) all carried. Resource-mode entry deltas are exactly the three documented cosmetics (`unit` null vs `""`, `maxValue` `""` vs absent, `metricUnitId` `"-1"` vs `-1`). |
| Restricted-term grep over the four commits | no hits |
| pak-compare | n/a (no builder/template change) |

## Hunt answers

1. **Time-segment.** Wire shape byte-identical to the export (test A + my
   re-run). List-only enforcement is in `loader._validate_time_segment_column`
   (`data_type != "list"` raises; test covers `trend`). All three reverse paths
   emit `time_segment:` instead of a bogus metric column. Global path: a view
   without `time_segment` renders identical bytes (corpus proof above).
2. **Resource-mode Scoreboard.** `entries.resource[]` keyed by
   (adapter, kind, name) triple cannot collide with kind mode because kind
   mode lives in `entries.resourceKind[]` (`kind_index`), a different table.
   Sharing the `License Usage` slot with the View pins is **correct on the
   wire**: the source export has one `resource:id:0_::_` (`License Usage`)
   referenced by the Scoreboard's `resourceMetrics[].resourceId` and by three
   View widgets' `config.resource.resourceId`. Verdict on empty metrics is
   PARTIAL (`_structural_key` now carries `_metric_signature`; test D).
3. **Seven drops.** Round trip proves each re-renders field-equal (table
   above). `round_decimals: null` vs absent: no YAML in `content/`,
   `third_party/`, or the sdk clones sets `round_decimals` to anything but a
   number; corpus render identical.
4. **`_WORLD_DISPLAY_NAME`.** Hard-coded map is the same shape as the
   existing `_VIEW_PIN_CONTAINER` table, so consistent. `pin.name` wins
   first in `_resolve_view_pin`. Existing pins in the corpus are
   VMWARE/{vSphere World,HostSystem} and vcfcf_compliance/ComplianceWorld,
   none in the new table; the private third-party project's dashboards carry no pins; render identical.
   The "kind-key pin never binds" claim is recorded with method, both
   dashboards' probe timeline and the resolved resourceId in
   `knowledge/context/wire-formats/dashboard_view_pin_resolution.md`.

## BLOCKING

- [`src/vcfops_packaging/deps.py:236`] authority: `knowledge/rules/` RULE-005
  (validate/audit gate must not reject good content) and the precedent at
  `deps.py:216-233` (instanced-group driver column is skipped because it
  carries no describe-cache key). `_refs_from_view` treats a `time_segment`
  column like a metric column and emits
  `MetricReference(adapter_kind=<subject>, resource_kind=<subject>,
  metric_key="Interval Breakdown")` (reproduced on the reversed reference
  ViewDef). `audit.run_dependency_audit` (`audit.py:142-155`) raises
  `AuditError` on any unknown key in every audit mode, so **every bundle
  containing a time-segment view fails to build** through
  `vcfops_packaging build` with "metric key not found in the describe
  cache: Interval Breakdown". The feature works on the standalone
  `vcfops_dashboards package/sync` path but is dead on the bundle path, which
  is the License Consumption deliverable's shipping path. Fix: in
  `_refs_from_view`, `if getattr(col, "time_segment", None) is not None:
  continue` (mirror the driver-column skip), plus a test in
  `tests/test_view_time_segment_column.py` asserting `_refs_from_view`
  yields no `Interval Breakdown` ref.

## WARNING

- [`src/vcfops_dashboards/render.py:139-171`, `tests/test_view_pin_display_name.py:71`]
  authority: reviewer doctrine (unproven == finding),
  `dashboard_view_pin_resolution.md`. `pin.name` on a **leaf** kind
  (`VMWARE/HostSystem`, name `esx01.lab`) bypasses the container redirect and
  emits `entries.resource[]` with `resourceKindKey: HostSystem` and the leaf
  `resourceKindId`. The test codifies this as intended, but the live probe
  only verified world-singleton pins by display name; a leaf pin by name is
  not evidence-backed and, if the importer also checks kind, is a new way to
  reach the stuck-deferred state the lesson
  `dashboard-import-deferred-materialization.md` describes. Fix: either mark
  it unverified in the wire doc and loader docstring, or reject `pin.name` on
  kinds present in `_VIEW_PIN_CONTAINER` until live-verified.
- [`src/vcfops_packaging/template_version.py:13`] authority: CLAUDE.md
  "After tooling changes", review dimension 9. `render.py` changed and
  `CURRENT_TEMPLATE_VERSION` is still `2026-08-24-2`. I proved the corpus
  renders byte-identical, so already-distributed zips are not functionally
  stale and I am not blocking on the stamp; but CLAUDE.md still requires the
  orchestrator to delegate a full `content-packager` rebuild of `bundles/`,
  and tooling should state explicitly (in the PR) that the bump was
  deliberately skipped because no shipped bundle's output changed.
- [`src/vcfops_dashboards/loader.py:2545-2575`] authority: wire_formats.md
  §Scoreboard resource mode (evidence widget has `selfProvider: true`).
  `metric_mode: resource` does not require `self_provider: true`; a
  resource-mode Scoreboard with `self_provider: false` renders an
  unverified shape (`selfProvider: false` + `resourceMetrics[]`). Fix: reject
  or warn in the loader until a non-self-provider example exists.

## NIT

- [`src/vcfops_dashboards/render.py:1373`] kind-mode `resourceKindName`
  emits the kind key (`NSXT World`, `CAS World`) where the export carries the
  display name (`NSX World`, `Automation World`); pre-existing, cosmetic in
  kind mode (not a binding field), surfaced by the round trip.
- Pre-existing: metric columns render `rollUpCount=1` where the export has
  `0`; outside this diff, noted so the byte-identical claim is scoped to
  Item 0 only.
- `src/vcfops_extractor/reverse_local.py:479` imports three private helpers
  from `extractor.py` mid-module; works, but the two `_parse_controls_meta`
  copies (`reverse.py`, `extractor.py`) are verbatim duplicates that will
  drift.

## If shipped as-is

A bundle manifest that includes the new time-segment view fails
`vcfops_packaging build` with a describe-cache "unknown metric: Interval
Breakdown" error; standalone dashboard sync of the same view works. No
existing bundle, dashboard, or pak changes a byte.

## Note

Untracked `knowledge/designs/dashboards/vcf-license-consumption-overview.*`
and a modified `knowledge/context/investigations/recon_log.md` were present
in the tree before this review and were not touched.

---

# Re-review 2026-08-26: fix commits on this branch

- This branch at its tip (5 fix commits on top of the
  first-pass review commit). Regression base unchanged: the pre-change base,
  fresh worktree, `PYTHONHASHSEED=0`.
- Verdict: **APPROVE** (0 BLOCKING, 1 WARNING carried, 2 NIT).

## Checks re-run (independently)

| Check | Result |
|---|---|
| `PYTHONHASHSEED=0 .venv/bin/python -m pytest` | 1283 passed, 4 failed, 16 skipped, 128 deselected. The 4 failures are the same `tests/test_common_doctor.py` environment failures as the first pass (fail identically at the reviewed change). Matches tooling's 1283 / 4 / 16. |
| `tests/test_view_time_segment_column.py::test_discrete_build_over_time_segment_view_passes_audit` run explicitly (`-m slow`, and again with `-o addopts=""`) | 1 passed both ways (0.7 s). A discrete build, audit ON, strict mode, over a time-segment view against a describe cache that knows only `cpu\|usage_average` produces a zip. |
| Seven-package validate chain, by exit code | all rc=0 |
| Render regression HEAD vs the reviewed change: views XML + dashboard JSON for `content/` (19 views / 9 dashboards), `third_party/idps-planner` (5/1), a private third-party project, sdk clones `compliance` (1/1), `vcommunity-os` (1/0), `vcommunity` (96/12) | byte-identical (`cmp` on the combined JSON). `vcommunity-vsphere` fails to load identically on both sides (cross-clone view ref `Windows Services vCommunity`, pre-existing). |
| Reverse-path tests (8 files importing `reverse_local` / `extractor` / `dashboards.reverse`) | 118 passed |
| `_parse_controls_meta` / `_trend_transformations_to_emit` definitions | exactly one each, `src/vcfops_dashboards/reverse.py:309,360`; callers `extractor.py:35,580,598` and `reverse_local.py:479,209,227` both import from `vcfops_dashboards.reverse`. The bodies deleted from `extractor.py` at the reviewed change diff clean against the surviving copy (`diff` empty). |
| Restricted-term grep over the five commits | no hits |
| pak-compare | n/a (no builder/template change) |

## Finding-by-finding closure

- **BLOCKING, deps.py time-segment audit: closed.** `deps.py:214` skips a
  column whose `time_segment` is not None before the instanced-group
  branch, mirroring the driver-column precedent. Test F1 asserts
  `_refs_from_view` yields only `cpu|usage_average`; F2 (slow) is the
  end-to-end bundle build. Both pass under my run.
- **WARNING, leaf-kind `pin.name`: closed.** `loader.py:2357-2372` rejects
  a non-empty `pin.name` when `(adapter_kind, resource_kind)` is a key of
  `render._VIEW_PIN_CONTAINER`, names the kind (`VMWARE/HostSystem`), points
  at `dashboard_view_pin_resolution.md`, and tells the author which
  container to pin instead. The wire doc gained an "Unverified" paragraph
  with the lift procedure (probe, record, remove the check). The import is
  lazy inside the branch; `render.py` imports nothing from `loader.py` at
  module level, so no cycle. The prior verbatim-pass test is replaced by
  `test_pin_name_on_leaf_kind_is_rejected` (matches kind and doc name).
- **WARNING, `metric_mode: resource` without `self_provider`: closed.**
  `loader.py:2577-2587` raises before any resource parsing when
  `self_provider` is false or absent; two parametrized negative cases added
  to `test_dashboard_scoreboard_resource_mode.py`.
- **NIT, kind-mode `resourceKindName`: closed.** `render.py:1427` now emits
  `_WORLD_DISPLAY_NAME.get(key, spec.resource_kind)`; `key` is the same
  `(adapter_kind, resource_kind)` tuple used for `kind_index`, so the lookup
  is well-formed. The binding field (`entries.resourceKind[].resourceKindKey`)
  is untouched (test asserts it). No dashboard in `content/`, `third_party/`,
  or the sdk clones references `NSXT World`, `CAS World`, or
  `LICENSE_USAGE_WORLD` (grep), and the corpus renders byte-identical.
- **NIT, duplicate `_parse_controls_meta`: closed.** One definition, both
  importers wired, bodies identical to what was removed, reverse fixtures
  unchanged (118 passed, suite total unchanged).

## Carried WARNING

- [`src/vcfops_packaging/template_version.py:14`] authority: CLAUDE.md
  "After tooling changes", dimension 9. `render.py` changed across the
  branch and `CURRENT_TEMPLATE_VERSION` is still `2026-08-24-2`. Proven
  byte-identical on every shipped bundle's source, so no distributed zip is
  functionally stale and this does not block; the PR description should say
  the bump was deliberately skipped for that reason, and the orchestrator
  still owes the `content-packager` rebuild CLAUDE.md requires.

## NIT

- [`src/vcfops_dashboards/reverse.py:157`] A live export that carries a
  genuine leaf-kind pin by name (e.g. `HostSystem` / `esx01.lab`) will now
  reverse into YAML the loader rejects. That is loud and the message is
  actionable, and such an export would itself be the probe evidence the
  wire doc asks for; noting it so `/extract` users are not surprised.
- [`src/vcfops_packaging/discrete_builder.py:851`] `datetime.utcnow()`
  deprecation warning surfaces in the new slow test; pre-existing, outside
  this diff.

## If shipped as-is

A bundle over the License Consumption content builds and audits clean;
resource-mode Scoreboards and world-singleton View pins render the
export-matching shape; an author who tries an unverified leaf pin by name
or a non-self-provider resource-mode Scoreboard gets a validation error
naming the fix. No existing bundle, dashboard, or pak changes a byte.

## Readiness as a PR on top of this branch

Ready. All five fix commits are scoped to the findings, each carries a
test, the suite and validate chain are green (doctor failures are
environmental and predate the branch), and the corpus render is
byte-identical to the pre-branch base with hash seed pinned. The only
open item is process, not code: state in the PR body that the template
version bump was skipped because no shipped output changed, and schedule
the `content-packager` rebuild CLAUDE.md requires after a `render.py`
change. Untracked `knowledge/designs/**/vcf-license-*` files and the
modified `recon_log.md` are content-side artifacts outside this review
and should be committed or excluded deliberately before the PR is opened.
