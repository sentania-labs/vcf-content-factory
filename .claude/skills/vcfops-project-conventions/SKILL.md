---
name: vcfops-project-conventions
description: >
  Project-specific conventions for the VCF Content Factory repo.
  Covers the [VCF Content Factory] naming prefix, YAML schema
  conventions, validation commands, the agent delegation protocol,
  the TOOLSET GAP reporting format, and the recon-before-authoring
  requirement. Use this skill whenever authoring content in this
  repo, delegating to subagents, reporting gaps, or validating
  content. This skill is specific to this project — the domain
  knowledge lives in the vcfops-api, vcfops-content-model, and
  vcfops-supermetric-dsl global skills.
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
  `docs/vcf9/metrics-properties.md`, recon results, or a key the
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
4. Allowlisted external reference repos (`context/reference_sources.md`)

If any source has an exact match, prefer reuse over authoring.

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

This repo's `docs/` directory: DSL references, OpenAPI specs,
extracted markdown. Plus existing YAML under `supermetrics/`,
`views/`, `dashboards/`, `customgroups/`, `symptoms/`, `alerts/`,
`reports/`.

Do NOT invent functions, operators, metric keys, or API endpoints.
