# Administrator Guide

This is a walkthrough of how the VCF Content Factory works — the
moving parts, the reasoning behind them, and the VCF Operations
concepts it touches. The framework is built so an average vSphere
admin can drive it by describing what they want in English, but
that's a thin veneer over real mechanics, and the mechanics are
worth understanding. Don't use a button until you know what the
button is doing.

## 1. What VCF Operations content actually is

Before the framework can help you, it's worth being clear about the
four building blocks we're producing. Each one is a first-class
object in VCF Operations with its own API, its own lifecycle, and
its own wire format.

### Super metrics

A **super metric** is a named formula that VCF Operations evaluates
against resources on a schedule. The formula is written in a DSL
with a few common shapes:

- *Aggregate children*: walk from an assigned container resource
  down to some descendant kind and roll up a metric.
- *Compare against a property*: filter that walk with a `where`
  clause.
- *Reference another super metric*: divide one rollup by another
  to get a ratio.

A super metric doesn't live anywhere by default. You *assign* it to
one or more **resource kinds** (e.g. `ClusterComputeResource`,
`Datacenter`, `VMwareAdapter Instance`) and then *enable* it on a
**policy** (almost always the Default Policy). Only after both
steps does Ops start collecting it.

The critical insight: one formula can be assigned to multiple
container levels at once, and Ops will compute a rollup at each
level independently. A formula like "sum provisioned vCPU across
descendant VMs" assigned to `ClusterComputeResource + Datacenter +
VMwareAdapter Instance` gives you per-cluster, per-datacenter, and
per-vCenter numbers for free. This is the idiom the framework
reaches for whenever a report needs "the same thing at different
scopes."

### Custom groups

A **custom group** is a named, dynamic set of resources defined by
a rule. Unlike a super metric, a custom group is itself a resource
in Ops — it has an ID, it appears in the inventory, and it can be
the target of views, alerts, and permissions. The rule can combine
property conditions, relationship conditions (ancestor/descendant
on specific parents), and static inclusions/exclusions.

Custom groups are the right tool when you need to **name a set of
things humans care about** — "VMs on NFS datastores", "production
clusters", "Tanzu worker nodes". They're the wrong tool when you
just need to filter inside a super metric formula; for that, use a
`where` clause. The framework will nudge you toward the lighter
tool when you're overreaching for groups.

### List views

A **list view** is a tabular report. Pick a subject resource kind
(e.g. `VMwareAdapter Instance`), pick a set of columns (each one
is a built-in metric, a property, or a super metric reference),
and Ops renders a table with one row per instance of that kind.

Views run two ways:

1. **Standalone**, from the Environment → Views menu, where Ops
   enumerates every resource of the subject kind in the instance.
2. **Embedded in a dashboard**, where the widget hosting the view
   must either be fed a resource by an interaction (e.g. a picker
   widget) or be configured as a *self-provider* pinned to a
   container resource whose descendants the view walks.

Most of the dashboard-rendering bugs you'll hit are actually list-
view widget configuration issues, not view problems.

### Dashboards

A **dashboard** is a layout of widgets with interactions between
them. In this framework's scope today, we build dashboards from two
widget types: `ResourceList` (an object picker) and `View` (a
saved view embed). Dashboards can live in **folders** in the Ops
sidebar, can be **shared** with other users, and carry per-widget
state like pinned resources.

Dashboards are stored inside Ops grouped by their owning user —
every user has a single "dashboards/<ownerUserId>" bundle
containing all their dashboards, not one file per dashboard. That
quirk matters when you think about install semantics.

## 2. How content gets installed

VCF Operations exposes two fundamentally different install paths
for content, and the framework picks one per content type for very
specific reasons.

### The content-import ZIP path

Used for **super metrics, views, and dashboards**.

You build a ZIP with a specific layout:

```
outer.zip
├── <19-digit>L.v1           # marker, contents = owner user UUID
├── configuration.json       # metadata about what's inside
└── supermetrics.json        # or dashboards/<ownerUserId>, or views.zip
```

You POST the ZIP to `/api/content/operations/import` with
`?force=true`, poll until the import finishes, and read the
`operationSummaries` to see what landed, what got skipped, and what
failed.

**Why this path over the simpler `POST /api/supermetrics`:**
`POST /api/supermetrics` rejects any caller-supplied `id` with
`400 "must be null"` — the server assigns a fresh random UUID
every time. That's fatal for a content bundle, because views
reference super metrics by literal `sm_<uuid>` strings. If the
same bundle installs with different UUIDs on different instances,
every cross-reference breaks. The content-import path preserves
caller-supplied UUIDs verbatim, which is the only way a bundle
portable across dev/test/prod.

### The direct REST path

Used for **custom groups**.

Custom groups go through `POST /api/resources/groups` (and `PUT`
for updates). They don't ride the content-import ZIP — there's no
`customgroups.json` inside any content ZIP exported by Ops, and
no internal endpoint wires custom groups into that path. The
framework's `vcfops_customgroups` package talks to the REST API
directly.

The implication: custom groups are identified by **name**, not by
UUID. Ops assigns the ID server-side at create time. Rename a
custom group and you create a new one; the old one lingers until
you delete it. The framework treats this as a hard carve-out from
the "UUID in YAML" rule that governs everything else.

### What that means in practice

- You can bundle super metrics + views + dashboards into a single
  content-import zip and install them atomically.
- Custom groups have to be installed first, separately, by their
  own CLI.
- For a cross-instance bundle (dev → prod), super metrics, views,
  and dashboards round-trip with their UUIDs intact. Custom groups
  get re-created on the destination under the same name.

## 3. The UUID contract

This is the most important concept in the framework. If you take
nothing else away, take this.

**Every super metric, view, and dashboard in this repo has a stable
uuid4 stored in its YAML's `id:` field.** The loader generates it
on first `validate` and never touches it again. Renaming the YAML
file, renaming the display name, changing the formula — none of
those change the `id`. That's the whole point: the `id` is the
stable identity across renames, across instances, and across
cross-references.

Why it matters:

- **Views reference super metrics** as `sm_<uuid>` column attributes.
- **Dashboards reference views** as `viewDefinitionId` pointers.
- **Super metric formulas** can reference other super metrics as
  `${this, metric=Super Metric|sm_<uuid>}`.

If a UUID drifts, every reference to it turns into a blank column
or a "view not found" error. The framework's job is to make sure
that never happens: the loader preserves UUIDs in YAML, the
content-import path preserves them on the wire, and the install
operation upserts in place rather than creating duplicates.

**When you're tempted to hand-edit a UUID, stop.** Either something
went wrong (and hand-editing will make it worse) or you're about to
break every reference that points at that object across the repo.

Custom groups are, as mentioned, the exception — their identity is
`resourceKey.name` because Ops assigns the UUID server-side and
there's no way to override it.

## 4. Recon → author → install, in detail

The framework runs a strict pipeline every time you ask for
content. Understanding the pipeline helps you understand why it
sometimes asks you questions, why it sometimes refuses, and why it
sometimes announces "this already exists on your instance."

### Step 1 — Reconnaissance

Before any authoring happens, an `ops-recon` subagent runs against
the live VCF Operations instance in read-only mode. It answers:

- **Does a built-in metric already cover this?** Ops ships with
  thousands of metrics and properties. If one of them already gives
  you what you want, there's no reason to author a super metric.
- **Does existing content already match?** Recon checks the instance
  for existing super metrics and views by name, then checks the
  repo's YAML files, then checks the allowlisted external reference
  libraries cached under `references/`.
- **What are the exact metric key spellings?** Property keys and
  stat keys are case-sensitive, underscore-sensitive, and unforgiving.
  `config|hardware|num_Cpu` is right; `config|hardware|numCpu` is
  the property-layer form of the same value and silently no-datas
  when used as a metric target.
- **Where in the hierarchy does the target live?** For a rollup,
  the framework needs to know which parent containers the target
  resource has and at what depth.

Recon output is the ground truth the authoring agents work from.
An authoring agent that's been given recon results writes grounded
YAML; an authoring agent without them refuses to proceed.

### Step 2 — Authoring

One authoring agent per content type:

- `supermetric-author` writes to `supermetrics/`
- `customgroup-author` writes to `customgroups/`
- `view-author` writes to `views/`
- `dashboard-author` writes to `dashboards/`

Each agent has a narrow scope and a list of hard rules it can't
break. None of them invent metric keys, API endpoints, or DSL
functions. When an agent needs something the recon output didn't
provide, it stops and asks the orchestrator for it.

For compound requests ("make me a super metric, a view, and a
dashboard"), the orchestrator runs the agents **bottom up**:
custom groups first (if needed), then super metrics, then views,
then dashboards. Each layer reads the previous layer's YAML from
disk — cross-references are resolved by name at author time and
rewritten to UUIDs by the loader at validate time. Order matters
because the view agent can't write `sm_<uuid>` for a super metric
that hasn't been authored yet.

### Step 3 — Validation

After each author run, the orchestrator runs `validate` across the
whole repo:

- `python -m vcfops_supermetrics validate`
- `python -m vcfops_dashboards validate`
- `python -m vcfops_customgroups validate`

Validation is lightweight but load-bearing. It mints any missing
UUIDs into the YAML files, lints the DSL for obvious mistakes, and
resolves cross-references. A failed validation stops the pipeline.

### Step 4 — Approval

You get to see the YAML and a summary of what's about to land
before anything touches the Ops instance. Approve, redirect, or
abandon.

### Step 5 — Install

The orchestrator runs the sync commands directly, not through an
agent, so every install call is visible to you in the transcript.
Super metrics and dashboards use the content-import ZIP path;
custom groups use the direct REST path. After install, super
metrics are enabled on the Default Policy automatically — a super
metric that's installed but not enabled produces no data.

## 5. The gotchas, and why they exist

These are the landmines that caught the framework's authors on the
way to getting this working. Knowing about them is the difference
between "it works" and "why is this dashboard blank."

### Super metric `where` clause shape

The DSL docs suggest several ways to express filters. Only one
works. The canonical form is:

```
where="summary|config|type equals VMOperator"
```

That's a **bare quoted string**. No nested `${}` around the key.
No single quotes around the literal. Key on the left, operator in
the middle, literal on the right. Property keys and stat keys are
both valid `metric=` targets and `where` clause keys; Ops doesn't
distinguish at this level.

Early attempts at `where=(${metric=key} equals 'literal')` or
`where="key equals 'literal'"` install cleanly — the importer
accepts them — but silently fail to produce data at eval time.
This is one of several examples of Ops accepting broken content
without a diagnostic, which is why the framework codifies the
correct shape into the agent prompts rather than trusting
validation alone.

### Metric key spelling

Two traps, both silent-no-data failures:

- `num_Cpu` (stat layer, underscore, capital C) vs `numCpu`
  (property layer, camelCase) — same logical value, but only the
  first is a valid `metric=` target in a formula.
- `num_CpuCores` (stat layer) vs `numCpuCores` (property layer) —
  same pattern on HostSystem.

The framework's `ops-recon` verifies metric keys against live
resources before authoring, which catches most of these. When you
see a super metric that installed but reports zero, metric key
spelling is the first thing to check.

### View super metric column attribute prefix

List view columns reference super metrics by a namespaced
attributeKey string: `Super Metric|sm_<uuid>`. Bare `sm_<uuid>`
installs cleanly but renders as a blank column with no error. Also,
super metric columns use `rollUpType=NONE`, not `AVG`.

YAML authors write the bare `sm_<uuid>` form in `attribute:` — the
view renderer in `vcfops_dashboards/render.py` auto-prefixes it
when building the XML. If you ever hand-edit view XML, know that
the `Super Metric|` prefix is mandatory.

### Self-provider dashboard widgets

A dashboard View widget that has no incoming interaction (no picker
feeding it a resource) must be configured as *self-provider* AND
pinned to a container resource whose descendants Ops will walk. For
VMWARE-subject views, the canonical pin is `vSphere World / VMWARE`
— the top-level singleton under which every vCenter lives.

The widget YAML declares this:

```yaml
widgets:
  - id: vks_core_view
    type: View
    view: "[VCF Content Factory] VKS Core Consumption by vCenter"
    self_provider: true
    pin:
      adapter_kind: VMWARE
      resource_kind: vSphere World
