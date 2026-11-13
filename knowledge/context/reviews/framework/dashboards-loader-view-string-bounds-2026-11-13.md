# Framework review: view string-attribute column bounds (2026-11-13)

- Branch: `tooling/view-string-bounds`, commit `55ad900d`, diff against
  `origin/main` (`d7191232`).
- Touched: `src/vcfcf_core/dashboards/loader.py`,
  `src/vcfcf_core/importer/{accounting,compare,views}.py`, tests
  `tests/test_view_string_bounds.py` (new), `tests/test_import_local_fidelity.py`,
  four `knowledge/context/` docs.
- Verdict: **APPROVE**. 0 BLOCKING / 1 WARNING / 4 NIT.

## Claims and what I checked myself

| Claim | Re-run | Result |
|---|---|---|
| Render of every existing view is byte-identical | Loaded and rendered all 66 view YAML (worktree `content/`, `third_party/`, `tests/fixtures/`, plus the gitignored pak repos `content/sdk-adapters/*/views` and `third_party/` of the main checkout) under `origin/main` src and branch src, SM refs through a fixed resolver, then compared sha256 | 66/66 identical, 0 load errors on either side. All 5 YAML files in the repo that set `is_string_attribute` are in that set, and the change only acts when that flag is set |
| No existing YAML trips the new load error | Same run | 0 errors. Every `is_string_attribute:` in the corpus is an unquoted YAML bool |
| `import-local` converts the former GAP views, verified exactly | vCommunity 0.8.1 (`--ids mint`) and hardware vCommunity (`--ids keep`), main vs branch | vCommunity: views 172 to 176 converted, 111 to 115 identical, 0 differ. Hardware: views 6 to 8, 8/8 identical. The YAML of objects that already converted is byte-identical between main and branch (only new files were added) |
| A one-character change of a string bound is caught | Own probe: 22 tricky source strings round-tripped (all identical), then mutated `' x '` to `' x'`, `'1.0'` to `'1'`, `'.5'` to `'0.5'`, `''` to `' '`, `'Off'` to `'off'` | Every mutation reports `differs` |
| Numeric-column values a float cannot hold still stop | `test_a_value_a_loader_rounds_through_float_is_a_gap` (more-digits case kept) | passes |
| Local CI | seven validators; `bash scripts/path_reference_audit.sh`; full pytest on branch vs a `git archive origin/main` tree | validators all rc=0; audit clear; pytest branch 20 failed / 4601 passed / 15 skipped, main 20 failed / 4592 passed. The 20 failures are the identical set on both (doctor venv/jmespath, real-repo release/publish), so they are baseline |

YAML spellings probed on a string column (branch): `"0"` / `'0'` give
`0`; `0`, `.nan`, `yes`, `Off`, `010`, `0x10`, `1.50`, `2024-01-01` are load
errors; `none`, `"none"`, `1e3`, `"1e3"`, `NaN`, `"NaN"`, `""`, `" "`,
`"a&b<c\"d"` are kept verbatim (XML-escaped on render); empty value and `~`
mean no bound. Under main, `yes`/`Off`/`010`/`0x10` rendered `1.0`/`0.0`/`8.0`/`16.0`
without any error, so the new error fixes a silent corruption.

## Dimensions

1. Global vs pak leak: the change keys only on the column's own
   `is_string_attribute`. No pak or path condition. The content-import path,
   pak path and SDK builder all go through the same `load_view`, then
   `render_views_xml`. Inert for every column without the flag (66/66 identical).
2. Key collisions: none. No key or label derivation touched.
3. Wire format: `view_column_wire_format.md` §Per-column color thresholds says
   to coerce bounds to strings at render. A str bound renders through `str()`
   and `_xml_property` escaping (probe confirmed `&`, `<`, `"`). The vendor
   scan (all `reference/`, 92 string-column Items with bounds) shows bounds
   like `0`, `.5`, `.75`, `Off`, `none`, `true` on string columns. Those now
   reproduce exactly.
4. Loader/validator: `numeric_bound` replaces both copies of the numeric
   test (omit check, color validation). The ordering warning and
   ascending-required rule are skipped for string columns (documented).
   `additional_columns` load through the same `_load_column`; they reject
   bounds anyway.
5. Render regression: clean (above).
6. Builder: not touched.
7. Corpus: clean (above).
8. Silent downgrade: none. The only behaviour removed is the GAP, now a
   verified exact conversion. One new rejection is undocumented (N1).
9. Stale zips: `render.py`, templates, builders and `assembly.py` are not
   touched. The loader change produces byte-identical output for every view
   in the repo and the pak repos, so no distributed zip changes and no
   `CURRENT_TEMPLATE_VERSION` bump is needed.
