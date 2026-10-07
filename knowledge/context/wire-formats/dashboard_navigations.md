# Dashboard Navigation (dashboard-to-dashboard drill-down)

Selecting an object in a source widget offers a jump to another dashboard,
optionally pre-selecting that object in named widgets on the target. The
content-import zip carries it as the per-dashboard `dashboardNavigations`
block; the UI config call exposes the same map as `tabNavigations`.

Design of record: `knowledge/designs/dashboard-navigations-v1.md`.
Implemented 2026-10-07 in `src/vcfcf_core/dashboards/loader.py`
(`Navigation`, `check_dashboard_navigations`), `render.py`
(`_render_dashboard_navigations`), `reverse.py` (raw parse),
`src/vcfcf_core/extractor/extractor.py` (`_navigations_to_yaml`) and
`src/vcfcf_core/packaging/loader.py`
(`check_bundle_dashboard_navigations`). Tests:
`tests/test_dashboard_navigations.py`.

## Wire format (verified)

Sources: the Oracle Database 9.1 vendor pak
(`reference/references/tvs/OracleDatabase-9.1.0_b20240520.165914.pak`,
`content/dashboards/Oracle * Drill Down/*.json`), and 33 vendor
dashboards on devel read through the UI dashboard config call on
2026-10-07 (ops-recon; `tabNavigations` cross-checked against the
content-export form with zero mismatches on 13 dashboards).

The TVS pak is a local-only artifact (a manual Broadcom download, not in
any fetch registry); not reproducible from a fresh clone. Findings are
summarized here in full (RULE-015), so nothing below depends on having
it.

```json
"dashboardNavigations": {
  "<source widget uuid>": [
    { "id": "<target dashboard uuid>",
      "widgets": [ { "interactionType": "resourceId", "id": "<widget uuid on target>" } ] },
    { "id": "<target dashboard uuid>", "widgets": [] }
  ]
}
```

- Outer keys are source widget ids on this dashboard. Inner `id` values
  are dashboard ids. Nested `widgets[].id` are widget ids on that target.
- `interactionType` is `resourceId` in every observed instance; the
  factory treats it as the only value.
- A target with `widgets: []` is a normal form (SD-WAN, Replications,
  RPO vendor dashboards): the jump exists, nothing is passed.
- Dangling targets install without error (vendor blocks on devel point at
  dashboards not present there). The product tolerates them silently,
  which is why the factory refuses them.
- Vendor paks target stock dashboards by their fixed ids (Cluster
  Performance is `533e14ed-2796-4ead-a644-468beb6396f8` on devel and in
  the Oracle pak alike).
- Stale keys exist in shipped content: both Oracle 9.1 Drill Down
  dashboards carry outer keys for four source widget ids that are not
  widgets on the dashboard (checked offline 2026-10-07). The importer
  accepts them; the factory's reverse parser drops them with a WARN.
- An empty block is `{}`. Contract: a dashboard whose widgets declare no
  `navigations:` renders exactly that, byte-identical to the output before
  the feature existed, on every render path (standalone zip, bundle, SDK
  pak). `tests/test_dashboard_navigations.py` guards it over the repo's
  dashboards.

## Factory YAML

Per widget, optional, any non-Section widget:

```yaml
widgets:
- id: cluster_list
  type: ResourceList
  ...
  navigations:
  - dashboard: "[VCF Content Factory] Cluster Detail"     # factory dashboard, by exact name
    widgets: [cluster_picker, cluster_metrics]            # local ids on the target
  - dashboard: "[VCF Content Factory] Capacity Assessment & Right-Sizing"
  - dashboard_id: 533e14ed-2796-4ead-a644-468beb6396f8    # raw id escape hatch
    label: Cluster Performance                             # documentation only
```

| Key | Rule |
|---|---|
| `dashboard` | Target's exact name (case- and prefix-sensitive). The convention. |
| `dashboard_id` | Raw dashboard UUID, for targets the factory does not own (stock or vendor dashboards). Lower-cased on load. |
| `widgets` | Optional list of the TARGET's local widget ids; omitted and `[]` are the same jump-only form. Rejected on a `dashboard_id` entry: the factory cannot know a foreign dashboard's widget ids. No duplicates. |
| `label` | Optional string, documentation only, never rendered. Printed in packaging prerequisites. |

Exactly one of `dashboard` / `dashboard_id` per entry. Unknown keys are
rejected. A Section rejects `navigations` (same as `view_details` and
interactions). An empty `navigations: []` is the same as omitting it.

