# Stock content id guard (issue #345)

VCF Operations tracks pak and content-import content by id. Installing
content overwrites any object with the same id; uninstalling a pak deletes
every id it shipped. Content that defines a view, dashboard, report
template, super metric, symptom, alert or recommendation under an id the
product ships as its own therefore overwrites the stock object on install
and deletes it on uninstall. That is how the retired factory vCommunity
port deleted 64 stock views from devel (9.0.2), and the upstream Python
vCommunity packs ship 117 (v0.2.8 to v0.3.1) and 120 (the e1 0.8.1 build)
stock view ids. Lesson: `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md`.
Investigation:
`knowledge/context/investigations/2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`.

Only definitions count. A dashboard widget, report section, alert symptom
set or recommendation ref, or a policy enablement that points at a stock id
is a reference and is legal.

## What it is

| Piece | Where |
|---|---|
| Baseline (data: ids, display name, versions) | `src/vcfcf_core/stock_ids/stock_ids_baseline.json` |
| Scanner, loader, allowlist, check | `src/vcfcf_core/stock_ids/guard.py` (stdlib only, self-contained) |
| Generator (pure) | `src/vcfcf_core/stock_ids/generate.py` |
| Factory CLI, repo allowlist, validate and import helpers | `src/vcfcf_packaging/stock_ids.py` |
| Buildkit copies | `sdk_buildkit/stock_ids.py` (guard.py verbatim) and `sdk_buildkit/stock_ids_baseline.json` |

`guard.py` finds the baseline beside itself
(`Path(__file__).with_name(...)`), so the factory and the kit load the same
file with no repo-layout assumption. Pak repos' CI gets it in the kit.

### Baseline format (`vcfcf-stock-ids/1`)

A JSON object: metadata (`about`, `generated`, `regenerate`, `rule`,
`sources`, `counts`, `candidates_not_included`) and
`ids: {<type>: {<id>: {"name": ..., "versions": [...]}}}`. Types:
`view`, `dashboard`, `report`, `supermetric`, `symptom`, `alert`,
`recommendation`. Ids compare case-insensitively, within a type. One line
per id so a regeneration diffs cleanly. Source instances are recorded by
neutral labels, never host names or paths.

### Fail closed

A missing, unreadable, malformed or empty baseline raises
`StockIdBaselineError`; every caller turns that into a failed build, a
failed validate or a refused import. Same posture as the defect gate.

## Where it runs

| Path | What is checked | On a hit |
|---|---|---|
| `validate-sdk` (factory and kit) | bundled content of adapter.yaml (`sdk_builder.check_stock_ids`) | error, exit 1 |
| `build-sdk` (factory and kit) | the same, before the compile; then every definition in the built pak (`_gate_built_pak_stock_ids`) | build fails; a `--release` build deletes the pak |
| `vcfcf_packaging build` / `build-discrete` / `release` / `publish` | the bundle's loaded content, then the assembled zip (`guard_bundle` in `builder.build_bundle` and `discrete_builder._assemble_zip`) | `BundleValidationError`, nothing written |
| `vcfcf_supermetrics`, `vcfcf_dashboards`, `vcfcf_symptoms`, `vcfcf_alerts`, `vcfcf_reports` `validate` | the definitions each loads (symptom, alert and recommendation ids as rendered into AlertContent) | `STOCK-ID:` error, exit 1 |
| every factory content import (`vcfcf_dashboards.client.import_content_zip`: dashboards, views, reports and super metric sync, bundle sync) | the zip about to be posted | refused before any request |
| `vcfcf_managementpacks install <pak>` | every definition in the pak, offline, before login | refused unless `--allow-stock-ids` (then a warning listing them) |
| `python3 -m vcfcf_packaging stock-id-check <path>...` / `python3 -m sdk_buildkit stock-id-check` | read-only report for any packed or unpacked pak, content zip or export | exit 2 (0 clean, 1 cannot check) |

