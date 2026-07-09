# Third-party redistribution patterns for Broadcom platform JARs

**Survey date:** 2026-06-09 (HPE addendum same day)
**Scope:** `inputs/from-marketplace/` — including the HPE SimpliVity pak
fetched 2026-06-09 from the public GitHub release (see provenance below)
and staged into the corpus.
**Method (clean-room safe):** outer-pak `manifest.txt`, inner-archive
jar **inventory** (filename list), adapter-jar **entry paths** (package
names only), bundled-jar `META-INF` package roots, and `eula.txt` /
NOTICE / LICENSE **text**. No bytecode was disassembled or decompiled;
base-contract is inferred from which SDK/framework jar is bundled, not
from reading any `extends` clause.

> **Conclusion only crosses the boundary.** This file records observed
> packaging practice. Observed practice is **not** a license grant; the
> redistribution determination for VCF-CF happens separately (see
> "Why we asked" at end).

---

## Population partition (auditable)

The marketplace corpus is 21 distinct `.pak` adapters plus 2 `.zip`
re-wraps of paks already counted. Partitioned by authorship:

### Genuinely third-party (in scope) — **5 paks, 4 vendors (Dell ×2, HPE, ControlUp, Lenovo)**

| Pak | Adapter | Vendor |
|---|---|---|
| `DellStorageAdapter-01.04.0301_signed.pak` | `dellstorage_adapter` (Compellent/SC) | Dell |
| `openmanageenterpriseadapter-3.0.68.pak` | `OpenManageEnterpriseAdapter` (OMIVV) | Dell |
| `HPESimplivityVropsMP-1.5.0.2.pak` | `HPESimplivityVropsAdapter` | HPE |
| `controlupadapter-1.0.0_signed.pak` | `ControlUpAdapter` | ControlUp |
| `lenovoxclarityadapter-1-1624943338646.pak` | `LenovoXClarityAdapter` | Lenovo |

**HPE provenance:** fetched 2026-06-09 from the public GitHub release
`github.com/HewlettPackard/simplivity-vrops-plugin` tag `v1.5.0`
(asset `HPESimplivityVropsMP-1.5.0.2.pak`, vROps 8.12), SHA256
`14a5de18eff7b22f2c4bc57ad68c53762b464e7820fdeb8ede540398d6d059a4`.
Binary pak inspected; the repo's Java source was **not** read
(clean-room hygiene). **ControlUp / Lenovo:** dropped into the corpus
2026-06-09 (SHA256 `cccc…dec4` / `81e2…778f`). No NetApp / Pure /
Cisco / F5 / Veeam / Hitachi / Nutanix pak is present. (Khriss research
notes Pure Storage also ships a binary-only pak elsewhere, not yet
fetched. A `dxenterprise_23.0.297.0_amd64.tgz` (DH2i) was also dropped
but is the **product install package, not a vROps pak** — no `.pak`,
no Broadcom jars inside; excluded from this survey.)

### Excluded — BlueMedora / True-Visibility-Suite lineage — **7 paks**

Decisive signal: inner-archive `lib/` bundles
**`aria-ops-core-8.2.0.jar`** (packages `com.vmware.tvs.vrealize.adapter.core`,
the post-acquisition BlueMedora framework whose `UnlicensedAdapter`
is the TVS SPI base). Confirmed for `mongodb` in a prior pass; the
other six match by the same bundled jar.

`microsoftsqlserver`, `mongodb`, `mysql`, `networkingdevices`,
`oracledatabase`, `postgresql`, `servicenow`.

### Excluded — Broadcom-TAM-authored, **zero-jar** — **1 pak**

