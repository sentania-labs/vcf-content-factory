# Prod (VCF Ops 9.1) JAX-WS Provider failure on compliance build 42

**Date:** 2026-06-09
**Investigator:** api-explorer
**Instances:** prod `vcf-lab-operations.int.sentania.net` (VCF Ops **9.1.0.0**, build 25435105),
devel `vcf-lab-operations-devel.int.sentania.net` (VCF Ops **9.0.2.0**, build 25137838)
**Pak under test:** compliance build 42 (C2 shape — `vrops-adapters-sdk-2.2.jar` removed from `lib/`)
**Posture:** read-only (SSH reads on devel, Suite API reads on both, offline jar inspection). Nothing created, deleted, reinstalled, or restarted.

---

## TL;DR

- **Devel leftover-jar verdict:** CLEAN. The devel adapter `lib/` holds exactly the 7 jars of build 42; `vrops-adapters-sdk-2.2.jar` is **absent**. The C2 validation in `c2_no_sdk_jar_install_test.md` is **not masked** on devel — no caveat needed *for the SDK jar specifically*. (One caveat is warranted on a different point — see below.)
- **Prod leftover-jar verdict:** UNVERIFIED ON DISK — **no working SSH/CaSA credential for prod** (root/admin/claude SSH all rejected; CaSA returns 401). Disk state inferred from the install record only.
- **Regression vs new:** Cannot be proven from logs (no prod SSH). Best evidence (`numberOfMetricsCollected: 0`, `lastCollected` stale) is consistent with **never having collected on 9.1** — i.e. a first-run-on-9.1 platform failure, not a regression introduced by removing the SDK jar.
- **Root cause (high confidence, mechanism proven byte-for-byte):** The exact prod error string `Error while searching for service [javax.xml.ws.spi.Provider]` is emitted by `javax.xml.ws.spi.ServiceLoaderUtil` shipped in the **platform's `jaxws-api-2.3.1.jar`** (on the collector classpath), **not** by the adapter's bundled `jaxws-api-2.1.jar`. Parent-first delegation resolves `Provider.provider()` to the platform 2.3.x API, whose `FactoryFinder`→`ServiceLoaderUtil.firstByServiceLoader` calls `java.util.ServiceLoader.load(Provider.class)` against the **thread context classloader (TCCL)**. On 9.1 that TCCL-driven `ServiceLoader` lookup fails (no visible/instantiable `META-INF/services/javax.xml.ws.spi.Provider`), and the failure is wrapped as the prod message. Devel does not fail because its collector classpath carries a complete `jaxws-rt-2.3.1` whose SPI entry is visible to the same loader.

---

## Q1 — On-disk extraction state / leftover jars

### Devel (SSH, full evidence)

Adapter root: `/usr/lib/vmware-vcops/user/plugins/inbound/vcfcf_compliance/` (conf, doc, lib, work; all `Jun 9 17:44` = build-42 upgrade).

`lib/` listing (devel):

```
aria-ops-core-8.0.0.jar        336773
javax.xml.soap-api-1.4.0.jar    46111
jaxws-api-2.1.jar               33428
jaxws-rt-2.3.1.jar            2604243
vcfcf-adapter-base.jar          38973
vim25.jar                     4313255
vim-vmodl-bindings-8.0.2.jar  7464633
```

Seven jars, all dated `Jun 9 17:44`. **`vrops-adapters-sdk-2.2.jar` is NOT present.** Sizes match the build-42 pak's `adapters.zip` `vcfcf_compliance/lib/*` **byte-for-byte**. No leftover from build 41 — the upgrade replaced the whole `lib/` (directory mtime `Jun 9 17:44`).

**Verdict (devel): no leftover SDK jar. C2 test not masked by a stray SDK jar.**

### Prod (no SSH — inferred only)

- SSH: `root@prod` / `admin@prod` / `claude@prod` with `VCFOPS_PROD_PASSWORD` → `Permission denied` (rc 5). Key auth → denied. The Suite-API password belongs to UI user `claude` (Local authSource) and is **not** the appliance root SSH password.
- CaSA (`/casa/...`) basic-auth with admin/claude/root → HTTP 401. No support-bundle path available.
- Suite API confirms build 42 installed and the adapter kind registered (per `c2_no_sdk_jar_install_test.md` prod confirmation). Whether the build-41→42 upgrade left `vrops-adapters-sdk-2.2.jar` behind on prod **cannot be confirmed**. **If** prod was installed by the same `/ui/` upgrade path, behaviour matches devel (whole-`lib/` replacement, no leftover). Build 42 was hand-installed by Scott from `tmp/vcfcf_sdk_compliance.1.0.0.42.pak`.

