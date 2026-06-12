# Building from source (canonical pak-README section)

This file is the **canonical, diffable source** for the "Building from
source" section that ships in every SDK pak repo's README (and the
template repo). Maintain it here; copy it into each pak README under a
`## Building from source` heading. Like `build-pak-on-tag.yml`, the
factory copy is the one that gets PR'd; pak repos carry snapshots.

Why this exists: a pak repo cloner had no in-repo path from "I edited
the Java" to "I have a `.pak`" — the build contract lived only in the
factory's buildkit release notes. (Two builder personas: a **factory
clone** drives `vcfops_managementpacks build-sdk` against
`content/sdk-adapters/<name>/`; a **pak-repo clone or fork** uses the
portable buildkit below, no factory checkout needed.)

---

<!-- COPY FROM HERE INTO PAK README -->

## Building from source

You don't need this repo's CI or the VCF Content Factory checkout to
build the `.pak` — the toolchain is a portable tarball. You need:

- **JDK 11+** (`javac` + `jar` on PATH)
- **python3** with `pyyaml` (`python3 -m pip install pyyaml`)
- **The Broadcom adapter SDK jar** (`vrops-adapters-sdk-2.2.jar`).
  This is a Broadcom build artifact with no public redistribution
  channel — it is **never** bundled in the toolchain or this repo.
  Get it from your own VCF Operations appliance:

  ```
  scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .
  ```

  (Also present at
  `/usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar`.
  Partners can pull it from the Broadcom TAP / partner SDK portal
  instead.)

Then, from the root of this repo:

```bash
# 1. Fetch the build toolchain (pin a full sdk-buildkit-vX.Y.Z tag for
#    reproducibility, or use the floating major sdk-buildkit-v1)
gh release download sdk-buildkit-v1 \
  --repo sentania-labs/vcf-content-factory \
  --pattern 'sdk-buildkit-*.tgz'
tar xzf sdk-buildkit-*.tgz

# 2. Point the kit at your SDK jar and build
export VCFCF_SDK_JAR=/path/to/vrops-adapters-sdk-2.2.jar
python3 -m sdk_buildkit validate-sdk .   # cheap loop: compile-check
python3 -m sdk_buildkit build-sdk .      # emits the .pak
```

The kit carries everything else it needs (including the
`vcfcf-adapter-base.jar` framework runtime that ends up in the pak's
`lib/`). `validate-sdk` is the fast iteration loop; exhaust it before
building paks.

**Dev builds vs releases.** Anything you build this way is a *dev
build*. The **official** artifact for this repo is the one its own CI
builds and attaches to a GitHub Release when a `v*` tag is pushed —
deterministic, no developer machine in the path.

**If you fork this repo**, the CI workflow
(`.github/workflows/build-pak-on-tag.yml`) needs two adjustments
before your own `v*` tags will build:

1. **Runner**: it targets a `self-hosted` runner pool — switch
   `runs-on` to `ubuntu-latest` (the workflow comments call this out).
2. **SDK jar sourcing**: the upstream workflow fetches the Broadcom
   jar from a private repo via an `SDK_RUNTIME_SSH_KEY` deploy-key
   secret you won't have. Replace that step with your own source —
   e.g. store the appliance-extracted jar in your own private repo or
   an Actions secret/artifact store — and point `VCFCF_SDK_JAR` at it.
   Do **not** commit the jar to a public repo (no redistribution).

<!-- COPY TO HERE -->
