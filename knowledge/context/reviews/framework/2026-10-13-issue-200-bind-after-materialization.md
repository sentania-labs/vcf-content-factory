# Framework review: issue #200, bind-summary after materialization (2026-10-13)

**Verdict: CHANGES REQUESTED.** 1 BLOCKING / 7 WARNING / 6 NIT.

The opt-in `install --rebind-summary` waits on the right dashboard (by the
pak's JSON id) and then binds whichever dashboard first matches the leaf
**name**. With a same-named dashboard in another folder, it clones the wrong
dashboard into the Summary template, exits 0, and reports that the blank
clone was replaced. Reproduced with a fake client (below).

- Branch: `fix/200-bind-summary-after-materialization` (worktree
  `/home/scott/claude/vcf-content-factory-wt200`), commits `be4fbe5`,
  `f22c4d0`, `4a37de5` on `origin/main` `802a517`.
- Area: `src/vcfcf_dashboards/{materialization,summary_bind,cli}.py`,
  `src/vcfcf_managementpacks/{summary_rebind,cli}.py`, two new test files,
  `knowledge/context/api-surface/summary_dashboard_pak_binding.md`.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (worktree) | pass, all seven rc 0 |
| Full suite (worktree) | 2080 passed, 6 failed, 15 skipped |
| Same 6 tests on a `git archive origin/main` export | the same 6 fail. Cause: `content/sdk-adapters/` is absent (`artifact source not found: content/sdk-adapters/synology/adapter.yaml`). Not counted. The brief expected one failure (`test_real_repo_vks_bundle_pairing_clean`). There are six, all from the same cause: five in `test_release_naming_phase_v2_item1.py`, one in `test_validator_phase2.py`. |
| Render regression | n/a. No renderer, builder, template or assembly file was touched. |
| pak-compare | n/a |
| Stale-zip / `CURRENT_TEMPLATE_VERSION` | n/a for the same reason. No rebuild or bump is owed. |
| Offline read of a real pak (`dist/vcfcf_sdk_compliance.0.0.0.90.pak`) | one binding parsed: `VCF_Content_Factory_Compliance_World_Summary`, id `4e2c777e-...`, kind `vcfcf_compliance:ComplianceWorld`. The id matches the installed source tab id in the 2026-10-13 investigation, which confirms the importer keeps the JSON id. |
| Em-dashes in added lines | 0 |

## Verified safe

- **`--no-wait` refusal happens before any install side effect.** `cmd_install` returns 2 before it calls `install_pak`, and `test_install_rebind_rejects_no_wait` asserts that install is never called. The offline pak read also runs before install.
- **Opt-in default.** Without the flag, `run_install_rebind` is never reached (`test_install_rebind_is_opt_in`).
- **Credentials stay out of output.** `run_install_rebind` never prints user or password, the test asserts the password is absent, and `UIClientError` messages carry server text only. An escaping `requests.HTTPError` (W2) carries the URL but no secret. Auth source `localItem` matches the installer's own session (`installer.py:334`).
- **Unbind and dry-run unchanged.** The deferred guard sits inside `if not unbind`, and dry-run returns before `bind_plans`. The existing `test_dashboard_summary_for.py` bind and unbind tests pass. Their fakes carry no `isLoading`, so they take the NOTE path, which proves no regression for builds without the key.
- **The "not listed yet" loop is bounded.** It ends at the timeout and returns `NOT_FOUND` (2). It cannot spin forever on a dashboard that never appears (see N3 for the cost).
- **Global / standalone content-import path.** `bind-summary` after a content-zip `sync` now refuses while the source is deferred. That is a loud, documented change in the safe direction: the prior behavior produced the same permanently blank clone. Its effect on the agent prompt is W5.
- **Missing `isLoading` in `bind-summary`.** NOTE-and-proceed equals the pre-change behavior (no guard at all), so it is not a regression there. In the rebind it is unsafe (W1).

## BLOCKING

**B1. The rebind waits by id and binds by name; a same-named dashboard elsewhere gets bound.**
`summary_rebind.py:211-229` waits on `b.dashboard_id`, then calls
`bind_plans`. `bind_plans` (`summary_bind.py:247`) resolves the source with
`_installed_entry(ui, name)`, which returns the first `getDashboardList`
entry whose name equals the leaf or ends with `/<leaf>`. `p.dashboard.id` is
never read there, despite the docstring at `summary_bind.py:195-197`.
Reproduced: list = [`My Dashboards/<name>` id `other-uuid`, `VCF Content
Factory/<name>` id `4e2c777e`]. The wait reports `4e2c777e` materialized,
then the association written is `<name>_::_other-uuid`. Exit 0, plus the
line "the installer's blank clone ... is no longer the Summary tab". With
the other entry deferred instead, the bind is refused and exits 2, judged
on the wrong dashboard's state.

- Authority: review dimension 2 (key derivation without context awareness, anchor `6c59f6b`); RULE-007 (UUID stability: the pak id is the stable identity on this path, and the importer keeps it, as verified above).
- Effect: the Summary tab shows a different dashboard than the pak bound, and the run reports success.
- Fix: when the plan carries an id (pak path), resolve the installed entry by id and fail if that id is not listed. Optionally cross-check the name. Add tests for both collision orders. The `bind-summary` YAML path can keep name identity, but see W6. Correct the `bind_plans` docstring and the doc's rebind bullet so they say how the source is resolved.

## WARNING

**W1. With no `isLoading` key, the rebind binds immediately and exits 0.**
`materialization.py:121-125` returns `MATERIALIZED` when the key is absent.
On the rebind path that runs seconds after the install, when the source is
almost certainly still deferred. The result is a second blank clone, a
possible orphan of the first, and exit 0. Reproduced (`NoFlag` probe: rc 0,
association written).

- Authority: shared reviewer doctrine (reports-green-while-broken); `dashboard-import-deferred-materialization.md` rule 1 (do not proceed until materialization is confirmed).
- Fix: fail closed in the rebind only. Do not rebind, return non-zero, and print the manual `bind-summary` re-run. Keep NOTE-and-proceed for interactive `bind-summary`. Add a test.

**W2. One transient HTTP error during a 15-minute poll aborts with a traceback after a successful install.**
`VCFOpsUIClient.list_dashboards` calls `raise_for_status()` and raises
`requests.HTTPError`. `run_install_rebind` (`summary_rebind.py:296-300`)
and `cmd_bind_summary` (`cli.py:839`) catch only `UIClientError`.
Reproduced: a 503 on the second poll gives an uncaught `HTTPError`. The
install's own poll already retries transient errors (`installer.py`,
`is_pak_installing` loop, "Status poll failed (will retry)"). The new loop
widens one call into about 30.

