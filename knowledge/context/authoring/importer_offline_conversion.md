# Offline import: existing content files to factory YAML (`import-local`)

`python3 -m vcfcf_extractor import-local` converts a tree of existing VCF
Operations content files to factory YAML, one file per object, into a target
layout the factory loaders read. No live instance, no network. Use it to port
a third-party pak or a lab export into the factory, or to bring existing
content under factory management.

Code: `src/vcfcf_core/importer/` (scan, per-type mapping, source accounting,
flat forms, conversion plan, comparison: location-agnostic) and
`src/vcfcf_extractor/importer.py` (CLI, staged writing, stock-id guard,
verification through the real loaders). Tests: `tests/test_import_local.py`,
`tests/test_import_local_fidelity.py` (the review fixes and the mutation
self-test).

## Which command

| Command | Use it for |
|---|---|
| `import-local` | Whole content trees: every view (referenced or not), dashboard, report template, alert, symptom, recommendation and super metric, every source key accounted for, explicit id and naming decisions, verification |
| `reverse-local` | One dashboard JSON and the views it references, with the old output shape (kept for its users, unchanged) |
| `extract dashboard` (`/extract`) | A dashboard from a live lab, with its dependency walk and enablements (unchanged) |

`import-local` is a sibling rather than an extension of `reverse-local`:
that command's contract (one dashboard per run, only referenced views, its
YAML shape and its diff report) has users, and changing what it writes
would change their output for the same input.

## Inputs

Any number of files, directories (walked recursively) and archives. Files
are classified by content, never by folder name:

- view XML (`<ViewDef>`, one or many per file, any nesting);
- dashboard JSON: a bare dashboard or an `{entries, dashboards[]}` envelope
  of one or many dashboards (a pak `dashboards/<Folder>/dashboard.json`
  becomes a Summary page with `summary_for: VMWARE:<Folder>`);
- report template XML (`<ReportDef>`);
- `alertContent` XML: alert definitions, symptom definitions (standalone or
  inline) and recommendations;
- super metric JSON (pak `supermetrics/*.json`, export `supermetrics.json`);
- content-export zips, packed `.pak` files and their nested zips.