```

A self-provider widget without a pin — or with a pin to a resource
kind Ops doesn't recognize — renders "Select the widget source with
an interaction or through the self-provider configuration." Very
easy to miss unless you're looking for it.

### `resourceKindId` prefix

The pinned-resource configuration inside a self-provider widget
includes a field like `resourceKindId: "002006VMWAREvSphere World"`.
The `002006` is a 6-digit **per-adapter-kind stable identifier**,
not a dashboard-local index. There's no API to derive it. The
framework has a hard-coded table of known prefixes in
`vcfops_dashboards/render.py::_ADAPTER_KIND_PREFIX`, harvested from
reference bundles:

| Adapter kind | Prefix |
|---|---|
| `VMWARE` | `002006` |
| `Container` | `002009` |
| `CASAdapter` | `002010` |
| `NSXTAdapter` | `002011` |
| `KubernetesAdapter` | `002017` |
| `VMWARE_INFRA_HEALTH` | `002019` |

An incorrect prefix (a zero-padded local index, for example)
installs cleanly and fails silently. When a dashboard renders blank
for no obvious reason, the prefix is the second thing to check
after the super metric column prefix.

### Dashboard folders (`namePath`)

Dashboards live in the Ops sidebar under folders. The wire format
for folder placement is: the dashboard's `name` field is rendered
as `"<folder>/<display name>"` AND the `namePath` field is set to
`<folder>`. Setting `namePath` alone without the slash prefix in
`name` does NOT place the dashboard in a folder — Ops ignores
`namePath` in that form.

Dashboard YAML authors just set `name_path: VCF Content Factory`
(or accept the default). The renderer handles the slash-in-name +
`namePath` duality.

### `shared: true` for dashboards

The Ops content importer defaults new dashboards to `shared: false`
— visible only to the user who imported them. For a framework whose
whole purpose is to share knowledge with other admins, that default
is wrong. The framework overrides it to `shared: true` unless you
explicitly ask otherwise.

### Content-task contention (`1523 Task is already running`)

The Ops content import/export endpoints share a single task slot.
Back-to-back imports (e.g. super metrics followed immediately by
dashboards) can hit a `403 apiErrorCode 1523 Task is already
running` even when `GET /api/content/operations/{import,export}`
reports `state: FINISHED`. The lock releases a few seconds after
the task reports finished. The fix is a sleep + retry.

## 6. Reading the repo

Once you've got the concepts, the repo is short enough to read end
to end:

```
supermetrics/              Super metric YAML source of truth
customgroups/              Custom group YAML source of truth
views/                     List view YAML source of truth
dashboards/                Dashboard YAML source of truth

