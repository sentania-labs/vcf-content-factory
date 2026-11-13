# Framework review: view schema fidelity (2026-11-12)

- **Branch:** `tooling/view-schema-fidelity`, base `origin/main` `285e156`.
  Commits `11828fc` (code + tests), `0fe760c` (docs), `8eafaf6` (view-author
  prompt + content-model skill).
- **Area:** `src/vcfcf_core/dashboards/loader.py`,
  `src/vcfcf_core/dashboards/render.py`; tests
  `tests/test_view_schema_fidelity.py` (new), `tests/test_view_column_sort.py`,
  `tests/test_view_subject_filter.py`; docs under `knowledge/context/`.
- **Verdict:** CHANGES REQUESTED (2 BLOCKING, 5 WARNING, 6 NIT).

## Checks re-run

| Check | Result |
|---|---|
| Render regression, author's harness run against an `origin/main` `src/` extracted with `git archive` and against the branch: `content/views`, `third_party/idps-planner/views`, the main checkout's `content/sdk-adapters/compliance/views` (the only registered pak with views), `tests/fixtures/views/*`, the 189 old-schema importer YAMLs; each view plain and with the SDK owning-SubjectType injection, each directory as one multi-view document, every dashboard | 511 files, `diff -r` **identical**. One load error, the same on both sides (an old-schema importer YAML, TRANSFORM_EXPRESSION with no expression). No view YAML anywhere else in the tree except `knowledge/context/attic/` |
| Test suite, branch vs `origin/main` (full tree from `git archive`) | branch 14 failed / 3763 passed; base 14 failed / 3638 passed. **Same 14 failure names** (`jmespath` not installed, doctor venv tests, and real-repo packaging validate tests that depend on them). 125 new tests pass |
| Seven-package validate chain (`PYTHONPATH=src`) | all seven exit 0 |
| Round trip (`port_eval/scripts/roundtrip.py`) | 183 / 189 zero difference. The 6 are 5 list views with an inert buckets-control and 1 empty `preferredUnitId`, as the author described |
| Property **order** check (my own script; the round-trip comparator ignores order) | every column Item, the metadata, pagination and attributes-selector controls, the top-level element sequence and the control sequence match the source for all 183. Only the buckets-control differs (see N1) |
| Loosened-rule evidence, recounted from the author's cited corpora (`vcommunity_pr_recon/base_views` 851 ViewDefs, `b818` 778, vCommunity 0.8.1 189) | LESS_THAN 56, CONTAINS 36, NOT_CONTAINS 93, EXISTS 6, NOT_EXISTS 2 (9.1.1 only, value `0`); transforms LAST/SUM/MAX present. String-only `redBound` with `ascendingRange`: true in 68 / 54 / 22 columns, absent in 1 / 0 / 2, false nowhere. Several sorted columns (up to 17 in one list view), sort on distribution views and on instanced-group drivers: present. **No sort on a trend column anywhere.** All three loosenings are backed by evidence |
| `sdk_builder.py` / buildkit path | `sdk_builder` calls `render_view_def_fragments`, which the harness's owning mode exercises: compliance views identical. The buildkit's import rewrite `from \.loader import \(` still covers the new `_COLUMN_OMITTABLE, _USAGE_ORDER` import (it sits inside the existing parenthesised block) |
| Callers of changed signatures | No signature changed. New dataclass fields are appended with defaults (`ViewColumn`, `BucketsConfig`, `SubjectFilterCondition.string_metric`, `ViewSubject.types`, `ViewDef`). Positional `ViewSubject(ak, rk)` in `reverse.py:305,557` is unaffected. No `asdict`/`fields` introspection of view types anywhere in `src/`. The migrator imports only `vcfcf_core.extractor.extractor`, `common.dep_walker` and `supermetrics.crossref`, none of them touched |

The defaults hold. A view that sets none of the new fields renders byte-identically
on every output path: standalone content-import, multi-view document, dashboard
bundle, and the SDK pak with owning injection. Nothing pak-local leaks onto
the global path (anchor `00d3382`). No key is derived (anchor `6c59f6b`).

