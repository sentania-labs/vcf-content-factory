# vsanhostmetrics 2.0.0 review, 2026-10-29

- **Fork:** `content/sdk-adapters/vsanhostmetrics/` (sentania-labs/vsanhostmetrics)
- **Branch:** `tuneup/upstream-2026-10`, commit `6897081` on `d3174fc` (v1.5.0-rc.3, reviewed in `vsanhostmetrics-tuneup-2026-10-28.md`)
- **Scope reviewed:** the one commit and how it interacts with the rest of the branch: the `vcenter_user` identifier removed, the username only in `vsan_vc_credential.vcenter_username` (now `required=True`), the fallback and its two log lines removed, new `MIGRATION.md`
- **Checklist:** `knowledge/context/python_integration_sdk.md` section 10
- **Verdict:** BLOCK (1 BLOCKING, 4 WARNING, 3 NIT)

The code change is clean. The username check runs before any network call in
both `test()` and `collect()`. It never reads the password or the certificates,
and it puts no credential in a log. No live reference to `vcenter_user` remains.
`perfsvc.py` and `app/vendor/` are untouched, so certificates, timeouts and
token handling are as they were at `d3174fc`. The block is in the docs. This
commit makes 1.x to 2.0.0 a schema-changing upgrade. `README.md` section 5 and
`QUICKSTART.md` section 1 tell anyone doing a schema-changing upgrade to
uninstall the old pack and delete its adapter instances. `MIGRATION.md` tells
them to install over the top. Following either of the first two loses every
object's history.

## Claims check (what was rerun)

| Claim | Rerun | Result |
|---|---|---|
| Unit tests 46/20/29 pass in Docker | Built the adapter image from `git archive` of `6897081` and of `d3174fc` (`FROM base-adapter:python-1.2.0`). Ran each suite the way CI does: read-only mount copied into the container, `--network none` | Reproduced: 46/46, 20/20, 29/29. `d3174fc` gives 46/46, 20/20, 31/31: 2 tests for the removed behaviour went, 2 were rewritten, 1 was added. One test skips by design (no git in the image) |
| `mp-build` succeeds | SDK 1.3.1 `mp-build --no-ttl` (headless) against a throwaway `registry:2` on `127.0.0.1:5091`, after `docker login --password-stdin` with a dummy secret, run for `6897081`, `d3174fc` and the released 1.4.7 (`c8dbdf5`). Registry, login and image tags removed afterwards | rc 0 for all three |
| describe.xml vs rc.3: kinds 70 to 70, keys 1701 to 1701, 0 removed; identifiers 6 to 5, only `vcenter_user` removed; username now required | My own parser (ElementTree, attribute paths per kind including groups) on the paks I built | Reproduced exactly. The credential field `vcenter_username` changes from `required="false"` to `"true"`; nothing else in the CredentialKind changes |
| (not claimed) describe.xml vs the **released 1.4.7**, which is what users run | Same parser, 1.4.7 pak vs 2.0.0 pak | 70/70 kinds and 1701/1701 attribute paths, 0 removed, 0 added. `vcenter_user` was `required="true" identType="1"` in 1.4.7, so **every** 1.4.7 account has a value in the identifier 2.0.0 drops. The credential gains a required field. 98 `nameKey`s are renumbered: the top three plus the `UnitType` block, which the SDK reorders on every build. The resources file is regenerated with them, so this is harmless |
| mp-test passes with the username, fails "No vCenter username" without | Not rerun live (no lab call needed for the claim). Read the author's `out/v2-mptest/` | `u-connect` passes. `n-connect` and `n-collect` fail with the exact text. The `n-*` adapter logs have no "Operations passed N certificate(s)" line and no login line, so `_accepted_pems` and `perfsvc.connect` were never reached |
| Secret hygiene | Scanned in-process the author's `v2-*` outputs, `build-*` logs, the PR body, the commit patch, my mp-build logs and every `connections.json` under the scratchpad against the 12 password/token/key values in the factory `.env`. Nothing was printed | 0 hits. Every `connections.json` is empty. `/dev/shm` is empty |
| Em-dashes | Grepped the added lines and the commit message for U+2014 | None |

Workflow files are untouched, so actionlint and the Trivy gate do not apply.

## Hunts

1. **Leftover references.** None live. A case-insensitive search of the whole tree for
   `vcenter_user`, `VC_USER_PARAM`, `deprecated`, `ignored` and
   `vCenter username (` finds only these:
   - `MIGRATION.md` and `BACKLOG.md:6,10`, which describe the removal.
   - `test_adapter.py:487`, a leftover identifier the test deliberately supplies to prove it is unread.
   - `test_adapter.py:509`, which asserts the identifier is absent.
   - Vendor XSDs and unrelated prose.
   The committed `resources/resources.properties` carries no field labels. `tools/` and `docs/` do not read the key.