Archives are read with the stock-id guard's limits and "cannot check"
discipline (`stock_id_guard.md`): more than 6 nested archives, a member over
512 MB, an encrypted member, an unreadable compression method or a zip that
does not open is `CANNOT READ`, and the run exits 1 whatever else happens
(`--allow-partial` does not cover it). The same holds for an XML file with a
DOCTYPE or entity declaration (refused before parsing: product exports carry
neither, so entity-expansion safety does not depend on the host's libexpat),
a JSON file with the same key twice in one object (which value the product
used cannot be known), and text that does not decode. Text is decoded by
byte-order mark, else by an XML declaration's `encoding`, else as UTF-8.

**Unsupported types** are listed per object as `NOT CONVERTED (unsupported
type)` and make the run exit 1 unless `--allow-partial`: custom groups (an
export `customGroups` list, or a pak custom group JSON with
`membershipDefinition`) and policies (each `<Policy>` of a policy export).
Everything else that is not a content definition (an XSD,
`configuration.json`, the marker file, a pak's `files/solutionconfig/*.xml`
check lists, `.properties` bundles, dashboard sharings, user mappings) is
listed as *passed over* with the reason. Every definition the stock-id
guard's own scanner finds must be one the converter read, or the run reports
`MISSED` and exits 1.

The same id in several files is one object when the comparator finds no
difference between the copies (the same flat form, below; only the ids the
product renumbers are left out) (`merged:` lines). When copies differ in
anything else the object fails, naming every file, until `--prefer-source
<fragment>` picks one: the fragment is matched against each file's path
relative to the input it was found under, must match exactly one of the
files that define that object, and is a usage error (exit 2) when it matches
two of them, picks a different copy than another fragment, or matches no
file of any differing duplicate.

## Command and options

```
python3 -m vcfcf_extractor import-local INPUT... \
  --out DIR --layout content|third-party|pak \
  --ids keep | --ids mint [--mint-namespace TEXT] | --id-map TSV [--id-map TSV ...] \
  --naming unprefixed|factory-prefixed \
  [--rename TSV] [--drop TSV ...] [--target-min 8.18.7|9.0.2|9.1.1] \
  [--prefer-source FRAGMENT ...] [--project-name NAME] [--report-dir DIR] \
  [--no-verify] [--allow-partial] [--force] [--dry-run]
```

| Layout | Writes | Loader verification uses |
|---|---|---|
| `content` | `<out>/{supermetrics,views,dashboards,reports,symptoms,recommendations,alerts}/` (a factory `content/` tree; every name must carry `[VCF CF] `) | the factory per-type loaders |
| `third-party` | the same folders plus a `PROJECT.yaml` (`factory_native: false`), i.e. a `third_party/<project>/` | the factory bundle loader on `PROJECT.yaml` |
| `pak` | the same folders relative to an SDK adapter project, plus `import-report/bundled_content.yaml` to merge into `adapter.yaml`; its header names the other settings the content needs (`content_naming: unprefixed` for unprefixed names, `content_foreign_adapter_kinds` for symptoms and alerts on another adapter kind) | `sdk_builder._load_bundled_content`, then the pak version-floor and reference checks |

Output: one YAML per object, named from the object's name, each with a
comment naming its source file. A name that slugs to a file name Windows
reserves (`con`, `nul`, `aux`, `com1` ...) is written as `<slug>-<type>.yaml`
(noted); colliding slugs get `-2`, `-3`. `id_map.tsv` records the file of
every object. `--report-dir` (default `<out>/import-report/`) receives
`report.json` (everything below, per object), `id_map.tsv` (type, old id,
new id, name, the source name when it differs, file) and, for a pak, the
`bundled_content` snippet. An explicit `--report-dir` outside `--out` that
holds those files without import-local's marker is refused; one it wrote
before is rewritten.

**Writing is staged.** The tree is written into a temporary sibling of
`--out`, verified there, and moved into place only when the run succeeds
(exit 0, which includes partial results `--allow-partial` accepted). On any
other outcome `--out` is untouched and the run says `nothing written to
<out>` (an explicit `--report-dir` outside `--out` still receives the
report). `--out` must be absent or empty; `--force` replaces a non-empty
`--out` only when it carries `.vcfcf-import-local` (written by an earlier
run), whole, so no file of the earlier run is left behind; its
`PROJECT.yaml`, which may carry edited attribution, is kept (`KEPT` line).
Any other non-empty `--out` is refused with or without `--force`.

Exit status: 0 success; 1 a failure, a loss, an unsupported object, a
dashboard not deliverable to `--target-min`, or a verification difference
(`--allow-partial` accepts these, except in the pak layout a pak check
failure or a not-deliverable dashboard), or an unreadable input (never
accepted); 2 a usage or safety refusal, or the tree could not be written; 3
the stock-id guard refused the result; 4 verification compared nothing; 5 an
internal error in the converter on at least one object (never accepted).
Nothing is written on any non-zero exit.

## Ids: an explicit decision

One of these is required:

- `--ids keep`: the source ids. Right only for content that never shipped
  under someone else's id.
- `--ids mint`: a new id for every object, UUID version 5 from a namespace
  (`--mint-namespace TEXT`, default `project:<--project-name>`; one of the two
  is required) and the object's type and source id, so a rerun with the same
  namespace gives the same ids and a second import updates rather than
  duplicates (RULE-007). A recommendation gets `Recommendation-<uuid>`.
  `id_map.tsv` records old to new and, in its first line, the namespace.
- `--id-map TSV` (repeatable): `old_id<TAB>new_id` rows (a header row and
  extra columns are allowed) for some objects; the rest keep their ids. An
  entry that matches nothing is a warning. A destination may be another
  object's source id (a chain `A -> B, B -> C` or a swap `A <-> B`): the
  rewrite is one simultaneous substitution over source ids and never
  touches a definition's own final id, and the collision check runs on the
  ids that ship, so two objects ending on one id both fail.

With `mint` or a map, every reference follows: by name inside the set
(below), and in every string of every type the old id of a re-identified
object in the set becomes its new id. Super metric keys (`sm_<uuid>`,
`Super Metric|sm_<uuid>`) take the name form where the schema has one
(view columns and additional columns `supermetric:"<name>"`, formulas
`@supermetric:"<name>"`) and the new id everywhere else (symptom conditions,
including an alert file's inline symptoms, view subject filters, dashboard
widget metric entries, Pareto additional columns, Heatmap metrics, HTML,
`view_details`, metric links). After the rewrite every written object is
scanned for any old id of a re-identified object in the set, in any letter
case, keys included; a hit fails that object, naming the field (an object
that names it then fails too). A dropped object's id is not re-identified,
so it remains, which is the point of `--drop`.

Whatever the mode, the stock-id guard runs on the result before anything is
written: a definition under a VCF Operations stock id fails the run (exit 3),
listing each id with the hint to mint, map or drop. So `--ids keep` on content
that copied product ids fails loudly, which is the correct result. The guard
runs again on the loaded tree during verification.

`--drop TSV` (repeatable): ids (first column) not to emit, so the content can
reference the product object in place instead of shipping a copy. References
to a dropped view or dashboard stay raw ids (`view: <uuid>`, report
`view_id:` / `dashboard_id:`, navigation `dashboard_id:`). An alert cannot
name a symptom or recommendation by raw id, so an alert whose symptom is
dropped or absent fails with that reason.

A symptom, alert or recommendation whose source id is the one the renderer
derives from its adapter kind and name (`AlertDefinition-<kind>-<slug>`,
factory content without `id:`) is written without `id:`; with a rename or the
prefix that derived id changes, so such an object needs `--ids mint`.

## Names

Every change the converter makes to a name is a recorded rename (`RENAMED`
line, report, `source_name` column of `id_map.tsv`), including surrounding
whitespace the factory loaders strip. Two objects of one type whose final
names are equal once stripped both fail, naming both sources (dashboards
included: `X` and `X ` collide).

- `--naming unprefixed`: names as in the source (stripped).
- `--naming factory-prefixed`: `[VCF CF] ` on every name (the legacy
  `[VCF Content Factory] ` is replaced), and every by-name reference follows.
  Each dashboard's name length is printed; a prefixed dashboard name over 50
  characters fails (the factory loader refuses it) with the hint to rename.
- `--rename TSV`: `type<TAB>old name or id<TAB>new name` rows (`type` is
  `view`, `dashboard`, `report`, `symptom`, `alert`, `recommendation` or
  `supermetric`), applied before `--naming` to names and references alike.
  The type keeps a rename from touching another type's object of the same
  name; a row keyed by an id renames that one object, which is how two
  objects sharing a name are told apart.

Cross-references inside the set are by NAME (the factory convention): a
dashboard View widget's `view:`, report sections, navigation targets, alert
symptoms and recommendations, `supermetric:"<name>"` in view columns and
additional columns, `@supermetric:"<name>"` in formulas. Outside the set, by
raw id where the schema has a raw-id form (a note names each one: it must
exist on the target).

## Every source key is accounted for

Each object is reduced to its **flat form** (`vcfcf_core/importer/flat.py`):
every attribute, element text, JSON key and list position, by an exact path
(`ViewDef/Controls/Control{attributes-selector}/Property{attributeInfos}/List/Item[3]/Value/Property{displayName}@value`,
`widget[2:View].config.refreshInterval`). After a mapper has built the YAML,
the source accounting (`accounting.py`) classifies every key of the flat
form by an explicit per-type table:

- **converted**: the mapper carries it into the YAML (and refuses a value it
  cannot carry);
- **renumbered by the product**: not in the flat form at all, counted (view
  control and data-provider ids, the column `Item`'s `id` Property; widget
  ids, compared as position tokens `w<i>`; `entries` internal ids, resolved
  to adapter, kind and name; `extModel` ids; the View pin's Ext resource id;
  dashboard creation and update times and user ids; super metric
  `modificationTime` / `modifiedBy`);
- **constant**: a value the renderer always writes, with the renderer
  function named on the row (`refreshInterval: 300`, `Control visible`, the
  `customFilter` default, CoverPage `ContentKey` ...), or a value it derives
  (a widget's `config.title` is its `title`, a tag filter's `path` comes from
  its kinds, a Heatmap `groupBy.id` from its kind): the source must hold
  exactly that value;
- **recorded loss**: a class the fidelity docs list as not modeled (below);
- **GAP**: anything else, including a key no row matches. The object stops
  with the key named and a `TOOLSET GAP` block, so a key a future product
  version adds cannot vanish.

**Documented losses** (`model.DOCUMENTED_NOT_MODELED`, each with the doc that
lists it) convert, and each is recorded per object at the exact path(s) it
alters (`LOSS ... [at <path>]`): `localizationKey` on a view's or template's
Title or Description (template fidelity doc, DEF-018); a buckets-control on a
list view, an empty `preferredUnitId`, per-SubjectType filters that differ,
filter `values` lists and `conditionId`, `startSubUnit`,
`BlacklistResourceKind`, `includeNotExistingResources`, `cellLink`,
related-object columns, `objectType=POLICY`, per-column transformations on a
trend view, `localizationKey` on a column or summary-row `displayName`, a
second `displayName` in one column (the first is rendered; the dropped value
is in the loss line) (view fidelity doc); `adapterName`, the absolute-date
time range, `ext-element` UI residue states, navigation entries keyed by a
widget that is not on the dashboard, a `config.widgetId` naming no widget of
its dashboard (dashboard fidelity doc); super metric formula whitespace
outside quoted literals (`supermetric_authoring.md` §Formula whitespace).

**Stripped display strings.** The view, template, dashboard and super metric
loaders strip surrounding whitespace from many strings. Each one is in one
of three groups:

- **names** (view, template, dashboard and super metric names): a recorded
  rename (`RENAMED` line), as in §Names;
- **display strings**, a recorded loss at the key (`accounting.py`
  `STRIPPED_TEXT`, one row per key with the loader line): `Description` on
  a view, template, dashboard or super metric; a widget title; dashboard
  labels (metric entry `label`, `metricName`, `unit`; HealthChart and
  ParetoAnalysis metric names; Heatmap `colorBy` / `sizeBy` labels and
  group text); a Heatmap tab name; TextDisplay HTML; view column labels
  (column, additional column and summary-row `displayName`,
  `localizedAttributeName`, `instanceGroupName`,
  `localizedMetricToRelateWith`);
- **everything else** (keys, kinds, references such as a pinned resource's
  name or a widget's view, enumerations, `viewDetails` routes): not a
  loss. Surrounding whitespace there is a
  difference verification reports, or a GAP where the mapper checks first
  (a dashboard `namePath`, the folder, is the one name-like string still a
  GAP, since it is not recorded as a rename).

A display-string loss is accepted only where the render is exactly the
source stripped.

Some of these hold only under a condition the mark carries, so the loss
cannot cover more than the ruled shape: a whitespace loss is accepted only
where the render is exactly the source stripped (an interior change is a
difference); a formula loss only where the render is exactly the source with
its whitespace collapsed and every quoted literal unchanged (whitespace the
collapse would change inside a literal, or literals that cannot be
delimited, is a GAP before rendering); a `config.widgetId` loss only where
the source id is none of the dashboard's widget ids and the render writes
the widget's own (one naming another widget of the same dashboard is a GAP).

**GAPs seen on real content** (not documented, so the object stops): an
alert or recommendation description with leading or trailing whitespace
(the alert and recommendation loaders were outside the stripped-string
sweep); a value other than the renderer's constant (an AlertList or View with
`refreshContent: true`, a HealthChart unit other than `Default Unit`); 9.1.1
shapes the schema does not have (AlertList `alertDefinitions` as bare id
strings, MetricChart `relationshipMode` as a list); a time selector without
`count`, a column without `isStringAttribute`, a fractional `percentile`
(99.9), text and image views, a SymptomSet `aggregationOperator`, widget
types the schema does not model.

A mapper exception that is not a mapping refusal fails that one object as
`INTERNAL ERROR` (object, source file, exception type; counted in its own
summary column) and the run exits 5; the other objects are converted and
reported as usual.

A written YAML a loader refuses is not written: each object is staged and
loaded with the layout's loader first; one it refuses fails with the
loader's message, and so does every object that names it, to a fixed point:
by name (a dashboard's views and navigation targets, a template's views and
dashboards, an alert's symptoms and recommendations, a super metric named
`@supermetric:"<name>"` in a formula or `supermetric:"<name>"` in a view
column) or by key (a `sm_<uuid>` in a symptom condition, a view filter, a
widget metric). The same holds for a super metric that fails to map: a
`sm_<uuid>` key naming it fails the object that carries it. A render or
compare exception during verification is that object's `LOAD ERROR`, never
a traceback. A reference to an
object that failed fails the referencing object (named as a cascade, never
downgraded to a raw id).

## Target versions

Without `--target-min` the source is reproduced exactly, and every `omit:`
entry whose proven floor is above 8.18.7 (the oldest export read) or unknown
is a `VERSION:` warning, as is every widget that needs a newer product
(Section needs 9.1.1). With `--target-min <version>` an `omit:` entry whose
floor is above the target is not emitted (the key renders, as on every
export of that version). Each such deviation is listed as `TARGET` with the
one path and kind of difference it sets aside: `dashboard.temporary` (extra),
`dashboard.namePath` (extra), `dashboard.name` (value; `folder_in_name`
then puts the folder back into the name, said on that line),
`dashboard.widgetInteractions` (extra, and only as an empty list: an
interaction under it is a difference). Everything else in that object is
compared normally.

A dashboard carrying a widget type that needs a newer product than the
target (Section on 8.18.7 or 9.0.2) is **converted, not deliverable to the
stated target** (`NOT DELIVERABLE` line): the run exits 1. `--allow-partial`
accepts it in the content and third-party layouts (the dashboard is written;
it imports on the newer lines only), never in the pak layout (the pak build
refuses it). The caller's options: raise `--target-min` to the widget's
floor, drop the dashboard (`--drop`), or remove the widget from the source
before converting. For Section there is a fourth, after the import: convert
at a target that accepts it (or without `--target-min`), then add
`section_fallback: omit` to the written dashboard YAML. Builds and syncs
below 9.1.1 then leave the Sections out and say so
(`../wire-formats/dashboard_fidelity_wire_format.md` §Section fallback).
The importer never writes that key itself: no source key maps to it, and
it is the author's decision that the dashboard is complete without its
header rows. The `NOT DELIVERABLE` and `VERSION:` lines for a Section name
it. Floors: `widget_versions.py`, `reports/loader.py`,
`symptoms/loader.py` (dashboard fidelity doc §Omit version floors).

## Verification and its limits

Verification runs by default (`--no-verify` skips it and says that nothing
was checked; a run that recorded a loss still exits 1 without
`--allow-partial`). The staged tree is loaded through the real loader of the
layout (table above; if that loader refuses the tree as a whole,
verification stops and says so), each object is rendered with the factory
renderer, and the render's flat form is compared key by key with the
source's after the intended changes (new ids, names, the old-to-new id
rewrites) are applied to the source. A key on one side only is always a
difference; values are compared verbatim, whitespace included.

