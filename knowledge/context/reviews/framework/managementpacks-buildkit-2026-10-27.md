# Framework review: buildkit 1.0.21 (pinnable kit, -proc:none on build-framework.sh)

- Branch: `buildkit-supply-chain-pin` (uncommitted diff), reviewed 2026-10-27
- Scope: `src/vcfcf_managementpacks/adapter_framework/build-framework.sh`,
  `src/vcfcf_managementpacks/buildkit.py` (BUILDKIT_VERSION 1.0.21),
  `tests/managementpacks/test_javac_proc_none.py` (new),
  `.github/workflows/publish-buildkit.yml`, `.github/release-notes-buildkit.md`,
  `knowledge/context/tier2_architecture.md` changelog row.
  Out of scope per brief: `third_party/idps-planner/PROJECT.yaml`, untracked review files.
- Verdict: **APPROVE** (0 BLOCKING / 2 WARNING / 2 NIT). Per delegation rule 9, fix all before the PR.

## Checks re-run

| Check | Result |
|---|---|
| Validate chain (7 packages) | all rc=0 |
| Full test suite (`-n 8 --dist=loadgroup`) | 3036 passed, 5 skipped |
| `test_javac_proc_none.py` | 7 passed on JDK 17.0.20 (control fires, so the guards discriminate) |
| Mutation: build-framework.sh with `-proc:none` removed, same test | FAILS with `ANNOTATION PROCESSOR RAN`: the test catches the regression |
| SHA256SUMS producer/consumer simulation (workflow commands verbatim, consumer snippet from release notes) | sums line is `<hash>  sdk-buildkit-1.0.21.tgz`, bare name (written after `cd dist/`), equal to the asset name `gh release create` derives from `dist/<tarball>`; consumer `sha256sum -c ci/sdk-buildkit.SHA256SUMS` resolves against cwd and passes; a tampered tarball fails with rc=1, a missing one with rc=1 |
| Render regression / pak-compare | n/a: no renderer, assembly or pak builder touched; kit content unchanged except the version stamp (build-framework.sh is not shipped in the kit, buildkit.py bundles only `adapter_framework/src/`) |

## Dimensions

1. Global-default leak (00d3382): n/a. `-proc:none` is now uniform across all four compile paths; nothing pak-specific.
2. Key collisions (6c59f6b): n/a.
3. Wire format: SHA256SUMS uses the same sha256sum format as the builder's sidecar (`buildkit.py` `_sha256_file`, `"{digest}  {name}\n"`); the workflow cross-checks the digests. Proven above.
4. Loader/validator: untouched.
5. Render regression: n/a (see table).
6. Builder/pak structure: only BUILDKIT_VERSION changes; tier2 row states built paks are identical, consistent with the code.
7. Corpus regression: clean.
8. Silent capability change: none. Floating `sdk-buildkit-v1` asset set unchanged (tarball + sidecar), so existing `sdk-buildkit-*.tgz*` consumers and the prune regex are unaffected; SHA256SUMS never reaches the floating release.
9. Stale-zip discipline: none of the trigger paths touched (`templates/`, `builder.py`, `assembly.py`, `render.py`); no `CURRENT_TEMPLATE_VERSION` bump needed. BUILDKIT_VERSION bump is present and justified (first tag carrying SHA256SUMS).
10. Test coverage: good. Behavioural test per compile path, static count guard on `sdk_builder.py` and on the kit's rewritten copy, and a JDK<23 control. CI runs JDK 17 so the control does not skip.

github-ci skill check: per-ref concurrency group (yes), actions pinned to SHA (yes), `runs-on: ubuntu-latest` on a public repo with no lab or daemon need (correct per placement rule 4), canonical-repo gate (yes). Gap: see W1.

## WARNING

- **W1** `.github/workflows/publish-buildkit.yml` (no step after checkout, line ~84). github-ci skill §Release workflows step 1: the tagged commit must be reachable from `main` (`git merge-base --is-ancestor "$GITHUB_SHA" origin/main`). The workflow has never had it, but this diff turns each versioned release into the trust anchor a pak repo commits: a `sdk-buildkit-vX.Y.Z` tag pushed on a stray branch would publish a kit with a self-consistent SHA256SUMS that a pinner then freezes as known-good. Fix: add a gate step right after checkout (`fetch-depth: 0` is already set): `git merge-base --is-ancestor "$GITHUB_SHA" origin/main || { echo "::error::tag not on main"; exit 1; }`.
- **W2** `.github/workflows/publish-buildkit.yml:55-58`. The per-ref group (correct per the skill) only serializes re-runs of the same tag. The shared state in this workflow is the floating `sdk-buildkit-v1` release (retag, upload, prune), and two different version tags still run in parallel and race on it. The comment "one run per version tag; never cancel a publish half way" is accurate but invites the reader to think the publish is serialized. Fix: say in the comment that the group does not serialize the floating release across versions. A real fix (serialize the floating step, and only move v1 forward to a higher version per skill step 5) touches the untouched floating step; open a follow-up issue for it rather than widening this PR.

## NIT

- **N1** `.github/release-notes-buildkit.md:54-58`. "Download both" is now ambiguous with three checksum-related names in the paragraph, and the reflowed line 56 overruns the file's wrap. Fix: "Download the tarball and its `.sha256` sidecar and run ...", rewrapped.
- **N2** `.github/release-notes-buildkit.md:44-50`. The pinning snippet is a bare indented `run` fragment without the `- name:` / `env: GH_TOKEN` framing the floating example above it has; a copy-paste into a workflow fails on auth. Fix: give it the same step shape as lines 18-27.

## If shipped as-is

Works: pak repos can pin `sdk-buildkit-v1.0.21` and the committed SHA256SUMS verifies the exact tarball they download; tampering or replacement fails the build. Residual risk is upstream of the checksum: nothing stops a non-main tag from minting a pinnable release (W1).
