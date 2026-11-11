# adapter_runtime SDK jar provenance

This directory is gitignored: the Broadcom jars in it are local-only and
never committed or shipped in the sdk-buildkit tarball. This note is the one
tracked file here (force-added) so the provenance of the SDK compile
targets sits next to the jars. Platform-version digest:
`knowledge/context/tier2_architecture.md`, section "SDK jar by platform
version".

## The compile targets

File names (2026-11-11): `vrops-adapters-sdk-<version>.<build>.jar`, for the
platform version and build the bytes come from. Every appliance calls its
copy `common/lib/vrops-adapters-sdk.jar` (under `/usr/lib/vmware-vcops/`),
the path the collector loads (`user/conf/collector/wrapper-classpath.conf`).

| Role | File here | Platform build | Path in the Ops install | sha256 | Size | Class files |
|---|---|---|---|---|---|---|
| Primary (shipped compile target, `--release 11`; also the 9.0 leg at `--release 17`) | `vrops-adapters-sdk-9.0.2.0.25137845.jar` | VCF Operations 9.0.2.0 build 25137845 | `common/lib/vrops-adapters-sdk.jar` | `2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54` | 1,002,682 | Java 17 (major 61), 480 classes |
| Known jar for the 9.0 line, accepted as the primary jar and for the 9.0 leg; not held in the runtime repo; classes identical to 9.0.2.0, Maven metadata differs | `vrops-adapters-sdk-9.0.2.0200.25431135.jar` | VCF Operations 9.0.2.0200 (Suite API build 25431135) | `common/lib/vrops-adapters-sdk.jar` | `a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b` | 1,002,682 | Java 17 (major 61), 480 classes |
| Compat leg, 8.18 (compile check only, `--release 11`, issue #252) | `vrops-adapters-sdk-8.18.7.25423534.jar` | Aria Operations 8.18.7 build 25423534 | `common/lib/vrops-adapters-sdk.jar` | `45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea` | 965,383 | Java 11 (major 55), 471 classes |
| Compat leg, 9.1 (compile check only, `--release 25`, issues #211, #252) | `vrops-adapters-sdk-9.1.1.0100.25795063.jar` | VCF Operations 9.1.1.0100 build 25795063 | `common/lib/vrops-adapters-sdk.jar` | `79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7` | 1,001,091 | Java 25 (major 69), 474 classes |

### Former names

Renamed 2026-11-11 (same bytes, same hashes; the private
`sentania-labs/vcf-content-factory-sdk-runtime` repo carries the new names
from its PR 10, merge commit `cff8dbd6eab2621428ad46e25a38dc0e23187b60`).
The former names still work wherever the kit looks a jar up by name in
this directory, with one INFO line; a jar given by path (`--sdk-jar`,
`VCFCF_SDK_JAR`, `--sdk-compat-jar`) may have any name and is identified by
its sha256.

| Former name | Name now | sha256 |
|---|---|---|
| `vrops-adapters-sdk-2.2.jar` | `vrops-adapters-sdk-9.0.2.0.25137845.jar` | `2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54` |
| `vrops-adapters-sdk-8.18.7.jar` | `vrops-adapters-sdk-8.18.7.25423534.jar` | `45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea` |
| `vrops-adapters-sdk-9.1.1.0100.jar` | `vrops-adapters-sdk-9.1.1.0100.25795063.jar` | `79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7` |

Factory CI reads the sha256 in the table rows naming each jar
(`.github/workflows/ci.yml`, job `sdk-compat`, one matrix row per line), and
`sdk_builder._SDK_COMPAT_LINES` carries the same four hashes (a test keeps
them equal). Every table row that names a jar, by its current or former
name, carries that jar's hash and no other, so a lookup by either name
finds exactly one.

### 9.0.2.0 jar (formerly `-2.2`)

Captured from the VCF Ops devel appliance on 2026-05-15 (section "Where the
JARs come from" in `src/vcfcf_managementpacks/README.md`); found
byte-identical to `common/lib/vrops-adapters-sdk.jar` on devel, then VCF
Operations 9.0.2.0 build 25137845, on 2026-10-13. Devel has since been
patched to 9.0.2.0200 (2026-10-14), so these bytes are no longer on any lab
appliance. A copy named `vrops-adapters-sdk-2.2.jar` exists in the
`LogAssistAdapter` pack's `lib/` on 9.0.2; whether our file was taken from
it is not recorded. The `2.2` in the former name was never a platform
version. The private `sentania-labs/vcf-content-factory-sdk-runtime` repo
carries the same bytes for pak CI (hash checked 2026-10-23).

### 9.0.2.0200 jar

**Where it is:** on devel (`/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`,
mode 644 admin:admin), VCF Operations 9.0.2.0200: Suite API
`versions/current` "VCF Operations 9.0.2.0" build 25431135, pak
`vRealizeOperationsManagerEnterprise-902020025431133`, RPM
`vmware-vcops-9.0.2.0-25429562`. Read in place over SSH 2026-11-11; no jar
left the box, and it is not in the runtime repo or on the holding share.

**What it is:** a rebuild of the 9.0.2.0 jar. Per-entry CRC32 and size are
identical for all 480 classes; only `META-INF/maven/.../pom.properties`
(build timestamp) and `pom.xml` (`bora-25137845` vs `bora-25429562` build
paths) differ. It is listed so a builder who copies the jar from a current
patched 9.0.2 appliance satisfies the 9.0 leg instead of being told its
sha256 matches no known line. Evidence:
`knowledge/context/tier2_architecture.md`, "Re-read over SSH, all three
devel appliances (2026-11-11)".

### 8.18.7 jar (formerly `-8.18.7`)

**Where it is:** not in this public repo (the 2026-06-09 redistribution
survey keeps Broadcom jars out of public artifacts; never commit it). It is
in the private `sentania-labs/vcf-content-factory-sdk-runtime` repo (its
PRs 7 and 8, merged 2026-10-24), where factory CI's `sdk-compat (8.18.7)`
row fetches it, checks the hash in the table above and compiles against
it, required. The lab copy is on the holding share at
`/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/` (local-only,
RULE-015), hash checked 2026-10-24.

**What it is:** `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`
of the devel_8_18 appliance, Aria Operations 8.18.7 build 25423534, read
2026-10-24 (one scp pull, nothing changed on the node). The collector loads
it (`wrapper-classpath.conf` line 63). Same bytes as the node's
`vrops-adapters-sdk-1.0.jar`, the Cloud Proxy's copy and the
`NSXTAdapter3` pack's copy. 471 classes, every one class major 55 (Java
11); the 8.18.7 collector and Cloud Proxy run OpenJDK 11.0.30. It is the
older API: it lacks 11 members the 9.0.2 jar has (AdapterBase 2,
CustomTrustManager 7, AdapterDescribe 2) and adds none. Evidence:
`knowledge/context/investigations/2026-10-24-devel-8-18-sdk-jar-and-proxy-log.md`.

### 9.1.1.0100 jar (formerly `-9.1.1.0100`)

**Where it is:** not in this public repo (the 2026-06-09 redistribution
survey keeps Broadcom jars out of public artifacts). It is in the private
`sentania-labs/vcf-content-factory-sdk-runtime` repo (its PR 7, merged
2026-10-24; issue #250 closed), beside the 9.0.2.0 and 8.18.7 jars, and the
`SDK_RUNTIME_SSH_KEY` deploy key is set on this repo, so factory CI's
`sdk-compat (9.1.1.0100)` row fetches it, checks the hash in the table above
and compiles against it, required. The lab copy is on the holding share at
`/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/` (hash checked
2026-10-23), local to this lab (RULE-015 local-only artifact).

**What it is:** `common/lib/vrops-adapters-sdk.jar` of VCF Operations
9.1.1.0100, build 25795063 (the build devel_9_1 runs). Manifest:
`Created-By: Maven JAR Plugin 3.5.0`, `Java-Version: 25`. 512 entries.

**Extraction chain:**

- Source image: `Operations-Appliance-9.1.1.0100.25795063.ova`
  (3,373,148,160 bytes, sha256
  `fd48dcb01c6c18c86a48d9579a8fe082a066c2ff4a63e853985f6a9153365234`), on
  the lab holding share at
  `/mnt/holding/vendor/vcf-ops-9.1.1.0100/PROD/COMP/VROPS/` (local-only, not
  in any fetch registry).
- OVA member `Operations-Appliance-9.1.1.0100.25795063-cloud-components.vmdk`
  (sha256 `1530535a5e94...`, matches the OVA `.mf`), an ISO 9660 filesystem
  whose `buildInfo` reads `RELEASENUMBER:9.1.1.0100.25795063`; inside it
  `product/vmware-vcops-9.0.0.0-25794169.x86_64.rpm` (sha256
  `9b50ef210235...`); inside the RPM payload
  `./usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar` (file mtime in
  the payload 2026-09-29). The sibling
  `./usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk-1.0.jar` is
  byte-identical.
- Extracted 2026-10-23 by `api-explorer`: `tar` the vmdk out of the OVA,
  `qemu-img convert -O raw`, `7z` the RPM out of the ISO, `bsdtar` the jar
  out of the RPM, all in session scratch. No appliance was touched.

**Not the same bytes as prod 9.1.1.0.** The 0100 patch rebuilt the jar (two
bytes larger, different hash); its entry list matches the one recorded for
9.1.1.0.

| Build | sha256 (prefix) | Size | Source |
|---|---|---|---|
| 9.1.1.0100 build 25795063 | 79f7b1234090 (full hash in the table above) | 1,001,091 | the OVA, as above |
| 9.1.1.0 build 25679751 | 9e905f1a5164 (only 12 characters recorded) | 1,001,089 | prod nodes, read 2026-10-13, not stored |
| 9.0.2.0 build 25137845 | 2d53a91fc2b9 (full hash in the table above) | 1,002,682 | devel before its 9.0.2.0200 patch; the 9.0.2.0 jar here |

## How the build uses them

- Everything that ships (framework jar, adapter jar) is compiled against
  the 9.0.2 jar only (either 9.0 row), with `javac --release 11` (Java 11
  bytecode and Java 11 library API: the 8.18 collector runs Java 11). The
  javac must be JDK 17 or newer to read the jar's Java 17 class files; an
  older one stops the build with a message saying so.
- `conf/version.txt` `Adapter-Version-Ref` is the compile jar's
  `<version>.<build>` from its sha256 (`9.0.2.0.25137845` or
  `9.0.2.0200.25431135`), whatever the file is called.
- build-sdk, validate-sdk and `adapter_framework/build-framework.sh` then
  compile the same main source (never tests) again once per supported
  line, keep nothing, and fail on any unresolved class or member, or any
  Java API the line's collector Java lacks. Each leg compiles with
  `--release` set to its line's collector Java, read from the jar's class
  files: 8.18.7 at 11, 9.0 (the 9.0.2 jar again) at 17, 9.1.1.0100 at 25, on
  a JDK at least that new. A supplied jar is matched to its line by the
  sha256 in the table above (`sdk_builder._SDK_COMPAT_LINES`; a test keeps
  the two equal). Every line is expected: one with no matching jar, or no
  JDK, is skipped with a warning, or fails when
  `VCFCF_SDK_COMPAT_REQUIRED=1`, unless `VCFCF_SDK_COMPAT_LEGS` narrows the
  set (each factory CI row names its own line).
- A compat jar must never join the primary classpath (a merged classpath
  resolves a class present in only one jar and hides the drift). The
  primary compile takes exactly one SDK jar: any other
  `vrops-adapters-sdk*.jar` here or under `lib/`, under any name (the
  appliance's is plain `vrops-adapters-sdk.jar`), stops the build with an
  error naming it. Use the exact names above (or a former name) or pass
  the jars with `--sdk-compat-jar` (repeatable).

## Setting it up locally

Copy each compat jar from the holding share (or that line's appliance's
`common/lib/vrops-adapters-sdk.jar`) into this directory **under the name
in the table** (`vrops-adapters-sdk-8.18.7.25423534.jar`,
`vrops-adapters-sdk-9.1.1.0100.25795063.jar`), then check every hash
against the table:

    sha256sum src/vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-*.jar
