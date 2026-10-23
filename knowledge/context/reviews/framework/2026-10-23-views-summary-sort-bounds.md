# Framework review: views summary rows, column sort, widget bounds order (#168, #175, #176)

- Branch: `feat/dashboards-168-175-176` at `b17ce9a` (src commits c97b00d, e5f9081, b17ce9a on docs commit f7752f1; merge base `10b1ad0` = origin/main)
- Touched src: `src/vcfcf_core/dashboards/loader.py`, `src/vcfcf_core/dashboards/render.py`
- Reviewer: framework-reviewer (RULE-013 gate), 2026-10-23
- Verdict: **CHANGES REQUESTED** (1 BLOCKING / 3 WARNING / 1 NIT)

## Bottom line

The renderer side is clean: every view and dashboard the factory owns renders
byte-identical, every built bundle is identical apart from its build timestamp,
and the sortCriteria position matches all 395 vendor occurrences. The problem
is the new summary-row allowlist: it rejects `DEVIATION`, an aggregation a
shipped vendor management pack uses, while it accepts `COUNT`, which no export
carries. The allowlist rests on a corpus inventory in the evidence doc that
only looked at loose files and missed the vendor paks.

## Checks re-run (independently, in detached worktrees of origin/main and the branch tip, pak clones symlinked)

