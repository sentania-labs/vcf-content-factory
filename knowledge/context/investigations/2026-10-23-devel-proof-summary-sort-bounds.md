# Devel proof: multi-row summary (#168), column sort (#175), descending Scoreboard bounds (#176)

- Run: 2026-10-23, 11:32 to 11:45 America/Chicago, qa-tester.
- Instance: profile `devel`, VCF Operations 9.0.2. Branch `feat/dashboards-168-175-176` (worktree run with `PYTHONPATH=src`).
- Method: one throwaway list view (`[VCF Content Factory] QA Throwaway Summary Sort 2026-10-23`, VirtualMachine, columns `cpu|usage_average` with `sort: desc`, `mem|usage_average`, `cpu|demandmhz`; `summary:` list of AVG on column 0 "Average" and MAX on column 1 "Maximum") and one throwaway dashboard (`[VCF Content Factory] QA Throwaway Bounds 2026-10-23`, Scoreboard on `mem|guest_usage` with bounds 90 / 80 / 70 plus a View widget embedding the view). Synced with `vcfcf_dashboards sync --profile devel` (restricted with `--views-dir` / `--dashboards-dir` pointed at temp dirs holding only the two files, since sync has no path argument), proven, then deleted with `delete-dashboard` and `delete-view`. Both gone (view GET 404, name lookup "not found"); worktree `git status` clean; nothing committed.
- Unsupported endpoint used: `GET /suite-api/internal/views/{id}/data/export?resourceId=<vSphere World>` with `X-Ops-API-use-unsupported: true`.

## Result

| Feature | Verdict |
|---|---|
| #168 two summary rows | PASS |
| #175 column sort | PASS |
| #176 descending Scoreboard bounds | PASS (stored form; see caveat) |
| Visual verification | SKIPPED (Playwright MCP failed to connect: CONNECTION_CLOSED) |

Sync output (no new post-import lines beyond the existing dependency check were printed):

```
state: FINISHED
  VIEW_DEFINITIONS     imported=1 skipped=0 failed=0 state=FINISHED
  DASHBOARDS           imported=1 skipped=0 failed=0 state=FINISHED
DEP-OK  OOTB metric check: all referenced metrics are defaultMonitored=true
```

## #168: two summaryInfos entries, in order

Content export (`VIEW_DEFINITIONS`, CUSTOM scope) of the installed view:

```xml
<Property name="summaryInfos"><List><Item><Value><Property name="displayName" value="Average"/><Property name="aggregation" value="AVG"/><Property name="attributeIndexes"><List><Item value="0"/></List></Property></Value></Item><Item><Value><Property name="displayName" value="Maximum"/><Property name="aggregation" value="MAX"/><Property name="attributeIndexes"><List><Item value="1"/></List></Property></Value></Item></List></Property>
```

Server-side render, the two summary rows (whitespace aside, verbatim), each aggregating only its own column (Average on the CPU column key `1`, Maximum on the memory column key `2`):

```json
{"summary": true, "1": 15.16903100775193, "groupUUID": null, "2": null, "3": null, "grandTotal": false, "objId": "Average", "objUUID": null}
{"summary": true, "1": null, "groupUUID": null, "2": 99.99380111694336, "3": null, "grandTotal": false, "objId": "Maximum", "objUUID": null}
```

This also closes the "inferred, not observed" gap in `wire-formats/dashboard_sort_color_default_summary_rows.md` for list views: several `summaryInfos` Items render as several `"summary": true` rows.

## #175: view opens sorted CPU descending

Exactly one `sortCriteria` Property in the whole view XML, on the CPU column, and none on the other two:

```xml
<Item><Value><Property name="objectType" value="RESOURCE"/><Property name="attributeKey" value="cpu|usage_average"/><Property name="isStringAttribute" value="false"/><Property name="adapterKind" value="VMWARE"/><Property name="resourceKind" value="VirtualMachine"/><Property name="rollUpType" value="AVG"/><Property name="rollUpCount" value="1"/><Property name="transformations"><List><Item value="CURRENT"/></List></Property><Property name="sortCriteria" value="false"/><Property name="isProperty" value="false"/><Property name="displayName" value="CPU Usage %"/><Property name="addTimestampAsColumn" value="false"/><Property name="isShowRelativeTimestamp" value="false"/></Value></Item>
```

Render with no widget input: 104 data rows, CPU column (`1`) strictly descending (first values 100.48, 92.97, 65.63, 41.19, 40.36, 35.59, 33.37, 31.85, 30.70, 28.43, 28.26, 28.00); a check `values == sorted(values, reverse=True)` was True.

## #176: Scoreboard bounds stored descending

The Suite API dashboard export only carries widget `config` after the deferred import phase 2 finishes (`importComplete` false and `config: {}` at first; see `api-surface/dashboard_import_two_phase_materialization.md`). Polling the export, it came back populated (`importComplete: true`) about 11 minutes after sync, at 11:44:

```json
{"yellowBound": 90, "metricUnitId": null, "metricName": "Guest Usage", "metricKey": "mem|guest_usage", "handleOldColoring": false, "maxValue": "", "link": "", "isStringMetric": false, "resourceKindName": "VirtualMachine", "resourceKindId": "resourceKind:id:3_::_", "label": "Guest usage", "orangeBound": 80, "unit": null, "id": "extModel34326-1", "redBound": 70, "colorMethod": 0}
```

Caveat: this proves the descending triple is rendered and stored unchanged. Whether the on-screen tile colors a low value as worse was not re-observed here (no browser); that behavior is the 2026-10-23 research replay in the wire-format file.

## Not proven

- Any on-screen render (dashboard, Scoreboard color, view in the View widget): Playwright MCP unavailable.
- Which column wins when several are sorted (the branch rejects it, by design).
- A `presentation: summary` view with a list `summary:` was not exercised.

## Notes for the next run

- The Suite API content export refuses a second export while one is running (403 "task is already running"); sequence exports, do not parallelize.
- `REQUESTS_CA_BUNDLE` in the shell breaks self-signed lab calls; unset it for ad hoc requests.
- The vcfcf_dashboards `delete-view` prints the UUID in place of the name for a view it cannot name; cosmetic.
