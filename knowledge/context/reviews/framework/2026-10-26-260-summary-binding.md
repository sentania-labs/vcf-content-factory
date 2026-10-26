# Framework review: Summary binding forms, still-building refusal, repair default-on (#260, #256, #200)

- **Date:** 2026-10-26, America/Chicago
- **Branch:** `fix/260-summary-binding`, code commit `2ccbd13` on base `1a758dc` (the branch head `cd7aee9` adds the orchestrator's content-installer prompt edit, reviewed only where it describes the code)
- **Area:** `src/vcfcf_dashboards/{ui_client,summary_bind,cli}.py`, `src/vcfcf_core/dashboards/summary_bind.py`, `src/vcfcf_managementpacks/{cli,installer,post_install}.py`
- **Verdict:** CHANGES REQUESTED, 1 BLOCKING / 4 WARNING / 10 NIT

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (worktree, `PYTHONPATH=src`) | all seven exit 0 |
| Full pytest | 2874 passed, 6 failed, 9 skipped. The 6 are `test_release_naming_phase_v2_item1.py` (5) and `test_validator_phase2.py` (1); each fails on `artifact source not found: content/sdk-adapters/synology/adapter.yaml`. The worktree has no `content/sdk-adapters/` clones. The diff touches no packaging code. I could not re-run them on the base commit (a second worktree was denied), so "they also fail on main" is the tooling claim, consistent with the cause I saw. |
| Touched suites (`test_summary_bind_forms_and_readiness`, `test_pak_summary_rebind`, `test_dashboard_summary_for`, `test_install_materialization`) | 188 passed |
| New tests | 26 collected in the new file (matches the claim), plus the edited cases in the two existing files |
| Render regression / pak-compare | n/a: no renderer, builder or pak-structure code in the diff |
| Stale zips (dimension 9) | n/a: no `templates/`, `builder.py`, `assembly.py` or `render.py` change. The bundle `install.py` has no Summary binding (grep), so no rebuild and no `CURRENT_TEMPLATE_VERSION` bump is due. |

Bytecode and SPA: the class files and JS the investigation read were not retained ("Copies ... stay in the session scratchpad only"), and none are on disk. So I checked the claims against the documented evidence (investigation part 1, the two api-surface docs, the build-98 record, issue #260), not against the bytecode itself. See W4.

## Claim-by-claim

| Claim | Verified? | How |
|---|---|---|
| Two-map first, then single-map once on non-`ok`, form remembered | Yes, as coded (`ui_client.py:382-406`) | Code read; tests `test_two_map_build_takes_one_call`, `..._falls_back_and_remembers`, `..._stops_working_still_falls_back`. |
| Retry is safe: each build NPEs before writing | Holds for the four builds read, on the HTTP 200 error-panel answer | Investigation part 1: `getParameter` then `new JSONObject(null)` at 2607 (9.0.2) and 2578 (8.18.6); the 2026-08-25 note gives the same for 9.0.0-pre and 9.2; 9.1.1 reads the two maps (bytecode table). On those builds a single-map call to a two-map build, or the reverse, NPEs before any lookup. The trigger is broader than that evidence (W2). |
| Single-map keeps resets | Yes | `association_params` merges `reset` as `<name>_::_null`. The overlap guard refuses a kind that is both bound and reset before any POST. Tested. Matches the SPA's `templateName + "_::_" + tabId`. |
| Remembered form cannot leak across profiles or clients | Yes | `association_form` is an instance attribute set in `__init__`. There is no class or module state. `from_env` and the pak `ui_factory` build a fresh client per profile and per install. |
| 9.0.2 readback without `isDashboard` | Yes | `summary_dashboard_tab`: an explicit `isDashboard` decides, otherwise a UUID `tabId` counts. That mirrors the server's own `isDashboard = UUID.fromString(tabId) parses` (assignment doc, `getSummaryTabId` section). The 9.0.2 shape is documented live (`{"tabId": "1680c6bc-..."}`, 2026-10-24). The pak repair path rejects only an explicit `isDashboard: false`, so it already copes. |
| Silent skip is an ERROR | Yes | `before` is read per kind before the write. An unchanged tab is an ERROR, exit 2. A tab that was unbound and stays unbound is the existing "did not return a dashboard tab" ERROR. The pak path has the matching `new == old` check, exit 3. |
| Still-building refusal, `--wait` 30 s / 660 s, duplicates refused | Yes | Code read; tests. The loop terminates: `step = min(poll_s, wait_s - elapsed)` is > 0 while `elapsed < wait_s` for the CLI's fixed `poll_s = 30` (N4 covers an API caller passing 0). A missing `isLoading` is refused with or without `--wait`, which is loud. The list carries the flag on 9.0.2 and 8.18.7 (build-98 record: source `isLoading false`). |
| Pak repair on by default; `--skip-summary-rebind` and `VCFCF_SUMMARY_REBIND=0` turn it off | Yes | `cli.py:597-608`, `install_pak(summary_rebind=True)`, `report_pak_dashboards(summary_rebind=True)`; the tests run the parameter matrix. |
| 9.1.1 installs that were `SUMMARY OK` are unchanged | Writes: yes. Timing and wording: no | Build-98 ran with the repair on, and 9.1.1 printed `SUMMARY OK: ... shows a finished copy` with no association call (`compliance-build-98.md` line 45; investigation Q5). So the default-on path writes nothing on a finished 9.1.1 copy. What does change: (a) for a pak with bindings, the materialization wait goes from one 180 s re-check to 30 s polls for up to 660 s; (b) the line becomes `SUMMARY OK: <kind> shows a finished copy ...` instead of `SUMMARY OK <kind> <copy> (0 of m widgets loading)`; (c) a 9.1.1 copy left unfinished (seen on prod 2026-10-13, approvals record) is now rebound in the two-map form, or reported as exit 3 where it used to exit 0. |
| Exit codes | Yes, with one gap | bind-summary: 0 / 1 (nothing to do, YAML load) / 2 (every ERROR, refused or not-taken association, UI login). A transport error at `login()` still escapes (N9). Pak install: 3 now possible by default (NOT REBOUND), documented in the epilog. |

## BLOCKING

**B1. The repair is on by default, but the write it now makes on 9.0.2 and 8.18 has never been sent live.** Locations: `src/vcfcf_managementpacks/cli.py:608`, `installer.py:1040`, `post_install.py:620`.

Authority: issue #260's own fix text ("Prove with one bind-summary on devel (writes a binding and a template, needs a go)"), which the PR claims to close. Also the investigation's follow-up "Exercise the pre-9.1 shape once on devel", the branch's own docs ("**The single-map call has not been sent live**", "Not yet seen working"), and RULE-019's "a line that could not be exercised is named as not exercised, never implied".

Four facts for that path are still unread:
- the body of the success answer (`ok` is assumed; see W1);
- the readback after a single-map bind;
- whether the 4-argument `saveDashboardAsTemplate` copy of a finished source comes out finished;
- whether the previous template is really deleted.

With the default on, the first single-map write anywhere happens on whatever 9.0.2 or 8.18 instance next installs a pak with `dashboards.properties`. That could be a user's cloned framework against their production, not the lab. If any of the four facts is wrong, every such install on two of the three supported lines changes from exit 0 to exit 3, and the operator reads a false "refused" (W1) or orphaned templates pile up.

**Smallest correct fix:** before the PR opens, run the proof the issue names: with Scott's go, one `bind-summary --wait` on devel (9.0.2) and one on devel_8_18. Record the answer body, the `getSummaryTabId` readback, the new copy's `isLoading` state, and whether the old template is gone, in the investigation. Then keep the default on. If the proof cannot happen before the PR, ship the form fallback with the repair still opt-in and flip the default in a follow-up. Either way #260 closes only on the proof.

**My judgment on default-on, as asked.** Default-on is the right end state. The broken Summary tab on 9.0.2 and 8.18 is a real, visible defect (#260 visual pass), and the repair has two guards: it writes only to a copy whose name reads as the pak's and that is known unfinished, and it reads back. But default-on is not right before the proof. The proof is minutes on lab instances, and the cost of skipping it lands on people who cannot see this repo.

## WARNING

**W1. A successful single-map write with any body other than `ok` is reported as "refused, nothing changed".** Locations: `ui_client.py:394`, `post_install.py:578-583`, `summary_bind.py` (the associate call).

Authority: `summary_dashboard_assignment.md`, "Two request forms": "What the success answer's body is ... has not been read for this form".

On 9.0.2, the two-map call NPEs and the single-map call writes. If that write answers with another body, the client raises. bind-summary then exits 2. The pak path prints `SUMMARY NOT REBOUND ... was refused, so the Summary tab still shows the unfinished copy <old>`, which would be false, and exits 3. That invites a manual repeat, which writes again.

Fix: when the associate call raises, read `getSummaryTabId` back before reporting a refusal, in both callers. A changed tab means the bind was written and the reply was unexpected, and the message should say exactly that. Or resolve this by recording the real body in B1's proof.

**W2. The fallback fires on "anything other than `ok`", but retry safety is proven only for the HTTP 200 generic error panel.** Locations: `ui_client.py:394-400`; the test `tests/test_summary_bind_forms_and_readiness.py:84` makes a 500 trigger the fallback.

Authority: investigation part 1 and the build-98 record. Both refusals were HTTP 200 with the Ext "Internal Server Error" panel, from the NPE on the first line.

A 401 or 403, a login-page redirect, a 502 or 504 from a proxy, or an expired CSRF token now trigger a write in the other form. That retry is still safe on the four builds read only because the other form NPEs there too. On a build nobody has read (another 9.0.x or 8.18.x patch, 9.1.0, 9.2 GA), the second write rests on inference. A gateway timeout that the server completed is exactly the case where a second form must not go out.

Fix: fall back only when the answer is HTTP 200 and its body carries the error-panel marker. Raise on anything else without sending the other form. Change the 500 parametrization to assert there is no fallback.

**W3. `--wait` can finish with the wrong diagnosis.** Location: `summary_bind.py:154-168` and `:304-314`.

If every list read fails for the whole budget (an expired session answers with a login page, so `.json()` raises; or the server is unreachable), or the dashboard drops out of the list, the loop keeps the first state, "building". The final line then reads `ERROR: ... is still building after 660 s (isLoading: true ...). Opening the dashboard once in the UI usually finishes it`. The exit code (2) is right. The cause and the advice are wrong, and the real error appears only in the per-poll lines.

Fix: track the last read failure, or "not in list", and when the final state was never re-read, name that cause in the final ERROR instead of `isLoading: true`.

**W4. The evidence the retry-safety argument rests on is not in the repo.** Location: `knowledge/context/investigations/2026-10-24-devel-summary-rebind-500-and-alertlist-gap.md`, "Clean-up".

Authority: the reviewer doctrine (independent verification), RULE-016 (vendor artifacts may be added under `reference/docs/`).

The class files, the javap output and the SPA excerpts stayed in a session scratchpad, and the hashes in the doc are truncated. Nobody can re-check three claims the code depends on:
- the NPE-before-write ordering;
- that a single-map entry merges into the association map rather than replacing it (otherwise a one-kind bind would wipe every other kind's Summary binding);
- that a reset leaves the template in place.

Fix: add the `javap -c -p -l` text of `associateResourceKindDashboards` for 9.0.2, 8.18.6 and 9.1.1, with the full sha256 values and the SPA `save()` lines, under `reference/docs/`, or inline in the investigation.

## NIT

- **N1. The form order deviates from #260's spec.** `ui_client.py:382`. The issue says to send the single-map form first; the branch sends two-map first. Two-map first is defensible: it is the live-proven form and the newer lines read it. But the deviation should be stated in the PR or the issue. Its cost is one NPE stack trace in `web.log` per new client on 9.0.2 and 8.18, which means every pak install with bindings and every bind-summary run.
- **N2. The exception keeps only the last form's status and body.** `ui_client.py:406`. `server_answer()` in the NOT REBOUND line uses `status`/`body`, so the "tried" list is lost. On 9.1.1, a real two-map refusal would be quoted as the single-map NPE panel. Keep the first (or remembered) form's answer as the body, or put both into the message `server_answer` prints.
- **N3. `source_loading` reads `"isLoading": null` as built.** `vcfcf_core/dashboards/summary_bind.py:152` (`bool(None)`). That contradicts its docstring ("never read as built") and fails open. Treat `None` as unknown. `loading_widgets` also accepts only `is True`, while `source_loading` accepts the string "true"; make them consistent.
- **N4. `_wait_until_built` never ends when `poll_s <= 0` and `wait_s > 0`.** API callers only; the CLI fixes 30. Guard `poll_s > 0`.
- **N5. Any unrecognised `VCFCF_SUMMARY_REBIND` value turns the repair on silently.** `cli.py:608`. A typo such as `fasle` counts as on. Warn on an unrecognised value.
- **N6. The pak repair lines do not name the request form.** `post_install.py:599`, and the NOT REBOUND lines. The content-installer prompt (cd7aee9) says the client "says so". Append `ui.association_form` to REBOUND and NOT REBOUND. That is also the evidence B1's proof wants.
- **N7. `.claude/agents/content-installer.md:105-108` (cd7aee9, orchestrator scope) still describes the old default.** It says the check runs "up to 180 s" and that SUMMARY OK / INCOMPLETE are printed "as information". With the repair on by default and a pak that binds, it is 30 s polls up to 660 s, and the lines are `SUMMARY OK:` / `REBOUND` / `NOT REBOUND`.
- **N8. The `tier2_architecture.md` changelog row for 2026-10-24 still says the repair is opt-in, and no row records the flip.** Add a dated row.
- **N9. A transport error at login still escapes bind-summary.** `cli.py:1047`: a `requests.ConnectionError` from `ui.login()` gives a traceback and exit 1, against the new epilog ("2 ... a UI login failure"). Catch `requests.RequestException` there too.
- **N10. Long waits, unequal limits, and aborts.** `--wait-timeout` has no upper bound, while the pak path caps at 900 s, and it is ignored silently without `--wait`. With several dashboards the waits run in sequence (worst case N x 660 s). A refused association raises out of the loop and skips the remaining dashboards. Add a cap, a warning when `--wait-timeout` comes without `--wait`, and a per-dashboard `continue` on a refusal.

## If shipped as-is

On 9.1.1 and 9.2, nothing visible changes except a longer wait budget and new SUMMARY line wording. On 9.0.2 and 8.18, every pak install with a Summary binding makes a first-ever, unproven single-map write on the operator's instance. If its answer body or its copy is not what the bytecode reading predicts, the install exits 3 with a possibly false "refused" line.
