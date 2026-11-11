# Framework review: tooling/small-fixes-2026-11-11

- Branch: `tooling/small-fixes-2026-11-11`, merge base `33a441c` (origin/main)
- Commits: `0943c53` (currentuser key), `be6946b` (skipped-import wording, template
  version 2026-11-11-1), `abca57e` (XML attribute quote escaping), `c99d1d0` (#318 auth source)
- Reviewer: framework-reviewer, 2026-11-11
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 6 WARNING, 2 NIT)

## Checks re-run

- Validate chain (seven packages) on the branch: all rc=0. Tree clean afterwards.
- Full suite, branch vs merge base (same machine, `PYTHONPATH=src`, no xdist):
  base 14 failed / 3518 passed / 12 skipped; branch 14 failed / 3546 passed / 13 skipped.
  The 14 failure ids are identical (doctor venv x5, release-naming real-repo x5,
  packaging-validate real-repo x1, MPB JMESPath predicates x2,
  `TestExtractDashboardNames::test_deeply_nested_json_does_not_escape_as_recursionerror`).
  One extra skip on the branch was not identified; none of the four new/extended test
  files skip, and the pwsh harness ran (`test_install_ps1_tls_and_advisories.py`: 66 passed).
- Render regression: every view (both plain and with an owning adapter kind, to exercise
  the owning `SubjectType`), every dashboard and the one report under `content/` and
  `third_party/idps-planner/`, rendered on the merge base and on the branch, 82 files:
  **byte-identical**. Not rendered: `content/sdk-adapters/` (gitignored, absent from
  this worktree) and the installer-template render paths (not touched by `abca57e`).
- Reserved files: `sdk_builder.py`, `sdk_project.py`, `buildkit.py`, `managementpacks/cli.py`,
  `adapter_framework/` untouched. `BUILDKIT_VERSION` unchanged.
- pak-compare: n/a (no builder change).

## Fix 4 (`c99d1d0`, #318)

### BLOCKING

**B1. [`src/vcfcf_managementpacks/installer.py:1208-1210`] Honouring the profile source in the
account watch can only make the watch fail; it cannot make it succeed.**
Authority: `knowledge/rules/` doctrine "prove behavior on every output path"; issue #318
reviewer comment (the /ui/ login is local-only and runs first).
The watch runs only after `ui.login()` succeeds, and that login is hard-coded local
(`installer.py:490`, `authSourceId: localItem`). So in every state where the watch is
reachable, `user`/`password` is a proven **local** account. Before: the watch used `Local`
with those credentials and worked. After: it sends `authSource=<profile source>` with
credentials just proven to be local, which fails unless the same name and password also
happen to exist in that directory. Every reachable non-Local case is either unchanged or now
`ACCOUNTS UNCHECKED` with no account restarted. The warning text predicts this failure itself.
Failing scenario: `.env` `VCFOPS_DEVEL_AUTH_SOURCE=corp-ad`, the operator runs
`install --user admin --password ...` because the new warning says the /ui/ login is local.
`_profile_auth_source(None)` still returns `('corp-ad','devel')` (verified), the login as local
`admin` succeeds, and the watch authenticates `admin` against `corp-ad`. That fails, so the
pre-install read is lost and, after the install, a remote-collector account the install left
FAILED is not started. On the merge base the same run watched and restarted correctly.
Fix: build the watch client with the source that actually authenticated the session (Local)
for as long as the /ui/ login is local, and keep the up-front warning. Honour the profile
source in both places together once api-explorer confirms the non-local /ui/ login
payload. This changes the brief's stated requirement; the orchestrator must make that call.

### WARNING

**W1. [`installer.py:1426-1439`, `account_restart.py:464,469`] The "unchecked" outcome a real
auth failure produces does not name the source.**
`VCFOpsClient.__init__` does not authenticate (`vcfcf_common/client.py:65-93`). A bad source
therefore never raises in `suite_factory(...)`; it raises inside `read_accounts` and
`restart_failed_accounts`, whose `ACCOUNTS UNCHECKED` lines at `account_restart.py:464/469`
carry no source. `auth_note` sits only on the construction-failure line (unreachable on auth
failure) and the pre-install read line. `test_non_local_unchecked_lines_name_the_auth_source`
passes only because its `suite_factory` raises at construction, which the real factory never
does. Scenario: profile `corp-ldap`, token acquire 401. The output is `ACCOUNTS UNCHECKED: could
not read the adapter instances ... last: auth failed (401)`, with no source. The `Account watch:` preamble
does name it. Fix: pass the source into `restart_failed_accounts` (or wrap its `err`), and test
it with a factory whose client fails on the first request.

**W2. [`installer.py:280-285`] A Local profile in another case or with whitespace changes the
wire value.** `" LOCAL "` gives `auth_source='LOCAL'`. `_is_local_auth_source` correctly
suppresses the warning, but `default_suite_factory` now sends `authSource: "LOCAL"` where the
merge base always sent `"Local"`. That breaks the "no behavior change for Local" requirement,
and the Suite API's case handling of `authSource` is not documented here. Fix: when
`_is_local_auth_source(...)`, pass the literal `"Local"`.

**W3. [`installer.py:1462-1515`] `uninstall_pak` has the same local-only `/ui/` login and no
warning.** A non-Local profile fails at `[1/5]` with the bare login error that #318 set out to
replace. Fix: call `_warn_ui_login_is_local(..., account_watch=False)` before its login. (Also
note: `post_install.report_pak_dashboards` still hard-codes `Local`/`localItem`, at
`post_install.py:697,703`. Given B1 that is the correct value, but the watch and step 8 now
disagree within one install.)

