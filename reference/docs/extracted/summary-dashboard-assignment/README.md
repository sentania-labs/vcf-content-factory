# getResourceKindList (UI Struts layer), captured 2026-08-25

`getResourceKindList-9.1.0-redacted.json` is the body of

```
GET /ui/resourceKind.action?mainAction=getResourceKindList
    &appendDetailPageMappings=true&adapterKindId=
    &searchField=name&searchText=&page=1&start=0&limit=2000
```

from a VCF Operations 9.1.0 instance (no adapter kind filter, so every
kind on the instance). Redaction: `resourceKindList[]` is filtered to the
entries whose `adapterKind` is `VMWARE`, `VirtualAndPhysicalSANAdapter`,
or `Container` (66 of 480); the surviving entries and the top-level
`totalCount` (still the original 480) and `defaultTemplateName` are
unmodified. Entry shape (every entry, all three captures compared during
the 2026-08-25 framework review): `resourceKindId`, `name`,
`resourceKind`, `resourceKindTemplate`, `adapterKind`, `showTag`,
`isLockedNode`, `type`, `subType`, `earlyWarningEnabled`, `dtEnabled`,
`iconSrc`, plus `isAdapterPlugin` (9.1+) and a per-entry
`defaultTemplateName` on kinds that have a built-in summary page. There
is no `id`, `key`, or `resourceKindKey`.

Digest: `knowledge/context/api-surface/summary_dashboard_assignment.md`.
