# Framework review: `import-local` offline converter (2026-11-13)

- **Branch:** `tooling/importer-fidelity` at `f15c536c` (with `origin/main` `a57cd618` merged), diff `origin/main...HEAD`
- **Area:** `src/vcfcf_core/importer/` (new), `src/vcfcf_extractor/importer.py` (new), `src/vcfcf_extractor/cli.py`, `src/vcfcf_packaging/loader.py`, `src/vcfcf_core/common/dep_walker.py`, `tests/test_import_local.py`, `knowledge/context/authoring/importer_offline_conversion.md`, `knowledge/context/defects.md` (DEF-019), the wire-format doc, `CLAUDE.md`
- **Verdict: CHANGES REQUESTED** (6 BLOCKING / 11 WARNING / 10 NIT)

The scan, the stock-id guard wiring, reference resolution through the id map
and drops, and the staged-load cascade are sound, and the four acceptance runs
reproduce. The comparator is good at what it compares: every YAML-side
mutation of a modeled field was caught (table below). The problems are what
it does not compare, what it hides once it has compared it, one class of
reference the id rewrite skips, a crash on product dashboards, and a
regression in the bundle-loader change.

## What I re-ran

| Check | Result |
|---|---|
| `scripts/path_reference_audit.sh` | clear (2 standing-exception warnings, same as main) |
| `scripts/immutability_guard.sh --range origin/main...HEAD` | clear |
| Core wheel gate | built; only `vcfcf_core/` + dist-info (all 11 `vcfcf_core/importer/*` files present); installed with `--target` and imported in isolation, including `vcfcf_core.importer.{convert,compare,inputs}`; no non-core imports in `vcfcf_core/importer/` |
| Seven-package chain (repo corpus) | all 7 exit 0 (`vcfcf_dashboards` with `--id-guard-baseline origin/main`) |
| pytest, full suite incl. slow (`-m ""`) | branch 20 failed / 4458 passed; `origin/main` 20 failed / 4402 passed; **identical failing names** (the author's 14 under default addopts plus 6 slow tests that need the gitignored `content/sdk-adapters/` clones) |
| `reverse-local`, same two pak dashboards, branch vs main | byte-identical YAML (`diff -r` clean); its code is untouched, the CLI only adds a subparser |
| Run (a) `--ids keep`, pak | rc 3, 120 stock ids, nothing written |
| Run (b) id map + drops, pak, `--target-min 8.18.7`, `--verify` | rc 1; 255 compared, 32,499 fields; 249 identical; 6 views only-documented; dashboards 52/52, reports 16/16, alerts 4/4, symptoms 10/10, 1 rec, 2 SMs |
| Run (c) same, third-party, no target | rc 1; 255 / 32,487 fields; same 249 + 6 |
| Run (d) 9.1.1 views + templates, `--ids mint` | rc 1; 757/851 views, 58/62 templates; 94 views fail on named gaps; 88 s |
| `validate-sdk` on (b) with the snippet's two settings | rc 1, exactly 2 errors: the two Section dashboards (version floor). Author's claim holds |
| Chain on (c) placed as `third_party/e1-port` in a scratch copy | only `vcfcf_dashboards` fails, on the 2 PROJECT-BOUNDARY unknown-SM lines the author names |
| Hand check of 25 objects from (b), independent script (no importer code) | 8 views, 8 dashboards (about 30 View widget references), 4 reports, 4 alerts with their symptoms and recommendations: every id is the id-mapped one, every in-set reference names the object whose *source* id it pointed at, dropped views are referenced by their original product id, names unchanged **except trailing whitespace stripped** (1 of 8 sampled views; W4). The 1 "problem" the script raised was the `--prefer-source alertdefs/` symptom choice, which is as requested |
| Stale navigation entries | 3 dashboards, 5 entries (one entry list is empty and counts 1): every key is a widget id absent from that dashboard and from every dashboard in the pack. `normalize_dashboard` sets aside only entries whose key is not one of the dashboard's own widget ids (`compare.py:241-249`), so it checks the condition and does not ignore navigation differences in general. A retargeted in-dashboard navigation is caught (mutation table) |
| Per-type dry runs on the other 9.1.1 export zips | DASHBOARDS: **crash** (B4); CUSTOM_GROUPS: rc 0, 0 found (W8); ALERT/SYMPTOM: clean failures with reasons |

Scratch harnesses (not committed): `mutate.py`, `srcmut.py`, `unread.py`,
`handcheck.py`, `safety.py` in the review scratchpad.

## Mutation self-test

**YAML side.** One change to one written YAML (a mapper bug), then the
importer's own `_verify` against the unchanged source. Run (b) options.

| Mutation | Result |
|---|---|
| view: drop a column | caught |
| view: change a column `yellow_bound` | caught |
| view: change a column `unit` | caught |
| view: flip a column `sort` | caught |
| view: change a filter operand | caught (also on a view with a documented loss, since its loss pattern did not cover `SubjectType`) |
| view: change description / time-window count | caught |
| view: two trailing spaces on the name | **missed** (whitespace set-aside, documented) |
| view: extra internal spaces in a column `display_name` | **missed** (whitespace set-aside, documented; a real wire change) |
| view with an "empty preferredUnitId" loss: change **another** column's `unit` | caught, but **classified "only documented losses"** (W1) |
| dashboard: move a widget, swap a View widget's view, change a widget title, Scoreboard `box_columns`, a metric label, TextDisplay html | caught |
| dashboard: retarget a navigation | caught |
| dashboard: invent an interaction (no deviation) | caught |
| dashboard with the `widget_interactions` target deviation: invent an interaction | **missed: counted identical** (B2) |
| dashboard: add a label to a raw-id navigation | not a comparator miss: the renderer drops `label` on a `dashboard_id:` navigation and the source has none |
| alert: drop a symptom; change a recommendation priority | caught |
| symptom: change the threshold; change `wait_cycles` | caught |
| super metric: change the formula | caught |
| report: swap a section's view; flip orientation; flip colorize | caught |

**Source side.** One change to a scratch copy of the pack, full CLI with run
(c) options, `--verify`.

| Source mutation | Result |
|---|---|
| widget `config.refreshInterval` 300 to 999 (mapper never reads it) | verify DIFFERS; **no LOSS line**; without `--verify` it is dropped silently (B6) |
| widget `config.isUpdatedView` changed | same as above |
| navigation `widgets[].interactionType` changed | same as above |
| time-interval-selector `visible` flipped | same as above |
| extra attribute on `DataProvider` | **missed: identical, no LOSS** (B3) |
| extra attribute on `ViewDef` | **missed** (B3) |
| `localizationKey` added to a column `displayName` Property | **missed** (B3) |
| extra attribute on a column `Item` | **missed** (B3) |
| extra attribute on a `Usage` element | **missed** (B3) |
| extra attribute on `Title` | verify DIFFERS (`Title@`); no LOSS line |

**Mutation classes it misses:** whitespace inside or around any string;
any attribute on `ViewDef`, `DataProvider`, `Item`, `Usage`; any `Property`
attribute other than `value` (so column `localizationKey`); `Control`
attributes other than `visible`; a second Control of one type; `Presentation`
children beyond their count; anything under a `--target-min` deviation's wire
key anywhere in the object; `config.widgetId` (replaced by a placeholder on
both sides and not counted).

## Unread source keys

Instrumented mapper run (pure-Python ElementTree with tracked attribute and
text reads, tracked JSON dicts; a subtree copied whole into the YAML counts
as read). Counts are objects. Only objects that mapped are counted.

**Third-party pack** (189 views, 52 dashboards, 16 reports, 4 alerts, 10 symptoms, 1 rec, 2 SMs mapped):

| Type | Unread path | Objects |
|---|---|---|
| view | `Control@id`, `DataProvider@id` | 189 (renumbered, set aside) |
| view | `Control@visible` (read only for pagination) | 189 |
| view | `Item/Value/Property@localizationKey` | 9 |
| view | `Item/Value/Property@name`, `@value` (nested) | 2 |
| report | `Section/ContentKey#text` (CoverPage / TOC constants) | 5 |
| dashboard | `config.title`, `config.refreshInterval` | 52 |
| dashboard | `config.refreshContent` | 47 |
| dashboard | `config.isUpdatedView` | 44 |
| dashboard | `config.customFilter.{filter,includedResources,excludedResources}` | 29 |
| dashboard | `config.filterMode` | 20 |
| dashboard | `config.resource{,.id,.resourceId}` | 16 |
| dashboard | `config.depth`, `config.relationshipMode`, `config.resInteractionMode`, `metric.resourceKindMetrics[].id` | 14 |
| dashboard | `resourceKindMetrics[].{yellow,orange,red}Bound` (colorMethod not 0), `config.{metricLabel,metricType,metricUnit,selectFirstRow,showMetricLabel,sortBy}` | 11 |
| dashboard | `config.tagFilter` (and `.path`, `.value.{adapterInstance,adapterKind,bus,collector,day,exclaim,healthRange,maintenanceSchedule,state,status,tag,tier}`) | 3 to 10 |
| dashboard | `config.filterOldMetrics` | 8 |
| dashboard | Heatmap `configs[].{attributeKind,mode,relationalGrouping,thenBy,groupBy.{id,originalText,parentId,type,resourceKind}}` | 4 to 6 |
| dashboard | `dashboardNavigations.*[].widgets[].interactionType` | 13 dashboards |
| dashboard | stale navigation entries' `id`, `widgets` | 3 (noted, set aside) |
| alert, symptom, recommendation, super metric | none | |

**9.1.1 export** (761 views, 62 reports, 103 dashboards, 1233 alerts, 1202 symptoms, 8 SMs mapped; 3 dashboards crashed, B4):

| Type | Unread path | Objects |
|---|---|---|
| view | `Control@id`, `Control@visible`, `DataProvider@id` | 761 |
| view | `Item/Value/Property@localizationKey` | **549** |
| view | nested `Property@name` / `@value` | 6 |
| view | `BlacklistResourceKind@adapterKind`, `@resourceKind` | 3 (documented loss class) |
| report | CoverPage / TOC `ContentKey#text` | 55 |
| dashboard | 126 paths; same families as the pack, largest `config.title` 103, `config.refreshInterval` 102, `config.refreshContent` 100, `config.isUpdatedView` 91, `config.resource.resourceId` 76, `config.customFilter.*` 71, `config.depth` / `filterMode` 55, `resInteractionMode` 53, `resourceKindMetrics[].{id,bounds}` 48 to 50, `tagFilter.value.*` 20, `additionalColumns` 16, `metric.subMode` 8 | |
| alert, symptom, super metric | none | |

Most dashboard keys are constants the renderer writes, which is why the pack
verifies identical; the mapper never checks that the source holds the
constant, so a non-default value is caught only by `--verify` (B6). The column
`localizationKey` is neither read, reported, nor compared (B3).

## BLOCKING

**B1. `--ids mint` / `--id-map` leave super metric references in symptoms and
view filters on the old id.** `rewrite_ids` returns for every type but
dashboards (`convert.py:607-610`); the symptom mapper copies the condition
key verbatim (`alerts.py:85`), the view filter mapper copies `metricKey`
verbatim (`views.py:128`). Proven: a symptom on `Super Metric|sm_<A>` with
SM `A` in the set, `--ids mint`: the SM gets a new id, the symptom keeps
`sm_<A>`, **rc 0** without `--verify`; the only signal is a WARNING calling
it "free text the converter does not rewrite" (`convert.py:650-651`). The
symptom then watches a super metric that does not exist. (Proven for symptoms; the view-filter case is by code reading: the same verbatim copy, and nothing else rewrites it.) The how-to says
"every reference is rewritten consistently" (lines 94-98). RULE-002 (a
reference that points at nothing). Fix: rewrite `sm_<uuid>` of in-set super
metrics in every string of every type (symptom condition `key`, view
`subject.filter[].metric_key`, `metric_to_relate_with`, the TIME_POINT
siblings), and make a surviving old id of an in-set object a failure of that
object, not a warning. Test it for symptoms and view filters under `mint` and
`--id-map`.

**B2. A `--target-min` deviation hides every difference that shares its wire
key, anywhere in the object, and the object counts as identical.**
`importer.py:546-552` drops any difference whose path matches
`[.@/]<key>(\b|$)` for any deviation key of the object, before the identical
count. Proven: in "Overall Daily Check" (the `widget_interactions`
deviation) an invented interaction is counted identical. Keys in use are
broad: `name` (`folder_in_name`), `label`, `unit`, `link`, `tagFilter`,
`customFilter`, `minValue`, `adapterKind` / `resourceKind`
(`group_by_kind_keys`), `ContentFormatting` for every report section, each of
which would hide value changes on every same-named path in that object. This
is the "a real difference hides inside a set-aside" case the brief asked
about. Fix: record the exact path each deviation produces (dashboard-level
`dashboard.<key>`, widget `widget[<i>:...]`, metric index, tab index, section
index) and the expected kind (`extra on render`, or for `folder_in_name` the
one value), and set aside only that path and kind. Add mutation tests that
change a same-named field elsewhere in a deviating object.

**B3. The view comparator and mapper share blind spots, so real source content
is dropped with an "identical" verdict.** `canon_view` (`compare.py:140-161`)
compares only `id` on `ViewDef`, only `dataType` on `DataProvider`, only text
on `Usage`, only `visible` on a Control, the first Control of each type, and
`Presentation` by child count; `_canon_prop` (`compare.py:105-118`) compares a
Property's `value` and ignores its other attributes and every `Item`
attribute. The view mapper reads none of these either. Proven by five source
mutations (table) and by the unread table: the column `displayName`
`localizationKey` is on 549 of 761 mapped 9.1.1 views and 9 pack views and is
dropped with no LOSS line and no difference. The renderer deliberately omits
it (`render.py:986-993`, the `6c59f6b` anchor), which is a fine decision but
must be a reported per-object loss, not a silent one. `canonical_key`
(`compare.py:362-363`) reuses `canon_view`, so two copies of one view id that
differ in any of these classes are merged as "the same" and the first copy
wins (proven for 8 classes, including a second time selector with other
values). Fix: canonicalize every attribute of every element except the
listed renumbered ids (which stay counted); in the mapper, route any
attribute it does not read through `loss_or_gap`; add "column displayName
localizationKey" to `DOCUMENTED_NOT_MODELED` with a per-object LOSS and the
how-to list (DEF-018).

**B4. A mapper exception that is not a `MappingError` aborts the whole run with
a traceback.** `map_all` catches only `MappingError` (`convert.py:332`). On
the 9.1.1 DASHBOARDS export: `AttributeError` at `dashboards.py:673` (AlertList
`alertDefinitions` as a list of id strings: "License Server Health", "vSAN
Snapshots and Replica") and `TypeError` at `dashboards.py:497` (MetricChart
`relationshipMode` a list: "vSAN Performance"). Nothing is reported, no
report is written, and the exit is Python's 1, the same code as a partial
result. Fix: accept the string form of `alertDefinitions`, test a list
`relationshipMode` before the dict lookup, and catch `Exception` per object in
`map_all` as a Failure (`mapper error: <type>: <msg>`, TOOLSET GAP) so one
object cannot stop the run. Add a fixture for each shape.

**B5. The bundle-loader change breaks a third-party project report that names
a cross-linked factory view.** `vcfcf_packaging/loader.py:70-77` now resolves
a `PROJECT.yaml`'s report sections only against the project's own `views/`
and `dashboards/`. A project may depend on factory views it lists under
`cross_links.views` (`project.py:35-37`, `CrossLinks`). Proven with a scratch
project whose report names `[VCF CF] Application Allocation Summary` and lists
it in `cross_links.views`: `load_bundle` succeeds on `origin/main` (section
resolves to `8580e840...`) and raises `BundleValidationError` on the branch.
No project in the repo has reports today, so no current output changes, but
this is a loader change that refuses content that loaded before (dimension 4).
Fix: resolve against the project's own folders first and fall back to
`content/views` / `content/dashboards` (at least for names listed in
`cross_links`), and test both the own-view and cross-link cases. Document the
change in the module docstring as both, not as a replacement.

**B6. Without `--verify`, source keys the mappers never read are dropped
silently.** The dashboard widget mapper has no unknown-key or constant check
below the dashboard level (`dashboards.py:259-357`; the top level has one at
:159-166), the report mapper ignores CoverPage / TOC `ContentKey`, and the view
mapper ignores `Control@visible` except for pagination. Each relies on the
renderer emitting the same constant and on `--verify` noticing when it does
not (source mutations above: four classes DIFFER under verify with no LOSS
line). `--verify` is optional, so the default run converts a dashboard with a
non-default `refreshInterval`, `tagFilter.value.tier`, `interactionType` or
`isUpdatedView` and exits 0 having changed it. The requirement is "nothing
skipped silently". Fix, either: run verification by default (it costs 16 s on
the pack; keep `--no-verify` with a loud "unchecked" line and a non-zero exit
unless `--allow-partial`), or add per-widget-type known-key and
renderer-constant checks that report a LOSS or stop with a TOOLSET GAP.