## Fix 2 (`be6946b`, wording)

No behavior change found. The CLI advice line moved inside the per-type loop (`cli.py:575`),
so it prints once per flagged type. Exit codes, the flagged set, and the advisory-vs-warning
lists are unchanged. The Python and PowerShell tails are character-identical to each other and
to `skipped_import_advice(ct, "re-installing")` (checked programmatically). The template-version
bump follows the established format, and nothing asserts the old value.

### WARNING

**W4. [`src/vcfcf_dashboards/client.py:50-81`, `install.py:1981-1996`, `install.ps1:3171-3183`]
The advice names cause 1 (`force=false`) for imports that never send `force=false`.**
Authority: `knowledge/context/api-surface/content_import_skip_semantics.md` §"The one-line
answer": "A `force=true` import that reports this signature on **views**, or on dashboards
whose owner maps ..., is still **unexplained** and should be treated as a new finding." Every
factory import sends `force=true` (`client.py:370`, `install.py:499`, `install.ps1:1004`). So
the view advice ("The one known cause for views is a create-only import ... if it is stale,
deleting it and re-syncing forces an update") states a cause that cannot apply. For a view
skip it hands the operator the old remedy in place of "unexplained, report it". The dashboard
advice opens with the same cause that cannot apply. Fix: say these imports run with
`force=true`. A dashboard skip is then the owner cause (check `view-bridge.log`) or
unexplained. A view skip is unexplained and should be reported. `install.ps1:1908-1916`
already says this in a comment.

## Fix 1 (`0943c53`, currentuser key)

Verified: the `user` schema in `operations-api-8.18.json`, `operations-api.json` and
`operations-api-9.1.json` names `username` (no `userName`). Mapping is safe on every path. Each
builder writes `owner_user_id` into the marker file (`packager.py:117`), so a source-less owner
maps by path 1 of the owner-mapping note whatever its `userName`. An `admin` session yields
`admin`, as before. Missing key, empty, whitespace-only or non-string values fall back to `admin`.
Reports (`reports/render.py`) and the super-metric zip carry no `usermappings.json`. The installer
templates use the login name. No other reader of the currentuser body uses the wrong key.

### WARNING

**W5. [`src/vcfcf_dashboards/cli.py:524-528`] `python3 -m vcfcf_dashboards sync` still writes
`admin`.** `cmd_sync` calls `build_import_zip(...)` without `owner_username`, so the default
`"admin"` applies. Only the handler paths were fixed, while the note's addendum and
`wire_formats.md` say the name now comes from `current_user_name`. Mapping is harmless (path 1),
but the fix is incomplete on one of the two sync entry points. Fix: pass
`owner_username=current_user_name(user)` there too, and add a test.

## Fix 3 (`abca57e`, escaping)

Render output is byte-identical (above). There is no double escaping: values come from YAML,
are never pre-escaped, and `&quot;` in a value correctly becomes `&amp;quot;`. Ids are
uuid4-validated. `reverse.py` parses with ElementTree, so entities decode. No touched attribute is
one the importer reads raw.

### WARNING

**W6. [`src/vcfcf_core/dashboards/render.py:443`] A missed attribute in the same file:
view-level `transformations` items are interpolated unescaped.**
`f'<Item value="{t}"/>' for t in view.transformations`. The loader (`loader.py:2963-2966`) only
uppercases and does not validate the values. Failing input: a `data_type: trend` view with
`transformations: ['TR"END']` (proved with `dataclasses.replace` on
`content/views/vcf_license_automation_consumption_trend.yaml`) gives
`ET.ParseError: not well-formed (invalid token)`. Fix: the same `escape(t, {chr(34): "&quot;"})`,
plus a test. The new test also covers only `SubjectType`. Presentation, transformations Item,
time-window, buckets and `ReportDef id` are untested; add one round-trip assertion per site.

## NIT

- N1. [`src/vcfcf_dashboards/cli.py:548`] The comment "the instance still holds the old
  content" is the same false claim the wording commit removed elsewhere.
- N2. [`installer.py:1205`] `_profile_auth_source` runs before the pak-existence check and
  re-resolves the profile independently of `_resolve_credentials`. That is harmless but
  duplicates resolution. Returning the source from `_resolve_credentials` would keep one source
  of truth.

## Distribution zips (CLAUDE.md "After tooling changes")

**Stale.** The trigger files touched are `src/vcfcf_packaging/templates/install.py`,
`src/vcfcf_packaging/templates/install.ps1` and `src/vcfcf_core/dashboards/render.py`. The
render change is byte-identical for current content, but the rule is path-based. Not touched:
`builder.py`, `discrete_builder.py`, `release_builder.py`, `assembly.py`, `alerts/render.py`.
`CURRENT_TEMPLATE_VERSION` was bumped (`2026-11-07-1` to `2026-11-11-1`), so distributed copies
will report stale. A full `content-packager` rebuild of every manifest in `bundles/` is required.

## If shipped as-is

An operator whose profile uses a non-Local source and who installs with a local account gets a
pak installed with its account watch failing to authenticate: no pre-install read, no restart of
FAILED remote-collector accounts, and an UNCHECKED line that does not name the cause. Before
this change, the same run watched and restarted correctly.
