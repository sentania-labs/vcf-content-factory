# Framework review: summary dashboard tooling (2026-08-25)

This branch, 9 commits on `main`, 7 touching
`src/vcfops_dashboards/{loader,render,cli,summary_bind,ui_client}.py` and
`src/vcfops_managementpacks/sdk_builder.py`.

Verdict: **CHANGES REQUESTED** (1 BLOCKING, 6 WARNING, 4 NIT).

## Checks re-run (independently)

- Seven-package validate chain: all rc=0.
- Test suite (pytest from the scratchpad debs): 1142 passed, 7 failed,
  16 skipped. The 7 failures are the same doctor/jmespath set as the
  committed baseline. New test files: 75 passed (tooling claimed 77).
- Render regression: `content/` rendered from a `main` worktree and from
  HEAD with `PYTHONHASHSEED=0` is byte-identical. Without a fixed seed two
  HEAD renders differ only in `extModel<hash>-<n>` ids; that is
  pre-existing on `main` (`render.py:1242`, tracked in
  `knowledge/context/defects.md:882`) and the new widgets do not touch it.
- pak-compare: n/a (no pak built; `dashboards.properties` emission checked
  by test `test_bound_dashboard_emits_properties`).
- Wire shapes: AlertVolume config key set and Section config/height match
  `reference/docs/extracted/dashboard-widgets/qa-9.2.0-export-*.json`.
- `resourceKindId` formula checked against three captured
  `getResourceKindList` responses in the session scratchpad (three captured responses,
  adapter-kind lengths 4..32): zero mismatches.

## BLOCKING

1. `src/vcfops_dashboards/summary_bind.py:105-113` (`_find_kind_entry`).
   Matches entries on keys `id`, `resourceKindKey`, `key`. The live
   `getResourceKindList` response (every entry in all three captures)
   carries `resourceKindId`, `resourceKind`, `adapterKind`, `name`,
   `resourceKindTemplate`; none carries `id`/`resourceKindKey`/`key`.
   On a real instance every plan hits `ERROR: resource kind ... not found`
   and `bind-summary` never writes anything. The unit fake
   (`tests/test_dashboard_summary_for.py:158-168`) encodes the same wrong
   keys, so the suite is green while the feature is dead. Authority:
   captured wire samples; `summary_dashboard_assignment.md` only names
   `resourceKindTemplate`, and the entry key names were never committed
   (RULE-015 gap; a redacted sample belongs under
   `reference/docs/extracted/`).
   Fix: match `entry.get("resourceKindId") == plan.resource_kind_id`
   (optionally `entry.get("resourceKind") == plan.resource_kind` as the
   fallback), and rebuild the FakeUI fixture from the captured shape.

## WARNING

1. `loader.py:2418-2424` + `sdk_builder.py:1997`. `summary_for` is stored
   with only the outer `.strip()`; `"VMWARE : VirtualMachine"` passes
   validation (tokens are stripped for the check) but is written raw into
   `dashboards.properties`. The installer splits on `:` without trimming
   and computes a resourceKindId containing spaces, binding nothing,
   silently. `bind-summary` strips and would work, so the two routes
   diverge. Fix: store the normalized `f"{ak}:{rk}"`.
2. `loader.py:2444` (`load_all`) / `sdk_builder.py:1997`. Two dashboards
   with the same `summary_for` are accepted. In a pak both lines are
   emitted and the installer's directory iteration decides the winner;
   in `bind-summary` the second plan overwrites the first and orphans
   its template. Fix: reject duplicate `summary_for` targets across a
   dashboards set (loader or builder).
3. `loader.py:2350` + `render.py:_section_widget`. Section `x` is
   author-controlled while `w` is forced to 12, so `coords: {x: 5}`
   renders `{x:5, w:12}`, overflowing the 12-column grid (the exact
   failure class of anchor `00d3382`); every observed Section is `x: 1`
   (`dashboard_widgets_alertvolume_section_viewdetails.md` §3). A data
   widget sharing a Section's row is likewise accepted and silently
   belongs to no Section. Fix: force `x: 1` (or reject `x != 1`) and
   reject non-Section widgets on a Section's row.
4. `summary_bind.py:177-189`. Update story deletes the prior template
   before writing the new association. If `associate` fails between the
   two calls, the kind's map still points at a deleted template and the
   Summary tab is broken. Fix: associate first, read the new tabId, then
   delete prior templates whose `userPageId != new tabId`.
5. `summary_bind.py:178` + `ui_client.py:348`. When the current
   assignment is ours and the account is not admin, `getTemplateList`
   returns the error panel, `get_template_list` raises, and the whole run
   aborts with exit 2 before any association (including `--unbind`). The
   "will be orphaned" warning branch is only reachable when the list is
   returned empty. Fix: catch `UIClientError` around `get_template_list`,
   emit the orphan warning, continue.
6. Stale-zip discipline (CLAUDE.md "After tooling changes"; review
   dimension 9). `render.py` was touched and no commit or result block
   flags a `content-packager` rebuild. Rendered output for existing
   content is provably byte-identical, so a `CURRENT_TEMPLATE_VERSION`
   bump is not required by the docstring in
   `src/vcfops_packaging/template_version.py` (no wire-format change for
   distributed content); the rebuild delegation still is.

## NIT

1. `knowledge/context/api-surface/summary_dashboard_pak_binding.md:185`
   named a specific vendor pack (reworded). `src/`, `tests/` and the wire-format doc are clean.
2. `summary_bind.py:_is_ours` deletes every template named `X`, `X 1`,
   ... on rebind/unbind; if the same dashboard was bound to a second
   kind through the UI, that kind's tabId now points at a deleted
   template. Document or scope the deletion to the kind being touched.
3. `ui_client.py:216` `list_dashboards` (pre-existing) does not send
   `X-Requested-With`; the five new methods do.
4. Tooling reported 77 new tests; 75 collect.

## Hunt results (brief items)

1. Section membership: last Section owns everything below; two Sections on
   the same row give the first nothing; a widget on a Section's row is in
   no Section (W3).
2. `view_details`: leading space stripped then accepted; `javascript:`
   rejected; omission emits no key; `""` emits `"viewDetails": ""`.
   Uppercase scheme/`/UI/` rejected (matches the product's
   case-sensitive `startsWith`).
3. Gauge: `maxValue` default semantics are the product's
   (`maxV = maxValue || (unit=='%' ? 100 : 1)`); loader emits `""` when
   unset and does not warn for theme 9 + non-% unit. Switches emitted only
   for theme 9; 0 and 10 rejected with the 1..9 message.
4. `summary_for`: `a:b:c`, `A:B,C:D`, `:x`, `x:` rejected; hyphens fine;
   pinned View/HealthChart/AlertList/RRA rejected under `summary_for`.
5. `bind_summary`: no credential or token is printed; CSRF only travels in
   request bodies. See B1, W4, W5, N2.
6. `dashboards.properties`: one line per bound slug, `<slug>=<AK>:<RK>`,
   file absent when nothing is bound. See W1, W2.
7. `abs(hash())` nondeterminism: pre-existing, tracked, not worsened.
8. Grep gate: see N1.

