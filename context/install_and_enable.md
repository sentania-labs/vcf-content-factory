# Install and enable

How a super metric (or dashboard/view) actually lands on a VCF Ops
instance, and how to enable it in a policy after install.

## Credentials

Credentials live in three named profiles in `.env`, never as flat vars:

```
VCFOPS_PROD_HOST / VCFOPS_PROD_USER / VCFOPS_PROD_PASSWORD
  vcf-lab-operations.int.sentania.net, user claude (read-only recon)

VCFOPS_QA_HOST / VCFOPS_QA_USER / VCFOPS_QA_PASSWORD
  vcf-lab-operations.int.sentania.net, user admin (uninstall round-trips)

VCFOPS_DEVEL_HOST / VCFOPS_DEVEL_USER / VCFOPS_DEVEL_PASSWORD
  vcf-lab-operations-devel.int.sentania.net, user admin (destructive playground)
```

Each profile also has `_AUTH_SOURCE` (default `Local`) and `_VERIFY_SSL`.

Active profile resolution order (first wins):
1. `--profile <name>` CLI flag
2. `VCFOPS_PROFILE` environment variable
3. Per-command default (`prod` for validate/list/recon; `devel` for sync/enable/delete)

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

1. **`PUT /internal/supermetrics/assign`** (internal, unsupported) —
   sets resource-kind assignment and policy enablement in one call.
   Body `{superMetricId, resourceKindKeys:[{adapterKind, resourceKind}]}`,
   `policyIds` as a repeatable query parameter, header
   `X-Ops-API-use-unsupported: true` required. **Empirically verified
   to accept only the Default Policy id** — any other policy UUID is
   rejected with 400 apiErrorCode 1501. See
   `context/internal_supermetrics_assign.md` for the full wire-format
   findings, readback path, and edge-case table.

   This is the path `vcfops_supermetrics enable` uses:

   ```bash
   python -m vcfops_supermetrics enable                       # all YAMLs
   python -m vcfops_supermetrics enable supermetrics/<f>.yaml
   ```

   The command resolves the Default Policy id at runtime, looks up
   each super metric on the instance by name, and calls assign. It
   refuses if the super metric isn't installed yet — run `sync` first.

2. **Policy export/import zip** — `GET /api/policies/export?id=<uuid>`,
   modify the XML to add
   `<SuperMetrics adapterKind=X resourceKind=Y>` with
   `<SuperMetric enabled="true" id="<uuid>"/>` children, re-import
   via `POST /api/policies/import`. **Required** for any non-default
   policy (path 1 will 400). Also the only way to *disable* a super
   metric — no internal unassign endpoint exists. Not yet wired into
   the CLI.

For non-default policies, fall back to the manual UI path:

1. Open **Infrastructure Operations → Configuration → Super Metrics**,
   confirm the new metric is assigned to the intended object type.
2. Open **Policies**, edit the relevant policy, enable the metric.

## List / delete (current CRUD surface)

These remain on `/api/supermetrics`; the migration to content-zip
install doesn't affect them.

```bash
python -m vcfops_supermetrics list
python -m vcfops_supermetrics delete "<name>"
python -m vcfops_supermetrics enable supermetrics/<file>.yaml  # Default policy
```