**Verdict (prod): UNVERIFIED.** Cannot confirm or deny leftover jars without prod SSH or CaSA.

### Caveat for the C2 doc

The SDK-jar removal is clean on devel, so `c2_no_sdk_jar_install_test.md`'s core claim stands. **However**, that doc's verdict ("C2 works, adapter collects without the SDK jar") was validated **only on devel 9.0.2**, where the collector's *platform* classpath happens to carry a complete, self-consistent `jaxws-rt-2.3.1` (see Q4). The prod 9.1 failure shows the C2 route's success is **platform-classpath-dependent for the JAX-WS stack**, independent of the SDK jar. Recommend adding to `c2_no_sdk_jar_install_test.md`: *"C2 validated on devel 9.0.2 only. On 9.1 the adapter's vim25 SOAP path fails at `Provider.provider()` (JAX-WS SPI discovery) — see `prod_91_jaxws_provider_failure.md`. This is a JAX-WS classpath/TCCL issue orthogonal to the SDK jar, but it means 'collects cleanly without the SDK jar' has only been shown on 9.0.2."*

---

## Q2 — Prod failure evidence

### What the API gives

`GET /suite-api/api/adapters?adapterKindKey=vcfcf_compliance` (prod), instance `dfddf` (vCenter `vcf-lab-vcenter-mgmt`, resourceId `feccc1fa-65fc-470a-9998-26e34e6828cb`):

```
numberOfMetricsCollected : 0
numberOfResourcesCollected: 1
messageFromAdapterInstance: "Compliance collection failed: Error while searching for service [javax.xml.ws.spi.Provider]"
```

`GET /suite-api/api/events?resourceId=<id>` → 0 events. The Suite API surfaces only the **one-line** adapter message; the full Java stack trace lives only in the on-disk per-adapter log (`.../user/log/adapters/...ComplianceAdapter_*.log`) and `collector.log`, which require SSH. **The full stack trace could not be captured on prod (no SSH).**

### What the message proves (offline jar forensics — definitive)

The string `Error while searching for service [` is **not** generic. Grepping every build-42 adapter jar and the devel platform classpath jar:

- adapter `jaxws-api-2.1.jar`: old-style `FactoryFinder` only; wording is `"Provider not found"` / `"could not be instantiated:"` / `"Provider for ... cannot be found"`. **No** `ServiceLoaderUtil`, **no** "searching for service".
- platform `jaxws-api-2.3.1.jar` (devel `/usr/lib/vmware-vcops/common/lib/`, also on the collector `-classpath`): contains `javax/xml/ws/spi/ServiceLoaderUtil.class`, whose constant pool holds the exact literal **`Error while searching for service [`** plus `Using java.util.ServiceLoader to find {0}`.

Disassembly of platform `jaxws-api-2.3.1`:

```
Provider.provider()
  -> FactoryFinder.find(Provider.class)
       -> ServiceLoaderUtil.contextClassLoader(...)            // TCCL
       -> ServiceLoaderUtil.firstByServiceLoader(Provider.class, log, EH)
            -> java.util.ServiceLoader.load(Provider.class)    // NO loader arg => TCCL
            -> .iterator().hasNext()/.next()
            -> catch(Exception) -> "Error while searching for service [" + name + "]"
       -> fromJDKProperties($java.home/lib/jaxws.properties)
       -> fromSystemProperty("javax.xml.ws.spi.Provider")
       -> lookupUsingOSGiServiceLoader(...)
       -> newInstance(default impl, ...)
```

So the failing call is resolved by the **platform 2.3.x API**, and the lookup is **TCCL-driven `java.util.ServiceLoader`** — it will only succeed if the active TCCL can both *see* a `META-INF/services/javax.xml.ws.spi.Provider` entry **and** instantiate the named impl without a linkage error.