vcfops_supermetrics/       Super metric Python package
  loader.py                YAML → model, uuid4 mint, DSL lint
  client.py                Suite API client, content-zip import
  cli.py                   `python -m vcfops_supermetrics ...`

vcfops_dashboards/         Views + dashboards Python package
  loader.py                YAML → models, uuid4 mint
  render.py                Models → view XML + dashboard JSON
  client.py                Content-zip import (shared helpers)
  cli.py                   `python -m vcfops_dashboards ...`

vcfops_customgroups/       Custom groups Python package
  loader.py                YAML → models
  client.py                /api/resources/groups REST client
  cli.py                   `python -m vcfops_customgroups ...`

context/                   Topical background the agents read on demand
  supermetric_authoring.md DSL reference, idioms, anti-patterns
  wire_formats.md          Content-zip wire formats for each type
  uuids_and_cross_references.md  The UUID contract
  internal_supermetrics_assign.md  Default Policy enable endpoint
  customgroup_authoring.md DSL + rule grammar
  customgroup_relationship_grammar.md  ANCESTOR/DESCENDANT rules
  content_api_surface.md   Public + internal + content-zip API map
  install_and_enable.md    Install flow + policy enablement
  reference_sources.md     Allowlisted external reference repos
  reference_docs.md        PDF extraction + VCF 9 doc inventory

