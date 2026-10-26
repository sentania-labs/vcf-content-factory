# Framework review: AlertList relationship_mode and depth bounds

- **Branch / commit:** `fix/alertlist-relationship-mode` @ `b826c49` (base `origin/main` @ `1a758dc`)
- **Date:** 2026-10-26
- **Reviewer:** framework-reviewer (RULE-013 gate)
- **Files:** `src/vcfcf_core/dashboards/loader.py`, `render.py`, `reverse.py`, `src/vcfcf_core/extractor/extractor.py`, `tests/test_dashboard_alertlist_relationship_mode.py`, docs
- **Evidence:** `knowledge/context/investigations/2026-10-26-alertlist-depth-semantics.md`

## Verdict: CHANGES REQUESTED (1 BLOCKING / 2 WARNING / 9 NIT)

The loader, renderer and depth bound are correct and the default output is byte-identical. The blocker is on the extraction path. When the source carries a relationshipMode the YAML can't express, the reverse parser rewrites it to `[-1, 0]`, so the extracted widget shows a different set of alerts. On `reverse-local` that rewrite is fully silent.

## Checks re-run

| Check | Result |
|---|---|
| Render regression: all dashboards in the main checkout (`content/`, `third_party/*`, `content/sdk-adapters/*`), base code vs branch code | 41 dashboards, 14 AlertList widgets, 0 load errors, **byte-identical** (`diff -r` clean) |
| Test suite, branch | 2879 passed / 6 failed / 10 skipped |
| Test suite, base | 2844 passed / 6 failed / 9 skipped. The same 6 fail on both. They are environmental: packaging validate needs the gitignored `content/sdk-adapters/synology/adapter.yaml` |
| New test file | 35 passed, 1 skipped (corpus test, see N5). That makes 36 tests, as claimed |
| Validate chain (7 packages) on branch clone | all rc=0 |
| pak-compare | n/a (no builder change) |

## Claims verified

- **relationship_mode as a name or a list, rendered in the order 1, -1, 0, default `[-1, 0]`.** Confirmed by probe and tests. `" Self "` normalizes. The reference corpus shows the same ordering: `[-1, 0]` in 12 widgets and `[1, -1]` in brockpeterson "Troubleshooting VMs v4".
- **Load errors for self+parents, an empty list, an unknown name, a duplicate, and raw ints.** Confirmed. `[True]` is rejected too.
- **depth outside 1 to 10, or not an integer, is a load error.** Partly confirmed: 0, -1, 11, 20, `"two"`, `True`, `1.5` and `None` are rejected. But `"5"` and `3.0` are accepted (N1).
- **The depth check only applies to AlertList.** Confirmed. ProblemAlertsList, Heatmap, ParetoAnalysis and ResourceList still load at depth 0 and 20, the same as base.
- **MetricChart relationship_mode does not regress.** Confirmed by probe. children renders scalar `-1`, parents `1`, omitted `0`. `self` and list forms are rejected exactly as on base. However, no test covers this path (W2).
- **Extraction keeps a self-only widget.** Confirmed. `[0]`, `[-1]`, `[1]` and `[1, -1]` round-trip through `reverse-local`, the loader and the renderer intact.
- **An unrepresentable value falls back to the default with a warning.** Refuted on one path. See B1.
- **Global import path vs pak path (anchor `00d3382`).** `_alert_list_widget` depends only on the widget, and both paths use the same function. No pak-local leak.
- **Key collisions (anchor `6c59f6b`).** Not applicable.
- **Stale zips / template version.** `render.py` is touched, but emitted output is byte-identical for all existing content. `template_version.py` asks for a bump only when the wire format changes, so no bump is needed. The hand-off does not say what happens to the rebuild (N8).

## BLOCKING

### B1. Extraction silently rewrites relationshipMode to a different alert set

Locations: `src/vcfcf_core/dashboards/reverse.py:995-1012` and `src/vcfcf_core/extractor/extractor.py:1015-1017`.

When the source `relationshipMode` is not one the loader accepts, the reverse parser sets `[-1, 0]` and the extractor omits the key. Observed via `_write_dashboard_yaml` (the reverse-local path), then loader and renderer:

| Source wire | Extracted YAML | Reloaded | stderr |
|---|---|---|---|
| `[1, 0]` (parents+self) | omitted | `[-1, 0]` (children+self) | nothing |
| `[1, -1, 0]` | omitted | `[-1, 0]` | nothing |
| `[]` | omitted | `[-1, 0]` | nothing (no warning even on the live path) |
| scalar `0` / unwrapped list | default | `[-1, 0]` | no warning |
| `[-1, -1]` | omitted | `[-1, 0]` (self added) | warning on live path only |

Why each path stays quiet:

- **reverse-local:** `reverse_local.py:616-624` records reverse warnings into `caught_warnings` and never reads them. The round-trip compare (`_compare_dashboard_round_trip`) matches only type and coords, so it reports MATCH.
- **live `/extract` path:** the warning is a bare Python `UserWarning` on stderr. Meanwhile the YAML validates green and installs a widget that shows other objects' alerts.

