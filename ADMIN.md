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
building blocks we're producing. Each one is a first-class object
in VCF Operations with its own API, its own lifecycle, and its own
wire format. The framework supports eight content types today:
super metrics, custom groups, list views, dashboards, symptoms,
alert definitions, report definitions, and recommendations.

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
them. The framework supports 10 widget types covering ~94% of
observed live usage:

| Widget type | Purpose |
|---|---|
| `View` | Embedded saved view — the workhorse |
| `ResourceList` | Object picker that feeds other widgets via interaction |
| `TextDisplay` | Static markdown panel (titles, instructions, links) |
| `Scoreboard` | Single-value metric callout with thresholds |
| `MetricChart` | Time-series line / area chart for metrics |
| `HealthChart` | Health-state over time |
| `ParetoAnalysis` | Ranked bar chart for top-N analysis |
| `Heatmap` | Colored grid for at-a-glance correlation |
| `AlertList` | Currently-active alerts for a resource set |
| `ProblemAlertsList` | Filtered alerts view (problem badges only) |

`PropertyList` is the highest-value remaining gap — see
`context/widget_renderer_scope.md` for the next implementation
wave. Dashboards can live in **folders** in the Ops sidebar, can be
**shared** with other users, and carry per-widget state like
pinned resources.

Dashboards are stored inside Ops grouped by their owning user —
every user has a single "dashboards/<ownerUserId>" bundle
containing all their dashboards, not one file per dashboard. That
quirk matters when you think about install semantics. It also
means content-zip-imported dashboards are owned by the `admin`
account regardless of who ran the import, and only the `admin`
UI session can delete them later.

### Symptoms

A **symptom** is a single condition evaluated against a resource —
"CPU utilization > 90%", "a specific event type was logged",
"property X changed to value Y". Symptoms don't fire anything on
their own; they're the building blocks for alerts.

Symptom conditions come in a few flavors:

- **Metric (static threshold)**: `metric >= value`, where `value`
  is a fixed number. Comparison operator is one of `>`, `>=`, `<`,
  `<=`, `=`, `!=`.
- **Metric (dynamic threshold)**: value is derived from the metric's
  own historical behavior (baseline deviation).
- **Property**: exact-match comparison on a resource property.
- **Event**: filter on message-event severity/category/message
  regex, used for alerts that fire on specific log events.

Each symptom has a severity (`INFORMATION`, `WARNING`, `IMMEDIATE`,
`CRITICAL`) and a `waitCycle` / `cancelCycle` pair that controls how
long the condition must hold before the symptom triggers and how
long it must clear before the symptom resets. Symptoms are
identified by **name**, not UUID — their server IDs are assigned
at create time via the REST API.

### Alert definitions

An **alert definition** combines one or more symptoms into a
triggering rule, decorates it with an impact badge (`HEALTH`,
`RISK`, `EFFICIENCY`), and optionally attaches remediation
recommendations. The symptom set structure supports nested
AND/OR composition — "fire if (symptom A AND symptom B) OR
symptom C".

Criticality can be static (`WARNING`, `IMMEDIATE`, `CRITICAL`,
`AUTO`) or `SYMPTOM_BASED`, where the highest active symptom's
severity drives the alert's criticality. The latter is the right
choice when you want tiered severity from a single alert — e.g. a
"VM CPU Utilization" alert with three symptoms at 50%/75%/95%
thresholds that surfaces whichever bucket is currently triggered.

Alerts install via REST (`POST /api/alertdefinitions`) and are
identified by name. Recommendations are referenced by name +
priority; the framework's loader resolves them at validate time
and the content-zip `AlertContent.xml` bundle carries the
relationship on disk.

### Report definitions

A **report definition** is a scheduled PDF/CSV export structured
as a series of pages. Each page can be a cover page, a table of
contents, an embedded view, or an embedded dashboard. The
framework's `report-author` agent renders the full XML wire
format; the importer round-trips report UUIDs via content-zip
like dashboards do. Delete is via Ext.Direct
`reportServiceController.deleteReportDefinitions` with the same
nested-JSON-string data shape as view delete (see
`context/dashboard_delete_api.md`).

### Recommendations

A **recommendation** is a reusable remediation-instruction block
that alerts reference by name. One recommendation can be attached
to multiple alerts (e.g. a "check host CPU contention" block that
applies to several VM and host CPU alerts). The description text
appears in the VCF Ops UI's alert-detail "Recommendations" panel.

Recommendations live as standalone YAML under `recommendations/`
and get deterministic IDs derived from the name + `adapter_kind`
(`Recommendation-df-<adapter>-<slug>`). The framework's
`alert-author` agent handles both authoring new recommendations
and referencing existing ones — the "reuse first, author only
if nothing fits" pattern.

## 2. How content gets installed

VCF Operations exposes two fundamentally different install paths
for content, and the framework picks one per content type for very
specific reasons.

### The content-import ZIP path

