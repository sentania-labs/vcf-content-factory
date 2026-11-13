# Content-name prefix: `[VCF CF] ` (moved from `[VCF Content Factory] `, 2026-11-12)

Factory content names start with `[VCF CF] `. Until 2026-11-12 they started
with `[VCF Content Factory] `. The Operations dashboard editor caps a
dashboard name at 50 characters
(`knowledge/lessons/dashboard-name-limit-50-editor.md`); the old prefix spent
22 of them and left 28 for the title, the new one spends 9 and leaves 41.

Unchanged by the move: management pack display names (prose
`VCF Content Factory <name>`, no brackets), the dashboard folder
(`name_path: VCF Content Factory`), vendor strings, repo and package names,
the `vcfcf_` adapter-kind prefix.

## If validate fails with "carries the retired prefix"

```
content/views/foo.yaml: name "[VCF Content Factory] Foo" carries the retired
prefix "[VCF Content Factory]"; factory content now uses "[VCF CF]". Run
`python3 -m vcfcf_common migrate-prefix` ...
```

Your clone has content written before the move. There is no period in which
both spellings are accepted: by-name cross-references (a view column naming a
super metric, a dashboard naming a view) would split across the two. Fix it
in one step:

1. Commit or stash your work (the command refuses a dirty tree unless
   `--force`, so the rename is its own reviewable diff).
2. `python3 -m vcfcf_common migrate-prefix --dry-run` from the repo root:
   every line it would change.
3. `python3 -m vcfcf_common migrate-prefix`, then the validation chain.
4. Each pak repo is its own repo: `python3 -m vcfcf_common migrate-prefix
   content/sdk-adapters/<name>` (or the path of a standalone pak checkout),
   committed in that repo.
5. Sync the renamed content, then clean up what the rename left on each
   instance (below).

`migrate-prefix [ROOT] [--dry-run] [--force]` rewrites the bracketed label as
text, so comments, quoting and key order stay as they were. It reads only:

- factory checkout: YAML under `content/` (not `content/sdk-adapters/`),
  `third_party/` (not `debug/` captures) and `bundles/`;
- pak repo (`ROOT/adapter.yaml`): its YAML, root `README.md` /
  `REFERENCE.md`, `docs/**/*.md`, `tests/**/*.py`, `describe.xml`,
  `*.properties`. Never `CHANGELOG*` or release notes.

Nothing else is opened, so investigations, reviews, designs and recon logs
keep their historical names even when the command runs at the repo root.
`[VCF Content Factory](https://...)` Markdown links are kept. A label wrapped
across two lines of a folded description is joined onto one. Every rewritten
YAML file is re-parsed and must equal the original with only its strings
rewritten; if not, nothing is written. A second run changes nothing.

## Where the prefix lives in code

