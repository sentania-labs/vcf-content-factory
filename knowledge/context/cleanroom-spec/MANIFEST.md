# MP Java SDK — transfer bundle

**Generated**: 2026-06-09 from `vcf-mp-cleanroom` (Mraize).
**Purpose**: everything VCF-CF needs for the **Tier 2 (Native / Java SDK)**
pipeline — the reverse-engineered SPEC plus the supporting analysis
conclusions.

## Clean-room boundary
This bundle contains **conclusions only** — SPEC documents and analysis
notes describing the platform's API surface, lifecycle contracts, and
observed patterns. It deliberately **excludes** `analysis/decompiled/`,
every `.pak`/`.jar`/binary, and any decompiled source. Nothing here is
copied implementation. (Guardrail: the bundle is asserted `.md`-only at
build time.)

## What to read first (Java-SDK core)
1. `spec/99-summary-and-vcf-cf-recommendations.md` — synthesis + recommendations
2. `spec/15-tier2-handoff-for-vcf-cf.md` — the Tier 2 handoff
3. `spec/01-adapter-lifecycle.md` — entry contract + AdapterBase helpers
4. `spec/19-adapterbase-behavioral-contract.md` — **NEW (2026-06-09)** step-level
   onTest/onDiscover/onCollect/onConfigure/stop contract for an orchestrator
   built directly on AdapterBase
5. `analysis/sdk-survey/third-party-broadcom-jar-redistribution-survey-2026-06-09.md`
   — **NEW** which Broadcom jars third parties bundle, SDK internals, the
   C2 "zero-Broadcom-jar" route, and the 2019→2025 API-stability diff

## Contents

### `spec/` — the SPEC (the transferable artifact)
- Core native/Java-SDK: `00` overview, `01` lifecycle, `02`/`02a` describe.xml+xsd,
  `03` credentials, `04` actions, `05` resource model, `06` metrics/units,
  `07` relationships, `08` alerts/symptoms, `09` capacity/policy,
  `13` classloading/classpath, `14` UI/operational surfaces,
  `16` install + signing, `17` VCF-CF framework design guidance,
  `18` pak content bundle, `19` AdapterBase behavioral contract,
  `99` summary + recommendations, `triage-report-2026-05-15`.
- MPB context (Tier 1, included for cross-reference — referenced by the
  native sections): `10` MPB builderfile schema, `11` MPB designer wire
  format, `12` MPB handoff.

### `analysis/sdk-survey/`
- `third-party-broadcom-jar-redistribution-survey-2026-06-09.md` — redistribution
  practice (5 paks / 4 vendors), `vrops-adapters-sdk.jar` internals + license
  posture, the `alive_*` boundary, the C2 escape hatch, and the public-API diff.
- `v2.2-public-api.md` — the SDK v2.2 public API surface notes.

### `analysis/per-adapter/` — RE conclusion notes (context; no source)
vim, NSXTAdapter3, vmwarevi_adapter3, mongodb (BlueMedora/TVS reference),
VCFAutomation, mpb-adapter (+ insights-for-vcf-cf), vcf-ops-data-sdk, and
two bulk survey notes.

### `analysis/pak-signing-chain.md` — pak signature/validation analysis.

## Decision-grade takeaways (see survey + spec/19 for detail)
- **C2 route**: the appliance ships `vrops-adapters-sdk.jar` on its own
  classpath, so a native pak can bundle **zero Broadcom jars** — sidestepping
  the in-pak redistribution question. (spec/13 + survey)
- **License lives in the partner channel, not the jar**: the SDK jar carries
  no license/NOTICE and only existed in gated internal Artifactory; any
  redistribution right is a private partner grant, non-inheritable by a
  non-partner. **Legal call, separate from this analysis.** (survey)
- **API is additively stable 2019→2025**: `AdapterInterface3` surface
  identical; `AdapterBase` only gains methods. (survey)
- **Never bundle `alive_common`/`alive_platform`** — appliance-resident
  platform jars; the only redistributed artifact is `vrops-adapters-sdk.jar`.

## Open items (would upgrade INFER→FIELD)
- `MetricDataCache` ctor int-params + `flushCachedData(boolean)` exact semantics.
- One live DEBUG collect-cycle capture → confirms onCollect step order and
  whether per-resource status is required every cycle.
- Pure Storage pak un-fetched (third-party population is Dell-heavy).