## WARNING

**W1. Documented-loss classification by path regex is too broad**
(`model.py:44-59`, `importer.py:553-557`). Proven: on the view with an "empty
preferredUnitId" loss a unit change on another column is reported "only
documented losses". `conditionId` / `metricValue.values` map to `SubjectType`
(any subject or filter difference); "absolute-date time range" maps to
`\.states` (any widget state); "Property related" maps to `related` (any path
containing it). The object still exits 1, but the summary line tells the
operator the difference is accepted. Fix: tie each loss to the exact path it
explains (column index, SubjectType index, state key).

**W2. A widget above the declared target floor is "converted" and can exit 0.**
With `--target-min 8.18.7` a Section dashboard is listed as converted, gets
only VERSION lines, and exits 0 without `--verify` (proven, pak layout, rc 0);
with `--verify` the pak refusal is a PAK CHECK that `--allow-partial` accepts
(`importer.py:802-805`). `test_target_min_drops_newer_omit_and_lists_the_deviation`
asserts rc 0 for exactly this. Fix: when `--target-min` is given, count such a
dashboard as failed (or a separate non-acceptable class), and never let
`--allow-partial` accept a pak-check failure.

**W3. `external_views` is recorded and never read** (`dep_walker.py:950`). The
discrete builder (`discrete_builder.py:517`), composer (`composer.py:275`) and
navigation walk (`navigation.py:65`) used to fail on a raw view id and now
build silently, shipping a dashboard that needs a view on the target, with no
line naming it and no stock-id reference check (validate runs one,
`vcfcf_dashboards/cli.py:219-225`; builders do not). The "own view by raw id
is an error" half is not a new break (main already errored as unknown view).
Fix: print each external view id the callers saw, and run
`report_reference_warnings` on them in the builders.