---

# Re-review (2026-08-25, fix commits on this branch)

Verdict: **APPROVE** (0 BLOCKING, 0 WARNING, 2 NIT). NIT 1 from the
first pass (pak-binding doc line 185) accepted by the orchestrator and
not re-raised. the reviewed change (RULE-011 amendment) is docs only, out of scope.

## Checks re-run (independently)

- Seven-package validate chain: all rc=0.
- Test suite: 1161 passed, 7 failed, 16 skipped, 127 deselected. The 7
  failures are the committed doctor/jmespath baseline
  (`test_common_doctor.py` x5, `test_gap_b_f_d.py` x2). Matches tooling.
- The five new test files: 94 passed. Matches tooling.
- Render regression: `content/` rendered from a `main` worktree and from
  HEAD with `PYTHONHASHSEED=0` is byte-identical (`cmp`).
- Old-matcher proof: the current `tests/test_dashboard_summary_for.py`
  run against a scratch copy of `src/` with the pre-change
  `_find_kind_entry` restored fails **11** tests (tooling claimed 7; the
  four extra are the new bind-flow tests, which also depend on the
  matcher). The fixture now encodes the live shape.

## Finding-by-finding

- **B1 closed.** `summary_bind.py:107-123` matches `resourceKindId`
  first, then the `(adapterKind, resourceKind)` pair. Capture
  `reference/docs/extracted/summary-dashboard-assignment/getResourceKindList-9.1.0-redacted.json`:
  66 entries, adapter kinds `Container` (29) / `VMWARE` (25) /
  `VirtualAndPhysicalSANAdapter` (12); every entry carries
  `resourceKindId`, `resourceKind`, `adapterKind`, `name`,
  `resourceKindTemplate`; no entry carries `id`, `key`, or
  `resourceKindKey`; restricted-term grep: zero hits in the JSON or
  README; top-level `defaultTemplateName` = `Summary Detail`.
  `test_captured_shape_has_no_legacy_keys` pins this.
- **W1 closed.** `loader.py:2460-2466` stores `f"{ak}:{rk}"`; the pak
  route uses the same `load_dashboard`, so both routes emit the
  normalized value. `test_stored_normalized` covers three whitespace
  forms.
- **W2 closed.** `check_unique_summary_for` (`loader.py:1611-1630`)
  runs in `load_all` (`loader.py:2495`) and in
  `sdk_builder._load_bundled_content` (`sdk_builder.py:904-907`,
  wrapped as `SdkBuildError`). Tests on both routes
  (`test_duplicate_target_rejected_by_load_all`,
  `test_duplicate_target_rejected_by_pak_builder`); comparison is on the
  normalized string, so `VMWARE : HostSystem` and `VMWARE:HostSystem`
  collide as they should.
- **W3 closed.** `loader.py:2076-2081` rejects Section `x != 1`
  (parametrized 0/2/5/12); `loader.py:2416-2424` rejects any widget on a
  Section's row, including a second Section. The loud reject is the
  right side of the `00d3382` line (no silent coordinate rewrite).
- **W4 closed.** `summary_bind.py:210-215` associates, reads
  `getSummaryTabId`, then deletes; the new tabId is excluded from the
  victims (`tid == str(tab)`). `test_failed_associate_leaves_prior_template`
  proves an `associate` failure deletes nothing; the rebind test asserts
  `associate < get_summary_tab_id < delete` by call index.
- **W5 closed.** `summary_bind.py:224-229` catches `UIClientError` from
  `get_template_list`, prints the orphan warning, continues; covered for
  bind and `--unbind` (`test_unprivileged_template_list_is_a_warning`,
  both parametrizations assert the associate happened and rc=0).
- **W6 closed.** the reviewed change records in the wire-format doc changelog that
  `dist/` zips are stale and need a full `content-packager` rebuild;
  `CURRENT_TEMPLATE_VERSION` not bumped, justified by the byte-identical
  render (consistent with the first-pass assessment).
- **N2 closed.** `_labels_assigned_elsewhere` (`summary_bind.py:126-148`)
  keeps any template whose label is currently assigned to another kind;
  `test_template_bound_to_another_kind_is_kept` covers it.
- **N3 closed.** `ui_client.py:224` `list_dashboards` now sends
  `X-Requested-With`.
- **N4 closed.** New-file count now 94 and matches the claim.

## New NIT

1. `summary_bind.py:224` catches only `UIClientError`. `get_template_list`
   calls `resp.raise_for_status()` (`ui_client.py:360`) before parsing,
   so if the unprivileged ERRPANEL ever comes back as an HTTP 4xx rather
   than a 200 HTML body, a `requests.HTTPError` escapes. No doc records
   the ERRPANEL status code (`vcf_operations_api_surface.md:298` treats
   it as a body class, which implies 200). Because the associate and the
   tabId read-back now happen first, the worst case is a traceback after
   a successful bind, not a broken kind. Fix if desired: catch
   `(UIClientError, requests.HTTPError)`.
2. `loader.py:2076` compares `sec_x != 1` without the `int()` cast used
   by `_x`; a YAML string `"1"` would be rejected with a confusing
   message. Cosmetic.

## If shipped as-is

`bind-summary` binds on a real 9.1 instance, survives a non-admin
`getTemplateList`, never leaves a kind pointing at a deleted template,
and both routes refuse two dashboards on one Summary tab. Existing
content renders unchanged. Distribution zips must still be rebuilt.

---

## 2026-08-25 (third pass): the reviewed change

Incremental review of the reviewed change (bind-summary sends
`assignedAssociations` / `resetAssociations`; template-list and
delete-template actions removed) and the reviewed change (view `subjects:` list,
one SubjectType pair per kind). Ground truth: the dated 2026-08-25 note
in `knowledge/context/api-surface/summary_dashboard_assignment.md`
(disassembled `DashboardAction`) and
`reference/docs/extracted/view-multi-subject/` plus the new section of
`knowledge/context/wire-formats/view_column_wire_format.md`.

**Verdict: APPROVE** (0 BLOCKING / 2 WARNING / 5 NIT).

### Checks re-run (real tools, not the stand-in runner)

- Test suite (pytest 7.4.4 from the Ubuntu debs in the session
  scratchpad): **1180 passed / 7 failed / 16 skipped / 127 deselected**.
  Baseline before these commits: 1161 / 7 / 16. The seven failures are
  the same pre-existing `test_common_doctor` (5) and
  `test_gap_b_f_d` JMESPath (2) cases; +19 new passes.
- Validate chain, all seven packages: rc=0.
- View XML regression, factory route (`content/views`, 19 views),
  rendered at the reviewed change and HEAD from a detached worktree: byte-identical.
- View XML regression, pak route (`content/sdk-adapters/*/views`, 189
  of 207 renderable in isolation, the other 18 need SM resolution and
  fail identically in both trees): byte-identical. So the "all 24"
  claim understates it; every existing view on both routes renders the
  same, and no existing view carries `subjects:`.
- Dashboard bundle JSON, `PYTHONHASHSEED=0`, the reviewed change vs HEAD:
  byte-identical.