- Fix: in `wait_for_materialization`, catch `requests.RequestException`, print a progress line, and keep polling until the deadline. Catch it in `run_install_rebind` as well. Add a test.

**W3. The `dashboards.properties` split does not match the installer's, contrary to the docstring.**
`summary_rebind.py:150-155` uses Python `str.split(":")` plus `strip()`
and requires non-empty tokens. The installer uses Java `String.split`,
which drops trailing empty strings, and does not trim
(`summary_dashboard_pak_binding.md` §File format). Probed:

| Value | Installer | Rebind |
|---|---|---|
| `A:B:` | `[A,B]`, binds A:B | skips, and prints "the installer skips it too" (false) |
| `:B` | `["",B]`, size 2, accepted | skips |
| `A: B` / `A:B ` | token `" B"` / `"B "`, binds a kind that does not exist | strips, then binds A:B (a binding the installer never made) |

Also, the installer never binds a `GenericTemplates*` directory, but the
rebind would wait the full timeout for one. Factory-built paks do not hit
these cases (the loader rejects whitespace, and the builder emits clean
pairs), but the rebind accepts any pak.

- Fix: emulate Java split (drop trailing empty tokens, no trimming, exactly two tokens), skip `GenericTemplates*` keys, correct the WARN wording, and add table-driven tests.

**W4. Exit code 2 means both "nothing happened" and "the install succeeded but the rebind failed".**
argparse usage errors and the `--no-wait` refusal return 2 before any
install. A rebind failure after a successful install also returns 2
(`summary_rebind.py:236-238`). An operator or wrapper that retries on 2
re-installs the pak, and per the doc each forced re-install leaves another
orphan template.

