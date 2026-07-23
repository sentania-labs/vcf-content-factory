# ResourceList widget "Show Columns" persistence — wire format

Investigation date: 2026-07-22. Instance: `vcf-lab-operations-devel`
(VCF Operations 9.x). Ground truth: the CPU Support Status dashboard
`b6796122-4c9b-4770-83d8-10f785755ef2`, ResourceList scope-picker widget
`f9c1e72c-25c0-5372-b865-8e4d64202d52`, which the operator had manually
set to **Name-only** in the UI before this capture.

> **Unsupported-surface caveat.** Everything below is the `/api/content`
> export/import wire format plus the internal `/ui/dashboard.action`
> UI-session endpoints. The content import/export endpoints are public
> Suite API; the `states[]` grid-state blob itself is an **internal Ops
> UI (ExtJS) persistence artefact** with no published schema and may
> change between releases. It is not covered by any OpenAPI spec
> (grepped both `operations-api.json` and `internal-api.json` — no
> `states` / `permResGrid` / column-grid-state schema in either).
> Treat the blob as opaque. Any tooling that *reads* it to make
> decisions should carry the `X-Ops-API-use-unsupported` warning
> discipline; here we only *reproduce* a captured constant.

## TL;DR

- `states[]` lives at the **top level of the widget object** (sibling of
  `config`, `type`, `gridsterCoords`), not inside `config`. Each element
  is exactly `{"value": <encoded-grid-state>, "key": <state-id>}`.
- For a **ResourceList**, the `key` is
  `permResGrid_widget_<DASHBOARD_UUID>_<WIDGET_UUID>`.
- The `value` is a multi-URL-encoded ExtJS grid state. Decoded, it is a
  47-entry column list. Column ids are **generic** (`h1`…`h16`,
  `resourceRating`, `h18`…`h47`) — they do **not** embed the widget/dash
  UUID, so **the decoded/encoded `value` for "Name-only" is a constant**.
  Only the `key` varies per widget.
- **`h15` is the Name column.** In the operator's confirmed Name-only
  state it is the *only* column with `hidden=b:0`; every other column is
  `hidden=b:1` or default-hidden.
- **Import survival: CONFIRMED.** A dashboard imported via
  `POST /api/content/operations/import` with the `states[]` blob present
  retains it verbatim (verified by API readback). The importer does not
  strip it.
- **Scoping:** the blob is stored **in the dashboard definition** (it
  travels in the content-zip export and survives import), so it ships to
  all viewers as the default. See caveat in §5 about per-user live
  overrides.

## 1. The `states[]` grammar (decoded)

The decoded `value` is a single ExtJS state object:

```
o:columns=a: <col> ^ <col> ^ <col> ...
```

- `o:` = object, `a:` = array, `s:` = string, `b:` = boolean, `n:` = number.
- `^` separates fields within a column record **and** separates column
  records from each other (flat delimiter; a new record begins at each
  `o:id=s:`).
- Each column record is `o:id=s:<colId>` optionally followed by
  `^hidden=b:<0|1>` and `^width=n:<px>` (and, when the user has reordered,
  `^index=n:<pos>` — seen on TableView captures, not on this ResourceList).

A column entry with **no** `hidden` field (just `o:id=s:hN`) carries no
override and falls back to that column's built-in default visibility
(for ResourceList metadata columns, default = hidden).

### Column roster for a ResourceList — 47 entries

Positional order in the blob (index → id → flag in the Name-only ground truth):

```
 0  h1              hidden=b:1
 1  h2              (default — no hidden attr)
 2  h3              hidden=b:1
 3  h4              (default)
 4  h5              (default)
 5  h6              (default)
 6  h7              hidden=b:1
 7  h8              hidden=b:1
 8  h9              hidden=b:1
 9  h10             hidden=b:1
10  h11             hidden=b:1
11  h12             hidden=b:1
12  h13             hidden=b:1
13  h14             (default)
14  h15             hidden=b:0   <-- NAME (only visible column)
15  h16             hidden=b:1
16  resourceRating  hidden=b:1   <-- health/rating column (named id, occupies slot 17 in place of "h17")
17  h18             hidden=b:1
...
46  h47             hidden=b:1
```