`src/vcfcf_core/naming.py` is the one definition: `FACTORY_PREFIX`,
`LEGACY_FACTORY_PREFIX`, the predicates, `framework_prefix_problem()` (the
load-error text every loader raises), `rewrite_legacy_prefix()` (the
migration's text rewrite) and `id_basis_name()`. The sdk-buildkit ships it as
`naming.py` (kit 1.0.29).

Behaviour that depends on the prefix beyond a string literal:

| Behaviour | Where | After the move |
|---|---|---|
| Prefix enforcement on load | every core loader's `validate` | legacy name: error naming the file and the command |
| Recommendation key `Recommendation-df-<kind>-<slug>` | `Recommendation.id` | slug strips either spelling: key unchanged |
| AlertContent.xml / pak alert ids `AlertDefinition-<kind>-<slug(name)>`, slug-form symptom ids, `_rec_key` | `vcfcf_core/alerts/render.py` `_slug` | slugs `id_basis_name(name)` (the legacy spelling): ids unchanged |
| Dashboard widget UUIDs `uuid5(widget::<dashboard name>::<local id>)` | `Widget.widget_id` | derived from `id_basis_name`: widget UUIDs unchanged |
| Discrete release slugs | `discrete_builder._item_slug` | strip either spelling: unchanged |
| Discrete zip file name `<prefix><display name>.zip` | `discrete_builder` | `[VCF CF] <name>.zip` |
| Alert-to-symptom and alert-to-recommendation reference checks | alerts loader, `sdk_builder.check_bundled_content_references` | either spelling is checked (a legacy reference fails, with a migration hint) |
| Pak `content_naming` | `sdk_builder.check_content_naming` | `factory_prefixed`: new prefix required, legacy an error even when the key is undeclared; `unprefixed`: neither spelling allowed |
| Dashboard name over 50 characters | `Dashboard.validate` | factory-prefixed: error stating the 41-character title budget; any other name: warning |
| Distribution README bundle names | `readme_gen` | new prefix |

So the rename changes display names and nothing that an installed object is
keyed by, except where the platform keys by name.

## What an installed instance sees

Import identity per type, and what a rename does to an object already
installed:

| Type | Factory install path | Identity | Rename result | Source |
|---|---|---|---|---|
| Super metric | content zip | YAML UUID | in place | vcfops-content-model skill §Identity schemes; `api-surface/install_and_enable.md` (upsert by id); `investigations/2026-08-26-vcf-license-consumption-inventory.md` (an SM renamed under its UUID) |
| View | content zip | YAML UUID (same name, new UUID duplicates with a numeric suffix) | in place, expected | `api-surface/content_import_skip_semantics.md` §Side finding |
| Dashboard | content zip, pak content | **name** (same name, new UUID replaces and orphans the old UUID) | not observed for same UUID, new name; may leave the old one | vcfops-api skill gotcha 8; `content_import_skip_semantics.md` run F1 |
| Report | content zip | YAML UUID | in place, expected | vcfops-content-model skill |
| Custom group | REST, matched by name | name (server id) | **new object, old one left** | vcfops-content-model skill; `vcfcf_customgroups` sync |
| Symptom | REST, matched by name (factory, distribution installer); pak: `SymptomDefinition-<uuid>` | name; pak: YAML UUID | factory: **new object, old left**; pak: in place | `vcfcf_symptoms` sync; `alerts/render.py` `_symptom_id` |
| Alert | REST, matched by name (factory, installer); pak / AlertContent.xml: derived id | name; pak: derived id (unchanged, above) | factory: **new object, old left**; pak: in place, expected | `vcfcf_alerts` sync; `reviews/compliance-build-86.md` item 1 (in-place rename expected, not proven) |
| Recommendation | AlertContent.xml / pak only | `Recommendation-df-<kind>-<slug>` (unchanged) | in place | `alerts/loader.py` `Recommendation.id` |

Pak upgrades: a pak-shipped alert, symptom or recommendation keeps its id, so
the upgrade is expected to update it in place (the compliance build 86
review's open question about whether active alerts survive a renamed
definition applies). A pak-shipped dashboard is imported by name; whether
the pak installer removes the dashboard the previous version shipped is not
recorded anywhere in the repo (a pak *uninstall* deletes its content by id:
`investigations/2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`),
so after an upgrade check for an old-named dashboard beside the new one.

## Removing the leftovers

`python3 -m vcfcf_common cleanup-legacy-prefix [ROOT] [--profile NAME]
[--types k1,k2] [--apply]`. `ROOT` is the factory checkout or pak repo whose
content defines the names (for a pak, its `bundled_content`). Dry run by
default; `--apply` deletes. An object is deleted only when all of these hold:

1. its name is exactly `[VCF Content Factory] <title>` for a repo object
   named `[VCF CF] <title>` (no pattern or prefix match);
2. the object named `[VCF CF] <title>` is installed;
3. super metrics, views, dashboards, reports: that new-named twin carries the
   repo UUID and the old-named object does not; anything else is a
   CONFLICT, listed and left alone;
4. custom groups, symptoms, alerts: the two are different objects.

It deletes dependents first (dashboards, views, alerts, symptoms, custom
groups, super metrics). Report definitions have no delete API: a report
leftover is listed as MANUAL (Administration > Content > Reports).
Recommendations are not checked: their key does not change. Exit 0 clean,
1 when a conflict was listed, 2 on a failed delete or bad arguments.