.claude/agents/            Subagent prompts
  ops-recon.md             Read-only reconnaissance
  supermetric-author.md    Super metric authoring rules
  customgroup-author.md    Custom group authoring rules
  view-author.md           View authoring rules
  dashboard-author.md      Dashboard authoring rules
  api-explorer.md          Undocumented wire format investigator

docs/                      Source material the framework trusts
  vcf9/                    Extracted VCF 9 documentation markdown
  operations-api.json      Public Suite API OpenAPI spec
  internal-api.json        Internal (unsupported) API OpenAPI spec

references/                Allowlisted external reference content (clones)
CLAUDE.md                  Hard rules every agent obeys
```

Every YAML file is readable. Every Python module is under ~300
lines. If you want to know what the framework is doing, read the
loader for the content type you care about — it's short, and the
validation rules are right there.

## 7. Using the CLIs directly

The framework drives the CLIs for you during authoring. You can
also drive them yourself — for inspection, for manual installs, or
for recovery.

```bash
# --- super metrics ---
python -m vcfops_supermetrics validate
python -m vcfops_supermetrics validate supermetrics/vks_cores.yaml
python -m vcfops_supermetrics list
python -m vcfops_supermetrics sync
python -m vcfops_supermetrics sync supermetrics/vks_cores.yaml
python -m vcfops_supermetrics enable supermetrics/vks_cores.yaml
python -m vcfops_supermetrics delete "[VCF Content Factory] VKS Cores (count)"

