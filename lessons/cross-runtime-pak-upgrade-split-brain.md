# Cross-runtime pak "upgrade" (container→classic) silently split-brains

## Rule

On VCF Ops 9.0.2, installing a classic Java SDK pak that shares the pak name
and adapter kind of an installed containerized (Python Integration SDK) pak is
**accepted as a version upgrade but never converts the adapter-kind
registration.** The solution version bumps and the outer manifest is replaced,
but the kind stays `adapterKindType=DOCKERIZED` with the **old** describe.xml,
the shipped Java JAR is dead weight (never wired in), and instance creation on
a non-container collector still fails with 500 "Collector is not compatible
with adapter type." No error surfaces at install time.

**There is no in-place container→classic migration path via the pak install
flow.** Do not ship a same-identity "upgrade" pak — it reports success while
silently leaving the old container adapter live. Use a distinct adapter kind
key and side-by-side install; migration for existing users is uninstall-old +
install-new + recreate instances/credentials.

## Evidence

Live experiment, devel instance, VCF Ops 9.0.2, 2026-06-10
(`context/investigations/vcommunity_upgrade_path_experiment.md`):

Installed containerized `iSDK_VCFOperationsvCommunity` 0.2.8 (kind
`VCFOperationsvCommunity`, registered `DOCKERIZED`), then installed a
hand-retargeted same-identity classic Java stub pak 1.0.0. The platform
recognised it as the same pak and processed a version update — "Install
completed and verified," `/api/solutions` version `1.0.0`, new icon. But
`GET /api/adapterkinds/VCFOperationsvCommunity` still returned `DOCKERIZED`,
the resource kinds were still the original's (new describe.xml not applied),
the integration description/vendor were still the original's, and
`POST /api/adapters` on the local collector still returned the same 500 as
before the "upgrade." Strictly worse than an honest rejection: the operator
sees version 1.0.0 while the old container registration (and on a real Cloud
Proxy, the old image digest) stays live.

The container marker is the `<kind>.conf` in `adapter.zip` (registry /
repository / digest, no code); classic paks ship `adapters.zip` with the JAR.
Both carry identical describe.xml schemas, which is what makes the
same-identity upgrade look plausible on paper.

Bonus: `GET /api/credentials?adapterKindKey=` is a **leaky filter** — it
returned 6 credentials belonging to unrelated kinds (`VMWARE`,
`vcfcf_compliance`, etc.) that merely share a credential-field shape. Verify
each candidate's real `adapterKindKey` via the unfiltered list before trusting
or deleting filtered results.

## Context

- `context/investigations/vcommunity_upgrade_path_experiment.md` — full
  experiment, structural comparison table, cleanup verification
- `designs/managementpacks/vcommunity.md` — Tier 2 design; "distinct kind key"
  is now a hard requirement, not a nicety
- Related toolset note: `src/vcfops_managementpacks/sdk_project.py` rejects
  mixed-case adapter kind keys (`[a-z][a-z0-9_]*`) that VCF Ops itself accepts
  — a same-identity build is un-buildable through `build-sdk` as it stands