**W4. Name whitespace is changed silently and the collision check is
inconsistent.** Views and reports strip titles (`inputs.py:152,157`,
`views.py:351`, `reports.py:28`; 12 pack views end in a space); dashboards are
not stripped (`dashboards.py:123`) but the dashboard loader strips
(`dashboards/loader.py:5253`), so "X" and "X " pass the collision check at
`convert.py:430-451` and collide after load. The comparator's whitespace
collapse and `_expected_xml` setting Title to the new name hide the change.
Fix: strip every name once, before the collision check, and note each changed
name per object.

**W5. `--ids mint` is not repeatable** (`convert.py:102`, `uuid4`). Two runs on
the same input gave the super metric different ids (`5e774c17...`,
`5fdf724c...`); a second import then creates duplicates (RULE-007). Fix:
document "rerun with `--id-map <report-dir>/id_map.tsv`", and refuse or warn
when `--out` already holds an `id_map.tsv` and `--ids mint` is given.

**W6. A write failure leaves a half-written tree and a traceback**
(`importer.py:168-212`). Proven with a read-only `views/`: `PermissionError`
traceback, exit 1 (the partial code). Fix: stage the whole tree beside `--out`
and rename, or catch `OSError` as a usage-class exit with an `INCOMPLETE`
marker in the report dir.

