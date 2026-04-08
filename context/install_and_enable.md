# Install and enable

How a super metric (or dashboard/view) actually lands on a VCF Ops
instance, and how to enable it in a policy after install.

## Credentials

Env vars, never on disk:

```
VCFOPS_HOST           hostname (no scheme)
VCFOPS_USER           username
VCFOPS_PASSWORD       password
VCFOPS_AUTH_SOURCE    optional, default "Local"
VCFOPS_VERIFY_SSL     optional, "false" to disable TLS verification
```

The project's `.claude/settings.local.json` has a PreToolUse/Bash
hook that sources `.env` before every Bash tool call, so Claude
doesn't need to re-export them each session.

## Install path — content zip

All installable content in this repo goes through
`POST /api/content/operations/import` via the shared packager in
`vcfops_dashboards` (and, after the planned refactor, a module
shared with `vcfops_supermetrics`). The importer preserves UUIDs
from the zip, which is why `context/uuids_and_cross_references.md`
insists on stable YAML-owned UUIDs.

```bash
# super metrics
python -m vcfops_supermetrics sync                   # all YAMLs
python -m vcfops_supermetrics sync supermetrics/<file>.yaml

# dashboards + views
python -m vcfops_dashboards sync                     # all YAMLs
```

Upsert-by-id semantics: importing a zip with `force=true` (which
the client sets) overwrites any existing object at the same UUID.
Since each YAML owns its UUID, that IS upsert-by-name from the
author's point of view.

## Enable a super metric in a policy

`sync` installs the super metric. It does **not** assign it to a
resource kind (now it does, via `resourceKinds` in the wire payload
— see `context/supermetric_authoring.md`) and it does **not** enable
it inside any policy.

Two paths to enable:

1. **`PUT /internal/supermetrics/assign`** (internal) — single call,
   sets both resource-kind assignment and policy enablement. Takes
   a body of `{superMetricId, resourceKindKeys:[{adapterKind, resourceKind}]}`
   and a `policyIds` query parameter (repeatable). Requires header
   `X-Ops-API-use-unsupported: true`. This is the path the planned
   `enable` CLI command uses.

2. **Policy export/import zip** — `GET /api/policies/export?id=<uuid>`,
   modify the XML to add
   `<SuperMetrics adapterKind=X resourceKind=Y>` with
   `<SuperMetric enabled="true" id="<uuid>"/>` children, re-import
   via `POST /api/policies/import`. Public but cumbersome; prefer
   option 1 unless we need bulk edits.

Neither path is wired into the CLI yet. Until the `enable` command
lands, instruct the user to:

1. Open **Infrastructure Operations → Configuration → Super Metrics**,
   confirm the new metric is assigned to the intended object type.
2. Open **Policies**, edit the relevant policy, enable the metric.

## List / delete (current CRUD surface)

These remain on `/api/supermetrics`; the migration to content-zip
install doesn't affect them.

```bash
python -m vcfops_supermetrics list
python -m vcfops_supermetrics delete "<name>"
```
