# vcfcf-adapter-base v2 — re-home onto AdapterBase (drop aria-ops-core)

## Initial prompt (verbatim, 2026-06-09 session)

> still diggin on the java SDK front. I dot think we shoudl plan to unwind
> the aria-ops-core since it's not common - and we reimplement those in
> vcfcf base

(Clarified in-session: "do think we should plan to unwind." Confirmed by
follow-up:)

> I think you said we would use base adapter or something - i.e. not
> reimplement it, but get the functionality from the base class? What gaps
> do we have that we should ask clean froom for?

> I see two steps
> 1> rebuild vcfcf-base to take on aria-ops-core, rebuild synology,
> compliance, unifi. Test in devel.
> 1b> Update template?
> 2> Test vrops-sdk free? This was a hunch since it extends what's there....
> 2b> Update template?

User also supplied the MP certification checklist (work-folder hygiene,
getSocketFactory-only SSL, no System.setProperty, thread exit on stop,
no mutable statics, identifier uniqueness/type-2, status reporting,
relationship consolidation, metric dedup) and asked that IP be respected
throughout — the unwind exists to remove `aria-ops-core` (a BlueMedora/TVS
partner-channel jar no third party uses) from our paks.

## Vision

- `VcfCfAdapter<C>` extends `com.integrien.alive.common.adapter3.AdapterBase`
  directly (was: `UnlicensedAdapter` from aria-ops-core). All TVS types
  (`Resource`, `ResourceCollection`, `Tester`, `Discoverer`, `LiveCollector`,
  `HistoricalCollector`, `TestException`, `CollectionException`,
  `SuiteAPIClient`) disappear from the framework and from adapter (Layer 4)
  code. vcfcf-base provides its own thin SPI + data-carrier types under
  `com.vcfcf.adapter.*` — deliberately NOT mirroring the TVS API shape.
- The orchestration (onCollect/onTest/onDiscover/onConfigure/stop) is
  implemented from the cleanroom behavioral contract:
  `knowledge/context/cleanroom-spec/spec/19-adapterbase-behavioral-contract.md`
  (spec-driven, never from decompiled aria-ops-core — clean-room wall).
- Certification requirements fold into the new orchestrator by design:
  - SSL only via `AdapterBase#getSocketFactory` (replaces
    `ManagedHttpClient.insecureSslContext()`).
  - Metric/property dedup via the SDK's own `MetricDataCache`.
  - Per-resource collection status every cycle; `TestParam.setErrorMsg`/
    `setLocalizedMsg` as the test-failure channel.
  - Cooperative cancellation: `onStopCollection` abort flag honored in
    collect loops; `onDiscard` joins/stops adapter-spawned threads.
  - Consolidated relationships: one `setRelationships(parent, children)`
    per parent per cycle (platform diffs); deltas only when known.
  - No mutable static state; no JVM system-property mutation.
- After the framework lands: migrate compliance → synology → unifi
  (sdk-adapter-author, serial), devel-test each, then ONE template-repo
  update carrying framework v2 + final pak/buildkit shape.
- Pak bundling endgame depends on the C2 install test
  (`knowledge/context/investigations/c2_no_sdk_jar_install_test.md`): if C2 works,
  paks ship zero Broadcom jars; either way `aria-ops-core` is gone.
  `vrops-adapters-sdk` remains compile-time-only and is never publicly
  redistributed outside a pak (survey: no precedent; partner-channel
  artifact).