Per object the result is one of: **identical**; **identical apart from keys
forced by `--target-min`** (only at the recorded deviation paths); **differs
only at N recorded losses** (every difference is at a path the mapper
recorded when it dropped or altered something; the losses are listed); or
**differs** (the differences are listed). The summary states objects and
fields compared, these four counts per type, every difference class with
its objects and occurrences, the differences at recorded losses per loss
class, the forced target keys, and what was set aside.

Set aside, each counted and printed by class: the renumbered ids above;
**number spelling**, exact in `Decimal` (never through a float, so
9007199254740993 is not 9007199254740992): a JSON `1` equals `1.0`; an XML
value `70` equals `70.0` only at a key that is numeric by its semantics (a
column bound unless the column is a string attribute, bucket, count, size
and roll-up Properties, a filter operand that is not a string metric, a
symptom condition whose `valueType` is numeric, cycle counts, alert type and
sub-type, recommendation priority; `compare.xml_numeric`), and every other
XML value is the exact string (`"01"` is not `"1"`, in a verification and
when deciding whether two copies of one id are the same); a string never
equals a number, `true` never `1`; and order where the product keys an element by identity
(SubjectType, SubjectsGroupBy and Usage elements of a view, Controls by
type, Properties by name, JSON object keys, dashboard and widget `states` by
key). Every other list is compared by position.