## BLOCKING

### B1. `omit: [transformation]` on a trend column drops the view's TREND/FORECAST stack

`loader.py:1179-1185` (`_validate_column_omit` conflicts) and
`render.py:898` + `render.py:976`.

On a trend view the column's `transformations` Property is the view-level
stack (`_xml_transformations_block(view)`, NONE/TREND/FORECAST). `omit:
[transformation]` passes validation on a trend column, because the conflict
check only looks at the column's own `transformation`/`percentile`/expression
fields, which a trend column never sets. `_drop_omitted` then removes the
stack from that column. Probe: a trend view with `transformations: [NONE,
TREND, FORECAST]` and `omit: [transformation]` on its column loads, and the
render has no `transformations` Property at all.

Authority: none of the 586 trend columns in the three corpora (287 / 269 /
30) lacks `transformations`. This is the doc's own contract
(`view_fidelity_wire_format.md` §Contract: "an `omit:` entry that contradicts
a field the YAML also sets" is a load error), and the view-level
`transformations:` is silently overridden for that column. It also hits
the brief's target: `omit:` producing an unevidenced ViewDef by dropping a
Property the view type needs.

**Fix:** in `_validate_column_omit`, reject `transformation` when
`self.data_type == "trend"` ("trend columns take the view-level
transformations list; no export has a trend column without one"). Add a
negative test. Update the `omit:` table row in the wire doc.

### B2. `additional_columns` are invisible to every dependency walker, and the literal super-metric form is accepted anyway

`loader.py:1223` (`_validate_additional_column`), with the walkers
`src/vcfcf_packaging/discrete_builder.py:133` (`_resolve_view_deps`),
`src/vcfcf_core/common/dep_walker.py:315` and `:668`,
`src/vcfcf_core/packaging/deps.py:268` (`_refs_from_view`) and
`src/vcfcf_core/packaging/audit.py:487` (staged-bundle XML walker,
`attributeInfos` only).

The loader rejects `supermetric:"<name>"` and bare `sm_<uuid>` in an
additional column. The reason it gives, in the code comment and in the wire
doc §1, is that "the dependency walkers only scan `columns:`, so the super
metric would not be bundled". It then accepts `Super Metric|sm_<uuid>`,
which has exactly the same problem. `discrete_builder._resolve_view_deps`
auto-bundles a view's super metrics by scanning `view.columns` for
`sm_<uuid>`, so a discrete release of a view whose only super metric sits in
an additional column ships without it. `dep_walker` (the live pre-flight,
also the migrator-facing walker) misses it. So does the packaging audit.
Nothing reports the gap. The column renders blank on the target (RULE-001 /
RULE-002 posture: an unbundled dependency is silent corruption). It also
puts a raw UUID in content YAML, against the cross-reference convention
("by exact name, never raw UUID", CLAUDE.md §Cross-references,
`vcfops-project-conventions` §Cross-reference syntax).

**Smallest fix:** reject every super-metric form in `additional_columns`: a
case-insensitive `Super Metric|` prefix, or any `sm_<uuid>` substring, with
an error that names the file and the field. Update wire doc §1 to match.
(Supporting super metrics there would mean name resolution in the renderer
plus all four walkers. That is a bigger change, and a port that needs it is
one of the 189, not the factory's own content.) See W2 for the built-in
metric half of the same gap.

## WARNING

### W1. Additional columns silently ignore two time-point fields

`loader.py:1240-1256`, the `stray` list in `_validate_additional_column`.

`metric_to_relate_with` is rejected, but `localized_metric_to_relate_with`
and `operator_to_relate_with` are not, and the renderer never emits them on
an additional column. Probe: both load without error and vanish from the
render. This breaks the stated requirement that a field the renderer cannot
honour is a load error. **Fix:** add both to the `stray` tuple and add a
parametrised negative test over every `ViewColumn` field the
additional-column renderer does not read.

### W2. Built-in metric keys in `additional_columns` skip the describe-cache audit and the live pre-flight

`deps.py:268`, `audit.py:487`, `dep_walker.py:315` iterate
`view.columns` / `attributeInfos` only.

A typo'd or policy-disabled metric in an additional column passes every gate
and renders blank. Subject-filter keys had the same blind spot and were
closed for it (issue #72, cited at `deps.py:307`). The branch creates this
new metric-reference surface, so it should close the gap. **Fix:** in
`_refs_from_view` and `extract_refs_from_views`, iterate
`getattr(view, "additional_columns", [])` the same way as `columns`. In
`audit.py`, also walk `metadata/distributionAdditionalColumns`. Add one test
per walker.

### W3. Fixed-mode `calc_function` is emitted unvalidated

`render.py:410` emits it, after `loader.py:1391` / `:1407`.

Fixed mode now emits `dynamicCalcFunction` whenever `calc_function` is
written, and accepts any string. Probe: `calc_function: BOGUS` with
`dynamic: false` loads and renders. Every fixed buckets-control in the
three corpora (73 / 72 / 33) carries `SIMPLEMAXMIN` and nothing else. The
dynamic path's lack of a vocabulary check is older than this branch. The
fixed-mode emission is new. **Fix:** when `not b.is_dynamic and
b.calc_function_set`, require `SIMPLEMAXMIN`, the rule `ranges` already
applies. Optionally fail-close dynamic mode to DISCRETE / SIMPLEMAXMIN /
LOGMAGNITUDE, the values seen.

### W4. `usage:` can drop a surface that same-repo content depends on

`loader.py:1300`, with the cross-reference checks in `Dashboard.validate`
(`loader.py:2409`).

`usage: [report, content]` on a view that a dashboard View widget in the
same content set references loads cleanly. What the product does with a
dashboard widget whose view lacks `<Usage>dashboard</Usage>` is unverified.
`details`-only is also accepted, although no corpus view has it (the
subsets seen are d/r/c, d/c, r/c). **Fix:** in `Dashboard.validate`, error
when a referenced view's `usage` excludes `dashboard`. Restrict `usage` to
supersets of the evidenced subsets, or document the remaining exposure. The
report-side check can be a follow-up, since the reports loader is out of
scope.

### W5. `render.py` changed: CLAUDE.md requires a full rebuild, and nothing flags it

CLAUDE.md §"After tooling changes" says that a change to
`src/vcfcf_core/dashboards/render.py` makes every distribution zip stale,
and that a `content-packager` rebuild of every `bundles/` manifest is
"Not optional". None of the three commits or the docs flag it. The
regression shows that rendered output for every existing view and
dashboard is unchanged, so the rebuild should produce zips with identical
content. That makes it a cheap confirmation, not a waiver. No
`CURRENT_TEMPLATE_VERSION` bump is needed or wanted: templates are
untouched and distributed bundles are not wrong, so a bump would tell
operators their bundles are stale when they are not.
**Fix:** the orchestrator delegates the rebuild, and the PR body states
"render output unchanged (511-file regression); rebuild run; no template
version bump, by design".

## NIT

- **N1.** `view_fidelity_wire_format.md:26` says "Property order inside a
  Control or an Item follows the vendor exports for every new Property".
  Item order does match: I checked it, and the round-trip comparator
  ignores order. The buckets-control does not. Vendor order is
  `dynamicCalcFunction, isDynamic, isSum` and `bucketCount` first in
  dynamic mode, while the render keeps the historical `isDynamic` first and
  puts `bucketCount` after `dynamicCalcFunction`. The product reads
  Properties by name, so this is harmless. Reword the line to "column Items
  and the metadata control follow vendor order; the buckets-control keeps
  its historical order".
- **N2.** Every error raised from `ViewDef.validate()`, which covers all
  the new fidelity rules, names the view and the field but not the file.
  `load_all` does not add the path. Probe: `view 'Probe' column 'CPU':
  use_symptom_thresholds only accepts false...`. This was already true of
  `validate()` before the branch, but the branch adds about 40 new
  messages. **Fix:** in `load_view` (`loader.py:3682`), catch
  `DashboardValidationError` from `v.validate(...)` and re-raise it with a
  `{path}: ` prefix. Existing `match=` tests keep passing because they use
  `re.search`.
- **N3.** Previously ignored keys now render. `count:` on a `dynamic: true`
  buckets block and `calc_function:` on a fixed one were silently dropped
  before and are now emitted. No repo YAML has either (checked), but an
  admin's clone might. The §Contract line is literally true, since it is
  about absence. Add one sentence there, and in the PR body, naming these
  two keys as the only render change for YAML that already existed.
- **N4.** The buildkit vendors `loader.py`/`render.py`, and pak CI runs
  published kit 1.0.28, so a bundled SDK-pak view that uses any new field
  fails pak CI until the next kit is cut. Past render/loader changes did not
  bump the kit per commit, so this is not a version finding. But the
  view-author prompt now points SDK-adapter view authoring at these fields
  without that caveat. Add one clause to `view-author.md` ("SDK-adapter
  paks need buildkit > 1.0.28") or cut the kit with the PR.
- **N5.** `buckets.ranges` checks `start < end` per range but not order or
  overlap: `[{0,50},{10,20}]` loads. **Fix:** require ascending,
  non-overlapping ranges, or state that they are passed through unchecked.
- **N6. Follow-up issue, files not touched by the branch:** three importer
  comments now state something false. `src/vcfcf_core/extractor/extractor.py:541-543`
  and `src/vcfcf_core/dashboards/reverse.py:510-513` (the latter also
  "the validator which rejects ascending_range in this configuration") say
  the forward renderer suppresses `ascendingRange` on a string-only red
  bound. It no longer does. `reverse_local.py:403-405` has the same
  suppression logic. The behaviour is still safe: the importers drop the
  flag and the YAML renders without it. Only the comments, and the lost
  round-trip fidelity, need the importer pass DEF-019 already tracks.

## Judged acceptable

- **Third-party content.** Code comments and the wire doc cite source-pack
  view titles ("ESXi Network Interfaces", "VM Disk Latency Distribution",
  "VM Shares by RP", "vSphere Switch Version", and others) as evidence
  pointers only. No definition, metric list, filter or description is
  reproduced. The wire-doc snippets use generic VMWARE keys and say they
  were composed for the doc. `tests/test_view_schema_fidelity.py` is
  synthetic: "Fidelity Probe", generic keys, a fixed fake UUID. The
  pre-existing `tests/fixtures/views/vcommunity_shapes_*` are not in this
  diff. Acceptable.
- **The three loosenings.** Sort (several columns, distribution, instanced
  driver/member), `ascending_range: true` on a string-only red bound, and
  the comparators/transforms are each backed by the cited corpora (counts
  above). Every input rejected before the branch for lack of evidence is
  still rejected: trend sort, sort beside a time segment,
  `ascending_range: false` on a string red bound, BETWEEN / MEDIAN,
  `use_symptom_thresholds: true`. The changed expectations in
  `test_view_column_sort.py` and `test_view_subject_filter.py` move to
  values that are still invalid. The tests were not weakened.
- **Render-side `ascendingRange` change.** The suppression branch was
  reachable only through input the loader used to reject. No caller builds
  a `ViewColumn` with that combination and renders it directly.
- **Group-by and the owning SubjectType.** `render_view_def_fragments`
  inserts the owning SubjectType before `<SubjectsGroupBy>`, and a test
  covers it (`test_owning_subject_lands_before_group_by`). The World
  injection is unchanged, as stated. The doc's analysis of why it has no
  opt-out is accurate and appropriately hedged.
- **Key collisions.** `top_n` and `group_by` also exist as dashboard-widget
  keys in the extractor (`extractor.py:1016`, `:1087`), but in a different
  file type and schema, so there is no shadowing. The new view keys do not
  collide with existing view keys.

## If shipped as-is

An author could ship a trend view with a column that has no trend/forecast
transformations (B1), or a distribution view whose additional super-metric
column ships without its super metric and renders blank, while every gate
stays green (B2). Existing content is unaffected.
