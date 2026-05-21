---
id: RULE-009
---

# RULE-009: No destructive actions on production instances

Never run remove, deactivate, or destructive pak operations on production VCF Operations instances. This includes calling `mainAction=remove` via any API surface.

On lab/test instances: never call remove against built-in paks (`isUnremovable: true` in `getIntegrations`). Test uninstall flows only with purpose-built test paks.

**If violated:** Built-in pak removal leaves the instance in an unrecoverable state. VCF Ops 9.0.2 does not enforce `isUnremovable` server-side — the flag is advisory-only, the API will accept and execute the call. Recovery requires cluster restart or snapshot restore. See `lessons/pak-isunremovable-vendor-bug.md`.
