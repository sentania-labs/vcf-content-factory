# Framework review: `section_fallback: omit` (feat/section-fallback, 2026-11-13)

- Branch / commit: `feat/section-fallback` at `1f3d420a`, one commit on `main` `3abf04e3`
- Area: `src/vcfcf_core/dashboards/{loader,widget_versions}.py`, `src/vcfcf_dashboards/{cli,client,handler}.py`, `src/vcfcf_managementpacks/{sdk_builder,cli,buildkit}.py`, `src/vcfcf_packaging/syncer.py`, `src/vcfcf_core/importer/convert.py`, docs, tests
- Verdict: **APPROVE** (0 BLOCKING / 0 WARNING / 4 NIT). Under delegation rule 9 every NIT is still fixed before the PR opens.

## Checks re-run (independently)

| Check | Result |
|---|---|
| Validate chain (7 packages, dashboards with `--id-guard-baseline 3abf04e3`) | all rc=0 |
| `bash scripts/path_reference_audit.sh` | rc=0 |
| pytest `tests/`, serial (no `pytest-xdist` on this host, so `-n auto --dist=loadgroup` was dropped), `--override-ini=addopts= -m ""` | head: 20 failed / 4756 passed / 15 skipped. Base (`git archive 3abf04e3`, same host, same command): 20 failed / 4706 passed / 12 skipped. **Same 20 test names fail on both, so the delta is zero.** The count is 20 here, not the 17 in the brief: environment, not this change (doctor, publish and real-repo release tests). |
| Touched test files (`test_section_fallback.py`, `test_import_shortfall_and_widget_floor.py`, `test_import_local.py`) | 183 passed |
| Render regression, no key | Every dashboard YAML in the worktree's `content/`, `third_party/`, `tests/fixtures/` and `bundles/`, plus the main checkout's `content/sdk-adapters/*` clones (compliance: 6). 21 dashboards, each rendered with `render_dashboards_bundle_json` on the content-import path (no adapter kind) and the pak path (adapter kind set), base src against head src: **42/42 sha256-identical**, 0 load or render errors. |
| Shipped vs omitted, real dashboard | `summary_widget_smoke.yaml` with the key added in scratch: every remaining widget's JSON is identical except `gridsterCoords.y`; widget ids, the dashboard-level object and `entries` are identical on both paths. |
| Buildkit | Assembled a kit to scratch (`assemble_buildkit`). Its `sdk_builder.apply_bundled_section_fallback` and `check_bundled_version_floors` import only kit-local modules and give the same output as the factory: auto at 8.18.7 omits with the note and the gate passes; `ship` prints KEPT BELOW FLOOR and the gate passes. The new rewrite rule matches (a rule that matched zero times would fail assembly with an AssertionError). |
| Stale-zip / template version (dimension 9) | Not triggered. No file under `templates/`, `builder.py`, `discrete_builder.py`, `release_builder.py`, `assembly.py`, dashboards `render.py` or alerts `render.py` changed. No `CURRENT_TEMPLATE_VERSION` bump is needed. |

## Dimension walk

1. **Global-default / pak-specific leak (00d3382).** Without the key, `apply_section_fallback` returns the same objects (it never calls `dataclasses.replace`), and every new branch depends on `section_fallback is not None` or `sections != "auto"`. The renderer is unchanged. The content-import and pak paths are proven byte-identical (above). The bundle builder and assembly never call the fallback, so content bundles are unchanged, as the brief intended. Clear.
2. **Key collisions (6c59f6b).** The widget uuid is `stable_id("widget", name::local_id)`. `dataclasses.replace` keeps `dashboard_name` and `local_id`, and no Widget or Dashboard field is `init=False`, so ids are the same in both variants (tested, and checked again here). So an upgrade from the omitted variant to the shipped one adds only the Section ids and orphans nothing. Sections add no `entries.resourceKind` / `entries.resource` slots, so the indices of the other widgets do not move. Clear.
3. **Wire format.** The omitted variant is a subset of the shipped widget list, with only `y` changed. The pak's per-dashboard `resources.properties` is generated from the transformed object, which matches what the doc says. Clear.
4. **Loader / validator.** Load errors confirmed for `ship`, `Omit`, `true` and `[omit]`, and for the key on a dashboard with no Section. Explicit `null` is treated as unset, the same `data.get` convention other keys use. The collapsed-member overlap is rejected: a member overlapping a widget directly below, and a member reaching past the next Section to overlap a widget there. A collapsed Section whose members overlap nothing is accepted, and its members are shown. Interactions are kept; any naming a removed id are dropped.
5. **Render regression.** Clean (above).
6. **Builder / pak.** `build-sdk` applies the fallback right after `_load_bundled_content`, before the floor gate, naming, stock-id, reference and render steps, so every later step sees the variant that ships. `validate-sdk` applies the same auto decision. `--release` combined with `ship` or `omit` is refused by `build_sdk_pak` itself, which is the one function both the factory CLI and the kit call, so neither entry point can bypass it.
7. **Corpus regression.** Clean (above).
8. **Silent change.** Every omission path prints its notes: `package`, `sync`, the dashboards handler, the bundle preflight, `build-sdk` and `validate-sdk`. No path that refused a Section dashboard before now imports one. Live sync has no `--sections`, unkeyed dashboards go through the old `import_check` unchanged, and `package --sections ship` is the old output. One path changes on purpose, and the docs say so: on live sync, a keyed dashboard on an instance whose version cannot be read is omitted, where before it would have been warned about and imported. PR 362 behaviour without the key: `plan_dashboard_import` gives the same result as `widget_import_refusal` (early return with no request, the unreadable note, `import_check`). The shortfall checks run on the planned list, which has the same names and ids.
9. **Stale zip.** N/A (above).
10. **Tests.** Good coverage of the decision table, overrides, release refusal on both CLIs, sync, handler, preflight, package, importer and kit rewrite. The edge-case gaps are NIT 4.

