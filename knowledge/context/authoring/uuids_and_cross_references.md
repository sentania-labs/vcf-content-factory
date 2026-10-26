# UUIDs are part of the contract

The central design constraint of this repo. Read this before touching
anything that creates or references content objects.

## The problem

- View definitions reference super metrics as literal `sm_<uuid>`
  strings in `attributeKey`. **No name-based lookup exists.**
- Dashboard widgets reference views by UUID (and, indirectly, the
  super metrics those views use).
- Super metric formulas cross-reference other super metrics as
  `${this, metric=Super Metric|sm_<uuid>}`.
- Therefore a repo-authored bundle (super metrics + views +
  dashboards) survives cross-instance installation only if every
  object lands with the **same UUID on every instance**.

### Where `@supermetric:"<name>"` gets resolved

Authors write the SM-to-SM reference by name, as
`@supermetric:"<exact name>"` inside the formula. VCF Ops cannot parse that
token; it must be rewritten to `Super Metric|sm_<uuid>` before the formula
reaches the platform. Resolution therefore happens at **emit/push time**, not
at load time: `SuperMetricDef.formula` still holds the authoring-time token
after `load_file()`, by design, so the YAML stays UUID-free and diffable.

The one resolver lives in `src/vcfcf_supermetrics/crossref.py`
(`resolve_sm_formula`). Every path that emits or pushes a formula calls it:

| Path | Call site | Name scope |
|---|---|---|
| Native bundle zip | `vcfcf_core.packaging.assembly._render_supermetrics_dict` | the bundle's own SMs |
| Discrete / release zip | same (via `discrete_builder`, `release_builder`) | component SMs, after `_expand_sm_crossrefs` pulls in referents |
| Live sync | `vcfcf_supermetrics.client.import_supermetrics_bundle` | the sync batch, then `find_by_name` against the target instance |
| Tier 2 pak | `vcfcf_managementpacks.sdk_builder._resolve_sm_formula` | `bundled_content.supermetrics` |

An unresolvable name is a **hard error** on every path. Emitting the literal
token produces a super metric the platform silently fails to evaluate, so
failing at build/push time is the cheaper failure. Resolution is idempotent:
an already-resolved `Super Metric|sm_<uuid>` is left alone.