`tam-mpak_1.2.0.2_signed.pak` (`TAMManagementPack`). **TAM = Technical
Adoption Manager** (formerly Technical Account Manager) — a Broadcom/
VMware customer-success role, **not** a third-party vendor and **not**
"Technology Alliance Management." This pack is authored within Broadcom's
own TAM orbit, the same lineage as the vCommunity reference (also
Broadcom-TAM-authored). Its inner archive ships **0 jars**
(declarative-only: `conf/describe.xml` + resources; no `vrops-adapters-sdk`,
no `alive_*`, no `aria-ops-core`, no suiteapi). Triaged 2026-05-15 as
**ELIMINATE-B** (Track B / Integration SDK by structural match to
vCommunity); re-confirmed 2026-06-09. **Out of scope** for this survey
on two counts: not third-party, and zero-jar (nothing to redistribute).
Still a useful **negative** data point: declarative / Integration-SDK
packs bundle no Broadcom jars at all, because the implementation runs
elsewhere (Cloud Proxy container or appliance `mpb-adapter`).

### Excluded — Broadcom / VMware-authored — **12 paks**

`vmware-awsadapter`, `vmware-diagnostics`, `vmware-hcxadapter`,
`vmware-mpforaggregator` (FederationAdapter), `vmware-mpforkubernetes`,
`vmware-mpfornsxadvancedlb`, `vmware-mpforvro`, `vmware-vcfaviadapter`,
`vmware-vcfhcxadapter`, `srmAdapterPak` (SRM), `vlcradapter` (Live
Cyber Recovery), `vmw-vcdaadapter` (Cloud Director Availability).

### Not a separate population — duplicate re-wraps

`dellstorageadapter-01.04.0301.zip` (unsigned re-wrap of the Dell
Storage pak) and `srmvrops.zip` (re-wrap of `srmAdapterPak`). Same
adapter identity as a counted pak; not counted again.

---

## Per-pak table — third-party (in scope)

Broadcom-origin jars only; vendor/OSS jars (httpclient, jackson,
spring, guava, byte-buddy, etc.) omitted.

All five are inner-shape **C1** (root adapter jar + `<Adapter>/lib/`).
Broadcom-origin jars only; vendor/OSS jars omitted. `AdapterBase`
(`com.integrien.alive.common.adapter3`) ships **inside**
`vrops-adapters-sdk.jar` in every case — no standalone `alive_common.jar`
/ `alive_platform.jar`, no `aria-ops-core`/`com.vmware.tvs.*` anywhere.

| Pak (vendor) | `vrops-adapters-sdk` | `vcops-suiteapi-client` + `platform-api-model` | Adapter pkgs | Base | License / attribution of Broadcom jar |
|---|---|---|---|---|---|
| Dell Storage | **yes** (unversioned) | **yes** (`-1.21` / `-1.3`) | `com/dell/storage`, `vcops/ds/compellent` | AdapterBase direct | Dell-only EULA; **none** |
| Dell OME | **yes** (unversioned) | **yes** (`-1.35` / `-1.35`) | `com/dell/pg`, `vrops/stratus/*` | AdapterBase direct | Dell CTS+EULA; **none** (`DellOMIVVLicenseListView` is a content report) |
| HPE SimpliVity | **yes** (unversioned) | **no** (no Suite API) | `adapter/core/*`, `adapter/modules/*` | AdapterBase direct | **MIT © HPE 2019** — grants copy/modify/distribute/sublicense/sell over whole bundle; **none** for the SDK jar |
| ControlUp | **yes** (unversioned) | **no** | `com/controlup/monitor` | AdapterBase direct | **VMware EULA** governs the bundle (not a ControlUp EULA); **none** specific to the SDK jar |
| Lenovo XClarity | **yes** (unversioned) | **no** | `com/lenovo/xclarity` | AdapterBase direct | Lenovo license **+ `ThirdPartyNOTICEs.txt`** — but the NOTICE lists OSS only and **omits** `vrops-adapters-sdk`/VMware/Broadcom |

**Note on `alive_common.jar` / `alive_platform.jar`:** neither standalone
jar appears in any pak in this corpus. The `com.integrien.alive.common.adapter3.*`
contract (incl. `AdapterBase`) ships **packaged inside** `vrops-adapters-sdk.jar`.
The old standalone `alive_*` naming is not the modern convention.

