# Framework review: migrator M4b, preview and the selection page

- Repo: `content/migrator` (vcf-cf-migrator), branch `feat/m4b-preview-and-page`, 4 commits over `main`, not pushed
- Reviewed: 2026-09-14
- Spec: `knowledge/designs/content-migrator-v1.md` (Preview; Shape; Repo, two tiers of test material; M4)
- Prior rounds: `migrator-m4a-tree-and-build-2026-09-14.md`, `migrator-m3-skeleton-2026-09-14.md`
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 7 WARNING, 6 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | 251 passed, 0 failed, none reading `corpus/` |
| hostile-export injection scan, preview, 20 objects x every kind | 0 raw injections |
| hostile-export injection scan, selection page, every panel and error path | 0 raw injections |
| same-origin, all 13 POST endpoints, over a real server | evil Origin 403, spoofed Host 403, suffix Origin 403, `null` 403, both good origins 303 |
| bind address | `127.0.0.1` only; GET `/..` 404; unknown POST path with good Origin 404 |
| preview over all 802 corpus objects in all five zips | 0 errors |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345, and a foreign TZ + locale | byte-identical on all five corpus zips and the fixture |
| select-all round trip, five corpus zips | 802 items, documents 0 missing / 0 changed / 0 extra (752 + the 8.x and scott-b document/item gaps already explained in M4a) |
| container shapes on select-all | only `configuration.json`, already settled in M4a; M4a's B4 (`ruleNameToTemplateNameMap`) is fixed, `notificationrules.json` now byte-identical |
| bundle reproducibility, two processes a second apart | byte-identical on all five |
| page-built bundle vs CLI-built bundle | byte-identical on all five |
| zip validity with the fixed timestamp | `unzip -t` clean on all five; every entry `(1980,1,1,0,0,0)`; mode bits and compressor unchanged from the previous `writestr(str)` path |
| closure audit, every node as a seed | 802 seeds, 0 unclosed |
| over-carry audit, one bundle built and read back per seed | 802 seeds, 0 over-carried, 0 under-carried |
| corpus-check | exit 0, 5 ok lines |
| corpus leak scan, 1886 corpus uuids + all 8-hex prefixes + 951 distinctive display names, every blob in every branch revision | 0 hits |
| em-dashes | none, in added lines or anywhere in the tree |
| widget census | 13 handled, 22 types met, 9 unhandled, exactly as claimed |

Author claims confirmed as stated: sha256-derived mock values, cross-process byte
identity, 13 laid out and 9 named, text markup escaped, same-origin on all 13,
127.0.0.1 only, no external resource, 802 objects with zero errors, page bundle
equals CLI bundle, the fixed-timestamp reason, closure 802/0, over-carry 802/0.
One claim did not hold: see N3.

## BLOCKING

### B1. Seven of the thirteen widget renderers have no test coverage, and nothing can tell

The milestone's headline is "13 widget types laid out specially". The committed
fixture carries five: `View`, `Scoreboard`, `ProblemAlertsList`, `TextDisplay`,
`Geo` (the last as the unhandled case). CI runs on the fixtures alone (spec,
"Repo": "CI runs on these alone"), so these renderer functions are executed by
nothing, ever:

`_widget_metricchart` (and its `SparklineChart` alias), `_widget_pareto`,
`_widget_heatmap`, `_widget_propertylist`, `_widget_resourcelist`,
`_widget_healthchart`, `_widget_section`.

Measured: `preview.py` is at 75% statement coverage under the suite, and the
uncovered runs are exactly those functions (lines 431-479, 494-496, 511-527,
568-573). Those seven cover 304 of the ~840 widgets in the corpus, including
every `MetricChart`, `ParetoAnalysis`, `Heatmap`, `PropertyList` and
`ResourceList` an admin will actually meet.

The author verified them by hand over 802 objects, and I reproduced that run with
zero errors, so this is not a claim that they are broken today. It is that the
next change to `preview.py` has no gate: a renderer that starts drawing the wrong
thing, or throwing, ships green on both the suite and CI. That is precisely the
shape of the factory's two named escapes (`00d3382`, `6c59f6b`): a render surface
with no test, where the wrong output still looked plausible.

`HANDLED_WIDGETS` already exists for this and is read by nothing (W4), which is
the fix and the seam in one place.

Fix: put one widget of each remaining handled type into the fixture dashboard, and
assert `set(HANDLED_WIDGETS) - met_types == set()` so a new entry in
`WIDGET_RENDERERS` fails the suite until the fixture covers it. Same
derive-do-not-hand-copy shape the repo already uses in
`tests/fixtures/ci_checks.py`.

## WARNING

