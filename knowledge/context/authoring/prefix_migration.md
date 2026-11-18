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

Your clone has content written before the move. For factory content
(`content/`, `third_party/`, `bundles/`) there is no period in which both
spellings are accepted: by-name cross-references (a view column naming a
super metric, a dashboard naming a view) would split across the two. Pak
repos are the one exception, a transition (§Pak repos). Fix it in one step:

1. Commit or stash your work (the command refuses a dirty tree unless
   `--force`, so the rename is its own reviewable diff).
2. `python3 -m vcfcf_common migrate-prefix --dry-run` from the repo root:
   every line it would change.
3. `python3 -m vcfcf_common migrate-prefix`, then the validation chain.
4. Each pak repo is its own repo and moves on its own schedule (§Pak repos):
   `python3 -m vcfcf_common migrate-prefix content/sdk-adapters/<name>` (or
   the path of a standalone pak checkout), committed in that repo.
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
`[VCF Content Factory](https://...)` Markdown links are kept. The rule is
lexical (the label directly followed by `(`), so it would also keep a *name*
of that shape, such as `[VCF Content Factory](Beta) X`; its loader then
rejects it with the retired-prefix error, and it is renamed by hand. No name
in the corpus has that shape (2026-11-12). A label wrapped
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
| Discrete zip file name | `discrete_builder._assemble_zip` | `[VCF CF] <title>.zip`, the prefix once (the display name's own prefix is stripped first; before, the name carried it twice). Release builds rename the zip to the release slug, so published names do not change |
| Alert-to-symptom and alert-to-recommendation reference checks | alerts loader, `sdk_builder.check_bundled_content_references` | either spelling is checked (a legacy reference fails, with a migration hint) |
| Pak `content_naming` | `sdk_builder.check_content_naming` | `factory_prefixed` (declared or default): all names legacy, accepted with one warning per pak; the two spellings mixed, an error per legacy name; all new, silent (§Pak repos). `unprefixed`: neither spelling allowed (before, only the legacy one was checked) |
| In-pak content paths: `content/dashboards/<dir>/`, `content/reports/<dir>/` (views and reports), `content/supermetrics/<name>.json`, `content/symptomdefs/<name>.xml`, `content/alertdefs/<name>.xml` | `sdk_builder._write_outer_pak`, `_view_slug` | slugged from `id_basis_name(name)` (the legacy spelling): paths unchanged |
| Summary-tab binding key in `content/dashboards/dashboards.properties` (`<dir>=<AdapterKind>:<ResourceKind>`, the key the server-side installer binds by: `api-surface/summary_dashboard_pak_binding.md`) | `sdk_builder._write_outer_pak` | the dashboard directory above: key unchanged |
| Dashboard `resources.properties` keys (the escaped dashboard name) | `sdk_builder._generate_dashboard_resources_properties` | new spelling: these are localization entries for the display name, consistent with `dashboard.json`; kept name-bearing by choice |
| Dashboard name over 50 characters | `Dashboard.validate` | factory-prefixed: error stating the 41-character title budget; any other name: warning |
| Distribution README bundle names | `readme_gen` | new prefix |

So the rename changes display names and nothing that an installed object is
keyed by, except where the platform keys by name. For paks this is pinned by
`tests/test_pak_render_prefix_stable.py`: a synthetic pak rendered with
legacy names and with migrated names has the same file list and the same
binding key, and its files differ by display strings only.

## Pak repos

Pak repos (`content/sdk-adapters/<name>/`, each its own repo) migrate at
their own pace once an sdk-buildkit containing this change (1.0.29 or later)
is released. A pak cannot move first: its release CI builds with the kit its
`BUILDKIT_TAG` pins, and a kit before this change rejects the new prefix in
a `factory_prefixed` pak. So for a transition, `check_content_naming`
(`validate-sdk`, `build-sdk`, and `vcfcf_managementpacks validate` over the
registered clones) treats a `factory_prefixed` pak, declared or default, as:

| Pak's bundled names | Result |
|---|---|
| all prefixed names in the legacy spelling | accepted, one warning per pak naming `migrate-prefix` and saying a later kit makes the legacy spelling an error |
| the two spellings mixed | an error per legacy name: the pak's by-name references would split |
| all in the new spelling | passes, nothing printed |

Factory content keeps the hard cut. The factory's CI, which clones the
registered paks at their default branch, therefore stays green while they
are unmigrated: each prints its warning.

To migrate a pak:

1. Wait for a released kit with this change (`sdk-buildkit-v1.0.29` or
   later).
2. From a factory clone, `python3 -m vcfcf_common migrate-prefix <pak dir>
   --dry-run`, then without `--dry-run` (clean tree).
3. In the same commit, bump the pak's `BUILDKIT_TAG` and its `SHA256SUMS` to
   that kit.
4. `validate-sdk` (the warning is gone), commit and PR in the pak repo.
5. After the upgraded pak is installed, clean up on each instance
   (§Removing the leftovers, run from the pak root).

Do not author new-prefix content into an unmigrated pak: that makes it a
mixed pak, which fails. Migrate it first.

## What an installed instance sees

Import identity per type, and what a rename does to an object already
installed:

| Type | Factory install path | Identity | Rename result | Source |
|---|---|---|---|---|
| Super metric | content zip | YAML UUID | in place | vcfops-content-model skill §Identity schemes; `api-surface/install_and_enable.md` (upsert by id); `investigations/2026-08-26-vcf-license-consumption-inventory.md` (an SM renamed under its UUID) |
| View | content zip | YAML UUID (same name, new UUID duplicates with a numeric suffix) | in place, expected | `api-surface/content_import_skip_semantics.md` §Side finding |
| Dashboard | content zip, pak content | **name** (same name, new UUID replaces and orphans the old UUID) | content zip: **a second dashboard under a server-assigned id; the old-named one keeps the repo UUID** (measured 8.18.7, 9.0.2, 9.1.1; §The RESYNC dashboard states). Pak: not measured | vcfops-api skill gotcha 8; `content_import_skip_semantics.md` run F1; `investigations/2026-11-18-dashboard-import-by-name-and-delete-noop.md` |
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

```
python3 -m vcfcf_common cleanup-legacy-prefix [ROOT] --profile NAME [--types k1,k2]
python3 -m vcfcf_common cleanup-legacy-prefix [ROOT] [--types k1,k2] --profile NAME --apply --plan-digest DIGEST
```

`ROOT` is the factory checkout or pak repo whose content defines the names
(for a pak, its `bundled_content`). There is no default profile: pass
`--profile`, or set `VCFOPS_PROFILE` (shell or `.env`); the first output line
names the profile, its host and which of the two chose it. The default is a
dry run. Flags are not abbreviated (`--appl` is an error, not `--apply`).

An object is deleted only when all of these hold:

1. its name is exactly `[VCF Content Factory] <title>` for a repo object
   named `[VCF CF] <title>` (no pattern or prefix match);
2. it is the same kind of object: symptoms and alerts match on name,
   adapter kind and resource kind from the repo YAML, custom groups on name
   and group type (`type:`, default `Environment`). A same-named object of
   another kind is listed as SKIP and left alone. Example in the repo today:
   the factory's MPB symptom `[VCF Content Factory] Synology UPS On Battery`
   (`mpb_synology_dsm`/`ups`) and the synology pak's symptom of the same
   name (`synology_diskstation`/`SynologyUps`); a run from either root
   touches only its own;
3. the object named `[VCF CF] <title>`, of the same kind, is installed;
4. super metrics, views, reports: never deleted. Their rename lands in place
   (same UUID), so a legacy-named one under another id is not a leftover of
   this migration (a pak's object, a user's clone): CONFLICT. One under the
   repo id is the repo object not yet synced: SKIP. Views are listed by the
   thumbnail's `viewDefinitionKey` (`id` as a fallback): the view listing
   on 8.18.7, 9.0.2 and 9.1.1 carries no `id`, and before 2026-11-18 the
   tool dropped every view, so no view appeared in any plan;
5. dashboards: the new-named twin carries the repo UUID, the old-named one
   does not, and the old one's owner (`getDashboardList` `owner`) is the
   account the factory's dashboard sync imports as on this profile
   (`/api/auth/currentuser`, the account `vcfcf_dashboards sync` stamps):
   delete. The repo UUID is not on the new name and a copy holds one of the
   names: RESYNC (§The RESYNC dashboard states). Anything else is CONFLICT.
   The listing shows each dashboard's owner, `locked` when listed so, and
   the twin's id;
6. custom groups, symptoms, alerts: the two are different objects.

The dry run ends with what to back up: a content export of the profile
(Administration > Content > Export, all content types) or a snapshot of the
instance, and the list of objects to be deleted. It then prints a plan
digest and the exact apply command to run. The digest has three dash-joined
parts: the scope (profile, resolved ROOT, selected kinds in canonical
order), the host, and every listed verdict. `--apply` needs `--plan-digest`
with that digest: it recomputes the plan and deletes nothing unless the
digest matches, so it deletes exactly what was reviewed, in the scope and on
the instance it was reviewed in. A refusal says which of scope, host or plan
changed, and names no object.

Run the printed command, not a hand-written one. It repeats every input that
shapes the plan: ROOT as an absolute path (omitted only when it is the
current directory), `--types` in canonical order when the dry run was given
it, and `--profile` always, even when the dry run took the profile from
`VCFOPS_PROFILE`, so the apply does not depend on the environment. Arguments
are shell-quoted (a ROOT with a space works). Dropping `--types` from it
widens the scope, and the apply is refused. Digests printed before the scope
was added (16 hex characters, no dashes) no longer match: dry-run again.

Deletes run dependents first (dashboards, alerts, symptoms, custom groups)
and stop at the first failure, listing what was deleted and what was not. A
dashboard delete counts only when a re-list no longer shows the id (the UI
delete answers HTTP 200 whether or not it deleted; §Deleting dashboards).
Recommendations are not checked: their key does not change. Exit 0 clean,
1 when a conflict or a RESYNC dashboard was listed, 2 on a refused apply,
a failed delete, a listing it could not read (no plan is made) or bad
arguments.

### The RESYNC dashboard states

Measured on 8.18.7, 9.0.2 and 9.1.1
(`investigations/2026-11-18-dashboard-import-by-name-and-delete-noop.md`):
a content-zip dashboard import is keyed by name. Syncing `[VCF CF] <title>`
while `[VCF Content Factory] <title>` is installed creates a second dashboard
under a server-assigned id; the old-named one keeps the repo UUID. Deleting
only the old-named one would delete the repo UUID and leave the new name
under a server id. Each further sync on that state, for instance after a
delete that did not take, adds another new-named copy.

What works, proven on all three versions: delete **every** copy (the
old-named one and each new-named one), then import the dashboard again.
With no dashboard of that name or id present, the import lands under the
repo UUID with the new name.

The plan reports RESYNC, listing every same-named copy, for three states:

| State | On the instance | Why it is not left alone |
|---|---|---|
| two-copy | old-named copy under the repo UUID, one or more new-named copies under server ids | what a normal sync leaves |
| old-only | old-named copy under the repo UUID, no new-named copy | a sync now creates the two-copy state (before 2026-11-18 this was SKIP "sync first") |
| new-only | new-named copies only, none under the repo UUID | a sync updates one of them by name and the repo UUID never returns (for instance after deleting only the old-named copy) |

An old-named copy under another id with no new-named copy stays SKIP: a sync
then lands under the repo UUID, because neither the name nor the id is taken.

The printed remedy covers every RESYNC dashboard of the run at once, in this
order:

1. one `python3 -m vcfcf_dashboards delete-dashboard <ids> --profile P`
   with every copy of every RESYNC dashboard (copies whose listed owner
   differs from the profile's session user get their own command, to run on
   a profile that signs in as that owner, §Deleting dashboards);
2. the same dry run again, which must show no RESYNC line; if any remains,
   repeat step 1 for the ids it lists;
3. one import per dashboards tree: `python3 -m vcfcf_dashboards sync
   --profile P` from the repo root (with `--views-dir` / `--dashboards-dir`
   for a `third_party/` project); for a pak, re-install the pak (the
   import-by-name behaviour was measured for content zips, not paks).

Why not a delete-then-sync pair per dashboard: `vcfcf_dashboards sync`
re-imports the whole dashboards tree, not one dashboard. With two RESYNC
dashboards A and B, deleting A's copies and syncing adds a copy of B (still
in its state) under an id none of the printed deletes covers; B's printed
delete then passes, the next sync updates the surviving copy by name, and B
stays off its repo UUID.

