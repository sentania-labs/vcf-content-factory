# Framework review: dashboard, report and alert fidelity (2026-11-12)

- **Branch:** `tooling/dashboard-report-alert-fidelity`, base `origin/main`
  `3a4eadf5`. Commits `6093305e` (code + tests), `75fc327f` (docs),
  `ceb49e34` (reports loader merge prep), `1048d89a` (author prompts +
  content-model skill).
- **Area:** `src/vcfcf_core/dashboards/{loader,render,widget_versions}.py`,
  `src/vcfcf_core/reports/{loader,render}.py`,
  `src/vcfcf_core/alerts/{loader,render}.py`, `src/vcfcf_core/symptoms/loader.py`,
  `src/vcfcf_core/common/dep_walker.py`, `src/vcfcf_core/packaging/deps.py`,
  `src/vcfcf_managementpacks/sdk_builder.py`, `src/vcfcf_packaging/discrete_builder.py`;
  three new wire docs; four author prompts and the content-model skill.
- **Verdict:** CHANGES REQUESTED (2 BLOCKING, 8 WARNING, 9 NIT).

## Checks re-run

| Check | Result |
|---|---|
| Render regression, author's `regress2.py` run against an `origin/main` `src/` from `git archive` and against the branch (192 renders: content, third_party, test fixtures, the four pak clones with content, plain and pak path, per-alert / per-symptom / combined AlertContent) | `diff -r` **identical**, 0 load errors either side |
| Corpus search for every key the branch newly reads (structural scan of 289 YAML files under `content/`, `third_party/`, `bundles/`, `tests/fixtures/` and the compliance, synology, unifi, vsanperf clones) | No alert `wait_cycles`/`cancel_cycles` != 1, no widget `description`, no MetricChart/Pareto `refresh_content`, no Pareto `max_value`/bounds/`percentile_value`, no metric `link`, none of the other new keys, no `id:` on any alert or recommendation. One Section widget: `content/dashboards/summary_widget_smoke.yaml`, in no bundle and no pak. No registered pak ships a Section |
| Test suite, branch vs base (serial; `pytest-xdist` is not installed locally) | branch 14 failed / 3964 passed; base 14 failed / 3813 passed; **same 14 names** (jmespath, doctor venv, real-repo packaging validate) |
| Seven-package validate chain (`PYTHONPATH=src`) | all seven exit 0. Dashboards: 10 warnings, including the Section warning on `summary_widget_smoke.yaml`, which now names the dashboard |
| Non-pytest CI `test` steps | `path_reference_audit.sh` exit 0; `immutability_guard.sh --range 3a4eadf5...HEAD` clear; `vcfcf_dashboards validate --id-guard-baseline 3a4eadf5` exit 0; wheel build exit 0, wheel holds only `vcfcf_core/`, isolated import of the touched core modules OK; `check_framework_review.sh` warns until this file lands (non-blocking). Not run: SDK jar fetch, install.ps1 pwsh matrix |
| Trial merge, scratch worktree: branch + `origin/main` (`77aecc1d`, stock-id guard) + `origin/migration/vcf-cf-prefix` (PR 354) | **No conflicts.** Merged tree: 14 failed / 4134 passed (same 14), validate chain green. `alerts/render.py`: the explicit `id:` override still wins over the migrated `_alert_id`/`_slug(id_basis_name(...))`, and `test_pak_render_prefix_stable` passes. Stock-id guard on the merged tree: an alert with `id:` set to a stock alert UUID is refused by `vcfcf_alerts validate` (the guard reads rendered XML, so explicit alert and symptom ids are seen on every path that renders: validate, bundle, discrete, SDK) |
| Round trip (`rt_dashboards.py`, `rt_others.py`, `rt_mutation.py`) | Reproduced: dashboards 18/52 zero-diff, 49 with `adapterName` set aside, 3 differing only by stale navigation entries; reports 16/16; alerts 4/4 (recommendation 1/1); symptoms 2/2; SMs 2/2. Mutation: 3,770 dashboard mutations over **12** dashboards, 843 XML mutations over the 16 reports, 0 missed |
| Probes (synthetic YAML) | listed under each finding |

The defaults hold on every output path. A YAML that sets none of the new
fields renders byte-identically on the standalone content-import path and the
SDK pak path. No pak-local default leaks onto the global path (anchor
`00d3382`); `_oldest_supported_line()` is read only inside `sdk_builder`. No
key or label is derived from content (anchor `6c59f6b`); `{self}` expands to
the widget's own `widget_<dashboard id>_<widget id>`, and the Heatmap tab
`model_id` uses the tab index within its own widget.

