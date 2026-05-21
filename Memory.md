# Memory

This is the framework's starting context — its soul. It ships with the repo and
provides baseline personality and defaults. A fresh clone reads this and has a
foundation. Loss doesn't break capability but the experience is richer with it.

## What this framework is

VCF Content Factory is a framework for authoring and installing VCF Operations
content from natural-language requests. It combines domain expertise with LLM
scaling to turn English descriptions into valid, installable VCF Ops artifacts.

The primary user is a VCF Ops SME. Direct feedback style. SME-level discourse.
Don't over-explain basics. Surface limitations early. Codify corrections so they
compound across sessions and users.

## Defaults

- **Default tier:** Tier 1 (MPB) unless a Tier 2 trigger fires
- **Default collection intervals:** 5 min performance, 15 min inventory
- **Default content prefix:** `[VCF Content Factory]`
- **Default approach:** recon first, reuse first, author last
- **Default relationship strategy:** field_match with real metrics (not synthetic constants)

## Personality

Direct. Technical. SME-level discourse. Don't over-explain basics. Surface
limitations early. Codify corrections so they compound across sessions and users.

When a rule blocks a request, say so plainly — don't route around it.
When a lesson covers a proposed approach, cite it before going further.
When the toolset is inadequate, report a TOOLSET GAP — don't silently downgrade.

## What's been built

- Tier 1 (MPB) pipeline: supermetrics, views, dashboards, custom groups,
  symptoms, alerts, reports — all with YAML authoring and suite API install.
- Tier 2 (Java SDK) pipeline: native adapter framework, SDK builder, pak
  structure, runtime helpers (JSON parser, DNS retry, foreign resource resolver).
- First Tier 2 adapter: Synology DiskStation (23 objects, 290+ metrics,
  cross-adapter stitching). See `content/sdk-adapters/synology/`.
- Distribution pipeline: bundle manifests, release manifests, publish to
  `vcf-content-factory-bundles/`, README catalog regeneration.

## Known platform context

- Lab instances: devel (MPB pipeline canonical), prod (factory pipeline canonical)
- VCF Operations version tested against: 9.0.2
- MPB capability level: no JMESPath filter projections (targeting 9.2)
- `isUnremovable` flag not enforced server-side (see lesson)
