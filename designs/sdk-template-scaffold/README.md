# SDK template scaffold (canonical source)

This directory holds the **canonical, diffable source** for the artifacts that
ship in `sentania-labs/vcf-content-factory-sdk-template` and every SDK pak repo
instantiated from it. It is not itself a pak — it is the seed the template repo
carries plus the reference CI workflow, kept in the factory so the workflow can
be maintained centrally and PR'd.

## Contents

- `build-pak-on-tag.yml` — the per-pak CI workflow. Copy to
  `.github/workflows/build-pak-on-tag.yml` in each pak repo. On a `v*` tag it
  pulls the published `sdk-buildkit` tarball from the factory's Releases, builds
  the `.pak` headlessly (no agent, no factory checkout), gates on `pak-compare`,
  and attaches the `.pak` to the tag's GitHub Release.
- `repo-README.md` (below, as the template repo's own README) — what a pak
  author reads after `Use this template`.
- `BUILDING_FROM_SOURCE.md` — the canonical "Building from source" README
  section for pak repos: interactive builds from a bare pak clone (buildkit
  tarball + self-sourced Broadcom SDK jar) and fork-CI rewiring. Copy the
  marked block into each pak README under `## Building from source`.

## Anatomy of a pak repo (instantiated from the template)

```
vcf-content-factory-sdk-<name>/
├─ adapter.yaml                      # name, version, build_number, adapter_kind, entry_class, bundled_content
├─ describe.xml
├─ src/…                             # adapter Java
├─ profiles/  resources/  icons/  lib/
├─ views/      <name>-*.yaml         # bundled_content, CO-LOCATED here (NOT factory-root)
├─ dashboards/ <name>-*.yaml         # bundled_content, CO-LOCATED here
└─ .github/workflows/build-pak-on-tag.yml
```

**Critical:** `bundled_content` paths in `adapter.yaml` resolve relative to the
adapter directory (where `adapter.yaml` lives). A pak repo must carry its own
view/dashboard YAML — it cannot reference the factory's root `views/` or
`dashboards/` dirs, which do not exist in the pak repo.

## Author / release loop

1. **Author** in-tree under the factory: `cd content/sdk-adapters/<name>` (the
   gitignored clone of this repo), edit, run the local dev preview
   `python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/<name>`.
   The `sdk-adapter-author` / `sdk-adapter-reviewer` agents operate here.
2. **Commit + push** to this pak repo's `main`.
3. **Release** = push a `v*` tag. CI builds the official `.pak` and publishes it
   as a Release asset. This — not a dev build, not a factory `/publish` — is the
   shippable artifact.
4. The factory references the pak by **pointer** to `…/releases/latest`; it
   never rebuilds or mirrors the binary.

## Runner requirements

The CI workflow needs, on the runner: a **JDK 11+** (`javac`/`jar`), `python3`
+ pip (for `pyyaml`), `gh`, and `tar`. The sentania-labs runner image currently
lacks a JDK — either bake `default-jdk` into the image (then drop the
`setup-java` step) or keep the `actions/setup-java` step in the workflow.

## Buildkit pinning

`BUILDKIT_TAG` in the workflow selects the toolchain. Pin a full `vX.Y.Z` for
explicit, reproducible opt-in, or follow the floating `v1` major tag to pick up
compatible buildkit updates automatically. The buildkit is published only by
`tooling` from the factory on an `sdk-buildkit-v*` tag.