---

## Modal-pattern summary

Third-party population is now **M = 5** paks across **4 vendors**
(Dell ×2, HPE, ControlUp, Lenovo):

- **5 of 5** bundle the native Track-C SDK **`vrops-adapters-sdk.jar`
  (unversioned)** inside `<Adapter>/lib/`. This is the universal
  must-have jar — every third-party native adapter ships it.
- **2 of 5** (both Dell) additionally bundle **`vcops-suiteapi-client-*.jar`**
  + its transitive **`platform-api-model-*.jar`** (Suite-API REST
  client). HPE, ControlUp, and Lenovo omit it — their adapters don't
  call the Suite API. So the suiteapi client is **per-need**, not
  universal. (Tracks use-case, not vendor: it's the adapters that read
  vROps' own inventory that pull it in.)
- **0 of 5** bundle `aria-ops-core` / any `com.vmware.tvs.*` framework
  jar, `alive_common.jar`, or `alive_platform.jar` as a standalone.
- **Base-contract split: 5 / 0** — all extend **`AdapterBase` directly**
  (native SDK); none use `UnlicensedAdapter` / the TVS SPI.
- **License: 0 of 5** attribute the bundled Broadcom jar. The SDK jar
  travels **silently** under whatever license governs the bundle, and
  that license varies widely:
  - Dell ×2 — vendor EULA/CTS, no attribution;
  - HPE — **MIT**, openly granting redistribution/sublicense/sale of the
    whole bundle incl. the Broadcom jar;
  - ControlUp — the bundle ships under a **VMware EULA** (VMware itself is
    the stated licensor of the pak);
  - Lenovo — vendor license **plus a `ThirdPartyNOTICEs.txt`**, the only
    attribution file in the population — yet it enumerates OSS components
    and **omits `vrops-adapters-sdk`** entirely.
  So even the single pak that ships a formal third-party NOTICE does not
  acknowledge the Broadcom SDK jar.

### SDK jar internals — what `vrops-adapters-sdk.jar` itself carries

Cracked open the bundled jar's `META-INF` across all 5 paks + the devel
kit (entry lists, `MANIFEST.MF`, embedded Maven `pom.xml` — no bytecode):

- **3 of 5 paks ship a byte-identical jar** (SHA `16db2823…`, 2019-10-16
  build: Dell-Storage, ControlUp, Lenovo); Dell-OME ships a 2022 build,
  HPE a 2018 build, the devel kit a 2025 build. Vendors ship whatever
  internal build they happened to pull.
- **The jar asserts no license at all.** No `LICENSE` / `NOTICE` /
  `COPYRIGHT` entry; the `pom.xml` has **zero** `<licenses>`,
  `<organization>`, `<developers>`, or copyright blocks (verified on both
  the 2018 and 2025 builds); `MANIFEST.MF` is bare Maven boilerplate
  (`Built-By: mts`, a VMware build-service account).
- **It is an internal build artifact.** pom `groupId` is
  `com.vmware.vcops`; `distributionManagement` points only to **gated
  internal Artifactory** — `build-artifactory.eng.vmware.com/artifactory/vrops-release`
  (2018) → `packages.vcfd.broadcom.net/artifactory/vrops-release` (2025),
  never Maven Central — and it depends on internal `-SNAPSHOT` artifacts
  (`vcops-security`, `vrops-trustmanager`).

**Implication:** the artifact is obtainable only from a gated
VMware/Broadcom repo (i.e. through a partner/SDK relationship) and
**grants nothing on its face**. Any redistribution right the five
vendors exercised therefore lives in the **out-of-band channel** that
delivered the jar (partner / TAP / MP-certification terms), not in the
jar. This is first-party evidence **against** "community convention" and
"implied public right," and **for** a private partner-channel grant —
which a non-partner (VCF-CF) cannot assume it inherits.

### What's actually *in* `vrops-adapters-sdk.jar` — and is it duplicated?

Class-name inventory of the SDK jar (entry lists only, clean-room safe):

- **480 classes**, ~96% under `com/integrien/alive/`:
  - `common/adapter3/` — **405** classes: the adapter SPI proper —
    `AdapterBase`, `AdapterInterface3`, lifecycle params/results
    (`DiscoveryParam`/`Result`, `CollectResult`, `CheckCertificate*`),
    data model (`MetricData`, `MetricKey`, `MetricPattern`,
    `Relationships`, `PropertyChanges`, `InstanceGeneratedMetrics`,
    `RatedMetricsCalculator`), connection/TLS helpers (`HttpsConnection`,
    `CustomSSLSocketFactory`, `CustomTrustManager`, `CertificateChecker`),
    logging (`AdapterLogger*`), licensing (`LicensableSolution`,
    `Licensing*`).
  - `common/util/` — 71; `common/security/` + `common/ingest/` — a few.
  - `com/vmware/vcops/` — 15; `com/vmware/vrops/` — 1 (glue).

**Duplication — two distinct answers:**

1. **At the class level: NOT duplicated.** Of the 480 SDK classes,
   **0** appear in *any other* appliance jar — not in `alive_common`
   (`vcops-common`), not in `alive_platform`, not in the ~20 suite-api
   client jars (appliance union = 4101 classes, intersection = **0**).
   `AdapterBase` exists **only** in `vrops-adapters-sdk*.jar`, nowhere
   else. The SDK is a clean, self-contained module — **not** a
   repackaged slice of the platform jars. (The `com.integrien.alive.*`
   classes inside `alive_common`/`alive_platform` are *different*
   subpackages — platform internals, not the `adapter3` SPI.)

2. **At the jar level: yes, the jar ships in two runtime locations.**
   `vrops-adapters-sdk.jar` is present **both** on the appliance
   classpath (`common-lib/` + `suite-api/WEB-INF/lib/`) **and** bundled
   into every C1 pak's `lib/`. So a C1 adapter runs with **two copies**
   of these 480 classes, reconciled by classloader precedence — and
   they are **version-skewed**: the appliance copy is a **2025-12-30**
   build; the third-party bundled copies are **2018–2019** builds
   (HPE 2018-06-29, Dell/ControlUp 2019-10-16). 6–7 years apart.

**API stability across the 6-year skew (2019-10-16 → 2025-12-30 build).**
Class names: **375 unchanged**, +80 top-level added, −21 removed (401 →
480). The adds are almost entirely the new `describe/policy/pricing` +
`describe/policy/{vc,vcd}` cost/metering model and the `AdapterLogger*`
family — additive capability. Public **signature** diff of the core SPI
(`javap -public`, declared surface only):

- `AdapterInterface3` (the implemented entry contract) — **identical**.
- `DiscoveryParam`, `MetricData`, `PropertyChanges` — **identical**.
- `AdapterBase` — **purely additive** (cert/truststore mgmt,
  `getConnectionURLs`, `getAllMonitoringResources`, `setAdapterDown/Error`,
  `registerInterface`, …) **except one removal**:
  `getAndResetStatistics()` (returned the dropped `AdapterStatistics`).
- `DiscoveryResult`, `CollectResult`, `MetricKey`, `Relationships` —
  **purely additive** (custom configs, cross-vC migration events,
  collection-issue warnings, generic relationships).

**Verdict: the adapter SPI is effectively backward-compatible** across
the skew — an adapter compiled against the 2019 jar binds against the
2025 platform (which is *why* the 2019-bundled Dell/ControlUp/Lenovo
paks still install on 9.x). The only breaking removals are
statistics/problems beans (`AdapterStatistics`, `com.vmware.vcops.common.problems.*`)
that left the SDK jar — niche, outside the collect/discover/relationship
contract. Removed `describe/` classes (`Struct*Describe`,
`ConfigurationProperty*Describe`, `Method*/ResourceReferenceDescribe`)
affect only adapters that used struct-kind or method-action describe —
not the common resource/metric path.

**The load-bearing consequence:** because the appliance already provides
the SDK on the classpath, a native adapter does **not have to bundle
it**. The two C2 "lean" adapters prove this — `Aggregator`
(`federation_adapter3.jar` only) and `SupervisorAdapter` ship **zero**
Broadcom jars and resolve `AdapterBase` from the appliance classpath at
runtime. So **VCF-CF has a real option to ship a C2-style pak with no
Broadcom jar at all** — sidestepping the in-pak redistribution question
(a) entirely. The nominal trade-off is version control: C1 bundling pins
a known SDK build; C2 carries nothing and takes whatever build the
appliance has. See `spec/13-classloading-and-classpath.md`.

**Why do 5/5 bundle when it's optional? — a hunch, and one our own
stability finding undercuts.** The intuitive reason is "compatibility /
ABI version-pinning." But *compatibility* and *stable interface* are two
ends of the same string: the more stable the SPI, the less pinning buys.
And we measured the SPI as **additively stable across 6 years**
(`AdapterInterface3` byte-identical; `AdapterBase` gains-only). Against a
stable interface, pinning protects against an event (a future breaking
change) that has not occurred in the observed history. Two further points
weaken the "for compatibility" reading:

- **Pinning freezes the wrong edge.** A bundled 2019 SDK against a 2025
  platform still relies on the platform keeping the **SDK↔platform**
  runtime contract stable — bundling only freezes the **adapter↔SDK**
  edge. So C1 does *not* escape the stability dependency; it merely
  freezes one of the two edges while still leaning on the platform's
  forward-compatibility for the other. The thing that makes a 2019-bundled
  pak keep working on 9.x is platform back-compat — the *same* property
  that makes C2 safe.
- **The more parsimonious explanation is build inertia, not strategy.**
  `vrops-adapters-sdk.jar` is a compile-scope dependency; many build
  setups copy all runtime deps into `lib/` by default. Five vendors
  shipping the same (often byte-identical, years-old) jar with no
  attribution looks like *the build swept it in*, not a deliberate
  compatibility decision.

So: the bundling is best read as **convention / build-output default —
neither technically required (C2 proves it) nor meaningfully buying
compatibility (the interface is already stable)**. That is a strengthening
of the C2 recommendation, not a caveat against it: if pinning a stable SPI
buys little, the redistribution cost of carrying the jar buys even less.
*(This is an inference about motivation — no vendor states a reason; the
artifacts show only that bundling is optional, the bundled builds are old,
and the SPI is stable.)*

### The `alive_*` platform jars — present, but never third-party-redistributed

The original ask flagged `alive_common.jar` / `alive_platform.jar`.
They **do** exist in the corpus — but only on the **appliance side**,
never in a third-party pak:

- Located only in the devel/appliance SDK kit
  (`inputs/from-devel/sdk/common-lib/`, `suite-api/WEB-INF/lib/`) and
  inside two **Broadcom-internal** adapters (`AppOSUCPAdapter3`,
  `VCFAutomation`). **0 of 5 third-party paks bundle either** (verified).
- `alive_common.jar` is Maven artifactId **`vcops-common`** (235
  `com/integrien/alive/*` + `com/vmware/vrops` pkgs; **does not contain
  `AdapterBase`**). `alive_platform.jar` (4.9 MB) is the platform engine
  proper (3052 `com/vmware/vcops` pkgs). Both are the **appliance
  runtime** the adapter binds to at scan time — provided on the Tomcat
  classpath, not bundled.
- Same internal-artifact fingerprint as the SDK jar: `Built-By: mts`,
  no `<licenses>`/NOTICE, `distributionManagement` → internal
  `packages.vcfd.broadcom.net/artifactory`.

**The redistribution boundary third parties actually observe is narrow
and consistent:** they bundle **only `vrops-adapters-sdk.jar`** (the
curated adapter-authoring SDK — 464 `com.integrien` classes *incl.*
`AdapterBase`), and rely on `alive_common`/`alive_platform` being
**present on the appliance classpath** at runtime. VCF-CF should mirror
exactly this line: ship the SDK jar in-pak (if licensed); **never** ship
the `alive_*` platform jars — they are appliance-resident and bundling
them is both unnecessary and a far larger redistribution ask.

**Contrast classes (excluded, for shape comparison):**
- TVS-lineage (7 paks): bundle **`aria-ops-core-8.2.0.jar`** instead of
  `vrops-adapters-sdk.jar`; `UnlicensedAdapter`/TVS-SPI base. This is the
  distinct "BlueMedora pattern."
- Broadcom-authored (12 paks): either bundle
  `vrops-adapters-sdk[.jar|-1.0.jar]` + `vcops-suiteapi-*client` (e.g.
  SRM, k8s, NSX-ALB, vCDA, VcfAvi), or ship **no** SDK jar and rely on
  the appliance Tomcat classpath (sub-shape C2 — e.g. AWS 109-jar lib
  with no SDK jar by name, Aggregator's single `FederationAdapter.jar`).

> The third-party mode (bundle `vrops-adapters-sdk` + `vcops-suiteapi-client`
> in-pak, no attribution) **matches the Broadcom-authored C1 mode** jar-for-jar.
> Outside vendors copy Broadcom's own in-appliance packaging convention.

---

## Distributing the JARs *outside* a pak — observable precedent

Two different answers for the two jars VCF-CF cares about:

- **`vrops-adapters-sdk.jar` (the adapter-side SDK):** **no public
  out-of-pak distribution.** Not on Maven Central, no public developer
  docs, not in Broadcom's SDK support matrix (Khriss research, High
  confidence). It exists outside a pak only **internally** — physically
  on every appliance (`common-lib/`, `suite-api` `WEB-INF/lib/`) and in
  the devel SDK kit captured at `inputs/from-devel/sdk/vrops-adapters-sdk-2.2.jar`
  + `common-lib/vrops-adapters-sdk{,-1.0}.jar`. TAP "gated SDK" language
  hints at a partner-portal channel, unconfirmed. **No third-party
  redistribution of this jar outside a pak is observed anywhere.**
- **`vcops-suiteapi-client` (the Suite-API REST consumer client):**
  **does have public out-of-pak distribution** — it appears as an
  artifact in the **Unified VCF SDK 9.0 on Maven Central** (Khriss
  research). That is the REST-API *consumer* client, not the adapter
  SDK, but it is the one Broadcom-origin jar in these paks with a
  legitimate public, non-pak distribution channel.

So the only Broadcom platform jar with any public out-of-pak precedent
is `vcops-suiteapi-client`; the adapter SDK proper has none.

---

## Why we asked (context, not a finding)

VCF-CF must decide which platform jars may respectfully ship (a) inside
built `.pak` artifacts and (b) in a public build-toolchain tarball.
This survey supplies the prevailing third-party practice as one input:

- **(a) inside built `.pak`:** outside vendors uniformly bundle
  `vrops-adapters-sdk` (5/5) — and `vcops-suiteapi-client` when needed
  (2/5) — **in-pak** with no attribution (0/5). One of the five (HPE
  SimpliVity) is **publicly distributed on GitHub under an MIT license**
  that purports to permit downstream redistribution of the whole bundle;
  another (ControlUp) ships under a **VMware EULA**. So there is direct
  precedent for an SDK-bearing pak being shipped openly and even
  permissively relicensed by a third party.
- **(b) public build-toolchain tarball:** **no** observed precedent for
  shipping the adapter SDK (`vrops-adapters-sdk`) outside a pak — it has
  no public Maven/portal channel. Only `vcops-suiteapi-client` has a
  public out-of-pak channel (Maven Central, via Unified VCF SDK 9.0).

Observed practice is not a license grant; the legal determination is
separate. Note the asymmetry for VCF-CF: there is precedent for the SDK
jar traveling *inside a publicly-distributed pak*, but none for it
traveling *as a standalone toolchain artifact*.
