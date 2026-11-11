# Building from source (canonical pak-README section)

This file is the **canonical, diffable source** for the "Building from
source" section that ships in every SDK pak repo's README (and the
template repo). Maintain it here; copy it into each pak README under a
`## Building from source` heading. This factory copy is the one that gets
PR'd; pak repos carry snapshots. (The CI workflow is different: its source
of truth is the template repo, see README.md in this directory.)

Why this exists: a pak repo cloner had no in-repo path from "I edited
the Java" to "I have a `.pak`" — the build contract lived only in the
factory's buildkit release notes. (Two builder personas: a **factory
clone** drives `vcfcf_managementpacks build-sdk` against
`content/sdk-adapters/<name>/`; a **pak-repo clone or fork** uses the
portable buildkit below, no factory checkout needed.)

---

<!-- COPY FROM HERE INTO PAK README -->

## Building from source

You don't need this repo's CI or the VCF Content Factory checkout to
build the `.pak` — the toolchain is a portable tarball. You need:

- **JDK 17+** (`javac` + `jar` on PATH; the 9.0.2 SDK jar's class files are Java 17)
- **python3** with `pyyaml` (`python3 -m pip install pyyaml`)
- **The GitHub CLI** (`gh`) — used to download the build toolchain
  below. The factory repo is public, so no `gh auth login` is needed
  for the download (authenticate only if you hit anonymous API rate
  limits). No `gh`? See the `curl` alternative under step 1.
- **The Broadcom adapter SDK jar for VCF Operations 9.0.2**, and
  **JDK 17 or newer** to read it. This is a Broadcom build artifact
  with no public redistribution channel — it is **never** bundled in
  the toolchain or this repo. The jar is different on every platform
  version; the build compiles against the 9.0.2 one. Get it from a VCF
  Operations 9.0.2 appliance, where it is
  `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`. Keep it
  **outside this repo's working tree**, so it can never be committed
  by accident:

  ```
  mkdir -p ~/vcf-ops-sdk && cd ~/vcf-ops-sdk
  scp root@<appliance>:/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar .
  sha256sum vrops-adapters-sdk.jar
  ```

  Look the hash up in the table under "Consumer contract" in the
  buildkit release notes. It lists the builds the kit recognises and the
  file name it uses for each, `vrops-adapters-sdk-<version>.<build>.jar`
  (for example `vrops-adapters-sdk-9.0.2.0.25137845.jar`); rename your
  copy to match. The kit identifies the jar by its hash, so a jar from a
  patched appliance is a different build with a different name. If the
  hash is not in the table, the appliance is at a build the kit does not
  know yet: the jar still compiles, the build reports it as an unknown
  jar, and you can name it `vrops-adapters-sdk-<version>.<build>.jar`
  from the appliance's own version and build. The same
  section covers the optional 8.18.7 and 9.1.1 jars for the
  compatibility checks. Partners can pull the jar from the Broadcom TAP
  / partner SDK portal instead.

Then, from the root of this repo:

```bash
# Run as one block. The subshell stops at the first failure, so a checksum
# mismatch never reaches the unpack or the build, and your own shell stays open.
(
set -e
# 1. Fetch the build toolchain. Pin a full sdk-buildkit-vX.Y.Z tag (the
#    floating sdk-buildkit-v1 tag moves under you) and verify the published
#    checksum before unpacking. Use the version this repo's release
#    workflow pins (BUILDKIT_TAG in .github/workflows/build-pak-on-tag.yml);
#    1.0.27 at the time of writing.
BUILDKIT_VERSION=1.0.27
gh release download "sdk-buildkit-v$BUILDKIT_VERSION" \
  --repo sentania-labs/vcf-content-factory \
  --pattern "sdk-buildkit-$BUILDKIT_VERSION.tgz*"
# No gh? The assets are public; fetch both with curl instead:
#   base=https://github.com/sentania-labs/vcf-content-factory/releases/download/sdk-buildkit-v$BUILDKIT_VERSION
#   curl -fsSLO "$base/sdk-buildkit-$BUILDKIT_VERSION.tgz"
#   curl -fsSLO "$base/sdk-buildkit-$BUILDKIT_VERSION.tgz.sha256"
# Verify before unpacking. The strong check is against the hash this repo
# commits for its release builds (BUILDKIT_SHA256 in the same workflow),
# which a replaced release asset cannot match:
echo "$(awk '/^  BUILDKIT_SHA256:/{print $2}' .github/workflows/build-pak-on-tag.yml)  sdk-buildkit-$BUILDKIT_VERSION.tgz" | sha256sum -c -   # macOS: shasum -a 256 -c -
# For a version other than the pinned one, the release's own sidecar only
# proves the download is intact:
#   sha256sum -c "sdk-buildkit-$BUILDKIT_VERSION.tgz.sha256"
tar xzf "sdk-buildkit-$BUILDKIT_VERSION.tgz"

# 2. Point the kit at your SDK jar and build
export VCFCF_SDK_JAR=~/vcf-ops-sdk/vrops-adapters-sdk-9.0.2.0.25137845.jar
python3 -m sdk_buildkit validate-sdk .   # cheap loop: compile-check
python3 -m sdk_buildkit build-sdk .      # emits the .pak
)
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
(`.github/workflows/build-pak-on-tag.yml`) needs one adjustment
before your own `v*` tags will build (it already runs on GitHub-hosted
`ubuntu-latest`, so no runner change is needed).

**SDK jar sourcing**: the upstream workflow fetches the Broadcom
   jar from a private repo via an `SDK_RUNTIME_SSH_KEY` deploy-key
   secret you won't have. Replace that step with your own source:
   store the appliance-extracted jar in **a private repo only**, and
   fetch it from there. Never upload the jar as a workflow artifact:
   on a public repo anyone can download workflow artifacts, which
   would amount to redistributing it. Then **also update the
   `--sdk-jar` argument** on the `build-sdk` line of the workflow to
   point at wherever your replacement step puts the jar. The explicit
   `--sdk-jar` flag overrides `VCFCF_SDK_JAR`, so setting the env var
   alone is not enough — if you leave `--sdk-jar _sdk_runtime/...` in
   place the build will look for the upstream path and fail. Do **not**
   commit the jar to a public repo (no redistribution).

<!-- COPY TO HERE -->