Notes:
- There is no `h17`; slot 17 is the named `resourceRating` column.
- **Empirically certain:** `h15` = Name (it is the single `hidden=b:0`
  column in a UI-confirmed Name-only picker), and `resourceRating` = the
  health/rating badge column.
- The remaining `hN` are the ResourceList metadata columns in ExtJS
  internal grid order. That internal order does **not** match the
  "Show Columns" dialog list order the operator reads (ID, Name,
  Description, Adapter Type, Object Type, Policy, Creation Time,
  Identifier 1–5, Object Flag, Collection State, Collection Status,
  Internal ID, Relevance) — so do **not** assume h1=ID, h2=Name, etc.
  Individually labelling every `hN` was **not** required to ship
  Name-only and was not attempted (would need a per-column probe). The
  load-bearing fact is `h15 = Name`.

## 2. Canonical Name-only `states[]` — quote verbatim

The renderer must emit, at the ResourceList widget's top level:

```json
"states": [
  {
    "value": "<CONSTANT VALUE BELOW — copy byte-for-byte>",
    "key": "permResGrid_widget_<DASHBOARD_UUID>_<WIDGET_UUID>"
  }
]
```

- `key`: substitute the dashboard UUID and the ResourceList widget UUID.
  Nothing else in the key is variable.
- `value`: the **constant** string below. It is byte-identical between the
  `working_dashboards.json` capture and the live CPU dashboard export;
  column ids are generic so it is reusable across any ResourceList.

Verbatim `value` (single line, no whitespace — 4244 bytes):

```
o%3Acolumns%3Da%253Ao%25253Aid%25253Ds%2525253Ah1%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah2%255Eo%25253Aid%25253Ds%2525253Ah3%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah4%255Eo%25253Aid%25253Ds%2525253Ah5%255Eo%25253Aid%25253Ds%2525253Ah6%255Eo%25253Aid%25253Ds%2525253Ah7%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah8%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah9%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah10%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah11%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah12%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah13%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah14%255Eo%25253Aid%25253Ds%2525253Ah15%25255Ehidden%25253Db%2525253A0%255Eo%25253Aid%25253Ds%2525253Ah16%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253AresourceRating%25255Ehidden%25253Db%2525253A1%255Eo%25253Aid%25253Ds%2525253Ah18%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah19%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah20%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah21%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah22%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah23%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah24%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah25%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah26%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah27%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah28%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah29%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah30%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah31%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah32%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah33%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah34%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah35%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah36%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah37%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah38%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah39%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah40%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah41%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah42%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah43%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah44%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah45%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah46%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100%255Eo%25253Aid%25253Ds%2525253Ah47%25255Ehidden%25253Db%2525253A1%25255Ewidth%25253Dn%2525253A100
```

### Encoding note (if the renderer builds it rather than pastes it)

The value is **not** a single URL-encode. It is ExtJS `Ext.state`
depth-encoding: each nesting level of the object graph adds a
`urllib.parse.quote` pass. `urllib.parse.unquote` applied 4× yields the
clean `o:columns=a:o:id=s:h1^hidden=b:1^width=n:100^…` string. The
outermost tokens (`o:`, `a:`) are singly-encoded (`%3A`), array-element
fields are progressively deeper (`%25253A`, `%2525253A`). **Recommended:
paste the constant above verbatim; do not re-derive the encoding.**

## 3. Import survival — CONFIRMED

