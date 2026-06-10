# Session Handoff — 2026-06-09 (framework v2 rehome, C2 verdict, 9.1 JAX-WS root cause)

Transient working-state note so a fresh session can pick up cold. Point the
new session here. Not durable knowledge — delete once consumed.

## HEADLINE

Big day: aria-ops-core unwind decided AND framework v2 built; C2 (no
vrops-adapters-sdk in pak lib/) **proven on devel 9.0.2 and prod 9.1**;
all 4 Codex PR-#6 findings fixed; buildkit made jar-free. **Everything is
uncommitted** on `feature/sdk-paks-independent-repos` (PR #6 open). Prod
compliance is **down** with a fully-diagnosed 9.1 JAX-WS collision; fix
decided (drop JAX-WS → raw SOAP) but not yet built. Compliance v2
migration is **blocked on one open question** (Suite API ambient auth).

## ⚠️ UNCOMMITTED WORKING TREE

All of today's work is `M`/`??` in git: framework v2 rewrite
(`adapter_framework/`), sdk_builder C2 bundling, buildkit jar-free, Codex
workflow/script fixes, cleanroom spec drop (spec/19 + survey), four new
context docs, design note. Commit before anything destructive. Suggested
grouping: (1) cleanroom spec sync, (2) framework v2 + migration guide +
arch doc, (3) sdk_builder C2 + lesson amendment, (4) Codex fixes +
buildkit, (5) investigations + design note + handoff.

## Decisions made today (user-confirmed)

1. **Unwind aria-ops-core**; reimplement its layer inside vcfcf-base on
   raw AdapterBase. DONE for framework; adapters not yet migrated.
2. **C2 pak shape** — don't bundle vrops-adapters-sdk (proven both
   instances; old "must bundle" lesson was misattribution — see
   `context/investigations/c2_no_sdk_jar_install_test.md`).
3. **JAX-WS fix = Option 2**: remove JAX-WS entirely from compliance —
   raw SOAP over java.net.http/ManagedHttpClient (multi-version-proof;
   compliance is the only SOAP adapter). NOT YET IMPLEMENTED.
   Acceptance bar: golden comparison vs build-41 results on devel.
4. **CI jar source = private repo + token**:
   `sentania-labs/vcf-content-factory-sdk-runtime` created (EMPTY — jar
   push was staged then put on hold; clone in /tmp). User must mint
   fine-grained read PAT for adapter-repo CI secrets when resumed.
5. **Buildkit release `sdk-buildkit-v1` stays up** (user call) until the
   jar-free replacement is published — NOTE it currently exposes all
   Broadcom jars publicly (IP exposure documented in survey); replace ASAP.
6. **No factory agent ever enters the cleanroom workspace.** User is
   moving this workspace into vault/PKA so cross-workspace requests to
   the cleanroom go direct (`/request-crossworkspace`, target TBD).
7. Auto-memory confirmed off (`autoMemoryEnabled: false`, no memory dirs).

## OPEN QUESTION blocking compliance migration (task #1)

How does the v1 injected SuiteAPIClient authenticate (no operator creds
in config — "platform session")? v2 needs that mechanism or config
fields. Two tracks, NEITHER LAUNCHED yet:
- **Empirical (api-explorer, read-only)**: devel build 42 runs v1 stitcher
  successfully RIGHT NOW — observe its Suite API principal via
  audit/access logs, collector env/token files. Brief was offered to user;
  ready to launch.
- **Cleanroom ask** (drafted, in conversation): behavioral contract of the
  wrapper client's auth flow; send via /request-crossworkspace once PKA
  wiring exists, or user ferries it.
If ambient mechanism is wrapper-private → fallback: Suite API credential
fields on adapter config + framework-level REST pusher (the existing
dead-code `SuiteApiPropertyPusher` is the transport to promote).

## Live instance state