- No restricted terms in the diff.
- `pak-compare`: n/a (no builder/template change).

### Hunts

- **POST body** (`ui_client.py:317-327`): `assignedAssociations` and
  `resetAssociations` are both always sent, `json.dumps(dict(x or {}))`
  so an empty map goes as `{}`; `secureToken` present; `_UI_XHR_HEADERS`
  (`X-Requested-With: XMLHttpRequest`) present; a non-`ok` body raises
  `UIClientError`. `TestUIClientWire` pins all of it against a fake
  session, including `dashboardAssociations` absent.
- **`--unbind`** (`summary_bind.py:184-191`): `_default_template_name`
  takes the per-entry `defaultTemplateName`, falls back to the
  top-level one, and when neither exists prints `ERROR: no
  defaultTemplateName` and counts a failure (rc=2) without calling
  associate. Reset value is the plain name (fake asserts no `_::_`).
- **`tabId`**: the only consumer is `_live_tab_id`
  (`summary_bind.py:125-131`), which treats a missing key, `None`, and a
  non-dict body as null. The `tabId` hits in `install.py` /
  `install.ps1` are the unrelated `deleteTab` payload. A bind counts only
  with `isDashboard: true` (`summary_bind.py:218`).
- **`subjects:`**: duplicates rejected in `ViewDef.validate`
  (`loader.py:462-472`); mutual exclusion with the scalar pair in
  `load_view` (`loader.py:1841-1845`); list order preserved through
  `subject_kinds`; `filter_attr` is emitted on every SubjectType
  (`render.py:764-768`, test asserts 4 `filter=` for 2 kinds). Exactly
  one `ViewDef(` construction site in the loader (`loader.py:2026`), and
  embedded dashboard views go through the same `load_view`, so
  `subjects:` cannot be dropped on one route and kept on another.

### WARNING

1. `src/vcfops_packaging/deps.py:209-210`, `_refs_from_view` audits
   every column metric against `view.adapter_kind / resource_kind`
   only. For a `subjects:` view the second and later kinds are never
   checked for metric enablement, so the dependency audit reports green
   while those kinds' columns can be policy-disabled and render blank
   (the same class the instanced_group comment in that function was
   added for, DEF-016 / PR #70). Inert today (no content uses
   `subjects:`), and unlike the reverse path this narrowing is not
   recorded in the wire doc. Fix: iterate `view.subject_kinds` and emit
   one `MetricReference` per kind.
2. `src/vcfops_dashboards/reverse.py:234-238`,
   `src/vcfops_extractor/extractor.py:546-550`,
   `src/vcfops_extractor/reverse_local.py:177-181`: first SubjectType
   wins, silently. The wire doc records this as a known gap, which keeps
   it out of BLOCKING, but the vendor corpus the doc itself cites
   (vCommunity, Kubernetes MP) contains multi-subject views, so an
   `/extract` of one narrows the view with no message. Fix: when more
   than one distinct (adapterKind, resourceKind) pair is seen, either
   populate `subjects` or print a WARN naming the dropped kinds.

### NIT

1. `src/vcfops_dashboards/cli.py:827`: `--unbind` help still reads
   `(<defaultTemplateName>_::_null)`; the reset value is the plain name.
2. `src/vcfops_dashboards/summary_bind.py:214-217`: unbind success keys
   on `tab` being falsy. The third documented `getSummaryTabId` shape
   (`tabId` non-uuid, `isDashboard: false`, `pluginExist`) would be
   reported as "expected null after unbind" and rc=2 even though the
   reset took. Checking `is_dashboard`, symmetric with the bind branch,
   is the exact condition.
3. the reviewed change touches `render.py`; the standing stale-zip flag from
   the reviewed change on this branch still applies and no rebuild has happened.
   Not restated in the commit. `CURRENT_TEMPLATE_VERSION` unchanged is
   justified by the byte-identical renders above (same reasoning as
   W6 in the second pass).
4. `tests/test_view_multi_subject.py:78,113`: the
   `x if (tmp_path / "a").mkdir() is None else None` idiom works but
   reads as a trick; two statements would do.
5. Working tree carries an uncommitted +170-line change to
   `knowledge/context/investigations/recon_log.md` that belongs to
   neither commit. Not written by this reviewer; commit or drop it
   before the PR.

### If shipped as-is

`bind-summary` sends the two parameters the server actually reads, so
binds stop NPEing into the ERRPANEL; `--unbind` restores the kind's own
default page. `subjects:` views render the vendor shape. Existing
content, both routes, is unchanged byte for byte. A future multi-subject
view would pass the dependency audit with only its first kind checked
(W1), and an extract of a vendor multi-subject view would lose kinds
without saying so (W2).

## 2026-08-25 (fourth pass): the reviewed change

Closure review of the third-pass WARNING/NIT set. Base for regression:
the third-pass review commit.

**Verdict: APPROVE** (0 BLOCKING / 0 WARNING / 2 NIT).

### Checks re-run (real pytest 7.4.4 from the scratchpad debs)

- Suite: **1190 passed / 7 failed / 16 skipped / 127 deselected**
  (+10 over the third-pass 1180). The seven failures are the same
  pre-existing `test_common_doctor` (5) and `test_gap_b_f_d` JMESPath
  (2) cases.
- Validate chain, all seven packages: rc=0.
- View XML, factory route (19 views) and pak route (189 of 207, same
  18 unrenderable in both trees), the reviewed change vs HEAD from a detached
  worktree: byte-identical.
- Dashboard bundle JSON, `PYTHONHASHSEED=0`: byte-identical.
- Dependency-audit refs, `_refs_from_view` over every loadable view on
  both routes plus `bundles/` (226 views, 1201 references), the reviewed change
  vs HEAD: byte-identical, so single-subject reference order and
  content are unchanged.
- No restricted terms in the diff.
- `pak-compare`: n/a. No `templates/`, `builder.py`, or `render.py` in
  this diff; no new stale-zip trigger (the standing stale-zip flag on
  the branch is unchanged).

### Finding-by-finding

- **W1 closed** (`deps.py:203-260`). Keys are gathered once (columns in
  order, instanced-group drivers still skipped, SM refs skipped, then
  subject-filter keys) and emitted per `view.subject_kinds`. Two-kind
  test asserts one ref per (kind, key) with filter keys included; the
  corpus diff above proves the scalar path is untouched.
- **W2 closed** (`reverse.py:234-281`, `extractor.py:547-587`,
  `reverse_local.py:178-218`). Ran all three parsers against the
  committed `reference/docs/extracted/view-multi-subject/` header and
  against synthetic ABAB, three-kind, and single-kind sequences: all
  three return the same distinct pairs in document order, scalar equals
  the first pair, single-kind leaves `subjects` empty. Both writers emit
  `subjects:` (no `subject:`) for the multi case and the unchanged
  `subject:` map otherwise; the round-trip test loads the written YAML
  through `load_view` and gets the same `subject_kinds`. The extractor
  enablement mirror (`extractor.py:2205-2223`) iterates the same kinds
  list, falling back to the scalar pair. `reverse_local.py` has no
  enablement mirror (it is offline by design); its change is the writer
  only. Wire-doc known-gap note replaced with the new behaviour.
