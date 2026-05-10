# Install and verification rules

Rules for installing content on VCF Ops instances and verifying the
results. Each rule prevents a documented failure mode.

## Install workflow

### Enable SMs on Default Policy after sync
After super metric sync, automatically enable on the Default Policy
for each SM's `resource_kinds`. Only skip if the user explicitly says
otherwise.

### Verify existing SM deps, not just new ones
When new content references a pre-existing SM, the install brief must
list that SM for enablement verification. Don't assume prior sessions
left it enabled.

### Install script UX pattern
Numbered steps, `OK`/`WARN` prefixes, defaults in `[brackets]`, auth
source prompt handling both local and domain accounts, masked password.

### Dashboard uninstall requires admin
VCF Ops content-zip import assigns dashboard ownership to the literal
`admin` account. Uninstall requires that account, not just admin
privileges.

### Installer syncs, recon verifies
content-installer runs CLI commands (sync, enable, delete). It does
NOT poll for data or verify existence. Verification belongs to
ops-recon.

## Dependency and metric validation

### Packaging-time dependency audit
The builder walks all dashboards/views/SMs, extracts metric keys,
resolves against adapter describe. Unknown key → fail build.
Known + `defaultMonitored=false` → require `builtin_metric_enables`
entry.

### Check defaultMonitored before picking metrics
Every metric key must have `defaultMonitored: true`. Keys with `false`
produce no data without customer policy changes. Prefer
`virtualDisk|*` over `disk|*` for storage metrics.

### Adapter describe is authoritative
Adapter describe files are the source of truth for all metrics and
properties. Live object queries may miss unpolled metrics. Pull
describe data via Suite API during recon.

### Recon must check describe cache
Searching only `docs/vcf9/metrics-properties.md` misses keys in live
adapter describe. Grep both `metrics-properties.md` AND
`context/adapter_describe_cache/<ADAPTER>/<ResourceKind>.json`.
