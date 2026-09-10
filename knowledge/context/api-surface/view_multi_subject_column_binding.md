# Multi-subject views: per-column kind binding (`subject:`)

**Finding date:** 2026-08-29 (api-explorer, live render on a 9.2.0.0 lab,
verbatim vendor ViewDefs, 26 multi-subject views surveyed). **Implemented:**
2026-08-29 (tooling), reviewed in
`knowledge/context/reviews/framework/2026-08-29-multi-subject-column-binding.md`.
The product-bound evidence (lab name, adapter and view names, raw extracts)
is held out of git under `embargo/`; this file carries the generic contract
that the code implements. Wire-format detail and the vendor sample live in
`knowledge/context/wire-formats/view_column_wire_format.md` §Multi-subject
views.

## What the platform does

On a list ViewDef, a column Item's `adapterKind` / `resourceKind` Properties
are a **kind filter, not metadata**. A column bound to one kind renders
`null` (a dash in the UI) on rows of every other subject kind; a column
carrying neither Property resolves its `attributeKey` against every
`<SubjectType>` the view declares. Broadcom's own multi-subject list views
leave most columns unbound (59 of 68 in the survey) and bind the rest to the
single kind that owns the key, which is not necessarily the first subject.

Until 2026-08-29 the factory bound every column to `subjects[0]`, which is
why factory multi-subject views populated only first-kind rows.

## What `subject:` on a column means

```yaml
subjects:
  - adapter_kind: VMWARE
    resource_kind: Datacenter
  - adapter_kind: VMWARE
    resource_kind: vSphere World
columns:
  - attribute: summary|total_number_hosts   # unbound: resolves on every kind
    display_name: Hosts
  - attribute: summary|parentVcenter        # bound: Datacenter rows only
    display_name: vCenter
    is_property: true
    is_string_attribute: true
    subject:
      adapter_kind: VMWARE
      resource_kind: Datacenter
```

| View shape | Column without `subject:` | Column with `subject:` |
|---|---|---|
| Single subject (scalar `subject:` or one-entry `subjects:`) | Bound to the one kind (unchanged, byte-identical to pre-change output) | Loader error: `declares no subjects: list` |
| Multi-subject (2+ `subjects:`) | Unbound: no `adapterKind`, no `resourceKind`; `isStringAttribute` is followed directly by `rollUpType` | Bound to exactly that kind; must be one of the view's `subjects:` (loader error otherwise) |

Loader: `src/vcfops_dashboards/loader.py` (`ViewColumn.subject`, parsed
as a `{adapter_kind, resource_kind}` mapping, unknown keys rejected;
`ViewDef.validate()` checks membership). Renderer:
`src/vcfops_dashboards/render.py::_column_kind_binding` decides the pair
or `None`, `_xml_kind_binding_props` emits the two Properties in the
historical position (after `isStringAttribute`, before `rollUpType`).

## Which column kinds accept `subject:`

| Column kind | `subject:` | Why |
|---|---|---|
| Generic metric / property column (`attribute:`) | accepted | `_xml_attribute_item` emits `_xml_kind_binding_props` |
| Instanced-group **member** (`instanced_group` with `prefix`/`suffix`) | accepted | `_xml_instanced_group_item` member path emits `_xml_kind_binding_props` |
| Instanced-group **driver** (`instanced_group` with no `prefix`/`suffix`, the "Instance Name" pseudo-column) | **rejected** at validate time | The driver Item is `objectType, attributeKey="Instance Name", rollUpCount, isInstancedGroup, showInstanceName, instanceGroupName, keepInstanceSummary, displayName` and returns before the binding helper; no vendor driver Item carries a kind |
| Time-segment (`time_segment`, the "Interval Breakdown" pseudo-column) | **rejected** at validate time | `_xml_time_segment_item` emits exactly the nine vendor Properties (`reference/docs/extracted/view-time-segment/`), none of them a kind |

The two rejections exist because the loader used to accept `subject:` on
those pseudo-columns and the renderer then dropped it without a word
(external Codex P2 on PR #150, 2026-09). A silent downgrade is the failure
mode this repo hunts (`knowledge/lessons/INDEX.md`), so the loader fails
with an error naming the view, the column, and the kind rather than
guessing a wire shape for which there is no vendor evidence. If a vendor
export ever shows a bound driver or time-segment Item, add the binding to
that renderer path and lift the matching check in `ViewDef.validate()`.
Tests: `tests/test_view_multi_subject_column_binding.py::TestLoaderRejects`.

## How the XML binding is emitted

Bound column on a multi-subject view (member or generic path):

```xml
<Item><Value>
  <Property name="objectType" value="RESOURCE"/>
  <Property name="attributeKey" value="summary|parentVcenter"/>
  <Property name="isStringAttribute" value="true"/>
  <Property name="adapterKind" value="VMWARE"/>
  <Property name="resourceKind" value="Datacenter"/>
  <Property name="rollUpType" value="AVG"/>
  ...
</Value></Item>
```

Unbound column: identical minus the two `adapterKind` / `resourceKind`
lines. The `<SubjectType>` block is unaffected: one `descendant` then
`self` pair per kind, in `subjects:` order, exactly as before.

## Consumers of the binding

- **Reverse path** (`src/vcfops_dashboards/reverse.py`,
  `src/vcfops_extractor/extractor.py`, `src/vcfops_extractor/reverse_local.py`):
  an Item with both Properties on a multi-subject view is written back as
  a per-column `subject:`; an Item without them gets no `subject:`; on a
  single-subject view the binding is implied and never written.
- **Bundle dependency audit** (`src/vcfops_packaging/deps.py::_refs_from_view`,
  `_column_kinds`): an unbound column is audited once per subject kind; a
  bound column is audited against its one kind only, otherwise the audit
  raises a false "metric key not found" for the other kinds
  (`tests/test_deps_multi_subject_column_binding.py`).

## Related defects

- **DEF-019** (`knowledge/context/defects.md`): the reverse path drops the
  `<SubjectType>` `filter=` JSON and the instanced-group member
  `isProperty` flag on round-trip. Pre-existing reverse-path lossiness
  observed while testing this contract, not caused by it; forward render
  and import are unaffected.
- **DEF-020** (`knowledge/context/defects.md`): the `vcommunity-vsphere`
  "VM Details" dashboard references a view shipped only in the sibling
  `vcommunity-os` pak. Exposed by the same PR's `UnresolvedViewReferenceError`
  renderer guard (see `knowledge/context/wire-formats/wire_formats.md`
  §External view references); it is a content defect, not a binding one,
  and keeps the managementpacks validate step red until the content is
  fixed.
