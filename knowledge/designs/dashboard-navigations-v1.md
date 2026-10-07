# Dashboard Navigation (dashboard-to-dashboard drill-down), v1

Status: approved for build, 2026-10-07.

## Initial prompt

> are dashboards capable of linking to other dashbaords?
> https://github.com/sentania-labs/vcf-cf-migrator/issues/3

> so to support this - we need to update the factory?

> yes let's get these all taken care of

## Vision

Factory dashboards can declare the product's Dashboard Navigation
drill-down: selecting an object in a source widget offers a jump to
another dashboard, optionally pre-selecting that object in named widgets
on the target. Today the renderer hardcodes `"dashboardNavigations": {}`
and the YAML schema cannot express it.

## Wire format (verified)

Source: Oracle Database 9.1 vendor pak (`reference/references/tvs/`, a
local-only Broadcom download, not registry-fetchable, RULE-015), and 33 vendor dashboards on devel read through the UI dashboard config
call on 2026-10-07 (ops-recon; the UI exposes the same map as
`tabNavigations`, cross-checked against the content-export form with
zero mismatches on 13 dashboards).

```json
"dashboardNavigations": {
  "<source widget uuid>": [
    { "id": "<target dashboard uuid>",
      "widgets": [ { "interactionType": "resourceId", "id": "<widget uuid on target>" } ] },
    { "id": "<target dashboard uuid>", "widgets": [] }
  ]
}
```

Facts the design relies on:

- Outer keys are source widget ids on this dashboard. Inner `id` values
  are dashboard ids. Nested `widgets[].id` are widget ids on that target.
- `interactionType` is `resourceId` in every observed instance. Treat it
  as the only value; no enum needed in v1.
- A target with `widgets: []` is a normal form (SD-WAN, Replications,
  RPO vendor dashboards): the jump exists, nothing is passed.
- Dangling targets install without error (vendor blocks on devel point at
  dashboards not present there). The product tolerates them silently,
  which is exactly why the factory must not.
- Vendor paks target stock dashboards by their fixed ids (Cluster
  Performance is `533e14ed-2796-4ead-a644-468beb6396f8` on devel and in
  the Oracle pak alike).

## YAML surface

Per widget, optional, any non-Section widget:

```yaml
widgets:
- id: cluster_list
  type: ResourceList
  ...
  navigations:
  - dashboard: "[VCF Content Factory] Cluster Detail"     # factory dashboard, by name
    widgets: [cluster_picker, cluster_metrics]            # local ids on the target
  - dashboard: "[VCF Content Factory] Capacity Assessment & Right-Sizing"
  - dashboard_id: 533e14ed-2796-4ead-a644-468beb6396f8    # raw id escape hatch
    label: Cluster Performance                             # documentation only
```

- `dashboard` (name) and `dashboard_id` (raw UUID) are mutually
  exclusive per entry. Name is the convention (cross-references are by
  exact name, never raw UUID); the raw form exists only for targets the
  factory does not own, same precedent as `view_details`.
- `widgets` is optional. Entries are the target dashboard's local widget
  ids and resolve to widget UUIDs through the target's own
  `Widget.widget_id` (stable, derived from dashboard name + local id).
  `widgets` is rejected on a `dashboard_id` entry: the factory cannot
  know a foreign dashboard's widget ids.
- Section widgets reject `navigations` (same as `view_details` and
  interactions).

## Resolution and validation

- Name resolution happens at render time against the set of dashboards
  in the repo (`content/dashboards/` plus `third_party/*/dashboards/`),
  the same way views resolve by name today.
- A `dashboard` name that does not resolve fails validation. A `widgets`
  entry not present on the target fails validation. Self-targeting is
  allowed (the product allows it) but a widget cannot name itself as a
  receiver on its own dashboard.
- Output stays byte-identical for every existing dashboard: the block is
  `{}` unless at least one widget declares `navigations`.

## Packaging

A bundle or release that carries a source dashboard must either carry
every named target or fail the build with the missing name. `dashboard_id`
targets are external by definition and are listed in the build output as
prerequisites, not errors.

## Extract

`/extract` (both the live extractor and `reverse_local`) carries the
block when pulling a dashboard: targets that resolve to a dashboard in
the same extraction become `dashboard:` by name with `widgets` mapped
back to local ids; targets that do not resolve become `dashboard_id:`
with the UUID preserved and a `label` of the target's name when the
extractor can read it, otherwise omitted.

## Out of scope

- Any `interactionType` other than `resourceId`.
- Authoring navigations into vendor dashboards (the factory does not own
  them).
- The static `view_details` route link, which already works.
- Receiving widgets on an external (`dashboard_id`) target. Extract keeps
  the jump but drops the pre-selection, since the factory cannot name a
  foreign dashboard's widgets. The Oracle pak's drill into stock Cluster
  Performance loses its pre-selection on extract.

## Related

- `knowledge/context/api-surface/summary_dashboard_assignment.md`
- `knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md`
- sentania-labs/vcf-cf-migrator issue #3 (the same edge on the migrator
  side).
