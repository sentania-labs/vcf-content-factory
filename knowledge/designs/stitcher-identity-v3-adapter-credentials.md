# stitcher identity v3 — platform-injected per-instance credential first

## Initial prompt (verbatim, 2026-07-02 session)

> This doesn't feel like using the platforms framework and tooling to do
> something, but trying to brute force it.
>
> What does the code say?

(Approving the pipeline:)

> so Update tooling/vcfvcfadapter?
> so update fix, and build synolgy
> test on devel and prod?
> close issue, update docs
> build with CI?

## Vision

The ambient Suite API identity becomes the credential the collector
hands every adapter at startup — the mechanism the vendor corpus uses
and the live Oracle adapter proves works on the prod Cloud Proxy.

- **Contract (bytecode-proven, `knowledge/context/api-surface/
  per-instance-suiteapi-credential-contract.md`):** the collector
  serializes a per-instance credential into the adapter's config
  payload; SDK-public read: `AdapterBase.getAdapterConfig()
  .getAdapterCredentials().getUserName()/.getPassword()`. The vendor
  library uses it credentials-first with the maintenance file as
  fallback; our framework only ever implemented the fallback — the
  root of the entire CP-403/401 saga.
- **New ambient order in `AmbientCredential`:** (1) injected
  per-instance credential (when present/non-null), (2)
  `automationuser.properties`, (3) `maintenanceuser.properties`.
  Selected source logged (`file=instance|automation|maintenance|
  override` + principal). Explicit-creds path untouched.
- **Clean-room posture:** the READ is pure public SDK surface (no
  aria-ops-core code or types); the token-acquire spend path is our
  existing one. No vendor code replicated.
- **Live residuals this build itself resolves on the prod CP fixture
  (DEF-006):** does a third-party instance receive the injected
  credential, and does its token carry resource-read on a CP — the
  first cycle's `principal=` line + `loadDatastores` outcome answers
  both.
- **Adapter-side (synology build 26, after the framework gate):** fix
  the NFS resolver NIC selection (adapter picked first NAS interface
  `.51`; ESXi mounts via `.52` — must use the interface(s) the
  export/target is actually served on, or all candidates), and REMOVE
  the build-25 `relationships|Datastore_parent` property emission +
  its describe placeholders (platform-proven inert for edge creation:
  `knowledge/context/investigations/platform-edge-engine-2026-07-02.md` — no
  property→edge code path exists).
- **Ladder:** tooling → framework-reviewer → build 26 → devel →
  prod CP fixture → DEF-006 close on live evidence → doc corrections →
  ONE PR → buildkit republish → CI `v*` release (defect-gate now
  passable).

## Evidence base

- `knowledge/context/api-surface/per-instance-suiteapi-credential-contract.md`
- `knowledge/context/investigations/oracle-stitch-autopsy-2026-07-02.md` (live
  DEBUG capture: token as instance UUID; corrects three earlier docs)
- `knowledge/context/investigations/platform-edge-engine-2026-07-02.md` (edge
  engine: identifier-keyed cache; no property path; traversal inert)
- DEF-006 in `knowledge/context/defects.md`