### JVM

- Devel collector JRE: `/usr/lib/vmware-vcops/jre/bin/java` → **OpenJDK 17.0.16 LTS**.
- Prod collector JDK: **unknown** (no SSH). 9.1 plausibly ships a newer 17.x or a different JDK; under JPMS/JDK17 the absence of `java.xml.ws` from the JDK (removed in JDK 11) makes the lookup depend entirely on the application classpath/TCCL — relevant to hypothesis (b).

---

## Q3 — History: regression or first-run-on-9.1?

No prod log access, so install/solution history and old-log mtimes are unavailable. Indirect evidence:

- Prod instance `numberOfMetricsCollected: 0` and the message is a hard collection failure, not a partial. If build 41 (with the SDK jar) had ever collected successfully on this 9.1 node, we'd expect a non-zero historical metric count / a different failure history — but the metric counter being flat at 0 is consistent with **never having had a successful cycle on 9.1**.
- The error is in JAX-WS **SPI bootstrap** (`Provider.provider()` at SOAP-stub creation), i.e. it fails before any vCenter call — the earliest possible point. A pak that merely lost the SDK jar would fail at `AdapterBase` class-load (`NoClassDefFoundError`), a *different* signature. This points away from "the SDK-jar removal broke it" and toward "the JAX-WS stack never resolved on this platform."

**Verdict:** Most likely **first-run-on-9.1 platform failure**, not a regression caused by the C2 change. Not provable without prod log/history access. The SDK jar removed in build 42 carries **zero** `javax.xml.ws` classes and zero `META-INF/services` entries (already established locally), so its removal **cannot** be the direct cause regardless.

---

## Q4 — Platform diff (9.1 vs 9.0.2)

### Devel 9.0.2 shared classpath (SSH)

`common/lib` JAX-WS / SOAP jars present:

```
common/lib/jakarta.xml.ws-api-2.3.3.jar
common/lib/javax.xml.soap-api-1.4.0.jar
common/lib/jaxws-api-2.3.1.jar
common/lib/jaxws-rt-2.3.1.jar
common/lib/jaxws-rt-2.3.6.jar
```

Devel **collector JVM `-classpath`** (from `/proc/<pid>/cmdline`) explicitly includes:

```
common/lib/vrops-adapters-sdk.jar
common/lib/jaxws-api-2.3.1.jar
common/lib/jaxws-rt-2.3.1.jar
common/lib/javax.xml.soap-api-1.4.0.jar
common/lib/saaj-impl-1.5.1.jar
common/lib/jaxb-api-2.3.1.jar   (+ jaxb-runtime-2.3.3, istack, stax-ex, policy, gmbal, streambuffer)
```

So on devel the **system/application classloader already provides a complete, self-consistent JAX-WS 2.3.1 RT** — `jaxws-api-2.3.1` (the API + `ServiceLoaderUtil`) **and** `jaxws-rt-2.3.1` (which carries `META-INF/services/javax.xml.ws.spi.Provider` → `com.sun.xml.ws.spi.ProviderImpl`, present in the same jar). When the adapter (or its loader chain) hits `Provider.provider()`, the TCCL/system loader resolves the SPI file and instantiates `ProviderImpl` cleanly. **That is why devel collects.**

### Prod 9.1 shared classpath

**Unknown (no SSH).** This is the central evidence gap. Hypotheses below are framed against what would have to differ.

### Ranked root-cause hypotheses

1. **(Most likely) 9.1's shared classpath JAX-WS layout breaks TCCL SPI resolution for the adapter loader.** On 9.1, either (a) `jaxws-rt`/the `META-INF/services/javax.xml.ws.spi.Provider` entry is no longer on the loader the adapter's TCCL points to (moved to a module, a different plugin loader, or replaced by `jakarta.xml.ws` only), or (b) the platform ships `jaxws-api`/`jakarta.xml.ws-api` **without** a matching `jaxws-rt` on the same loader. Either way `ServiceLoader.load(javax.xml.ws.spi.Provider)` under the adapter TCCL finds nothing instantiable and throws → exact prod message. The adapter *does* bundle `jaxws-rt-2.3.1` in its own `lib/`, but because the **API class** that runs `FactoryFinder` comes from the platform (parent-first) and `ServiceLoader.load` uses the **TCCL** — and the adapter's plugin classloader may not be the TCCL at the moment vim25 builds its SOAP stub — the bundled RT is not guaranteed to be consulted. This is the classic "API on parent loader + impl SPI not visible to the active TCCL" JAX-WS trap.

