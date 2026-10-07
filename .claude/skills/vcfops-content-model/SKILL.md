---
name: vcfops-content-model
description: >
  The VCF Operations content object model: super metrics, views,
  dashboards, custom groups, symptoms, alerts, and reports. Covers
  what each content type is, how they reference each other, UUID
  contracts, policy enablement, and identity schemes. Use this skill
  whenever authoring, reviewing, or planning VCF Ops content —
  especially when working out cross-references between content types,
  deciding which content types a request needs, or understanding
  the dependency graph (SM → view → dashboard, symptom → alert).
  Also use for questions about VCF Operations / Aria Operations /
  vRealize Operations content management concepts.
---

# VCF Operations content model

## Content types

### Super metrics

A named formula evaluated against resources on a schedule. Written
in a DSL (see the `vcfops-supermetric-dsl` skill). Assigned to one
or more **resource kinds** and enabled in a **policy**.

Key facts:
- Formula is the DSL expression. For DSL details, use the
  `vcfops-supermetric-dsl` skill.
- Must be assigned to resource kinds AND enabled in a policy to
  collect data.
- UUID is caller-owned (stored in YAML, preserved by content-zip
  import).
- Install path: content-zip import (preserves UUIDs).
- Enable path: `PUT /internal/supermetrics/assign/default`
  (Default Policy only).

### Custom groups

A named, dynamic set of resources defined by membership rules.
The group itself is a resource in Ops (has an ID, appears in
inventory, can be a view/alert/permission target).

Key facts:
- Identity is `name`, not UUID. Server assigns `id` on create.
- Install path: REST POST/PUT (not content-zip).
- Rules use AND within a single rule, OR across multiple rules.
- Each rule selects one `(resourceKind, adapterKind)` pair.
- `autoResolveMembership: true` for dynamic evaluation.
- For rule grammar details, read `knowledge/context/wire-formats/customgroup_relationship_grammar.md`.

### List views

A tabular report: pick a subject resource kind, pick columns
(built-in metrics, properties, or super metric references), and
Ops renders a table.

Key facts:
- UUID is caller-owned (stored in YAML).
- Install path: content-zip (views.zip containing content.xml).
- Columns reference super metrics as `sm_<uuid>` in `attributeKey`.
- Can run standalone or embedded in a dashboard widget.
- No REST CRUD — delete only via UI action layer.

### Dashboards

A layout of widgets. Currently supported widget types:
`ResourceList` (object picker) and `View` (embedded list view).

Key facts:
- UUID is caller-owned.
- Install path: content-zip (dashboard.json per owner).
- Widgets reference views by UUID (`config.viewDefinitionId`).
- `widgetInteractions` wire provider→receiver by widget UUID.
- `dashboardNavigations` is the Dashboard Navigation drill-down: source
  widget UUID to a list of target dashboard UUIDs, each optionally naming
  receiving widgets on the target (`interactionType: resourceId`, the
  only value observed). YAML: per-widget `navigations` with `dashboard`
  (by name) or `dashboard_id` (raw, external); see
  `knowledge/context/wire-formats/dashboard_navigations.md`.
- No REST CRUD — delete only via UI action layer.

### Symptom definitions

A condition evaluated on collected data (metric threshold, property
comparison, or event trigger). Feeds into alert definitions.

Key facts:
- Identity is `name`, not UUID. Server assigns `id` on create.
- Install path: REST POST/PUT via `/api/symptomdefinitions`.
- Types: metric_static, metric_dynamic, property, message_event,
  fault_event, metric_event.
- Hundreds of built-in symptoms ship with every adapter.

### Alert definitions

Combines symptom sets into actionable alerts with impact badges,
criticality levels, and recommendations.

Key facts:
- Identity is `name`, not UUID. Server assigns `id` on create.
- Install path: REST POST/PUT via `/api/alertdefinitions`.
- References symptoms by name (resolved at sync time).
- Has public enable/disable endpoint (unlike super metrics).
- Impact badges: HEALTH, RISK, EFFICIENCY.

### Report definitions

Ordered page layouts combining cover pages, TOC, and view/dashboard
sections into a printable/exportable document.

Key facts:
- UUID is caller-owned.
- Install path: content-zip (reports.zip containing content.xml).
- References views and dashboards by name (resolved at validate).
- No REST create — content-zip only.

## Cross-reference graph

```
super metric ──referenced-by──▶ view column
super metric ──referenced-by──▶ super metric formula
view ──────────referenced-by──▶ dashboard widget
view ──────────referenced-by──▶ report section
dashboard ─────referenced-by──▶ report section
symptom ───────referenced-by──▶ alert definition
custom group ──scoped-by──────▶ view / alert / permission
```

**Dependency order for authoring:**
SM → custom group → view → dashboard → report
symptom → alert

**Dependency order for install:**
SM sync → SM enable → custom group sync → symptom sync →
alert sync → dashboard+view sync → report sync

## Identity schemes

Two schemes coexist:

| Scheme | Content types | Authoring | Sync match |
|---|---|---|---|
| UUID-owned | SM, view, dashboard, report | Generate v4 on first validate, never change | Content-zip preserves UUID |
| Name-owned | Custom group, symptom, alert | No `id` in YAML | REST match by `name` |

For UUID-owned types, renaming is safe (UUID stays stable).
For name-owned types, renaming creates a new object on sync.

## Cross-reference syntax

For detailed syntax and resolution rules, read
`knowledge/context/authoring/uuids_and_cross_references.md`.

Quick reference:

| From → To | Syntax | Resolved to | When |
|---|---|---|---|
| SM formula → SM | `@supermetric:"<name>"` | `sm_<uuid>` | validate |
| View column → SM | `supermetric:"<name>"` | `sm_<uuid>` | validate |
| Dashboard → View | `view: "<name>"` | view UUID | validate |
| Dashboard → Dashboard | `navigations: [{dashboard: "<name>", widgets: [<local id>]}]` | dashboard UUID + target widget UUIDs | render (validate checks) |
| Alert → Symptom | `name: "<name>"` | symptom ID | sync |
| Report → View | `view: "<name>"` | view UUID | validate |
| Report → Dashboard | `dashboard: "<name>"` | dashboard UUID | validate |

## Policy enablement

Super metrics must be enabled in a policy to collect data. Two paths:

1. **Internal API** — `PUT /internal/supermetrics/assign/default`.
   Works for Default Policy only. Single call.
2. **Policy export/import** — Download XML, edit, re-import.
   Required for non-default policies.

Alert definitions have public enable/disable endpoints.
Symptom definitions, views, dashboards, and custom groups do not
require policy enablement.

## Reference files

- `knowledge/context/authoring/uuids_and_cross_references.md` — Full cross-reference
  syntax, resolution rules, and dependency ordering for all
  content types.