- **devel** (9.0.2, `VCFOPS_DEVEL_*`): compliance build 42 (C2 shape,
  still v1 code w/ aria-ops-core) healthy & collecting. lib/ verified
  byte-clean (no leftovers).
- **prod** (9.1, `VCFOPS_PROD_*`; root SSH creds added to .env today as
  `VCFOPS_PROD_SSH_USER/_PASSWORD`): compliance build 42 installed,
  **collection DOWN since install** — javax/jakarta JAX-WS collision,
  fully diagnosed in
  `context/investigations/prod_91_jaxws_provider_failure.md`
  (platform jaxws-api-2.3.1 + jakarta jaxws-rt-4.0.3; parent-first loads
  wrong ProviderImpl → "not a subtype"). Never collected on 9.1; not a
  C2 regression. Will be fixed by build 43 (v2 + raw SOAP).
- QA instance exists in .env (`VCFOPS_QA_*`) — untouched today.

## Task board (harness tasks #1–#7)

#1 resume compliance v2 migration — BLOCKED on Suite-API-auth question;
   when unblocked, fold IN: v2 SPI port (full mechanical recipe + 5
   migration-guide corrections are in the stopped author agent's report,
   summarized in conversation; guide at context/framework_v2_migration.md
   still needs those 5 corrections applied), raw-SOAP rewrite (drops
   vim25/jaxws/saaj jars), stitcher rewire to chosen transport.
#2 review + devel install + push compliance (golden comparison vs 41).
#3/#4 synology, unifi migrations (REST-only; no JAX-WS issue; stitching
   transport applies to both).
#5 DONE (Codex fixes + jar-free buildkit, uncommitted).
#6 wire private-repo jar fetch into 3× build-pak-on-tag.yml + template;
   publish jar-free buildkit; tag v* on adapter repos; CI green ×3; then
   replace/remove old sdk-buildkit-v1 release.
#7 single template-repo update at the end (v2 + C2 + CI).

## Key facts a fresh session must not re-derive

- Survey + spec/19 (cleanroom, synced into context/cleanroom-spec/):
  third parties bundle only vrops-adapters-sdk (5/5, AdapterBase direct,
  no attribution); SDK jar has NO license, gated-internal-only → no
  public out-of-pak distribution, partner-channel grant non-inheritable;
  alive_* never bundled by anyone; SPI additively stable 2019→2025;
  framework v2 compile classpath = vrops-adapters-sdk-2.2.jar ONLY.
- vcfcf-adapter-base v2: extends AdapterBase; own SPI under
  com.vcfcf.adapter.spi; MetricDataCache reused; platform SSL via
  getSocketFactory (allowInsecure = documented opt-out); cooperative
  cancellation; MetricPusher property-flag bug fixed (v1 silently
  dropped properties). 4 [INFER] caveats listed in agent report +
  spec/19 §8/§1 open items — DEBUG collect capture on migrated
  compliance will upgrade them.
- 8.18 compatibility: NOT verified; java.net.http + -source 11 require
  JDK11+ collectors; check 8.x collector JVM before promising.
- MP certification checklist (user-supplied, Broadcom-internal): do NOT
  commit verbatim to this public repo; distill-in-own-words if codifying.
- Factory repo is PUBLIC — mind what lands in context/.

## Where everything is

- Design note: designs/vcfcf-base-v2-adapterbase-rehome.md
- Migration guide (needs 5 corrections): context/framework_v2_migration.md
- Investigations: context/investigations/{c2_no_sdk_jar_install_test,
  prod_91_jaxws_provider_failure}.md
- Cleanroom drop (synced): context/cleanroom-spec/ (spec/19, survey under
  analysis/sdk-survey/)
- C2 test pak: tmp/vcfcf_sdk_compliance.1.0.0.42.pak (also installed both
  instances)
- Private jar repo: github.com/sentania-labs/vcf-content-factory-sdk-runtime
  (empty; staged clone in /tmp/sdk-runtime-*)