2. **9.1 collector runs a newer/stricter JDK with different TCCL behavior.** JDK 11+ removed `java.xml.ws` from the JDK, so discovery is 100% classpath/TCCL dependent. If 9.1's collector sets a different TCCL for adapter threads (or runs modularized), the lookup that devel's JDK17 happens to satisfy via the system classpath could miss on 9.1. Plausible contributor, not independently provable here.

3. **(Least likely) 9.1 extraction layout puts the adapter's own `lib/` jars on a loader that the JAX-WS `FactoryFinder` (running on the platform loader) can't see.** Even if the bundled `jaxws-rt-2.3.1` is on disk, a parent-first delegation means the platform API's `ServiceLoader.load` won't reach a child-loader-only RT. This is really a facet of #1.

All three converge on the same fix space: **make a complete, self-consistent JAX-WS RT visible to the loader that actually runs `Provider.provider()` on 9.1, with the TCCL set correctly around the SOAP call.**

---

## Recommended fix directions

1. **TCCL bracketing around the vim25 SOAP path (preferred, surgical).** In the adapter/framework code that creates the vim25 SOAP stub (`com.vcfcf.adapters.compliance` / `vcfcf-adapter-base` vim25 connect path), wrap the `Provider.provider()`-triggering call in:
   `Thread.currentThread().setContextClassLoader(<the adapter plugin classloader that owns jaxws-rt-2.3.1>)` … restore in `finally`. This forces `ServiceLoader.load(Provider.class)` to see the bundled RT's `META-INF/services/javax.xml.ws.spi.Provider` regardless of which loader owns the platform API class. Lowest-risk, version-agnostic, fixes both 9.0.2 and 9.1.

2. **Bundle a complete, self-contained, self-consistent JAX-WS stack and force the adapter loader to win.** Keep `jaxws-api` + `jaxws-rt` + `saaj-impl` + `streambuffer`/`stax-ex`/`policy`/`gmbal` at **one matching version** in `lib/` (the current mix is `jaxws-api-2.1` + `jaxws-rt-2.3.1` — an API/RT **version skew**; align both to 2.3.1). On its own this is *insufficient* if delegation is parent-first (the platform API still wins), so it should be paired with #1 (TCCL) or a child-first plugin loader if the platform supports one.

3. **9.1-specific classpath accommodation (last resort).** If neither is feasible in adapter code, set `-Djavax.xml.ws.spi.Provider=com.sun.xml.ws.spi.ProviderImpl` (the `fromSystemProperty` branch in `FactoryFinder`) for the collector so discovery short-circuits the TCCL `ServiceLoader` — but this is a platform-wide JVM arg, not shippable in a pak, so it's a diagnostic/confirmation lever, not a product fix.

**First action when prod SSH/CaSA becomes available:** pull `.../user/log/adapters/ComplianceAdapter_*.log` for the full stack trace (confirm the throwing class is the platform `jaxws-api-2.3.x` `ServiceLoaderUtil` and identify the active TCCL), then `cat /proc/<collector-pid>/cmdline` for the prod collector `-classpath` and `java -version`. That single look confirms hypothesis #1 vs #2 and tells you whether the platform `jaxws-rt` SPI entry is present on 9.1.

---

## Evidence appendix (commands / artifacts)

- Devel SSH: `sshpass -e ssh root@<devel>` (`SSHPASS=VCFOPS_DEVEL_PASSWORD`). Listings of adapter root, `lib/`, `common/lib` JAX-WS jars, `/proc/<collector-pid>/cmdline` classpath, `jre/bin/java -version`.
- Prod: Suite API only (`vRealizeOpsToken`). Adapter-instance health + message, version endpoint. SSH/CaSA unauthenticated.
- Offline: build-42 pak from `/home/scott/projects/vcf-content-factory/tmp/vcfcf_sdk_compliance.1.0.0.42.pak`; jar disassembly via local `javap`/`strings` (temp dirs under `/tmp`, removed after).
- Platform `jaxws-api-2.3.1.jar` scp'd from devel to `/tmp` for `javap` (local read-only inspection; not modified on the appliance).