- **NIT 1 closed** (`cli.py:827`): help text names `resetAssociations`.
- **NIT 2 closed** (`summary_bind.py:215-221`): unbind success keys on
  `is_dashboard`, which is `False` for a null/absent body, for the
  legacy `{tabId: "hostSummaryTab", isDashboard: false, pluginExist}`
  shape (new test, rc=0, no WARNING), and `True` only when the server
  still reports a dashboard. Symmetric with the bind branch.
- **NIT 4 closed**: the `mkdir() is None` idiom is two statements.

### NIT (open)

1. Third-pass NIT 5 still stands: `knowledge/context/investigations/recon_log.md`
   is modified and uncommitted in the working tree. Commit or drop
   before the PR.
2. Pre-existing, not introduced here: neither `_write_view_yaml` writes
   the SubjectType `filter=` JSON back as `subject.filter`, so an
   extracted view (single or multi subject) loses its subject filter
   silently. Out of this diff's scope; worth an issue.

### If shipped as-is

A multi-subject view is audited on every kind and extracts intact as
`subjects:`; `--unbind` reports success on the native-page shape.
Existing content on both routes renders byte for byte as before.

## 2026-08-25 (fifth pass): the reviewed change

Scoreboard bound contract: the loader rejects a partial
yellow/orange/red set on `color_method: 0`; the smoke dashboard's two
gauges gain `red_bound: 100`. Base for regression: the reviewed change. Ground
truth: `knowledge/lessons/scoreboard-partial-bounds-render-unknown.md`
and the gauge section of
`knowledge/context/wire-formats/dashboard_section_gauge_viewdetails.md`.

**Verdict: APPROVE** (0 BLOCKING / 1 WARNING / 2 NIT).

### Checks re-run (real pytest 7.4.4 from the scratchpad debs)

- Suite: **1197 passed / 7 failed / 16 skipped / 127 deselected**,
  matching tooling's claim. The seven failures are the standing
  `test_common_doctor` (5) and `test_gap_b_f_d` JMESPath (2) cases.
  `tests/test_dashboard_metric_bounds.py`: 7 passed.
