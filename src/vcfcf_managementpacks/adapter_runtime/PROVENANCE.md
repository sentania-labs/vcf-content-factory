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

- **2.2 jar:** captured from the VCF Ops devel appliance on 2026-05-15
  (section "Where the JARs come from" in `src/vcfcf_managementpacks/README.md`);
  byte-identical to devel 9.0.2.0's `common/lib/vrops-adapters-sdk.jar`
  when compared on 2026-10-13. The private
  `sentania-labs/vcf-content-factory-sdk-runtime` repo carries the same
  bytes for pak CI (hash checked 2026-10-23). The `2.2` in the name is a
  name, not a version.
- **9.1.1.0100 jar:** a copy of
  `reference/docs/vendor-jars/vrops-adapters-sdk-9.1.1.0100.jar`, which was
  extracted from the `Operations-Appliance-9.1.1.0100.25795063.ova` image
  (full chain in `reference/docs/vendor-jars/PROVENANCE.md`). Prod 9.1.1.0
  build 25679751 carries different bytes (`9e905f1a5164...`, 1,001,089
  bytes, same class set); the 0100 patch rebuilt the jar.

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
  classpath resolves a class present in only one jar and hides the drift);
  `sdk_builder._is_compat_sdk_jar` keeps it out of every glob here.

## Setting it up locally

    cp reference/docs/vendor-jars/vrops-adapters-sdk-9.1.1.0100.jar \
       src/vcfcf_managementpacks/adapter_runtime/
    sha256sum src/vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-*.jar