Render: `dashboard` resolves to the target's YAML `id`; each `widgets`
entry resolves to the target's `Widget.widget_id` (stable uuid5 of the
target dashboard's name and the local id, so it matches the id the target
renders with). `dashboard_id` passes through with `widgets: []`.

## Resolution and validation

- Names resolve against every dashboard in the repo:
  `content/dashboards/` plus `third_party/*/dashboards/`, plus the
  `--dashboards-dir` set when the CLI is pointed elsewhere.
  `python3 -m vcfcf_dashboards validate` (full corpus) checks factory and
  third-party dashboards alike as sources; an explicit `--dashboards-dir`
  validate checks the loaded dashboards as sources against the same
  lookup set.
- Failures, each naming the source dashboard, the widget and the bad
  reference: a name that matches no dashboard (the error also lists any
  dashboard YAML that failed to load, since the target may be one of
  them); a name that matches two dashboards with different ids
  (ambiguous); a `widgets` entry that is not a non-Section widget on the
  target; a `dashboard_id` that is the id of a dashboard the repo owns
  (use `dashboard: "<name>"`, which keeps it under carry-or-fail).
- Self-targeting is allowed (the product allows it), but a widget cannot
  name itself as a receiver on its own dashboard.
- The renderer refuses an unknown name, an ambiguous name (two ids) and
  an unknown receiver (`UnresolvedDashboardNavigationError`), as the
  backstop for callers that skipped validate.
  `render_dashboards_bundle_json(..., known_dashboards=...)` supplies
  targets that are not being rendered. Resolving is not the same as
  shipping: a target supplied that way is not in the zip, so each
  import path decides what to do about it (next section).

## Packaging

Every import path either ships each named target or says so out loud.
`dashboard_id` targets are external by definition and are always printed
as `PREREQUISITE:` lines (the target must already exist on the instance).

| Path | Named target not in the import |
|---|---|
| Bundle / release build, discrete build | fails, naming each missing dashboard (`load_bundle`; `render_bundle_payloads` for discrete builds, which never pass through `load_bundle`) |
| `vcfcf_packaging sync` (bundle install) | fails in `load_bundle`; external targets printed as prerequisites |
| `vcfcf_dashboards package` / `sync` (standalone zip of `--dashboards-dir`) | printed as `PREREQUISITE:`, and fails unless `--allow-external-navigation-targets` is passed (for a target already installed) |
| SDK pak build | fails: targets must be dashboards bundled in the pak |

A discrete dashboard release with a named target therefore cannot build
on its own; ship the pair as a bundle. The `/bundle` composer reports a
missing navigation target as a dependency and auto-adds it, iterating
to convergence at any chain length (each pass must add a component not
seen before, so a cycle ends the loop) so the added dashboard's own
views and targets come too. Anything still unresolved after convergence
fails composition with the names, and no manifest is written.

## Extract

Both `/extract` paths carry the block:

- `reverse_local` (multi-dashboard source file): a target that is another
  dashboard in the same source file becomes `dashboard:` by name, with
  `widgets` mapped back to that dashboard's reversed local ids.
- Live extractor (one dashboard per run): only a self-target is in the
  extraction. A target whose id is a dashboard the repo already owns
  (`content/dashboards/` or `third_party/*/dashboards/`) becomes
  `dashboard:` by that dashboard's name, with receivers mapped back
  through its widget ids (validate rejects a `dashboard_id` naming an
  owned dashboard). Every other target becomes `dashboard_id:` with the
  UUID preserved and `label:` set to the target's name from the same
  content export, when the export carries it.
- When the live extractor names an owned target, the generated
  `PROJECT.yaml` carries it so the advertised `build` passes
  carry-or-fail: explicit content lists with the project's own files plus
  the owned dashboard and its closure (its views, super metrics, custom
  groups and its own named targets, transitively; `navigation_closure` in
  `src/vcfcf_packaging/navigation.py`). References are repo-relative when
  the project sits inside the repo, absolute otherwise. Without an owned
  target the manifest keeps auto-discovery (no lists).
- Receivers on a target that is neither in the extraction nor owned by
  the repo are dropped with a WARN
  (a `dashboard_id` entry cannot name widgets); the jump itself is kept.
  A receiver the reverse parser skipped (unsupported widget type) is also
  dropped with a WARN.

## Out of scope (v1)

- Any `interactionType` other than `resourceId`.
- Authoring navigations into vendor dashboards.
- The static `view_details` route link
  (`dashboard_section_gauge_viewdetails.md`), which already works.