Used for **super metrics, views, dashboards, and reports**.

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

Used for **custom groups, symptoms, and alert definitions**.

- Custom groups: `POST /api/resources/groups` (and `PUT` for
  updates). `vcfops_customgroups` package.
- Symptoms: `POST /api/symptomdefinitions` (and `PUT` for updates).
  `vcfops_symptoms` package.
- Alerts: `POST /api/alertdefinitions` (and `PUT` for updates).
  `vcfops_alerts` package. Alerts reference symptoms by
  server-assigned symptom IDs, so the installer resolves symptom
  names → IDs at install time.

None of these ride the content-import ZIP — their content types
aren't wired into the content-zip importer's resolvers. The
framework's install scripts use the REST endpoints directly.

The implication: these three types are identified by **name**, not
UUID. Ops assigns the ID server-side at create time. Rename one
and you create a new one; the old one lingers until you delete it.
The framework treats this as a hard carve-out from the "UUID in
YAML" rule that governs the content-zip-path content types.

### Known gap: recommendations via REST

Recommendations are a fully-authored content type in the framework,
and they serialize correctly into the `AlertContent.xml` drag-drop
drop-in file. However, the `_install_alerts` REST path
(`POST /api/alertdefinitions`) doesn't include recommendation
references in the alert wire body. Recommendations render
correctly in the drag-drop path (admins hand-importing
`AlertContent.xml` into the UI) but the REST install path silently
drops them.

Fix path: either verify a `POST /api/recommendations` endpoint
exists (api-explorer task) and wire it into `_install_alerts`
before the alert POST, or switch alerts to content-zip envelope
install matching how reports work. Deferred to a follow-up
session; see `context/qa_log.md` for the session history.

### What that means in practice

- You can bundle super metrics + views + dashboards + reports into
  a single content-import zip and install them atomically with
  UUIDs preserved.
- Custom groups, symptoms, and alerts are installed via per-object
  REST calls in dependency order (symptoms before alerts, since
  alerts reference symptoms by name → ID lookup).
- For a cross-instance bundle (dev → prod), super metrics, views,
  dashboards, and reports round-trip with their UUIDs intact.
  Custom groups, symptoms, and alerts get re-created on the
  destination under the same name.

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
# --- authored content (source of truth, version-controlled) ---
supermetrics/              Super metric YAML
customgroups/              Custom group YAML
views/                     List view YAML
dashboards/                Dashboard YAML
symptoms/                  Symptom definition YAML
alerts/                    Alert definition YAML
recommendations/           Remediation recommendation YAML
reports/                   Report definition YAML