**The token carries its own `Super Metric|` prefix.** It replaces the whole
wire term, so the correct authoring form is `metric=@supermetric:"<name>"`,
never `metric=Super Metric|@supermetric:"<name>"`. The hand-written prefix
used to emit `Super Metric|Super Metric|sm_<uuid>`, which VCF Ops cannot parse
and which no build step flagged (PR #141/#142). The regex now absorbs every
immediately-preceding `Super Metric|`, in any case and spacing and however many
of them there are (`super metric|`, `SUPER METRIC|`, `Super Metric| `,
`Super Metric|Super Metric|`), so both forms resolve to a single prefix, but the
second form is still wrong on the page. A doubled prefix that survives anyway
(hand-written with no token to absorb it) is a hard error on every emit path, so
it can never ship silently.

**Near-miss syntax is a hard error, not a passthrough.** `@supermetric: "X"`
(space after the colon) and `@supermetric:X` (unquoted) do not match the
token regex. Any literal `@supermetric` surviving substitution raises, in any
case spelling, because shipping it is the same corrupt-SM outcome as an
unresolvable name.

**The token itself is case-insensitive, like the prefix.**
`@SuperMetric:"X"` and `@SUPERMETRIC:"X"` resolve exactly as `@supermetric:"X"`
does. They used to pass straight through: the resolver matched the token
case-sensitively, and `vcfcf_core.packaging.deps._is_sm_ref` lowercases before
comparing, so the dependency audit classified a mis-cased token as an
already-good SM reference and skipped it. Audit green, build green, literal
token in the zip (PR #141 round 3). Only the *token* is forgiving: the
referenced SM **name** in the quotes is still matched exactly.

**`validate` proves nothing here.** The SM loader has no `@supermetric`
awareness at all, by design (the formula stays in authoring form). The only
real check on a cross-reference is building the bundle / pak and reading the
emitted `supermetric.json`.

The reverse direction (`vcfcf_core.supermetrics.reverse.rewrite_formula`,
`vcfcf_extractor`) turns `sm_<uuid>` back into `@supermetric:"<name>"` so
extracted content round-trips through the authoring form.

## Why `POST /api/supermetrics` is a dead end

The public create endpoint rejects caller-supplied `id`:

```
POST /api/supermetrics  →  400 "must be null"
```

Confirmed empirically against the lab. Server assigns a fresh random
UUID every time. That's incompatible with bundle portability.

## The scheme

**Store a random UUIDv4 in the YAML** at authoring time, reuse it
forever.

```yaml
id: 76801377-1807-4a46-93d4-9b9dc0f0c54b   # generated once, never touched
name: [VCF Content Factory] Cluster - Avg Powered-On VM CPU Usage (%)
```

- The loader generates a `uuid4()` and writes it back on first
  `validate` if the `id` field is missing. Subsequent runs reuse it.
- Rename-safe: changing `name` does not change `id`, so cross-refs
  survive authoring iteration.
- Matches the pattern the sentania/AriaOperationsContent bundles
  already use — the `supermetric.json` files there are keyed by
  hand-picked v4 UUIDs, for the same reason.
- No namespace bookkeeping, no "derive from name" magic, no collision
  surface between authors.

## The install path

Install flows through `POST /api/content/operations/import` with a
zip whose `supermetrics.json` is keyed by the YAML's `id`. Ops stores
the UUID verbatim — verified round-trip: derived a custom UUID, built
a content zip with it, imported, listed, UUID matched byte-for-byte.

See `context/wire_formats.md` for the exact zip layout and
`context/install_and_enable.md` for the CLI flow.

## Cross-references in authoring

Because UUIDs live in the YAML, the loader can resolve references by
name at load time without round-tripping to the server:

- **Views/dashboards referencing a super metric**: YAML uses
  `attribute: supermetric:"<name>"`; the renderer looks up the super
  metric YAML by name, reads its `id`, emits `sm_<id>`. The name is
  scoped to the view's content set (issue #270), see below.
- **Super metric formulas referencing another super metric**: YAML
  uses `@supermetric:"<name>"` inside the formula string. This one is
  **not** resolved at validate time: it is rewritten to
  `Super Metric|sm_<id>` at emit/push time by
  `vcfcf_supermetrics.crossref` (see the section above), which fails
  loudly if the referenced name doesn't resolve.

### Which super metric a `supermetric:"<name>"` column means

Display names are unique inside one content set, not across sets: the
factory's `content/`, each `third_party/<project>/`, and each
`content/sdk-adapters/<pak>/` is its own set (a pak sits under `content/`
but is keyed by its path, not by its `"factory"` provenance). A column
resolves in this order (issue #270):

1. the view's own content set;
2. then the factory set (`content/supermetrics`), so a third-party or pak
   view may name a factory SM;
3. otherwise the column is an error. Another third-party project's SMs are
   never in reach.

Every failure is loud, before anything is imported or written: an
unresolved name; two different SMs of that name in the set that answers
(ambiguous); a set whose SM YAML did not load (no silent fall-through to a
same-named factory SM); an SM whose YAML has no `id` yet (run validate to
mint one).

Where each path gets its SMs:

- `vcfcf_dashboards package` / `sync` and the bundle views/dashboards
  handlers: the corpus is `--supermetrics-dir` (default
  `content/supermetrics`), `content/supermetrics`, every
  `third_party/*/supermetrics` and every `content/sdk-adapters/*/supermetrics`,
  loaded read-only (`vcfcf_dashboards.sm_columns`). One resolver
  (`vcfcf_core.supermetrics.column_resolver.SmColumnResolver`) feeds the
  renderer, the pre-import referent check (#154) and the post-import
  walker, so the three cannot disagree.
- Bundle and discrete builds: the bundle's own SM list (`sm_id_map` over
  `bundle.sm_paths`); two different SMs of one name in that list are an
  error.
- SDK pak builds and `validate-sdk`: only the pak's
  `bundled_content.supermetrics`, an empty scope when it bundles none; a
  column naming any other SM fails the build (no fallback to
  `content/supermetrics`, which the pak does not ship).

The post-import walker (`walk_and_check`, `vcfcf_dashboards sync`) treats a
name-form column as a super metric reference (issue #266): it is bound
through the same resolver and checked and enabled on the Default Policy
like an `sm_<uuid>` column, and it is never sent to the describe endpoint as
an OOTB metric. A name the repo does not know is looked up on the target by
name. Bundle and pak installers (`install.py`, `install.ps1`, the pak
installer) do not walk columns: the shipped view XML already carries
`sm_<uuid>`, and the bundle's own SMs are enabled from its manifest.

## Cross-reference syntax quick reference

Every content type uses name-based references in YAML. The loader
for each type resolves names to UUIDs (or server-assigned IDs) at
validate or sync time.

| From → To | YAML syntax | Loader output | When resolved |
|---|---|---|---|
| SM formula → other SM | `@supermetric:"<exact name>"` | `Super Metric|sm_<uuid>` | **emit/push** (`crossref`), not `validate` |
| View column → SM | `supermetric:"<exact name>"` in `attribute:` | `sm_<uuid>` in `attributeKey` | render (package / sync / build), scoped to the view's content set then the factory (see above) |
| Dashboard widget → View | `view: "<exact view name>"` | view UUID in widget config | `validate` (dashboard loader) |
| Dashboard widget → Dashboard (drill-down) | `navigations: [{dashboard: "<exact dashboard name>", widgets: [<target local ids>]}]` | `dashboardNavigations`: target dashboard UUID plus target widget UUIDs | `validate` (dashboards CLI, against `content/dashboards/` + `third_party/*/dashboards/`) and render; a bundle must carry every target. Raw `dashboard_id: <uuid>` only for dashboards the factory does not own. See `../wire-formats/dashboard_navigations.md` |
| Alert → Symptom | `name: "<exact symptom name>"` in symptom set | symptom definition ID | `sync` (alert installer, via `GET /api/symptomdefinitions`) |

**Rules:**
- Names must match exactly (case-sensitive, prefix included).
- SM/view/dashboard references resolve at validate time from local
  YAML — the referenced object must exist in the repo.
- Alert → symptom references resolve at sync time from the live
  instance — symptoms must be synced before alerts.

## Orphan and rename handling

Under the new scheme renaming a YAML keeps the same `id`, so the
orphan problem is much smaller than before. But deleting a YAML
leaves the corresponding super metric on the server until someone
cleans it up. Plan: an `orphans` CLI that lists server-side objects
whose UUID doesn't match any current YAML, so operators can prune.
