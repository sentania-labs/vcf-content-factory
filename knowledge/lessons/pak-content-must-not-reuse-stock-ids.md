# A pak that ships content under stock ids deletes the stock content when it is uninstalled

**Rule.** Every view, dashboard, report and super metric a pak bundles carries
an id the pak owns: minted by the factory, never copied from VMware stock
content or from an upstream pak that copied it. Before a pak is installed or
uninstalled, check its bundled content ids against the target. An id that
already exists there, and was not installed by an earlier version of the same
pak, stops the operation.

**Why.** VCF Operations tracks pak content by id. Installing a pak whose
content reuses a stock id overwrites the stock definition. Uninstalling the pak
deletes every id the pak shipped, stock or not. The stock dashboards that use
those views stay installed and `importComplete`, and each affected widget
shows "The view does not exist.". Nothing warns at either step.

**Reproducer (devel 9.0.2, 2026).** The factory's vCommunity vSphere port
copied upstream vmbro/VCF-Operations-vCommunity content. That content carries
64 VMware stock view ids.
- Install, 2026-07-16: the audit log shows `VIEW_DEFINITION_CREATE_UPDATE` on
  the stock ids under the pak's names. For example, `2788178d` "Configuration
  | Resource Pool" became "vSphere Resource Pool Configuration".
- 9.0.2.0200 upgrade, 2026-10-14: the stock definitions were put back.
- `SOLUTION_REMOVE`, 2026-10-15 18:33:49Z: two minutes later a single
  maintenanceAdmin `VIEW_DEFINITION_DELETE` of 109 ids removed all 64 stock
  views.

Six stock Configuration, Performance and Capacity dashboards were left with
dangling View widgets. Evidence:
`knowledge/context/investigations/2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`.

**How to check.** Grep the pak's or port's content for ids found in a clean
lab export (`/api/content/operations/export`, scope `ALL`). For an installed
third-party pak, check its content the same way before anyone uninstalls it:
prod's upstream vCommunity carries the same 64 ids.

**Not enough on its own.** `content_naming: factory_prefixed` checks names,
not ids. Ports run `unprefixed` by design (#229). The `isUnremovable` guard in
`uninstall_pak` protects built-in paks, not built-in content shipped inside a
custom pak.