Authorities: dimension 8 (a silent downgrade is BLOCKING), RULE-001/002 (the source is the truth; don't fabricate a value it didn't carry), and the CLAUDE.md principle of never silently downgrading.

**On the brief's question:** yes, this should be an error, not a fallback. The smallest correct fix:

1. Carry the source ints through `AlertListConfig.relationship_mode` verbatim.
2. Have the extractor emit names for 1, -1 and 0, and the raw value for anything else.

The extracted YAML then fails `vcfcf_dashboards validate` with the loader's existing message ("cannot combine 'self' and 'parents'", "is not one of", "twice", "non-empty list"). That puts a human decision at the validate gate. Do not raise inside `parse_dashboard_json`: on the live path that drops every widget (`extractor.py:1274-1276`). Also warn on the non-list and empty forms instead of defaulting quietly.

## WARNING

### W1. Tests assert the meaning-changing fallback as correct and never check the warning

Location: `tests/test_dashboard_alertlist_relationship_mode.py:205-223`.

- `test_reverse_parses_relationship_mode` pins `[1, 0] -> [-1, 0]` as expected behavior, inside `simplefilter("ignore")`.
- Nothing tests the extractor emission (`_widget_to_yaml_dict`).
- There is no end-to-end round trip from wire to YAML to load to wire.

Fix: once B1 lands, assert a faithful round trip for representable values and validate failure for the rest.

### W2. The changed MetricChart guard has no MetricChart test

Location: `loader.py:3417-3432`.

`test_metric_chart_relationship_mode_unchanged` loads a TextDisplay only. No test anywhere renders a MetricChart with `relationship_mode`. This is the path where the array form once caused an Internal Server Error on load (`widget_types_survey.md` §MetricChart). The branch's probe-verified behavior is correct but unpinned. Dimension 10 asks for a regression test here.

Fix: parametrize children -> `-1`, parents -> `1`, omitted -> `0`, and reject self and list forms on MetricChart.

## NIT

- **N1** (`loader.py:2415-2437`). `depth: "5"` and `depth: 3.0` are accepted and coerced. That is out of step with the docstring's "must be an integer" claim. Either reject non-int types or document the coercion.
- **N2** (`reverse.py:994`). `int(cfg.get("depth") or 1)` has three problems:
  - It maps depth 0 to 1 silently. The source is a broken widget, and extraction quietly repairs it.
  - String `"0"` passes through as 0.
  - A non-numeric value throws and drops every widget on the dashboard.

  This line predates the branch, but it now contradicts the documented rule. Emit the source value faithfully so validate flags it.
- **N3** (`reverse.py:1003`). `int()` coercion accepts `[True]` as parents, `[0.9]` as self and `["0"]` as self. Accept real ints only.
- **N4** (`loader.py:3419-3429`). On a non-MetricChart, non-AlertList widget, `relationship_mode: self` gets "must be 'children', 'parents', or omitted" (seen on Heatmap) before the type check runs. Now that `self` is valid on AlertList, that message misleads. Check the type first.
- **N5** (`tests/...:236`). `test_repo_alertlists_render_default_mode` finds AlertList dashboards only under the gitignored `content/sdk-adapters/`. It therefore skips in CI and in any fresh clone. Add a committed fixture, or say in the test that it is a dev-only check.
- **N6.** `relationship_mode: self` with `depth` other than 1 is accepted without comment. The editor disables depth for self-only, so the value is inert. Mention this in the design guide or warn.
- **N7** (docs). The `parents` (`[1]`) mode was not replayed live: the evidence doc lists it under "Not tested". `[1, -1]` has reference backing (brockpeterson Troubleshooting VMs v4). The design guide and survey present `parents` without that caveat.
- **N8** (CLAUDE.md "After tooling changes"). `render.py` is touched, but neither the commit nor the hand-off says what happens to the `content-packager` rebuild. Output is proven byte-identical, so the rebuild is a no-op and no template bump is needed. The orchestrator should record that decision rather than skip it silently.
- **N9** (docs). The editor's default for a new widget is Parent+Children (`[1, -1]`), while the factory default is `[-1, 0]`. Worth one line in `widget_types_survey.md` §AlertList so nobody "fixes" the default to match the UI.

## Follow-ups (code the branch does not touch; issue, not a fix here)

- `src/vcfcf_core/extractor/reverse_local.py:616-624`: `caught_warnings` is dead. Every reverse-parser warning is discarded on the reverse-local path, not just this one.
- ProblemAlertsList `depth` is unbounded. It may hit the same `problemalerts.action` check, but that is unproven and needs an investigation before any loader rule.

## If shipped as-is

Authoring and rendering are fine. An operator who extracts a dashboard whose AlertList carries parents+self (or another value the YAML can't express) gets YAML that validates green and installs a widget showing children's alerts instead of parents'. On reverse-local nothing on screen says so.