## BLOCKING

### B1. `disable_in_base_policy` and `id:` on an alert are silently dropped by every bundle installer

`src/vcfcf_core/packaging/assembly.py:160-183` (`_render_alerts_payload`) and
`:394`, read by `src/vcfcf_packaging/templates/install.py:2254` (`_install_alerts`
→ `_alert_to_wire`, `:2368`) and `templates/install.ps1:3471`. The doc claim
is at `knowledge/context/wire-formats/alert_fidelity_wire_format.md:26-35`.
The prompt claim is `.claude/agents/alert-author.md` hard rule 6 ("REST sync
and bundle installs refuse it"). The `knowledge/context/README.md` index line
says the same.

The refusal lives in `AlertDef.to_wire()` (`alerts/loader.py:373`). Only
`vcfcf_alerts sync` / `handler.py` call it. The bundle builder never does: it
serialises alerts to `content/alerts.json` through `_render_alerts_payload`,
which writes a fixed key list without `disable_in_base_policy` or `id`, and the
installers POST that through their own `_alert_to_wire`. (Symptoms are
refused, because `assembly.py:391` calls `SymptomDef.to_wire()`.)

Probe: I set `disable_in_base_policy: true` and `id: <uuid>` on
`content/alerts/cluster_storage_path_inconsistency.yaml` in a scratch
worktree and ran `vcfcf_packaging build --no-live-describe
bundles/storage-path-monitoring.yaml`. It **built**. `AlertContent.xml` in the
zip carries `disableInBasePolicy="true"` and `AlertDefinition-<uuid>`.
`content/alerts.json` carries neither. So `install.py` / `install.ps1` ship
the alert **enabled** under a server id, and the drag-drop file in the same
zip ships it disabled. That is a silent downgrade on the main bundle install
path (dimension 8), and it contradicts the stated requirement "REST sync and
bundle install.py paths refuse it". The discrete and release builders share
`render_bundle_payloads`, so they have the same gap.

**Smallest fix:** in `render_bundle_payloads` (or `_render_alerts_payload`),
raise when any bundled alert has `disable_in_base_policy`, naming the file and
field, the same way symptoms already fail there. Add a test that builds
payloads for such an alert and expects the error. Correct the doc,
alert-author rule 6, and the README index line to name the bundle builder as
the refusing point. If you choose instead to carry the flag in `alerts.json`
and honour it in the installers (a policy PUT after create), that edits
`src/vcfcf_packaging/templates/`: `CURRENT_TEMPLATE_VERSION` must then be
bumped (dimension 9). An explicit alert `id:` on the REST path is fine to drop,
because the server assigns ids and the doc says so; only the disable flag
needs the refusal.

### B2. Explicit alert and recommendation ids have no uniqueness check; duplicates render, and one alert silently replaces the other on import

`src/vcfcf_core/alerts/loader.py:263-267` (format check only), `:496-503`
(recommendation key format only); `load_dir` `:668` and
`load_recommendations` `:515` check **names** only; render
`alerts/render.py:375` and `:555`.

Probe (merged tree): two alerts with different names and `id:` values that
differ only in case. `vcfcf_alerts validate` exits 0, and
`render_alert_content_xml` emits two `<AlertDefinition
id="AlertDefinition-02cb446d-...-e9bee94a5600">`. The loader lowercases
alert ids, so the case variant collides too. On content import the second
definition overwrites the first, and nothing reports it. The recommendation
key is free text, so it can also equal another recommendation's derived
`Recommendation-df-<kind>-<slug>`, or another explicit key: duplicate `key=`
in `<Recommendations>`, and every `ref=` resolves to whichever one wins. The
derived ids could not collide, because they come from distinct names. The
explicit-id feature brings the collision with it, so it has to bring the
guard. RULE-007 (`knowledge/rules/uuid-stability.md`): identity must be stable
and unique.

**Fix:** in `load_dir` and `load_recommendations`, collect the **rendered**
id (`AlertDefinition-<id>` or `_alert_id(...)`; `explicit_id or rec.id`) and
raise on a repeat, naming both files. Run the same check in
`render_alert_content_xml` (or in the SDK and bundle callers) across the
combined list, because a pak or bundle can mix directories. Add tests for a
duplicate explicit alert id, an explicit recommendation key equal to another
recommendation's derived key, and the same pair of checks for symptoms.
Symptom `id:` predates this branch and has the same gap, and the check costs
the same.

## WARNING

### W1. "Keys the old parser silently ignored now render" lists 6 of about 40, and one previously ignored key now fails to load

`knowledge/context/wire-formats/dashboard_fidelity_wire_format.md:21-25`;
`template_fidelity_wire_format.md:12-13`; `alert_fidelity_wire_format.md:13-21`.

The dashboard, report, alert and symptom loaders do not reject unknown keys,
so every newly read key was silently ignored before. I compared the keys the
base and branch loaders read. Dashboard: `time_range`, `disabled`,
`edit_allowed`, `doc_center_key`, `column_proportion`, `column_count`,
`omit`. Widget: `title_localized`, `ui`, `omit`, `tag_filter`,
`traversal_spec_id`, `old_metric_values`, `pin_resource`, `selected_tab`,
`metric_label`, `metric_unit`, `additional_columns`, `pin.traversal_spec`.
Metric entry: `label_localized`, `label_orig`, `metric_unit`, `def_unit`,
`resource_kind_name`, `omit`, and `unit: ""` (now `""`, was null). Heatmap
tab: `name_localized`, `name_orig`, `model_id`, `tag_filter`, `filter_mode`,
`custom_filter`, `omit`, `group_by.parent_text`. Report: CoverPage
`colorize`, `font_color`, section `omit`. Symptom: `omit`,
`disable_in_base_policy`, `symptom_def_type`. Alert and recommendation:
`id`. Two of them change identity or visibility on an admin's existing YAML.
First, `id:` on an alert or recommendation. The old prompts said "no
`id:`", but a value copied from REST output was harmless until now. It now
re-keys the object on the XML path: a pak upgrade leaves the old
definition and adds a new one. Second, `disabled: true`. A Dashboard
section's `colorize:` used to be ignored and is now a load error
(`reports/loader.py`, "colorize is not rendered on a Dashboard section").
That failure is loud, but it is a break all the same. No repo or pak YAML
sets any of these (I checked).

**Fix:** replace the list in all three docs with the complete set, mark the
two identity and visibility keys, name the Dashboard-section `colorize` load
error, and put the same list in the PR body.

### W2. The doc says buildkit 1.0.28 rejects fidelity fields; the old loader silently ignores almost all of them, and pak CI pins 1.0.27

`dashboard_fidelity_wire_format.md:33-34`; `.claude/agents/dashboard-author.md:120`.
`alert-author.md`, `symptom-author.md` and `report-author.md` say nothing about
the kit.

Probe against the base loaders, which match what kit 1.0.28 vendors. A
dashboard with `time_range`, `disabled: true`, `omit: [temporary]`, and a
widget `description` and `ui.height` loads without error. It renders
`states: []`, `disabled: false`, `temporary` present, no description, and
height 600. An alert with `disable_in_base_policy: true` and `id:` loads and
renders enabled under the derived id. The registered paks' CI pins
`BUILDKIT_TAG: sdk-buildkit-v1.0.27`. The official release path (RULE-012) is
that CI, so a pak author who uses these fields gets the fidelity locally and
a pak from CI with all of it dropped and no error. The Section gate does not
bind there either: its "Tier 2 pak build now fails" holds for the factory's
`build-sdk` only, until a kit carrying it is cut and the paks bump their pin.

**Fix:** correct both lines to "the older kit ignores them silently; the
Section gate and these fields bind the official CI build only from kit
\>= <next>". Add the same clause to the alert, symptom and report author
prompts. Either cut the kit with this PR, or have the PR body say no pak may
use the fields before the cut.

### W3. `omit:` entries carry no per-version evidence, and at least one is proven absent only on 9.1.1

`loader.py:2451` (`DASHBOARD_OMIT_KEYS`), `:2411` (`WIDGET_OMIT_KEYS`),
`METRIC_OMIT_KEYS`, `HEATMAP_TAB_OMIT`; doc table `dashboard_fidelity_wire_format.md:47-50`, `:143`, `:182`, `:198-200`.

Lesson `unknown-widget-type-aborts-pak-dashboard-import.md`: the 9.0.2
importer reads dashboard JSON with strict `getString`. One missing key
throws, aborts the whole dashboard, and install still reports FINISHED.
`omit:` removes keys the renderer always wrote. From the author's own
surveys (`dsurvey_818.out`, `dsurvey_902.out`): `temporary` is on all 163
dashboards on 8.18.7 and all 180 on 9.0.2. Its absence is seen only on
9.1.1 and on 11 third-party dashboards whose target build is not stated.
Whether 8.18 or 9.0 import a dashboard without `temporary` (or without
`namePath`, `widgetInteractions`, `alertDefinitions`, `paginationNumber`,
`selectFirstRow`, `subMode`, groupBy kind keys, `minValue`) is unproven. A
Tier 2 pak must import on 8.18.7 (RULE-019). Absent proof, that is a finding.

**Fix:** record, per `omit:` entry, the oldest corpus version on which the key
is absent. Run each entry not proven on 8.18.7 through the same mechanism
as Section: `Dashboard.widget_version_problems` (or a sibling) reports it, and
the Tier 2 pak build fails on it. Document the floor in the omit tables.

### W4. Widget-level fidelity errors do not name the file or the dashboard

`loader.py:4056` (`_fid_err`) and every `_fid_err` / `widget {id!r}:` raise in
`load_dashboard`. Probe via the CLI: `INVALID: widget 'app_allocation':
ui.height must be an integer >= 0; got -3`, with no path and no dashboard
name. The brief requires errors to name the file and field. Dashboard-level
errors do name `{path}`, so the two levels disagree. The branch adds about
100 messages of the widget kind (prior review N2 is the same class).

**Fix:** in `load_dashboard`, wrap the widget loop: catch
`DashboardValidationError`, then re-raise with a `{path}: ` prefix. The
existing `match=` tests use `re.search` and keep passing.

### W5. Report `view_id` / `dashboard_id` are unchecked; the stock baseline on `main` can check them

`reports/loader.py` (external branch of `load_file`);
`template_fidelity_wire_format.md:54-62`.

The doc is honest that nothing checks a typo'd id offline. After merging
`origin/main`, though, `src/vcfcf_core/stock_ids/stock_ids_baseline.json`
lists 771 stock view ids and 148 stock dashboard ids with the versions each
ships in. A typo, or an id present only on 9.1.1, produces a section that
renders blank. In a Tier 2 pak that also breaks RULE-019 on 8.18 and 9.0.

**Fix (after the main merge):** `vcfcf_reports validate` warns when an
external id is not in the baseline ("not a known stock id; if it is another
pak's object, ignore"). The SDK pak build warns, or fails, when the id is
missing from any line `_SDK_COMPAT_LINES` covers. Update the doc's "No walker
can check" sentence.

### W6. `render.py` and `alerts/render.py` changed: CLAUDE.md requires a full bundle rebuild, and nothing flags it

CLAUDE.md §"After tooling changes". None of the four commits or docs mention
it. The regression shows unchanged output, so the rebuild is a cheap
confirmation. No `CURRENT_TEMPLATE_VERSION` bump is wanted as the branch
stands, since templates are untouched. If B1 is fixed by editing the
installers, a bump becomes mandatory. **Fix:** the orchestrator delegates
the `content-packager` rebuild, and the PR body states "render output
unchanged (192-artifact regression); rebuild run; template version <bumped
| not bumped, templates untouched>".

### W7. Pre-existing: the alert XML path ignores `threshold_type` / `threshold_value` on non-SELF sets, in a file this branch edits

`alerts/loader.py:318` accepts them and `:453-456` puts them on the REST body.
`alerts/render.py` never reads them (`:408`: "aggregation=\"any\" attribute
is never emitted"). The defect is real. It does not undermine this branch's
round-trip claim: none of the 4 third-party alerts, and no repo or pak alert,
uses them (I checked). It is still loader acceptance without renderer support
on the pak path. Delegation rule 9 reserves follow-up issues for code the
branch does not touch, and the branch touches `alerts/render.py`. **Fix:**
render `aggregation` / `value` on the XML SymptomSet (built-ins carry 389,
per the author's survey), or raise in the XML renderer when either is set on
a non-SELF set. Nothing renders `negateCondition`, and no YAML field exists
for it, so nothing is silently dropped there.

### W8. `validate-sdk` reports the Section gate as a "localization check" load error and skips the rest of the bundled checks

`sdk_builder.py:2345` raises inside `_load_bundled_content`. `validate-sdk`
calls it inside the localization block and catches `SdkBuildError` at
`:5646` as `"bundled_content load error during localization check: ..."`.
Naming, `check_bundled_content`, and the view localization checks then never
run. So one Section dashboard hides every other bundled-content error until
it is removed. The gate message itself is actionable, and the build path
(`:4834`) is correct. **Fix:** collect version problems in
`_load_bundled_content` as a separate error list, or run the gate after the
load in both `build-sdk` and `validate-sdk`, so validate reports it under its
own label beside the other checks.

## NIT

- **N1.** `resource_kind_name:` on a metric entry is accepted on a resource-mode
  Scoreboard or MetricChart, and silently does nothing there.
  `render.py:1700` applies it only when the entry already has
  `resourceKindName`, and resource-mode entries never have it. Reject it
  when `metric_mode` is `resource`.
- **N2.** Explicit alert ids are lowercased (`alerts/loader.py:661`), while
  symptom ids are kept as written. `id:` exists to keep a source id byte for
  byte. Keep the case and compare case-insensitively in B2's check, or say in
  the doc that ids are lowercased.
- **N3.** `vcfcf_alerts validate` prints `ref={r.id}` (`vcfcf_alerts/cli.py:118`),
  which is the derived key even when `explicit_id` is set. The stock guard
  on `main` attributes recommendation locations by `o.id`, so a hit on an
  explicit key loses its file name. The cleaner fix: have
  `Recommendation.id` return `explicit_id` when set, and drop the
  `getattr(..., "explicit_id") or rec.id` pairs in `render.py:482`, `:555`.
  The stock baseline has no recommendation ids, so an explicit key equal to
  a stock recommendation key is not caught. Say so in the alert doc.
- **N4.** `widget_extra_metric_refs` (`loader.py:4248`) and the doc's
  §Dependency walkers say "every walker ... calls this". The `vcfcf_extractor`
  enablement walk (`src/vcfcf_extractor/extractor.py:1387-1410`) does not.
  It is harmless today, because its widgets come from `reverse.py`, which
  never fills the new fields, and the importer was left untouched by
  design. Reword to "every walker over loaded YAML", and name the extractor
  exception.
- **N5.** `dashboard-author.md:114` "Default time range: `time_range:
  last7Days`" reads as a default the factory applies, or one authors should
  add. Absent `time_range` renders no state, which leaves the product default.
  Reword to "To set the dashboard time range: `time_range: <value>`; leave it
  out for the product default". The doc's `disabled: true` row
  (`dashboard_fidelity_wire_format.md:42`) does not say what the flag does. In
  the light of anchor `00d3382`, state its effect (or that it is unverified),
  and add `disabled` to the prompt's "only to reproduce a source dashboard"
  caveat.
- **N6.** `symptom-author.md` rule 5 says "REST sync refuses the first two".
  The bundle builder also refuses them, because `assembly.py:391` calls
  `to_wire()`, so a bundle with such a symptom fails to build. Say so.
- **N7.** `dashboard_fidelity_wire_format.md:248-249`: the mutation check ran
  over 12 of the 52 dashboards, and its XML half covered the 16 reports, not
  the alerts or symptoms. State both scopes. The comparators are otherwise
  honest about what they set aside: ids renumbered by position, synthetic
  entries resolved, timestamps and users, whitespace (`" ".join(split())`,
  which also hides whitespace-only text changes; say that), key order.
- **N8. Follow-up issue, files not touched:** the staged-bundle audit
  (`src/vcfcf_core/packaging/audit.py:542-572`) reads `dashboardList` /
  `widgetList`. The renderer writes `dashboards` / `widgets`, so the audit
  extracts no dashboard keys at all. Confirmed. It does not undermine the
  new-surface coverage claim: that rests on `packaging/deps.py`
  `_refs_from_widgets` (the build-time describe-cache audit) and on
  `dep_walker`, both of which call the helper, and the doc says plainly
  that the JSON audit checks nothing. Separately,
  `discrete_builder._resolve_report_deps` walks a report's Dashboard
  sections through `_resolve_dashboard_deps`, which sees only View widgets,
  so super metrics on any other widget type of that dashboard, old or new,
  are not bundled with a discrete report.
- **N9.** A Pareto `additional_columns` entry accepts `metric_key:
  supermetric:"<name>"` and emits it verbatim. The column then renders blank,
  and the walkers treat it as a built-in key. Every other widget metric
  surface already behaves this way (a Scoreboard metric does the same), so
  this is consistent with the existing raw-key convention for widgets. A
  one-line reject of the `supermetric:` form in the two new surfaces would
  stop it spreading.

## Judged acceptable

- **`ui.states` passthrough.** Keys: a closed prefix list per type,
  enforced in `_parse_widget_ui` (`loader.py:4123`), which is the only place
  a `WidgetUi` is built. A probe with key `evil_`, an integer key, and a
  TextDisplay state was rejected; the renderer composes
  `<prefix>widget_<dash>_<widget>`, so YAML cannot choose the key.
  Values: the alphabet (`loader.py:2406`) excludes quotes, `<`, `>`, `&`,
  `=`, spaces and braces, and the JSON is built with `json.dumps`, so the
  document cannot be broken or given new keys. Double encoding
  (`%253Cscript%253E`) and `s%3Ajavascript%3A...` are accepted. ExtJS's
  state provider decodes values into types and does not evaluate them.
  Content authors already have arbitrary HTML through TextDisplay, so this
  is no new trust boundary. `{self}` is safe: braces are outside the
  alphabet, so the only way a value can contain `{self}` is as the token
  (a probe with `{selfx}` is rejected).
- **The Section gate default.** RULE-019 requires every Tier 2 pak to work
  on 8.18, 9.0 and 9.1, so a "this pak is 9.1.1-only" escape would
  contradict the rule. No escape hatch is the right default; changing it
  needs a rule change, not a flag. It fires in `build-sdk` and `validate-sdk`
  (see W8). Content bundles, discrete and release builds keep the warning,
  because they declare no target. No registered pak ships a Section today.
- **`adapterName` not modeled.** It records which solution owns an installed
  dashboard. The pak builder sets it from `owning_adapter_kind`, and letting
  YAML claim it would let content impersonate a pak. Correct.
- **Stale navigation entries not modeled.** They are keyed by widget ids that
  are not on the dashboard, so no widget can fire them. Correct to drop.
- **Report `localizationKey` not modeled.** A dangling key fails import on
  8.18 (DEF-018, RULE-019), and the factory ships no localization bundle for
  reports. Omitting it is the safe choice.
- **The three adjusted tests.** `test_dashboard_alertlist_relationship_mode.py`:
  Heatmap now accepts `children`, and `self` is still rejected with the
  new message. `test_dashboard_section_widget.py`: `collapsed` is now
  legitimate on ResourceList, so the negative case moved to
  ProblemAlertsList, which is still rejected.
  `test_dashboard_widget_min_version.py`: docstring only. None of the three
  was weakened.
- **Signatures.** No function signature changed. New dataclass fields are
  appended with defaults. `_fan_out_summary_specs` copies `MetricSpec` with
  `dataclasses.replace`, so the new fields survive summary fan-out. Nothing
  in `src/` introspects these dataclasses. The buildkit rewrite rule
  `from \.widget_versions import widget_version_problems` now matches twice
  (`re.subn` rewrites both), and the kit-isolation tests pass.
- **The two new metric surfaces, consumer by consumer.**
  `dep_walker.extract_refs_from_dashboards` (live pre-flight): yes.
  `dep_walker.collect_deps` (dashboard discrete builds, super-metric
  bundling): yes. `packaging/deps._refs_from_widgets` (describe-cache audit
  at build): yes. `render_dashboards_bundle_json` kind index (entries rows
  for additional-column kinds and tag-filter kinds): yes. The buildkit copy
  vendors `loader.py` and `render.py` but not the walkers, as before.
  `packaging/audit.py` reads nothing (N8, pre-existing). `vcfcf_extractor`
  is not reached (N4). The discrete report path does not reach it either
  (N8, pre-existing).
- **Report external ids in walkers.** `discrete_builder._resolve_report_deps`
  skips them. The SDK report embedding embeds only bundled views, so an
  external id passes through verbatim. The bundle loader has no "report
  view must be bundled" check that could misfire.
- **Third-party content.** Code, docs and tests cite source titles, keys and
  counts only (`vcom_522`, one instanced license metric key,
  `vCommunityCollectionWarnings`). The tests are synthetic ("Fidelity Probe",
  "Section Probe", generic VMWARE keys, fake UUIDs). No definitions are
  copied.
- **Prompts and skill vs code.** Accurate except as noted in B1
  (alert-author rule 6), N5, N6 and W2. `content-model` skill rows match the
  loader. The widget-type list in `dashboard-author.md` rule 5 matches the
  loader's supported types.

## If shipped as-is

An admin installing a bundle with `install.py` gets a "disabled in base
policy" alert enabled, while the same zip's drag-drop file ships it disabled
(B1). Two ported alerts given the same `id:` validate green, and one
overwrites the other on import (B2). Existing content renders unchanged.
