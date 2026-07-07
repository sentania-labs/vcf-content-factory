# Framework Review — SDK content-emit pipeline + vCommunity reverse-port (CONSOLIDATED)

- **Date:** 2026-06-17
- **Reviewer:** framework-reviewer (RULE-013 blanket pre-PR gate)
- **Area:** `vcfops_managementpacks/sdk_builder.py`, `vcfops_dashboards/{render,reverse,loader}.py`, `vcfops_alerts/render.py`, `vcfops_symptoms/loader.py`, `vcfops_managementpacks/buildkit.py`, `vcfops_extractor/{reverse_local.py(new),cli.py,extractor.py}`
- **Change:** Framework support for the vCommunity content reverse-port + the SDK-pak content-emit pipeline (SM/symptom/alert/report emit, content/files, `@supermetric` formula resolution, bundled-content prefix relaxation, external-view UUID passthrough, `sm_scope` wiring, `safe_name` dedup, PropertyList/RRA reverse parsers + render, operator map, symptom `id:` field, buildkit dead-rewrite removal).
- **Verdict:** **APPROVE** (0 BLOCKING)

## Checks re-run (independently)

- **validate-chain:** PASS — SM(24), views(16)/dashboards(6), customgroups(3), symptoms(17), alerts(9)/recs(10), reports(1), MP Tier1(5)/Tier2(4 incl. vcommunity). Warnings are pre-existing advisory key-drift/label-lint, not errors.
- **tests:** 430 passed, 4 skipped, 162 deselected, 103 warnings. Targeted content-emit + reverse round-trip suites: 63 passed.
- **render-regression:** clean — emitted view XML carries zero `displayName` localizationKeys (6c59f6b preserved); empty-description views emit `<Description>` with no `localizationKey` AND no `.desc` properties entry (symmetric, localization tree intact).
- **SDK build:** `build-sdk content/sdk-adapters/vcommunity` → `vcfcf_sdk_vcommunity.1.0.0.7.pak`. Inventory matches the brief exactly: **37 SM JSON (all with modificationTime), 96 view XML, 12 dashboard JSON, 2 symptomdef (UUID ids + `!=`), 6 solutionconfig.** No `content/alertdefs/` dir (vcommunity bundles no alerts) — "only emit populated subdirs" holds.
- **pak-compare:** n/a (reference_paks dir absent); compared key emitted artifacts directly against `reference/references/vmbro_vcf_operations_vcommunity/` source pak instead (SM JSON keying, formula tokens, RRA depth — all match).

## Hunt results (every named failure mode)

1. **Tuple-arity (`_load_bundled_content` 6-tuple).** Both production call sites (`sdk_builder.py:2788`, `:3032`) unpack exactly 6; all test sites use `*_`. Def returns 6-tuple incl. empty-`[]` reports. No latent `ValueError`. CLEAR.
2. **Global-default / pak-specific leak (anchor 00d3382).** `enforce_framework_prefix=False` is confined to bundled-content (`sdk_builder` 769–857), local reverse-port, and the pre-existing packaging/composer `factory_native` paths. `vcfops_dashboards/loader.py` `load_dir` (the standalone content-import / validate path) still defaults `enforce_framework_prefix=True`. Packaging/composer/SM/CG/report loaders untouched this session. No leak.
3. **Cross-ref resolution.** `_resolve_sm_formula` emits `Super Metric|sm_<uuid>` and raises `SdkBuildError` loudly on an unbundled ref (not a dangling ref). Verified end-to-end in the built pak: `Business Application Performance` formula → `sm_ad345475-...` which is PRESENT as a bundled SM JSON key. SM JSON keyed by bare UUID inner-shape matches the reference pack exactly. `sm_scope` wires bundled SM source paths into `render_views_xml` so view-column `supermetric:"name"` resolves against the same bundled YAMLs (same `id:`-derived UUID). **Operator map covers all 14 operators** the symptoms loader permits (STATIC ∪ PROPERTY) — complete, maps to platform symbol form (`NOT_EQ`→`!=`).
4. **External-UUID passthrough.** Loader gate `w.view_name not in known_views and not _UUID_RE.match(...)` with **anchored** `^uuid$` regex — a bare unbundled *name* still raises; only canonical UUIDs pass through. Render falls back to self for the (already-validated) UUID case. No name leak.
5. **Reverse round-trip.** PropertyList/RRA/`ascending_range`/`is_string_metric`/`_to_bound` parsers invert the forward render; both new types are in `_SUPPORTED_WIDGET_TYPES` and wired into the dispatch + the extractor YAML-emit side (symmetric field names). Dedicated round-trip tests (parse→forward-render→MATCH) pass. RRA `depth="0,2"` re-emitted byte-faithful vs the reference source pak.
6. **content/files + SolutionConfig + symptom UUID.** 6 solutionconfig emitted; symptomdef ids are `SymptomDefinition-<uuid>`; alertdef SymptomSet cross-ref (`render.py:292`) resolves `sym_uuid` from the matched referenced symptom — alertdef and symptomdef agree on the id. Symptom `id:` is optional, UUID-validated, defaults None (sync-by-name path & RULE-007 contract preserved for native content).

## Findings

### BLOCKING
None.

### WARNING
- **[process / CLAUDE.md "After tooling changes"]** `vcfops_dashboards/render.py` is modified → **all distribution zips in `dist/` are stale.** A `content-packager` rebuild of every `bundles/` manifest must run before any built zip ships. Flag to orchestrator. (Not a code defect; a release-hygiene gate.)

### NIT
- `vcfops_extractor/reverse_local.py` docstring (line ~20) still lists PropertyList/ResourceRelationshipAdvanced as "unsupported … skipped" — they are now fully supported in `reverse.py`. Stale doc-comment; update for accuracy.
- `vcfops_dashboards/render.py` external-view INFO guard `if _view_ref is w.view_name and _view_ref not in views_by_name` — the second clause is redundant given the first. Harmless.

## If shipped as-is

An operator installing the vCommunity SDK pak gets a correct content tree (37 SMs with resolved cross-refs, 96 views with distinct transformed-column labels, 12 dashboards incl. topology/property widgets, 2 UUID-keyed symptomdefs). The one actionable item is process: rebuild `dist/` zips before publishing, or downstream bundle consumers would ship a stale renderer's output.
