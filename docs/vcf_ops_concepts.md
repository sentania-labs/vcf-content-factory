# VCF Operations Content Concepts

Reference walkthrough of every VCF Operations content type the
framework produces — what they are, how they relate, how they're
identified, and how they install. Read this when "what's a super
metric vs a custom group?" is a real question for you, or when
debugging why a piece of content isn't doing what you expected.

For the framework architecture, see
[../HOW_IT_WORKS.md](../HOW_IT_WORKS.md). For first-time use, see
[../Getting_Started.md](../Getting_Started.md).

---

## 1. What VCF Operations content actually is

The framework produces eight first-class content types, plus
management packs as a ninth track. Each is a first-class object in
VCF Operations with its own API, lifecycle, and wire format.

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
`../context/widget_renderer_scope.md` for the next implementation
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
`../context/dashboard_delete_api.md`).

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

### Management packs

A **management pack** (`.pak` file) adds a whole new adapter to
VCF Operations — a new source of data, a new set of resource
kinds, and a new lifecycle Ops doesn't ship with out of the box.
Two tiers:

- **Tier 1 (MPB)** — REST-API-sourced adapters expressed in YAML,
  compiled into a `.pak` by the built-in Management Pack Builder.
  Fast to author, no Java required. Handles most HTTP REST sources.
- **Tier 2 (native Java SDK)** — Custom Java code extending
  `UnlicensedAdapter`. Handles cases MPB can't (complex auth,
  non-HTTP protocols, per-instance attribute groups, dynamic time
  parameters). Framework provides `vcfcf-adapter-base.jar` with
  typed auth, retry, HTTP, metric push, and describe.xml helpers,
  so per-adapter code is small.

The tier decision is documented in
[`../context/tier_decision_framework.md`](../context/tier_decision_framework.md).
The framework defaults to Tier 1; it proposes Tier 2 when specific
triggers (e.g. need for `instanced="true"` ResourceGroups,
non-HTTP transport, OAuth2 refresh, programmatic actions) apply.

---

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
is portable across dev/test/prod.

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

### The `.pak` install path (management packs)

Management packs install via the admin pak-upload endpoint:
`POST /admin/admin/services/solution/upload`. The pipeline is
multi-stage: stage → preapply validate → validate → apply adapter
pre-script → apply adapter → post-apply adapter. The
`apply_adapter` phase is where the platform parses describe.xml
and registers the adapter kind. Failures at that stage produce
the dreaded "Adapter install failed" with no surface-level error
— logs live at
`/usr/lib/vmware-vcops/user/log/pakManager/vcopsPakManager.root.apply_adapter.log`
and `/storage/log/vcops/log/casa/casa_pak_history_<pakID>.json`.

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
exists and wire it into `_install_alerts` before the alert POST,
or switch alerts to content-zip envelope install matching how
reports work.

### What that means in practice

- You can bundle super metrics + views + dashboards + reports into
  a single content-import zip and install them atomically with
  UUIDs preserved.
- Custom groups, symptoms, and alerts are installed via per-object
  REST calls in dependency order (symptoms before alerts, since
  alerts reference symptoms by name → ID lookup).
- For a cross-instance bundle (dev → prod), super metrics, views,
  dashboards, and reports round-trip with their UUIDs intact.
- Management packs install separately via the admin pak-upload
  endpoint and add new adapter kinds to the instance.

---

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

Custom groups, symptoms, alerts, and recommendations are the
exceptions — their identity is `name` (or a deterministic ID
derived from name + adapter_kind for recommendations) because Ops
assigns the UUID server-side and there's no way to override it.

Full grammar in
[`../context/uuids_and_cross_references.md`](../context/uuids_and_cross_references.md).

---

## 4. Wire-format gotchas worth knowing

These aren't bugs — they're undocumented behaviors of VCF Ops's
wire formats that the framework handles for you. Knowing them
helps you understand framework decisions and hand-edit YAML
correctly when needed.

### Super metric `where` clause shape

The DSL docs suggest several ways to express filters. Only one
works. The canonical form is:

```
where="summary|config|type equals VMOperator"
```

Quoted key on the left, `equals` operator, **literal value** on
the right (no quotes around the value). String values are compared
verbatim. The framework's super-metric author always emits this
form.

### Metric key spelling

Property keys and stat keys are case-sensitive, underscore-sensitive,
and unforgiving. `config|hardware|num_Cpu` is right;
`config|hardware|numCpu` is the property-layer form of the same
value and silently no-datas when used as a metric target. Recon
always confirms the live-instance spelling before authoring.

### View super metric column attribute prefix

When a view references a super metric column, the attribute path
must be `Super Metric|sm_<uuid>` (with the literal "Super Metric|"
prefix, not just the UUID). Forget the prefix and the column
renders blank.

### Self-provider dashboard widgets

A dashboard widget pinned to a container resource (e.g. a View
widget that should walk the descendants of a specific
ClusterComputeResource) needs `selfProvider: true` plus a
`pinnedResources` block. Otherwise the widget waits forever for an
interaction that never comes and renders blank.

### `resourceKindId` stable prefix

In the content-zip wire format, resource kind references use
prefixed IDs like `<adapterKind>-<resourceKind>`. The framework
preserves these prefixes; hand-editing them is the fastest way to
break a content-zip import.

### Dashboard folders (`namePath`)

Dashboards live under a `namePath` — `VCF Content Factory/...`
in this repo. The framework applies the path automatically; YAML
doesn't specify it. Custom folders require both the dashboard's
`namePath` and a folder declaration on the import side.

### `shared: true` for dashboards

Without `shared: true`, a dashboard imported via content-zip is
visible only to the import owner. The framework defaults
dashboards to shared.

### Content-task contention

VCF Ops's content-import path serializes against itself —
attempting two imports concurrently produces `1523 Task is already
running`. The framework's installer retries with backoff.

### Management pack describe.xml `<ResourceGroup>` wrapping

Discovered 2026-05-18: ResourceAttribute elements on data
ResourceKinds must be wrapped in `<ResourceGroup key="summary"
instanced="false">`. The XSD permits bare ResourceAttributes under
ResourceKind, but Ops 9.1's apply_adapter phase rejects them. The
factory's `builder.py` enforces this invariant. See
[`../context/mpb_describe_xml_emission.md`](../context/mpb_describe_xml_emission.md).

### MPB Tier 1 cannot emit `instanced="true"` ResourceGroups

Confirmed empirically. Per-instance attribute groups (e.g. one
resource per server with `Hardware|Power:PS1|...` style addressing
per PSU) require Tier 2 (native Java SDK). The framework will
propose Tier 2 when this trigger applies. See
[`../context/mpb_instanced_groups_wire_format.md`](../context/mpb_instanced_groups_wire_format.md).

---

## Further reading

- [`../context/`](../context/) — the authoritative files agents
  read on demand: DSL reference, wire format notes, API surface
  map, UUID contract, allowlisted reference sources, codified
  lessons. Start at `../context/README.md`.
- [`../HOW_IT_WORKS.md`](../HOW_IT_WORKS.md) — orchestrator + agents
  architecture and reasoning.
- [`../Getting_Started.md`](../Getting_Started.md) — first-use
  walkthrough with example prompts.