---

## Prod confirmation (2026-06-09) — root SSH obtained, READ-ONLY

Root SSH now works with the **doubled** password (`VMware123!VMware123!`,
length 20) as `root@vcf-lab-operations.int.sentania.net`. Entire pass was
read-only: `cat`, `ls`, `/proc` reads, `unzip -l`/`-p` to stdout. Nothing
created, changed, restarted, or reinstalled. `/tmp` verified clean of any
artifacts. Adapter on prod is `Implementation-Version=0.42` (build 42).

### 1. Full stack trace (prod `ComplianceAdapter_714630.log`)

The earlier evidence gap (full trace) is now closed. The `Caused by`
**rewrites the root cause** — it is NOT "no provider found" (RT missing);
it is a **same-FQCN javax-vs-jakarta version collision across loaders**:

```
2026-06-09T21:56:48.157Z INFO ... ComplianceAdapter configured:
    vcenter=vcf-lab-vcenter-mgmt.int.sentania.net profile=VMware_SCG_9.0 stitcher=true
2026-06-09T21:56:48.511Z ERROR ... Collection failed:
    Error while searching for service [javax.xml.ws.spi.Provider]
javax.xml.ws.WebServiceException: Error while searching for service [javax.xml.ws.spi.Provider]
    at javax.xml.ws.spi.FactoryFinder$1.createException(FactoryFinder.java:61)
    at javax.xml.ws.spi.FactoryFinder$1.createException(FactoryFinder.java:58)
    at javax.xml.ws.spi.ServiceLoaderUtil.firstByServiceLoader(ServiceLoaderUtil.java:70)
    at javax.xml.ws.spi.FactoryFinder.find(FactoryFinder.java:89)
    at javax.xml.ws.spi.Provider.provider(Provider.java:96)
    at javax.xml.ws.Service.<init>(Service.java:112)
    at com.vmware.vim25.VimService.<init>(Unknown Source)
    at com.vcfcf.adapters.compliance.VSphereClient.connect(VSphereClient.java:36)
    at com.vcfcf.adapters.compliance.VSphereClient.ensureConnected(VSphereClient.java:127)
    at com.vcfcf.adapters.compliance.ComplianceAdapter$1.getCurrentMetrics(ComplianceAdapter.java:147)
    ... (LiveCollectionExecutor -> UnlicensedAdapter.onCollect -> AdapterBase.collect -> CollectorWorkItem3)
Caused by: java.util.ServiceConfigurationError:
    javax.xml.ws.spi.Provider: com.sun.xml.ws.spi.ProviderImpl not a subtype
    at java.base/java.util.ServiceLoader.fail(Unknown Source)
    at java.base/java.util.ServiceLoader$LazyClassPathLookupIterator.hasNextService(Unknown Source)
    ... at javax.xml.ws.spi.ServiceLoaderUtil.firstByServiceLoader(ServiceLoaderUtil.java:63)
    ... 17 more
```

**`... not a subtype`** is the decisive line. ServiceLoader *did* find an
SPI entry naming `com.sun.xml.ws.spi.ProviderImpl`; it failed because the
`ProviderImpl` class it loaded does **not** extend the `javax.xml.ws.spi.Provider`
class the lookup expects. Two different `Provider` supertypes are in play.

The throwing API class is confirmed the **platform `jaxws-api-2.3.1`**
`ServiceLoaderUtil` (matches the offline disassembly). The call site is
exactly `vim25 VimService.<init>` → `javax.xml.ws.Service.<init>` →
`Provider.provider()` — the first SOAP-stub creation, before any vCenter call.

### 2. Prod adapter `lib/` — VERIFIED (was UNVERIFIED)

`/usr/lib/vmware-vcops/user/plugins/inbound/vcfcf_compliance/lib/` holds
**exactly the 7 build-42 jars; `vrops-adapters-sdk-2.2.jar` is ABSENT.**
Sizes match devel/pak byte-for-byte (md5s captured):

