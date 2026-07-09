# Framework Review — guard hooks become enforcing CI gates

- **area:** `scripts/immutability_guard.sh` (rename-policy rework), `.github/workflows/ci.yml` (two new enforcing steps), `STRUCTURE.md` (prose)
- **change:** wire `path_reference_audit.sh` (always, exit-2 fails build) and `immutability_guard.sh` (on `pull_request`, `--range origin/<base>...HEAD`) into CI as enforcing gates; generalize the guard's rename handling (R100 into/within `reference/` allowed; R100 out refused; R<100 either side refused).
- **verdict:** APPROVE
- **findings:** 0 BLOCKING / 1 WARNING / 2 NIT
- **checks re-run:** guard scenario matrix 7/7 as specced; three-dot range accepted + semantically correct; no-op range clean; R0xx parse correct; tooling's `c0a38ac..46b1461` → 0 reproduced; path audit exit 0 on branch **and** in a stripped CI-like clone (reference/ + sdk-adapters absent); ci.yml YAML parses; referenced scripts present. render-regression n/a; pak-compare n/a.

## What I verified independently (re-run, not taken on faith)

Guard scenario matrix in a scratch repo (default git, `diff.renames` unset → built-in true):

| scenario | expected | observed |
|---|---|---|
| modify vendor file under `reference/` | refuse (2) | 2 (`M`) |
| delete vendor file | refuse (2) | 2 (`D`) |
| add new vendor file | allow (0) | 0 |
| R100 rename **within** `reference/` | allow (0) | 0 |
| R100 move **into** `reference/` from outside | allow (0) | 0 |
| R100 move **out of** `reference/` | refuse (2) | 2 ("deletion in disguise") |
| R<100 rename+edit touching `reference/` | refuse (2) | 2 |

- **Three-dot integration point (the critical one).** `--range "origin/main...HEAD"` is passed as a single arg to `git diff --name-status "${RANGE}"`, so three-dot works. It is also semantically *required*: I forked a branch, then advanced the base with an unrelated `reference/` edit. `mainline...feat` (three-dot) reported only the feat-side change; `mainline..feat` (two-dot) additionally reported the base-side edit as a false offender. **CI correctly uses three-dot** — two-dot would have manufactured spurious refusals from base-side history.
- **Similarity parsing.** `git diff --name-status` emits `R100\told\tnew` / `R084\t…`. `code=${status:0:1}`, `similarity=${status:1}` parse `R100`, `R084`, `R099` correctly (verified a genuine ~85%-similar rename → `R084` → else-branch → refuse). Only exact `100` takes the allow path.
- **No-op range** (`HEAD...HEAD`, base == HEAD): empty diff → "no changes to check" → exit 0.
- **Tooling's claim** `--range c0a38ac..46b1461 → 0` reproduced (both two- and three-dot).
- **path_reference_audit in a CI-shaped checkout.** Cloned the repo into scratch with the branch's modified files copied in and **no** `reference/references/` and **no** `content/sdk-adapters/` on disk (matches CI: `bootstrap_managed_paks.sh` runs, `bootstrap_references.sh` does not). Result: exit 0, only the two `reference/references/tvs` standing-exception WARNINGs — **absent registry-managed roots do not flip warnings into failures.** Validity is decided by `git ls-files` + registry parses, never bare filesystem existence; `looks_like_prose_list`'s only `-d` test gets *more* lenient when a dir is absent. Proven safe on the global/CI path, not just locally.
- **ci.yml.** Parses as YAML. Fork-gate is job-level (`head.repo.owner.login == 'sentania-labs'`). Immutability step is correctly gated `if: github.event_name == 'pull_request'` (it needs a base ref); path audit runs always (push + PR) as intended. All referenced scripts exist.
- **STRUCTURE.md.** Prose-only; the one path it cites (`scripts/path_reference_audit.sh`) is correct and tracked. No code impact.

## Findings

### WARNING
- **[scripts/immutability_guard.sh:86,88,90]** The guard does not force rename detection; it depends on the ambient `diff.renames` default (`true`). With `diff.renames=false` (a per-repo/global/env override), a **pure rename *within* `reference/`** — an explicitly ALLOWED case per the header spec — is emitted as `D old` + `A new`, and the `D` is refused (exit 2). Verified empirically: `git -c diff.renames=false` → within-reference R100 → REFUSED. GitHub-hosted `ubuntu-latest` runners use the built-in default (true), so the enforcing CI step is correct today, and the *near-term* step-2 use (move-IN: the source `D` is outside `reference/`, allowed) is inert to the setting — hence WARNING, not BLOCKING. But this is (a) documented as a future `pre-commit` hook where developer git configs vary, and (b) an enforcing gate should not hinge on unpinned ambient config. **Fix:** make detection explicit — `git diff --name-status --find-renames "${RANGE}"` (likewise the 2-arg and `--cached` branches), or invoke `git -c diff.renames=true …`. Deterministic, trivial.

### NIT
- **[scripts/immutability_guard.sh:55]** `usage()` prints `sed -n '2,30p'`, but the header now runs past line 30 (the rename-policy block added lines ~16–29 pushed the "does not yet run automatically" note beyond 30). `--help` truncates mid-note. Bump the upper bound.
- **[.github/workflows/ci.yml:74-75]** `git fetch … || true` swallows a fetch failure; if `origin/<base>` is then unresolvable, `git diff origin/<base>...HEAD` errors and `set -euo pipefail` exits the guard non-zero → step fails **closed** (blocks PR). Safe direction, but the operator sees a cryptic `git diff` error rather than a clear "base ref unavailable" message. Optional: guard the range resolves before diffing.

## If shipped as-is
On GitHub-hosted runners the gates behave exactly as intended: dead-reference PRs and vendor-material edits are refused, additions and pure renames into/within `reference/` pass, and the step-2 grouping merge is clean. The only latent surprise is a future *within-`reference/` restructure* PR (or the pre-commit-hook use) on a checkout with `diff.renames=false`, which would be falsely refused until the one-line `--find-renames` fix lands.
