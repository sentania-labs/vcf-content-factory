
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository is a framework for **authoring and installing VCF Operations
content from natural-language requests**. The user describes what they
want — a super metric, a list view, a dashboard — and you translate it
into a valid YAML definition under this repo, validate it, and (when
given credentials) install it on a VCF Operations instance via the
Suite API or, where the API does not support direct install, package
it for manual import.

## Hard rules (do not violate)

1. **Source of truth is this folder.** Build super metrics using ONLY:
   - The DSL documented in `docs/vcf9/supermetrics.md` (extracted from
     the VCF 9 docs, pages 4171–4180: functions, operators, `where`
     clause, `isFresh`, resource-entry aliasing, ternary, depth rules,
     looping vs. single functions).
   - Valid metric keys and attribute names from
     `docs/vcf9/metrics-properties.md`.
   - The Suite API surface defined in `docs/operations-api.json` and
     the narrative in `docs/vrops-content-management.md`.
   - Existing examples under `supermetrics/`, `views/`, `dashboards/`.
   - Anything under `docs/` is fair game as valid/safe reference
     material — treat it as authoritative. Other extracted VCF 9
     sections live under `docs/vcf9/` (dashboards, views-reports,
     policies, alerts-actions, suite-api).

   Do **not** invent functions, operators, query parameters, attribute
   paths, or API endpoints. If something is not in the PDF, the OpenAPI
   spec, or an existing YAML, it does not exist for the purposes of this
   repo. When unsure, extract the relevant pages of the PDF and re-read
   them rather than guessing.

2. **Never fabricate metric/attribute names.** Metric keys
   (e.g. `cpu|usage_average`, `mem|host_contentionPct`) must come from
   one of: an existing YAML in `supermetrics/`, the PDF, or a name the
   user explicitly provided. If you need a metric you cannot ground in
   one of those sources, ask the user for the exact key — do not guess.

3. **Never write secrets to disk.** Credentials are passed via environment
   variables only (`VCFOPS_HOST`, `VCFOPS_USER`, `VCFOPS_PASSWORD`,
   optional `VCFOPS_AUTH_SOURCE`, `VCFOPS_VERIFY_SSL`). Do not put them
   in YAML, commit messages, or shell history echoes.

4. **Always validate before installing.** Run
   `python -m vcfops_supermetrics validate <file>` and fix any errors
   before calling `sync`.

## Repository layout

```
docs/
  operations-api.json            VCF Ops Suite API OpenAPI spec
  vrops-content-management.md    Extracted from Suite-API whitepaper
  vcf9/
    supermetrics.md              VCF 9 docs p.4171–4180 (DSL reference)
    metrics-properties.md        VCF 9 docs p.4242–4507 (metric key reference)
    dashboards.md                VCF 9 docs p.3921–4053
    views-reports.md             VCF 9 docs p.4137–4169
    policies.md                  VCF 9 docs p.3130–3155
    alerts-actions.md            VCF 9 docs p.3157–3270
    suite-api.md                 VCF 9 docs p.7968–7986
  (PDFs are gitignored — extract new ones to markdown, see below)
vcfops_supermetrics/             Python package (client, loader, CLI)
  client.py                      Suite API client + supermetric CRUD
  loader.py                      YAML schema + DSL validation
  cli.py / __main__.py           validate / list / sync / delete commands
supermetrics/                    YAML definitions, one per file
README.md                        Human-facing usage docs
requirements.txt                 requests, PyYAML
```

## Workflow when a user asks for a super metric

Follow these steps in order. Do not skip steps.

### 1. Clarify the request
Confirm enough to write a correct formula:
- **What object type** the metric is assigned to (Cluster, Host, VM,
  Datastore, etc.). This determines `depth`.
- **Which underlying metric(s)** to read, and on which object type.
- **Aggregation**: average, max, min, sum, count, combine.
- **Filters** (e.g. powered-on VMs only) — these become a `where` clause.
- **Units / display name**.