**W7. `--force` leaves files it did not write in the type folders, and the
layout loaders load them** (`importer.py:171-177`). Proven: a stale
`views/stale.yaml` stays, the third-party loader then refuses the tree, verify
compares nothing (rc 4). Fix: list every pre-existing file under the folders
the run writes, and verify only the written set or refuse.

**W8. Unsupported content types are passed over with a reason that says there
is no definition.** The 9.1.1 CUSTOM_GROUPS zip: "JSON with no dashboard or
super metric definition", 0 found, rc 0 (`inputs.py:211-232`). The factory
has a custom group type. Fix: recognize custom group files and report "N
custom groups: not converted (unsupported type)" with a non-zero exit, and say
so in the how-to.

**W9. The report loader is quadratic and dominates run time.**
`reports/loader.py:330-360` rebuilds the view and dashboard name index by
parsing every YAML on each `load_file`; run (d) through the real third-party
loader: 174 `load_file` calls, 131,719 `yaml.safe_load` calls, 268 of the
profiled run's seconds. Existing code that this change exposes; the importer
cannot fix it in its own files without bypassing the real loader it is meant
to use (its staged load already uses stubs). Follow-up issue: build the index
once per directory per `load_bundle` / `load_dir` (CLAUDE.md delegation rule
9: code the branch does not touch).

