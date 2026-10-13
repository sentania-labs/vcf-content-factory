# SDK adapter review: compliance build 89

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-13 (local, America/Chicago)
- **Adapter:** `content/sdk-adapters/compliance`, branch `feat/build-88-rollup-unmatched-pod-skip`, HEAD `70882cf` (9:03 AM), one commit on top of the build 88 review baseline `936e1fa`. Working tree clean before and after every check.
- **Artifacts:** author's `dist/vcfcf_sdk_compliance.0.0.0.89.pak` (built 9:02 AM), sha256 `62b60f1d...246f` (matches the brief); reviewer build from HEAD (scratchpad), sha256 `46b94c4b...0d35`. Reference: `dist/vcfcf_sdk_compliance.0.0.0.88.pak` (built 2026-10-12 3:54 PM, the post-W1 rebuild), sha256 `5e253764...a641`.
- **Prior pass:** `compliance-build-88.md` (APPROVE, 0 / 3 / 6)
- **Verdict:** APPROVE (0 BLOCKING / 1 WARNING / 1 NIT)
- **Fit for a devel install: YES.** Scott's go is recorded (`knowledge/context/approvals/2026-10-13-compliance-build-89-devel-install.md`, commit `bd62c02`).

## Bottom line

Build 89 does exactly what the commit says. The only pak change is the World Summary dashboard: the Section widget is gone, the six other widgets are byte-identical apart from `y` moving up one row (the Section was 1 row high), the grid has no gap and no overlap, and the vCenter view to AlertList interaction is unchanged. The adapter jar, describe.xml, views, reports and the other four dashboards are byte-identical to build 88. Every widget type left in the five dashboards is one that devel 9.0.2 accepted. The author's pak was built 54 seconds before the commit, but its contents match a fresh HEAD build entry for entry, so unlike build 88 it is not stale.

One warning: nothing automated stops a Section widget from coming back, and the failure it causes is silent (the install succeeds and the Summary tab just stays stock).

## Independent verification

| Check | Result |
|---|---|
| `git diff --stat 936e1fa..70882cf` | 6 files: `CHANGELOG.md`, `adapter.yaml` (build_number 88 to 89), `dashboards/compliance-world-summary.yaml`, `docs/README.md` and `docs/inventory-tree.md` (version stamp only), `docs/overview.md` (table cell plus a 5-line note). No `src/`, `tests/`, `ci/`, views or profiles. Matches the stated scope. |
| Dashboard YAML diff | Section widget `compliance_environment` removed; six widget `coords.y` reduced by 1 (2 to 1, 6 to 5, 14 to 13, 21 to 20); row comments renumbered. No other key changed. |
| `validate-sdk content/sdk-adapters/compliance` | OK (only the existing `-source 11` options warning) |
| `build-sdk` from HEAD into scratchpad | builds `0.0.0.89`, bundles the World Summary dashboard and `dashboards.properties (1 binding(s))`; adapter tree unchanged afterwards |
| Author pak vs reviewer pak (recursive, nested zips and jar unpacked) | 160 entries each; identical except `overview.packed`, whose 10 differing bytes are all zip local/central header mod-time fields (byte 75 vs 137 at offsets 10, 51, 98, ...). Content identical. |
| Pak 88 vs author pak 89 (recursive) | differs only in: both `manifest.txt` (version 0.0.0.88 to 0.0.0.89), `conf/version.txt` (Implementation-Version 0.88 to 0.89), `overview.packed` (timestamps), World Summary `dashboard.json`, and its `resources.properties` (the `Compliance Environment` title line removed). `vcfcf_compliance.jar` classes, describe.xml, views.zip, reports and the other four dashboards byte-identical. |
| `pak-compare` author pak 89 vs 88 | gate PASS, 0 BLOCKING / 0 WARNING / 0 INFO |
| `pak-compare` reviewer pak 89 vs 88 | gate PASS, 0 / 0 / 0 |
| `ci/run_java_tests.sh` | 12 Java suites pass; generator tests 16 OK; dashboard AlertList tests 6 OK |
| `pytest tests/` | 22 passed, 5 subtests |
| `scripts/generate_compliance_alerts.py --check` | "up to date" (136 + 6 alerts) |
| `defect-gate --pak compliance` | refuses on DEF-022 (correct: release gate, not a devel gate) |

## Rendered World Summary (inside the author's 89 pak)

- **No Section widget.** The string `Section` does not occur anywhere in the 89 `dashboard.json` (it does in 88). No other dashboard in the pak has a `"Section"` widget, and no YAML under `dashboards/` mentions one.
- **Grid.** Scoreboard (x1 y1 w9 h4), PropertyList (x10 y1 w3 h4), View (x1 y5 w12 h8), MetricChart (x1 y13 w6 h7), View (x7 y13 w6 h7), AlertList (x1 y20 w12 h7). A cell-by-cell fill of the 12 x 26 grid finds no overlap and no empty cell.
- **Widgets unchanged.** Each remaining widget, keyed by its id, is identical to build 88 with `gridsterCoords` removed from the comparison. Dashboard-level fields (everything but `widgets`) identical.
- **Interaction.** `widgetInteractions` identical to 88: provider `3a97cfb0` (Compliance by vCenter and Object Type) to receiver `370dc707` (Open Compliance Alerts), type `resourceId`. AlertList config still `depth: 4`, `type: ["15_21"]`, `alertDefinitions: []`, `selfProvider: false`.
- **Binding.** `content/dashboards/dashboards.properties` carries `VCF_Content_Factory_Compliance_World_Summary=vcfcf_compliance:ComplianceWorld`; the key matches the dashboard directory name.

## Widget types against 9.0.x