If the user gave a clear description (e.g. "average CPU of powered-on
VMs in a cluster"), do not over-clarify — proceed and show them the
result.

### 2. Author the YAML
Place the file under `supermetrics/<short_snake_case>.yaml` with this
shape (see existing files for examples):

```yaml
name: <ResourceKind> - <Human Name> (<unit>)
resource_kinds:
  - resource_kind_key: <ResourceKind>   # e.g. VirtualMachine, ClusterComputeResource, HostSystem, Datastore
    adapter_kind_key: VMWARE            # adapter that owns the resource kind
description: >
  One or two sentences: what it measures, which resource kind it is
  assigned to, and any non-obvious depth or filtering choice.
formula: |
  <DSL expression>
```

**`resource_kinds` is mandatory.** Every super metric YAML must include
a `resource_kinds:` list naming the VCF Operations resource kind(s) the
metric is calculated on. Use the exact VCF Ops nomenclature:
**`resource_kind_key`** (the resource kind, e.g. `VirtualMachine`,
`ClusterComputeResource`, `HostSystem`, `Datastore`) and
**`adapter_kind_key`** (the adapter that owns it, almost always
`VMWARE` for vSphere objects). These names match the wire field names
`resourceKindKey` / `adapterKindKey` exactly so YAML and JSON line up.

If the user does not specify a resource kind, **default to the resource
kind of interest** — the object whose behavior the metric describes
(a "VM snapshot" metric defaults to `VirtualMachine`, a "cluster CPU"
metric to `ClusterComputeResource`, etc.). When in doubt, ask.

The list form is intentional: the Suite API accepts multiple
`{resourceKindKey, adapterKindKey}` pairs per super metric, so a single
metric can be assigned to several resource kinds at once. Most metrics
use a single entry; only use multiple when the same formula genuinely
applies to more than one kind.

`resource_kinds` IS sent to the Suite API. The `/api/supermetrics`
create/update payload accepts a `resourceKinds` array of
`{resourceKindKey, adapterKindKey}` pairs even though the documented
OpenAPI schema in `operations-api.json` only lists
`id/name/formula/description/modificationTime`. The undocumented field
is real — verified against an exported super metric — and the loader
and client in this repo wire `resource_kinds` straight through to it.
This means `sync` alone is enough to assign the metric to its resource
kind; the post-sync UI step is now only "enable it in the relevant
policy".

DSL rules to apply (from the PDF, p.4171–4181):

- **Looping functions** (allowed): `avg`, `sum`, `min`, `max`, `count`,
  `combine`. They take a single resource entry.
- **Single functions** (allowed): `abs`, `acos`, `asin`, `atan`, `ceil`,
  `cos`, `cosh`, `exp`, `floor`, `log`, `log10`, `pow`, `rand`, `sin`,
  `sinh`, `sqrt`, `tan`, `tanh`.
- **Operators**: `+ - * / %`, `== != < <= > >=`, `&& || !`, ternary
  `cond ? a : b`, parentheses, `[x, y, z]` arrays.
- **String operators** (only in a `where` clause): `equals`, `contains`,
  `startsWith`, `endsWith`, and their `!` negations.
- **Resource entry forms**:
  - `${this, metric=group|name}` — bound to the assigned object.
  - `${adaptertype=ADAPT, objecttype=KIND, attribute=group|name, depth=N}`
    — iterate over related objects N hops away.
  - `${..., resourcename=NAME, identifiers={k=v,...}, metric=...}` — a
    specific named resource.
  - `objecttype=*` is allowed only with an explicit `adaptertype=` and
    means "all resource kinds for that adapter".
- **`depth`**: positive = children, negative = parents, **never 0**.
  Cannot cross sibling branches in one super metric (e.g. VM →
  Datastore Cluster requires two chained super metrics; see p.4173).
- **`where` clause**: filters by another metric **on the same object**;
  the right operand must be a literal number, not another super metric
  or variable. Use `$value` to refer to the entry's own value, e.g.
  `where=($value==1)`. Use `isFresh()` to require freshness:
  `where=($value.isFresh())`.
- **Aliasing**: `${...} as alias` lets you reuse a resource entry. The
  alias is case-insensitive, cannot start with a digit, cannot use
  `()[]+-*/%|&!=<>,.?:$`, and each name can be used at most once. See
  `supermetrics/datastore_vm_iops_ratio.yaml`.
- **Ternary**: `cond ? a : b`, e.g. `${this, metric=cpu|demandmhz} as a
  != 0 ? 1/a : -1`.

The loader (`vcfops_supermetrics/loader.py`) enforces a subset of these
rules. **The loader is not a full parser** — it catches obvious mistakes
but cannot certify semantic correctness. Treat a successful `validate`
as necessary but not sufficient; reread the formula yourself before
proposing to install it.

### 3. Validate locally
```bash
python -m vcfops_supermetrics validate supermetrics/<file>.yaml
```
Fix any error and re-run until clean. Do not edit the loader to make
a bad formula pass.

### 4. Show the user the result
Show them the YAML and the formula. Briefly explain your depth choice,
any `where` clause, and which object type they should assign it to in
the UI. Ask for confirmation before doing anything that touches their
VCF Ops instance.

### 5. Install (only when the user confirms and credentials are present)
Required env vars:
```
VCFOPS_HOST       hostname (no scheme)
VCFOPS_USER       username
VCFOPS_PASSWORD   password
VCFOPS_AUTH_SOURCE optional, default "Local"
VCFOPS_VERIFY_SSL optional, "false" to disable TLS verification
```
Then:
```bash
python -m vcfops_supermetrics sync supermetrics/<file>.yaml
```
`sync` upserts by `name`. Report the action (`created` / `updated`)
and the returned id back to the user.

### 6. Tell the user what `sync` cannot do
The Suite API endpoint `/api/supermetrics` only manages
`name / formula / description`. It does **not** assign the super metric
to an object type and does **not** enable it inside a policy. After
`sync`, instruct the user to:

1. Open **Infrastructure Operations → Configuration → Super Metrics**.
2. Open the new super metric and assign it to the intended object type
   (the one whose `depth` you wrote the formula against).
3. Open **Policies**, edit the relevant policy, and enable the super
   metric for that object type.

If the user asks you to automate steps 2–3, tell them the public
`/api/supermetrics` surface in `operations-api.json` does not expose
object-type assignment, and offer to investigate the policies endpoints
in the same spec instead of inventing one.

## Dashboards and view definitions

The repo also ships a `vcfops_dashboards/` package for authoring **list
views** and **dashboards** as YAML and packaging them in the
ZIP-in-ZIP layout VCF Operations uses for content import. The v1
scope is intentionally narrow:

- **View definitions**: list views only. Subject is a single
  `(adapter_kind, resource_kind)` pair. Columns are a flat list of
  `{attribute, display_name, unit?}`. Rendered as `content.xml`.
- **Dashboards**: two widget types — `ResourceList` (the object
  picker) and `View` (a saved view definition embed). Interactions are
  the `resourceId` pattern: a `ResourceList` provider drives one or
  more `View` receivers. Rendered as `dashboard/dashboard.json` plus
  empty i18n property bundles.

YAML lives under `views/` and `dashboards/`. UUIDs are derived from
content names via `uuid5` in a fixed namespace
(`vcfops_dashboards.loader.NS`) so re-syncing the same name updates
the existing entry rather than creating duplicates.

```bash
python -m vcfops_dashboards validate           # lint YAML
python -m vcfops_dashboards package -o out.zip # build the import ZIP
python -m vcfops_dashboards sync               # build + import
```

### Wire formats (learned by reverse engineering)

**View definition** — XML rooted at `<Content><Views><ViewDef id=…>`
with: `Title`, `Description`, two `SubjectType` elements (`type=self`
and `type=descendant`), `Usage` tags (`dashboard report details
content`), and a `Controls` block containing `time-interval-selector`,
`attributes-selector` (one `Item` per column with `attributeKey`,
`displayName`, optional `preferredUnitId`, etc.), `pagination-control`,
and `metadata`. `DataProviders/DataProvider dataType="list-view"` and
`Presentation type="list"` close it out.

**Dashboard** — JSON object with:
- `uuid` — package wrapper id
- `entries.resourceKind[]` — list mapping synthetic ids
  (`resourceKind:id:N_::_`) to real `{resourceKindKey, adapterKindKey}`
  pairs. Widget configs reference resource kinds by these synthetic
  ids, *not* by the real keys.
- `dashboards[]` — each entry has the per-dashboard metadata
  (`name`, `id`, `description`, `columnCount`, `gridsterMaxColumns`,
  `widgets`, `widgetInteractions`, etc.)
- Each widget has `id` (UUID), `type`, `title`, `gridsterCoords`
  (`{x,y,w,h}` on a 12-column grid), and a type-specific `config`.
- `widgetInteractions` is a list of
  `{widgetIdProvider, type: "resourceId", widgetIdReceiver}`.

A `View` widget references its view by `config.viewDefinitionId` —
which is exactly the id derived by the loader's `stable_id("view",
name)`, so dashboards and views in this repo wire up automatically as
long as the dashboard YAML's `view:` field matches the view's `name`.

### Import package layout (matches the export wire format)

```
outer.zip
├── <digits>L.v1                        # marker; content = owner user UUID
├── configuration.json                  # merged manifest for all content types
├── views.zip                           # nested: one content.xml with all ViewDefs
├── usermappings.json                   # owners referenced by dashboards/<id>
├── dashboards/<ownerUserId>            # nested: dashboard/dashboard.json holding
│                                       #   ALL owner's dashboards + i18n bundles
└── dashboardsharings/<ownerUserId>     # JSON list ([] = private to owner)
```

Three things the importer is picky about (learned the hard way;
earlier iterations sent a nested-per-item layout and got
`INVALID_FILE_FORMAT` on every attempt):

1. **The marker filename is a per-instance fingerprint.** Every export
   from one VCF Ops cluster uses the same `<19-digit>L.v1` name, and
   the importer rejects any other value — even an off-by-one is
   `INVALID_FILE_FORMAT`. The sync path discovers it by doing a
   throwaway `SUPER_METRICS` export and reading the marker name from
   the resulting zip (`vcfops_dashboards.client.discover_marker_filename`).
2. **Dashboards are grouped by owner user**, not per-dashboard. All of
   one user's dashboards live in a single nested zip named
   `dashboards/<ownerUserId>` whose inner `dashboard/dashboard.json`
   has a shared `entries.resourceKind[]` table and a `dashboards[]`
   array with every dashboard object. A matching `usermappings.json`
   at top level must reference the same owner id.
3. **The multipart field is `contentFile`** on
   `POST /api/content/operations/import`. `file` or raw
   `application/zip` request bodies return 500.

`python -m vcfops_dashboards sync` drives the full flow end-to-end
(discover marker → fetch current user → build zip → POST → poll on
operation id). No more UI-upload fallback.

## Useful commands

```bash
# Lint every YAML under supermetrics/
python -m vcfops_supermetrics validate