- Fix: give a post-install rebind failure its own code. Document 0 / 1 / 2 / 3 / new in the `install --help` epilog.

**W5. Agent prompt and docs now contradict the tool (orchestrator-owned, same PR).**
`.claude/agents/content-installer.md:133-144` says to run `bind-summary`
right after `sync`. That run is now refused while the dashboard is deferred,
which is the normal state right after a sync. The same passage says "Pak
installs bind at install time ... do not run bind-summary for those", which
the new `--rebind-summary` workaround supersedes. The CLI synopsis in
`knowledge/context/api-surface/summary_dashboard_assignment.md:325` lacks
`--wait` / `--force-deferred`.

- Fix: the orchestrator does the non-`src/` sweep in this PR (CLAUDE.md delegation rule 9). Tell content-installer to bind after its materialization wait, or to pass `--wait`, and describe `--rebind-summary`.

**W6. `bind-summary` picks the first of several same-named dashboards without saying so.**
`_installed_entry` (`summary_bind.py:84-91`, touched by this branch) and
`find_dashboard_entry` (`materialization.py:45-62`) return the first
leaf-name match. The match logic predates this branch, but the function is
modified here, so a follow-up issue does not apply.

- Fix: when more than one entry matches the name, refuse and list the candidates (folder and id). Shares the fix with B1.

**W7. The rebind has not been seen working live, and parts of it are unproven.**
The doc says so honestly. Still unverified: (a) that `getDashboardList`
`isLoading` for a dashboard owned by the installer's admin and shared with
Everyone, as read by a different session user, is the owner's
`importComplete` flag; (b) that 9.0.2's UI bind deletes or orphans the
installer's clone.

- Authority: user rule 7 (done means seen working); RULE-005.
- Fix: no code change. The PR body must not claim #200 fixed. A `qa-tester` / `content-installer` live pass must show the proof named in the doc (a new `getSummaryTabId`, and `getDashboardConfig?isTemplate=true` with `isLoading: false` and `widgetConfig` on every widget) before the workaround is relied on.

## NIT

1. **`summary_rebind.py:172`**: a `dashboard.json` that is valid JSON but not an object (for example a list) raises `AttributeError`. `cmd_install` catches only `OSError` and `BadZipFile`, so the user gets a traceback. It happens before install, so there is no side effect. Fix: an `isinstance(doc, dict)` check with WARN and skip.
2. **`summary_rebind.py:176-178`**: several dashboards in one bound `dashboard.json` produce a WARN, and the first one is rebound. The installer's pick is a `HashMap` iteration (nondeterministic), so the rebind can move the Summary tab to a different dashboard than the one the installer bound. Fix: skip that binding with a WARN instead of guessing.
3. **`materialization.py:146-149`, `summary_rebind.py:217-220`**: a bound dashboard that never appears costs the full timeout per dashboard (default 15 minutes, serially). The message then suggests `bind-summary --wait`, which will fail with "not installed". Fix: for NOT_FOUND, say the import likely failed (check the pak's install log, for example an unsupported widget type aborting the import) and drop the re-run hint.
4. **Dangling evidence reference.** The doc and both module docstrings cite `knowledge/context/investigations/2026-10-13-compliance-summary-clone-config-loss.md`. That file exists only in unpushed commit `9b9147a` on the main checkout's `docs/compliance-build-88-designs` branch. It is not on `origin/main` and not on this branch. Land that first, or carry the file.
5. **`summary_bind.py:195-197`**: the docstring claims `bind_plans` reads `plan.dashboard.id`. It does not. Resolved by B1.
6. **Cosmetic.** Rebind output prints the `== <name> -> <kinds>` header twice (once in `rebind_summary_after_install`, once in `bind_plans`).

## If shipped as-is

An operator who opts into `--rebind-summary` and has a same-named
dashboard in another folder gets that dashboard silently cloned onto the
pak's Summary tab, with exit 0. A transient 503 during the wait ends a
successful install with a traceback. A content-installer following its
prompt now hits a refusal after every sync.