10. Tests: loader, render, error, numeric-unchanged, end-to-end importer and
    one-character verification are covered. Missing: the error hint for
    YAML-coerced spellings (W1) and the ascending_range false case (N1).

Other consumers that still float: `dashboards/reverse.py` `_parse_bound`,
`extractor/extractor.py` and `extractor/reverse_local.py` float bounds, and
none of them carries `isStringAttribute` (N4). `importer/dashboards.py`,
`render.py` `_num_json` and the MetricSpec `_to_bound` handle dashboard
widget metric bounds, not view columns, and are outside this change. No
second copy of the numeric-bound test remains in the loader. Summary rows:
the renderer's summaryInfos Items carry no bounds. `compare._COLPROP` covers
summaryInfos, so a bound there would be compared with the same rule.

## Findings

### WARNING

**W1. The load-error hint respells the value YAML already coerced.**
`src/vcfcf_core/dashboards/loader.py` `_text_bound` (about lines 3609-3622)
builds the example from the parsed value and says "quote it as written in
the source". YAML 1.1 has already rewritten the author's text by then.
Repro, on an `is_string_attribute: true` column:

```
red_bound: Off    ->  ... quote it as written in the source (e.g. red_bound: "false")
red_bound: yes    ->  (e.g. red_bound: "true")
red_bound: 010    ->  (e.g. red_bound: "8")
red_bound: 0x10   ->  (e.g. red_bound: "16")
red_bound: 1.50   ->  (e.g. red_bound: "1.5")
```

An author who follows the hint ships a different match string. The view
loads, the column never colours, and no tool reports it. This is a real
vendor case: 4 hardware-vCommunity Dell columns carry `redBound="Off"` on
string columns. Authority: `view_fidelity_wire_format.md` §String-column
bounds ("names the bound and the quoted spelling to write").
Fix: do not build a spelling from a coerced value. For a bool, say YAML
reads yes/no/on/off/true/false as a boolean. For an int or float, say YAML
read it as a number. In both cases ask the author to quote the exact text
VCF Ops shows. Alternatively, recover the scalar's source text from the node
marks. Add a test with `Off` and `yes`.

### NIT

**N1. A string-column shape that main accepted is now rejected, and nothing
documents it.** If `is_string_attribute: true` and the only bound is a
numeric-looking `red_bound: '0'` with `ascending_range: false`, main loaded
it as a numeric bound. The branch raises "with only a string red_bound
(property-match coloring) ascending_range may be omitted or true". The same
happens with `is_string_attribute: true` on a metric column (`cpu|usage_average`,
`red_bound: '90'`, `ascending_range: false`). The repo corpus has 0 such
columns and the reference corpus has 0 (all 45 red-only string columns carry
`true`). `import-local` reports the case cleanly ("the written YAML does not
load"), where before it stopped as a GAP. Fix: add one line to
§String-column bounds saying the property-match ascending rule now applies
to every bound on a string column, plus a test.

**N2. `is_string_attribute` is read by truthiness.** `_load_column` uses
`c.get("is_string_attribute")` and the dataclass uses `bool(...)`. So
`is_string_attribute: 'false'` makes the column a string column, and with
`red_bound: 0` the new error tells the author it is one. The flag also
renders `isStringAttribute="true"`, which predates this branch. The corpus
uses only unquoted bools. Fix: read it with `_opt_bool`, which already
exists in the loader.

**N3. "One definition" is overstated.** The `compare.string_attribute_bound`
docstring says it is "the one definition the importer, accounting and the
comparison share". `importer/views.py` (`d.get("isStringAttribute") == "true"`,
then `col.get("is_string_attribute")`) and `loader._load_column` each derive
it again. I checked that they agree on every input the importer can write.
Both take the first of any repeated Property (`_item_props`, and the flat
form's unsuffixed key). A wire `"True"`/`"TRUE"` is treated as numeric by
both, and verification flags the `isStringAttribute` value difference.
Fix: reword the docstring, or route `views.py` through a shared predicate.

**N4 (follow-up issue, untouched code). The reverse paths lose the flag and
float the bound.** `dashboards/reverse.py` `_parse_bound`,
`extractor/extractor.py` and `extractor/reverse_local.py` never carry
`isStringAttribute`. They write `orangeBound="0"` from a string column as
`orange_bound: 0.0`, which renders `isStringAttribute="false"` and `0.0`.
That is the same defect this branch fixes, on `/extract`. The new doc
paragraph says those paths "keep the float behaviour", which reads as fine.
Fix: call it a known loss in §String-column bounds and open a follow-up
issue for the extractor paths.

## If shipped as-is

Operators get exact string-column bounds and four more vCommunity views and
two more hardware views that import-local converts and verifies as
identical. Existing content renders byte-for-byte as before. The one real
trap is W1: an author who hand-writes `red_bound: Off` and follows the error
hint ships a column that silently never colours.