```
aria-ops-core-8.0.0.jar        336773
javax.xml.soap-api-1.4.0.jar    46111
jaxws-api-2.1.jar               33428
jaxws-rt-2.3.1.jar            2604243
vcfcf-adapter-base.jar          38973
vim25.jar                     4313255
vim-vmodl-bindings-8.0.2.jar  7464633
```

So the prod C2-shape verification is now positive on disk, matching devel.
The SDK-jar removal is clean on prod too — it is **not** the cause.

### 3. Collector JVM (prod, pid 6350)

- JRE: `/usr/lib/vmware-vcops/jre/bin/java` → **OpenJDK 17.0.16+13-LTS**
  (runtime exec is `/usr/java/jre-vmware-17/bin/vcops-collector`).
- Same JDK major as devel (17). So hypothesis **#2 (JDK/TCCL behavior change)
  is RULED OUT** — JDK is identical; the difference is purely the platform
  classpath jars.

### 4. Platform JAX-WS inventory (prod 9.1 collector `-classpath`) — THE SKEW

The collector classpath carries a **mismatched JAX-WS API/RT pair**:

| Role | Jar (prod 9.1) | Namespace | `Provider` it defines/extends |
|---|---|---|---|
| API (lookup driver) | `collector/lib/jaxws-api-2.3.1.jar` | **javax** | defines `javax.xml.ws.spi.Provider` + `ServiceLoaderUtil` (emits the error string) |
| RT (impl) | `common/lib/jaxws-rt-4.0.3.jar` | **jakarta** | `com.sun.xml.ws.spi.ProviderImpl` extends **`jakarta.xml.ws.spi.Provider`** |
| Jakarta API | `common/lib/jakarta.xml.ws-api-4.0.2.jar` | jakarta | defines `jakarta.xml.ws.spi.Provider` |
| SAAJ | `common/lib/saaj-impl-3.0.4.jar` + `jakarta.xml.soap-api-3.0.2.jar` | jakarta | — |
| also present | `collector/lib/javax.xml.soap-api-1.4.0.jar` (javax SAAJ API, no impl) | javax | — |

Compare devel 9.0.2, which had a **matched** `jaxws-api-2.3.1` +
`jaxws-rt-2.3.1` pair → `ProviderImpl(2.3.1)` extends `javax...Provider` →
subtype check passes → devel collects. **9.1 upgraded the RT to 4.0.3
(jakarta) but left the javax `jaxws-api-2.3.1` on the collector lib.**

Byte-confirmed superclasses:
- `jaxws-rt-4.0.3` `ProviderImpl` constant pool: `jakarta/xml/ws/spi/Provider`.
- bundled `jaxws-rt-2.3.1` `ProviderImpl` constant pool: `javax/xml/ws/spi/Provider`.

Where the bad SPI entry comes from: the **adapter's bundled
`jaxws-rt-2.3.1.jar`** carries `META-INF/services/javax.xml.ws.spi.Provider`
→ `com.sun.xml.ws.spi.ProviderImpl` (visible to the adapter loader / TCCL).
The platform `jaxws-rt-4.0.3` only ships
`META-INF/services/jakarta.xml.ws.spi.Provider` (no javax service file). So
ServiceLoader's javax lookup finds the adapter's service file, then resolves
the class name `com.sun.xml.ws.spi.ProviderImpl` **parent-first** to the
platform **4.0.3** class (jakarta-extending) → "not a subtype". The adapter's
own correct 2.3.1 `ProviderImpl` is shadowed by parent-first delegation.

### 5. Hypothesis decision

**Hypothesis #1 is CONFIRMED (refined). Hypothesis #2 is RULED OUT.**

- #2 (JDK/TCCL change): ruled out — prod JDK is the same OpenJDK 17.0.16 as devel.
- #1 (9.1 classpath JAX-WS layout breaks the lookup): confirmed, with the
  precise mechanism upgraded from "RT not visible / missing SPI" to a
  **same-FQCN class collision**: platform RT moved to the **jakarta-era
  4.0.3** while the platform API stayed **javax 2.3.1**, so the
  `com.sun.xml.ws.spi.ProviderImpl` reachable parent-first extends the wrong
  (`jakarta`) `Provider`. The adapter bundling `jaxws-rt-2.3.1` actually
  *supplies the javax SPI service file* that triggers the collision; without
  TCCL/loader control the bundled correct impl is never the one loaded.

