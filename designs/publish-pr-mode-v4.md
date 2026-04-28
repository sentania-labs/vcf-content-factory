# Publish via Pull Request — v4

**Status:** queued 2026-04-27 (after v3 Phase 1 lands)
**Owner:** orchestrator (planning) + tooling agent (implementation)
**Builds on:** `designs/release-lifecycle-v1.md` (publish pipeline) and `designs/content-structure-v3.md` (Phase 1 layout migration must land first)

## Context

Today `/publish` pushes directly to `main` of the distribution repo
(`sentania-labs/vcf-content-factory-bundles`). That's fast, but assumes:
- The runner has push access to the dist repo.
- No human review is wanted between build and ship.
- Branch protection isn't enforced on the dist repo.

Three problems start to bite as the framework matures:

1. **External contribution path doesn't exist.** A third-party content author
   who wants to update their dashboard (e.g., the IDPS team ships v2)
   can't push directly. There's no clean "fork the factory, run /publish,
   open a PR" flow.

2. **No review checkpoint.** Routine publishes commit straight to public
   `main`. Easy to ship a broken artifact (the post-v3 Phase 1 reorg
   could expose new edge cases). A PR review (even self-review) catches
   issues before they're public.

3. **CI runs after the fact.** When the dist repo eventually grows CI
   (link checking, install-script smoke test in a clean env, README
   render verification), pushing to main means CI runs *after* breakage
   is already public. PR-based runs happen *before* merge — the value
   moment.

## Decision

`/publish` **defaults to PR**. Direct push remains available as an
opt-in override.

```
/publish              ← opens a PR against the dist repo's main branch.
/publish --push       ← direct push to main (legacy/owner-fast-path).
/publish --dry-run    ← unchanged: build into temp dir, no commit/push/PR.
```

Per-invocation flag, no config file. Add a tunable only when a second
consumer with a different policy appears.

### Why default PR vs default push

- **Safe by default.** PR works for everyone (push access not required).
  Owner who forgets `--push` gets a PR they can immediately merge —
  one extra command, no silent surprise. Owner who never adds `--push`
  effectively trades 1 extra step for review/CI/audit benefits.
- **External contributors get a clean path.** Fork factory repo, run
  `/publish` against own fork as `--dist-repo`, and the same code path
  produces a PR-shaped contribution. No "external mode" branch in the
  codebase.
- **Branch protection compatible.** When/if dist repo gets branch
  protection requiring PRs, the default already complies. `--push`
  fails loudly in that case, which is correct.

## Implementation sketch

`vcfops_packaging/publish.py`:

1. **PR mode (default)** — instead of pushing to main:
   - Create a release branch on the dist repo:
     `release/<release-name>-<version>` (or `release/<date>-<n>` for
     multi-release publishes).
   - Push the branch.
   - Open a PR via `gh pr create`:
     - Title: `release: <release-names> (<N> built, <M> retired)`
     - Body: auto-generated from each release manifest's
       `release_notes:` field. README diff included as a section.
     - Base: `main`. Head: the release branch.
   - Print the PR URL.

2. **Push mode (`--push`)** — current behavior unchanged.

3. **Dry-run** — unchanged.

4. **Lockfile semantics adjust.** Currently the lockfile signals "publish
   in flight." With PR mode, the open PR itself is the in-flight signal
   (anyone can see it on GitHub). Lockfile still acquired during the
   build/branch-push phase to prevent two concurrent local runs, but
   released on PR open (not on PR merge) — the local runner has
   finished its work.

5. **Auto-merge optional.** If the owner has branch-protection auto-merge
   configured and wants the routine "PR + auto-merge = effectively
   push" flow, they can enable it via:
   ```
   /publish --auto-merge
   ```
   Translates to `gh pr merge --auto --merge` after PR creation.
   No-op if branch protection blocks auto-merge.

6. **CLI changes:** `--pr` and `--push` are mutually exclusive. `--push`
   defaults to false; `--pr` is implicit unless `--push`. Adding `--pr`
   as a no-op flag for explicitness is fine.

## Constraints

- Requires `gh` CLI installed and authenticated. If absent, fall back
  to detailed instructions ("push the branch manually, then open a PR
  with this body...") rather than failing silently.
- The dist repo's `main` branch protection (if any) needs to permit
  the runner identity to push to feature branches. Branch protection
  on `main` is what we want; on `release/*` branches, no.
- Idempotence: if a release branch with the expected name already
  exists, the publish should fail with a clear message ("PR for this
  release version already open at <URL>" or "delete the branch and
  retry"). Don't silently overwrite.

## Out of scope

- Multi-tenant config (per-dist-repo defaults). Defer until a second
  consumer needs a different policy.
- Per-release publish-mode declarations in release manifests. Same
  reason.
- Required-reviewers automation. The dist repo can configure that
  via branch protection independently.

## Sequencing

After v3 Phase 1 lands and is stable. Mid-v3 work would conflict with
publish.py touch points; defer until layout migration is committed and
the next set of v3 phases (validator, walker, /bundle CLI) is at
least planned.

## Open questions (resolve before implementation)

1. **Release-branch naming convention.** `release/<slug>-<version>` is
   readable but assumes one release per branch. If multiple releases
   ship in one publish, do we batch them into one branch (`release/<date>-<n>`)
   or one branch per release? Lean batched — multiple PRs per publish
   adds review burden.

2. **PR body length and shape.** Just release notes? Plus README diff?
   Plus list of files added/removed? Keep tight; consumers can click
   through to the diff.

3. **Auto-merge default.** For owners running locally, should
   `--auto-merge` be implicit alongside `--push`, or always opt-in?
   Lean opt-in — keep `--push` as the legacy/fast direct-push, and
   `--auto-merge` as the explicit "PR + immediate merge" alternative.

4. **`--no-push` legacy flag.** Today `--no-push` means "commit but
   don't push to remote." In PR mode this becomes "build but don't
   open a PR" — same semantic, different action. Probably keep the
   flag with its updated meaning.
