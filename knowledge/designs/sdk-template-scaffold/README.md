# SDK template scaffold

This directory holds the factory-side notes for the artifacts that ship in
`sentania-labs/vcf-content-factory-sdk-template` and every SDK pak repo
instantiated from it. It is not itself a pak.

## Source of truth (decided 2026-10-18, issue #180)

**The template repo wins.** `sentania-labs/vcf-content-factory-sdk-template`
is the canonical, reviewed source for everything a pak repo carries in
`.github/workflows/` and `ci/`:

- `.github/workflows/build-pak-on-tag.yml`: the release workflow. On a `v*`
  tag it verifies the tag against `adapter.yaml`, runs the vendored defect
  gate (RULE-012), builds the `.pak` headlessly from the `sdk-buildkit` the
  workflow's `BUILDKIT_TAG` selects, with `--release`, gates on `pak-compare`, and publishes the `.pak` as the
  tag's GitHub Release with provenance. Hardened through reviewer, peer and
  Codex rounds in template PRs #22, #23 and #24.
- `.github/workflows/pak-tests.yml`: the reusable JDK matrix test workflow;
  `tests.yml` is the per-repo caller every pak PR runs.
- `ci/defect_gate.py` and `tests/ci/test_defect_gate.py`: the vendored,
  fail-closed defect gate and its tests. (An earlier revision of this README
  said the gate was deliberately absent; that predates RULE-012 and is no
  longer true.) Factory-side drift between this copy and
  `src/vcfcf_packaging/defects.py` is tracked as factory issue #226.

A copy of the workflow used to live here as `build-pak-on-tag.yml` and
drifted from the template (no defect gate here, no tag check there). It is
removed; do not re-add a mirror. Changing the workflow means a PR on the
template repo, then a copy into each live pak repo (the flow compliance #60,
synology #39 and unifi #37 used on 2026-10-16). Synology and unifi carry the
template's workflow byte for byte; compliance adds one pak-specific step
("Check generated alert definitions are current") that a re-copy must keep.

## Contents

- `BUILDING_FROM_SOURCE.md`: the canonical "Building from source" README
  section for pak repos: interactive builds from a bare pak clone (buildkit
  tarball + self-sourced Broadcom SDK jar) and fork-CI rewiring. Copy the
  marked block into each pak README under `## Building from source`.
- `repo-README.md` (below, as the template repo's own README): what a pak
  author reads after `Use this template`.

## Anatomy of a pak repo (instantiated from the template)

```
vcf-content-factory-sdk-<name>/
├─ adapter.yaml                      # name, version, build_number, adapter_kind, entry_class, bundled_content
├─ describe.xml
├─ src/…                             # adapter Java
├─ profiles/  resources/  icons/  lib/
├─ views/      <name>-*.yaml         # bundled_content, CO-LOCATED here (NOT factory-root)
├─ dashboards/ <name>-*.yaml         # bundled_content, CO-LOCATED here
├─ .github/workflows/   # build-pak-on-tag.yml, tests.yml (from the template repo)
└─ ci/                  # defect_gate.py, run_java_tests.sh (from the template repo)
```

**Critical:** `bundled_content` paths in `adapter.yaml` resolve relative to the
adapter directory (where `adapter.yaml` lives). A pak repo must carry its own
view/dashboard YAML: it cannot reference the factory's root `views/` or
`dashboards/` dirs, which do not exist in the pak repo.

## Author / release loop

1. **Author** in-tree under the factory: `cd content/sdk-adapters/<name>` (the
   gitignored clone of this repo), edit, run the local dev preview
   `python3 -m vcfcf_managementpacks build-sdk content/sdk-adapters/<name>`.
   The `sdk-adapter-author` / `sdk-adapter-reviewer` agents operate here.
2. **Commit + push** to this pak repo's `main`.
3. **Release** = push a `v*` tag. The release rules (RULE-014, the `0.x`
   dev-preview line is never tagged; RULE-012, no release while an open
   blocking defect names this pak) are enforced at **push** time by the
   factory's `.githooks/pre-push` hook. CI re-checks RULE-012 only, through
   the vendored `ci/defect_gate.py` step; its tag check confirms the tag
   matches `adapter.yaml` and does not refuse the `0.x` line, so RULE-014
   is hook-only. CI then builds the official `.pak` and publishes it as a
   Release asset. This, not a dev build and not a factory `/publish`, is
   the shippable artifact.

   **The hook only covers a clone inside a factory checkout.** It requires
   the pak to sit under `content/sdk-adapters/` with `core.hooksPath` set,
   which `scripts/bootstrap_managed_paks.sh` does for every repo registered
   in `knowledge/context/managed_paks.md`. For RULE-014, a standalone clone
   of a pak repo is **not gated at all**, and neither is a tag created in the GitHub UI or
   a push with `--no-verify`. Register the pak and let bootstrap clone it.
4. The factory references the pak by **pointer** to `…/releases/latest`; it
   never rebuilds or mirrors the binary.

## Runner requirements

The CI workflow runs on GitHub-hosted `ubuntu-latest`. The job reaches only
github.com, and the pak repos are public, so hosted minutes are free; the lab's
`runs-on: lab` pool is for jobs that must reach lab resources. The workflow
installs its own JDK (`actions/setup-java`) and Python (`actions/setup-python`,
then `pyyaml` via pip); `gh`, `tar`, `ssh`, and `curl` come with the image.

## Buildkit pinning

`BUILDKIT_TAG` in the template's workflow selects the toolchain. Pin a full `vX.Y.Z` for
explicit, reproducible opt-in, or follow the floating `v1` major tag to pick up
compatible buildkit updates automatically. The buildkit is published only by
`tooling` from the factory on an `sdk-buildkit-v*` tag.