`vcfcf_customgroups` has no check (custom group ids are server-assigned).
Symptom and alert `sync` create through REST, where the server assigns the
id, so they cannot collide; their content-zip and pak forms are checked
above.
`vcfcf_managementpacks validate` and the Tier 1 MPB build have none: MPB
paks ship empty content directories. The distribution zips' `install.py`
is not changed: what it installs passed the bundle build check.

The scanner reads `<ViewDef id>`, `<ReportDef id>`,
`<SymptomDefinition id>`, `<AlertDefinition id>`, `<Recommendation key>`
(not `ref`), policy-embedded `<superMetric uuid>` with a `<formula>`, a
dashboard JSON's top-level `dashboards[].id` and a super metric JSON's
top-level keys, inside nested zips to any practical depth. XML that does
not parse is still scanned for definition tags, so a malformed file cannot
hide one.

## Escape hatch

```yaml
stock_id_allowlist:
  - type: view
    id: 2788178d-7df4-47d7-81de-016f7a1cd18d
    reason: "Why this content must ship under the stock id."
```

In adapter.yaml (paks) or a bundle / `PROJECT.yaml` manifest. Exactly
`type`, `id` and a non-blank `reason`; anything else is refused. Absent by
default. An allowlisted hit prints a warning naming the reason on every
build; an entry that matches nothing is a warning too. The per-type
`validate` commands and the content-import path honour the entries of every
manifest in `bundles/` and `third_party/*/`. A pak built with an allowlist
still needs `install --allow-stock-ids`. The allowlist is for the rare
deliberate case; it is reviewable in the diff that adds it.

## How the baseline is generated, and how an id is shown to be stock

```
python3 -m vcfcf_packaging stock-id-baseline \
  --export <version>=<label>=<export dir or zip> ...   # clean scope-ALL exports
  --inventory <version>=<label>=<type>=<id-name list>   # REST inventories of other instances
  --custom-export <scope-CUSTOM export>                 # negative evidence
  --known-content <label>=<pak, fork or content repo>   # third-party packages
  --factory-tree <dir> --factory-artifacts <dist> --factory-git <repo>
  --exclude-name <marker> --exclude-adapter-kind <prefix>
  --out src/vcfcf_core/stock_ids/stock_ids_baseline.json \
  --candidates-out <scratch path>
```

Lab instances hold factory content, third-party content and pak content
beside the product's. A non-stock id in the baseline fails good builds; a
stock id missing is a hole. The rule (full text in the `generate.py`
docstring) is conservative: an id that cannot be shown to be stock is left
out and listed in the candidates report, never guessed in.

1. **Sources.** Scope-ALL exports from clean instances (no pak under test
   installed), each tagged with version and instance; id/name inventories
   of further instances. Policy-embedded definitions are not observations.
2. **Exclusions (any one keeps an id out).** A name marker (factory prefix
   in both forms, `[AI Content]`, plus third-party tags passed on the
   command line); an excluded adapter kind; a factory id (YAML `id:` values
   in the factory tree, its git history, the registered pak repos, and
   every id in built factory artifacts); a scope-CUSTOM export lists it.