- **W1. A widget outside the declared grid is silently squashed into a sliver.**
  `preview.py:_widget_cell` clamps `x` to the column count and then clamps `w` to
  what is left, with no note. In the corpus, `Rubrik/Rubrik Overview` (present in
  both `prod-9.1.1.0` and `devel-9.0.2.0`) has an `AlertList` at `x=13 w=6` on a
  12-column dashboard; the preview draws it at column 12, span 1. Fourteen more
  widgets (the factory's own capacity dashboards, `x=2 w=12`) lose a column the
  same way. The preview's own stated rule is that a plausible-looking wrong is
  worse than nothing ("drawing a Geo widget as a bar chart would be worse than
  drawing nothing"), and a full-width alert list rendered as an unreadable column
  is that. Fix: when a widget's `x + w - 1` exceeds the column count, add a note
  naming it, the way unhandled types are named.

- **W2. The preview does not tell the admin that heights are not the export's.**
  The banner says "Every value below is made up ... Names, titles, columns and
  keys are the export's own", which reads as: the layout is the export's. It is
  not; height comes from content by deliberate choice, so a widget the source
  gives 14 rows to sits at the same height as its neighbours and the vertical
  proportions of the dashboard are the preview's invention. The choice is right
  (see the judgment calls below); the silence about it is not. Fix: one clause in
  the banner, "widths and order are the dashboard's own, heights are this page's".

- **W3. `uipage.py`'s "No script, no external anything" is not true.** Line 367
  emits `onchange='this.form.submit()'`, an inline handler, on every checkbox in
  the tree. `test_the_page_carries_no_external_resource` asserts only that
  `<script` is absent, so it passes over an inline handler and the false claim
  survives. The behaviour is fine (the add/remove button submits the same form, so
  the page does degrade with JS off). The claim is not. Fix: narrow the docstring
  to "no script file and no external resource; one inline submit handler", or drop
  the handler and let the button carry it.

- **W4. `HANDLED_WIDGETS` is dead, so `ac95899` did not do what its message says.**
  The commit is "derive the handled widget list from the renderer table" and the
  comment says "derived from the table above so the two cannot disagree". Nothing
  reads the constant, and the hand-typed list of 13 names still sits in both
  `README.md` and `CHANGELOG.md`, free to drift from `WIDGET_RENDERERS` exactly as
  before. Fix: consume it (B1's assertion is the natural consumer), and let the
  docs name the count rather than re-type the list.

- **W5. `corpus-check` does not run `preview`.** The spec's second tier is the
  local regression run whose output goes in the PR body, and `check_one` now does
  inspect, tree, build, document identity and container shape, but not the command
  this milestone adds. The 802-object preview run the PR will cite is a one-off
  script the author wrote and nobody else can re-run. Fix: render every node in
  `check_one`, count errors, and add the total to the ok line.

- **W6. The 13-endpoint cross-origin test carries a hand-maintained list.**
  `test_every_endpoint_refuses_a_cross_origin_post` parametrizes a literal list of
  paths. A fourteenth endpoint added to `do_POST` is unguarded by this test and
  nothing says so. This repo already learned the lesson one directory away:
  `tests/fixtures/ci_checks.py` exists in full because a hand-copied count went
  stale. Fix: derive the path list from one place both the handler and the test
  read, and assert the test's set equals it.

- **W7. "accepts a post from itself only" overstates what the check is.** README
  and the settings panel both say it. The Origin check is a CSRF control: it stops
  another web page in the admin's browser from driving the port, and it does that
  correctly on all 13 endpoints. It is not an access control, because any process
  on the machine can set the header, and `/open`, `/build`, `/settings` and
  `/corpus-check` between them read and write arbitrary paths as the admin. On a
  single-user workstation that is the accepted model; the sentence should say so
  rather than imply an authorization boundary. Fix: one line, "a same-origin check
  stops another web page from driving it; it is not an access control, and any
  process on this machine can reach the port while it is running".

## NIT

- **N1. Reproducibility is per-platform, not absolute.** `containers.zip_entry`
  fixes the timestamp but `zipfile.ZipInfo.__init__` sets `create_system` to 0 on
  Windows and 3 elsewhere, so a bundle built by the Windows binary differs in
  bytes from one built by the Linux binary for the same selection. Not a
  regression (the old `writestr(str)` path had it too) and the claim in CHANGELOG
  says only "two builds of one selection", which is true. Worth one clause so an
  admin comparing hashes across the three shipped binaries is not surprised.
- **N2. `_widget_cell`'s docstring claims 8.x exports carry widgets with no
  coordinates.** Zero of ~840 widgets across all five corpus zips, the 8.18.7
  included, lack `gridsterCoords`. The fallback is worth keeping; the claim about
  the corpus is not supported by it.
- **N3. The 0.03 to 0.10s per action figure is the common case, not the range.**
  Measured on `scott-b` (430 objects): open 0.20s, tree render 0.009s, select-all
  0.005s, toggle 0.007s, but the worst dashboard preview render is **0.339s**
  (`Custom Dashboards/Datastore Details v2`, 14 widgets, most of them embedded
  views each of which re-scans every container). Still fine to use. The PR body
  should quote the worst case.
- **N4. `cmd_preview` does not guard the write.** `out.write_text` on an
  unwritable path gives a traceback, where every other refusal in this CLI gives a
  message and an exit code. The page's `build` guards `OSError` and says "cannot
  write"; the CLI's `build` has the same gap, so this is consistency rather than
  regression.
- **N5. `_strip_tags` is a depth counter, not a parser.** A `>` inside an
  attribute value ends the tag early and leaks attribute text into the shown text,
  and HTML entities are not decoded, so `&amp;` would display literally. Neither
  occurs in any corpus text widget (checked: 0 of them). Escaping is unaffected;
  this is readability only.
- **N6. A multi-tab dashboard would show `tab <tabId>`, a raw identifier.** No
  dashboard in any of the five corpus zips has more than one tab, so the path has
  never run against real data. Either read the tab's name out of the document or
  say in the heading that the id is all the document gives.

## The five judgment calls

| Call | Verdict |
|---|---|
| Widget height from content, not the export's row span | **Ship.** A clipped widget cannot be recognised, which defeats the only purpose the preview has, and columns and order (the things that identify a dashboard) are preserved exactly: I diffed three real dashboards widget by widget and every column and span matched the document. Ship it with W2's one clause. |
| Mock rows carry only the columns the view defines | **Ship.** Anything else invents a column, which is the one thing the module's own rules forbid. |
| AlertList standard columns | **Ship.** The widget genuinely has no per-instance column definition, the three headings are the product's own, and the frame says so in its own footer ("standard alert list columns; the export defines none"). Real alert names are used where `alertDefinitions` carries them. This is the honest version. |
| A shared uuid is refused in preview rather than picked | **Ship.** `cmd_preview` refuses and prints the exact spellings that name one object, which matches the M4a position that the tree is where ambiguity is reported. Note the inner `_find_node` still takes the first match when resolving a reference inside a formula or a widget; that is documented and correct, since repeating the ambiguity inside a formula would bury the formula. |
| Fixture growth | **Change**, and this is B1. The fixture grew, but not along the axis that matters: it covers 5 of the 22 widget types met in the corpus and 5 of the 13 the renderer claims. Growing it by seven more widgets is the cheapest fix in this review. |

## Settled, not findings

- **Injection.** I built a hostile export whose every name, title, column heading,
  description and key carries `<script>alert(1)</script>"><img src=x
  onerror=alert(1)>`, a bare single quote, an ampersand, U+202E and a 300
  character run, injected XML-escaped into the XML members and JSON-escaped into
  the JSON members so every document still parses and the parser hands the raw
  payload back. Rendered all 20 objects as standalone preview pages and drove the
  whole selection page over them: tree rows, `title=` attributes, aria labels,
  hidden form values, the anchor id, the filter echo, the selection textarea, the
  build report, the listing, the tree output, the error messages, and a build to
  an output path that is itself a script tag. Zero raw markup reached the DOM on
  any path. `html.escape` defaults to `quote=True`, so the single-quoted
  attributes in both modules are covered, and `_resolve_formula` escapes before it
  substitutes, which is the one place the order could have gone wrong and did not.
- **Path handling.** `_anchor` reduces to alphanumerics and dashes, so the `303`
  `Location` header cannot carry a newline; GET serves only `/`; POST to an
  unknown path is 404 after the origin check, not before. Reading and writing
  admin-named paths is the tool's job, and the only exposure is W7's wording.
- **The fixed timestamp.** 1980-01-01 is the earliest a DOS timestamp can express
  and the entries are otherwise identical to what `writestr(str)` produced (mode
  `0o600`, deflate); `unzip -t` accepts all five bundles. No importer reads the
  stored time. The live import proof is still M5's job, per the spec.
- **The coordinate convention.** Worth stating because it is the `00d3382` shape:
  gridster `x` is 1-based in all five corpus zips (439 widgets at `x=1`, none at
  `x=0`) and `gridsterMaxColumns` is 12 on every one of the 136 dashboards. The
  renderer treats `x` as 1-based on the single path all callers share, so there is
  no per-export convention to leak. The only departure from the export's own
  numbers is W1's clamp.
- **M4a's findings.** B3 (the symptom to super metric edge) holds: 802 seeds, 0
  unclosed. B4 (`ruleNameToTemplateNameMap`) holds: the 8.18.7
  `notificationrules.json` now round trips byte for byte. W1 (`corpus_check`
  blind to containers) is fixed: `container_shapes` is compared and the ok line
  reports it.
- **Leak discipline.** Nothing from the corpus is on this branch. The scan built
  its needles from the corpus rather than from memory, per the guard recorded in
  the spec.

---

# Round 2

- Branch `feat/m4b-preview-and-page`, now 6 commits over `main` (`ac95899`,
  `40a550c`, `0a82d54` are new), not pushed
- Reviewed: 2026-09-14
- Verdict: **APPROVE** (0 BLOCKING, 1 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | 274 passed, 0 failed |
| coverage | preview 90%, uipage 99%, ui 83%, mockdata 96%, total 89%: the author's four figures exactly |
| preview.py uncovered lines | 66, every one an absent-field or parse-failure fallback; no renderer body uncovered |
| B1 gate, by construction | added a 14th entry to `WIDGET_RENDERERS` with no fixture widget: `test_every_widget_type_the_preview_claims_is_exercised` goes red, naming it |
| renderer mutation test, all 11 renderer functions | 10 of 11 detected by at least one test; `_widget_section` not (see N7, it is a deliberate no-op) |
| corpus render, every dashboard in all five zips | 148 dashboards: 7 widened, 0 clamped, every widening noted |
| `Rubrik/Rubrik Overview`, both zips, emitted HTML read | `grid-template-columns:repeat(18,1fr)`, AlertList at `grid-column:13 / span 6`, widening named in the notes |
| W6 gate, by construction | added a 14th entry to `ui.ACTIONS`: `test_the_cross_origin_test_covers_every_endpoint_the_server_has` goes red |
| origin check placement | `do_POST` checks origin before `ACTIONS.get`, so a new endpoint is covered structurally, not only by the test |
| W3 gate, by construction | a second single-quoted inline handler fails the suite; a double-quoted one does not (W8) |
| `.coverage` in history | absent from every commit of every ref; gitignored; present only as an ignored working file |
| corpus leak scan, 881 generated needles vs all 310 blobs in all refs | 1 real hit, on the stale `feat/m3-skeleton` branch only, not on `main` and not on this branch, not on the remote (N8) |
| closure + over-carry, every node as a seed, bundle read back | 802 seeds, 0 unclosed, 0 over-carried, 0 under-carried |
| determinism | bundles and the concatenated previews of all five zips byte-identical across processes with `PYTHONHASHSEED` 0 vs 12345, `TZ=Asia/Kathmandu`, `LC_ALL=tr_TR.UTF-8` |
| page bundle vs CLI bundle | identical sha256 on all five, and identical to the determinism run's hashes |
| `corpus-check` | exit 0, 5 ok lines, 83+83+158+48+430 = 802 objects previewed |
| CI chain, run locally end to end | listing, preview, build, bundle listing all pass; `actionlint` clean |
| hostile export through the new renderers, DOM-parsed | 22 pages, 0 injected tags, 0 event attributes, 0 external URLs |
| preview pages over the corpus | 802 pages, no `<script>`, no `<img>`, no `@import`, 0 `href=`; the 8 `https://` hits are the export's own escaped text |
| em-dashes | 0 in the tracked tree |
| tree card | `430 object(s): 214 that nothing else points at, listed first, and 216 reached only as a dependency`, heading present, per-kind `56 of 181 here` and halves summing to 181 |

## Round 1 findings

- **B1 resolved.** The fixture carries a widget of every one of the 13 types,
  the set assertion is real (proved by adding a renderer and watching it go
  red), and the parametrized assertions are not tautologies: mutating each
  renderer to return a fixed string reddens the suite for 10 of the 11
  functions. The one exception is `_widget_section`, which is a deliberate
  no-op whose body `_widget_cell` discards (N7).
- **W1 resolved, and better than asked.** Nothing in the corpus clamps at all
  now: 7 dashboards widen, 0 clamp. `Rubrik/Rubrik Overview` draws 18 columns
  with its AlertList at its declared column 13 span 6, which is the third of
  the width the document gives it, and the widening is named.
- **W2 resolved.** "Widget widths and order are the dashboard's own; widget
  heights are this page's", asserted on both halves.
- **W3 resolved in substance.** The docstring, the README and the settings
  panel all say one inline handler; the no-JS path is asserted (each
  checkbox's form still carries its button). The guarding test has a hole: W8.
- **W4 resolved.** `HANDLED_WIDGETS` is consumed by B1's assertion, and the
  hand-typed 13 names are gone from both `README.md` and `CHANGELOG.md`; the
  CHANGELOG names the count and points at `preview.WIDGET_RENDERERS`.
- **W5 resolved.** `corpus-check` previews every object, reports the count per
  zip, and returns `error` naming the object on any failure. 802 across five,
  exit 0, reproduced.
- **W6 resolved, twice over.** One `ACTIONS` table, `POST_PATHS` derived from
  it, the test asserting its own list equals both, and the origin check sitting
  ahead of dispatch so a new endpoint is guarded before anyone writes a test.
- **W7 resolved.** README, the `ui.py` module docstring and the settings panel
  all say CSRF control, not access control, and that any process on the machine
  can reach the port.
- **N1, N2, N4, N5, N6 resolved.** `create_system` pinned to 3 with the reason;
  the unsupported 8.x coordinate claim dropped; `preview` and `build` refuse an
  unwritable path with a message and exit 1; `_strip_tags` is an `HTMLParser`
  with `convert_charrefs`; a multi-tab dashboard names the tab where the
  document names it and says the id is all there is where it does not.
- **N3 is a PR-body item and cannot be closed here.** The worst-case figure
  (0.339s, `Custom Dashboards/Datastore Details v2`) appears in neither README
  nor CHANGELOG, which is correct, since it was never a docs claim. It has to
  land in the PR body.

## WARNING

- **W8. `test_the_only_script_on_the_page_is_the_checkbox_submit` only sees
  single-quoted handlers.** `tests/test_ui_selection.py:241` matches
  `\son([a-z]+)\s*=\s*'([^']*)'`. I added `onclick="this.form.submit()"` to
  `_button`, so every button on the page carried a second inline handler, and
  the whole suite stayed green (55 passed). This is not hypothetical quoting:
  `uipage._button` already emits `class="{klass}"` with double quotes, so the
  next handler written in this file's own local style slips the gate that was
  added to catch it. Fix: match either quoting and the unquoted form, e.g.
  `\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)`, and assert the single allowed
  pair after stripping the quotes.

## NIT

- **N7. The `Section` row of the parametrized renderer table asserts a class
  the cell sets, not anything the renderer emits.** `("[Fixture] Second half",
  "pv-section")`: `_widget_cell` picks `pv-section` from `widget_type ==
  "Section"` and then discards the renderer's body outright, so
  `_widget_section` is the one function whose mutation leaves the suite green.
  Nothing is wrong (the renderer is a deliberate no-op), but the test's
  docstring, "each renderer puts the export's own label or key on the page", is
  not true of that row. Either say so in a comment or assert the frame rather
  than the renderer.
- **N8. The corpus value the M4a review found is still alive on a stale local
  branch.** `0c44e115-dc21-4ea5-8a56-01c22f18325b` (the prod marker's owner
  uuid) is in `tests/fixtures/make_export_fixture.py` at commit `7e6b0f9`,
  reachable from `refs/heads/feat/m3-skeleton` and its stale
  `refs/remotes/origin/feat/m3-skeleton`. It is **not** public: `git ls-remote
  --heads origin` shows `main` alone, and it is on neither `main` nor this
  branch, so the design note's rewrite did what it claimed. But the guard the
  note describes scans every revision, so it will keep hitting this forever,
  and a push of that branch would republish the value. Fix: delete the local
  branch and `git remote prune origin`. Outside this diff; a follow-up, not a
  gate on this PR.
- **N9. CI's console-script preview renders a view, not the dashboard.**
  `ci_checks preview-object` returns `view:<VIEW_IDS[0]>`, so the installed-binary
  pass exercises no widget renderer. The suite covers them and CI runs the
  suite, so nothing is uncovered; previewing the dashboard instead would make
  the binary pass cover the surface this milestone is about, for one changed
  string.

## What an operator would experience if shipped as-is

A correct preview and a correct selection page. The one live consequence of
W8 is on the next change, not this one: a future inline handler written with
double quotes would land without the page's "one inline handler" claim
failing, which is the same reports-green-while-broken shape the round 1
findings were about, one level up in the test rather than the code.

---

# Round 3

- Branch `feat/m4b-preview-and-page`, now 7 commits over `main` (`d28f3fe` is
  new), not pushed
- Reviewed: 2026-09-14
- Scope: Scott's two requirements ("We should never have an empty pre[view]",
  "We should also make sure the previews respect relationships") plus the three
  round 2 leftovers
- Verdict: **CHANGES REQUESTED** (2 BLOCKING, 5 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | 293 passed, 0 failed |
| state-3 widget census, my own count from the raw `dashboard.json` documents | 82 of 1017, and the by-type and by-reason breakdowns match theirs string for string |
| state-3 object census | 4 of 802, all four views in `scott-b` declaring no columns |
| no-config widgets, checked against every alternative place a config could hide | 49; the only widget keys in the whole corpus are `collapsed config gridsterCoords height id state states tabId title type`, and the `states` blob decodes to column widths and hidden flags, never a subject or a metric. Nothing is called empty because the tool could not read it |
| wiring census, my own count | 148 dashboards, 109 interaction driven, 585 receivers, 199 providers, 32 orphans, 117 context driven: their six figures exactly |
| `selfProvider` spellings | 0 flat, 919 nested, 98 absent; 674 resolve to `False`, 245 to `True`. The correction to my round 2 brief's premise is right, and the 674 figure is exact |
| the 32 "will never show data" | **27 of them are the dashboard's own selector, which drives everything else on the page.** See B1 |
| `dashboardNavigations` | 82 targets, 15 nested widget ids, 0 resolve against any widget id or dashboard id in any of the five exports. 6 of the 28 navigation keys also resolve to nothing, which they did not mention |
| state-3 wording, adversarial | 89 rendered boxes, 4 distinct reason strings, 0 containing `this preview`, `lay out`, `cannot`, `unable`, `unknown`, `unhandled`, `not implemented`, `no renderer` |
| provider and receiver badges, every wired widget in the corpus | 700 wired widgets, 0 blank titles, 0 ambiguous provider titles, so no badge can name the wrong widget |
| empty widget frames | 1017 frames, 0 with an empty body. The 17 that look empty to a crude scan are Section dividers carrying their heading, which is by design |
| branch coverage of the emptiness table, traced under the full suite | 3 of 9 object branches and 2 of 9 widget branches executed. See B2 |
| closure, every node as a seed | 802 seeds, 0 unclosed |
| over-carry and under-carry, bundle built and read back per seed | 802 seeds, 0 over, 0 under |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345, `TZ=Asia/Kathmandu` | previews and bundles of all five zips byte-identical |
| page-built bundle vs CLI-built bundle | identical sha256 on all five |
| `corpus-check` | exit 0, 5 ok lines, 83+83+158+48+430 = 802 objects previewed |
| W8 gate, by construction | `onclick="this.form.submit()"` added to `_button` in double quotes: the suite goes red naming it. Resolved |
| N7 | `test_the_section_renderer_draws_a_divider_and_nothing_else` asserts `WIDGET_RENDERERS["Section"](...) == ""`, the renderer rather than the frame class. Resolved |
| N9 | `ci_checks preview-object` returns the fixture dashboard and `check_preview` asserts `<polyline` and `pv-tiles`. Resolved |
| corpus leak scan, 1877 uuids + 108 dashboard names, every blob and every commit message on the branch | 1 hit, in a commit message. See W4 |
| em-dashes | 0 in the tracked tree |

The census numbers reproduce exactly. Everything Scott would read off the
"82 of 1017", "4 of 802", "49 / 32 / 1", "148 / 109 / 585 / 199 / 32 / 117"
and the twelve-line type breakdown is what the code computes. The problem is
not the arithmetic. It is what one of those numbers means.

## BLOCKING

### B1. 27 of the 32 "will never show data" widgets are the dashboard's own selector

This is the finding. The rule at `preview.py:1005-1019` is: a widget whose
`selfProvider` is false, that nothing on this dashboard feeds, on a dashboard
that wires other widgets, is broken and will never show data. It never asks
whether that widget is itself a **provider**.

On a real VCF Ops dashboard the selector at the top is exactly that shape. It
does not choose its own subject (`selfProvider: false`, it takes the dashboard
or the user's scope), nothing feeds it (it is the source), and it drives
everything below it. The rule classifies it as broken. Of the 32:

- **27 are providers.** `Select SQL Server Instance` (drives 9),
  `VMs (select VM here)` (drives 12), `Select a Scope` (drives 4),
  `Select an Application` (drives 4), `Select vSAN Cluster` (drives 2),
  `Scope (World / vCenter)` (drives 2), `Select vCenter or Datacenter`
  (drives 3), `Search for an incoming replicated VM to report its RPO
  violation count and transferred bytes` (drives 2), and the rest.
- **5 drive nothing** (3 distinct widgets: a Heatmap, a View, a Geo). Those
  are the only ones the claim fits.

The rendered page says both things in one frame. From
`prod-9.1.1.0`, `[VCF Content Factory] MSSQL Query Performance & Blocking`:

```
<h3>Select SQL Server Instance<span class='pv-flow drives'>drives 9 widgets</span>
    <span class='pv-type'>ResourceList</span></h3>
<div class='pv-nothing'><b>nothing to show</b>this widget takes its subject from
  another widget&#x27;s selection, and nothing on this dashboard feeds it while
  other widgets here are wired, so it will never show data</div>
```

and the wiring summary three lines above it reads
`Select SQL Server Instance drives Top Queries by Total Wait Time, ...`.
On `Custom Dashboards/VM Details v4` the notes do it in plain English:

```
- 12 of 13 widgets are driven by the object picked in another widget
  (1 widget(s) do the driving) ...
- 1 widget(s) wait on a selection that nothing on this dashboard provides,
  so they will never show data
- 1 widget with nothing to show: ... (VMs (select VM here) [View])
```

The one widget that does the driving and the one widget that will never show
data are the same widget.

Three things are wrong at once, and all three are load-bearing:

1. **It fails Scott's second requirement on the exact case it was written
   for.** "Respect relationships" and then getting the direction backwards on
   the widget the whole relationship hangs off.
2. **It tells Scott he has broken content that is not broken.** The brief says
   he will act on this. He would go looking at 32 widgets across 15 dashboards
   including four of the factory's own, and 27 of them are fine. Asserting a
   fault the source does not support is the `knowledge/rules/` no-fabrication
   line, and it is worse here than an omission would be, because it is
   confident and specific.
3. **State 3 suppresses the widget that most needs drawing.** `_widget_grid`
   replaces the body outright, so the selector's columns, its resource kind
   and its ordering are gone from the preview, on the one widget an admin
   would use to recognise the dashboard.

The module contradicts itself on the same page. For a receiver that **does**
have a provider, `preview.py:1023-1031` argues the opposite and is right:
"Mock values are shown rather than an empty frame ... a blank box shows
neither its columns nor its metrics. The label is what keeps that honest."
Every word of that applies to a receiver with no provider too.

Fix, smallest correct version, two parts:

- A widget that is itself a provider is never an orphan receiver. Gate the
  branch on `not feeds`. That takes the count from 32 to 5 (3 distinct).
- For the remaining genuine cases, keep the sentence but **draw the widget**,
  as a `pv-drivenby` caption above the rendered body, the way a fed receiver
  and a context-driven widget are already handled. Nothing is served by
  blanking a Heatmap that declares its colour and size metrics.

The corrected census for the PR body and the docs is **5 widget occurrences,
3 distinct widgets**, not 32. And a provider that takes its subject from
outside is worth its own sentence, since 27 widgets do it: it is how a
selector works, not a fault.

### B2. Nothing in the suite exercises the classification B1 gets wrong, or six of the nine object states the claim lists

I traced `preview.py` line by line under the full 293-test suite. Of the
emptiness table this commit is built on:

| Branch | Line | Exercised by the suite |
|---|---|---|
| view declares no columns | 1131 | yes |
| super metric, empty formula | 1152 | yes |
| group, no membership rules | 1446 | yes |
| dashboard, no widgets | 937 | **no** |
| alert, no state | 1255 | **no** |
| symptom, no state | 1324 | **no** |
| symptom, no condition | 1335 | **no** |
| recommendation, no text | 1378 | **no** |
| report, no sections | 1413 | **no** |
| rule, no conditions | 1498 | **no** |
| widget names no view | 727 | **no** |
| scoreboard / chart names no metric | 730 | **no** |
| pareto names no metric | 734 | **no** |
| health chart names no metric | 738 | **no** |
| heatmap, no colour or size metric | 742 | **no** |
| text widget, no text | 749 | **no** |
| section, no heading | 753 | **no** |

Three of nine object branches and two of nine widget branches run. The claim
lists all nine object cases as covered; the code has all nine, the tests have
three.

And the one branch that matters most is covered in a way that could not
catch B1. `test_a_receiver_nothing_feeds_will_never_show_data` pins the
fixture's `[Fixture] Orphaned trend`, which drives nothing, so it models the
5-widget minority case. No fixture widget is a provider with
`selfProvider: false`, which is 27 of the corpus's 32 and the case the rule
gets wrong. The gate exists and points away from the bug.

This is the round 1 B1 shape returning one milestone later: a new render
surface, verified by hand over the corpus, with no executable gate. Round 1
established the cure in this very file, `test_every_widget_type_the_preview_claims_is_exercised`
asserting `set(HANDLED_WIDGETS) - met_types == set()`. The emptiness table
and the wiring classes need the same treatment: a table of the reasons, a
fixture object or widget per row, and a set assertion so a new branch fails
the suite until it is covered. Add, specifically, a fixture widget that is a
provider with `selfProvider: false` and assert it is **not** state 3.

## WARNING

- **W3. The census counts export occurrences, not distinct content, and
  nothing says so.** Three dashboards appear in two zips each. Distinct:
  **118** dashboards not 148, **835** widgets not 1017, **27** no-config
  widgets not 49, **23** orphans not 32. The per-object numbers are right
  (a preview is per object per export, and the tool is correct to render
  each). The roll-up sentence is what misleads: Scott will read "82 of 1017
  widgets carry nothing to show" as an inventory of his estate and it
  overstates by about a quarter. Fix: state both, "82 widget occurrences
  across five exports, 55 distinct" (and recount after B1 lands).

- **W4. Three state-3 boxes render on dashboards and are not counted, so the
  roll-up note undercounts.** 85 `pv-nothing` boxes render across the 148
  dashboards; `empty_widgets` holds 82. The three come from `_non_list_view`
  called inside `_widget_view` (`preview.py:481`): an embedded view that
  declares no attributes draws "this image view declares no attributes, so it
  has nothing to chart wherever it is used" and never reaches
  `preview.empty_widgets`. On `Custom Dashboards/VM Rightsizing Details v5`
  two widgets say they have nothing to show and the notes say nothing at all.
  `_symptom_logic:1289` has the same shape on the object side. The commit's
  own promise is that "the notes count the empties". Fix: route both through
  the same accumulator the widget grid uses.

- **W5. README and CHANGELOG carry B1's claim verbatim** (`README.md`,
  "A widget that waits on a selection nothing on the dashboard provides,
  while other widgets there are wired, is state 3: it will never show data";
  `CHANGELOG.md`, the same plus "32 wired to nothing"). Both change with the
  code, and the wiring census line needs the distinct figures from W3.

- **W6. A corpus dashboard path is in a commit message on this branch.**
  `Rubrik/Rubrik Overview` appears in the body of `d28f3fe`. My leak scan
  (1877 corpus uuids plus all 108 dashboard names, against all 79 objects and
  all seven commit messages) found this one hit and nothing else; no tracked
  file leaks, and `main` is clean. But a commit message is history, the
  recurrence guard the design note describes scans every revision, and this
  repo is destined to be public. The branch is unpushed, so `git commit
  --amend` costs nothing today and a force-push and a conversation with Scott
  tomorrow. Fix now: reword to "one corpus dashboard has a Skittles widget
  with an empty config".

- **W7. "an alert with no state or no symptom sets" is half implemented.**
  Only the no-state case sets `empty_reason` (`preview.py:1255`). An alert
  that declares a State whose symptom sets are empty draws
  `_symptom_logic`'s box (1289) and is never counted as state 3, so it is
  absent from the object census. Either add the branch or drop the claim from
  the commit message, the README and the CHANGELOG.

## NIT

- **N10. 13 of the 199 wiring-summary lines repeat a receiver name.**
  `ResourceList drives Scoreboard, Scoreboard, MetricChart, MetricChart,
  MetricChart, MetricChart` on the MSSQL and Oracle dashboards, and
  `VMs (select a VM here...) drives Disk Usage (for selected VM), ...,
  Disk Usage (for selected VM)` on Troubleshooting VMs v4 and v5. The titles
  are the export's own and the badge is never wrong; the line just reads as a
  bug. A count suffix (`Disk Usage (for selected VM) x2`) fixes it.
- **N11. The coverage figure was not independently re-verified this round.**
  `coverage` is not installed in this environment, so the 89% claim stands
  on round 2's check. The branch-level trace in B2 is what I could measure,
  and it is the more useful number here anyway: statement coverage was high
  in round 2 while nine of the eighteen new branches run in no test at all.
- **N12. `dashboardNavigations`, my view: preview note now, follow-up issue,
  not a graph edge.** Confirmed: 82 targets and 15 nested widget ids, 0
  resolving to any widget or dashboard in any of the five exports, plus 6 of
  28 keys resolving to nothing (they reported the targets, not the keys). An
  edge is the wrong instrument, because the ids name nothing the graph can
  reach: 82 permanently unresolvable entries would be noise in the tree's
  missing list and would weaken the signal that list exists to carry. But the
  preview note is too quiet for something that silently drops navigation on
  15 dashboards, and it only appears to someone who previews that particular
  dashboard. It belongs in `inspect`'s output too, where it is seen before a
  bundle is built, and the real question (are these dashboards on the source
  instance that the admin did not select) is M5's, against a live import.
  Follow-up issue, named in the PR body.

## Scott's two requirements, assessed

| Requirement | Verdict |
|---|---|
| "We should never have an empty pre[view]" | **Met.** 1017 widget frames across the corpus, 0 with an empty body; 89 state-3 boxes, all four reason strings in the content's voice with no trace of the tool's; the three states are visually distinct and state 3 beats state 2. The census is honest about what it counts (W3, W4) and the branches are undertested (B2), but no box says nothing. |
| "We should also make sure the previews respect relationships" | **Not met.** The rendering of the relationship is good: the flow summary, the coloured edges, the badges and the "values stand for one object picked in X" caption are correct on every real dashboard I read, and no badge can name the wrong widget. But the classification built on top of it declares the dashboard's own driver broken on 27 of 32 occurrences, which is the opposite of respecting the relationship, and the notes say both things about one widget in the same breath. B1. |

## What an operator would experience if shipped as-is

An admin previewing `[VCF Content Factory] MSSQL Query Performance &
Blocking`, or any of the other fourteen dashboards with a selector, sees the
selector blanked out and labelled "will never show data" directly under a
badge saying it drives nine widgets. If they trust the preview they go and
fix fifteen dashboards that are not broken; if they do not trust it, they
stop trusting the state-3 box everywhere, including on the 49 widgets where
it is telling them something true and useful.

---

# Round 4

- Branch `feat/m4b-preview-and-page`, 8 commits over `main`, head `18dd3a1`, unpushed
- Reviewed: 2026-09-14
- Verdict: **CHANGES REQUESTED** (4 BLOCKING, 4 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **300 passed**, 0 failed |
| `preview.py` statement coverage | **92%**, as claimed (73 of 878 missed) |
| B2 mutation: a new code in each of the three tables, no fixture row | **all three gates fail by name** (`no fixture widget exercises: ['widget-brand-new-reason']`, `no fixture object exercises: ['object-brand-new-reason']`, `{'brand-new-kind'}`). Not tautologies: each compares the module constant against what the fixture actually produced. |
| corpus-check | exit 0, 5 ok lines |
| closure audit, every node as a seed | **802 seeds, 0 unclosed** |
| select-all round trip, five zips | documents byte-identical, containers unchanged (via corpus-check) |
| determinism, `PYTHONHASHSEED` 0 vs 12345 plus a foreign TZ | byte-identical bundles on all five |
| corpus leak scan, 1750 needles (full uuids, 8-hex prefixes, owner ids, names) over every tracked file **and all 8 commit messages** | **0 hits.** Round 3's W6 is fixed; the reworded history carries nothing. |
| em-dashes | none, in any tracked file or any commit message |
| selectors, corpus | 27 occurrences / 17 distinct, **every one captioned, none state 3** |
| never-shows, corpus | 5 occurrences / 3 distinct, **every one still drawn** under its caption |
| `inspect` navigation links | reported: 82 on `prod-9.1.1.0`, 0 elsewhere |

Round 3's B1 fix is real as far as it goes, and W4, W5, W6, W7 and the nits are done.
Four things do not hold.

## BLOCKING

### B1 (round 4). The 158 are overwhelmingly management-pack views, and calling them "nothing to show" is the same false alarm as calling a selector broken

Measured myself over all five zips: **155 widget occurrences name a view absent
from the export** (the other 3 of the claimed 158 are `widget-view-no-columns`),
across **99 distinct view uuids**. What those 99 targets are:

- **Zero** of the 99 is a view any of the five exports carries. Five exports,
  four instances, and not one holds these views. A CUSTOM-scope export (every
  corpus zip declares `type=CUSTOM` in its manifest) carries every custom view
  on the instance, so a custom view referenced by a custom dashboard would be
  there.
- **75 of the 99 distinct targets, 118 of the 155 occurrences, resolve to a
  `<ViewDef>` shipped inside a management pack in this factory's own reference
  repos.** Overwhelmingly `reference/references/vmbro_vcf_operations_vcommunity/`
  (`Management Pack/content/reports/View - Collection01.xml`, `View - Set 2.xml`),
  plus `dalehassinger_unlocking_the_potential`. Worked example: view
  `3a88e1a7-511c-440d-868b-65df4a2c7898`, named by 7 widgets on
  `vCommunity/ESXi Configuration 2.0`, is
  `<ViewDef id="3a88e1a7-511c-440d-868b-65df4a2c7898"><Title>vSphere Data Centers
  Inventory</Title>` in that pak.
- The remaining 24 distinct sit on product dashboards (`NSX-T/NSX Gateway
  Inventory`, `Protection and Recovery/Vsphere Replication`, `[Custom] Showback
  (Business Application)` and the cost dashboards). Our reference set holds
  community content, not VMware product paks, so absence from `reference/` is
  not evidence they are custom; their shape is the same as the 75.

So the honest reading of the 158 is: **almost none of them is a broken widget.**
They are dashboards that were cloned from or built on an installed management
pack, embedding that pak's views. On a target with the same pak they import and
render. On a target without it they do not, and the admin needs to install the
pak, which is a completely different action from "fix this widget".

What the tool does with that today, in its own voice, on
`vCommunity/ESXi Configuration 2.0`:

```
20 widgets with nothing to show: 1 where the view the widget names is not in
this export; 1 where the view the widget names is not in this export; ...
```

A twenty-widget working community dashboard, reported as twenty widgets with
nothing to show. This is round 3's B1 exactly: the tool telling Scott his
content is broken when it will import and work.

The tool **cannot** tell "absent because built in" from "absent and the target
will not have it" from an export alone, and it must therefore not imply it can.
It already knows how to say that, in `inspect`, one command away:

> `dashboard navigation links pointing outside this export: 82 (they will not
> land on the target unless it already has what they point at)`

and in `graph.MissingEdge`'s own docstring: *"Information, not an error: the
target instance may well already have the object."* The preview is the only
surface that contradicts them.

**What I would have it say instead.** Not state 3, and never folded into one
"nothing to show" total:

- Per widget, its own state, styled apart from the warn box:
  "this widget shows view `<uuid>`, which this export does not carry. A CUSTOM
  export carries only custom content, so a built-in or management-pack view is
  expected to be absent and the target will render it if the target has the same
  pak. If it was a custom view on the source, it was not exported and the widget
  will be empty there. This export cannot tell the two apart."
- Per dashboard, two counts, never added together:
  "3 widgets carry nothing themselves" (actionable) and "17 widgets show views
  this export does not carry (12 distinct); they will render on the target if it
  already has them."
- In the CHANGELOG, drop the 158 out of the empties sentence entirely and give
  it its own, with the distinct-view count, so Scott reads a pak prerequisite
  rather than an inventory of broken widgets.

> `src/vcfcf_migrator/preview.py:519` (`widget-view-missing`), `:1703-1715`
> (the roll-up), `CHANGELOG.md:40`.

### B2 (round 4). The badge still contradicts its own body, on the same dashboard as round 3, and the gate points away from it

Round 3's fix gated only the *never-shows* branch on `not feeds`. The emptiness
check `_widget_nothing` runs **before** the wiring block and is not wiring-aware
at all, so a widget that drives other widgets can still be state 3 by any of the
other nine codes.

Measured: **54 widget occurrences (48 distinct widgets on 27 distinct
dashboards) that drive at least one other widget are classified state 3**
(43 `widget-view-missing`, 11 `widget-no-config`). **24 of those render a frame
whose badge and body disagree**, on 19 distinct dashboards. Verbatim from the
rendered page for `[VCF Content Factory] MSSQL Query Performance & Blocking`,
which is the dashboard round 3 named:

```html
<h3>ResourceList<span class='pv-flow drives'>drives 9 widgets</span>...
<div class='pv-nothing'><b>nothing to show</b>this widget carries no
configuration at all, so it shows nothing on the dashboard either; it is
usually an unfinished leftover</div>
```

Same widget, same contradiction, new sentence. The affected widgets read like a
list of selectors: `Select a DC or World`, `Datacenters`, `Clusters Capacity`,
`NSX Gateways`, `NSX Segments`, `License Servers (select ...)`, `Data Centers`.

The new test does not catch it because it pins only the never-shows code:
`test_a_selector_is_not_called_broken` asserts `"[Fixture] Clusters" not in
titles`, and the fixture selector has a config, so it never meets the
`widget-no-config` or `widget-view-missing` path.

Fix: make the state-3 decision wiring-aware for **every** code, not one. A
widget that drives others is a selector; the sentence for it is about what it
selects, not about what it shows. And add the fixture case the gate is missing:
a selector whose emptiness code is `widget-no-config`, asserted not to be state 3.

> `src/vcfcf_migrator/preview.py:1085-1140`, `tests/test_preview.py:701-717`.

### B3. `widget-no-config` is a false statement about the content: VCF Ops stores some widget configuration in `states`, not `config`

`_widget_nothing` line 784 reads only `cfg`. The MSSQL `ResourceList` above has
`"config": {}` and a `states[0].value` of **4213 characters** of URL-encoded
column layout (`o:columns=a:o:id=s:h1^hidden=b:1^width=n:100^...` through h16 and
`resourceRating`). The tool says it "carries no configuration at all ... usually
an unfinished leftover". That is not true, and it is the sentence Scott is told
to act on.

Corpus: **29 of the 49 `widget-no-config` occurrences carry a non-empty `states`
blob; 24 carry one of 40 characters or more** (`ResourceList` 4213, `AlertList`
1060). The remainder (`MetricChart`, `LogAnalysis`) carry only a date-range
state, where "no metric chosen" is defensible.

This is the `6c59f6b` pattern: deriving a claim from one field without knowing
where the product actually writes the value. `widget-no-config` is the largest
bucket in the "31 unfinished content" figure, so the figure is wrong too.

Fix: before claiming no configuration, look at `states`. If a state blob is
present, the widget is configured and the honest sentence is that this preview
cannot decode the encoded state, which is state 2 (a fact about the tool), not
state 3.

> `src/vcfcf_migrator/preview.py:784-787`.

### B4. The corrected distinct census does not reproduce, and it moves when you change the order you read the zips in

I rebuilt the census four ways. **634 objects reproduces only under identity
`(kind, uuid, name)`**, which is not the stated rule:

| Identity | Objects | Widgets |
|---|---|---|
| `(kind, uuid or name)` | 632 | 832 |
| `(kind, uuid, name)` | **634** | **833** |
| `node.key` (uuid@owner) | 650 | 940 |
| `(kind, uuid)` | 602 | 832 |

Under the rule that produces 634, `self`=229, `selector`=17, `from-outside`=117
and `never-shows`=3 all match the claim, but **`fed`=467 not 469, widgets=833
not 835, and view-missing plus no-columns = 157 not 158.**

Two further problems with that rule:

- It is not "uuid, so one dashboard under two owners counts once": it counts an
  object twice when the same uuid carries two names. There are **two** such
  objects, not the one the brief names: dashboard
  `12e4af4c-...` (`Custom Dashboards/ESXi Host Certificates` / `ESXi Host
  Certificates`) **and** view `38957c6d-...` (`[VCF Content Factory] VM Snapshot
  Inventory` / `... v2`). The +2 on the object count is exactly those two.
- **It is order-dependent.** Dashboard `a04dfafe-... / Custom Dashboards/Cluster
  Details v2` exists twice in `scott-b` under two owners with **7 widgets in one
  copy and 9 in the other**, so "distinct" silently keeps whichever copy is read
  first. Reversing the zip order moves `widget-no-config` from **27 to 11** and
  `selector` from **17 to 20**. The headline "27 widgets with no configuration
  at all" is a property of iteration order, not of the estate.

No script in the repo produces any of these numbers; they are hand-derived and
nobody, including the author next milestone, can re-derive them.

Fix: commit the census as a script (next to `corpus_check.py`) so the number is
reproducible, define the identity rule to match what the script does, and where
two copies of one uuid differ, say so rather than silently picking one.

> `CHANGELOG.md:37-41`, `CHANGELOG.md:55-57`, `README.md` wiring paragraph.

## WARNING

- **W1. The N10 fix dedupes wiring receivers by title, so the summary now names
  fewer widgets than the badge counts.** `_wiring_summary` (`preview.py:958-964`)
  collapses on `wiring.title(receiver)`, which also collapses genuinely distinct
  widgets that share a title. On MSSQL the line reads `ResourceList drives
  Heatmap, MSSQL Top Queries, Scoreboard, MSSQL Wait Types, MetricChart` (5) next
  to a badge reading `drives 9 widgets`. **9 of 199 wiring lines** now understate.
  Round 3's N10 asked for a count suffix for a reason: dedupe on the receiver
  **id**, then suffix the repeated names (`MetricChart x4`).

- **W2. The state-3 roll-up groups on the full reason, not the short one, so it
  prints the same clause once per widget.** `preview.py:1704-1712` keys
  `reasons[reason]` on the uuid-bearing sentence and only then calls
  `_short_reason`. Result on `vCommunity/ESXi Configuration 2.0`: `1 where the
  view the widget names is not in this export` repeated twenty times.
  **14 of the 51 dashboards** that emit a note are affected. Fix: key the dict on
  `_short_reason(reason)`.

- **W3. Two of the three `widget-no-metric` branches are dead, and the CHANGELOG
  claims otherwise.** `coverage` puts `preview.py:805` (`ParetoAnalysis`) and
  `:810` (`HealthChart`) in the missed set, and the corpus reaches neither. The
  gate passes because a *sibling* branch (`Scoreboard`/`MetricChart`/
  `PropertyList`, line 800) emits the same code. The claim "Every one of those
  branches carries a code, and the suite asserts the fixture exercises all of
  them, so a new one fails until something does" (`CHANGELOG.md:33-34`) is true
  per code, not per branch, and three branches share one code. Either give the
  three branches distinct codes or soften the claim. (`:821`, the dict
  `editorData` path, is uncovered too.)

- **W4. The unplanned `graph.missing` change collapses nothing and has no test.**
  I counted unresolved `(node, ref)` pairs against `len(graph.missing)` on all
  five zips: **350 before, 350 after, zero rows collapsed**, because the dedupe
  key includes `via` and no corpus node names one absent target twice under one
  `via`. So the answer to "did it change the counts an admin sees" is no, and the
  answer to "is it exercised" is also no: `grep` finds no test for it. An
  unplanned behaviour change in the graph, landing in a preview commit, with no
  gate, is how the next regression gets in.

## NIT

- **N1. `widget(s)` in operator-facing prose**, four places
  (`preview.py:1037, 1692, 1696, 1701`): "1 widget(s) do the driving". The code
  already pluralises properly elsewhere (`f"{'s' if count != 1 else ''}"`).
- **N2. The repo now says two things about a missing edge.**
  `graph.MissingEdge`'s docstring: "Information, not an error: the target
  instance may well already have the object." The new dedupe comment three
  hundred lines down (`graph.py:740`): "which is one thing the admin has to fix,
  not two." Pick one voice; the docstring's is the correct one and is the same
  voice B1 needs.
- **N3. `gap not in graph.missing` is a linear scan inside the build loop**
  (`graph.py:743`), O(n^2) over up to 201 rows. Harmless today; a set of the
  tuples costs nothing and does not rot.

## What an operator would experience if shipped as-is

Scott previews his estate and is told that 189 widgets show nothing. 158 of
those are dashboards that came with the vCommunity, NSX-T and vSphere
Replication packs and will render perfectly on any target that has those packs;
the tool does not say so, and on `vCommunity/ESXi Configuration 2.0` it reports
all twenty widgets as having nothing to show. Of the 31 it calls unfinished, the
biggest single case is a `ResourceList` carrying four kilobytes of column
configuration that the tool did not look for, sitting under a badge that says it
drives nine widgets. And the census he would quote in a planning conversation
changes by more than half its value depending on which order the zips were read
in.

---

# Round 5

- Branch `feat/m4b-preview-and-page`, 10 commits over `main`, head `b1061bf`, unpushed
- Reviewed: 2026-09-14
- Verdict: **CHANGES REQUESTED** (4 BLOCKING, 7 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **312 passed**, 0 failed |
| census, recomputed from the raw documents by a reviewer-written walker that imports nothing from `vcfcf_migrator` | **every published figure reproduces**, see the table below |
| census order independence, real corpus, forward vs reversed | identical (occurrences aside) |
| corpus-check | exit 0, 5 ok lines, every object previewed, select-all round trips, documents byte-identical, containers unchanged |
| closure audit, every node as a seed | **802 seeds, 0 unclosed** |
| over-carry audit, bundle built and read back per seed | **414 seeds** (all of the three smaller zips, 100 sampled from each of the two large), **0 over, 0 under** |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 plus a foreign TZ | byte-identical select-all bundles on all five zips |
| page bundle vs CLI bundle | gated by `test_a_build_through_the_page_is_the_build_the_cli_writes` (fixture); not re-run over the corpus this round |
| gate mutations, 8 tried | 4 fail correctly, **2 stay green** (B3, W4), 2 inert |
| corpus leak scan, 1844 needles (uuids, 8-hex prefixes, owner ids, member tails, display names) over every tracked file, every branch blob and all 10 commit messages | **0 hits.** The one match is the phrase "Custom Groups", product vocabulary |
| em-dashes | none, in any tracked file or any commit message |

### The census, reproduced

My walker reads the zips with `zipfile`, enumerates objects from the member
layout, and re-implements the classification rules from the wording of the
code tables rather than by calling them. It agrees with
`tools/corpus_census.py` on every line:

| Figure | Script | Mine |
|---|---|---|
| objects / carrying nothing | 632 / 4, all `view-no-attributes` | 632 / 4, same |
| objects with two names | 2 | 2 (dashboard `12e4af4c`, view `38957c6d`) |
| dashboards / interaction driven | 118 / 86 | 118 / 86 |
| widgets | 835 | 835 |
| widgets carrying nothing | 11 (4 no-config, 3 never-shows, 3 columnless view, 1 no metric) | identical |
| content elsewhere | 111 view-not-carried, 4 state-not-read | identical |
| subjects | 469 fed, 154 self, 117 from-outside, 92 selectors, 3 never-shows | identical |
| divergent dashboards / subjects | 2 / 0 | 2 / 0 |
| divergent widgets | **15** | **15** |

Two notes on that. My first pass produced 630 objects and one two-name
object; both gaps were mine (I read `pluginConfig.name` where the export
writes `pluginName`, and a ViewDef's name from an attribute where it lives in
`<Title>`), and the script is right. And **the script prints 15 divergent
widgets, not the 14 the result block claims** (W5).

Identity and divergence rules, assessed: both are right for an admin reading
this as an inventory. `(kind, uuid)` falling back to `(kind, ident)` is the
only rule that survives the corpus, where one uuid legitimately carries two
names and one dashboard uuid legitimately carries two widget sets. **The
union rule on a divergent dashboard is correct and should not become
intersection**: the question an inventory answers is "what could I be asked
to carry", and intersection would silently drop a widget that exists on one
instance, which is the failure the previous four rounds were about. Union
plus a reported `divergent dashboards` count discloses it. The tie-break on
*classification* is the part that is wrong, W1.

### The 92 selectors: why the number moved, and whether the split is right

The definition changed from "feeds another widget **and** declares
`selfProvider: false` **and** is not itself empty" to "feeds another widget
and is not itself driven". Measured, the whole 17 to 92 move is that: 75
widgets left `self` for `selector`, and `self` fell 229 to 154 by the same 75.

**The split is right; the sentence attached to it is not.** Deciding a
selector from the wiring is correct, and it is what round 4 asked for: a
widget that provides a `resourceId` selection to another widget is the
dashboard's selector whatever its own config looks like. Verified against the
raw JSON on a sample: `[Custom] Showback (Business Application)` / `Select a
Group` drives four widgets by `resourceId`; `[Custom] Identify VMs on PG
Type` has three View widgets each driving the same
`ResourceRelationshipAdvanced`; `Fleet Capacity & Rightsizing` / `Cluster
Capacity Breakdown` drives three. None is a widget that merely happens to
feed something. Also correct: 64 widgets that both drive and are driven are
counted `fed` rather than `selector`, so "92 selectors" is not "156 widgets
that drive something", and under the heading "how widgets come by their
subject" that is the right call.

What is wrong is B1: **72 of the 92 declare `selfProvider: true`**, and the
caption tells the admin they choose no subject of their own.

## BLOCKING

### B1 (round 5). The selector sentence asserts the opposite of what 72 of the 92 selectors declare

`preview.py:1203` captions every selector:

> this widget chooses no subject of its own: it is the selector that drives N
> widgets on this dashboard

and `preview.py:1795` repeats it in the notes ("they choose no subject of
their own and drive the widgets below them"), as do `README.md:198` and the
CHANGELOG. Under the old definition that clause was true by construction,
because `_self_provider(cfg) is False` was part of what made a widget a
selector. It is no longer part of it, and the clause was not revisited.

Measured over the corpus, of the 92 distinct selectors: **72 declare
`selfProvider: true`**, 17 declare `false`, 3 say nothing. Raw evidence,
`prod-9.1.1.0`, `[Custom] Identify VMs on PG Type`, widget `VMs on Only NSX
PGs`: `"selfProvider": {"selfProvider": true}`, driving a
`ResourceRelationshipAdvanced` by `resourceId`. The factory's own surface map
says what that value means: *"`true`: widget fetches its own data (pinned to
a specific resource or resource kind, independent of other widget
selections)"*
(`knowledge/context/api-surface/widget_types_survey.md` §selfProvider vs
interaction-driven; see also `dashboard_selfprovider_pin_wire_format.md`).
The widget chooses its own subject **and** drives others. The page says it
does not choose one.

That dashboard's note reads, in full: "3 widgets on this dashboard are
selectors: they choose no subject of their own and drive the widgets below
them", when all three declare that they do. This is `6c59f6b`'s shape
exactly: an operator-facing claim derived without reading the field that
decides it, in a surface where the wrong answer still looks plausible.

Fix, smallest correct: the driving clause is unconditional, the subject
clause is conditional. "this widget drives N widgets on this dashboard: what
is picked in it sets their subject", plus ", and it takes no subject of its
own" only when `_self_provider(cfg) is False`. Same split in the note, the
README and the CHANGELOG.

> `src/vcfcf_migrator/preview.py:1199-1204`, `:1793-1797`, `README.md:198`,
> `CHANGELOG.md:64-66`.

### B2 (round 5). `widget-state-not-read` fires on an empty state object, so three widgets that carry nothing are reported as configured

`_widget_verdict` treats any non-empty concatenation of `states[].value` as
proof the widget is configured. Three widgets in the corpus have `config: {}`
and a single state whose entire value is `"o%3A"`, which unquotes to `o:`.

The factory's own wire-format note says what that is: the decoded value is
`o:columns=a: <col> ^ <col> ...`, where `o:` is the object marker and the
content is the column list
(`knowledge/context/api-surface/resourcelist_column_state_wire_format.md` §1,
"The `states[]` grammar (decoded)"). `o:` with nothing after it is an empty
state object: no columns, no settings, nothing.

The three are two `Heatmap` widgets and one `ResourceRelationship`, each with
no config at all. Each is told:

> VCF Operations stores this widget's layout in its saved state rather than in
> its configuration (4 characters of it), in a form this page does not decode,
> so the widget is configured and its shape is not shown here

They are not configured. A Heatmap with no config and an empty state blob is
the `widget-no-heatmap-metric` case these rounds have been about, and the
fix for round 4's B3 overshot into asserting the opposite. It also means
"widgets carrying nothing: 11" is low by up to three.

Fix: unquote the value (`urllib.parse.unquote`, repeatedly, as the doc's
grammar is multi-encoded) and require something after the `o:` marker before
calling the widget configured. Keep the test, add a fixture widget whose
state value is `o%3A`.

> `src/vcfcf_migrator/preview.py:290-297` (`widget_state_blob`), `:909-914`.

### B3 (round 5). The round-4 B2 fix has no gate, and the invariant it claims is not true by construction

Two separate problems, one cause.

**The fix is untestable as gated.** I deleted the wiring-aware short-circuit
(`_widget_verdict`'s `if feeds: return ("", "", "")`, `preview.py:907`) and
ran the suite: **312 passed, zero failures.** The regression that round 3 and
round 4 both caught can be reintroduced with the suite green. The reason is
the fixture widget that was added for it: `[Fixture] Bare selector` has
`config: {}` **and** a `states[]` blob, so with the short-circuit gone it is
caught by the state-blob branch and still never reads as empty. It proves
B3's fix, not B2's. Round 4 asked in as many words for "a selector whose
emptiness code is `widget-no-config`, asserted not to be state 3"; the widget
that was added cannot reach that code.

**The invariant is empirical, not structural.** The claim is that
`_widget_verdict` returns not-empty for any widget that feeds another "before
`_widget_nothing` runs, so the verdict is wiring-aware for every code". It is
wiring-aware for every code *that flows through `_widget_verdict`*. The
renderers can still raise a state-3 box for a feeding widget, and two of them
do. Both mutations are two-field edits to ordinary document shapes:

- a driving `Scoreboard` whose `metric` block lists no metrics: verdict is ""
  (it feeds), then `_widget_scoreboard` calls `_tiles([])`, which draws
  `nothing_here("this widget names no metric...")` under a badge reading
  `drives 1 widget`. It is also **not counted**: `_tiles` calls
  `nothing_here` directly rather than `_record_empty`, so the roll-up said
  "14 widgets with nothing to show" while 15 boxes were drawn, against the
  CHANGELOG's "The notes count every box the page shows";
- a driving `View` widget naming a carried view that declares no columns:
  `_widget_view` calls `_record_empty(..., "widget-view-no-columns")`, badge
  and body contradict, and this one *is* counted as state 3, so the same
  widget is a selector and an empty widget at once.

Verified clean on today's corpus (0 contradiction frames over 1109 frames,
0 uncounted boxes), which is why the assertion passes. But 11 feeding widgets
in the corpus already read empty by config alone and are saved only by which
renderer they happen to use. That is luck, and it is the `00d3382` /
`6c59f6b` shape: the gate proves absence on today's material rather than
preventing the class.

Fix: make the wiring-aware decision the only place a state-3 box can be
raised for a widget, or pass `feeds` into the renderer context and have
`_record_empty` and `_tiles` refuse to draw state 3 for a feeding widget.
Then add the two fixture widgets above, and keep
`test_no_frame_claims_nothing_to_show_while_claiming_to_drive_widgets`, which
will then have something to catch.

> `src/vcfcf_migrator/preview.py:894-916`, `:571-604` (`_widget_view`),
> `:548-560` (`_tiles`), `tests/test_preview.py:765-792`,
> `tests/fixtures/make_export_fixture.py` (the `Bare selector` widget).

### B4 (round 5). The census undercounts the one figure it exists to publish, by 43 widgets, using a different rule from the tool it inventories

`corpus_census.Census.add_dashboard` resolves a View widget's target only
when the widget does not feed another:

```python
if not verdict and widget_type == "View" and not feeds:
    verdict, code = self.view_verdict(graph, cfg)
```

The preview has no such condition: `_widget_view` runs for every View widget,
so a selector naming an uncarried view gets the "not shown here" box and is
counted in the dashboard's roll-up. Measured over the corpus: **155 distinct
View widgets name a view the export does not carry; 43 of them also drive
another widget.** The census publishes 111. The same report prints
"widgets showing a view the export does not carry: 155" in the occurrence
block and 111 in the distinct block, which reads as ordinary deduplication
and is not: 43 of the gap is a rule change between the two lines.

That number is the pak-prerequisite figure round 4's B1 created, the one
thing in this census an admin would act on, and it is 28% low. `elsewhere`
is not an emptiness claim, so recording it for a selector does not conflict
with "a selector is never empty".

Fix: drop `and not feeds` from that line. Expect 154 distinct
(155 less the one divergent widget that has a clean copy).

> `tools/corpus_census.py:147-149`.

## WARNING

- **W1. The census resolves a disagreement toward "fine" for widgets and
  toward "broken" for objects, and the direction is not stated.**
  `report()` takes `sorted(v)[0]` for a widget (the empty string sorts first,
  so a clean copy wins) and `sorted(v)[-1]` for an object (a code sorts last,
  so the empty copy wins). All **15** divergent widgets have one clean copy
  and one flagged copy, so all 15 resolve to clean: **10 `widget-state-not-read`
  and 4 `widget-no-config` widgets that the tool flags in at least one export
  never appear in the headline.** The true "flagged somewhere" counts are 15
  carrying nothing and 126 elsewhere, against the published 11 and 115. The
  docstring says the tie-break exists; it does not say which way it points,
  and it points two ways. Pick one direction, state it, and print both numbers
  if both matter.

- **W2. The census is a second implementation of the preview's classification,
  and it has already drifted.** `add_dashboard` re-derives the subject rule in
  one expression rather than calling the preview. It omits the preview's
  `not missing` guard on the never-shows branch, so a widget that is empty by
  config, declares `selfProvider: false` and is not driven would be
  `never-shows` in the census and `self` in the preview. Inert on today's
  corpus (occurrence counts agree at 5), which is the only reason it is a
  warning. Two implementations of one rule, one of them gated: extract the
  subject decision into a function both call.

- **W3. `dashboard_widgets` is a dead accumulator, and the documented union
  rule does not live where the docstring says.** Only `len()` of it is read
  (the dashboard count). I mutated `.update(ids)` to `= set(ids)`, the exact
  last-copy-wins behaviour the docstring forbids, and all 312 tests stayed
  green, because the widget union actually comes from `widget_state`. Either
  read the union from the field that holds it or delete the field.

- **W4. The order-independence gate does not cover classification, which is
  what round 4's B4 actually was.** I mutated `widget_state[key].add(...)` to
  `= {...}` (last copy wins) and `tests/test_census.py` stayed green, all four
  tests. The fixture corpus is the same content twice with a member dropped,
  so no widget classifies differently between copies and the forward/reversed
  comparison has nothing to bite on. The real corpus is order independent (I
  re-ran it forward and reversed: identical), but CI runs on fixtures alone.
  Fix: make the second fixture export change one widget's config, not only its
  membership.

- **W5. The result block's "14 divergent widgets" is not what the script
  prints.** `python3 tools/corpus_census.py corpus` prints **15**, and my
  independent walker agrees at 15. The script is the artifact; the quoted
  figure is stale. Every other figure in the result block reproduces exactly.

- **W6. The README still says the preview resolves to one of three
  statements, and never mentions the two that were added.** `README.md:174-179`
  lists drawn / named / carrying nothing. The fourth outcome, "not shown here",
  now covers **115 distinct widgets, 179 occurrences**, far more than the 11
  empties, and the README does not say it exists. The CHANGELOG describes it
  correctly; the admin-facing document does not. One paragraph, next to the
  three.

- **W7. The selector note is ungrammatical in the singular, which is most of
  them.** "1 widget on this dashboard is a selector: it chooses no subject of
  their own and drive the widgets below them". The round-4 fix pluralised the
  head of the sentence and not the tail. Seen on `MSSQL Query Performance &
  Blocking` and `vCommunity/ESXi Configuration 2.0`, both of which an admin
  will open. (The tail is also B1's false clause, so both fixes land in one
  edit.)

## NIT

- **N1. `widget(s)` survives in the preview's own notes**, `preview.py:1134`,
  "(2 widget(s) do the driving)", seven hundred lines above a docstring
  stating that operator-facing strings do not say `widget(s)`. Four more in
  `uipage.py` and `ui.py` and two in `corpus_check.py` say `object(s)` and
  `edge(s)`.
- **N2. `_SHORT_REASONS` keeps a dead entry in the old voice.**
  `("is not in this export", "the view the widget names is not in this export")`,
  `preview.py:1860`. No state-3 reason can now contain that needle, since the
  case moved to `elsewhere`. Harmless today, and it is the exact sentence
  round 4 ruled out, sitting in the table a future branch would reach for.
- **N3. `widget_state_blob`'s docstring asserts where VCF Operations keeps
  this and cites nothing.** The claim is correct, and the factory owns the
  proof: `knowledge/context/api-surface/resourcelist_column_state_wire_format.md`
  ("`states[]` lives at the top level of the widget object, sibling of
  `config`", import survival confirmed) and `known_limitations.md` §Widget
  `states[]`. One citation makes it checkable, per RULE-001.

## What is fixed, verified

- Round 4 B1 is fully done. `vCommunity/ESXi Configuration 2.0` now reads
  "20 widgets show a view this export does not carry, so they will show
  whatever the target already has ... nothing here tells that apart from a
  view that is genuinely gone", and no "nothing to show" line. The state has
  its own code, its own count and its own box style, outside the empties.
  `inspect` and `tree` say nothing that implies the tool can tell a built-in
  from a missing view.
- Round 4 B4 is done in substance: the census is a committed script, states
  its identity rule, is order independent on the real corpus forward and
  reversed, reports divergence rather than merging it, and every figure it
  prints reproduces against a walker that shares no code with it.
- Round 1 W1 (the squashed sliver) is properly fixed: the grid widens, and a
  widget beyond even that is named in the notes with what happened to it.
- Round 1 W5 is fixed: `corpus-check` previews every object and says how many.
- Gates that do fail when broken: a new `WIDGET_EMPTY_CODES` entry, a new
  `WIDGET_ELSEWHERE_CODES` entry, a new `WIDGET_RENDERERS` entry, a
  `widget_state_blob` that reads the wrong field, and a census that stops
  reporting divergent dashboards.

## What an operator would experience if shipped as-is

Scott previews `[Custom] Identify VMs on PG Type` and is told that its three
View widgets "choose no subject of their own", when all three declare that
they do; the same sentence is wrong on 72 of the 92 selectors in his estate.
On two other dashboards a Heatmap with no configuration at all is reported as
configured, with its layout supposedly held in four characters of saved state
that decode to an empty object. And the number he would quote for how many
widgets need a management pack on the target, 111, is 43 short of what his
own tool flags on screen.

# Round 6

Branch `feat/m4b-preview-and-page`, 11 commits over `main`, HEAD `e942890`.
Suite: **320 passed** (with `vcfcf_core` and the migrator `src` on
`PYTHONPATH`; without the migrator package importable, one determinism test
fails on its subprocess, which is an environment artefact and not a finding).
`corpus-check corpus`: **ok on all five zips**, select-all round trips,
every document byte-identical, every container unchanged.

**Verdict: CHANGES REQUESTED.** 2 BLOCKING, 4 WARNING, 3 NIT. Round 5's four
blocking findings are all genuinely fixed and I could reproduce every figure
in the result block. The two new blockings are in the fix itself: the
sentence that replaced round 5's B1 makes a second claim the export does not
support, and the census/page sharing that replaced round 5's B4 is keyed two
different ways, so on any document carrying an id-less widget the census
attributes verdicts to the wrong widgets.

## The census, reproduced independently

I wrote a walker (`/tmp/r6/walker.py`) that opens the five zips with
`zipfile`, reads `dashboards/<owner>` inner zips and `views.zip/content.xml`
directly, and re-implements classification from the documented rules. It
imports nothing from `vcfcf_migrator.preview`. Figures I personally
reproduced, all exact:

| figure | census | my walker |
|---|---|---|
| objects | 632 | 611 reproduced by kind (dashboards 118, views 237, supermetrics 155, reports 23, customgroups 26, symptoms 31, alerts 18, recommendations 3); the 21 notification/outbound identities I did not reproduce with a flat parse, and this branch does not touch their identity rule |
| objects carrying nothing (view-no-attributes) | 4 | 4 ViewDefs with zero `attributeInfos` items |
| objects with two names | 2 | 2 |
| dashboards / interaction driven | 118 / 86 | 118 / 86 |
| widgets / classified | 835 / 835 | 835 / 835 |
| carrying nothing | 12 | 12 (never-shows 3, no-config 5, no-metric 1, view-no-columns 3) |
| elsewhere | 157 | 157 (view-not-carried 154, state-not-read 3) |
| subjects | fed 469, self 154, from-outside 117, selector 92, never-shows 3 | identical |
| divergent dashboards / widgets / subjects | 2 / 15 / 0 | 2 / 15 (see below) / 0 |
| occurrences | widgets 1017, dashboards 148 | 1017, 148 |

My walker reports **17** divergent widgets, not 15. The two extra are widgets
that drive others and carry no config of their own, which my stricter walker
calls `widget-drives-only` in the copy where the config is empty; the page
says nothing about them at all (their type has no renderer, so they are named
rather than drawn, under a correct "drives N widgets" caption). Difference in
my reimplementation, not a defect: 17 = 15 + 2, reconciled per widget id.

### Every move since round 5 reconciled

I ran the round-5 census (`HEAD~1`) over the same corpus to compare:
no-config 4, state-not-read 4, view-not-carried 111, carrying nothing 11,
divergent widgets 15.

- **view-not-carried 111 to 154.** The `and not feeds` removal. Round 5's
  own prediction was "expect 154 distinct"; the script prints 154 and my
  walker, which has no such line, computes 154 from the raw `viewDefinitionId`
  values against the ViewDefs each zip carries. Confirmed.
- **no-config 4 to 5, state-not-read 4 to 3, carrying nothing 11 to 12.**
  The corpus holds **24** widgets whose entire state value decodes to the
  empty-object marker. Only **three** of those also have an empty `config`,
  which is the condition `_widget_verdict` tests, and of those three, one is
  agreed across copies (it moves from state-not-read into no-config, +1/-1)
  and two diverge between copies and are therefore in neither total, before
  and after. Every arithmetic step checks out; the commit message's "the
  three widgets carrying o%3A are empty again" is true per widget, and only
  one of the three is visible in the headline.
- **content elsewhere 115 to 157** = 154 + 3, against 111 + 4. Confirmed.

### Is the census still an independent statement of fact?

It is not, and that is the right call, with one caveat. The census now counts
what the page will tell the admin; a second implementation of the
classification is what drifted twice, and there is nothing to be gained from
two rules that can disagree about one widget. The independence that matters
has moved to the right place: the identity and reduction layer is still the
census's own, the fixture gates are still the census's own, and a genuinely
independent statement of fact is exactly what an external walker like mine
is for. What an admin needs from the census is not a second opinion on a
widget, it is "how many of these will the page report, and where do my
exports disagree with each other", which is what it now answers. **Caveat:**
the module docstring, which is where the census explains itself, never says
the verdicts come from the renderer. Only an inline comment in
`add_dashboard` does (N2).

### Finding 3: 0 versus 15, settled

Two methods, both saying **0**:

1. My walker records every widget where `widgetInteractions` makes it a
   provider and classification lands in a state-3 code: **0 in the corpus**.
2. I rendered all 148 dashboard pages and parsed the HTML with
   `html.parser`, tracking div nesting so a frame ends where its div ends
   rather than where the next regex match starts: **1017 widget frames, 115
   carrying a "drives N widgets" badge, 28 carrying a "nothing to show" box,
   0 carrying both.** 1017 and 115 and 28 match the census's widget,
   selector and empty-widget occurrence counts exactly, which is the check
   that the parse saw every frame.

Round 5's "15" was a frame regex swallowing the following frame, as claimed.
Withdrawn.

### Mutation results (their claims, my runs)

| mutation | claimed | observed |
|---|---|---|
| delete `if feeds: return ("", "", "")` in `_widget_verdict` | 2 tests red | **2 failed** |
| delete the `ctx["feeds"]` gate in `_record_empty` | 4 tests red | **4 failed** |
| drop the `unquote` in `widget_state_blob` | suite red | **1 failed** |
| restore the old unconditional selector clause | 3 tests red | **3 failed** |
| census `widget_state` last-copy-wins | 2 census tests red | **2 failed** |
| census `dashboard_widgets` last-copy-wins | live | **1 failed** (round 5 W3 fixed) |
| add a `WIDGET_EMPTY_CODES` entry | red | **1 failed** |
| add a `WIDGET_ELSEWHERE_CODES` entry | red | **61 failed** |
| add a `WIDGET_RENDERERS` entry | red | **2 failed** |

Every claim holds.

## BLOCKING

- **B1. The selector sentence's new tail states an inbound data path the
  export denies, on 17 of the 92 selectors.** `preview.py:1275-1276`. Where
  `selfProvider` is false the caption reads "this widget chooses no subject
  of its own: this widget drives N widgets on this dashboard, and shows
  whatever is picked in them". The only plural antecedent of "them" is the
  widgets it drives, so the sentence says this widget takes its subject from
  the widgets it feeds, which is the wiring backwards: `widgetInteractions`
  names this widget as the **provider** on every one of those edges, and
  nothing in any of the five exports names a provider for it. The factory's
  own authority says the opposite outcome:
  `knowledge/vcf_ops_concepts.md:395-399`, a widget without `selfProvider:
  true` and a pin "waits forever for an interaction that never comes and
  renders blank", and `knowledge/context/api-surface/widget_renderer_scope.md`
  calls `selfProvider: false` interaction driven. This is the same class as
  round 5's B1, one branch over: the clause that is checked is now correct,
  and the clause bolted to it is not checked by anything. No test pins the
  tail; `tests/test_preview.py:867` asserts only the head clause.
  I verified the split against the raw values on all 92 distinct selectors:
  72 true (says "picks its own subject", correct), 17 false (says the above),
  3 absent (says neither, correct).
  → Say what the export says and stop: drive N widgets, and where
  `selfProvider` is false, "the export says it does not choose its own
  subject, and nothing on this dashboard feeds it". Pin the tail in the
  fixture selector test.

- **B2. The census reads the page's verdicts with a key the page does not
  write, and a miss is silently counted as a clean, self-subject widget.**
  `tools/corpus_census.py:105` keys an id-less widget `index-<document
  index>`; `preview.py:1359` keys it `index-<position within its tab, in
  layout order>`, because `_widget_grid` is called once per tab and its
  `position` restarts at 0 in each tab. `corpus_census.py:120` then does
  `.get(wid, ("", "", "self"))`, so a key that does not match fabricates a
  verdict instead of failing. The corpus has no id-less widget and no
  multi-tab dashboard, which is why every corpus figure above still
  reconciles. **The fixture, which is the only thing CI measures, is full of
  them:** 16 of 66 widget occurrences get a key that does not match, and
  because the mismatch shifts the alignment rather than just missing, **14
  distinct widgets (28 occurrences) are counted under another widget's
  verdict.** Measured, not inferred: the alert list is counted as
  `widget-view-not-carried`, the property list as `widget-no-view`, the text
  widget with no text as `widget-no-health-metric`, a widget naming an absent
  view as clean. Neither the "widgets == widgets classified" gate nor the
  order-independence gate can see it, because both sides use the census's own
  keys. This is the drift round 5's B4 was meant to end, re-entering through
  the join rather than through a second implementation, and it reports green.
  → Key both sides with one expression (have `build()` record the verdict
  under the widget's document index as well as its id, or have the census ask
  by the same per-tab layout position), and make a widget with no verdict
  raise rather than default. RULE-001: a counted figure must come from the
  source, not from a fallback tuple.

## WARNING

- **W1. The reproducible-bundle fix is entirely ungated.** `containers.py:64`
  `zip_entry` pins the timestamp and `create_system`, and the CHANGELOG sells
  it ("Bundles are reproducible"). I reverted every `writestr(zip_entry(n))`
  to `writestr(n)`: **320 passed**. Two builds two seconds apart then differ
  in bytes, which I confirmed. Both gates that look like they cover it build
  twice back to back in one process, so a clock timestamp passes them.
  → Assert the written entries' `date_time` and `create_system` in a built
  bundle, or build the second copy with the clock moved.

- **W2. The divergence-exclusion fix is half gated, and the half that is not
  gated is the exact defect of round 5.** `corpus_census.py:133`. Resolving
  divergent widgets toward the flagged copy (`sorted(v)[-1]`) fails
  `test_a_widget_...is_reported_not_picked`; resolving toward the clean copy
  (`sorted(v)[0]`, which is what round 5 W1 found, hiding 14 classified
  widgets) leaves all 7 census tests green, because the fixture's one
  divergent widget is clean in one copy and the two behaviours coincide on
  it. The object side (`:139`) is ungated in both directions: a
  `sorted(v)[-1]` there is green.
  → A second divergent fixture widget carrying two different non-empty codes
  distinguishes them; an object whose copies differ covers `:139`.

- **W3. The README and the CHANGELOG still carry the claim the code just
  dropped.** `README.md:213` and `CHANGELOG.md:68`: "a selector, which
  chooses no subject of its own precisely because it drives the widgets below
  it". That is the sentence round 5 blocked, stated as a general rule, in the
  two documents an admin and a reviewer read, shipping in the same commit
  that removed it from the code for 72 of 92 selectors.

- **W4. The output never says the per-reason totals exclude the divergent
  copies.** `corpus_census.py:render`. The policy is right: with two exports
  disagreeing there is nothing to base a tie-break on, so excluding and
  counting separately is the honest reduction. But an admin reading the
  headline as an inventory sees "widgets carrying nothing 12" and a line
  further down reading "divergent widgets 15", with nothing saying the second
  number is **in none of the lines above**; that consequence exists only in
  the module docstring. 15 widget identities and their codes appear nowhere
  in the rendered figures.
  → One line under the per-reason blocks: "totals are where the copies agree;
  15 widget identities whose copies disagree are in none of them".

## NIT

- **N1.** `README.md:211` and `CHANGELOG.md:66` say a widget's subject "has
  four answers". `SUBJECT_KINDS` has five, and the census prints five; the
  omitted one is `self`, which is 154 widgets, the largest bucket after fed.
- **N2.** The census module docstring explains identity, order independence
  and divergence, and never says the classification comes from the page. That
  is the single most important thing about how it now works.
- **N3.** The `selfProvider: false` caption says "this widget" twice across
  its colon ("this widget chooses no subject of its own: this widget drives
  ..."). Falls out with the B1 fix.

## What else I checked and found clean

- Finding 2 against the wire-format doc
  (`knowledge/context/api-surface/resourcelist_column_state_wire_format.md`
  §1, "`o:` = object, `a:` = array ... a column record is `o:id=s:<colId>`"):
  one `unquote` then stepping past the `o:`/`a:` markers is exactly the
  documented grammar, `o%3A` decodes to an object with no fields and is
  correctly not a layout, and the widget carrying a real 4kB blob is still
  read as configured. The docstring cites the doc by path, per RULE-001.
- Closure, over-carry, select-all identity, page-versus-CLI bundle: all five
  corpus exports round trip byte-identical under `corpus-check`, 83/83/158/48/430
  objects previewed, zero errors.
- Leak scan, my own: 107 corpus dashboard names and 953 corpus widget and
  dashboard uuids, checked against every tracked file in the migrator repo
  and against all 11 commit messages. **Zero hits.** No em-dash in any
  tracked file or any commit message. No credential-shaped string.
- 13 `WIDGET_RENDERERS`, matching the CHANGELOG's "thirteen".
- Nits from round 5: the `widget(s)` parentheticals are gone from every
  operator string (one `wording.plural` helper, imported by all four
  modules), the dead `_SHORT_REASONS` entry is gone, and the singular
  selector note reads correctly ("drives 1 widget ... and picks its own
  subject").

**If shipped as-is:** on 17 dashboards an admin is told a selector takes its
subject from the widgets it drives, which is the wiring backwards and, by the
factory's own concepts doc, describes a widget that will actually render
blank. And the script that produces every corpus figure in the PR body
attributes verdicts to the wrong widgets on any export carrying a widget
without an id, silently, with the fixture that gates it scrambled 14 widgets
deep and green.

# Round 7

- Branch `feat/m4b-preview-and-page`, 12 commits over `main`, not pushed
- Reviewed: 2026-09-14
- Round-6 fixes under review: `e942890`, `e748b1c`
- Verdict: **CHANGES REQUESTED** (2 BLOCKING, 3 WARNING, 4 NIT)

Both round-6 BLOCKING findings are genuinely fixed in the code, and I could
not make the preview say anything the export does not say. Both of the
remaining BLOCKINGs are single sentences of prose that state a number
wrongly: one in the census output, one in the README. Neither is polish;
each makes an admin carry away a figure the tool's own output contradicts.

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **325 passed**, 0 failed (with `vcfcf_core` and the repo `src` on `PYTHONPATH`; bare `pytest` cannot collect without them) |
| corpus-check | exit 0, 5 ok lines, 802 objects previewed, select-all round trips byte-identical on all five |
| preview over all 802 corpus objects | 0 errors |
| census, reproduced my own way | objects 632, dashboards 118, widgets 835, widgets classified 835, carrying nothing 12, selectors 92, divergent widgets 15 |
| census order independence | reversed plus three random permutations, all four reports identical to sorted order |
| selector tails vs raw `selfProvider`, all 115 rendered captions | **0 disagreements**; 92 distinct selector identities, 71 true / 20 false / 1 absent |
| state-3 boxes rendered vs counted, whole corpus | 28 rendered, 28 counted |
| selectors classified empty / contradictory frames | 0 / 0 |
| key agreement, page vs census, all 152 dashboards | 0 disagreements; 0 documents with a duplicate widget key |
| closure fixpoint, every node as a seed | 802 seeds, 0 non-fixpoints |
| determinism | preview and select-all bundle byte-identical across processes with `PYTHONHASHSEED` 0 vs 12345 and `TZ=Asia/Tokyo`, builds 2s apart |
| zip stamps in a built bundle | 17 outer entries and every entry of both rebuilt inner zips at `(1980,1,1,0,0,0)` / `create_system 3` |
| page vs CLI bundle | `test_a_build_through_the_page_is_the_build_the_cli_writes` compares full bytes and passes; `bundle.py`, `containers.py`, `graph.py`, `selection.py` untouched by the two fix commits |
| leak scan | 597 corpus display names and 600 uuids against every tracked file and all 12 commit messages: **0 hits** (the one match, "Alerts", is the substring of `ProblemAlertsList` in the renderer table) |
| em-dashes | none in any tracked file, none in any commit message |
| mutations run | 19, listed below |

## Round-6 BLOCKING findings, re-verified

**B1 (selector tail) is fixed.** `preview.py:1291-1304`. I read the tail out of
the rendered HTML for every selector in the corpus and compared it against the
raw `selfProvider` value in the document: 115 rendered captions, **0 backwards**.
The removed phrasings appear nowhere outside the comment that explains their
removal and the tests that assert their absence. Mutations, each rerunning the
full suite:

| Mutation | Result |
|---|---|
| restore "and shows whatever is picked in them" | 1 failed |
| drop the `selfProvider: false` tail entirely | 1 failed |
| drop the `selfProvider: true` tail entirely | 1 failed |
| swap the true and false branches | 1 failed |
| **give the absent branch the `true` tail** | **325 passed** (W1) |

**B2 (one key for one widget) is fixed.** `preview.widget_keys` is computed once
per document at `preview.py:1165`, above the tab split, and passed into
`_widget_grid`; the census calls the same function at `corpus_census.py:116`;
`corpus_census.py:132` raises instead of defaulting. Making the page key per tab
again fails 10 tests. Restoring the `.get(wid, ("", "", "self"))` default fails 1.
My own scan looked up every widget of all 152 corpus dashboards by the shared
key and never missed, and no document in the corpus or the fixture produces a
duplicate key. Two of the claimed mutations do not hold, though: re-keying the
census by its own document index is green (it is the same expression, so that
one is harmless), and re-keying it by per-tab position, **the exact round-6
defect**, is also green (W2).

## Round-6 WARNING gates, each mutated

| Gate | Mutation | Result |
|---|---|---|
| W1 reproducible zips | outer `writestr(zip_entry(name))` reverted (`bundle.py:237`) | 1 failed |
| W1 | inner rebuilt zip reverted (`containers.py:173,175`) | 1 failed |
| W1 | second container's entries reverted (`containers.py:432,434`) | 1 failed |
| W1 | `ZIP_EPOCH` replaced with the clock | 1 failed |
| W1 | `info.create_system = 3` removed | **325 passed** (N2, platform-bound) |
| W2 divergence, widgets | tie-break to `sorted(v)[0]` (clean) | 1 failed |
| W2 | tie-break to `sorted(v)[-1]` (flagged) | 1 failed |
| W2 divergence, objects | tie-break to `sorted(v)[0]` | 1 failed |
| W2 | tie-break to `sorted(v)[-1]` | 1 failed |
| W2 divergence, subjects | tie-break to `sorted(v)[0]` | **325 passed** (W3) |
| W3 docs | n/a | the removed claim is gone from `README.md` and `CHANGELOG.md`; both now say five subject answers and name `self` |
| W4 census output | n/a | the line exists, and it is **wrong** (B1 below) |

## BLOCKING

### B1. The census's own exclusion note is false for five of the figures above it

`tools/corpus_census.py:221`. The rendered line is

> `every total above counts only identities whose copies agree; these are the ones they exclude`

and it sits under the whole report, headline block included. Measured on the
corpus: `widgets 835` and `widgets classified 835` are `len(widget_state)` and
the per-dashboard id union, both of which **include** all 15 divergent widget
identities (820 agreed + 15 divergent = 835). `dashboards 118` includes the 2
divergent dashboards. `objects 632` includes the 2 identities carrying two
names. Only `objects carrying nothing`, `widgets carrying nothing`, the three
by-reason blocks and the subject block exclude anything.

So an admin reading the block from the top and the note at the bottom adds the
15 to the 835 and carries 850. Round 6's W4 asked for the opposite precision;
generalising it from "the per-reason totals" to "every total above" turned an
ambiguity into a false statement about the five most prominent numbers the
script prints, and those are exactly the numbers that go in a PR body.
RULE-001: a stated figure must be what the source says.
→ Scope the sentence to the totals it is true of, for example "the per-reason
and subject totals above count only identities whose copies agree; the counts
at the top include everything, divergent or not; these are the identities the
per-reason totals exclude".

### B2. The README tells the admin the opposite of what their dashboards do, two sentences after telling them correctly

`README.md:212-213`, in the paragraph that explains the milestone's central
concept:

> **The preview shows the dashboard's wiring.** Most widgets on a real
> dashboard do not choose their own subject ... How a widget comes by its
> subject has five answers ...: **it picks its own (the commonest, and what
> `selfProvider` says when it says anything)**; it is fed by a named widget; ...

Both halves of the parenthetical are false against the corpus, and the first
contradicts the paragraph's own opening sentence:

- `self` is **154 of 835** distinct widgets (18%). `fed` is **469** (56%). It
  is not the commonest; it is second, and the sentence three lines above says
  so correctly.
- `selfProvider`, when it says anything, says **false 590 times and true 198**.
  It overwhelmingly says the widget does *not* pick its own subject.
- 38 of the 154 `self` widgets carry no `selfProvider` at all, so for a quarter
  of that bucket the export says nothing and `subject_of` is applying a
  default. The page is silent about those, correctly; the README describes the
  bucket as what the export states.

This is the same class as round 6's W3: a general claim in the document an
admin reads, contradicted by the tool's own output. An admin who believes it
will expect most widgets to preview standalone and be surprised by a
dashboard that is 56% fed.
→ Drop the parenthetical, or replace it with what the census shows ("the
default when `selfProvider` says nothing, and the second commonest after fed").

## WARNING

- **W1. The third `selfProvider` branch is not pinned.** `preview.py:1303`.
  Giving the "export does not say" case the `", and picks its own subject"`
  tail leaves **325 passing**, and the fixture has **4** selectors shaped that
  way (the corpus has 1 distinct). The claim that all three branches are pinned
  on the tail holds for two. The unpinned one is the branch where the export
  says nothing, which is the only branch where a regression fabricates a claim
  rather than getting one wrong, which is what RULE-001 is about.
  → Assert in the fixture selector test that a selector whose config carries no
  `selfProvider` renders the bare "drives N widgets" clause and neither tail.

- **W2. The census/page key guard does not catch the drift it was written for.**
  `corpus_census.py:131-138`. Re-keying the census by per-tab position, the
  exact round-6 defect, leaves **325 passing**. The `KeyError` only fires on a
  key the page never wrote; per-tab keys are a *subset* of document-index keys
  (`index-0`, `index-1` for a two-tab dashboard whose document has four id-less
  widgets), so every lookup hits, no key is missing, and 2 widgets are silently
  counted under another widget's verdict. The fixture's `[Fixture] VM Overview`
  (4 id-less widgets, 2 tabs) is precisely that shape and passes. This is the
  fifth round in which a guard here reports green while the property it guards
  is violated.
  → Compare the sets, not the members. I verified the fix: adding
  `if set(ids) != set(preview.widget_verdicts) or len(set(ids)) != len(ids): raise`
  before the loop is green on the current code (325 passed) and fails 9 census
  tests the moment the per-tab keying is reintroduced.

- **W3. The fifth divergence path is ungated.** `corpus_census.py:155`.
  Four of five `len(v) == 1` filters are now pinned in both directions; the
  widget-subject one is not, and `sorted(v)[0]` there is green. It feeds the
  "how widgets come by their subject" block and `divergent widget subjects`.
  Nothing is wrong today (the corpus has 0 divergent subjects), which is also
  why nothing would notice.
  → Give the divergence fixture a widget whose two copies land in two different
  subject buckets.

## NIT

- **N1.** `tests/test_census.py:231`: `assert any(w.get("tabId") for w in idless) or True`
  asserts nothing. It is the line that was meant to record that the fixture
  covers the multi-tab shape, in the test whose docstring makes that claim.
- **N2.** Removing `containers.py:77` (`info.create_system = 3`) leaves the
  suite green, because `ZipInfo` already sets 3 off Windows and CI is
  ubuntu-only. The assertion is honest and the pin matters for the Windows
  binary; it simply cannot fail on any runner this project has. Worth a comment
  saying so, so a future reader does not trust the mutation.
- **N3.** `ui.py:224`: trailing whitespace inside the concatenation
  (`+ " no longer needed and " `). Cosmetic; CI does not lint.
- **N4.** `corpus_census.py:109` reads `doc.get("widgets", [])` where
  `preview.py:1156` guards with `isinstance(..., list)`. A document with
  `"widgets": null` renders as an empty dashboard on the page and raises
  `TypeError` in the census. No corpus or fixture document is shaped that way.

## What else I checked and found clean

- 13 `WIDGET_RENDERERS`, `HANDLED_WIDGETS` derived from it and consumed by
  `test_preview.py:86`, matching the CHANGELOG's "thirteen" and its claim that
  the fixture carries one of each.
- The README's state-4 claim ("covers more widgets than state 3") holds: 157
  elsewhere against 12 carrying nothing.
- Nits from round 6 fixed: five subject answers with `self` named in both docs;
  the census docstring now leads with the verdicts coming from the preview; the
  selector caption no longer says "this widget" twice.
- `wording.plural` is imported by all four surfaces; no `(s)` parenthetical
  remains in an operator string.
- Rendered a real interaction-driven dashboard end to end and read it as an
  admin would: the banner states what is invented and what is the export's, the
  wiring summary, badges, fed-widget labels and the two selector tails all read
  correctly, and a widget that both drives and is driven correctly takes the
  fed sentence rather than the selector one.

**If shipped as-is:** the preview itself is trustworthy, and I could not make
it misstate a dashboard. But the two artefacts an admin reads *around* it each
carry one wrong number: the census tells them the headline counts exclude the
divergent identities when those counts include every one of them, and the
README tells them most widgets pick their own subject in the same paragraph
where it tells them most widgets do not.

---

# Round 8: narrow confirmation pass

Branch `feat/m4b-preview-and-page` at `48801c0`, 14 commits over `main`. Scope
as briefed: confirm the round-7 findings are closed and that nothing regressed.
No fresh lines of enquiry were opened; the one finding below is round-7 B1,
which is not closed.

## Checks re-run

| Check | Result |
|---|---|
| pytest | **329 passed**, 0 failed (was 325; +4 new gates) |
| corpus-check | exit 0, 5 ok lines, 802 objects previewed, select-all round trips byte-identical on all five |
| closure fixpoint, every node as a seed | 802 seeds, 0 non-fixpoints |
| determinism, select-all | byte-identical across `PYTHONHASHSEED` 0 vs 12345, `TZ` UTC vs Asia/Tokyo, builds 2s apart |
| determinism, single seed | byte-identical, second process, different seed and TZ |
| zip stamps | every outer and inner entry at `(1980,1,1,0,0,0)` / `create_system 3`, one distinct pair |
| over-carry | a one-dashboard seed closes to 5 nodes and the bundle carries 5 outer entries |
| page vs CLI bundle | `test_a_build_through_the_page_is_the_build_the_cli_writes` passes; `bundle.py`, `containers.py`, `graph.py`, `selection.py` untouched since the round-7 baseline `e942890` |
| select-all identity | `test_two_builds_of_one_selection_are_byte_identical` passes |
| leak scan | 603 corpus display names and 600 uuids against every tracked file and all 14 commit messages: 0 real hits (the two matches are the English words "test" and "Alerts" inside `ProblemAlertsList`) |
| em-dashes | none in any tracked file, none in any commit message |
| trailing whitespace | none in any tracked `.py` or `.md` |

## Round-7 findings, re-verified by mutation

| Finding | How confirmed | Result |
|---|---|---|
| W1 third `selfProvider` branch | give the absent branch the `true` tail | **2 failed** |
| W1 | give the `false` branch the `true` tail | **2 failed** |
| W1 corpus sweep hardened | captions matched as a per-dashboard multiset, not by title | code reads as claimed |
| W2 census/page key guard | re-key the census by per-tab position, the round-6 defect | **10 failed**, all in `test_census.py` (claim said 9) |
| W3 fifth divergence path | subject tie-break `sorted(v)[0]` | **1 failed** |
| W3 | subject tie-break `sorted(v)[-1]` | **1 failed** |
| N1 `assert any(...) or True` | `or True` appears nowhere in `tests/`, `src/`, `tools/`; the id-less multi-tab shape is now asserted on `len(idless) >= 3` and more than one `tabId` | closed |
| N2 `create_system` | removing `containers.py:77` now fails, via a test that patches `sys.platform` to `win32` | **1 failed** |
| N3 trailing space | gone | closed |
| N4 census widgets guard | `corpus_census.py` now guards with `isinstance(raw_widgets, list)` and filters non-dict members, the way the page does | closed |
| B2 README parenthetical | the false parenthetical is gone; the line now reads "it is **fed** by a named widget, which is the commonest answer on a real dashboard", which matches the census (fed 469 of 835, the largest bucket) | closed |
| B1 census exclusion sentence | see below | **not closed** |

All mutations were run in a throwaway copy of the tree, not in the clone, and
the clone is byte-for-byte as committed.

## BLOCKING

### B1 (carried over). The rescoped exclusion sentence is wrong about the fourth block, and points the 15 at a total that excludes them

`tools/corpus_census.py:209-210` (the header) and `:227-231` (the tail
sentence). The round-7 over-reach was correctly narrowed, but the replacement
makes two claims that the script's own output contradicts:

**1. The subject block leaves out 0 identities, not 15.** The sentence says
"the four blocks above count only identities whose copies agree: 15 widgets and
0 objects are left out of them". It is true of the three by-reason blocks. The
fourth block, "how widgets come by their subject", is filtered on
`self.widget_subject` (`corpus_census.py:159`), which is subject agreement, not
code agreement, and the corpus has **0 divergent widget subjects**. Measured:

```
subject block sum      : 835   (fed 469 + from-outside 117 + never-shows 3 + selector 92 + self 154)
widgets classified     : 835
widgets left out of the subject block: 0
```

An admin reconciling the block against the total three lines above it expects
`835 - 15 = 820` and finds 835. RULE-001: a stated figure must be what the
source says.

**2. "and are in the totals at the top" is false for one of the seven totals,
and the header repeats the error.** The header says "(the totals below count
every identity, including the ones whose copies disagree)". `widgets carrying
nothing 12` is `len(unfinished)`, built from `agreed` at
`corpus_census.py:156-158,170` (printed at `:184`), so it excludes all 15 divergent identities.
Six of those 15 classify as carrying nothing in one of their two copies
(`widget-no-config` in each case). Measured:

```
top-line 'widgets carrying nothing' (agreed only)        : 12
if divergent identities were included (any copy unfinished): 18
```

So the one place the sentence sends the admin to find the 15 is the one total
that does not have them, and the header states the opposite. The same is
latently true of `objects carrying nothing`, vacuous today only because
divergent objects is 0.

This is the same class as the round-7 finding: the census tells the admin where
a number went, and the number is not there.

→ Smallest correct fix, one clause each: scope the tail sentence to the three
by-reason blocks and give the subject block its own figure (`divergent widget
subjects`, 0), and change the header to exempt the two "carrying nothing"
totals, which are agreed-only like the by-reason blocks. For example: the three
by-reason blocks and the two "carrying nothing" totals count only identities
whose copies agree (15 widgets, 0 objects left out); the subject block leaves
out only the 0 identities whose copies disagree about the subject; the rest of
the totals at the top count every identity.

## WARNING / NIT

None. Every round-7 WARNING and NIT is closed and, where a mutation applies,
pinned by a failing test.

## Verdict

**CHANGES REQUESTED.** One BLOCKING, carried over. The preview, the page, the
build path and the README are clean: nothing in the tool misstates a dashboard,
nothing regressed against round 7, and the four new gates hold in both
directions. The census output is still not internally consistent with itself,
which is the one thing I said I would not sign off, and it is now a
two-clause wording fix rather than a code change.

**If shipped as-is:** an admin reading the census bottom line subtracts 15
widgets from the subject block that were never in it, and goes looking for 15
divergent widgets in `widgets carrying nothing 12`, which excludes every one of
them. The 469/154 split the README now leans on is correct; the note underneath
it says it is not.

---

# Round 9: sign-off pass on round-8 B1

Branch `feat/m4b-preview-and-page` at `8047191`, 15 commits over `main`,
unpushed. Scope as briefed: confirm round-8 B1 is closed by reading the
rendered census end to end and checking every block's arithmetic against every
claim made about it, run the three claimed mutations, and re-run the standing
checks. No new lines of enquiry opened.

- Verdict: **APPROVE** (0 BLOCKING, 0 WARNING, 2 NIT)

## Checks re-run

| Check | Result |
|---|---|
| pytest | **331 passed**, 0 failed (was 329; +2 new gates) |
| census, recomputed by my own walker (own keying, own reduction, no call into `corpus_census`) | every figure reproduces: 632 / 4 / 118 / 86 / 835 / 835 / 15 / 820 / 12 / 157 / 6 / 0 |
| census order independence | reversed plus three random permutations: report and rendered text identical |
| corpus-check | exit 0, 5 ok lines, 802 objects previewed, select-all round trips byte-identical, containers unchanged on all five |
| closure fixpoint, every node as a seed | **802 seeds, 0 non-fixpoints** |
| over-carry, bundle built and read back | **82 sampled seeds across all five zips, 0 over, 0 under** |
| determinism, select-all | byte-identical across processes, `PYTHONHASHSEED` 0 vs 12345, `TZ` UTC vs Asia/Tokyo, `LC_ALL=C`, builds a second apart, all five |
| page bundle vs CLI bundle, real corpus | identical sha256 on all five, and identical to the determinism run's hashes |
| leak scan, 771 corpus uuids + 771 8-hex prefixes + 471 display names, against all 34 tracked files, all 122 blobs in every ref, and every commit message | **0 real hits** (the four matches are the English words `summary`, `percentage`, `Alerts`, `Custom Groups`). Round 2's N8 is closed too: `feat/m3-skeleton` no longer exists locally or on the remote |
| em-dashes | none in any tracked file, none in any commit message |
| trailing whitespace | none in any tracked `.py` or `.md` |

## The rendered census, read end to end

Every line of the real-corpus report, against every claim made about it:

| Claim | Arithmetic | Holds |
|---|---|---|
| header: totals count every identity **except** the two carrying-nothing counts | `objects 632`, `dashboards 118`, `dashboards interaction driven 86`, `widgets 835`, `widgets classified 835` all include the divergent identities (the driven count is a union over copies); `objects carrying nothing 4` and `widgets carrying nothing 12` are built from agreed copies only | yes, for all seven |
| carrying-nothing block sums to its total | 3 + 5 + 1 + 3 = 12 | yes |
| "the two blocks above cover the 820 widgets whose copies agree" | 835 classified - 15 divergent = 820, and the two blocks are computed over exactly those 820 | yes |
| "the other 15 are in neither" | the 15 divergent identities appear in no by-reason block | yes |
| "6 of those carry nothing in at least one copy" | I listed all 15: 6 are `['', 'widget-no-config']`, 9 are `['', 'widget-state-not-read']` or `['', 'widget-view-not-carried']` | yes, 6 |
| objects block: "covers the 632 objects whose copies agree; the other 0" | divergent objects 0, block sums 4 = the total above | yes |
| subject block: "covers the 835 widgets whose copies agree on the subject; 0 disagree" | 469 + 117 + 3 + 92 + 154 = 835 = widgets classified, divergent widget subjects 0 | yes |
| divergence block | 2 / 0 / 2 / 15 / 0, all reproduced independently | yes |
| occurrences block | subject occurrences 585 + 117 + 5 + 115 + 195 = 1017 = widget occurrences; objects 802; dashboards 148 | yes |

Round-8 B1 is closed on both clauses. The subject block no longer points the 15
at itself, and the header no longer claims the two carrying-nothing totals
include identities they exclude. Nothing an admin reads off this report
contradicts anything else in it.

## The three claimed mutations, run

| Mutation | Result |
|---|---|
| one note back over four blocks (the round-8 tail sentence restored, the three per-block notes removed) | **1 failed**, `test_every_block_sums_to_the_figure_its_note_claims` |
| the old header restored | **1 failed**, `test_the_header_exempts_the_two_agreed_only_totals` |
| subject block counts divergent copies (`sorted(v)[0]`, no agreement filter) | **1 failed**, but by `test_a_widget_whose_subject_differs_between_copies_is_excluded_too`, not by either new test (N1) |

Two further mutations of my own, to check the new test is not a tautology:

| Mutation | Result |
|---|---|
| a total drifts from its block (`widgets carrying nothing` = `len(empty)`) | **1 failed**, `assert 12 == 17`. The sums half of the new test is live |
| the disputed figure inflated (`disputed_widgets` = every divergent identity, dropping the unfinished filter) | **331 passed** (N2) |

All mutations were run in a throwaway copy; the clone is byte-for-byte as
committed and I wrote nothing into it.

## NIT

- **N1. The new test's subject-block assertions are vacuous on their own
  fixture.** `tests/test_census.py:437-465` runs on
  `_two_copies_classifying_differently`, whose `divergent widget subjects` is
  **0**, so `widgets with a subject == widgets classified - divergent widget
  subjects` holds whether the subject counter filters on agreement or not. The
  mutation is still caught, by the older
  `test_a_widget_whose_subject_differs_between_copies_is_excluded_too`, which
  uses the subject-divergent fixture. The claim that the three mutations fail
  *these* tests holds for two of three. Nothing is unprotected; the claim is
  one test too generous. (Also: the first mutation fails through an
  `IndexError` in `_blocks` rather than an assertion, because removing a note
  empties the list the test indexes. It detects, but the failure names the
  parser rather than the property.)
- **N2. "6 of those carry nothing in at least one copy" is pinned to nothing.**
  `tools/corpus_census.py:169-172`. The new test asserts
  `str(report["widgets disputed as carrying nothing"])` appears in the note,
  which is the number the note is formatted from, so the assertion cannot fail
  on a wrong figure. Dropping the `UNFINISHED_CODES` filter, which would make
  the note say 15 where the truth is 6, leaves the suite green. The figure is
  correct today: I enumerated all 15 divergent identities and 6 carry
  `widget-no-config` in one copy. One line asserting the fixture's disputed
  count against the codes the fixture was built with would close it.
- Cosmetic, inside N2's line: `corpus_census.py` does not import
  `wording.plural`, so a corpus with one divergent widget prints "the other 1
  are in neither" and "1 disagree and are not in it". Visible on the divergence
  fixture; the real corpus prints 15 and reads correctly.

## Sign-off

**The census output, as an admin reads it, is internally consistent.** Every
block sums to the figure its own note claims, every note is true of the block
it sits under, the header is true of all seven totals it governs, and the 15
divergent identities are accounted for in one place and only one place. This is
the confirmation withheld in rounds 7 and 8.

**If shipped as-is:** an admin reads a census whose blocks reconcile against
each other and against the totals above them, and a preview, page and build
path that are unchanged since the round-8 baseline and still byte-reproducible.
The two nits are about the gate, not the numbers, and neither changes anything
an operator sees.
