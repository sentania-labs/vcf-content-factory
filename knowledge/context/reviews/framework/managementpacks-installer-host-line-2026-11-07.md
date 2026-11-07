# Framework review: managementpacks installer, `[2/6]` host line + profile-watch tests (#315, #311)

- **Date:** 2026-11-07
- **Branch:** `worktree-agent-a88609726483c8188` (diff vs `main` at `ce34da8`)
- **Reviewer:** framework-reviewer (RULE-013)
- **Verdict:** APPROVE (0 BLOCKING / 1 WARNING / 2 NIT)

## Change under review

| File | Change |
|---|---|
| `src/vcfcf_managementpacks/installer.py:1183` | `[2/6] Authenticating to /ui/ as {user!r}` becomes `[2/6] Authenticating to /ui/ on {host} as {user!r}` |
| `tests/test_install_account_restart.py` | `_two_profiles` harness (real `_resolve_credentials`, `_env._LOADED=True`, all `VCFOPS_*` cleared, two fake profiles) and 5 test cases: watch uses `--profile` (x2 parametrized), `--profile` beats `VCFOPS_PROFILE`, CLI `--profile` reaches the watch, output names the host |
| `knowledge/context/tier2_architecture.md` | one changelog row |

Root cause claim (process error: parallel installs on different profiles writing one shared log) is consistent with the code: both `suite_factory(...)` call sites (`installer.py:1205`, `:1369`) take `host, user, password` from the single `_resolve_credentials(..., profile=profile)` at `:1160`. No path in `install_pak` re-resolves credentials.

## Checks re-run

- Validate chain (7 packages) in the worktree: all rc=0.
- `pytest -q tests/test_install*.py`: 275 passed.
- Full suite: 15 failed / 3244 passed / 13 skipped. All 15 are environmental and unrelated: jmespath not installed (`test_gap_b_f_d` x2, `test_common_doctor` x5), no `content/sdk-adapters/` clones (`test_release_naming_phase_v2_item1` x5, `test_validator_phase2` x1), git-ancestry probe (`test_common_setup` x1), and deep-nesting recursion in the untouched packaged template `src/vcfcf_packaging/templates/install.py` (`test_dashboard_import_all_skipped` x1). None imports `vcfcf_managementpacks.installer` or `account_restart`.
- Render regression / pak-compare: n/a (no renderer, builder, or template touched).

### Mutation tests (scratch copy of `src/` + `tests/`, worktree untouched)

| Mutation | Result |
|---|---|
| M1: installer watch re-resolves with `profile=None` (default profile) | 3 new tests fail (caught) |
| M2: `default_suite_factory` ignores its args, builds `VCFOpsClient.from_env(profile=None, default_profile="devel")` | 1 failure, only because no `VCFOPS_DEVEL_*` exists in the test env |
| M2b: M2 with `VCFOPS_DEVEL_HOST/USER/PASSWORD` set (an operator machine) | **72/72 pass (not caught)** |
| M3: CLI passes `profile=None` to `install_pak` | 1 fails (caught) |
| M4: host dropped from `[2/6]` line | 1 fails (caught) |

## Dimension walk

1. Global/pak-specific leak: n/a; stdout text only.
2. Key/label collisions: n/a.
3. Wire-format conformance: no wire output changed.
4. Loader/validator: untouched; validate chain green.
5. Render regression: n/a.
6. Builder/pak structure: n/a.
7. Corpus regression: none (above).
8. Silent capability change: none.
9. Stale-zip discipline: `installer.py` is not on the CLAUDE.md stale list and no template changed, so no rebuild and no `CURRENT_TEMPLATE_VERSION` bump is due. The packaged templates already name the host (`templates/install.py:2938`, `install.ps1:3906`).
10. Test coverage: present, with the gap in W1.

**Output consumers.** I grepped the repo, `src/vcfcf_packaging/templates/`, the `.github/` workflows, and the main checkout's `content/sdk-adapters/*` clones for `Authenticating to /ui/` and `[2/6]`. The only hits are the changed line itself, the `uninstall_pak` sibling at `:1439`, an unrelated `[2/6]` in an investigation doc, and the templates' own independent wording. Nothing parses the line, so the change cannot break a consumer.

**Secrets.** `_info` prints to stdout. The new line interpolates only `host` (a hostname, already printed by connection errors such as `installer.py:429`) and `user`. `password` is not referenced. No secret reaches the line.

## Findings

### WARNING

- **W1 [`tests/test_install_account_restart.py:665`; `src/vcfcf_managementpacks/account_restart.py:541`]**
  - **Authority:** framework-reviewer dimension 10. The change's own stated purpose is "pinning the watch to the install's resolved `--profile`."
  - **Problem:** All five new tests inject `suite_factory`, so they bypass `default_suite_factory`, which is the production factory. The factory-to-client handoff is pinned only by the existing timeout test, and that test never checks host or user. Mutation M2b shows the gap: a factory that ignores its arguments and opens the default profile passes all 72 tests on any machine where `VCFOPS_DEVEL_*` is set. That is exactly the #315/#311 symptom, falling back to the default profile, reintroduced one layer down where nothing watches.
  - **Fix:** add a test that calls `ar.default_suite_factory("devel-91.example", "u-91", "p", True)` with a different `VCFOPS_DEVEL_*` profile present in the environment. Using the existing fake session, assert that the token POST URL host is `devel-91.example` and that `json["username"] == "u-91"`.

### NIT

- **N1 [`src/vcfcf_managementpacks/installer.py:1439`]**
  - **Problem:** `uninstall_pak` still prints `[1/5] Authenticating to /ui/ as {user!r}` without the host. Parallel uninstalls into a shared log have the same misattribution problem, and uninstall is the destructive operation.
  - **Fix:** use the same `on {host}` wording there.
- **N2 [`tests/test_install_account_restart.py`, `test_install_output_names_the_target_host`]**
  - **Problem:** the test pins that the host is printed but not that the password is absent. `"pw"` is too short to assert against.
  - **Fix:** give `_two_profiles` a distinctive password sentinel, then assert it appears in neither `out` nor `err`.

## Author's aside: `default_suite_factory` hard-codes `auth_source="Local"`

The narrow framing is not a defect. `_UISession.login` also hard-codes `authSourceId: "localItem"` (`installer.py:440`), and `_resolve_credentials` discards `creds.auth_source` entirely. A profile with a non-Local `AUTH_SOURCE` therefore fails at `[2/6]` ("UI login failed for user ..."), before the watch ever runs. The watch's `Local` is consistent with the only auth path the installer supports, and fixing the factory alone would change nothing.

The real gap is installer-wide: `VCFOPS_<P>_AUTH_SOURCE` is silently ignored by `install` and `uninstall`, while `VCFOpsClient.from_env` honours it. It is worth one low-priority follow-up issue. It touches code this branch does not change, so it should not block this branch. The issue should take one of two approaches:

- Have `_resolve_credentials` warn loudly when the profile's `AUTH_SOURCE` is not `Local` ("pak install uses a local account").
- Or, after `api-explorer` confirms the `/ui/login.action` `authSourceId` values for vIDM/LDAP sources, honour it in both `_UISession` and `default_suite_factory`.

## If shipped as-is

Operators see the target host on every install's `[2/6]` line, so shared logs become attributable. A future regression inside `default_suite_factory` that falls back to the default profile would still pass CI.
