# C2 classpath route: does an SDK pak install + collect WITHOUT bundling vrops-adapters-sdk.jar?

**Date:** 2026-06-09
**Investigator:** api-explorer
**Instance:** devel (`vcf-lab-operations-devel.int.sentania.net`), VCF Ops 9.x
**Pak under test:** `dist/vcfcf_sdk_compliance.1.0.0.41.pak` → modified copy build 42

---

## Verdict

**C2 WORKS on our pak shape.** A Tier 2 SDK pak installs cleanly, registers its
adapter kind, and runs a full collection cycle with `vrops-adapters-sdk-2.2.jar`
**removed** from `<adapter>/lib/`. `AdapterBase` / `AdapterInterface3` resolve
from the appliance classpath (`common-lib/` + `suite-api/WEB-INF/lib/`) at
runtime. No `installSolution` failure, no `NoClassDefFoundError`, no
`ClassNotFoundException`.

**The historical lesson in `knowledge/context/tier2_architecture.md` should be AMENDED.**
The row asserting that `vrops-adapters-sdk.jar` "must bundle in `<adapter>/lib/`
despite being on shared classpath / installSolution task fails in 14ms with empty
errorMessages" is **not reproducible** on the current build 41 pak shape against
the current devel appliance. See "Reconciling with the historical lesson" below.

---

## Question

Does a Tier 2 SDK pak install and collect without bundling
`vrops-adapters-sdk.jar` in its `lib/` (the "C2 classpath route" described in the
sdk-survey: the appliance ships the SDK jar on its own classpath, and two
Broadcom adapters — Aggregator, SupervisorAdapter — ship paks with zero Broadcom
jars, resolving `AdapterBase` from the appliance classpath at runtime)?

---

## Method — exactly how the pak was modified

Start from `dist/vcfcf_sdk_compliance.1.0.0.41.pak` (latest known-good; previously
installed on devel). One variable isolated: **remove only**
`vcfcf_compliance/lib/vrops-adapters-sdk-2.2.jar` from the inner `adapters.zip`.
`aria-ops-core-8.0.0.jar` and `vcfcf-adapter-base.jar` were **kept** (those classes
are NOT on the appliance classpath, so removing them would confound the test).

Rebuild script: `/tmp/c2test/rebuild.py`. It rewrites both zips entry-by-entry
from the original `ZipInfo` list, which preserves:

- **All 14 zero-byte directory entries** in `adapters.zip` (verified identical to
  the original via `diff` — see Evidence step 0). This respects the hard-won
  "explicit zero-byte directory entries required for every subdirectory" lesson.
- **`manifest.txt` duplicated** inside `adapters.zip`, plus `eula.txt`,
  `default.svg`.

