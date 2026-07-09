# Design note — compliance adapter v2 migration (build 43)

## Initial prompt

2026-06-09/10 session (verbatim):

> okay we are back and have moved working directories. let's pick up the
> session hand-off, but also take stock that we didn't lose any context
> through unintended leakage. Also when I merged the PR there we a couple
> CI failures.
>
> Then you should be able to finally use the corss workspace request skill
> to make that outstanding request to the cleanroom workspace
> (vcf-mp-cleanroom).
>
> Once that stuff is done I think we can resume our breaking the
> sdk-adapter pathway of bundled depenencies and the other in-flight tasks

User-confirmed decisions carried from the 2026-06-09 session
(`context/session-handoff.md`, now consumed):

1. Unwind aria-ops-core; framework v2 re-homed directly on AdapterBase
   (built — `vcfops_managementpacks/adapter_framework/`, design at
   `knowledge/designs/vcfcf-base-v2-adapterbase-rehome.md`); adapters not yet
   migrated.
2. C2 pak shape — never bundle vrops-adapters-sdk.
3. JAX-WS fix = Option 2: remove JAX-WS entirely from compliance — raw
   SOAP over java.net.http/ManagedHttpClient (multi-version-proof;
   compliance is the only SOAP adapter). Acceptance bar: golden
   comparison vs build-41 results on devel.

## Vision

- Port compliance (the v2 reference implementation) from v1
  (aria-ops-core) to framework v2: implement `com.vcfcf.adapter.spi`
  roles (VcfCfCollector / VcfCfDiscoverer / VcfCfTester) on VcfCfAdapter.
- Replace the vim25/JAX-WS/SAAJ SOAP path with raw SOAP envelopes over
  the framework's ManagedHttpClient — drops vim25.jar,
  vim-vmodl-bindings, jaxws-api, jaxws-rt, javax.xml.soap-api from
  `lib/`. This fixes the prod 9.1 outage: platform pairs javax
  jaxws-api-2.3.1 with jakarta jaxws-rt-4.0.3, parent-first loads the
  wrong ProviderImpl → "not a subtype" every cycle
  (`knowledge/context/investigations/prod_91_jaxws_provider_failure.md`).
- Stitching transport = **Option 1, ambient maintenance credentials**
  (empirically proven on devel 9.0.2 AND prod 9.1,
  `knowledge/context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md`):
  read `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties`,
  decrypt via the platform SDK `com.integrien.alive.common.security.Crypt`
  (MANDATORY reuse — 9.1 collector runs FIPS approved-only; never
  hand-roll the cipher), token acquire/release against
  `https://localhost/suite-api/` as `maintenanceAdmin`, push properties
  via REST. Framework-level transport (promoted/generalized from the
  adapter's dead-code `SuiteApiPropertyPusher`); explicit Suite-API
  credential fields on adapter config as documented fallback (remote
  collectors / missing file).
- Pak stays C2 shape; target version build 43. Devel golden comparison
  vs build 41 gates promotion; prod install then restores 9.1
  collection.