- Validate chain, all seven packages: rc=0. The managementpacks
  package is **green, not red**: the `vcommunity-vsphere` clone already
  carries the upstream fix ("complete Scoreboard bound triple on HA/DRS enabled
  tiles"), so the two `Cluster Performance 2.0.yaml` entries the brief
  expected to fail have been fixed upstream and both Tier 2 projects
  validate.
- Dashboard bundle JSON, `PYTHONHASHSEED=0`, the reviewed change vs HEAD over
  `content/dashboards/` + `third_party/idps-planner/` +
  a private third-party project with multi-kind summary dashboards (0 load errors on either side):
  the only differences are the two smoke-gauge `redBound: null ->
  100.0` lines. The (git-excluded) private summary dashboard renders
  byte-identical under base and HEAD source.
- No restricted terms in the diff.
- `pak-compare`: n/a. No `templates/`, `builder.py`, or `render.py` in
  the diff; `summary_widget_smoke.yaml` is in no `bundles/` manifest, so
  no new stale-zip trigger.

### Behaviour probed (synthetic YAML through `load_dashboard` + render)

- Each single missing bound on `color_method: 0` is rejected with the
  widget id, the metric key, and only the missing bound named (the test
  asserts the other two names are absent from the "missing" clause; my
  probe on the fixture's second metric names `mem|usage_average` and
  `yellow_bound` only). Two missing names both. `red_bound: 0` counts
  as present (`is None` test, not truthiness). A quoted `'0'`
  color_method still fires (`int()` coercion precedes the check).
- Full set and empty set both load; render emits exactly the validated
  triple (`70.0, 85.0, 95.0`) or three nulls with `colorMethod: 0`.
- `color_method: 2` (and 1, 3) with a partial set is tolerated and is
  inert on the wire: `render.py:1276-1283` emits `null` for all three
  bounds whenever `color_method != 0`, so nothing partial ever reaches
  the server on those methods. Tolerating it is correct.
- The check fires for MetricChart and PropertyList too, because all
  three widgets share `_parse_metric_specs` (`loader.py:2199`) and
  `_render_metric_spec`, so an explicit `color_method: 0` entry lands as
  the same `resourceKindMetrics[]` shape on the wire. PropertyList
  defaults to `color_method: 2` (nulls), so an author only hits the
  check by writing `color_method: 0` with a partial set, which is an
  authoring error in any widget. Judged correct; see NIT 1 for coverage.
- Existing factory, idps-planner and private third-party dashboards load and validate
  unchanged (corpus diff above).

### WARNING

1. `src/vcfops_dashboards/loader.py:807-808` and `:827-828`, plus the
   wire doc lines 79-80, now document `color_method: 3` as "the same
   three bounds read as a percent of `max_value`". The renderer does not
   emit that: `render.py:1276-1283` writes `yellowBound/orangeBound/
   redBound: null` for every method other than 0, and my probe of a
   full triple on `color_method: 3` produced `(3, None, None, None)` on
   the wire. An author who follows the new docstring gets a
   percent-mode tile with no thresholds, silently (reviewer dimension
   8, silent capability gap; the loader has never rejected 3, so this
   is pre-existing renderer behaviour that the diff newly advertises).
   Zero corpus uses of `color_method: 3` today, so no regression
   shipped. Fix: either state in both docstrings that the factory does
   not emit bounds for 3, or extend `render.py:1276` to
   `color_method in (0, 3)` and apply the same all-or-none check to 3
   once the partial-set behaviour on 3 is confirmed on the server.

### NIT

1. `tests/test_dashboard_metric_bounds.py` covers the Scoreboard path
   only. The check also runs for MetricChart and PropertyList through
   the shared helper; one parametrized case per widget type would pin
   that.
2. Standing since the third pass:
   `knowledge/context/investigations/recon_log.md` is modified and
   uncommitted. Commit or drop before the PR.

### If shipped as-is

A partial bound set on a colored tile is refused at validate time with
the widget, metric and missing bound named, instead of rendering "?" on
the server. The smoke gauges now carry `(70, 85, 100)`. Every other
dashboard on every route renders byte for byte as before. An author
who reads the new `color_method: 3` note and authors bounds for it
would get an uncolored percent tile with no error (W1).

## 2026-08-25 (sixth pass): the reviewed change

Closure of the fifth-pass WARNING: the loader now rejects any bound
supplied with `color_method: 3`; the `MetricSpec` docstring, the
`ScoreboardConfig` docstring and the gauge wire doc say the factory
emits bounds only for `color_method: 0`; one partial-bound rejection
case each for MetricChart and PropertyList (fifth-pass NIT 1). Base for
regression: the reviewed change. Ground truth: `render.py:1276-1283`,
`knowledge/lessons/scoreboard-partial-bounds-render-unknown.md`, gauge
section of `dashboard_section_gauge_viewdetails.md`.

**Verdict: APPROVE** (0 BLOCKING / 0 WARNING / 3 NIT).

### Checks re-run (real pytest 7.4.4 from the scratchpad debs)

- Suite: **1202 passed / 7 failed / 16 skipped / 127 deselected**,
  matching tooling's claim. Same seven standing failures
  (`test_common_doctor` x5, `test_gap_b_f_d` JMESPath x2).
  `tests/test_dashboard_metric_bounds.py`: 12 passed.
- Validate chain, all seven packages: rc=0. managementpacks covers the
  six sdk-adapter clones (compliance, synology, unifi, vcommunity,
  vcommunity-os, vcommunity-vsphere).
- Corpus grep for `color_method: 3` (quoted or bare) over `content/`
  including `content/sdk-adapters/*/`, and `third_party/`: zero hits, so
  no dashboard can trip the new check.
- Render regression, `PYTHONHASHSEED=0`, the reviewed change loader vs HEAD over
  `content/dashboards/`, `third_party/idps-planner/`,
  a private third-party project and `content/sdk-adapters/*/dashboards/`
  (36 dashboards, 0 load errors on either side): `cmp` byte-identical.
- No restricted terms in the diff.
- `pak-compare`: n/a. Diff is `loader.py`, one test file, one wire doc.
  No `render.py`, `templates/`, `builder.py`; no new stale-zip trigger
  beyond the standing stale-zip flag.

### Behaviour probed (synthetic YAML through `load_dashboard` + render)

- `color_method: 3` with the full triple, with `red_bound` only, with
  `red_bound: 0`, and with a quoted `'3'` all reject
  (`loader.py:2233-2252`). The message names the widget id
  (`'cpu_gauge'` / `'pl1'`), the metric key (`'cpu|usage_average'`) and
  exactly the supplied bound names: full set lists all three, red-only
  lists `red_bound` alone, PropertyList yellow+orange lists those two.
  `is not None` test, so `red_bound: 0` counts as supplied and explicit
  `yellow_bound: null` / `~` count as absent.
- `color_method: 3` with no bounds loads, validates and renders
  `colorMethod: 3` with `yellowBound/orangeBound/redBound: null` on
  Scoreboard, MetricChart and PropertyList. The `color_method: 0` sibling
  metric in the same widget still renders its `(80, 90, 95)` triple.
- The check is an `elif` on the same `color_method` int as the method-0
  branch, so 0 and 3 are mutually exclusive and 1/2 are untouched
  (fifth-pass probes for 1 and 2 partial sets still tolerate and null).
- Doc statements vs `render.py:1276-1283`: the renderer copies the three
  bounds only when `spec.color_method == 0` and writes `None` otherwise.
  Both docstrings (`loader.py:807-808`, `:827-833`, `:917-919`) and the
  wire doc (lines 79-86) now say exactly that, and say partial-set
  behaviour on 3 is unverified server-side. Accurate.
- MetricChart and PropertyList partial-set-on-0 tests build their own
  fixtures over public VMWARE kinds and assert widget id, metric key and
  `missing red_bound`; they pass under HEAD.
- The extract path is consistent: `extractor.py:1012-1020` (pre-existing
  on `main`) writes `color_method: 3` and omits bounds for any method
  other than 0, so a re-extracted vendor gauge loads under the new check.

### NIT

1. `knowledge/lessons/scoreboard-partial-bounds-render-unknown.md:28`
   still reads "`colorMethod: 3` means percent-of-`maxValue`
   thresholds" with no "factory does not emit" qualifier. Lessons rank
   above context docs; an author reading only the lesson could still
   try it (they now get a clear error, so no silent failure). One
   clause, orchestrator-owned file.
2. `src/vcfops_extractor/extractor.py:1014` (pre-existing on `main`)
   silently drops the bound triple when extracting a vendor gauge with
   `colorMethod: 3`; the YAML gets `color_method: 3` and an uncolored
   tile on re-import, with no warning in the extract output. Not this
   diff, and consistent with the loader, but worth a one-line warning
   when 3 is met with non-null bounds. Issue, not initiative.
3. Standing since the third pass:
   `knowledge/context/investigations/recon_log.md` is modified and
   uncommitted (+170). Commit or drop before the PR.

### If shipped as-is

An author who writes thresholds on `color_method: 3` is refused at
validate time with the widget, metric and the bounds they supplied,
and told to use `color_method: 0`. `color_method: 3` without bounds
still round-trips (extract and author) unchanged. Every corpus
dashboard on every route renders byte for byte as before.

---

## Seventh pass, 2026-08-26: `summary_for` binds one dashboard to many kinds (the reviewed change)

Diff: `src/vcfops_dashboards/loader.py` (+66/-35),
`src/vcfops_dashboards/summary_bind.py` (+118/-66),
`src/vcfops_managementpacks/sdk_builder.py` (+5/-2),
`tests/test_dashboard_summary_for.py` (+170/-9), two wire docs. No
`render.py`, `templates/`, `builder.py`; no new stale-zip trigger beyond
the standing stale-zip flag.

**Verdict: APPROVE.** 0 BLOCKING / 1 WARNING / 3 NIT.

### Checks re-run

- Real pytest from `.venv/bin/python` (jmespath + pytest present):
  **1222 passed, 4 failed, 16 skipped, 127 deselected** (22s). The 4
  failures are all `tests/test_common_doctor.py` (`missing_modules ==
  ['jmespath']` from `inspect_environment` against the real venv); they
  fail identically on the pre-change worktree with the same interpreter,
  and `src/vcfops_common/doctor.py` is untouched. Baseline moved from 7
  to 4, none attributable to this diff. `tests/test_dashboard_summary_for.py`
  alone: 63 passed.
- Seven-package validate chain: all rc=0.
- Render regression, `PYTHONHASHSEED=0`, the reviewed change src vs HEAD src over
  `content/`, `third_party/idps-planner`, a private third-party project, and
  `content/sdk-adapters/*/dashboards` (34 dashboards; the
  `vcommunity-vsphere` `VM Details` load error `unknown view 'Windows
  Services vCommunity'` is identical on both sides and pre-existing):
  every `dashboard.json` `cmp` byte-identical. The single-string YAML in
  `content/` and the private multi-kind summary dashboards load as one-element
  lists and render unchanged.
- No restricted terms in the diff.
- pak-compare: n/a (no pak built; `dashboards.properties` emission is
  covered by `TestPakDashboardsProperties::test_many_kinds_emit_comma_joined_value`,
  which I ran).

### Behaviour probed (`normalize_summary_for` direct, `loader.py:1684-1712`)

| input | result |
|---|---|
| `"VMWARE:HostSystem"` | `['VMWARE:HostSystem']` |
| `"VMWARE:HostSystem,VMWARE:VirtualMachine"` | two-element list, order kept |
| YAML list / tuple | same |
| `" VMWARE : HostSystem , VMWARE:Datastore "` | tokens stripped, `['VMWARE:HostSystem','VMWARE:Datastore']` |
| `"VMWARE:HostSystem,"` / `"a,,b"` | ERR: two non-empty tokens, got `''` (loud, matches the installer's silent skip made visible) |
| `["VMWARE:HostSystem", 5]` | ERR: must be a string, got int |
| `["VMWARE:HostSystem,VMWARE:Datastore"]` (comma inside a list entry) | ERR: three colon tokens. Loud, correct: a list entry is one kind. |
| `"vmware:HostSystem,VMWARE:HostSystem"` | two distinct kinds. Correct: `IdGeneratorUtil.toID` concatenates raw keys, so case is significant server-side (`summary_dashboard_pak_binding.md` §Install-time behavior step 3). |

- Duplicate within one dashboard: rejected after strip, so
  `"VMWARE : HostSystem"` collides with `"VMWARE:HostSystem"`
  (`loader.py:1708-1710`, test `test_duplicate_within_dashboard_rejected`).
- Cross-dashboard: `check_unique_summary_for` (`loader.py:1715-1733`)
  iterates kinds, so a kind buried in one dashboard's list collides
  with another dashboard's single string. Both `load_all`
  (`loader.py:2677`) and the pak route (`sdk_builder.py:905`) call it.
- Associate map: `summary_bind.py:222-251`. One
  `associate_resource_kind_dashboards(assigned, reset)` per dashboard;
  bind builds `assigned` as one entry per kind keyed
  `resourceKind_<id>` with the same `<name>_::_<uuid>` value and
  `reset={}`; unbind builds `reset` as one entry per kind with that kind's
  `defaultTemplateName` and `assigned={}`. Matches
  `summary_dashboard_assignment.md` §Factory tooling. `getResourceKindList`
  is fetched once per distinct adapter kind (`kind_lists` cache,
  `summary_bind.py:212-215`).
- Readback: `summary_bind.py:257-290` loops kinds, calls
  `get_summary_tab_id(k.resource_kind_id)` per kind, prints
  `<label>  LIVE tabId:` per kind, and `_live_tab_id` (`:158-164`) still
  returns None on a missing `tabId` key, evaluated per kind. Bind
  requires `isDashboard: true` + `tabId` on every kind; unbind counts a
  still-`isDashboard` kind as a failure. rc=2 if any kind fails.
- `dashboards.properties` (`sdk_builder.py:2001-2004`):
  `Host_Summary=VMWARE:HostSystem,VMWARE:VirtualMachine,VMWARE:Datastore`,
  each part exactly two colon tokens, no whitespace (the loader stripped
  it). This is the shape at `summary_dashboard_pak_binding.md:60-66,81`.
- `Dashboard.summary_for` was `Optional[str]`, now `Optional[list[str]]`.
  Every consumer in `src/` was grepped: `sdk_builder.py:2000-2004`
  (updated) and `summary_bind.py` (updated). `cli.py` only passes the
  dashboards through. No string-typed consumer left behind.

### WARNING

1. `src/vcfops_dashboards/summary_bind.py:210-232`, the
   "skip the whole dashboard if any kind is unresolvable" rule. Assessed
   against the pak route as ground truth: the installer loops
   `for (String objectType : objectTypes)` and associates each kind
   independently (`summary_dashboard_pak_binding.md:82-84`); there is
   no all-or-nothing at the server, and each kind's association is a
   separate template copy that the server replaces on the next bind
   (`summary_dashboard_assignment.md` §Factory tooling). So a partial
   map is not a corrupt state, it is exactly what a pak install of the
   same dashboard would produce on the same instance. For the intended
   many-kind summary dashboard on an instance missing a few kinds
   (adapter version skew is the normal case), the current rule binds
   nothing and returns rc=2, which is a worse operator outcome than
   binding 24 and naming the 3 misses, and re-running after the adapter
   catches up is idempotent either way. Recommend: bind the resolvable
   kinds, print `ERROR` per missing kind, keep rc=2 so the miss is not
   silent. Not blocking: the behaviour is loud, documented in
   `summary_dashboard_assignment.md` and tested
   (`test_unknown_kind_skips_whole_dashboard`), so it is a judgment call
   with a safer alternative, not a regression. If tooling keeps
   all-or-nothing, a `--partial` flag would give the operator the choice.

### NIT

1. `.claude/agents/content-installer.md:131` still describes
   `summary_for: "<AdapterKind>:<ResourceKind>"` as a single string and
   says "its resource kind's Summary tab" (singular); `bind-summary` now
   prints one `LIVE tabId` / template UUID per kind and the install
   report should record all of them. Orchestrator-owned file.
2. `src/vcfops_dashboards/cli.py:682` docstring and the `--dashboard`
   help at `:816` say "its resource kind's Summary tab" (singular).
   Cosmetic.
3. Standing since the third pass: `knowledge/context/investigations/recon_log.md`
   is modified and uncommitted. Commit or drop before the PR.

### If shipped as-is

An author can declare one summary dashboard for many kinds in any of
three YAML shapes and gets a loud load-time error for a malformed entry,
a kind listed twice, or a kind another dashboard already owns. A pak
carries the comma-joined line the installer already parses; `bind-summary`
writes one call and reports one template UUID per kind. Existing
single-kind YAML renders byte for byte as before. The one operator-facing
sharp edge is the WARNING: a dashboard with any kind absent on the
instance binds nowhere until that kind exists.

## 2026-08-26, eighth pass: the reviewed change (partial bind on missing kinds)

Scope: `src/vcfops_dashboards/summary_bind.py`, `src/vcfops_dashboards/cli.py`,
`tests/test_dashboard_summary_for.py`,
`knowledge/context/api-surface/summary_dashboard_assignment.md`. This is
the resolution of the seventh pass WARNING 1 (all-or-nothing skip) and
NIT 2 (singular docstrings). NIT 1 was closed by the orchestrator in
the reviewed change. Verdict: **APPROVE**, 0 BLOCKING / 0 WARNING / 2 NIT.

### Verified (code read in data-flow context, tests re-run)

- Associate map contains exactly the resolved kinds:
  `summary_bind.py:224-249` builds `bound` from kinds whose
  `_find_kind_entry` hit (and, for unbind, whose `defaultTemplateName`
  is non-empty); `assigned` (`:259`) and `reset` (`:240`) are keyed only
  from `bound`; one `associate_resource_kind_dashboards(assigned, reset)`
  call (`:261`). Readback loop (`:268`) iterates `bound` only, so the
  missing kind is never queried. Test
  `test_unknown_kind_binds_the_rest_and_exits_2` asserts the single call's
  exact map (`KEYS[0]`, `KEYS[2]`, `reset={}`) and the two-element
  `get_summary_tab_id` sequence.
- Missing kind's existing template untouched on unbind: the missing kind
  is absent from `reset`, and `resetAssociations` is keyed per kind
  (`summary_dashboard_assignment.md` §Factory tooling), so the server has
  nothing to act on for it. `test_unbind_unknown_kind_resets_the_rest_and_exits_2`
  asserts `ui.templates[KEYS[1]] == "old-copy-uuid"` after the run while
  `KEYS[0]`/`KEYS[2]` are popped.
- Zero-resolved writes nothing: `:250-252` `continue` before
  `_resolve_installed` and before the associate call.
  `test_all_kinds_unknown_writes_nothing` asserts no `associate`,
  `list_dashboards`, or `get_summary_tab_id` call and two `not found` lines
  plus the `no listed kind resolves` line.
- rc semantics: `failures += 1` per miss (`:233`, `:243`), so any miss
  yields rc 2 even when the rest bind and readback cleanly (`:297`).
  Zero-resolved needs no extra increment because each miss already
  counted. Not-installed after a partial resolve adds one more and
  `continue`s, still rc 2. No path returns 0 with a miss. Dry-run path
  (`:200-210`) unchanged: prints the full listed map, rc 0.
- Docs match: `summary_dashboard_assignment.md:335-342` describes exactly
  this behaviour (ERROR per miss, resolvable kinds bound, rc 2, skip only
  on zero, `--unbind` same). Module docstring `:185-191`, `cli.py:682`
  docstring and `:816` help now say "every listed resource kind's Summary
  tab". `content-installer.md:131-133` (closed in the reviewed change) is consistent.
  No stale "skipped whole"/"no partial map" wording anywhere outside this
  review file.
- Escape anchors: no global-path defaults, no key derivation, no render
  or builder change. `dashboards.properties` emission untouched
  (`sdk_builder.py`), so the pak route is unaffected.

### Re-runs

- `.venv/bin/python -m pytest`: **1224 passed, 4 failed, 16 skipped,
  127 deselected** (20s). Same 4 `tests/test_common_doctor.py` venv
  failures as passes five through seven; `doctor.py` untouched.
- Seven-package validate chain: all rc 0.
- Render regression, `PYTHONHASHSEED=0`, the reviewed change src (detached worktree)
  vs HEAD src over `content/`, `third_party/idps-planner`,
  a private third-party project, `content/sdk-adapters/*/dashboards` (34 dashboards,
  the pre-existing `vcommunity-vsphere` `VM Details` load error identical
  on both sides): every rendered `dashboard.json` byte-identical.
- No restricted terms in the diff.
- pak-compare: n/a (no builder/template change).
- Stale-zip: none of the CLAUDE.md trigger files touched, renders
  byte-identical, no `CURRENT_TEMPLATE_VERSION` bump required.

### NIT

1. `src/vcfops_dashboards/summary_bind.py:230-232`: the missing-kind
   ERROR line ends `{k.label} not bound` on the unbind path too, where
   "not reset" would be accurate (the `defaultTemplateName` miss at `:241`
   already says "not reset"). Cosmetic; the dashboard and kind are named
   either way.
2. Standing since the third pass: `knowledge/context/investigations/recon_log.md`
   is modified and uncommitted on the branch. Commit or drop before the PR.

### If shipped as-is

An operator running `bind-summary` against an instance missing some of a
dashboard's kinds gets the resolvable kinds bound in one call, one ERROR
line per miss naming the dashboard and kind, and rc 2; re-running after the
adapter catches up binds the rest. `--unbind` resets only the kinds it can
resolve and leaves any other kind's template alone. This is the same end
state a pak install of the same dashboard leaves.

### Whole-branch readiness (34 commits, main..HEAD)

Every `src/vcfops_*/` diff on this branch has been reviewed
across eight passes; the seven earlier verdicts stand (APPROVE, with the
one CHANGES REQUESTED from pass two resolved and re-reviewed), and this
pass closes the last open WARNING. Test suite, validate chain, and render
regression have been byte-identical against the previous review point at
every pass, the pak route emits the documented `dashboards.properties`
shape, no stale-zip trigger file was touched on the branch without its
version bump being assessed, and the only open items are two cosmetic
NITs and the uncommitted `recon_log.md`. The branch is ready for a PR.

## 2026-08-26, ninth pass: the reviewed change (multi-kind summary_for fan-out)

**Area:** `src/vcfops_dashboards/render.py` (`_fan_out_summary_specs`, the
three metric-widget emitters, and the `entries.resourceKind[]` kind-index
pass), `src/vcfops_dashboards/loader.py` (docstrings only, no behaviour),
`tests/test_dashboard_summary_for.py` (+5 tests).
**Change:** on a dashboard whose `summary_for` lists more than one kind, every
Scoreboard / MetricChart / PropertyList `MetricSpec` whose kind is listed is
emitted once per listed kind of the same adapter kind, in `summary_for`
order; unlisted kinds pass through; single-kind and non-summary dashboards
unchanged.
**Ground truth:** `knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
"Widgets bound to many resource kinds": server-side selection by the page
object's kind in `getTopImportantMetrics`, foreign-kind entries hidden, no
wildcard `resourceKindId` (every any-kind form returned ERRPANEL).

**Verdict: APPROVE.** 0 BLOCKING / 1 WARNING / 3 NIT.

### Verified (code read in data-flow context, own re-runs)

- Anchor `00d3382` (pak-local default leaking global): the fan-out is gated
  on `len(summary_kinds) >= 2` (`render.py:1256`), and `summary_kinds` is
  `[]` for any dashboard without `summary_for` (`loader.py:1483`). Every
  caller of `render_dashboards_bundle_json` (content-import path via
  `packager.py:106`, pak paths via `builder.py:647`,
  `discrete_builder.py:727`, `sdk_builder.py:1978`, extractor
  `reverse_local.py:712`) goes through the same function, so the two output
  paths cannot diverge. Proven inert on the corpus: every root other than
  the private third-party project renders byte-identical (below).
- Anchor `6c59f6b` (key collisions): the `extModel<hash>-<seq>` id runs over
  the expanded list (`render.py:1294`); on the private many-kind dashboards every
  fanned widget has all-unique ids (largest: 162 entries on one
  PropertyList, all distinct). Fanned entries differ only in
  `resourceKindId` / `resourceKindName` / `id`; a field-by-field diff of
  base vs head entries over all nine changed private-project widgets shows zero drift
  in any other key, and the non-`metric` widget config is identical.
- Entry order and count: metric-major, `summary_for` order within a metric
  (test `test_scoreboard_two_kinds` asserts it; the private project shows K kinds per
  metric for every fanned widget, `base_entries x K == head_entries` on
  all nine).
- Each fanned kind gets its own `entries.resourceKind[]` slot: private-project slots
  expand one per fanned kind, internalIds unique, and every head entry's `resourceKindId`
  resolve to a slot whose `resourceKindKey` equals the entry's
  `resourceKindName` (0 mismatches; base: 198 entries, 0 mismatches). The
  reference form `resourceKind:id:N_::_` is unchanged from the single-kind
  path, so the importer rewrite is the same one already live-proven.
- Self-provider-on widgets are not fanned: `_fan_out_summary_specs` returns
  early on `self_provider` (`render.py:1256`), and the loader already
  rejects `self_provider: true` on any `summary_for` dashboard
  (`loader.py:1506`), so the render gate is a second fence behind a
  validation error. PropertyList passes `False` (`render.py:1984`,
  `:2258`), matching its always-`selfProvider:false` wire shape.
- Unlisted kind passes through (test `test_pinned_child_kind_untouched`;
  re-proven by hand with a Datastore spec on a Host/VM list).
- Foreign adapter kind is not fanned into the listed kinds: hand render of
  `summary_for: [VMWARE:HostSystem, NSXTAdapter:TransportNode,
  VMWARE:VirtualMachine]` with NSXT, VMWARE:VirtualMachine and
  VMWARE:Datastore specs gives `[a|b TransportNode, c|d HostSystem, c|d
  VirtualMachine, e|f Datastore]`, four slots, four ids. The adapter-kind
  filter at `render.py:1262` does what the docstring says.
- Kind-index pass and emitter pass call `_fan_out_summary_specs` with the
  same `(specs, d.summary_kinds, self_provider)` triple
  (`render.py:2220-2225`, `:2228-2233`, `:2258-2260` vs `:1397`, `:1472`,
  `:1984`), so a fanned kind can never miss its slot (`kind_index[key]` at
  `:1291` would KeyError otherwise; it does not on the corpus).
- Not a validation change: the loader still accepts single-entry YAML; the
  documented non-check (metric key absent on one listed kind is a hidden
  entry, not an error) matches section 1 of the ground-truth doc.

### Re-runs

- `.venv/bin/python -m pytest`: 1229 passed, 4 failed, 16 skipped. The 4
  are the standing `tests/test_common_doctor.py` jmespath set (passes six
  through eight); `doctor.py` untouched. Matches tooling's 1229 / 4 / 16.
- Seven-package validate chain: all rc 0.
- Render regression, `PYTHONHASHSEED=0`, the reviewed change src (detached worktree)
  vs HEAD src over `content/`, `third_party/idps-planner`,
  a private third-party project, `content/sdk-adapters/*/dashboards` (39 dashboards,
  the pre-existing `vcommunity-vsphere` `VM Details` load error identical
  on both sides): `content`, `idps-planner`, `sdk-adapters/compliance`,
  `sdk-adapters/vcommunity` byte-identical. the private third-party project differs in
  exactly its two many-kind summary dashboards, nine widgets, the change's stated
  intent, characterised above; the project's other dashboards are
  unchanged. So "single-kind and no-summary_for byte-identical" holds.
- No restricted terms in the diff.
- pak-compare: n/a (no builder/template change; the pak route consumes the
  same renderer).
- Stale-zip: `render.py` is a CLAUDE.md trigger file; the standing
  the reviewed change rebuild flag on this branch still applies. No `bundles/`
  manifest (top-level or `releases/`) carries a multi-kind dashboard, so a
  rebuild is byte-identical for every distributed zip and no
  `CURRENT_TEMPLATE_VERSION` bump is owed (`2026-08-24-2` stands).

### WARNING

1. `tests/test_dashboard_summary_for.py:257-333`: the fan-out is tested for
   Scoreboard and PropertyList on a single-adapter list only. Two behaviours
   the docstring at `render.py:1248-1254` promises have no test: a
   `summary_for` mixing adapter kinds (a spec fans only over its own
   adapter's listed kinds) and MetricChart fan-out. Both proven by hand
   this pass, but the adapter-kind filter at `render.py:1262` is exactly
   the line a later edit would simplify away, and no corpus dashboard
   reaches it. Add one test with a mixed-adapter list on a MetricChart
   (dimension 10; the render surface was untested when both escapes
   shipped).

### NIT

1. `render.py:1256`: the `self_provider` early return is unreachable
   through `load_dashboard` (`loader.py:1506` raises first). Fine as a
   fence for direct callers; worth one comment line so nobody "fixes" the
   loader gate away thinking the renderer covers it, or vice versa.
2. Scoreboard sends `limit=100` to `getTopImportantMetrics` (ground-truth
   doc, request section). The doc's `metricTotalCount` evidence (1, not 2)
   says the count is taken after kind filtering, so the limit should apply
   post-filter, but that was observed on a 2-entry list, not proven on a
   long one. Largest fanned Scoreboard on the corpus today is 81 entries,
   under the limit either way; a future many-kind dashboard with 4+ metrics
   on one Scoreboard crosses 100 pre-filter. Recorded for the next live
   pass, not a finding against this diff.
3. Standing since the third pass: `knowledge/context/investigations/recon_log.md`
   modified and uncommitted on the branch.

### If shipped as-is

A dashboard bound to K kinds renders each metric K times in the zip and
the pak; on any bound kind's Summary page the server keeps that kind's
entries and hides the rest, so the operator sees one tile per authored
metric with values, on every kind, from one YAML file. Nothing changes for
any dashboard already in a distributed zip.

## Tenth pass, 2026-08-26: the reviewed change (mixed-adapter MetricChart test, self_provider comment)

Diff: `src/vcfops_dashboards/render.py` +3 comment lines at `:1256-1258`
(no code change; `git diff` over the reviewed change for `src/` is those three lines
only) and `tests/test_dashboard_summary_for.py:320-349`
`test_metric_chart_mixed_adapter_kinds`. Closes the ninth-pass WARNING and
NIT 1.

**Verdict: APPROVE.** 0 BLOCKING / 0 WARNING / 0 NIT new.

### Checks re-run

- Mutation: scratch copy of `render.py` with the adapter-kind filter at
  `render.py:1265` (`if ak == spec.adapter_kind:`) removed, so every
  listed spec fans over every listed kind regardless of adapter. Result
  on `tests/test_dashboard_summary_for.py`: **1 failed, 70 passed**, the
  one failure being the new test (first assertion, `resourceKindName`
  order). So the filter is now covered by exactly this test and by
  nothing else; the ninth-pass concern (a later edit simplifies the line
  away unseen) is closed. The test also pins summary_for order
  (HostSystem before VirtualMachine, the reverse of the spec's own kind),
  the pinned Datastore pass-through, the `resourceKindId` slots per
  adapter, and 4 unique entry ids.
- `.venv/bin/python -m pytest`: **1230 passed, 4 failed, 16 skipped**,
  127 deselected. Matches tooling. The 4 failures are the standing
  `test_common_doctor.py` venv/jmespath baseline, untouched by this diff.
- `vcfops_dashboards validate`: pass, 9 corpus dashboards listed.
- Render regression, `PYTHONHASHSEED=0`, the reviewed change source vs HEAD source
  through `load_all` + `render_dashboards_bundle_json` +
  `render_views_xml` over `content/` (19 views, 9 dashboards),
  `third_party/idps-planner/` (5 / 1) and a private third-party project (includes its git-excluded summary dashboard): all six outputs
  **byte-identical** (`cmp`). Expected, the src diff is comments.
- No restricted terms in the diff.
- `pak-compare`: n/a. `render.py` is in the diff, so the CLAUDE.md
  stale-zip rule triggers by filename, but the change is three comment
  lines and the render is byte-identical, so a rebuild would be
  byte-identical too; no `CURRENT_TEMPLATE_VERSION` bump owed
  (`2026-08-24-2` stands, as in the ninth pass).

### Comment accuracy

`render.py:1256-1258` says the loader rejects `self_provider` on
`summary_for` dashboards first and the renderer return is a second fence
for direct callers. Consistent with the ninth-pass finding
(`loader.py:1506` raises). Accurate, no drift.

### Standing

NIT 2 (Scoreboard `limit=100` post-filter behaviour) and NIT 3
(`recon_log.md` uncommitted on the branch) carry over unchanged.
