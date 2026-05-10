# Operational rules

Rules for day-to-day operations: credentials, lab usage, cross-
workspace communication, and distribution.

## Credentials and labs

### .env at repo root is authoritative
The `.env` file holds all credentials as three named profiles:
- `VCFOPS_PROD_*` — primary lab, user `claude` (read-only recon)
- `VCFOPS_QA_*` — primary lab, user `admin` (uninstall round-trips)
- `VCFOPS_DEVEL_*` — devel lab, user `admin` (destructive playground)

Source it directly. Select profile with `--profile <name>` or
`VCFOPS_PROFILE` env var.

### Devel lab is a destructible playground
Content lost on devel during probes or experiments is NOT an incident.
Primary lab is sacred. Still prefer minimal-touch paths — devel is
tolerant, not disposable.

## Cross-workspace communication

### Async requests can be short-circuited
When Scott provides a value out-of-band before a cross-workspace
response arrives, use Scott's value. Acknowledge the response file for
cleanliness but don't re-install.

### Riker to: field = workspace directory name
The `--to` slug for cross-workspace requests must match a directory
name under `~/pka/workspaces/` exactly. Run `ls ~/pka/workspaces/` to
confirm.

## Distribution and attribution

### Public vs PKA info boundary
In bundles (public): names, roles, source venue, URL, upload date.
In PKA only (private): LinkedIn URLs, employer affiliations, personal
connections. Don't put contact info in public artifacts unless Scott
explicitly authorizes it.

### QA reports structured for downstream agents
Each QA finding must name which agent acts on it. Include enough
detail (wire captures, raw request/response) that the downstream agent
can execute without re-running QA.
