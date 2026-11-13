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
those views stay installed and report as fully imported, and each affected widget
shows "The view does not exist.". Nothing warns at either step.

**Reproducer (devel 9.0.2, 2026).** The factory's vCommunity vSphere port
copied upstream vmbro/VCF-Operations-vCommunity content. That content carries
64 VMware stock view ids.
- Install, 2026-07-16: the audit log shows the stock ids written under the
  pak's names. For example, `2788178d` "Configuration
  | Resource Pool" became "vSphere Resource Pool Configuration".
- 9.0.2.0200 upgrade, 2026-10-14: the stock definitions were put back.
- `SOLUTION_REMOVE`, 2026-10-15 18:33:49Z: two minutes later a single
  maintenanceAdmin `VIEW_DEFINITION_DELETE` of 109 ids removed all 64 stock
  views.

Stock Configuration, Performance and Capacity dashboards were left with
dangling View widgets (29 dashboards on devel reference the 64 views). Evidence:
`knowledge/context/investigations/2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`.

**How to check.** Grep the pak's or port's content for ids found in a clean
lab export (`/api/content/operations/export`, scope `ALL`). For an installed
third-party pak, check its content the same way before anyone uninstalls it:
prod's upstream vCommunity carries the same 64 ids.

**Enforced since issue #345 (build time and content import).** The
stock-id guard (`knowledge/context/stock_id_guard.md`) refuses any
definition under an id in the committed stock-id baseline
(`src/vcfcf_core/stock_ids/stock_ids_baseline.json`: 4282 view,
dashboard, report, symptom and alert ids from clean 8.18.7, 9.0.2 and
9.1.1 exports; it holds no super metric or recommendation ids yet, so
those two types are not checked): `validate-sdk` and `build-sdk` in the
factory and the sdk-buildkit (bundled content, then the built pak), the
bundle, discrete and release builders, the per-type `validate` commands,
every factory content-zip import, and `vcfcf_managementpacks install`
(unless `--allow-stock-ids`). `stock-id-check <pak>` lists the stock ids
in any pak or export, read-only: run it on a third-party pak before anyone
installs or uninstalls it. It reports 117 view ids in upstream vCommunity
0.3.1 and 120 in the e1 0.8.1 build. The deliberate case is an explicit
`stock_id_allowlist` entry with a reason, warned on every build. Not
covered yet: the install-time check against the target's existing ids and
the uninstall check from issue #345 (wanted items 2 to 4).

**Not enough on its own.** `content_naming: factory_prefixed` checks names,
not ids. Ports run `unprefixed` by design (#229). The `isUnremovable` guard in
`uninstall_pak` protects built-in paks, not built-in content shipped inside a
custom pak.
