# [VCF Content Factory] Compliance Objects by SCG Version

- **Type:** view (bundled in the compliance pak)
- **Slug:** compliance-scg-versions
- **Authored YAML:** content/sdk-adapters/compliance/views/compliance-scg-versions.yaml
- **Date:** 2026-09-23
- **Status:** authored 2026-09-23; ships in adapter build 61

## Initial prompt

Scott, 2026-09-23 (verbatim, relevant part):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

Derived from the approved dashboard design. Verbatim prompts live in
`knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`; the
approved layout and keys in `knowledge/designs/dashboards/compliance-environment-overview.md`.

## Vision

Feeds Environment Overview W4. Spec: see the dashboard note section New views; includes the unknown bucket added in build 58. Keys are the adapter v3 build 60 key list
(content/sdk-adapters/compliance/README.md and docs/overview.md).