Build number bumped 41 → 42 **everywhere** (respecting the "build number must
increment or platform skips JAR replacement" lesson):

- outer `manifest.txt`: `"version": "1.0.0.41"` → `"1.0.0.42"`
- inner `manifest.txt`: same
- `vcfcf_compliance/conf/version.txt`: `Implementation-Version=0.41` → `0.42`
- output filename: `vcfcf_sdk_compliance.1.0.0.42.pak`

Result: 42 inner entries → 41 (exactly one file dropped), zip integrity clean
(`unzip -t` no errors on both archives).

Install via the factory installer:
`python3 -m vcfops_managementpacks install /tmp/c2test/vcfcf_sdk_compliance.1.0.0.42.pak --profile devel`
(the `/ui/` Struts upload→install→poll path in `vcfops_managementpacks/installer.py`).
This was an **upgrade-in-place** over the already-installed build 41.

---

## Evidence

### Step 0 — pak modification integrity (offline)

```
inner lib/ jars after rebuild (vrops-adapters-sdk GONE, others KEPT):
  vcfcf-adapter-base.jar        38973     <- KEPT
  aria-ops-core-8.0.0.jar       336773    <- KEPT
  javax.xml.soap-api-1.4.0.jar  46111
  jaxws-api-2.1.jar             33428
  jaxws-rt-2.3.1.jar            2604243
  vim-vmodl-bindings-8.0.2.jar  7464633
  vim25.jar                     4313255
  (vrops-adapters-sdk-2.2.jar   REMOVED)

inner directory entries: 14 original == 14 new (diff: IDENTICAL)
inner file count: 42 -> 41 (exactly one dropped)
outer + inner manifest version: "1.0.0.42"
version.txt: Implementation-Version=0.42
zip integrity: no errors detected (both outer pak and inner adapters.zip)
```

### Step (a) — install completes, no installSolution failure

```
[5/6] Triggering install (/ui/solution.action mainAction=install) ...
[6/6] Waiting for install to complete ...
      pakInstalling=True   (x10, ~50s)
      pakInstalling=False  pakUninstallActive=False
OK: Install completed and verified: VCF Content Factory Compliance 1.0.0.42
    (adapterKind='vcfcf_compliance' isInstalled=true)
```

Upload accepted (`pakId='VCFContentFactoryCompliance-10042'`), install ran ~55s
to a clean terminal state. **No 14ms failure, no empty `errorMessages`, no
rejection.**

### Step (b) — adapter kind registers

`GET /suite-api/api/adapterkinds` → `vcfcf_compliance` present
("VCF Content Factory Compliance"). The installer's own post-install verification
(`_verify_adapter_registered`) confirmed `isInstalled=true` via `getIntegrations`.

### Step (c) — collection cycle succeeds

Two pre-existing compliance adapter instances survived the upgrade and ran a
fresh collection. `GET /suite-api/api/resources/{id}/stats/latest`:

| Instance | Stat | Pre-install (baseline) | Post-install |
|---|---|---|---|
| vcf-lab-vcenter-mgmt | collected_resources | 2.0 @ 16:16:50 | 2.0 @ **16:44:29** |
| | collected_metrics | 10.0 | 10.0 |
| | collected_properties | 1.0 | **2.0** |
| | elapsed_collect_time | 16717 ms | 16171 ms |
| vcf-lab-vcenter-wld01 | collected_resources | 2.0 @ 16:16:47 | 2.0 @ **16:44:29** |
| | collected_metrics | 10.0 | 10.0 |
| | collected_properties | 1.0 | **2.0** |
| | elapsed_collect_time | 13496 ms | 15881 ms |

Both instances: `resourceStatus=DATA_RECEIVING`, `resourceState=STARTED`.
The collection timestamp advanced (16:16 → 16:44) and the adapter is doing real
work — querying vCenter, pushing metrics/properties. If the SDK classes were
absent the collector would throw at class-load and never collect.
`Instance Attributes|collected_*` is the API surface for "Number of Objects
Collected".

### Step (d) — collector logs: no classloading errors

Via SSH (`root@<devel>`), two fresh adapter logs written post-restart
(`ComplianceAdapter_3235.log`, `ComplianceAdapter_3240.log`):

```
grep -c "NoClassDefFoundError|ClassNotFoundException" ComplianceAdapter_3240.log -> 0
grep -c "NoClassDefFoundError|ClassNotFoundException" ComplianceAdapter_3235.log -> 0
grep "(ClassNotFound|NoClassDef).*(adapter3|integrien|AdapterBase|AdapterInterface3)"
   across all ComplianceAdapter logs -> (no matches)
collector wrapper logs, compliance/adapter3/integrien linkage errors -> (none)
```

The newest log's last entry (`2026-06-09T21:44:29.298Z` UTC = 16:44 local) is the
adapter's own business-logic WARN ("Profile VMware_SCG_9.0 declares 37 vim_property
control instances ... declared-but-unreadable") — a coverage signal, **not** a
classloading error — emitted from
`com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn`. The adapter class
loaded, ran, and logged normally with no SDK jar in its `lib/`.

---

## Reconciling with the historical lesson

The `tier2_architecture.md` table (dated 2026-05-19) claims bundling
`vrops-adapters-sdk.jar` is mandatory, with failure signature "installSolution
fails in 14ms with empty errorMessages." This test does **not** reproduce that.

The most likely explanation for the original failure being misattributed:

- The 2026-05-19 lesson predates the directory-entry fix and several other pak
  structural fixes (the same table documents the "explicit zero-byte directory
  entries" requirement, also dated 2026-05-19). A 14ms-with-empty-errorMessages
  `installSolution` failure is the classic signature of the **stage/extract**
  phase choking on pak *structure* (missing directory entries → `extractFiles()`
  throws), **not** of a runtime classpath problem — runtime classpath issues
  surface as `NoClassDefFoundError` during *collection*, long after install
  succeeds. The early build that "fixed it by adding the SDK jar" almost
  certainly fixed an unrelated structural defect in the same rebuild and
  attributed the cure to the jar.
- The survey's class-level analysis already shows `AdapterBase` exists **only** in
  `vrops-adapters-sdk*.jar` and is present on the appliance classpath
  (`common-lib/`, `suite-api/WEB-INF/lib/`), and that the two Broadcom C2 adapters
  ship zero Broadcom jars. Our result is consistent with that and with the survey's
  load-bearing conclusion: "because the appliance already provides the SDK on the
  classpath, a native adapter does not have to bundle it."

**Recommendation:** amend the `tier2_architecture.md` "Pak format — hard-won
lessons" row for `vrops-adapters-sdk.jar` from "must bundle" to "optional —
empirically resolves from the appliance classpath (C2 route); bundling pins a
known build but is not required for install or collection (proven build 42 on
devel 2026-06-09)." The canonical pak-structure listing's `lib/` line for
`vrops-adapters-sdk-*.jar` should be marked optional. (Documentation change for
the `tooling`/orchestrator to action — api-explorer does not edit that file's
lesson table as part of this run beyond recommending it.)

**Caveat retained:** C2 takes whatever SDK build the appliance ships (here a
2025-12-30 build per the survey). The survey measured the SPI as additively
stable across a 6-year skew, so this is low-risk, but a C1 pak that pins a known
build remains a legitimate choice where build determinism matters. The
`aria-ops-core` and `vcfcf-adapter-base` jars are **not** appliance-resident and
must always be bundled — this test does not change that.

---

## Instance state after test

devel currently runs **build 42** (the C2 test pak), installed and healthy: both
compliance adapter instances `DATA_RECEIVING`/`STARTED`, collecting on schedule.
Install succeeded, so the failure-remediation path (reinstall build 41) was not
needed. Build 42 is functionally identical to 41 minus the redundant SDK jar, so
the instance is in a realistic working state. If a downgrade to the canonical
build 41 is desired for tidiness, reinstall `dist/vcfcf_sdk_compliance.1.0.0.41.pak`
— but it is not required for health.

The unmodified `dist/...41.pak` was never altered; the modified pak lives only in
`/tmp/c2test/`.

---

## Reproduction artifacts (ephemeral, /tmp)

- `/tmp/c2test/rebuild.py` — pak modifier (drop SDK jar, bump 41→42)
- `/tmp/c2test/probe.py` — adapterkind + instance state
- `/tmp/c2test/collstat.py` — collection stats (objects collected)
- `/tmp/c2test/vcfcf_sdk_compliance.1.0.0.42.pak` — the C2 test pak

## Prod confirmation (2026-06-09, hand-installed by Scott)

Build 42 (the no-SDK-jar variant from this test) was hand-installed on the
prod instance from `tmp/vcfcf_sdk_compliance.1.0.0.42.pak`: install and
adapter-kind validation succeeded. Collection cycle not yet explicitly
verified on prod (devel verified collection fully). C2 verdict now rests on
two independent instances.
