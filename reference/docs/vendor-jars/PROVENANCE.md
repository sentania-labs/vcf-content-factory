> **Binary not committed.** This factory repo is public and the 2026-06-09
> redistribution survey keeps Broadcom jars out of public artifacts. The jar
> described here lives in the private `vcf-content-factory-sdk-runtime` repo
> beside the 2.2 jar, and on the lab holding share at
> `/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/`. This file is the
> provenance record only.

# vendor-jars

Verbatim Broadcom jars, byte-for-byte as shipped. Immutable once added
(RULE-016). Findings about them live in `knowledge/context/`, not here.

## vrops-adapters-sdk-9.1.1.0100.jar

- **What:** the VCF Operations adapter SDK jar, `common/lib/vrops-adapters-sdk.jar`
  of VCF Operations 9.1.1.0100, build 25795063 (the build devel_9_1 runs).
- **sha256:** `79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7`
- **Size:** 1,001,091 bytes. Manifest: `Created-By: Maven JAR Plugin 3.5.0`,
  `Java-Version: 25`. Classes are major version 69 (Java 25). 512 entries.
- **Source image:** `Operations-Appliance-9.1.1.0100.25795063.ova`
  (3,373,148,160 bytes, sha256
  `fd48dcb01c6c18c86a48d9579a8fe082a066c2ff4a63e853985f6a9153365234`),
  held on the lab NAS at
  `/mnt/holding/vendor/vcf-ops-9.1.1.0100/PROD/COMP/VROPS/`. Local-only
  artifact, not in any fetch registry.
- **Path inside the image:** OVA member
  `Operations-Appliance-9.1.1.0100.25795063-cloud-components.vmdk` (sha256
  `1530535a5e94...`, matches the OVA `.mf`), an ISO 9660 filesystem whose
  `buildInfo` reads `RELEASENUMBER:9.1.1.0100.25795063`; inside it
  `product/vmware-vcops-9.0.0.0-25794169.x86_64.rpm` (sha256
  `9b50ef210235...`); inside the RPM payload
  `./usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar` (file mtime in
  the payload 2026-09-29). The sibling
  `./usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk-1.0.jar` is
  byte-identical.
- **Fetched:** 2026-10-23 by `api-explorer`: `tar` the vmdk out of the
  OVA, `qemu-img convert -O raw`, `7z` the RPM out of the ISO, `bsdtar` the
  jar out of the RPM. All in session scratch, deleted after. No appliance
  was touched.

### Not the same bytes as prod 9.1.1.0

| Build | sha256 | Size | Source |
|---|---|---|---|
| 9.1.1.0100 build 25795063 | `79f7b1234090...` (full hash above) | 1,001,091 | this file, from the OVA |
| 9.1.1.0 build 25679751 | `9e905f1a5164...` (only 12 characters recorded) | 1,001,089 | prod nodes, read 2026-10-13, not stored |
| 9.0.2.0 build 25137845 | `2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54` | 1,002,682 | devel; identical to `src/vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-2.2.jar` |

The 0100 patch rebuilt the jar (two bytes larger, different hash). Its entry
list matches the one recorded for 9.1.1.0. Digest:
`knowledge/context/tier2_architecture.md` section "SDK jar by platform version".
