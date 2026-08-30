# Importing a dashboard without its views corrupts view references

## The rule

Render and import a dashboard only with its referenced views loaded
into the same `views_by_name` set. A `view:` value may reach the wire
verbatim only when it is a canonical UUID; a bare name that does not
resolve is an error, never a fallback.

Enforced in code since 2026-08-29:

- `Dashboard.validate()` (`src/vcfops_dashboards/loader.py`) rejects a
  non-UUID `view:` that is not in `known_views` (`unknown view`).
- `_build_dashboard_obj` (`src/vcfops_dashboards/render.py`) raises
  `UnresolvedViewReferenceError` for the same condition, so a caller
  that skipped validate cannot ship a name.
- `sdk_builder._load_bundled_content` cross-validates each bundled
  dashboard against `bundled_content.views` at load time.

## The failure mode

Before the render guard, the external-UUID passthrough fired on any
string not found in `views_by_name`. A dashboard rendered without its
views got the view's display NAME written into
`config.viewDefinitionId`, with only a stderr INFO line. The content
import accepted it (state OK, dashboard imported), the dashboard opened,
and the View widgets showed blank with "view does not exist".
`GET /internal/views/{id}/data/export` on the literal name returned 400
`Cannot convert ... to uuid`. Diagnosis chased the association step and
the view definitions first; both were innocent.

Summary-tab binding is copy-not-reference, so re-binding a broken source
dashboard reproduces the corruption in the template copy. Fix the source
(re-sync views and dashboard together), then re-bind.

## Minimum reproducer

```python
render_dashboards_bundle_json([dashboard_with_view_widget], {}, owner_id)
```

with `view: Real-time Metrics Services` on the widget. Old behavior:
JSON with `"viewDefinitionId": "Real-time Metrics Services"`. New
behavior: `UnresolvedViewReferenceError: dashboard '...' widget '...':
view 'Real-time Metrics Services' is not a loaded view and is not a
UUID; load the referenced views alongside the dashboard`.

## Source of truth

- `knowledge/context/investigations/recon_log.md`, entry "2026-08-29:
  multi-subject view column binding and view-reference investigations" (embargoed detail).
- `knowledge/context/wire-formats/wire_formats.md`, Dashboard JSON,
  "External view references".
- Tests: `tests/test_external_view_passthrough.py`.
