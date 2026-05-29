# Lessons Index

Lessons written in blood. Dead ends documented so nobody walks into them again.
Read before going down a path that looks obvious. If a lesson covers your
situation, heed it.

| Story | Lesson |
|---|---|
| [dell-redfish-relationship-strategies.md](dell-redfish-relationship-strategies.md) | Three MPB relationship strategies tried against Dell Redfish; all failed. URL-path hierarchies require Tier 2. |
| [synology-dsm-client-side-joins.md](synology-dsm-client-side-joins.md) | Synology DSM has no common join key across endpoints. MPB can't model it. First Tier 2 build: 9 paks, 8 structure fixes, 20 commits. |
| [pak-install-reliability.md](pak-install-reliability.md) | Five consecutive pak install failures (vSphere Storage Paths v2). Root causes: adapter kind mismatch, reserved chars, CredentialKinds, ARIA_OPS in template.json, events wrong format. |
| [unifi-metric-key-parity.md](unifi-metric-key-parity.md) | MPB ignores `key:` in design.json — derives keys from labels only. Six of eight base metrics had key drift. Also: MPB <9.2 doesn't support filter projections; don't ship fragile workarounds. |
| [pak-isunremovable-vendor-bug.md](pak-isunremovable-vendor-bug.md) | VCF Ops 9.0.2 `isUnremovable` flag not enforced server-side. vSAN pak removed from lab; no recovery path. |
| [foreign-resource-property-push.md](foreign-resource-property-push.md) | Java SDK `ResourceCollection.add()` silently drops foreign resources. Use `suiteAPIClient.getClient()` via reflection for cross-MP property push. 10 builds to prove it. |
| [pak-content-bundling.md](pak-content-bundling.md) | Pak content/ directory must use subdirectory pattern (not flat files). Views go in `content/reports/`, not `content/views/`. SymptomSets needs ≥2 children. 3 builds to get right. |
| [pak-content-localization-bundles.md](pak-content-localization-bundles.md) | Four localization bundles required for dashboard/view import. `localizationKey` in view XML must exactly match properties-file suffix — mismatch kills the entire content tree with `ERROR: Localization for key <x> is absent`. 2 builds (v21/v22) to isolate. |
| [heatmap-empty-groupby-crashes-renderer.md](heatmap-empty-groupby-crashes-renderer.md) | Heatmap `groupBy:{}` causes `JSONException("type not found")` in `HeatMapAction.initParam` — widget blank, Internal Server Error popup. Fix: emit 9-key self-grouping block. Also: `AlertList selfProvider:true + resource:[]` silently never queries; use `pin_to_world:true` to emit world-bound resource array. |
