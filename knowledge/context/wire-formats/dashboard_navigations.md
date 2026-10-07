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
- An empty block is `{}`. Every factory dashboard without navigations
  still renders exactly that, byte-identical to the pre-feature output
  (before/after render diff over all 45 dashboard YAMLs in the repo and
  the managed SDK paks, plus every bundle's dashboard payload,
  2026-10-07: identical).

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
  `content/dashboards/` plus `third_party/*/dashboards/`.
  `python3 -m vcfcf_dashboards validate` (full corpus) checks factory and
  third-party dashboards alike; an explicit `--dashboards-dir` validate
  checks against the loaded set only.
- Failures, each naming the source dashboard, the widget and the bad
  reference: a name that matches no dashboard; a name that matches two
  dashboards with different ids (ambiguous); a `widgets` entry that is not
  a non-Section widget on the target.
- Self-targeting is allowed (the product allows it), but a widget cannot
  name itself as a receiver on its own dashboard.
- The renderer refuses the same cases
  (`UnresolvedDashboardNavigationError`) so no render path can emit a
  dangling target. `render_dashboards_bundle_json(...,
  known_dashboards=...)` supplies targets that are not being rendered;
  the dashboards CLI `package` / `sync` pass the repo corpus, the SDK pak
  builder passes the pak's own dashboards.

## Packaging

A bundle or release that carries a source dashboard must carry every
`dashboard:` target, or the build fails naming each missing one
(`load_bundle`, and `render_bundle_payloads` for discrete builds, which
never pass through `load_bundle`). `dashboard_id` targets are external by
definition and are printed as `PREREQUISITE:` lines in the build output
(the target must already exist on the instance). A discrete dashboard
release with a named target therefore cannot build on its own; ship the
pair as a bundle.

## Extract

Both `/extract` paths carry the block:

- `reverse_local` (multi-dashboard source file): a target that is another
  dashboard in the same source file becomes `dashboard:` by name, with
  `widgets` mapped back to that dashboard's reversed local ids.
- Live extractor (one dashboard per run): only a self-target is in the
  extraction; every other target becomes `dashboard_id:` with the UUID
  preserved and `label:` set to the target's name from the same content
  export, when the export carries it.
- Receivers on a target outside the extraction are dropped with a WARN
  (a `dashboard_id` entry cannot name widgets); the jump itself is kept.
  A receiver the reverse parser skipped (unsupported widget type) is also
  dropped with a WARN.

## Out of scope (v1)

- Any `interactionType` other than `resourceId`.
- Authoring navigations into vendor dashboards.
- The static `view_details` route link
  (`dashboard_section_gauge_viewdetails.md`), which already works.