**W10. Test gaps.** No test for `--report-dir`, `--dry-run`, `--project-name`,
a second `--ids mint` run, SM rewrites outside dashboards (B1), the cross-link
report (B5), the 9.1.1 dashboard shapes (B4), deviation scope (B2), or loss
scope (W1); and no mutation self-test of `--verify`. The tests do drive the
real CLI and the real loader per layout (no production-unreachable helper
arguments, the PR 356 defect), and the fixtures are synthetic ("Probe" names,
one stock id from the committed baseline). Fix: add the cases above, and a
parametrized mutation test over the YAML-side classes in the table.

**W11. Docs overstate.** How-to lines 94-98 (B1); lines 222-237 omit the
set-aside and blind-spot classes in B2, B3, W1 and the uncounted `widgetId`
placeholder; the limits do not state "no mutation self-test". DEF-019's
narrowing note (`defects.md`) says `--verify` "reports any remaining
difference per view", which B3 disproves. Fix the wording after the fixes,
and list every remaining blind spot as a limit.

## NIT

1. `convert.py:680-681`: `e.deviations[-1].text += "(the dashboard name then carries its folder)"` lands on the wrong deviation when another entry follows `folder_in_name`. Visible in run (b): it is appended to the `temporary` line of "vSphere Cluster Capacity 2.0".
2. `convert.py:208-210`: slugs `con`, `nul`, `aux`, `com1` and the like are reserved file names on Windows (proven: `views/con.yaml`, `views/nul.yaml`). Suffix them.
3. `importer.py:192-196`: `--report-dir` into an existing directory overwrites `report.json` / `id_map.tsv` without a word (proven).
4. `inputs.py:188`: JSON duplicate keys are last-wins with no report (proven: `"name"` twice). Use `object_pairs_hook` and report it.
5. `inputs.py:101-115`: a well-formed XML declaring `ISO-8859-1` is CANNOT READ. It is reported, so not silent; honor the declaration.
6. `inputs.py:146-148,178-179`: a policy file is listed twice (policy element, then "no content definition element").
7. `convert.py:341-345`: a `--rename` row keyed by name renames objects of every type with that name. Document it or key by type.
8. Billion laughs and an external entity were refused (expat 2.7.4, no file read). That protection depends on expat 2.4.1 or later; product exports carry no DOCTYPE, so refusing any DOCTYPE would make it independent of the host's libexpat.
9. `compare.py:219-220`: `config.widgetId` is replaced by a placeholder on both sides and not counted, against the "each counted and printed" rule.
10. `convert.py:262-266`: `--prefer-source` matches a substring of the absolute location across every duplicate group, so a fragment that happens to occur in the input root path matches every copy. Match against the path relative to the input root.

