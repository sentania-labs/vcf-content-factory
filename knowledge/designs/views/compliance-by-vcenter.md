# [VCF Content Factory] Compliance by vCenter and Object Type

- **Type:** view (bundled in the compliance pak)
- **Slug:** compliance-by-vcenter
- **Authored YAML:** content/sdk-adapters/compliance/views/compliance-by-vcenter.yaml
- **Date:** 2026-09-23
- **Status:** authored 2026-09-23; ships in adapter build 61

## Initial prompt

Scott, 2026-09-23 (verbatim, relevant part):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

Derived from the approved dashboard design. Verbatim prompts live in
`knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`; the
approved layout and keys in `knowledge/designs/dashboards/compliance-environment-overview.md`.

## Vision

Feeds Environment Overview W3. Spec: see the dashboard note section New views. Keys are the adapter v3 build 60 key list
(content/sdk-adapters/compliance/README.md and docs/overview.md).
