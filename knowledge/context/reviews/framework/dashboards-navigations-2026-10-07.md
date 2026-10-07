# Framework review: Dashboard Navigation drill-down (feat/dashboard-navigations, 24cbbea)

Reviewer: framework-reviewer. Date: 2026-10-07. Base: origin/main (e2720b7).

**Verdict: CHANGES REQUESTED.** 1 BLOCKING, 7 WARNING, 6 NIT.

The byte-identical claim holds: every dashboard in the repo and in the five
managed SDK paks renders the same bytes before and after the change. The
blocking finding is a new one, on the standalone content-import path:
`vcfcf_dashboards package` / `sync` can ship a navigation to a dashboard that
the zip does not contain. It exits 0 and prints nothing. That is the
silent-dangling case this feature says it refuses.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (worktree) | all rc=0, tree clean afterwards |
| Full pytest | 2022 passed, 6 failed, 15 skipped. All 6 failures are `artifact source not found: content/sdk-adapters/synology/adapter.yaml` (SDK repos not cloned in the worktree). None relate to this change. |
| `tests/test_dashboard_navigations.py` | 41 passed |
| Render regression, origin/main vs HEAD | **identical**. 77 outputs: 10 factory and 1 third-party dashboard rendered alone and as a set; 55 SDK-pak dashboards (compliance, synology, unifi, vcommunity, vcommunity-vsphere, read-only from the main checkout) rendered the way `sdk_builder` does it, one per call with `owning_adapter_kind`, plus `known_dashboards` at HEAD; bundle dashboard payloads via `load_bundle` + `render_bundle_payloads` for 3 of 4 bundles and the idps-planner PROJECT.yaml. `vks-core-consumption-bundle` fails to load in the harness on both sides (report view-dir resolution), so its dashboard is covered only by the per-file render. |
| Wire shape vs reference | Oracle Database 9.1 pak, both Drill Down dashboards: entry keys `{id, widgets}`, `interactionType` only `resourceId`, `widgets: []` present, 4 stale outer keys each. Matches `dashboard_navigations.md` and the renderer's emitted key order. |
| SDK buildkit vendoring | Applied `buildkit._IMPORT_REWRITES` to loader/render in scratch. `dashboard_render` imports `UnresolvedDashboardNavigationError`, `dashboard_loader` imports `Navigation` / `check_dashboard_navigations`: self-contained. |
| pak-compare | n/a (no pak structure change) |

## Adversarial probes (scratch fixtures, results observed)

1. **Same-name targets.** `check_dashboard_navigations` reports "ambiguous".
   `render_dashboards_bundle_json` called directly silently picks the last
   (`known`) or the rendered one. See W1.
2. **Factory source to a third_party target, `vcfcf_dashboards package`.**
   rc=0, empty stderr. The zip carries only the source dashboard, its
   navigation points at the third-party dashboard's UUID, and no notice is
   printed for that target or for the `dashboard_id` entry. See B1.
3. **Package of an explicit subdirectory** targeting a factory dashboard
   outside it: full validate rc=0, package rc=1 with "does not exist (no
   dashboard has that exact name)". See W2.
4. **SDK path, target outside the pak:** raises
   `UnresolvedDashboardNavigationError` (loud, correct).
5. **`dashboard_id` equal to a repo dashboard's id:** no error. Bypasses
   carry-or-fail. See W3.
6. **Extractor, duplicate receivers in a source export:** the written YAML
   fails to load ("lists ... more than once"). Duplicate target entries load
   fine. See N1.
7. **Self-target:** allowed. Self-receiver is rejected in `Dashboard.validate`,
   in the renderer and in both extractor writers (WARN plus drop).
8. **Extract, target outside the extraction:** becomes `dashboard_id` plus
   `label`. Receivers are dropped with a WARN, and that drop is documented.

## Dimension walk

- **Global-default leak (00d3382):** clean. The block stays `{}` unless a
  widget declares navigations. Proven by the byte-identical diff on the
  standalone, bundle and SDK-style render paths.