# Lint a single file
python -m vcfops_supermetrics validate supermetrics/cluster_avg_vm_cpu.yaml

# What is currently installed on the target instance
python -m vcfops_supermetrics list

# Push everything (idempotent upsert by name)
python -m vcfops_supermetrics sync

# Push one file
python -m vcfops_supermetrics sync supermetrics/<file>.yaml

# Remove by name
python -m vcfops_supermetrics delete "Cluster - Avg Powered-On VM CPU Usage (%)"
```

## Reading reference docs

Prefer the extracted markdown under `docs/vcf9/` and
`docs/vrops-content-management.md` — they're grep-friendly and
directly readable with the `Read` tool. The original PDFs are
gitignored because the VCF 9 PDF alone is ~148 MB / 8,285 pages and
exceeds GitHub's file-size limit.

**When a new PDF lands in the repo:** review it, identify the sections
relevant to VCF Operations content authoring, and extract them to
markdown under `docs/` (use `docs/vcf9/` for chapters of the main VCF
docs; put standalone whitepapers at `docs/<slug>.md`). Add each new
file to the `docs/` listing in the Repository Layout section above.
Extraction recipe:

```python
import pypdf
r = pypdf.PdfReader("<path/to.pdf>")
with open("docs/vcf9/<section>.md", "w") as f:
    f.write(f"# <section> (pages S-E)\n")
    for p in range(S-1, E):   # S, E are 1-indexed inclusive
        f.write(f"\n\n---\n## page {p+1}\n\n{r.pages[p].extract_text() or ''}")
```

After extracting, commit the markdown. Do NOT commit the PDF —
`*.pdf` is gitignored.

## Style

- Super metric **names** use Title Case, include the object scope and
  unit, e.g. `Cluster - Avg Powered-On VM CPU Usage (%)`. The name is
  the natural key for upserts; renaming a metric creates a new one and
  orphans the old.
- Keep one super metric per file. File name is short snake_case.
- `description` should explain *why* the metric exists and any
  non-obvious depth/where choice — future-you will thank you.