Numbers are converted exactly: an integer spelling becomes a YAML integer
(never through a float), any other decimal a float only when that float is
the written value, else the object stops. Where a factory loader reads a
number through a float (view column bounds and bucket min / max; dashboard
metric entry bounds and `maxValue`, Scoreboard `boxHeight` and
`roundDecimals`, ParetoAnalysis and HealthChart bounds, Heatmap colour min
/ max; `accounting._FLOATED`), a value a float does not hold exactly stops
the object as a GAP rather than ship rounded. A bound on a string attribute
column is not a number: it is written and rendered as the exact source
string (`"0"` stays `"0"`; view fidelity doc §String-column bounds; until
2026-11-13 the loader respelled it and the view stopped as a GAP). Symptom
condition values are not floated on the content path and survive exactly.

Limits, each a place a difference can still pass or a check the run does not
make:

- The accounting classifies source keys that are present. A key the source
  leaves out and the renderer writes anyway (an `extra on render`), and a
  converted key a loader strips that is not a display string (a metric key,
  a pinned resource's name), are caught by verification, not before; with
  `--no-verify` they pass.
- A **converted** row trusts the mapper to carry the key; verification
  proves it. The tables were cross-checked against the mappers (no key the
  tables call converted goes unread, on the third-party pack, the 9.1.1
  export and the factory corpus), but with `--no-verify` a mapper bug on a
  converted key is not caught.
- Changes a loader makes that leave the render unchanged cannot be seen:
  two trailing spaces added to a name in the written YAML are stripped by
  the loader and the render is byte-identical.
- Unused rows of a dashboard file's shared `entries` table (no dashboard in
  the file references them) are not compared; they have no effect.
