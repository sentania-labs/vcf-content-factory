# adapter_runtime SDK jar provenance

This directory is gitignored: the Broadcom jars in it are local-only and
never committed or shipped in the sdk-buildkit tarball. This note is the one
tracked file here (force-added) so the provenance of the two SDK compile
targets sits next to the jars. Platform-version digest:
`knowledge/context/tier2_architecture.md`, section "SDK jar by platform
version".

## The two compile targets

| Role | File here | Platform build | Path in the Ops install | sha256 | Size | Class files |
|---|---|---|---|---|---|---|
| Primary (shipped compile target) | `vrops-adapters-sdk-2.2.jar` | VCF Operations 9.0.2.0 build 25137845 | `common/lib/vrops-adapters-sdk.jar` | `2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54` | 1,002,682 | Java 17 (major 61) |
| Second target (compile check only, issue #211) | `vrops-adapters-sdk-9.1.1.0100.jar` | VCF Operations 9.1.1.0100 build 25795063 | `common/lib/vrops-adapters-sdk.jar` (under `/usr/lib/vmware-vcops/` in the image) | `79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7` | 1,001,091 | Java 25 (major 69) |

Factory CI reads the sha256 in the second row (`.github/workflows/ci.yml`,
job `sdk-compat`); keep exactly one table row naming each jar.

### 2.2 jar (9.0.2)

Captured from the VCF Ops devel appliance on 2026-05-15 (section "Where the
JARs come from" in `src/vcfcf_managementpacks/README.md`); byte-identical to
devel 9.0.2.0's `common/lib/vrops-adapters-sdk.jar` when compared on
2026-10-13. The private `sentania-labs/vcf-content-factory-sdk-runtime` repo
carries the same bytes for pak CI (hash checked 2026-10-23). The `2.2` in
the name is a name, not a version.

### 9.1.1.0100 jar

**Where it is:** not in this public repo (the 2026-06-09 redistribution
survey keeps Broadcom jars out of public artifacts), and **not yet** in the
private `sentania-labs/vcf-content-factory-sdk-runtime` repo, which today
holds only its README and the 2.2 jar. It is parked on the lab holding share
at `/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/` (hash checked
2026-10-23). That share is local to this lab, not reachable from a fresh
clone or from CI (RULE-015 local-only artifact). Uploading it to the private
repo and adding the `SDK_RUNTIME_SSH_KEY` secret to this repo is issue #250;
until then the factory CI job `sdk-compat` skips with a notice.

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
| 9.0.2.0 build 25137845 | 2d53a91fc2b9 (full hash in the table above) | 1,002,682 | devel; identical to the 2.2 jar here |

## How the build uses them

- Everything that ships (framework jar, adapter jar) is compiled against
  `vrops-adapters-sdk-2.2.jar` only.
- build-sdk, validate-sdk and `adapter_framework/build-framework.sh` then
  compile the same source a second time against
  `vrops-adapters-sdk-9.1.1.0100.jar`, keep nothing, and fail on any
  unresolved class or member. That pass needs JDK 25+; without the jar or
  the JDK it is skipped with a warning, or fails when
  `VCFCF_SDK_COMPAT_REQUIRED=1`.
- The 9.1.1.0100 jar must never join the primary classpath (a merged
  classpath resolves a class present in only one jar and hides the drift).
  The primary compile takes exactly one SDK jar: any other
  `vrops-adapters-sdk*.jar` here or under `lib/`, under any name (the
  appliance's is plain `vrops-adapters-sdk.jar`), stops the build with an
  error naming it. Use the exact name `vrops-adapters-sdk-9.1.1.0100.jar`
  or pass the jar with `--sdk-compat-jar`.

## Setting it up locally

Copy the 9.1.1.0100 jar from the holding share (or a 9.1.1.0100 appliance's
`common/lib/vrops-adapters-sdk.jar`) into this directory **under the name
`vrops-adapters-sdk-9.1.1.0100.jar`**, then check both hashes against the
table:

    sha256sum src/vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-*.jar