3. **Explained presence.** Each known third-party package is a group of
   ids. It counts as installed on an instance when 90 percent of its ids
   (of the types that instance's sources cover) are present. Presence
   explained by an installed package is not evidence. This keeps a pak
   installed on every lab out (vsanhostmetrics' views and dashboards are on
   all three labs) while a package that merely copied stock ids does not
   hide them.
4. **Evidence.** Present and unexplained on two or more instances: stock.
   On one instance: stock only for a view or report template whose title
   carries the product's `localizationKey` there, or a dashboard whose
   `adapterName` two-instance stock dashboards carry, AND an independent
   third-party package (not installed there) carries the same id: an export
   of its author's own appliance, so a second independent observation.
   Super metrics, symptoms, alerts and recommendations need two instances.

The candidates report names non-stock content found on the source
instances, so it is written to a scratch path, never committed.

## The committed baseline (generated 2026-11-12)

Sources (labels as in the file):

| Label | Version | Inputs |
|---|---|---|
| lab-a | Aria Operations 8.18.7 | scope-ALL export taken before the 2026-11-12 vCommunity fix test (B0), a views-only export the same day, and the built-in view set used for the vCommunity PR recon (8.18.7) |
| lab-b | VCF Operations 9.0.2 | scope-ALL exports before the 2026-11-12 fix test (B0) and its repeat (R0), and the 2026-11-11 views export taken before the 64-view restore |
| lab-c | VCF Operations 9.1.1 | scope-ALL exports before the 2026-11-12 e1 fix test and fix test (B0), the 2026-11-11 upstream-repro baseline, and the built-in view set used for the PR recon (9.1.1) |
| lab-d | VCF Operations 9.1.1 | REST inventories of alerts, symptoms, reports and super metrics (2026-11-11); its scope-CUSTOM export as negative evidence |

Known packages: the factory's reference repos, the three Python forks
(vsanhostmetrics, cluster-perf-risk, vcommunity), and the released
vCommunity paks 0.2.8, 0.3.0, 0.3.2 and 0.8.1. Factory ids: the factory
tree and its YAML history, the registered pak repos (compliance, synology,
unifi, vsanperf, template, vcommunity-java; working trees only) and the
built paks and zips in `dist/`.

| Type | Ids | 8.18.7 | 9.0.2 | 9.1.1 | Candidates, not included |
|---|---|---|---|---|---|
| view | 771 | 704 | 768 | 742 | 176 |
| dashboard | 148 | 135 | 148 | 141 | 61 |
| report | 62 | 60 | 62 | 62 | 37 |
| super metric | 0 | 0 | 0 | 0 | 88 |
| symptom | 2161 | 1373 | 1762 | 2031 | 1189 |
| alert | 1140 | 533 | 862 | 1131 | 1182 |
| recommendation | 0 | 0 | 0 | 0 | 0 |

4282 ids. The 9.0.2 view count includes the 64 stock views devel lost on
2026-10-15 and got back by the 2026-11-11 re-import from a 9.1.1 export:
devel's audit log shows them in its first-boot content load, so they are
stock on 9.0.2.

Cross-checks: all 120 ids in the vCommunity fork's
`tests/test_view_ids.py` (branch `fix/builtin-view-ids-e1`) are in the
baseline as views, the three VCF Management Services views only for 9.1.1.
`stock-id-check` reports 120 view hits in the released e1 vCommunity 0.8.1
pak and 117 in the unpacked upstream 0.3.1 pak, none of their other
content, and none in the fixed builds with re-minted ids.

### Known holes (why a stock id may be missing)

- **Single-instance content of types with no product signal.** 8.18.7-only
  and 9.0.2-only symptoms and alerts (one lab each) and every 8.18.7-only
  or 9.0.2-only view without an independent copy (for example the 8.18.7
  vRealize Automation pricing views) are candidates. An export of a second
  instance of that version closes the gap.
- **Content the export leaves out.** Scope-ALL exports omit adapter-kind
  `ALL` symptoms and alerts and every badge or capacity-key symptom
  (`2026-11-11-alert-symptom-export-completeness.md`); only lab-d's REST
  inventory sees those, so they are single-instance.
- **Recommendations and super metrics.** No source export carried
  `RECOMMENDATION_DEFINITIONS`; the labs show no super metric the product
  ships. Both tables are empty until an export shows otherwise.
- **Versions not measured.** 9.0.2.0200 and 9.1.1.0100 are not separate
  sources; 9.2 is absent.

### Adding a version

Take a scope-ALL export (`POST /api/content/operations/export`,
`{"scope":"ALL"}`, all content types including
`RECOMMENDATION_DEFINITIONS`) on a clean instance of the new version, add
it as `--export <version>=<label>=<path>` to the previous command line
(record the full command line in the PR that changes the file), run it,
read the candidates report, and commit the new baseline. The generator is
deterministic: the same inputs give the same file byte for byte. The guard, the kit and pak
CI pick it up from the file; no code change.