- **Key collision (6c59f6b):** target widget ids come from the target's own
  `Widget.widget_id` (name::local_id), so they agree with what the target
  renders. Name collisions are caught in the check function but not in the
  renderer backstop (W1).
- **Wire conformance:** matches the Oracle reference and the wire doc.
- **Loader/validator:** shape validation is strict (XOR, unknown keys,
  UUID, Section rejection, duplicates). Corpus resolution is correct for
  full validate. The explicit-path scope is inconsistent (W2), and
  `dashboard_id` is not cross-checked (W3).
- **Corpus regression:** none.
- **Silent downgrade:** B1.
- **Stale zips:** N3.
- **Tests:** W7.

## BLOCKING

**B1.** `src/vcfcf_dashboards/cli.py:375` (package) and `:396` (sync).
Authority: `knowledge/context/wire-formats/dashboard_navigations.md`
("Dangling targets install without error... which is why the factory refuses
them"; "so no render path can emit a dangling target"), and design
§Packaging.

- **What happens:** `_navigation_corpus` resolves names against the loaded
  set plus every `third_party/*/dashboards/` YAML, but the zip contains only
  the loaded set.
- **Effect:** a factory dashboard that targets a third-party dashboard is
  packaged or synced pointing at a UUID that this import never creates.
  Exit code 0, nothing printed (probe 2).
- **`dashboard_id` targets:** the build path prints these as `PREREQUISITE:`,
  but this path never does.
- **Why this is the path that matters:** it is the standalone
  content-import zip, the same path both named escapes hid in.

**Fix:** in `cmd_package` and `cmd_sync`, list every resolved `dashboard:`
target that is not in `dashboards`, and every `dashboard_id`, as a loud
`PREREQUISITE:` line (or fail, matching the bundle rule). Correct the wire
doc's "no render path" sentence to match. Add a CLI test for both cases.

## WARNING

**W1.** `src/vcfcf_core/dashboards/render.py:2518-2519`. Authority: anchor
6c59f6b (context-blind key collapse); lesson
`dashboard-import-without-views-corrupts-refs.md` (the renderer is the
backstop for callers that skipped validate).

- `targets_by_name` is a last-wins dict. "Rendered wins on a clash" is a
  silent choice between two different dashboard UUIDs.
- `sdk_builder` runs no `check_dashboard_navigations` first, so a pak with
  two same-name dashboards would emit an arbitrary target.

**Fix:** keep name to list of distinct ids, and raise
`UnresolvedDashboardNavigationError` when a referenced name maps to more
than one id. Add a test.

**W2.** `src/vcfcf_dashboards/cli.py:39-67`. Authority: design §Resolution
("against the set of dashboards in the repo: content/dashboards/ plus
third_party/*/dashboards/").

- With an explicit `--dashboards-dir`, the corpus omits
  `content/dashboards/`.
- So package or sync of a subset fails with a misleading "does not exist",
  even though full validate passes (probe 3).

**Fix:** always fold `DEFAULT_DASHBOARDS` into the corpus (deduped by
name/id). Pair this with B1's prerequisite notice.

**W3.** `src/vcfcf_core/dashboards/loader.py:2076`
(`check_dashboard_navigations` skips `dashboard_id`). Authority:
`knowledge/context/authoring/uuids_and_cross_references.md` (cross-references
by exact name; raw `dashboard_id` only for dashboards the factory does not
own).

- A `dashboard_id` naming a repo dashboard passes (probe 5).
- It skips the bundle carry-or-fail rule and ships as a "prerequisite".

**Fix:** when a `dashboard_id` matches a corpus dashboard's id, report it
as an error that names the dashboard and says to use
`dashboard: "<name>"`.

**W4.** `src/vcfcf_packaging/syncer.py:167` (bundle install path).
Authority: design §Packaging (`dashboard_id` targets are reported as
prerequisites). `sync_bundle` never surfaces them; only the zip builders
do. An operator installing straight from a bundle gets no notice that the
external target must already exist.

**Fix:** after `load_bundle`, print the `check_bundle_dashboard_navigations`
prerequisite lines in `sync_bundle`.

**W5.** `src/vcfcf_packaging/composer.py:275` (`_check_deps` via
`collect_deps`). Authority: design §Packaging (carry-or-fail). The `/bundle`
composer's dependency check and auto-add do not know about navigation
targets. It reports a selection as complete, then `build_bundle` rejects the
manifest.

**Fix:** include unresolved `dashboard:` targets in the composer's
missing-dependency list and in `_auto_add_deps`.

**W6.** `knowledge/context/wire-formats/dashboard_navigations.md:20` and
`knowledge/designs/dashboard-navigations-v1.md` §Wire format. Authority:
RULE-015 (`cited-artifacts-reproducible.md`: "Any new citation of a TVS pak
must carry the local-only disclaimer"). The `reference/references/tvs/`
Oracle pak is cited without one. (It is absent from the worktree; present
in the main checkout.)

**Fix:** add the disclaimer. The doc already summarizes the shape fully.

**W7.** `tests/test_dashboard_navigations.py`. Authority: framework-reviewer
dimension 10. Three paths have no test coverage:

- the `sdk_builder` wiring (`known_dashboards=dashboards`, per-dashboard
  render, out-of-pak target raising);
- the `vcfcf_dashboards package` / `sync` CLI paths;
- renderer ambiguity.

The in-repo byte-identity test only compares HEAD with and without a corpus,
not against pre-change output. It is still a sound forward guard, and this
review's diff covers the backward case.

**Fix:** add tests with B1 and W1, plus one SDK-path render test.

## NIT

**N1.** `src/vcfcf_core/dashboards/reverse.py:1529`. Duplicate receiver ids
in a source export are carried through, and the extracted YAML then fails
to load (probe 6). **Fix:** de-duplicate receivers (order preserved) in the
parser or in `_navigations_to_yaml`.

**N2.** `knowledge/context/wire-formats/dashboard_navigations.md:54`.
Authority: lesson `no-volatile-status-in-reference-docs.md`. "all 45
dashboard YAMLs ... 2026-10-07" is a volatile count. It is already
inconsistent: the commit says 56, and this review rendered 66 dashboards
(10 factory, 1 third-party, 55 SDK). **Fix:** state the contract and drop
the count and date.

**N3.** Stale-zip discipline (CLAUDE.md "After tooling changes").
`render.py`, `assembly.py`, `builder.py` and `discrete_builder.py` are
touched, so the rebuild trigger fires. The commit does not flag it.

- Byte-identical output is proven, so a rebuild is a no-op.
- No `CURRENT_TEMPLATE_VERSION` bump is warranted: no distributed artifact
  differs from what HEAD builds.

**Fix:** say so explicitly in the PR body, so the orchestrator records why
it skips or performs the rebuild.

**N4.** `knowledge/designs/dashboard-navigations-v1.md` §Out of scope.
Receiving widgets on external (`dashboard_id`) targets are a deliberate
loss: extracting a vendor-style drill (the Oracle pak passes selection to
widget `67bac823...` on stock Cluster Performance) keeps the jump but drops
the pre-selection. The wire doc records this; the design's Out of scope
does not. **Fix:** add one line there.

**N5.** `src/vcfcf_dashboards/cli.py:66`. A third-party YAML that fails to
load is silently left out of the corpus. A navigation to it then reports
"does not exist", which misleads. **Fix:** collect the skipped paths and
name them in the unresolved-target error.

**N6.** `src/vcfcf_packaging/discrete_builder.py:739`. It imports the
private `_print_navigation_prerequisites` from `builder`. **Fix:** move the
helper into a shared module, or make it public.

## If shipped as-is

An operator who syncs or packages a factory dashboard that drills into a
third-party (or not-yet-installed) dashboard gets a drill-down link to a
dashboard that does not exist on the instance. The command reports success,
and nothing tells them.