- The SDK pak build's owning-SubjectType injection on views is not rendered
  (a pak build adds one SubjectType per view; view fidelity doc), nor is the
  pak builder's `adapterName` (recorded as a loss).
- Verification says nothing about how an instance imports the content
  (install and look). The staged load and the layout loader do not run the
  factory's repo-wide checks, so validate the written tree as any authored
  content: the seven-package chain for `content/` and a third-party project
  (whose views and dashboards it walks, including the project-boundary check
  that refuses a super metric the project does not ship), and `validate-sdk`
  for a pak.

The mutation self-test (`tests/test_import_local_fidelity.py`) applies one
change at a time to the synthetic sources or to their written YAML and
requires every one to be reported: on the YAML side column, filter, unit,
sort, threshold, time window, widget position, title, HTML, navigation,
interaction (also on a dashboard with a target deviation), unit beside a
recorded loss, internal whitespace in a name and a display name, alert,
symptom, super metric and report fields; on the source side attributes on
ViewDef, DataProvider, a column Item, Usage and Title, a control Property
attribute, Control `visible`, a second control of one type, widget
`refreshInterval`, `isUpdatedView`, `config.title`, `config.widgetId`,
navigation `interactionType`, a `customFilter` resource, an unknown
dashboard key, a CoverPage `ContentKey`, a symptom Condition attribute and an
unknown super metric key.