2. **"No vCenter username".** `_connect` (`app/adapter.py:541-549`) evaluates `split_host` (no I/O), then `_username`, which raises. `_password` and `_accepted_pems` are never called and `perfsvc.connect` is never reached. `test()` catches it as `PerfSvcError` (`:640-642`) and logs only the message. `collect()` catches it at `:860-866` (`logger.exception` at `:865`), with a traceback but no locals. Nothing logs the credential object. The new test (`test_adapter.py:481-499`) patches `perfsvc.connect` and asserts that it is not called on either path. Reintroducing the fallback would fail it, because the test supplies a leftover `vcenter_user`.
3. **`required=True` per SDK lib 1.1.0.** `aria/ops/definition/credential_type.py:17-38` only stores the flag and serializes it. The CLI's `describe.py:313-323` writes it as `required="true"`. `mp-test` (`mp_test.py:577, 715`) uses it to decide whether to prompt. At runtime, `AdapterInstance` (`adapter_instance.py:37-46, 131-140`) builds `credentials` from whatever `credential_fields` arrive, and `get_credential_value` returns `None` for a missing key. Nothing on the adapter side enforces `required`. The adapter handles `None` and `""` the same way (`or ""`, then `strip`). **What Operations does with a credential saved before the field existed cannot be determined from SDK code.** It might refuse to load it, force an edit, or pass it through without the field. The factory has no source on it either (`cleanroom-spec/spec/03-credential-model.md` says only "whether the user must fill it"). The live install has to settle it. `MIGRATION.md:70-72` already marks it as owed.
4. **Identity and `_cfg` fallbacks.** Only four identifiers are read: `vcenter_host` (no default, reported if empty), `verify_certs` ("true"), `metric_scope` ("dashboard") and `attach_to_vcenter` ("true") (`app/adapter.py:480, 497, 542, 583, 663, 713`). Each one still exists in the 2.0.0 describe, with the same `identType` and default as 1.4.7. RELEASING.md section 5 is unaffected. No code path reads an identifier that no longer exists, and `constants.py` no longer defines one. The leftover `vcenter_user` an upgraded instance may still deliver is ignored.
5. **MIGRATION.md.** The describe numbers are proven (rerun above), and so are the error text and the no-login behaviour. The in-place upgrade, the credential-required behaviour and the duplicate-account collision are correctly marked as owed (`:44-48`, `:64-76`). Three statements outrun that: W1, W2 and W4. One instruction would lose data if it were followed in combination with the repo's other upgrade docs: B1. Another destroys state with an unstated scope: W3.
6. **Regressions vs `d3174fc`.** None. `git diff d3174fc 6897081` touches no file under `app/` except `adapter.py` (the username and definition hunks only) and `constants.py`. Certificate handling (`perfsvc.connect`, `_accepted_pems`, `get_endpoints`) is unchanged, and so are the timeouts (`perfsvc.py`) and the Suite API token path. Error reporting is unchanged except that one fallback branch, which returned a value, now raises into the existing handlers.

## BLOCKING

1. **Two opposite upgrade procedures for this exact release, and the one most users meet first destroys history.** `README.md:372-377` ("Replacing an existing install? Remove the old pack first ... and delete its adapter instances. A schema change means ...") and `QUICKSTART.md:51-62` with its checker at `:66-89` both apply. The checker compares `(key, identType)` of every `ResourceIdentifier`, and `('vcenter_user','1')` is gone. For 1.4.7 to 2.0.0 it therefore prints `SCHEMA CHANGED -- uninstall first`, and the text then says to uninstall and delete the adapter instances. `MIGRATION.md:58` says to "Install the 2.0.0 pak over the installed one". Uninstalling and deleting the instances loses all object history, which is the outcome `MIGRATION.md` exists to avoid. Factory lesson `pak-uninstall-cascades-credentials.md` adds that a pak uninstall on Ops also deletes credentials. This text is upstream's (Nick Wilson, 2026-09-22/10-01), but this commit is what turns the upgrade into the case it covers, and it edited both files without reconciling them. Fix in this commit:
   - In `README.md` section 5 and `QUICKSTART.md` section 1, add a line before the schema rule saying that 1.x to 2.0.0 follows `MIGRATION.md`, not the uninstall rule, until the live install says otherwise.
   - Have the checker report an identifier-only removal separately ("identifier removed: see MIGRATION.md") instead of the uninstall verdict.
   - Extend the checker to compare `CredentialField` key and `required`. It currently compares only `CredentialKind` keys, so it misses the field that becomes required.
   - If the live install shows that in-place install is refused, change `MIGRATION.md` to the uninstall path with its history loss stated. Do not ship two answers.