`--apply` does not perform the remedy: it leaves no dashboard of that name
until the re-import, which breaks rule 3 (nothing is deleted before its
successor is installed), and the re-import is a separate step this tool
does not run. RESYNC does not block `--apply` of the plan's other deletes.

### Deleting dashboards: owner and lock

Measured on 9.1.1 (`investigations/dashboard_delete_non_owner_2026-11-18.md`;
the migration run in
`investigations/2026-11-18-dashboard-import-by-name-and-delete-noop.md`):
ownership decides whether the UI delete (`deleteTab`) deletes; the lock does
not. A non-owner's delete, the built-in admin account included, answers HTTP
200 and deletes nothing; the owner deletes, even a dashboard every other
account sees as locked. `locked`, `edit` and `shared` are per-viewer:
`locked: true` is how a non-owner sees a dashboard someone else owns and
shared. 8.18.7 and 9.0.2 not measured for a non-owner.

A factory sync is owned by the built-in admin account whichever account runs
it: the zip writes the importing user's id into the `L.v1` marker and the
`usermappings.json` entry, and 9.1.1 maps a marker match to the built-in
admin. Delete as the account the listing names as owner:

- run `delete-dashboard` on a profile whose session user
  (`/api/auth/currentuser`) is the listed `owner`. The plan flags each copy
  whose listed owner differs from that user; the lock is never reported as a
  cause;
