# [VCF Content Factory] Compliance Objects Scored

- **Type:** supermetric (bundled in the compliance pak)
- **Slug:** compliance-objects-scored
- **Authored YAML:** content/sdk-adapters/compliance/supermetrics/compliance-objects-scored.yaml
- **Date:** 2026-09-23
- **Status:** authored 2026-09-23; ships in adapter build 61

## Initial prompt

Scott, 2026-09-23 (verbatim, relevant part):

> Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.

Derived from the approved dashboard design. Verbatim prompts live in
`knowledge/designs/sdk-adapters/compliance-v3-version-aware.md`; the
approved layout and keys in `knowledge/designs/dashboards/compliance-environment-overview.md`.

## Vision

Feeds Environment Overview W1, W5. Spec: sum over vCenters (depth 1 from vSphere World) of `VCF-CF Compliance|Rollup|All|scored`. Keys are the adapter v3 build 60 key list
(content/sdk-adapters/compliance/README.md and docs/overview.md).