Types in the five bundled dashboards: World Summary uses Scoreboard, PropertyList, View, MetricChart, AlertList. The other four add ResourceList, Heatmap and TextDisplay.

Evidence, strongest first:

1. **Live import on the target build** (`knowledge/context/investigations/2026-10-12-compliance-pak-summary-binding.md`): on devel 9.0.2.0 Build 25137845 the other four dashboards imported with build 88 content, and their 89 bytes are identical to 88 (checked above). That covers ResourceList, Heatmap, TextDisplay, View, MetricChart, AlertList, PropertyList and Scoreboard as used in those files.
2. **The 9.0.2 `WidgetDTONew$WidgetType` enum** (same investigation): 47 constants (the earlier count of 48 included the values array), no `Section`, and it names Scoreboard, PropertyList, View, MetricChart and AlertList explicitly. Those are the five types left in World Summary.
3. **Pre-9.0 reference content** under `reference/references/` (HOL-2501 lab dashboards, vmbro vCommunity MP dashboards, AriaOperationsContent): Heatmap (7 files), TextDisplay (2), ResourceList (1), Scoreboard (12), PropertyList (7), View (20), MetricChart (2), AlertList (7), and **zero** Section. This fits Section being newer than this content and the other eight types being long-standing. `reference/docs/extracted/dashboard-widgets/` has Section only in the 9.2.0 export and the appliance templates, neither of which is 9.0.

Limit: I cannot touch devel, so (1) and (2) are the orchestrator-side investigation's findings, not something I reproduced. No 9.0-era exported dashboard with an explicit version stamp exists under `reference/`. The static evidence agrees with the investigation, and nothing contradicts it.

## Dimension walk

- **1 to 8 (correctness, vim25, exceptions, loader, stitching, logging, memory, API discipline):** not touched. No Java, profile or describe.xml change; the jar is byte-identical to the build 88 reviewer-checked jar.
- **9 Build hygiene:** build_number bumped, CHANGELOG line under Unreleased, minimal diff. The pak is not stale (content matches HEAD).
- **10 Gap honesty:** no new gaps. The existing Scoreboard color TOOLSET GAP comment is carried unchanged.
- **11 Docs parity:** `docs/overview.md` says the Summary tab binds on 9.0.x from build 89 and why the dashboards use no Section widgets. True of the pak. The README and the generated docs mention the Summary tab (build 88 W3) and still match behavior. No cross-MP change.
- **12 Registry:** below.

## Findings

### WARNING

**W1. Nothing automated stops a Section widget from coming back (owner: `sdk-adapter-author`).** Authority: skill § *Gaps, name them, never hide them* (the failure is silent), `knowledge/rules/validate-before-install.md`. The only guard against a repeat is prose in `docs/overview.md` and the CHANGELOG. `validate-sdk`, `pak-compare` and the tests all pass a dashboard with a Section widget. On 9.0.x the importer then drops the whole dashboard and the Summary tab stays stock, with the install reporting success. Finding that out cost an install cycle and an investigation. **Fix:** add a case to `tests/test_dashboard_alert_lists.py`, or a sibling test, that fails when any bundled dashboard YAML has `type: Section`, or that limits widget types to the eight now in use (Scoreboard, PropertyList, View, MetricChart, AlertList, ResourceList, Heatmap, TextDisplay), with the investigation cited as the reason. Does not block this build. A factory-wide check in `validate-sdk` would also work, but that belongs to `tooling` and is out of this review's scope.

### NIT

**N1. The 9.0.2 enum is recorded by count, not as a list (owner: orchestrator / `api-explorer`).** The investigation names 5 of the 47 `WidgetType` constants. Heatmap, ResourceList and TextDisplay are proven only by the four dashboards importing, not by the enum. Recording all 47 constants in `knowledge/context/api-surface/summary_dashboard_pak_binding.md` would let a future reviewer check a new widget type against 9.0.x statically. This is a factory knowledge file, not adapter code.

## Registry check (`knowledge/context/defects.md`)

Open defects with `Affects: compliance`: DEF-022, DEF-023. No `defects.local.md` exists.

- **DEF-022 (blocking, open): still present.** `src/com/vcfcf/adapters/compliance/ControlEvaluator.java:150-161` re-checked: when `actual` is null or empty and `allowsUndefined(expected)` is false, the branch hits `continue` without recording a result. Unchanged in 89 (no Java change). `defect-gate` correctly refuses a release.
- **DEF-023 (tracked, open): fix in place, closure still owed.** The build 88 paging fix (`ComplianceStitcher.java` around 266-307, `ComplianceDecisions.resourcePageOutcome`) is byte-identical in the 89 jar. Its close condition is devel proof (paging seen in the log, or the collection alert path exercised), which a static review cannot supply. Devel has 88 installed, so the proof can be taken there or on 89.

No new registration candidates. W1 is a missing guard, not a defect present in the shipped pak.

## If shipped as-is

On 9.0.x devel, upgrading over 88 should import the World Summary dashboard and bind it to ComplianceWorld, so the Summary tab shows the environment tiles, scan time, per-vCenter table, trend, SCG spread and the alerts for the selected vCenter. Without the header row there is no "Compliance Environment" title strip. Collection behavior is identical to 88.

## Closure 2026-10-13

- W1 closed: adapter commit 72c44e6 adds `tests/test_dashboard_widget_types.py`
  (allowlist of the eight types proven on 9.0.x) and wires it into
  `ci/run_java_tests.sh`.
- N1 closed: `summary_dashboard_pak_binding.md` now carries the complete 9.0.2
  WidgetType list (47, not 48; the earlier count took the values array as a
  type). `Section` is the only renderer type absent from 9.0.2.