## WARNING

1. **History is stated as kept, then stated as unknown.** `MIGRATION.md:7-8` ("so object history carries over") and `:23-25` ("the account, its objects and their history stay as they are") are platform outcomes. `:64-72` correctly says they are "proven only by installing it". The proven part is adapter-side: no keys or kinds are removed, the adapter deletes nothing, and no login is attempted. Fix: reword `:7-8` and `:23-25` to that, and point to the live-install section for the rest.
2. **The comparison base is a version nobody runs.** `MIGRATION.md:8-10` compares against 1.5.0-rc.3, which `BACKLOG.md:10` says is not released. Users upgrade from 1.4.7. The numbers hold against 1.4.7 too (rerun above). But in 1.4.7 the dropped identifier was `required="true"`, so every existing account carries a value in it. That is the case the doc should name. Fix: compare against 1.4.7, and say that the identifier was required there. Also, `:28-30` ("Accounts that were already given the username ... under a 1.5.0 release candidate are not affected") overclaims. Those accounts lose the identifier like every other account. They are only spared the "No vCenter username" failure.
3. **Step 2 deletes accounts and does not say what that deletes.** `MIGRATION.md:57` (and `:46-48`) tells the user to delete duplicate accounts before upgrading. Nothing on the branch or in the factory establishes what deleting one of two adapter instances that collect the same objects does: whether the shared objects, their history, or the credential go with it. Fix: either say what is known and that it is untested, or move the step after the live install has shown what happens to a pair that is left in place (`:48` already admits that is untested). The step should say how to tell a true duplicate (same vCenter, same three settings) from two accounts that only look alike.
4. **Rollback is stated as a procedure, but it is untested twice over.** `MIGRATION.md:78-83` says to install the 1.4.7 pak. It is not established that Ops accepts a pak with a lower version over a higher one. 1.4.7 also re-adds `vcenter_user` as a **required identifying** field, so "enter the username there again" edits account identity on a live account. That outcome was already unknown in the prior review (W4 there). Fix: mark the rollback as owed to the live install alongside `:74-76`, and add a downgrade case to that test.

## NIT

1. `README.md:418` says "Fields, as generated by `get_adapter_definition()` (verified 2026-09-23)" over a table this commit edits. Re-date it, or drop the date.
2. `MIGRATION.md:74-76` ships a `_PLACEHOLDER_`. That is right for a branch, but the `v2.0.0` tag must not be cut until the placeholder is filled. Add it to the release checklist (RELEASING.md section 5 is the natural home: "an identifier removed requires the live-install result in MIGRATION.md").
3. `test_adapter.py:481-499` proves no login is attempted but does not assert that the error text and the logged lines omit the password. A one-line `assert "x" not in tested["errorMessage"] + collected["errorMessage"]` with a distinctive dummy password would lock in hunt 2.

## Checklist (section 10) summary

- **Certificates:** unchanged from `d3174fc` (no diff in `perfsvc.py`, `_accepted_pems`, `get_endpoints`).
- **Credentials:**
  - The username is in the credential, and only there: pass.
  - No identifier holds a credential: pass.
  - No secret in logs or messages: pass.
  - `connections.json`, `logs/` and `build/` are gitignored: pass.
- **Error reporting:**
  - The missing-username path reaches `with_error` in both `test()` and `collect()`: pass.
  - Nothing is swallowed: pass.
- **Timeouts and tokens:** unchanged.
- **Definition and identity:**
  - The identifier removal is called out as an identity change in `BACKLOG.md`, `MIGRATION.md` and the commit message: pass.
  - The repo's own upgrade rule contradicts that callout (B1).
- **Dependencies:** unchanged. lib `~=1.1.0`, `base-adapter:python-1.2.0`, `pyvmomi==8.0.3.0.1`.
- **Packaging:** `mp-build` succeeds. The manifest stays 1.4.7, as upstream RELEASING section 1 requires (the tag sets the version).

## If shipped as-is

- An admin who follows README section 5 or the QUICKSTART checker uninstalls 1.4.7 and deletes the adapter instances.
- That admin loses every vSAN object's history, and per the factory lesson, the credentials too.
- An admin who follows MIGRATION.md installs over the top. What happens then (accepted or refused, objects kept or not) is the open live-install question.
- In both cases, every 1.4.x account stops collecting with "No vCenter username" until its credential is edited. The message is clear, and no login is attempted.
- Rolling back to 1.4.7 is offered as a known procedure when it is not one.
