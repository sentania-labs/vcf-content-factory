# Design note — unifi adapter v2 migration

## Initial prompt

2026-06-10 session (verbatim):

> you have my go to loop until all 3 paks are refactored and working as
> expected in devel

Carried decisions: framework v2 rehome (aria-ops-core unwind), C2 pak
shape, stitching transport = ambient maintenanceAdmin via
`SuiteApiStitcher` (proven on devel/prod; see
`knowledge/context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md`).

## Vision

- Port unifi from v1 (aria-ops-core) to framework v2: VcfCfAdapter +
  com.vcfcf.adapter.spi roles. REST-only adapter — no JAX-WS/SOAP
  involvement. Note: unifi currently fails compile against the v2
  framework with 71 errors (e.g. `addProperty()` not found) — these are
  the v1-on-v2 API breaks the migration resolves.
- Stitching (if the adapter stitches): rewire to `SuiteApiStitcher`
  ambient mode, same pattern as compliance build 43/44.
- Use the framework default `onDescribe()` (do not hand-roll).
- C2 pak shape: lib/ = vcfcf-adapter-base.jar only.
- Acceptance: devel install, collection parity vs the pre-migration
  baseline (`knowledge/context/investigations/` baseline doc), clean cycles at
  debug interval.
