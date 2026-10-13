# CI for the forked Python SDK packs: build on GitHub-hosted runners, publish to GHCR with attestation, attach the pak

Investigated 2026-10-13 by `api-explorer`, read-only (source, docs, anonymous
registry probes, `gh api` reads). Nothing was pushed, tagged, or created.

Scope: the two forks registered in `knowledge/context/managed_paks.md`,
`content/sdk-adapters/vsanhostmetrics/` (upstream `nickfirefoot/vsanhostmetrics`)
and `content/sdk-adapters/cluster-perf-risk/` (upstream
`gillaspy/cluster-perf-risk`). Goal: a workflow we prove in the
`sentania-labs` forks and then offer upstream as a PR that merges cleanly and
works for the maintainer with no secrets.

## Answer first

1. **The pak does not contain the image.** It carries a pointer
   (`REGISTRY`, `REPOSITORY`, `DIGEST`) in `adapter.zip!<AdapterKind>.conf`, and
   the Cloud Proxy pulls that digest **anonymously** at run time (per the SDK
   docs; not yet observed in the lab, which has no Cloud Proxy). So the image
   must be in a public registry, and the attestation has to be on the exact
   digest the pak names.
2. **The image can be built with plain `docker build`, the pak cannot.**
   `mp-build` always builds its own image, pushes it, and writes the digest the
   registry returned into the pak. It has no "skip push" or "use this digest"
   option. The clean design is therefore: let `mp-build` do the one build and
   push, driven with `-r ghcr.io/<owner>/<repo>` (which overrides the
   project's `config.json` registry), then read the digest back out of the pak
   and attest that. A plain `docker build` is still used, in a separate
   read-only job, as the pre-publish smoke test that runs on every PR.
3. **Workflow shape:** three jobs. `verify` (every PR and push, read-only)
   builds the SDK base image and the adapter image with plain docker and boots
   it. `publish` (tag push only) runs `mp-build` against GHCR with
   `GITHUB_TOKEN`, checks the pak points at the pushed digest, checks the image
   is anonymously pullable, attests the image digest and the pak, optionally
   cosign-signs, and adds an immutable version tag. `release` (tag push only,
   the only job with `contents: write`) attaches the pak to the GitHub Release.
4. **PR behavior:** a PR from our fork to upstream runs only `verify`, with a
   read-only token, after the maintainer clicks "Approve and run" (first-time
   contributor). `publish` cannot run on `pull_request` by construction. After
   merge the maintainer needs **no secrets**. One-time chores differ:
   `nickfirefoot` already has a public, hand-pushed GHCR package and must make
   sure the repo has Write in the package's "Manage Actions access";
   `gillaspy` currently publishes to Docker Hub, so the first tag creates a new
   GHCR package that he must flip to public once and re-run.
5. **vsanhostmetrics has a blocker the workflow cannot paper over:** upstream
   `main` is not an `mp-build` project (no `manifest.txt`, `Dockerfile`,
   `commands.cfg`, `conf/`, `config.json`; the build is assembled out of tree
   by `scaffold_project.py`). That has to be fixed first, upstream, or the CI
   has nothing deterministic to build.

## Evidence for (1): what mp-build produces, and where the image lives

Sources: the official SDK repo, cloned at
`reference/references/vmware-vcf-operations-integration-sdk/` (HEAD `9619df8`,
`pyproject.toml` version `1.3.1`), and the PyPI sdist
`vmware_aria_operations_integration_sdk-1.3.1` (scratchpad). The two copies of
`mp_build.py` differ only in a `pkg_resources` to `importlib.metadata` swap
(checked with `diff`).

**The pak references, it does not embed.**

- `vmware_aria_operations_integration_sdk/mp_build.py`, `build_pak_file()`:
  builds the image (`build_image`), then `_tag_and_push()` returns
  `domain, port, path, digest`, then writes `<adapter_kind>.conf`:
  `KINDKEY`, `API_VERSION`, `API_PROTOCOL`, `API_PORT`, then
  `REGISTRY=<domain[:port]>` (omitted when `use_default_registry`),
  `REPOSITORY=/<path>`, `DIGEST=<digest>` (lines ~469 to 504). The image
  object is removed from the local daemon after the push (`image.remove(force=True)`).
  `adapter.zip` gets the `.conf`, `manifest.txt`, eula, icon, `resources/`,
  `conf/`. No image layers or tar anywhere.
- `docs/references/mp-build.md` §Pak file: adapter.zip contains "A
  configuration file that includes information about the adapter, including
  the container's registry, repository, and digest."
- `docs/references/architecture.md` §Management Pack Distribution: "Within a
  Pack File, the adapter container image is referenced by the registry
  location and image digest SHA", and "the VCF Operations Cloud Proxy needs
  anonymous pull access to the registry."
- `docs/troubleshooting_and_faq/container_registries.md`: "During
  installation, VCF Operations uses the information inside the
  `<ADAPTERNAME>.conf` file to pull the container from the registry"; the
  repository must be public "so that the image can be pulled anonymously";
  Cloud Proxies "lookup images locally before attempting to pull" (the only
  private-registry workaround is a manual `docker pull` on each proxy).
- Field evidence from upstream's own lab notes,
  `content/sdk-adapters/vsanhostmetrics/docs/OFFLINE-DELIVERY.md`: the running
  container on the Cloud Proxy has
  `Config.Image = <registry>/<repo>@sha256:...`, i.e. it is started by
  RepoDigest, and `docker load` of a saved tar does not satisfy it.

**The pull is anonymous, so GHCR visibility matters.** A private GHCR package
makes the adapter fail on the Cloud Proxy with a pull error. The workflow
below checks anonymous pull before it attests or releases anything.

**mp-build's image tag is `<manifest version>_<epoch>`** (`_tag_and_push`,
`tag = manifest["version"] + "_" + str(time.time())`). Both upstreams' current
registries show exactly that pattern (anonymous probe 2026-10-13):
`ghcr.io/nickfirefoot/vsanhostmetrics` has `1.2.0_1790200136.97...` through
`1.4.x_...`; `docker.io/gillaspy/cluster-perf-risk` has `1.0.0_...` through
`1.1.x_...`. So today both maintainers build and push by hand from a
workstation and attach the pak to a release manually (nickfirefoot v1.4.6,
2026-10-06; gillaspy v1.1.4, 2026-09-02). Neither repo has any workflow
(`gh api repos/<r>/actions/workflows` total_count 0).

**What each fork's config says.**

