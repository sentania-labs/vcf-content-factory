# Framework Review — ResourceList `column_preset` ("name-only")

- Date: 2026-07-22
- Reviewer: `framework-reviewer` (RULE-013 blanket pre-PR gate)
- Area: `src/vcfops_dashboards/loader.py`, `src/vcfops_dashboards/render.py`
- Change (tooling): add a typed, closed-enum `column_preset` field on
  ResourceList widgets. `name-only` emits a top-level widget
  `states: [{value: <4244-byte captured ExtJS grid-state blob>, key:
  permResGrid_widget_<dashUuid>_<widgetUuid>}]`. Loader validates the
  enum and rejects it on non-ResourceList widgets. New test file
  `tests/test_resource_list_column_preset.py` (6 tests).
- Basis doc: `knowledge/context/api-surface/resourcelist_column_state_wire_format.md`
- Scope note: working tree also carries two already-APPROVED reviewed
  diffs (DEF-013 gridster clamp; select_first_row opt-out) and a
  concurrently-edited `content/dashboards/cpu_support_status.yaml`.
  Reviewed the `column_preset` addition only; content/ ignored.

## Verdict: APPROVE (0 BLOCKING)

## Checks re-run (independently)

- **Blob byte-identity** — extracted the constant from all three
  locations (wire-format doc §2, `render.py`
  `_RESOURCE_LIST_COLUMN_STATE_NAME_ONLY`, test `EXPECTED_NAME_ONLY_VALUE`).
  All three: **4244 bytes, identical**. Decoded 4× via `urllib.parse.unquote`
  → clean `o:columns=a:o:id=s:h1^hidden=b:1^width=n:100^…`; **47 `o:id=s:`
  column records**, `h15^hidden=b:0` present as the sole visible column,
  `resourceRating` present. Matches the doc's roster exactly. No
  single-character corruption of the multi-pass-encoded blob.
- **Key templating** — uses `dashboard_id` + `w.widget_id`, i.e.
  `permResGrid_widget_<dashUuid>_<widgetUuid>` — **not** the widget uuid
  twice. Verified against ground truth: the corpus dashboard
  `b6796122-…` widget `f9c1e72c-…` renders key
  `permResGrid_widget_b6796122-…_f9c1e72c-…`, byte-for-byte the doc's
  captured stateId.
- **validate chain** — all seven `vcfops_* validate` modules: **pass**.
- **tests** — new file: **6 passed**. Dashboard/render/resource/gridster/
  select_first subset: **78 passed**. Full suite: **601 passed, 4 skipped,
  0 failed** (88s).
- **Render regression (corpus)** — rendered all 7 corpus dashboards with
  the change vs. with `src/vcfops_dashboards/{loader,render}.py` stashed
  to pre-change. After removing the one intended `states` addition and
  normalizing pre-existing per-process `extModel<N>` counter ids
  (hash-seed non-determinism that exists in HEAD, identical within a
  single process, unrelated to this diff), the two renders are
  **byte-identical**. Only one widget in the entire corpus gains a
  `states` key — the one that opts in via `column_preset`. Every other
  widget is inert.

## Dimension walk

1. **Global-default / pak-specific leak (anchor `00d3382`)** — CLEAR.
   `states[]` is emitted only when `column_preset == "name-only"`, an
   opt-in per-widget YAML field defaulting to `None`. When absent, no
   `states` key is added (`"states" not in widget_obj`, test-guarded and
   confirmed by the byte-identical corpus diff). No new global default,
   coordinate shift, or hidden flag leaks onto the standalone
   content-import path. Inert unless explicitly requested.
2. **Key / label collision (anchor `6c59f6b`)** — CLEAR. The `key` is
   derived from the dashboard UUID + the widget UUID, both unique. Two
   ResourceList widgets on one dashboard get distinct keys
   (`…_<widgetA>` vs `…_<widgetB>`); the same widget across dashboards
   gets distinct keys via the dash UUID. No context-blind derivation, no
   collision.
3. **Wire-format conformance** — CLEAR. `states[]` is placed at the
   widget top level (sibling of `config`/`gridsterCoords`), exactly one
   entry, shape `{"value": …, "key": …}` — matches the doc §2 canonical
   form. `value` is the verbatim captured constant (paste, not
   re-derived per the doc's encoding note).
4. **Loader / validator correctness** — CLEAR. Two new guards run at the
   per-widget loop top level (not inside a ResourceList-only block), so
   they cover every widget type: (a) `column_preset not in
   {"name-only"}` → rejected; (b) `column_preset` on a non-ResourceList
   → rejected. Both test-covered and independently confirmed to raise
   `DashboardValidationError`. Closed enum by design — a raw-blob
   passthrough is correctly refused.
5. **Render regression vs known-good** — CLEAR (see corpus diff above).
6. **Builder / pak structure** — n/a (no builder/template change).
7. **Corpus regression** — CLEAR (validate chain + full suite green).
8. **Silent capability change / downgrade** — CLEAR. Concern probed:
   what if `dashboard_id` is `None`/empty when `states` is emitted?
   Traced: `load_dashboard` always sets `dash_id` to a validated uuid4
   or freshly mints one (`loader.py` ~1641-1647), and `column_preset` is
   only reachable through the YAML→`load_dashboard` path. So `dashboard.id`
   is never empty when `states` is emitted; the key can never degrade to
   `permResGrid_widget__<widget>` on any live path. No silent downgrade.
9. **Stale-zip discipline** — see WARNING below.
10. **Test coverage** — CLEAR. A dedicated 6-test file covers absent (no
    `states` key), present (one entry, templated key, verbatim value +
    length), and both rejection paths. The blob is copied into the test
    (not imported from `render.py`) so the test independently guards
    against silent corruption of either copy. Good.

## Findings

### WARNING
- [src/vcfops_dashboards/render.py] CLAUDE.md "After tooling changes" —
  this diff modifies `render.py`, a stale-zip trigger file, so **all
  `dist/` zips built from `bundles/` are now stale**. The change must be
  accompanied by a `content-packager` rebuild of every `bundles/`
  manifest before any zip ships. If tooling's handoff did not flag this,
  the orchestrator must schedule the rebuild. → Re-brief: flag
  content-packager rebuild.

### NIT
- [src/vcfops_dashboards/render.py:1032] `_resource_list_widget(…,
  dashboard_id: str = "")` — the `= ""` default is a latent footgun. It
  is not reachable today (the sole caller passes `dashboard.id`, always a
  validated uuid4), so no live path degrades. But a future caller that
  forgets the argument while a widget carries `column_preset` would emit
  `permResGrid_widget__<widgetUuid>` silently. Consider making the
  parameter required (no default) or asserting non-empty when `states`
  is emitted. Not blocking; documented here so it is not rediscovered
  the hard way.

## If shipped as-is

An operator authoring `column_preset: name-only` on a ResourceList gets
a dashboard that imports with the "Show Columns → Name only" default for
all first-load viewers, keyed correctly per widget; every dashboard that
does not opt in is byte-for-byte unchanged. The one caveat an operator
must remember (outside this diff's scope, but from the basis doc §5): a
viewer who later changes their own columns keeps their per-user override
— the blob sets the default, it cannot force. Only operational follow-up:
rebuild the distribution zips (WARNING above) before packaging.