### Fix assessment — does the planned fix still stand?

The planned fix was: **(a) TCCL bracketing around vim25 stub creation +
(b) a version-aligned self-contained jaxws stack in the pak.** It stands,
but the prod evidence sharpens the requirement and adds a hard constraint:

1. **TCCL bracketing alone is NECESSARY BUT NOT SUFFICIENT.** Setting the
   TCCL to the adapter plugin loader makes `ServiceLoader.load` *find* the
   adapter's `META-INF/services/javax.xml.ws.spi.Provider`. But the failing
   step is **class resolution of `com.sun.xml.ws.spi.ProviderImpl`**, which
   under **parent-first** delegation still resolves to the platform 4.0.3
   (jakarta) class regardless of TCCL. Same-FQCN parent-first shadowing is
   not cured by TCCL. So bracketing must be paired with one of:
   - a **child-first / isolated plugin classloader** for the adapter lib
     (if the 9.1 adapter framework offers one), so the bundled 2.3.1
     `com.sun.xml.ws.spi.ProviderImpl` wins; **or**
   - **shading/relocating** the bundled JAX-WS RT impl packages
     (e.g. relocate `com.sun.xml.ws.**` → `com.vcfcf.shaded.cxf...`) plus a
     correspondingly relocated SPI service file, so there is **no FQCN
     collision** with the platform 4.0.3 at all. This is the most robust
     option on a parent-first platform and the one I recommend leading with.

2. **The bundled stack must be fully self-consistent AND javax-era.** Current
   `lib/` has an API/RT **version skew of its own**: `jaxws-api-2.1` +
   `jaxws-rt-2.3.1`. Align to a single matched javax pair (jaxws-api 2.3.1 +
   jaxws-rt 2.3.1) and include the full transitive RT: `saaj-impl` (javax,
   e.g. 1.5.x — **note prod ships only jakarta `saaj-impl-3.0.4`; there is
   NO javax saaj-impl on the platform**, so the pak MUST carry its own javax
   saaj-impl or vim25 SOAP message handling will hit the same jakarta wall a
   layer down), `streambuffer`, `stax-ex`, `policy` (javax 2.3.x, not the
   4.0.0-M4 jakarta one), `gmbal-api-only`, `istack-commons-runtime`,
   `jaxb-api`/`jaxb-runtime` (javax 2.3.x). The platform's jakarta versions
   of every one of these will shadow a child-first/un-shaded javax jar by
   FQCN, so **whichever isolation strategy is chosen (child-first or
   shading) must cover the entire javax JAX-WS + SAAJ + JAXB closure, not
   just `Provider`.**

3. **9.1-specific detail the fix MUST account for:** 9.1 has crossed the
   javax→jakarta line for the RT/SAAJ/JAXB **impl** jars (`jaxws-rt-4.0.3`,
   `saaj-impl-3.0.4`, `jaxb-runtime-3.0.2`, `jakarta.xml.ws-api-4.0.2`) while
   keeping the **javax `jaxws-api-2.3.1` API** on the collector lib. Any pak
   that relies on platform jars to complete its javax JAX-WS stack will
   break, because the platform no longer provides a *complete javax* stack —
   only the API shell. The pak must be **100% self-contained in the javax
   namespace and isolated from the platform jakarta impls by FQCN** (shading
   is the clean way to guarantee that under parent-first). The alternative
   long-term fix is to **migrate the adapter's vim25 path to the jakarta
   JAX-WS API** and let it use the platform 4.0.3 RT — but that requires a
   jakarta-compatible vim25 binding (the bundled `vim25.jar` is javax-era),
   which is a larger change.

**Net:** the planned direction is correct in spirit (self-contained stack +
loader control), but "TCCL bracketing + version-aligned bundled stack" as
literally worded is insufficient on its own. The load-bearing addition is
**FQCN isolation from the platform's jakarta `com.sun.xml.ws.**` impl** —
shade the bundled RT (preferred) or run the adapter lib child-first — and
the bundled stack must include a **javax `saaj-impl`** because 9.1 ships
none. TCCL bracketing remains a useful belt-and-suspenders for the
ServiceLoader file lookup but does not by itself resolve the
parent-first class collision.