# --- views + dashboards ---
python -m vcfops_dashboards validate
python -m vcfops_dashboards sync

# --- custom groups ---
python -m vcfops_customgroups validate
python -m vcfops_customgroups list
python -m vcfops_customgroups list-types
python -m vcfops_customgroups sync
python -m vcfops_customgroups delete "[VCF Content Factory] VMs on NFS"
```

Credentials are read from a `.env` file at the repo root. The
Python clients auto-load it, so you never need to shell-source
anything:

```bash
VCFOPS_HOST=vcfops.example.com
VCFOPS_USER=admin
VCFOPS_PASSWORD=secret
VCFOPS_AUTH_SOURCE=Local        # optional
VCFOPS_VERIFY_SSL=false         # optional, for self-signed
```

## 8. When to reach for the framework, and when not to

The framework is a good fit when:

- The thing you want involves a formula, a cross-reference, or a
  rollup across multiple scopes.
- The thing you want will benefit from being version-controlled,
  cross-instance portable, and reviewable.
- You want the result to outlive the one conversation in which it
  was built.
- Multiple admins on your team will use or maintain it.

The framework is overkill when:

- You're doing a one-off exploration in the GUI to answer a
  question once.
- You need something the framework doesn't support yet (alert
  definitions, report definitions — see the README's scope table).
- You already have a working bundle and just need to tweak a single
  threshold in the Default Policy — do that in the GUI.

## 9. Now you can open the GUI

With the concepts in hand, the Ops UI is your inspection and
debugging surface for content the framework authored:

- **Dashboards sidebar → `VCF Content Factory` folder**: confirm
  new dashboards landed in the right folder with the right name.
  Click one — does the view render rows? Are the columns populated
  or dashes?
- **Environment → Views**: find the view by name, run it
  standalone. A view that works standalone but renders blank in
  its dashboard is almost always a widget pin or `resourceKindId`
  issue; a view that's blank both ways is a column-attribute issue
  or a metric-key-spelling issue.
- **Administration → Configuration → Super Metrics**: find the
  super metric by name. Check the formula is what you expected.
  Click into the assignments — is it assigned to the resource
  kinds you want?
- **Administration → Policies → Default Policy → Metrics**: find
  the super metric. Is it enabled on the resource kinds you
  assigned? An installed-but-unenabled super metric produces zero
  data with no error.
- **Environment → Custom Groups**: find the group. Click into it.
  Does the member list look right? If not, the rule isn't matching
  the resources you expected — fix the YAML and re-sync.

Treat the GUI as **read-only** for content the framework authored.
Edits you make in the GUI will be overwritten by the next `sync`,
and they won't round-trip back into the YAML. If you want to change
something the framework authored, change the YAML and re-sync.

The exception: **tuning `shared` or the dashboard folder via the
GUI is fine** if you're experimenting. Just know that a re-sync
will reset those fields to whatever the YAML says.

## 10. Extending the framework

When you find a new DSL quirk, a new wire format detail, or a new
pattern that should be the default, the right move is to **codify
it into the prompts, the loader, and the memory**, not to fix it as
a one-off. The framework's purpose is to encode the expert's
knowledge so the next admin to use it doesn't need to learn the
same lessons.

- New DSL pattern → `context/supermetric_authoring.md` plus
  `.claude/agents/supermetric-author.md`.
- New wire format detail → `context/wire_formats.md` plus the
  relevant loader/renderer in `vcfops_*/`.
- New "do this, not that" correction → a memory note under
  `~/.claude/projects/.../memory/` so future Claude Code sessions
  start already knowing.

The goal is that every time an admin hits a landmine, the fix
propagates into the framework itself, not just into one
conversation. Over time the framework should get smarter and the
landmines should get rarer. That's the whole point.