Each conditional or ruled loss is tested from both sides: the tolerated
shape converts as exactly that recorded loss (each stripped display-string
class: view, template, dashboard and super metric Description, widget
title, metric label, TextDisplay HTML, view column label, tab name; a column and a summary-row `displayName` `localizationKey`, a
second column `displayName`, a `config.widgetId` naming a widget of another
dashboard, formula whitespace outside literals), and one step beyond it is
still caught. On the YAML side: an interior change to each of those
display strings, the kept `display_name` beside a
`displayName` loss, a dropped `widgetId`, a changed literal or token in a
formula carrying a whitespace loss. On the source side (each a GAP): a
`localizationKey` on a column `attributeKey` or an additional column's
`displayName`, a second `displayName` in a summary row, a second
`attributeKey` in a column, a `config.widgetId` naming another widget of the
same dashboard or not a widget id, formula whitespace inside a quoted
literal or beside an unbalanced quote or a backslash; and a metric key with
a trailing space is no loss and is reported as a difference.

## Results on real content (2026-11-13)

Third-party pak (not in the repo): 255 ViewDef copies of 189 unique views,
52 dashboards (one file of 34), 16 report templates, 4 alerts, 10 symptoms
(9 inline, 2 standalone, one shared), 1 recommendation, 2 super metrics; 22
files passed over (6 check-list XML, 2 XSD, 14 empty markers). Same id
defined differently: one view (its copy in `View - Set 4.xml` is the
superset and was preferred) and one symptom (the alert file and the
standalone file give it different names; the alert file's copy was
preferred). Each run takes 2 to 4 seconds.