| | cluster-perf-risk | vsanhostmetrics |
|---|---|---|
| `config.json` | `container_repository: docker.io/gillaspy/cluster-perf-risk`, `use_default_registry: false`, `default_memory_limit: 1024` | not in repo |
| `manifest.txt` | in repo, `name iSDK_ClusterPerfRisk`, `version 1.3.0`, `adapter_kinds [ClusterPerfRisk]`, placeholder display_name/vendor (fork issue #9) | not in repo (scaffold writes it out of tree) |
| `Dockerfile` | `FROM base-adapter:python-1.2.0`, no OCI labels | only `Dockerfile.reference`, same FROM, `LABEL org.opencontainers.image.source="https://github.com/nickfirefoot/vsanhostmetrics"` |
| `commands.cfg`, `conf/`, `resources/` | in repo | not in repo |
| Current image home | Docker Hub (public) | GHCR (public, `ghcr.io/nickfirefoot/vsanhostmetrics`) |

`conf/describe.xml` is absent in both, so `mp-build` generates it by running
the container and calling `adapterDefinition` (`build_pak_file`:
`adapter_container.start()`, `Describe.get(...)`). That means the publish job
needs a working Docker daemon and port 8080 free, both true on
`ubuntu-latest` hosted runners.

## Evidence for (2): what mp-build needs in CI, and whether plain docker can replace it

**What mp-build needs.**

- A Docker daemon reachable via `docker.from_env()` (`docker_wrapper.init()`).
  GitHub-hosted, not the `lab` pool (github-ci skill rule 2: the lab pool has
  no daemon).
- The base image `base-adapter:python-1.2.0`, which is **not pulled from any
  registry**. `docker_wrapper.ensure_base_image_exists()` builds it locally
  from the SDK package's bundled `images/base-python-adapter/` when absent
  (`constant.py`: "The base adapter images are now bundled with the SDK and
  built locally. Remote registry configurations are kept for legacy
  compatibility but are deprecated."). `pyproject.toml` ships `images/**/*`
  in the wheel, so a plain `pip install vmware-aria-operations-integration-sdk==1.3.1`
  is enough. The legacy remote (`projects.packages.broadcom.com/vmware_aria_operations_integration_sdk/base-adapter`)
  returns `UNAUTHORIZED` / `no such manifest` anonymously for every tag tried,
  so it is not an option.
- Base image source: `images/base-python-adapter/Dockerfile`,
  `FROM python:3.11.12-slim-bookworm`, apt upgrade, non-root user
  `aria-ops-adapter-user`, `pip install -r requirements.txt`, entrypoint
  `python3 -m swagger_server`, ports 443/8080. Version comes from
  `vmware_aria_operations_integration_sdk/container_versions.json`
  (`base_image.version 1.2.0`).
- Registry login. `is_valid_registry()` always calls `docker_wrapper.login()`,
  which shells `docker login <registry>` and adds `--username/--password`
  **only if passed**. With `docker/login-action` run first, `mp-build -r ...`
  can be called with no credentials and the CLI reuses the stored ones, which
  keeps `GITHUB_TOKEN` off argv. (Not yet run; first item of the fork proof.
  Fallback: pass `--registry-username "$GITHUB_ACTOR" --registry-password
  "$GITHUB_TOKEN"`; the runner is ephemeral and Actions masks the token.)
- `--no-ttl` (headless; every value from flags).
- Registry choice: `-r ghcr.io/<owner>/<repo>` overrides `config.json`.
  `_tag_and_push` uses the arg first, falls back to config only when absent,
  and rewrites `config.json` only when the push target differs from the
  original value; with `-r` they are equal, so nothing is rewritten. The
  Docker Hub shortcut regex (`_is_docker_hub_registry_format`) does not match
  `ghcr.io/...` (the dot fails the namespace class), so no Docker Hub prompt.
  Result in the pak: `REGISTRY=ghcr.io`, `REPOSITORY=/<owner>/<repo>`.
  (`get_config_values` will write `default_memory_limit` back into
  `config.json` if missing; harmless in a CI workspace.)

**Can plain docker build the image? Yes.** Both Dockerfiles are ordinary:
`FROM base-adapter:python-1.2.0`, copy `commands.cfg`,
`adapter_requirements.txt`, `app/`. Build the base from the SDK's bundled
directory, tag it `base-adapter:python-1.2.0`, then `docker build .`. mp-build
itself does exactly this (`build_image`, via the Docker SDK, `nocache=True`).
The `verify` job below does it with no registry at all.

**Can plain docker replace mp-build for the release? Not without
re-implementing or post-processing the pak.** The pak's `DIGEST` is whatever
mp-build's own push returned, and there is no flag to supply a digest or skip
the push. Two ways to keep image and pak consistent:

| | A. mp-build is the build (recommended) | B. buildx builds, mp-build only packs |
|---|---|---|
| Image build | mp-build, pushes to GHCR | `docker/build-push-action`, pushes to GHCR |
| Pak | mp-build output, untouched | mp-build against a throwaway `registry:2` on localhost, then rewrite `REGISTRY/REPOSITORY/DIGEST` in `adapter.zip!<kind>.conf` |
| Attested digest | read back from the pak | from build-push-action output |
| Depends on SDK registry config | only the `-r` flag | no |
| Risk | mp-build's login path (above) | post-processing a vendor artifact; describe.xml comes from a sibling build; two image builds per release |

A matches what both maintainers already do by hand, so it changes the least
for them, and the attestation covers the exact digest the pak names by
construction. B is documented in case the login reuse fails in the proof and
the argv fallback is unacceptable.

## The workflow (approach A)

File: `.github/workflows/release-pak.yml`. Generic across both repos; the
only per-repo edits are the three `env` values at the top. Actions are pinned
to commit SHAs resolved 2026-10-13 via `gh api repos/<action>/commits/<tag>`.

```yaml
# As built and proven in sentania-labs/cluster-perf-risk (branch
# tuneup/ci-ghcr-attestation, commit c6f46b5, proof tags v1.3.0-rc.1 and
# rc.2). Signing (cosign keyless, image and pak), Trivy in verify and
# publish, and both attestations are unconditional. The vsanhostmetrics
# copy differs only in repo-specific values and the test command.
# Build the adapter container on GitHub-hosted runners, scan it, publish it to
# GHCR signed and with build provenance, and attach the .pak to a GitHub Release.
#
# Why this shape:
# - A .pak does not contain the adapter. adapter.zip!<AdapterKind>.conf names
#   REGISTRY, REPOSITORY and DIGEST. Per the VMware SDK documentation, the
#   Cloud Proxy pulls this digest on first collection, ANONYMOUSLY. So the
#   image must be public, and the signature, attestation and scan must be on
#   the exact digest the pak names.
# - mp-build always builds, pushes, and writes the pushed digest into the pak.
#   So mp-build is the one build of record; this workflow drives it at GHCR and
#   reads the digest back out of the pak to scan, sign and attest it.
# - Pull requests (including from forks) only run `verify`, with a read-only
#   token. Nothing is published except from a v* tag pushed to this repo.
#
# Releasing: merge to the default branch, then
#   git tag vX.Y.Z && git push origin vX.Y.Z
# The tag sets the version. The publish job writes X.Y.Z into manifest.txt in
# the runner's working copy before mp-build (never committed), so the pak is
# named and versioned X.Y.Z. The committed manifest.txt stays at the last
# released version for hand builds; there is nothing to bump before tagging.
# A tag vX.Y.Z-rc.N publishes a prerelease and may come from any branch; its
# pak carries version X.Y.Z, and its Release and image tag keep the full name.
#
# Verifying a release: see "Build and release" in README.md.
name: build-and-publish

on:
  pull_request:
  push:
    branches: [main]
    tags: ['v*']

permissions: {}

concurrency:
  group: build-and-publish-${{ github.ref }}
  cancel-in-progress: false

env:
  PROJECT_DIR: .               # holds manifest.txt, Dockerfile, commands.cfg, conf/
  SDK_VERSION: "1.3.1"         # vmware-aria-operations-integration-sdk (mp-build)
  TRIVY_VERSION: "v0.75.0"     # scanner version used by trivy-action
  TRIVY_IGNOREFILE_PATH: .trivyignore.yaml  # documented exceptions, each with an expiry
  # Unit tests, run INSIDE the adapter image (same Python and libraries the
  # Cloud Proxy runs) with PROJECT_DIR mounted read-only at /src as the
  # working directory. Leave empty to skip.
  TEST_COMMAND: "python3 -m pip install --user -q --disable-pip-version-check --no-warn-script-location pytest==8.4.2 && python3 -m pytest -q -p no:cacheprovider tests"

jobs:
  verify:
    # Plain docker, no registry, read-only token. Proves the image builds from
    # the SDK base, the unit tests pass inside it, it has no fixable HIGH or
    # CRITICAL vulnerability, and the adapter answers adapterDefinition, which
    # is what mp-build needs at release time.
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"

      - name: Install the SDK CLI (carries the base image source)
        run: python -m pip install --disable-pip-version-check "vmware-aria-operations-integration-sdk==${SDK_VERSION}"

      - name: Build the SDK base image the Dockerfile expects
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          set -euo pipefail
          read -r images have < <(python - <<'EOF'
          import json, os, vmware_aria_operations_integration_sdk as m
          pkg = os.path.dirname(m.__file__)
          v = json.load(open(os.path.join(pkg, "container_versions.json")))["base_image"]["version"]
          print(os.path.realpath(os.path.join(pkg, "..", "images")), "python-" + v)
          EOF
          )
          want="$(sed -n 's/^FROM base-adapter:\(python-[0-9.]*\).*/\1/p' Dockerfile)"
          if [ "$want" != "$have" ]; then
            echo "::error::Dockerfile wants base-adapter:${want:-<none>} but SDK ${SDK_VERSION} provides base-adapter:${have}. Align the FROM line or SDK_VERSION."
            exit 1
          fi
          docker build -t "base-adapter:${have}" "${images}/base-python-adapter"

      - name: Build the adapter image (plain docker build)
        working-directory: ${{ env.PROJECT_DIR }}
        run: docker build -t adapter-under-test:ci .

      - name: Unit tests (inside the adapter image)
        if: env.TEST_COMMAND != ''
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          docker run --rm --entrypoint bash -e PYTHONDONTWRITEBYTECODE=1 \
            -v "$PWD:/src:ro" -w /src adapter-under-test:ci \
            -euo pipefail -c "$TEST_COMMAND"

      - name: Vulnerability report for code scanning (all severities, never fails)
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/')
        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          version: ${{ env.TRIVY_VERSION }}
          image-ref: adapter-under-test:ci
          format: sarif
          output: trivy-results.sarif
          trivyignores: ${{ env.TRIVY_IGNOREFILE_PATH }}
          exit-code: "0"

      - name: Keep the report for the code scanning job
        if: ${{ !cancelled() && github.event_name == 'push' && startsWith(github.ref, 'refs/heads/') }}
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: trivy-sarif
          path: trivy-results.sarif
          if-no-files-found: ignore

      - name: Vulnerability gate (fails on fixable HIGH or CRITICAL)
        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          version: ${{ env.TRIVY_VERSION }}
          image-ref: adapter-under-test:ci
          format: table
          severity: HIGH,CRITICAL
          ignore-unfixed: true
          trivyignores: ${{ env.TRIVY_IGNOREFILE_PATH }}
          exit-code: "1"

      - name: Boot it and fetch the adapter definition
        run: |
          set -euo pipefail
          docker run -d --name adapter -p 8080:8080 adapter-under-test:ci
          for _ in $(seq 1 30); do
            curl -fsS http://localhost:8080/apiVersion >/dev/null 2>&1 && break
            sleep 2
          done
          curl -fsS http://localhost:8080/adapterDefinition -o definition.json
          python -c 'import json,sys; d=json.load(open("definition.json")); sys.exit(0 if d else "empty adapter definition")'
          echo "adapterDefinition OK ($(wc -c < definition.json) bytes)"

      - name: Container log on failure
        if: failure()
        run: docker logs adapter || true

  code-scanning:
    # Branch pushes only: a pull request token from a fork cannot write
    # security events. Runs no repository code, only uploads the report.
    needs: verify
    if: ${{ !cancelled() && github.event_name == 'push' && startsWith(github.ref, 'refs/heads/') }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      actions: read
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: trivy-sarif

      - name: Upload to code scanning (skipped with a warning where code scanning is not enabled)
        id: upload
        continue-on-error: true
        uses: github/codeql-action/upload-sarif@24c54180a607b1449ed407dd24f251e4e9147c8d # v4.38.3
        with:
          sarif_file: trivy-results.sarif
          category: trivy-adapter-image

      - name: Say so if the upload was refused
        if: steps.upload.outcome == 'failure'
        run: echo "::warning::Code scanning refused the Trivy report (not enabled on this repository?). The verify job's gate still applies."

  publish:
    needs: verify
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write          # push the image, its signature and attestation to ghcr.io/<owner>/<repo>
      id-token: write          # Sigstore identity for attestation and cosign
      attestations: write      # store the attestation on this repo
      artifact-metadata: write # storage record for push-to-registry attestations
    outputs:
      image: ${{ steps.tag.outputs.image }}
      image_tag: ${{ steps.tag.outputs.image_tag }}
      prerelease: ${{ steps.tag.outputs.prerelease }}
      digest: ${{ steps.pak.outputs.digest }}
      pak_name: ${{ steps.pak.outputs.pak_name }}
    env:
      DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Refuse a bad tag
        id: tag
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          set -euo pipefail
          tag="$GITHUB_REF_NAME"
          if [[ ! "$tag" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)(-rc\.[0-9]+)?$ ]]; then
            echo "::error::Tag $tag is not vX.Y.Z or vX.Y.Z-rc.N"; exit 1
          fi
          ver="${BASH_REMATCH[1]}"; rc="${BASH_REMATCH[2]}"
          if [ -z "$rc" ]; then
            git fetch --no-tags origin "$DEFAULT_BRANCH"
            if ! git merge-base --is-ancestor "$GITHUB_SHA" "origin/$DEFAULT_BRANCH"; then
              echo "::error::$tag is not on $DEFAULT_BRANCH. Only -rc tags may come from other branches."; exit 1
            fi
          fi
          {
            echo "image=ghcr.io/${GITHUB_REPOSITORY,,}"
            echo "image_tag=${tag#v}"
            echo "version=$ver"
            echo "prerelease=$([ -n "$rc" ] && echo true || echo false)"
          } >> "$GITHUB_OUTPUT"

      - uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Fail early if the version tag is already published
        env:
          IMAGE: ${{ steps.tag.outputs.image }}
          IMAGE_TAG: ${{ steps.tag.outputs.image_tag }}
        run: |
          set -euo pipefail
          command -v skopeo >/dev/null || { sudo apt-get update -q && sudo apt-get install -yq skopeo; }
          # Courtesy check only; the gate is "Add the immutable version tag"
          # below, which re-checks once the package certainly exists.
          if err="$(skopeo inspect --raw --authfile "$HOME/.docker/config.json" "docker://${IMAGE}:${IMAGE_TAG}" 2>&1 >/dev/null)"; then
            echo "::error::${IMAGE}:${IMAGE_TAG} already exists. Version tags are immutable; release a new patch version."; exit 1
          elif grep -qi 'manifest unknown' <<<"$err"; then
            echo "${IMAGE}:${IMAGE_TAG} is not published yet."
          else
            echo "::warning::Could not tell whether ${IMAGE}:${IMAGE_TAG} exists (expected on the first release, before the package exists): ${err}"
          fi

      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"

      - name: Install the SDK CLI
        run: python -m pip install --disable-pip-version-check "vmware-aria-operations-integration-sdk==${SDK_VERSION}"

      - name: Stamp the manifest version from the tag (runner copy only, never committed)
        working-directory: ${{ env.PROJECT_DIR }}
        env:
          VERSION: ${{ steps.tag.outputs.version }}
        run: |
          set -euo pipefail
          python3 - "$VERSION" <<'EOF'
          import json, sys
          version = sys.argv[1]
          with open("manifest.txt", encoding="utf-8") as f:
              manifest = json.load(f)
          if "version" not in manifest:
              sys.exit("manifest.txt has no version field to stamp")
          committed = manifest["version"]
          manifest["version"] = version
          with open("manifest.txt", "w", encoding="utf-8") as f:
              json.dump(manifest, f, indent=4, ensure_ascii=False)
              f.write("\n")
          with open("manifest.txt", encoding="utf-8") as f:
              if json.load(f)["version"] != version:
                  sys.exit("manifest.txt did not take the stamped version")
          print(f"manifest.txt version {committed} -> {version} (this runner only; the committed file is unchanged)")
          EOF

      - name: mp-build (builds, pushes to GHCR, writes the digest into the pak)
        env:
          IMAGE: ${{ steps.tag.outputs.image }}
        run: |
          set -euo pipefail
          # -r and --push-registry override config.json. No credentials on
          # argv: mp-build's docker login reuses the ones docker/login-action
          # stored above.
          mp-build -p "$PROJECT_DIR" --no-ttl -r "$IMAGE" --push-registry "$IMAGE"

      - name: Read the digest the pak points at, and check it
        id: pak
        working-directory: ${{ env.PROJECT_DIR }}
        env:
          IMAGE: ${{ steps.tag.outputs.image }}
          VERSION: ${{ steps.tag.outputs.version }}
        run: |
          set -euo pipefail
          shopt -s nullglob
          paks=(build/*.pak)
          [ "${#paks[@]}" -eq 1 ] || { echo "::error::expected one pak in build/, found ${#paks[@]}"; exit 1; }
          digest="$(python3 - "${paks[0]}" "$IMAGE" "$VERSION" <<'EOF'
          import io, json, re, sys, zipfile
          pak, image, version = sys.argv[1:]
          with zipfile.ZipFile(pak) as z:
              manifest = json.loads(z.read("manifest.txt"))
              if manifest.get("version") != version:
                  sys.exit(f"pak manifest version {manifest.get('version')!r}, expected {version} from the tag")
              kind = manifest["adapter_kinds"][0]
              with zipfile.ZipFile(io.BytesIO(z.read("adapter.zip"))) as a:
                  conf = a.read(kind + ".conf").decode()
          f = dict(l.split("=", 1) for l in conf.splitlines() if "=" in l)
          reg, repo = image.split("/", 1)
          if f.get("REGISTRY") != reg or f.get("REPOSITORY") != "/" + repo:
              sys.exit(f"pak points at {f.get('REGISTRY')}{f.get('REPOSITORY')}, expected {image}")
          if not re.fullmatch(r"sha256:[0-9a-f]{64}", f.get("DIGEST", "")):
              sys.exit(f"bad DIGEST in pak: {f.get('DIGEST')!r}")
          print(f["DIGEST"])
          EOF
          )"
          # The registry must serve exactly those manifest bytes.
          got="sha256:$(skopeo inspect --raw --authfile "$HOME/.docker/config.json" "docker://${IMAGE}@${digest}" | sha256sum | cut -d' ' -f1)"
          [ "$got" = "$digest" ] || { echo "::error::registry manifest $got != pak DIGEST $digest"; exit 1; }
          {
            echo "digest=$digest"
            echo "image_ref=${IMAGE}@${digest}"
            echo "pak_name=$(basename "${paks[0]}")"
            echo "pak_path=${PROJECT_DIR}/${paks[0]}"
          } >> "$GITHUB_OUTPUT"

      - name: Vulnerability gate on the pushed digest (fails on fixable HIGH or CRITICAL)
        # mp-build rebuilds without cache, so this scans the exact bytes the
        # pak names, not the verify job's sibling build. Nothing is signed,
        # attested, version-tagged or released if it fails.
        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          version: ${{ env.TRIVY_VERSION }}
          image-ref: ${{ steps.pak.outputs.image_ref }}
          format: table
          severity: HIGH,CRITICAL
          ignore-unfixed: true
          trivyignores: ${{ env.TRIVY_IGNOREFILE_PATH }}
          exit-code: "1"

      - name: Check the image is anonymously pullable (Cloud Proxies pull without login)
        env:
          IMAGE: ${{ steps.tag.outputs.image }}
          DIGEST: ${{ steps.pak.outputs.digest }}
        run: |
          set -euo pipefail
          repo="${IMAGE#ghcr.io/}"
          hint="Make the package public (Package settings > Change visibility), then re-run failed jobs. Nothing has been signed, tagged or released yet."
          # A private package already fails here: the anonymous token request is refused.
          if ! tok="$(curl -fsS "https://ghcr.io/token?scope=repository:${repo}:pull" | jq -er .token)"; then
            echo "::error::Anonymous token for ${IMAGE} was refused, so Cloud Proxies cannot pull it. ${hint}"
            exit 1
          fi
          code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${tok}" \
            -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.index.v1+json' \
            "https://ghcr.io/v2/${repo}/manifests/${DIGEST}")"
          if [ "$code" != "200" ]; then
            echo "::error::Anonymous pull of ${IMAGE}@${DIGEST} returned HTTP ${code}. ${hint}"
            exit 1
          fi
          echo "Anonymous pull of ${IMAGE}@${DIGEST} OK"

      - name: Attest build provenance on the image digest
        uses: actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2
        with:
          subject-name: ${{ steps.tag.outputs.image }}
          subject-digest: ${{ steps.pak.outputs.digest }}
          push-to-registry: true

      - name: Attest build provenance on the pak
        uses: actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2
        with:
          subject-path: ${{ steps.pak.outputs.pak_path }}

      - uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2
        with:
          cosign-release: v3.0.6

      - name: Cosign keyless signatures on the image digest and the pak
        working-directory: ${{ env.PROJECT_DIR }}
        env:
          IMAGE_REF: ${{ steps.pak.outputs.image_ref }}
          PAK_PATH: ${{ steps.pak.outputs.pak_path }}
        run: |
          set -euo pipefail
          # Keyless: the certificate is issued to this workflow run's OIDC
          # identity; no key or secret exists to manage.
          cosign sign --yes "$IMAGE_REF"
          pak="build/$(basename "$PAK_PATH")"
          cosign sign-blob --yes --bundle "${pak}.sigstore.json" "$pak"
          # Prove the commands the README gives consumers work on what we just made.
          id="https://github.com/${GITHUB_REPOSITORY}/.github/workflows/build-and-publish.yml@${GITHUB_REF}"
          iss="https://token.actions.githubusercontent.com"
          cosign verify --certificate-identity "$id" --certificate-oidc-issuer "$iss" "$IMAGE_REF" >/dev/null
          cosign verify-blob --certificate-identity "$id" --certificate-oidc-issuer "$iss" --bundle "${pak}.sigstore.json" "$pak"

      - name: Add the immutable version tag (same digest, no rebuild)
        env:
          IMAGE: ${{ steps.tag.outputs.image }}
          IMAGE_TAG: ${{ steps.tag.outputs.image_tag }}
          DIGEST: ${{ steps.pak.outputs.digest }}
        run: |
          set -euo pipefail
          auth=(--authfile "$HOME/.docker/config.json")
          # The package exists and this token can read it now, so anything
          # other than "manifest unknown" is a reason to stop, not to tag.
          if err="$(skopeo inspect --raw "${auth[@]}" "docker://${IMAGE}:${IMAGE_TAG}" 2>&1 >/dev/null)"; then
            echo "::error::${IMAGE}:${IMAGE_TAG} already exists. Version tags are immutable; release a new patch version."; exit 1
          elif ! grep -qi 'manifest unknown' <<<"$err"; then
            echo "::error::Could not check ${IMAGE}:${IMAGE_TAG} before tagging: ${err}"; exit 1
          fi
          skopeo copy --preserve-digests "${auth[@]}" \
            "docker://${IMAGE}@${DIGEST}" "docker://${IMAGE}:${IMAGE_TAG}"
          got="$(skopeo inspect "${auth[@]}" --format '{{.Digest}}' "docker://${IMAGE}:${IMAGE_TAG}")"
          [ "$got" = "$DIGEST" ] || { echo "::error::${IMAGE}:${IMAGE_TAG} resolves to $got, expected $DIGEST"; exit 1; }

      - name: Checksums
        working-directory: ${{ env.PROJECT_DIR }}/build
        run: sha256sum -- *.pak *.pak.sigstore.json > SHA256SUMS

      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: pak
          path: |
            ${{ env.PROJECT_DIR }}/build/*.pak
            ${{ env.PROJECT_DIR }}/build/*.pak.sigstore.json
            ${{ env.PROJECT_DIR }}/build/SHA256SUMS
          if-no-files-found: error

  release:
    # The only job that can write to the repo, and it runs no build code.
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: pak
          path: dist

      - name: Create or update the GitHub Release
        env:
          GH_TOKEN: ${{ github.token }}
          IMAGE: ${{ needs.publish.outputs.image }}
          IMAGE_TAG: ${{ needs.publish.outputs.image_tag }}
          DIGEST: ${{ needs.publish.outputs.digest }}
          PAK: ${{ needs.publish.outputs.pak_name }}
          PRERELEASE: ${{ needs.publish.outputs.prerelease }}
        run: |
          set -euo pipefail
          id_re="^https://github\\.com/${GITHUB_REPOSITORY//./\\.}/\\.github/workflows/build-and-publish\\.yml@refs/tags/v"
          cat > notes.md <<EOF
          Adapter image. The pak names it by digest. Per the VMware SDK
          documentation, the Cloud Proxy pulls this digest on first collection,
          from ghcr.io (outbound 443). VCF Operations does not check signatures,
          attestations or scans when it installs a pak; check them yourself:

              ${IMAGE}:${IMAGE_TAG}
              ${IMAGE}@${DIGEST}

          Built by GitHub Actions run
          ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}
          from commit ${GITHUB_SHA}.

              sha256sum -c SHA256SUMS
              cosign verify ${IMAGE}@${DIGEST} \\
                --certificate-identity-regexp '${id_re}' \\
                --certificate-oidc-issuer https://token.actions.githubusercontent.com
              cosign verify-blob ${PAK} --bundle ${PAK}.sigstore.json \\
                --certificate-identity-regexp '${id_re}' \\
                --certificate-oidc-issuer https://token.actions.githubusercontent.com
              gh attestation verify oci://${IMAGE}@${DIGEST} --repo ${GITHUB_REPOSITORY}
              gh attestation verify ${PAK} --repo ${GITHUB_REPOSITORY}
              trivy image --severity HIGH,CRITICAL --ignore-unfixed ${IMAGE}@${DIGEST}

          The pak is not Broadcom-signed: install with "Ignore the PAK file signature checking".
          EOF
          flags=(--repo "$GITHUB_REPOSITORY" --title "$GITHUB_REF_NAME" --notes-file notes.md --verify-tag)
          [ "$PRERELEASE" = "true" ] && flags+=(--prerelease)
          gh release create "$GITHUB_REF_NAME" dist/* "${flags[@]}" \
            || gh release upload "$GITHUB_REF_NAME" dist/* --repo "$GITHUB_REPOSITORY" --clobber
```

Per-repo values:

| | cluster-perf-risk | vsanhostmetrics |
|---|---|---|
| `PROJECT_DIR` | `.` | `.` once the project skeleton is committed (see blocker) |
| `TEST_COMMAND` | `pip install -r adapter_requirements.txt pytest && pytest -q tests` (unverified that `tests/` runs standalone) | `python3 test_perfsvc.py` (QUICKSTART: "expect 26/26") |
| Image | `ghcr.io/gillaspy/cluster-perf-risk` (new) | `ghcr.io/nickfirefoot/vsanhostmetrics` (exists, public) |

Design notes on the YAML:

- **Least privilege by job.** Workflow default `permissions: {}`. `verify`
  has `contents: read` only. `publish` has `contents: read` plus the four
  publish/attest permissions; `contents: write` lives only in `release`, which
  executes no repo code. Scott's list said `contents: read` for the publish
  path; creating a Release needs `contents: write`, hence the split.
- **`artifact-metadata: write`** is required by `actions/attest` v4 (which
  `attest-build-provenance` v4 wraps) to create the storage record when
  `push-to-registry: true` (actions/attest README, Usage). If the runner
  rejects the key, set `create-storage-record: false` instead.
- **The upstream action, not the org composite.** `sentania-labs/.github`
  has `.github/actions/attest-provenance` (file subjects, refuses private
  repos). A third-party repo should not depend on a sentania-labs repo, so
  the workflow calls `actions/attest-build-provenance` directly. Same
  pattern as `sentania-labs/air-gap-gitlab-ci-tools/.github/workflows/release.yml`
  (image digest attest with `push-to-registry`, cosign keyless).
- **Smoke before publish.** `verify` gates `publish` (`needs`). mp-build also
  boots the container to generate describe.xml before it pushes, so a
  non-starting image fails before reaching the registry.
- **Immutability vs idempotency.** mp-build rebuilds with `nocache=True`
  and a timestamped tag, so a re-run produces a new digest; it cannot be
  idempotent at the image level. The version tag is created last, after the
  anonymous-pull check and attestation, so a re-run after any earlier failure
  is safe (it leaves an orphaned `X.Y.Z_<epoch>` tag, which is how both
  maintainers' registries already look). Once `:X.Y.Z` exists the job refuses,
  and the fix is a new patch version. The Release step is idempotent
  (`upload --clobber`).
- **No `latest`.** The pak pins a digest, so `latest` serves nobody in the
  install path. Add it only if a maintainer wants it (github-ci skill: it must
  follow the highest version, not the newest push).
- **amd64 only.** Cloud Proxies are x86_64; mp-build builds for the runner
  arch, `ubuntu-latest` is amd64. Multi-arch is not needed.

## Blocker: vsanhostmetrics is not an mp-build project on main

Upstream `main` (same commit as the fork, `49ac57f`) has `app/`, `content/`,
`Dockerfile.reference`, `eula.txt`, `pak_icon.png`, `scaffold_project.py`,
but no `manifest.txt`, `Dockerfile`, `commands.cfg`, `adapter_requirements.txt`,
`conf/`, `resources/`, or `config.json`. The documented build
(QUICKSTART §Building it yourself) runs `scaffold_project.py` to generate a
project elsewhere, copies `app/` and the icon in, hand-bumps `manifest.txt`,
then runs mp-build there. Two problems for CI:

- `scaffold_project.py` hard-codes `PROJECT = "/home/vsanmp/vsan-host-metrics"`
  and ignores its argument, although QUICKSTART invokes it as
  `python3 scaffold_project.py ~/vsan-host-metrics`.
- The released pak's version and contents depend on untracked, hand-edited
  files, so there is nothing for a tag-matches-manifest gate to check, and
  `adapter_requirements.txt` (pyVmomi, fork issue #5) is not tracked either.

Fix, as its own upstream PR before the CI PR (or as the first commit of it):
commit the generated project files at the repo root (rename
`Dockerfile.reference` to `Dockerfile`; add `manifest.txt` with the real
version and `pak_icon`, `commands.cfg`, `adapter_requirements.txt` with
pyVmomi pinned, `conf/`, `resources/`, `config.json` pointing at
`ghcr.io/nickfirefoot/vsanhostmetrics`), and either delete
`scaffold_project.py` or fix its path handling. Whether the repo's
`content/dashboards` should ship in the pak is the maintainer's call; today
QUICKSTART does not copy it.

cluster-perf-risk has no such blocker: it is already a complete mp-build
project. Recommended small additions in the same PR: an
`org.opencontainers.image.source` label in the Dockerfile (links the GHCR
package page to the repo), and the manifest placeholder cleanup tracked as
fork issue #9 (separate PR is fine).

## PR plan

**Phase 0, prerequisites (per repo, on fork branches).**

- vsanhostmetrics: the project-skeleton PR above. Upstream first, or the
  workflow PR stacks on it.
- cluster-perf-risk: decide with gillaspy whether GHCR replaces Docker Hub.
  The workflow is GHCR-only and needs no secret; pushing to Docker Hub would
  need a Docker Hub token secret and is out of scope.

**Phase 1, prove it in the sentania-labs fork.** Fork convention is that
`main` tracks upstream and work happens on branches (`managed_paks.md`).

1. Branch `ci/ghcr-release` in `sentania-labs/<repo>`, add the workflow (and
   for vsanhostmetrics, the skeleton).
2. Open a PR inside the fork (branch to fork `main`) to watch `verify` run on
   `pull_request` with a read-only token. Do not merge it.
3. Push tag `v<manifest version>-rc.1` on the branch. The `-rc` form is
   allowed off the default branch and publishes a prerelease, so the fork's
   `main` stays clean. Expect `publish` to stop at the anonymous-pull check
   on the first run, because `ghcr.io/sentania-labs/<repo>` is new; make that
   package public (org allows public packages; the existing sentania-labs
   container packages are public) and re-run failed jobs.
4. Checks that make it "seen working":
   - `gh attestation verify oci://ghcr.io/sentania-labs/<repo>@<digest> --repo sentania-labs/<repo>`
   - `gh attestation verify <pak> --repo sentania-labs/<repo>`
   - unzip the pak, confirm `REGISTRY=ghcr.io`, `REPOSITORY=/sentania-labs/<repo>`,
     `DIGEST` equal to the attested digest
   - anonymous `docker pull ghcr.io/sentania-labs/<repo>@<digest>` from a
     logged-out host
   - optional, on Scott's go and through `content-installer`: install the rc
     pak on the lab and confirm the Cloud Proxy pulls from ghcr.io and
     collects. This is the only check that proves the end-to-end install path.
   - confirm `mp-build` reused the login-action credentials (no
     `--registry-password` needed). If not, switch to the argv fallback.
5. Clean up after the proof. Deleting the fork prerelease, the rc tag, and
   the GHCR package versions is destructive and outward-facing: needs Scott's
   verbatim go recorded first (his rule 8). Leaving them as public evidence is
   also defensible.

**Phase 2, the upstream PR.** From `sentania-labs:ci/ghcr-release` to
`<upstream>:main`, containing:

- `.github/workflows/release-pak.yml` with the repo's `env` values (and the
  `-rc` path kept; it is useful to maintainers too).
- A README section, "Releases and verification": how to cut a release (bump
  `manifest.txt`, merge, push `vX.Y.Z`), where the image lives, the two
  `gh attestation verify` commands, the Cloud Proxy egress requirement
  (outbound 443 to ghcr.io), and that the pak is unsigned.
- cluster-perf-risk: the Dockerfile OCI label. vsanhostmetrics: already has
  one.
- PR body: link to the green fork run, the fork prerelease, and the verify
  command output, so the maintainer can see it working before merging.

How the PR behaves upstream: the `pull_request` run from a fork needs the
maintainer's "Approve and run" (first-time contributor policy); it gets a
read-only `GITHUB_TOKEN` and no secrets; only `verify` runs, because
`publish` requires a tag push. `push: branches: [main]` re-runs `verify`
after merge. Nothing publishes until the maintainer pushes a tag.

**What the maintainer does after merge.**

| | nickfirefoot (vsanhostmetrics) | gillaspy (cluster-perf-risk) |
|---|---|---|
| Secrets | none | none |
| Package | `ghcr.io/nickfirefoot/vsanhostmetrics` exists and is public, but was pushed by hand with a personal token. Package settings > Manage Actions access: make sure `nickfirefoot/vsanhostmetrics` has **Write**, or the first tag fails at mp-build's push with `permission_denied` | first tag creates `ghcr.io/gillaspy/cluster-perf-risk`; the run stops at the anonymous-pull check; set the package public once and re-run failed jobs |
| Habit change | stop running mp-build and uploading paks by hand; merge, tag (CI stamps the manifest version from the tag; the committed manifest matters only for hand builds) | same; also update README and `config.json` references from docker.io if he adopts GHCR |
| Signing | nothing to set: cosign keyless signing of the image and the pak is unconditional in the as-built workflow | same |
| Repo setting check | Actions > General: allow non-GitHub actions (docker, sigstore). Default allows them | same |

## Open questions

1. **Login reuse.** Does `docker login ghcr.io` with no flags and no TTY
   succeed from the credentials `docker/login-action` stored? Expected yes;
   settled by the first fork run. Fallback is the argv form.
2. **New-package visibility.** Whether a GHCR package first pushed from a
   public repo's workflow starts public or private was not verified. The
   workflow handles both (it stops before tagging and tells the maintainer),
   but the fork run will tell us which one-time step to document.
3. **Actions access on nickfirefoot's existing package.** Whether a
   hand-pushed package whose `image.source` label names the repo already
   grants that repo's workflows Write, or needs the manual grant. Only
   nickfirefoot can see or change it.
4. **Image source label in the fork proof.** vsanhostmetrics' label names
   `nickfirefoot/vsanhostmetrics`; a push from `sentania-labs` will be linked
   to the workflow's repo via `GITHUB_TOKEN`, and the cross-owner label is
   expected to be ignored. Cosmetic; confirm in the proof.
5. **cluster-perf-risk registry.** GHCR or stay on Docker Hub. Staying needs
   a secret and changes the PR from "no maintainer setup" to "add a token".
6. **vsanhostmetrics skeleton.** Upstream may prefer to keep the out-of-tree
   scaffold. Then the CI would need an assemble step that recreates the
   project, which reintroduces untracked state; we should argue for committing
   it.
7. **TEST_COMMAND for cluster-perf-risk.** Whether `tests/` runs without a
   live Ops instance was not checked.
8. **Approach B** (buildx image, mp-build only packs, `.conf` rewritten) is
   kept in reserve; not recommended unless question 1 fails and argv
   credentials are unacceptable.
9. **Official SDK repo has no container-adapter CI to model on.**
   `reference/references/vmware-vcf-operations-integration-sdk/.github/workflows/`
   holds `aria-operations-integration-sdk.yaml` (lint and pytest of the SDK
   itself and its Python/Java libraries, `on: [pull_request]`), `black.yaml`,
   and two documentation workflows. Nothing builds or publishes an adapter
   image or pak. The workflow above is original, modeled on
   `sentania-labs/air-gap-gitlab-ci-tools` (GHCR, attest, cosign) and the
   compliance pak's `build-pak-on-tag.yml` (tag-equals-version gate, Release
   upload).

## Decision 2026-10-13: vsanhostmetrics project files are manufactured once in the fork and committed

Scott, verbatim: "I mean we manufacutre the porject and manifest in our fork
and then make it part of the PR, right?" (correcting an earlier reading).
The mp-build project files for vsanhostmetrics (`manifest.txt`,
`Dockerfile`, `commands.cfg`, `conf/`, `config.json`, whatever the scaffold
script assembles) are generated once in the sentania-labs fork, committed
on the CI branch, and included in the upstream PR with the workflow. CI
does not run the scaffold; it builds from the committed project. The PR
body explains the files to the author and that the scaffold script can be
retired or kept as documentation. `manifest.txt` version is stamped by CI
from the tag at build time (sed into the work copy, not committed).

Task, Scott verbatim: "Build the CIs that build installable versions of
both of those MPs in our forks". Order: cluster-perf-risk first (already an
mp-build project), then vsanhostmetrics (project files first, then the
workflow). Each proven by a tag run in the fork publishing to
`ghcr.io/sentania-labs/<repo>` with attestation and a Release carrying the
pak; the pak then installed on devel through `content-installer` under its
own go, which is the end-to-end proof that the Cloud Proxy pulls from GHCR.

## Requirement 2026-10-13: attested, signed, scanned

Scott, verbatim: "we should insure the image is attested, signed, and
security scanning by something like trivy". The workflow therefore carries
all three, none optional:

- **Attested:** `actions/attest-build-provenance` on the pushed image digest
  and on the pak file (SLSA provenance, stored with the package and the
  repo's attestations).
- **Signed:** cosign keyless (sigstore, the job's OIDC identity) on the image
  digest; the pak blob signed the same way with the signature bundle attached
  to the Release. Consumers verify with the workflow identity regex and the
  GitHub OIDC issuer; no long-lived key anywhere.
- **Scanned:** Trivy on the built image in `verify` (every PR and push) and
  again in `publish` before anything is pushed, failing on HIGH and CRITICAL
  findings that have a fix; SARIF uploaded to code scanning on push and tag
  runs (a fork PR token cannot). A scan failure blocks the publish.

The README section for consumers lists the three checks: `cosign verify`,
`gh attestation verify` (image and pak), `trivy image` on the published
digest.

### What the platform does with all this: nothing

Scott, verbatim: "the pproblem is the pak install doesn't do those things
because unless they are in an offline mode - they are pulling directly from
the ghcr, but it doesn't mean we shouldn't do those things and provide
guideance." The Cloud Proxy pulls the digest the pak names and verifies no
signature, attestation or scan. The value is for the consumer who checks
before install, and the pak's pinned digest is what makes the check exact.
The README therefore carries: verify the digest the pak pins (read it from
the adapter conf inside the pak) with cosign, gh attestation and trivy; for
a private registry or air-gapped site, pull, verify, copy preserving the
digest (crane or cosign copy), rebuild the pak with `mp-build -r` against
the mirror, verify again. The README states plainly that Ops never
enforces any of it.

### Sidelined: a custom worker image

Scott, 2026-10-13: "sideline that thought and get the CI working". A
prebuilt worker image (SDK CLI, base image, Trivy, cosign) would only make
sense on the lab's self-hosted pool for our own fork runs; the upstream
workflow stays on plain hosted runners installing the pinned SDK from PyPI
so the maintainer's CI depends on nobody but VMware. Revisit if the number
of Python packs grows or lab-registry verification is wanted.

## As built for cluster-perf-risk (branch tuneup/ci-ghcr-attestation, ec4f61b, 2026-10-13)

Changes from the design text above, found while building and proving locally:

- cosign v3 writes one bundle per artifact (`<pak>.sigstore.json`, signature
  and certificate together); that bundle goes on the Release.
- The anonymous-pull check calls the token endpoint without `curl -f` so a
  private package yields guidance instead of a dead step.
- "Tag already exists" treats only `manifest unknown` as absent and
  re-checks before tagging; any other registry error stops the run.
- `--push-registry` added to mp-build; the stored docker login is reused with
  nothing on argv (design open question 1 answered: yes).
- Tests run inside the adapter image (the SDK lib needs `requests` from the
  base image).
- SARIF upload only on branch pushes (tag refs unverified for code scanning).
- Mirror flow: `mp-build -r <mirror>` would produce a new, unsigned digest;
  the README instead copies with `crane copy` (digest preserved), verifies
  the mirror's digest, and points the pak conf at the mirror keeping the
  verified DIGEST; `oras copy -r` carries signatures.
- Trivy exceptions: `.trivyignore.yaml` lists eight SDK-inherited HIGH
  findings (cryptography 44.0.0 pinned exactly by the SDK lib 1.1.0; pip's
  vendored msgpack, urllib3, setuptools in the base image) by exact version
  with reasons, expiring 2027-01-11. Scott, 2026-10-13: "if we can't do
  anythign abou them, that's acceptable". New findings still fail.
- Manifest keys DISPLAY_NAME / DESCRIPTION / VENDOR are the SDK's
  localization keys resolved through resources.properties, not placeholders
  (assessment finding 9 corrected).

Proof tag `v1.3.0-rc.1` pushed to the fork 2026-10-13 ~3:45 PM; run 38471417171.

### Proof run, cluster-perf-risk fork, 2026-10-13 ~3:50 PM

Run 38471417171 on tag `v1.3.0-rc.1`: verify, publish and release all
succeeded on the first run; code-scanning skipped on the tag ref by design.
Package `ghcr.io/sentania-labs/cluster-perf-risk` was created public by the
workflow's own first push (design open question 2 answered: public). Release
`v1.3.0-rc.1` (prerelease) carries `ClusterPerfRisk_1.3.0.pak`, its sigstore
bundle and SHA256SUMS. Verified from the workstation: `gh attestation
verify` passes for the image digest
`sha256:f995d4535d380379329d61b2a4c4f98de3efec9fcb65c2dd1f94f5bc7f0a5e51`
and for the pak; the pak's adapter conf pins exactly that registry,
repository and digest. cosign verify not run locally (cosign not
installed); the workflow's own self-verify step passed. Still unproven: the
Cloud Proxy pulling that digest from GHCR at install, which needs the rc
pak installed on devel under its own go (copied to
`dist/ClusterPerfRisk_1.3.0.pak`).

### vsanhostmetrics, as built (branch tuneup/ci-ghcr-attestation-release, fce9f17, 2026-10-13)

Base is the author's release branch `agent/beta-vsan-host-metrics` (v1.4.6
plus five docs commits), not `main` (stale at 1.2.3, one failing test):
Scott confirmed the release branch. Three commits: the mp-build project
files generated once and compared byte for byte with the published v1.4.6
pak and image (manifest, resources, schemas, app/, dashboards and views
identical; pyvmomi pinned 8.0.3.0.1 as the image carries); a views refresh
(the committed views were older than the shipped ones; the author's own
generator reproduces all 30 shipped views, so once the checkout is the
build source this commit keeps the release unchanged); the workflow
cherry-picked with `RELEASE_BRANCHES: "main agent/beta-vsan-host-metrics"`
and the test step working on a copy inside the container because one test
rewrites a source file. Verify steps all pass locally (56 tests). Extra
files in the pak versus the shipped one: the content/*.md and help HTML,
untested on install. Proof tag `v1.4.6-rc.1`, run 38477153855. A main-based
branch (`tuneup/ci-ghcr-attestation`, 461951d) is kept locally for
reference, not pushed.

### Proof run, vsanhostmetrics fork, 2026-10-13 ~5:30 PM

Run 38477153855 on tag `v1.4.6-rc.1`: verify, publish and release
succeeded first run; package created public; Release carries
`VsanHostMetrics_1.4.6.pak`, its sigstore bundle and SHA256SUMS. Verified
from the workstation: `gh attestation verify` passes for the pak and for
the image digest
`sha256:62577d09ba15dde8f8bdec3b30d099375ec28f8a88ff7a751cefc026f048ba25`,
which is what the pak's adapter conf pins. Both forks' CI are therefore
proven through publish. Platform-side proof (Cloud Proxy pull and
collection) is blocked on devel having no Cloud Proxy (see the approval
record 2026-10-13-python-pack-rc-devel-install.md).

### Status 2026-10-13: complete at publish; platform proof deferred

Scott: "the python paks install on dv: red herring - there is not cloud
proxy so it won't work". Both forks' CI is done and proven through
publish (image and pak attested, signed, scanned; pak pins the digest).
The install-and-collect proof needs an Ops instance with a Cloud Proxy
and is deferred until one exists; it is not a gap in the workflows.
Upstream PRs are on hold ("no upstream PRs yet").

### Runner image 2026-10-13

Scott: "we should update the CIs so they don't run on ubuntu 24. either
latest or push them to 26 already." Both fork workflows now use
`ubuntu-latest` (amd64), so the maintainer never tracks a runner version;
the lab's other pak workflows already do the same. Design text above
updated to match.