- `delete-dashboard` compares the listed owner with the same
  `/api/auth/currentuser` account the cleanup uses, and words a mismatch as
  "listed owner X differs from session user Y" (a directory suffix shows as
  what it is). It warns before the call, still sends it, then re-lists with
  a strict listing (an unreadable answer is an error, never "empty") and
  reports each id deleted, still listed (with the likely cause), or not
  verified (not listed before the call; an after-listing that could not be
  read or lost dashboards that were not targets). A name matching several
  dashboards is refused with their ids unless `--all-copies`; the cleanup's
  remedy passes ids. A UUID is matched case-insensitively. Exit 0 only when
  every target was listed and is gone, 1 otherwise, 2 on a UI error;
- the verification's limit: when another owner already holds the same id,
  an import adds a second record under it, one per owner, and each account
  lists only the other's copy. Deleting the session's own copy then leaves
  its listing unchanged, and the id is reported still listed although
  something was deleted. The "still listed" message says so; a `DASHBOARDS`
  content export or a listing as the owner settles it. The error is in the
  safe direction: a surviving dashboard is never reported deleted;
- measured, not implemented: an Administrator-role session removes another
  account's dashboard with `dashboardShare.action` `discardDashboards`
  (`api-surface/dashboard_delete_api.md` §Non-owner removal). Unlocking does
  not let a non-owner delete, `changeOwner` by a non-owner answers `notOk`,
  and Take Ownership rebuilds the dashboard under a new id with ` 1`
  appended, so none of those is a delete path;
- unverified: the delete request carries no `X-Requested-With` header (the
  list request does) and `currentComponentInfo=TODO`. The same request
  works when the session owns the dashboards, so neither is known to matter.
  From an account that had never opened the UI, the first deletes answered
  the Struts error panel instead of JSON (cause not isolated), which the
  client raises on.

## The core wheel and the external migrator

`vcfcf_core` gains `naming.py` and behavior (the dashboard name error, the
widget-id basis). The external migrator imports only
`extractor._*_from_export_zip` and `supermetrics.crossref.crossref_names`
from it, both unchanged, so nothing there breaks. A `core-v*` tag is needed
only when the migrator should pick this change up.