## Things checked and found sound

- Stock-id guard: runs on the plan in every mode and layout, with rendered alert/symptom ids (`importer.py:159-164`), and again on the loaded tree under `--verify`; `--id-map` onto a stock view id exits 3 in pak and third-party layouts (proven). Super metrics and recommendations are reported as unchecked by the baseline, honestly.
- Path safety: file names come from `slug()`, `[a-z0-9-]` only, at most 80 characters, collisions suffixed case-insensitively; `../../x`, `a/b\c`, a 300-character name and three names slugging to `same-name` all landed inside `--out` (proven). Archive member names are only labels; nothing is extracted. A symlink loop in an input directory did not hang (Python 3.14 `rglob`).
- Zip limits reuse the stock-id guard's (`_MAX_ZIP_DEPTH`, `_MAX_MEMBER_BYTES`, encrypted members); depth and broken-member tests exist.
- References: by name inside the set, raw id outside where the schema has one, failure where it has not (alert to symptom or recommendation), failed targets cascade (`convert.py:419-488`), all confirmed by the hand check. Id-map entries are type-blind, but a by-id collision within a type fails and cross-type id identity has no wire effect.
- Staged load cascade (`importer.py:287-349`): a refused object and every object naming it are reported as FAILED with the loader's message and counted, so `--allow-partial` does not drop them quietly.
- No distribution zip changes: no renderer, template, builder or assembly file changed, so neither a `content-packager` rebuild nor a `CURRENT_TEMPLATE_VERSION` bump is needed; no project or bundle in the repo has a report the B5 change affects.
- CLAUDE.md "Offline import" line: accurate.

## If shipped as-is

An operator who mints ids gets symptoms watching super metrics that no longer
exist with exit 0, a `--target-min` run reports dashboards identical that are
not, column localization keys and several view attributes vanish with an
"identical" verdict, a product dashboard export crashes the run, and a
third-party project report that names a cross-linked factory view stops
loading.
