Portable Tier 2 SDK adapter build toolchain (jar-free).

## Consumer contract

The kit compiles adapters against `vrops-adapters-sdk-2.2.jar` which
**you must supply** — it is a Broadcom internal build artifact with no
public redistribution channel and must not ship in a public toolchain
tarball (see redistribution survey 2026-06-09).

**How to obtain the SDK JAR (pick one):**
1. Extract from your VCF Ops appliance:
   `scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .`
   (also present at `/usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar`)
2. Pull from the Broadcom TAP / partner SDK portal (if you have access).

**CI usage (adapter repo's build workflow):**

```yaml
- name: Download sdk-buildkit
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh release download @FLOATING_TAG@ \
      --repo sentania-labs/vcf-content-factory \
      --pattern '*.tgz'
    tar xzf sdk-buildkit-*.tgz

- name: Build adapter pak
  env:
    VCFCF_SDK_JAR: ${{ secrets.VCFCF_SDK_JAR_PATH }}   # path to vrops-adapters-sdk-2.2.jar
  run: python3 -m sdk_buildkit build-sdk .
```

## Version pinning
- **Exact pin**: `@REF_NAME@`
- **Floating major**: `@FLOATING_TAG@`
  (always points at the latest backwards-compatible release of this major)