- `--ids keep`: refused by the stock-id guard, 70 stock ids among the
  objects that convert, nothing written.
- `--ids keep`: every one of the 274 objects maps (no GAP); the stock-id
  guard refuses 120 stock ids among them, nothing written.
- With the 101-entry id map and the 19-entry drop list, third-party layout:
  every object converts: 170 views, 52 dashboards, 16 templates, 10
  symptoms, 4 alerts, 1 recommendation and 2 super metrics (the 4 views
  with a numeric-looking bound on a string attribute column, and the 2
  dashboards and 1 template on them, stopped until 2026-11-13). 255 objects
  and 46,117 fields compared: 152 identical, 103 differ only at recorded
  losses, 0 differ. The losses:
  Description whitespace on 51 views and 11 templates, `adapterName` on 34 dashboards,
  a buckets-control on 5 list views, a `config.widgetId` naming no widget of
  its dashboard on 3, stale navigations on 3, metric label whitespace on 2
  (11 Scoreboard labels), and one each of tab-name whitespace, formula
  whitespace, `displayName` `localizationKey`, Title / Description
  `localizationKey` and empty `preferredUnitId`. 11 view names lose trailing
  whitespace (recorded renames). The run exits 1 because losses were
  recorded; with `--allow-partial` it exits 0 and writes all 255.
- The same as a pak with `--target-min 8.18.7`: the same objects; 146
  identical, 6 identical apart from forced keys (`temporary` is forced on 11
  dashboards, the folder in the name and `widgetInteractions` on one each),
  103 differ only at recorded losses, 0 differ. "Overall Daily Check" and
  "vSphere Cluster Capacity 2.0" carry Sections, so they are not deliverable
  to 8.18.7, and the pak layout never accepts that: the run exits 1 even
  with `--allow-partial` (raise the target to 9.1.1 or drop them).
- `content/` layout with `--naming factory-prefixed`: 4 dashboards fail the
  50-character limit with the prefix and one template that names one of them
  cascades; 250 compared, 149 identical, 101 only at recorded losses, 0
  differ.

9.1.1 built-in export, views, report templates and dashboards (851 + 62 +
179), `--ids mint`, third-party layout: no internal error. 756 views, 56
templates and 43 dashboards convert (855 compared: 62 identical, 788 differ
only at recorded losses, mostly the Title / Description and `displayName`
`localizationKey` and empty `preferredUnitId`, 5 dashboards differ at real
mismatches: TextDisplay `editorData`, HealthChart bounds and
`relationshipMode`, a View state value); 95
views stop on the gaps listed above (fractional `percentile`, text views,
`relatedAdapterKind` columns, a metadata control without
`hideObjectNameColumn` ...), 134 dashboards on their own gaps (unmodeled
widget types, renderer constants) and 2 dashboards and 6 templates cascade.
The dashboards alone: 46 of 179 convert (4 identical, 36 only at recorded
losses, 6 differ at real mismatches verification reports); 133 stop, 26 of
them on widget types the schema does not model.