Method: exported the live CPU dashboard JSON (which carries the blob),
cloned it to a throwaway dashboard `[VCF Content Factory] XPROBE
states-survival` with a fresh UUID, rewrote the `states[].key` to the new
dashboard UUID, packaged it into a content-import zip (marker +
`configuration.json` + `usermappings.json` + `dashboards/<owner>` inner
zip holding `dashboard/dashboard.json`), and POSTed to
`/api/content/operations/import?force=true`.

Result: import `state=FINISHED`. API readback via
`/api/content/operations/export` (DASHBOARDS) showed the ResourceList
widget with **1 states entry preserved**, `h15^hidden=b:0` intact,
`resourceRating` present, 47 columns — byte-identical to what was sent.
**The content-route importer preserves `states[]` verbatim; it does not
strip it.** Cleanup: the XPROBE dashboard was deleted via
`dashboard.action deleteTab` and its absence re-verified (0 XPROBE
dashboards remain).

> **Correction to a stale in-code comment.** `src/vcfops_dashboards/reverse.py`
> (~line 905) says the `states[]` array "is ignored on import and skipped
> here." That statement is about the **reverse→YAML** direction only —
> `reverse.py` chooses to drop `states` when generating YAML. It is **not**
> a statement about the import endpoint, which (as proven above) honors
> `states`. Do not read that comment as "the server ignores states."

## 4. Renderer implication

To author a Name-only ResourceList today, the renderer/loader must be able
to emit a top-level `states[]` array on the ResourceList widget with the
constant `value` and a `key` templated as
`permResGrid_widget_<dashUuid>_<widgetUuid>`. This requires the widget/dash
UUIDs to be known at render time (they are — the renderer assigns them).
`reverse.py` currently **drops** `states`, and the dashboard loader/render
path does not currently carry it (grep `states` in `src/vcfops_dashboards/`
before implementing). This is a **tooling** change, not authorable in YAML
until the renderer supports a `columns:`/`show_only:` style directive that
compiles to this blob. Simplest first cut: a per-widget escape hatch that
passes a literal `states[]` through render unmodified, with the `key`
UUIDs substituted.

## 5. Scoping caveat — per-dashboard vs per-user

- The blob is stored **in the dashboard definition**. Evidence: it comes
  out of the `/api/content` **dashboard export** (part of the dashboard
  object, not a user-preferences endpoint), and it **survives import into
  a brand-new dashboard**. So shipping the `states[]` blob in the imported
  dashboard delivers Name-only **as the default for every viewer** on
  first load. This is what we want.
- The operator's manual "Show Columns → Name only" edit in the UI **was
  persisted back into the dashboard definition** (that is exactly the blob
  we read from the live export). So an owner's UI change to the picker
  becomes the shipped default — good.
- **Caveat (unverified, ExtJS-standard behavior):** ExtJS grids also keep
  a **live per-user grid state** keyed by the same `permResGrid_widget_…`
  stateId. If a *viewer* later hides/shows columns themselves, that
  per-user state can override the baked-in definition **for that viewer
  only**, and it is stored outside the dashboard definition (user prefs /
  browser-side state), so:
  - Re-importing the dashboard will **not** clobber a viewer's own
    per-user override.
  - A viewer who has never touched the picker gets the baked default from
    the `states[]` blob.
  This means the `states[]` blob is the correct and sufficient ship
  vehicle for "everyone sees Name-only by default"; it does not and cannot
  force a viewer who has made their own column choice back to Name-only.
  This per-user override layer was **not** exercised in this
  investigation (would require a second user account); flagged as a known
  boundary, not a proven behavior.

## Cross-references

- Widget `states[]` general note: `knowledge/context/api-surface/widget_types_survey.md`
  (§ states are optional URL-encoded UI prefs).
- Content-zip import wire format: `knowledge/context/wire-formats/wire_formats.md`.
- Import client / marker discovery: `src/vcfops_dashboards/client.py`.
- Dashboard export helper used for ground-truth capture:
  `src/vcfops_extractor/extractor.py` `_export_dashboard_json`.
