# view-time-segment

Verbatim `<ViewDef>` (whole element, including the `Controls` body) of the
`[VCF Consumption Overview v2] VCF Licensing Overtime` list view, id
`6b512229-ff2c-490b-8cfb-ae70f3008de0`. Column 0 of its
`attributes-selector` is a time-segment pseudo-column
(`attributeKey="Interval Breakdown"`, `isTimeSegment="true"`,
`breakdownBy="MONTHS"`, `startingOnUnit="WEEKS"`, `startingOnCount="1"`)
and its `metadata` control carries `hideObjectNameColumn="true"`.

- **Source:** https://github.com/sentania/AriaOperationsContent (Scott
  Bowe's public community content, licensed for reuse), folder
  `VCF License Consumption Overview`, file `Views.zip` -> `content.xml`,
  repository commit `287ef44aeab046602d7a901f09f8db43c6aae074`. The same
  zip is fetched into `reference/references/AriaOperationsContent/` by
  `scripts/bootstrap_references.sh`.
- **Extracted:** 2026-08-26, unmodified apart from trimming to the one
  `<ViewDef>` element (RULE-016; immutable once added).
- **Digest:** `knowledge/context/wire-formats/view_column_wire_format.md`,
  section "Time-segment columns (`time_segment:`)".

What it shows: a segment column carries exactly nine Properties
(`objectType`, `attributeKey`, `rollUpCount`, `sortCriteria`,
`isTimeSegment`, `breakdownBy`, `startingOnUnit`, `startingOnCount`,
`displayName`) and none of the metric-column properties
(`adapterKind`/`resourceKind`/`rollUpType`/`transformations`/`isProperty`).
The view's time window is `YEARS x 1`, so the list shows one row per
month. Two sibling list views in the same export (`e378c921-...` NSX
Licensing Overtime, `156aaea0-...` Automation Licensing Overtime) carry
the identical column 0.
