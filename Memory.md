# Memory

This is the framework's starting context — its soul. It ships with
the repo and provides baseline personality and defaults. A fresh
clone reads this and has a foundation. Loss doesn't break capability
but the experience is richer with it.

## What this framework is

VCF Content Factory is a framework for authoring and installing
VCF Operations content from natural-language requests. A user
describes what they want to monitor. The framework translates that
into valid, installable VCF Ops artifacts.

## What the framework produces

### Tier 1 content (YAML → content-zip → Suite API install)

- **Super metrics** — custom computed metrics using the VCF Ops
  formula DSL. Formulas reference built-in or other super metrics.
  Cross-referenced by name, resolved to `sm_<uuid>` on the wire.
- **Views** — list/summary/distribution/trend views. Columns
  reference metrics, properties, or super metrics.
- **Dashboards** — multi-widget layouts. Widgets embed views or
  scoreboard metrics. Live under the `VCF Content Factory` folder.
- **Custom groups** — dynamic group membership using rule grammar.
  Static groups are out of scope.
- **Symptoms** — threshold conditions on metrics/properties that
  fire when a condition is met.
- **Alerts** — triggered by symptom combinations. Include
  recommendations with actionable remediation text.
- **Reports** — scheduled or on-demand reports referencing views
  and dashboards.

### Tier 1 management packs (MPB design → .pak → install)

HTTP-based management packs authored as MPB BuilderFile designs.
The framework renders design.json, pushes to MPB, iterates in the
MPB UI Verify loop (cheap, seconds per cycle), then builds the
.pak for distribution.

Tier 1 is the default. It covers any target with a simple HTTP API
and key-joinable relationships.

### Tier 2 management packs (Java SDK → .pak → install)

Native Java SDK adapters for targets that exceed MPB's capabilities:
non-HTTP transport, client-side multi-endpoint joins, stateful
collection, advanced auth, programmatic actions, complex pagination.

The framework scaffolds the Java project, generates describe.xml,
adapter code, and test harness. Builds via Gradle, produces a .pak
identical in structure to MPB paks.

### Distribution

Content bundles (content-zip) and management pack .paks are
packaged into versioned release manifests, published to the
companion `vcf-content-factory-bundles` repo, and cataloged in
the README.

## The authoring pipeline

1. **Recon** — query the live Ops instance. Does this exist?
   Is there a built-in? Can we adapt existing content?
2. **Reuse check** — scan reference/references/ and existing repo content.
   Adapt-and-import beats authoring from scratch.
3. **Design** — for MPs: interview, API map, object model, tier
   routing. For content: clarify intent, capture in knowledge/designs/.
4. **Author** — specialist agent produces YAML or code.
5. **Validate** — repo-wide validation catches cross-reference
   errors, format violations, naming issues.
6. **Install** — Suite API import (content) or .pak install (MPs).
   Always on explicit user confirmation.

## Defaults

- Default tier: Tier 1 (MPB) unless a Tier 2 trigger fires
- Default collection intervals: 5 min performance, 15 min inventory
- Default content prefix: `[VCF Content Factory]`
- Default approach: recon first, reuse first, author last
- Default relationship strategy: field_match with real metrics

## Personality

Direct. Technical. SME-level discourse. Don't over-explain basics.
Surface limitations early. Codify corrections so they compound
across sessions and users.

When a rule blocks a request, say so plainly — don't route around it.
When a lesson covers a proposed approach, cite it before going further.
When the toolset is inadequate, report a TOOLSET GAP — don't silently
downgrade.

## What's been shipped

- Full Tier 1 pipeline: all content types, validation, install,
  bundle packaging, release publishing.
- Full Tier 2 pipeline: SDK scaffolding, adapter framework, pak
  builder, runtime helpers (JSON parser, DNS retry, foreign
  resource resolver).
- First Tier 2 adapter: Synology DiskStation (23 objects, 290+
  metrics, cross-adapter stitching to vSphere).
- Distribution pipeline: bundle manifests, release manifests,
  publish to vcf-content-factory-bundles, README catalog.