# --- distribution bundles (manifest + build outputs) ---
bundles/                   Bundle manifest YAML (declares what's in each dist package)
dist/                      Built distribution zips (gitignored; produced by vcfops_packaging)

# --- Python packages (one per content type + packaging layer) ---
vcfops_supermetrics/       loader, client, CLI, content-zip import
vcfops_dashboards/         views + dashboards loader, render, client, CLI
vcfops_customgroups/       loader, REST client, CLI
vcfops_symptoms/           loader, REST client, CLI
vcfops_alerts/             loader, REST client, render (AlertContent.xml), CLI
vcfops_reports/            loader, render (report XML), client, CLI
vcfops_packaging/          bundle loader, builder (zip assembly), sync CLI
  templates/
    install.py             Python installer (goes inside every dist zip)
    install.ps1            PowerShell installer (goes inside every dist zip)
    README_framework.md    Framework README (goes inside every dist zip)

# --- topical background the agents read on demand ---
context/
  supermetric_authoring.md       DSL reference, idioms, anti-patterns
  wire_formats.md                Content-zip wire formats for each type
  uuids_and_cross_references.md  The UUID contract
  internal_supermetrics_assign.md  Default Policy enable endpoint
  customgroup_authoring.md       Custom group rule grammar
  customgroup_relationship_grammar.md  ANCESTOR/DESCENDANT rules
  content_api_surface.md         Public + internal + content-zip API map
  install_and_enable.md          Install flow + policy enablement
  reference_sources.md           Allowlisted external reference repos
  reference_docs.md              PDF extraction + VCF 9 doc inventory
  dashboard_delete_api.md        Ext.Direct delete wire formats (authoritative)
  chart_widget_formats.md        Widget wire formats for the 10 supported types
  widget_types_survey.md         Live instance widget usage survey
  widget_renderer_scope.md       Next renderer expansion plan (PropertyList+)
  reports_api_surface.md         Report definition wire format + API
  ui_import_formats.md           SPA UI import behavior + drag-drop paths
  struts_exploration_backlog.md  Legacy Struts/Ext.Direct endpoint reference
  struts_import_endpoints.md     Full Ext.Direct controller catalog
  vks_vm_classification.md       VKS VM type filter patterns
  qa_log.md                      Acceptance run audit trail

# --- subagent prompts ---
.claude/agents/
  ops-recon.md             Read-only reconnaissance (runs before every author)
  supermetric-author.md    Super metric authoring
  customgroup-author.md    Custom group authoring
  view-author.md           List view authoring
  dashboard-author.md      Dashboard authoring
  symptom-author.md        Symptom definition authoring
  alert-author.md          Alert + recommendation authoring (tight coupling)
  report-author.md         Report definition authoring
  api-explorer.md          Undocumented wire format investigation
  tooling.md               Python package maintenance (the only agent that edits vcfops_*/)
  content-installer.md     Sync, enable, verify against live instance
  content-packager.md      Bundle manifest + zip build pipeline
  qa-tester.md             End-to-end acceptance testing of distribution packages

# --- framework skills (loaded on demand by agents) ---
.claude/skills/
  vcfops-project-conventions/  Naming, validation, delegation protocol
  vcfops-content-model/        Content type relationships + cross-references
  vcfops-supermetric-dsl/      SM formula DSL reference
  vcfops-api/                  Suite API surface + content-zip + auth

# --- source material the framework trusts ---
docs/
  vcf9/                    Extracted VCF 9 documentation markdown
  operations-api.json      Public Suite API OpenAPI spec
  internal-api.json        Internal (unsupported) API OpenAPI spec

references/                Allowlisted external reference content clones
                           (gitignored; populate via scripts/bootstrap_references.sh)

CLAUDE.md                  Hard rules every agent obeys (orchestration + delegation)
README.md                  High-level overview (you are in ADMIN.md)
ROADMAP.md                 What's done, in progress, next, and future
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
python3 -m vcfops_supermetrics validate
python3 -m vcfops_supermetrics validate supermetrics/vks_cores.yaml
python3 -m vcfops_supermetrics list
python3 -m vcfops_supermetrics sync
python3 -m vcfops_supermetrics sync supermetrics/vks_cores.yaml
python3 -m vcfops_supermetrics enable supermetrics/vks_cores.yaml
python3 -m vcfops_supermetrics delete "[VCF Content Factory] VKS Cores (count)"

# --- views + dashboards ---
python3 -m vcfops_dashboards validate
python3 -m vcfops_dashboards sync

# --- custom groups ---
python3 -m vcfops_customgroups validate
python3 -m vcfops_customgroups list
python3 -m vcfops_customgroups list-types
python3 -m vcfops_customgroups sync
python3 -m vcfops_customgroups delete "[VCF Content Factory] VMs on NFS"

# --- symptoms ---
python3 -m vcfops_symptoms validate
python3 -m vcfops_symptoms sync
python3 -m vcfops_symptoms delete "[VCF Content Factory] VM CPU Usage Critical"

# --- alerts + recommendations (tightly coupled; loaded together) ---
python3 -m vcfops_alerts validate          # loads symptoms, alerts, AND recommendations
python3 -m vcfops_alerts sync
python3 -m vcfops_alerts delete "[VCF Content Factory] VM CPU Utilization Alert"

# --- reports ---
python3 -m vcfops_reports validate
python3 -m vcfops_reports sync

# --- distribution packaging ---
python3 -m vcfops_packaging validate                            # validate all bundle manifests
python3 -m vcfops_packaging build bundles/vks-core-consumption.yaml   # build one zip
python3 -m vcfops_packaging sync bundles/<name>.yaml             # sync a whole bundle to the instance
```

The **validate chain** is the fast health check run before any
sync or build:

```bash
python3 -m vcfops_supermetrics validate && \
python3 -m vcfops_dashboards validate && \
python3 -m vcfops_customgroups validate && \
python3 -m vcfops_symptoms validate && \
python3 -m vcfops_alerts validate && \
python3 -m vcfops_reports validate
```

If any of those six fail, something is wrong with a source YAML;
fix it before installing.

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
- You need a widget type the renderer doesn't support yet — see
  `context/widget_renderer_scope.md` for the current coverage and
  the next expansion queue (`PropertyList` is the biggest gap).
- You already have a working bundle and just need to tweak a single
  threshold in the Default Policy — do that in the GUI.
- You're authoring a one-off dashboard that won't outlive the
  current investigation.

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
- **Alerts → Definitions**: find the alert by name. Verify its
  symptom set, impact badge, and recommendation list. Attached
  recommendations render in the detail panel — if one is missing,
  check whether `install.py` actually carried it (the REST path
  currently has a known gap around recommendation attachment; the
  drag-drop `AlertContent.xml` path is the reliable one).
- **Alerts → Symptom Definitions**: find each symptom the alert
  references. Check the metric key, threshold, and wait/cancel
  cycles.
- **Administration → Reports**: find the report by name. Verify
  the pages ordered correctly and the embedded views resolve.
- **Alert-author panel on any resource**: one of the clearest ways
  to see whether an alert is actually firing on the right target
  kind is to navigate to an instance of that kind and look for
  the alert in the resource's detail panel.

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