| Check | Result |
|---|---|
| Seven-package validate chain (branch) | all seven rc=0 |
| pytest, full suite (branch) | 2205 passed, 9 skipped, 131 deselected (matches the author's claim) |
| Render regression, my own baseline from origin/main (not the author's `before/`) | 247 views + 42 dashboards across `content/`, `third_party/`, all pak clones, `tests/fixtures`: 0 load errors on either side, `diff -rq` IDENTICAL |
| Bundle build, base vs branch (`build --all` + `build bundles/releases/*.yaml`, `--no-live-describe`) | 13 zips each side; nested contents identical except `vcfops_manifest.json` `built_at` |
| HealthChart `sort_by_dir` | vcommunity `Critical Business Applications` renders `orderByDir: desc` identically on base and branch |
| Em-dashes in added lines | 0 |

## Corpus scans (reference/references, including zips and pak-in-pak `adapters.zip`)

- **sortCriteria position**: 395 of 403 column Items carry it between
  `transformations` and `isProperty` (the renderer's position); 5 on
  time-segment pseudo-columns (`rollUpCount` -> `isTimeSegment`, already
  emitted by `_xml_time_segment_item`); 3 on instanced-group drivers
  (`rollUpCount` -> `isInstancedGroup`). Value semantics true=asc,
  false=desc per the doc's UI-source citation and devel live render.
- **Views with several sorted columns**: 91 of 214. The one-column limit is
  a stated, loud restriction ("which wins is unverified"); acceptable.
- **No time-segment view carries a second sorted column**; the
  sort-beside-time_segment rejection agrees with the corpus.
- **sortCriteria by view type**: 197 list views, 17 distribution views
  (bar/pie/donut).
- **summaryInfos**: 78 distinct views, all `list-view`. Aggregations:
  SUM 58, AVG 29, MAX 15, MIN 9, **DEVIATION 1**, COUNT 0. 14 views with
  `presentation: list` carry several summary rows (Citrix XenDesktop, Oracle
  EM, HPE, IBM Db2 paks under `reference/references/tvs/`).
- **Widget bounds, color method 0**: Scoreboard 205 ascending / 28
  descending, MetricChart 45 ascending, PropertyList 7 descending, **0
  mixed**. The new order rule rejects nothing the vendor ships; ties count
  as either direction, and a genuinely mixed triple (e.g. 1/2/1, 70/50/90)
  fails both comparisons, verified in code and by the new tests.

## Findings

### BLOCKING

1. **`src/vcfcf_core/dashboards/loader.py:317`** (`_VALID_SUMMARY_AGGREGATIONS`).
   Authority: vendor export `reference/references/tvs/OracleEnterpriseManager-9.0.0_b20231005.113304.pak`
   -> `adapters.zip` -> `oem_adapter3/conf/reports/Oracle Database Instance Bottlenecks Report.xml`,
   view `Oracle Databases Overview`: a list view with four summary rows, the
   fourth `displayName="Standard Deviation" aggregation="DEVIATION"`. RULE-002
   (no fabrication; the allowlist must be traced to evidence).
   Before this branch `aggregation: DEVIATION` loaded and rendered that exact
   vendor shape; now it is a load error whose message implies the value does
   not exist. Meanwhile `COUNT` is admitted and tested
   (`tests/test_view_summary_rows.py:128`) with zero vendor occurrences. The
   allowlist is the inverse of the evidence on both ends. Output path: the
   loader, so every path (standalone content-import and pak) loses the
   capability.
   Fix: add `DEVIATION` to the set, add an accept test for it, and update the
   SummaryRow docstring (loader.py ~297) and the evidence doc to list it as
   seen.

### WARNING

2. **`src/vcfcf_core/dashboards/loader.py:900`**: the rejection error says
   "no vendor export carries sortCriteria on one" (an instanced_group
   column). False: the vmbro vCommunity pak, the same reference this
   renderer's instanced-group path was modeled on, carries
   `sortCriteria="true"` on the driver in `View - Collection01.xml` (ESXi
   Network Interfaces), `View - Set 4.xml` (ESXi Security Policy List) and
   `VM SCSI Types.zip`, positioned `rollUpCount` -> `sortCriteria` ->
   `isInstancedGroup`. Keeping the rejection is fine (`_xml_instanced_group_item`
   would otherwise drop the sort silently), but the message must not misstate
   the evidence. Fix: reword to "vendor exports carry it on the driver only
   (rollUpCount -> sortCriteria -> isInstancedGroup); not yet modeled", or
   support it on the driver at that position.

3. **`src/vcfcf_core/dashboards/loader.py:906`**: "the vendor evidence is
   list views only". False: 17 distribution views (bar, pie, donut) in the
   corpus carry sortCriteria, e.g. vmbro vCommunity `ESXi Distribution by
   CPU GHz`, AriaOperationsContent `Cost | VM Potential Savings`. The
   restriction itself is a reasonable scope choice (the list-view meaning is
   what was live-confirmed); the message is wrong. Fix: say "only verified
   on list views; distribution views carry it too but its effect there is
   unverified".

4. **`knowledge/context/wire-formats/dashboard_sort_color_default_summary_rows.md:368-371, 403`**
   and **`knowledge/context/authoring/view_dashboard_design_guide.md:34`**.
   The corpus inventory ("14 views carry summaryInfos ... No export in the
   corpus or on devel shows a list view with two summary rows"; "values seen
   are SUM, AVG, MIN, MAX") missed every view inside the `tvs/` paks: 78
   views, 14 of them list views with several rows, plus DEVIATION. The
   correction strengthens #168 (multi-row on list views is observed, not
   inferred), but the doc is the authority the loader cites, so it must be
   right. The design guide's worked example teaches `aggregation: COUNT`,
   the one value with no evidence. Fix: correct the inventory, move list
   multi-row from "inferred" to "seen in export" citing the Citrix XenDesktop
   pak view, and change the guide example to a seen value (DEVIATION or AVG).

### NIT

5. Content comments now contradict the framework: several views say a view
   default sort is "not a loader-supported field" and point authors at
   widget `sort_by_column`/`sort_by_dir`, which this branch now rejects
   (`content/views/oversized_vms_reclaimable.yaml:11-12`,
   `undersized_vms_add_resources.yaml:11`, `datastore_reclaimable_space.yaml:36`,
   `vm_contention_v2.yaml:91`, `host_contention_outliers.yaml:90`,
   `cluster_demand_capacity_v2.yaml:107`, `host_vsan_contribution.yaml:23`,
   `vsan_cluster_performance.yaml:23`, `vsan_cluster_health_resync.yaml:23`,
   `vm_snapshot_inventory.yaml:14`, and three compliance pak dashboards).
   Outside `tooling`'s write scope and not in this diff, so per delegation
   rule 9 this is a follow-up issue (a view-author pass to adopt `sort:`),
   not a branch fix. Note it in the PR body.

## Hunt items from the brief, resolved

- **Silent-ignore paths that became errors**: no factory, third-party,
  fixture or pak-clone YAML fails to load (render pass loads all 289
  objects with 0 errors). The only widget sort key in any content is
  `sort_by_dir: desc` on a vcommunity / vcommunity-vsphere HealthChart, which
  stays allowed and renders identically. No column carries `sort:`; every
  `summary:` in content is `true`, `false`, or a mapping with SUM.
- **sortCriteria element order vs a real export**: matches (see scans).
- **COUNT claim**: COUNT is not in any export; DEVIATION is (finding 1).
- **Tie rule**: monotone non-strict only; mixed rejected; NaN would also be
  rejected. Non-numeric bounds raise ValueError exactly as before (the
  pre-existing `float()` in MetricSpec construction), not widened.
- **Extractor / reverse path**: `vcfcf_core/extractor/extractor.py`
  `_parse_view_def_element` and `reverse_local.py` parse neither
  `summaryInfos` nor column `sortCriteria`; neither file is in the diff.
  Pre-existing drop, not widened. The extractor emits `sort_by_dir` only
  inside the HealthChart branch (extractor.py:955), which the loader still
  accepts.
- **Global vs pak path (00d3382 anchor)**: no path-specific default added;
  the loader/renderer change is shared and output-inert for existing content.
- **Key collision (6c59f6b anchor)**: no key or label derivation touched.
- **Stale zips (dimension 9)**: `render.py` is on the CLAUDE.md list, but
  rebuilt bundles are content-identical to origin/main, so no
  `CURRENT_TEMPLATE_VERSION` bump is needed (templates untouched). The
  mandated `content-packager` rebuild is a no-op for content; still run it
  per CLAUDE.md.
- **Tests**: new behavior is covered (summary forms and rejections, sort
  position and rejections, HealthChart carve-out, bounds order on all three
  widget types). Missing: a DEVIATION accept case (finding 1).

## If shipped as-is

An author porting the Oracle EM style "Standard Deviation" footer row gets a
load error claiming the value is invalid, while one using `COUNT` ships an
aggregation no product export has ever shown; the docs would tell the next
agent multi-row list summaries are unobserved when 14 vendor views show them.
