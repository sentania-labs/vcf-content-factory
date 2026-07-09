---
name: vcfops-project-conventions
description: >
  Project-specific conventions for the VCF Content Factory repo.
  Covers the [VCF Content Factory] naming prefix, YAML schema
  conventions, validation commands, the TOOLSET GAP reporting
  format, and the recon-before-authoring requirement. Use this
  skill whenever authoring content in this repo, reporting gaps,
  or validating content. For delegation protocol and workflow
  patterns, use vcfops-orchestration instead. This skill is
  specific to this project — the domain knowledge lives in the
  vcfops-api, vcfops-content-model, and vcfops-supermetric-dsl
  global skills.
---

# VCF Content Factory — project conventions

## Naming prefix

Every content object this repo creates has its display name
prefixed with `[VCF Content Factory] ` (literal brackets, one
space after).

Example: `[VCF Content Factory] Cluster - Avg Powered-On VM CPU Usage (%)`

- Do NOT invent alternate prefixes.
- `[AI Content]` is a legacy name and must NOT be reintroduced.
- Do NOT skip the prefix for brevity.
- Dashboards additionally live under the `VCF Content Factory`
  folder (the `name_path` field).

## Never fabricate

- **Metric keys**: Must be grounded in existing YAML,
  `reference/docs/vcf9/metrics-properties.md`, recon results, or a key the
  user provided.
- **Property keys**: Same grounding requirement.
- **Attribute names**: Same.
- **API endpoints**: Use only documented endpoints from the two
  OpenAPI specs.

When unsure, re-read the docs or ask the user for the exact key.

## Credentials

Flow via env vars only. Never on disk, never in YAML, never echoed
in shell output:

```
VCFOPS_HOST, VCFOPS_USER, VCFOPS_PASSWORD,
VCFOPS_AUTH_SOURCE, VCFOPS_VERIFY_SSL
```

## Validation commands

Run after every authoring round:

```bash
python3 -m vcfops_supermetrics validate &&
python3 -m vcfops_dashboards validate &&
python3 -m vcfops_customgroups validate &&
python3 -m vcfops_symptoms validate &&
python3 -m vcfops_alerts validate &&
python3 -m vcfops_reports validate
```

## Recon-before-authoring

Every content-authoring request begins with `ops-recon`. Check in
this order:

1. Built-in metrics (live `/statkeys` + docs)
2. Existing content on the instance
3. Existing YAML in the repo
4. Allowlisted external reference repos (`knowledge/context/reference_sources.md`)

If any source has an exact match, prefer reuse over authoring.

## Intent capture (`knowledge/designs/<type>/<slug>.md`)

After recon confirms new content is needed, the orchestrator writes
a design note before spawning an author:

- `knowledge/designs/supermetrics/<slug>.md`, `knowledge/designs/dashboards/<slug>.md`,
  `knowledge/designs/bundles/<slug>.md`, `knowledge/designs/managementpacks/<slug>.md`,
  etc. — one file per authored content object.
- Two required sections: **Initial prompt** (verbatim) and **Vision**
  (distilled understanding).
- Path is passed to the author agent in its brief. Author agents
  read it; they do not rewrite the prompt or vision sections.

See `knowledge/designs/README.md` for the full template. Over time this turns
the repo into a sample-prompt corpus.

## TOOLSET GAP reporting

When a loader, renderer, or schema can't express what's needed:

```
TOOLSET GAP
- what: <missing feature>
- minimum repro: <smallest YAML that exposes it>
- loader error: <exact message>
- needed to satisfy: <user's original request>
- suggested fix: <1-2 sentences>
```

Never silently downgrade. Never hack around a gap. Report it.

## UUID contract

- SM, view, dashboard, report: UUID v4 stored in YAML `id` field.
  Generated on first validate, never changed.
- Custom group, symptom, alert: No `id` field. Server assigns.
  Sync matches by `name`.

## Cross-reference syntax

Use names in YAML, never raw UUIDs:

- SM formula → SM: `@supermetric:"<exact name>"`
- View column → SM: `supermetric:"<exact name>"`
- Dashboard → view: `view: "<exact name>"`
- Alert → symptom: `name: "<exact name>"` in symptom set
- Report → view/dashboard: `view:` / `dashboard:` by exact name

## Source of truth

This repo's `reference/docs/` directory: DSL references, OpenAPI specs,
extracted markdown. Plus existing YAML under `content/supermetrics/`,
`content/views/`, `content/dashboards/`, `content/customgroups/`,
`content/symptoms/`, `content/alerts/`, `content/reports/`.

Do NOT invent functions, operators, metric keys, or API endpoints.