**Callers of `widget_import_refusal`:** none remain anywhere in the worktree (`src/`, `scripts/`, `tests/`, `knowledge/`, `.claude/`, `.github/`, installer templates). The pinned installers never imported it. They have their own Section refusal, which this change leaves alone.

**Row-closing transform, proven safe.** A closed row is one that no remaining widget covers. So no widget spans a closed row, and the shift (the number of closed rows above a widget's top) is a strictly increasing map over the rows that remain, which keeps each widget contiguous. It cannot create an overlap and cannot change a height. With y >= 1 the output stays >= 1. Probed: two adjacent Sections, a Section on the last row, and a widget spanning a Section row (that row stays open) all give correct layouts with no overlaps on the wire.

## Findings

### NIT 1: the transform computes on authored `y`, the renderer clamps to `max(1, y)`
`src/vcfcf_core/dashboards/loader.py:3161` (`_grid_rows`), used by `without_sections` at `:2769`. Authority: `render._clamp_gridster_floor` (DEF-013).

Failing input: `section_fallback: omit`, Section `s1` at `y: 0`, TextDisplay `a` `{x:1, y:1, w:12, h:2}`, TextDisplay `b` `{x:1, y:3, w:12, h:2}`. In the shipped wire, `a` covers rows 1-2 and `b` rows 3-4. In the omitted variant, `a` moves to y 0, which is clamped to 1 (rows 1-2), and `b` moves to y 2 (rows 2-3). That is a new overlap between `a` and `b`.

The source is already malformed: once clamped, the Section shares row 1 with `a`. So this only happens in a broken layout. Fix: compute rows from `max(1, y)` in `_grid_rows`, or reject `section_fallback` when any widget has `y < 1`.

### NIT 2: the "78 renders" claim in the wire doc cannot be reproduced
`knowledge/context/wire-formats/dashboard_fidelity_wire_format.md:352`. The roots it names hold 21 dashboards on this checkout (15 in the repo, 6 in compliance; no other registered pak bundles one), which is 42 renders over the two paths. Fix: state the set and how it was counted, or drop the number.

### NIT 3: bundle sync plans twice, prints SECTIONS OMITTED twice and reads the version twice
`src/vcfcf_packaging/syncer.py:233` discards `_planned`, then `DashboardsHandler.sync` (`handler.py:361`) plans again. Input: any bundle with a keyed Section dashboard synced to 9.0.2. The same `SECTIONS OMITTED` line prints once as `WARN` from the preflight and once as `  WARN  ` from the handler, and `GET /api/versions/current` is called twice. The double version read and the double warning predate this change; the new line inherits them. Fix: either pass the plan through, or have one of the two print the omission line.

### NIT 4: missing edge-case tests and a misleading importer message
- `tests/test_section_fallback.py` has no case for two adjacent Sections, a Section on the last row, or `y < 1` (NIT 1). All three behave correctly in probes except `y < 1`. Pin them.
- `src/vcfcf_core/importer/convert.py:896`: the `NOT DELIVERABLE` text says "section_fallback: omit on the written YAML would deliver it", but under that deviation the dashboard is not written. `importer_offline_conversion.md` gives the right recipe (convert at an accepting target or without `--target-min`, then add the key). Fix: put that recipe in the message.

## If shipped as-is
Nothing changes for any dashboard without the key, on any path. An author who adds the key gets a Section-less dashboard on 8.18.7/9.0.x/9.1.0, with a printed line for each omission, and the same dashboard with its Sections from 9.1.1. Rough edges: a duplicated line on bundle sync, and a theoretical overlap only in layouts whose source is already malformed (0-based Section).
