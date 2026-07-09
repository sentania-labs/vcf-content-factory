# Content Structure & Tooling Cleanup v2

**Status:** queued 2026-04-27 (items #1 and #3 still scoped; #2 superseded
by v3; #4 subsumed into v3)
**Owner:** orchestrator (planning) + tooling agent (implementation)
**Builds on:** `designs/release-lifecycle-v1.md` (publish pipeline + ThirdPartyContent routing already shipped)
**Related:** `designs/content-structure-v3.md` — bigger restructure that
supersedes the third_party/ promotion in this doc and the resolver fix.

## Context

After the release-lifecycle work landed and the first `/publish` ran end-to-end (factory-native + third-party), several follow-up items surfaced that are individually small but cluster around the same conceptual area: **what kinds of things live where in source, and what does the validator check for them**. Queuing them together as a single v2 workstream so they ship as a coherent reorganization rather than scattered patches.

## Items in scope

### 1. Convert legacy single-dashboard bundles to discrete dashboard releases

Two bundles in the repo today are 1-dashboard wrappers, not true multi-content bundles:

- `bundles/capacity-assessment.yaml` — wraps `dashboards/capacity_assessment.yaml` + 11 SMs + 2 views + 1 customgroup (all already in top-level dirs).
- `bundles/vks-core-consumption.yaml` — wraps `dashboards/vks_core_consumption.yaml` + 8 SMs + 1 view + 1 report (all in top-level dirs).

Per the dictionary update (`context/dictionary.md`, the `Bundle` definition tightened 2026-04-27), bundles are reserved for genuinely multi-content sets. These two predate the release-manifest concept; they earned their place when bundles were the only way to declare "this group ships together," which is now the release manifest's job.

**Per-bundle cleanup:**

1. Create `releases/<slug>.yaml` with headline = the dashboard YAML, version 1.0.
2. Delete `bundles/<slug>.yaml`.
3. Validate.
4. Move existing `description:`, attribution if any, into the release manifest.

After this, `bundles/` has zero entries. It's reserved for true multi-content bundles when they appear (a "Capacity Suite" or "All VCF-CF" mega-bundle).

**Risk:** the dependency walker (Phase 1.5) handles dashboard → views → SMs → customgroups for capacity-assessment correctly (verified during Phase 1.5 build). vks-core-consumption has a report dependency, which the walker may or may not handle today — needs verification before conversion.

### 2. Promote third-party content to a top-level `third_party/` directory

Currently third-party content lives at `bundles/third_party/<name>/` (subdirs: dashboards, views, supermetrics). The Phase 2 routing tooling reads `factory_native: false` from the bundle YAML and routes to `vcf-cf-bundles/ThirdPartyContent/<sub>/`. Routing is correct, but the source layout has cosmetic friction:

- `bundles/` conceptually mixes factory-native with third-party (third-party isn't really a bundle concept anymore).
- The dist-repo uses `ThirdPartyContent/` — symmetric source layout would be `third_party/` at repo root.

**Move:**

- `bundles/third_party/<name>/` → `third_party/<name>/`
- `bundles/third_party/<name>.yaml` → `third_party/<name>.yaml`
- Validator/loader updates in `vcfops_packaging` to scan `third_party/` (in addition to `bundles/`).
- `release_types.headline_to_dir()` updated to recognize `third_party/<name>.yaml` source path.
- The Phase 2 routing logic still triggers on `factory_native: false`; just the source dir changes.

**Risk:** low — pure rename + validator path update. UUIDs unchanged, manifests unchanged in content.

### 3. Validator polish: time_window warning only when view isn't dashboard-embedded

The view loader's validate step (`vcfops_dashboards/loader.py:923`) warns on any view with aggregating column transformations (AVG/MAX/PERCENTILE/TRANSFORM_EXPRESSION) that lacks an explicit `time_window:`. The warning is conservative — for views designed to be embedded in dashboards, the dashboard's time selector drives aggregation regardless of the view's own `time_window:`. The warning fires whether or not the view will ever be consumed standalone.

Surfaced 2026-04-27 on IDPS Planner views (both `IDPS Planner Host Metrics` and `[IDPS] IDPS Planner VM Metrics`), which are dashboard-embedded — the warning is decorative noise for that case.

**Improvement:** during validate, build a set of view names referenced by any dashboard's `View` widgets. For each view with the aggregating-column-no-window condition, suppress the warning if the view is in that set. Still warn for views that aren't embedded in any dashboard (those genuinely default to the validator's safe-default window when opened standalone).

**Risk:** low — the dependency walker already builds the dashboard→view edge (Phase 1.5). Reuse it.

### 4. Bundle name resolver: also search `third_party/` (or `bundles/third_party/`)

When running `python3 -m vcfops_packaging release bundle idps-planner` (without the full path), the resolver fails:

```
ERROR: could not resolve 'idps-planner' to a bundle YAML file.
  Tried: path, bundles/idps-planner.yaml, display name match in bundles/
```

The slash command's name resolution doesn't search `bundles/third_party/`. Workaround today: pass the full path
(`bundles/third_party/idps-planner.yaml`).

**Fix:** extend `cmd_release`'s bundle-name resolver to also search `bundles/third_party/<name>.yaml` (or, after item #2 lands, `third_party/<name>.yaml`).

**Risk:** trivial — one extra path candidate in the lookup.

## Sequencing

The four items are independent in code but related in concept. Suggested order:

1. **Item 4** (resolver fix) — trivial, ships standalone, removes the workaround.
2. **Item 2** (third_party/ promotion) — one-time directory move + validator path update. Do this before item 1 so the legacy bundle cleanup can also get the resolver-aware shape.
3. **Item 1** (legacy bundle cleanup) — convert capacity-assessment + vks-core-consumption to dashboard releases.
4. **Item 3** (validator polish) — independent; can ship alongside any of the above.

All four can land in a single tooling pass (or split per-item if review is tighter that way).

## Validation gates

Each item ships only when:

- All 8 validators return their expected exit codes.
- Existing pytest suite passes.
- A `--dry-run` publish against a temp dist repo confirms no unintended routing changes (third-party still goes to ThirdPartyContent/, factory-native still goes to top-level subdirs).

## Out of scope

- Mega-bundle support (true multi-content "Capacity Suite" or "All VCF-CF") — author when there's actually content to compose, not preemptively.
- Bundle composition syntax (`includes: [other-bundle.yaml]`) — same reason; defer.
- Renaming the dist repo (`vcf-content-factory-bundles` → something else) — historical name, marketing-resonant, not worth the disruption.
