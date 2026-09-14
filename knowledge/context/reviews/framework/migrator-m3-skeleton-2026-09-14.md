# Framework review: vcf-cf-migrator M3 skeleton (feat/m3-skeleton)

Date: 2026-09-14. Reviewer: framework-reviewer. Repo under review:
`sentania-labs/vcf-cf-migrator`, clone at `content/migrator/`, branch
`feat/m3-skeleton`, six commits over `main` (6241b10 .. cffd763).
Spec: `knowledge/designs/content-migrator-v1.md` (Shape, Repo, M3).
CI rules: `~/.claude/skills/github-ci/SKILL.md`. Precedent:
`.github/workflows/publish-core.yml`.

## Verdict

APPROVE. 0 BLOCKING / 6 WARNING / 8 NIT. Every finding below gets fixed
in the one re-brief before the PR opens (CLAUDE.md delegation rule 9);
two are factory-side and become follow-up issues.

## What I re-ran (scratch venv under `$CLAUDE_JOB_DIR/tmp/mig-venv`, never the factory venv)

| Check | Result |
|---|---|
| `pip install <clone>` in a fresh venv | pulls `vcf-cf-tooling-core 0.1.0` by the release URL; migrator installs as `0.0.1.dev7+gcffd7638f` |
| `pytest -q` (PYTHONPATH unset) | 19 passed |
| `inspect` on `tests/fixtures` generator output | 12 items, 1 carried (`resources/content.properties`) |
| `inspect --json corpus/devel-9x-2026-09-14.zip` | 83 items: dashboard 12, view 28, supermetric 33, customgroup 3, symptom 4, alert 2, report 1. Matches `configuration.json` counts and `unzip -l` (views.zip has 28 `<ViewDef`, reports.zip one `<ReportDef>`). No duplicate uuids, nothing carried. |
| corpus zip minus `reports.zip` + `customgroups.json` | rc 0, no traceback, counts drop accordingly |
| corpus zip minus `dashboards/`, `dashboardsharings/`, `supermetrics.json`, `usermappings.json` | rc 0, no traceback |
| marker-only zip, empty zip, junk zip (bad xml/json/inner zip) | rc 0, no traceback; junk members listed as carried |
| corpus zip with `configuration.json` = `{"version": 1, ...}` | **refused: "export identifies as VCF Operations 1; the floor is 8.10"** (W1) |
| `vermin -t=3.9-` over `src/`, `tests/`, and the installed `vcfcf_core` | no violations |
| core wheel contents | 36 `.py`, zero data files; only third-party import is `yaml` |
| PyInstaller `--onefile --copy-metadata x2` (Linux) | 9.3 MB binary; run from an empty dir with `env -i`: `version` prints both versions (not 0.0.0), `inspect` fixture = 12, corpus = 83, `tree` stub rc 2. Bundle carries both dist-infos, `yaml`, all five migrator modules, 8 of 36 `vcfcf_core` modules (only what `inspect` imports; see N7). |
| `ui --no-browser --port N` from the binary and from the venv script | `ss` shows `127.0.0.1:N` only; GET 200 with versions, corpus_dir control, fixture listing; SIGINT sent from a Python harness stops both with rc 0 and "stopped" on stderr (a `&` job in non-interactive bash ignores SIGINT, so the first attempt was a false negative). |
| POST `/settings` with `Origin: http://evil.example` | accepted (303), settings file rewritten (W2) |
| POST `/inspect` with `zip=/etc/hostname` | reads the path, answers "is not a zip file" (W2) |
| `actionlint` on both workflows | clean |
| Action SHAs vs `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` | checkout `11d5960a…` = v4 / v4.4.0; setup-python `a26af69b…` = v5 / v5.6.0; upload-artifact `ea165f8d…` = v4 / v4.6.2; download-artifact `d3f86a10…` = v4 / v4.3.0. All correct. |
| Em-dash / en-dash grep over the tree | none |
| `git log -p --all` for corpus identifiers (owner uuid, marker, signature) and secrets | none; `corpus/` gitignored and `git check-ignore` confirms the zip |
| Repo visibility / default branch | public / main; no `v*` tags yet |

## release.yml walk-through (as if `v0.0.1` were pushed)

- `validate`: `if: github.repository == 'sentania-labs/vcf-cf-migrator'` gates the whole chain via `needs`. `fetch-depth: 0` fetches all branches and tags, so `git fetch origin main` + `merge-base --is-ancestor` works (same shape that released `core-v0.1.0`). `pip install .` at the tagged detached HEAD: setuptools-scm's `git describe --tags --long --match v*` yields `v0.0.1-0-g<sha>` = `0.0.1`; `*.egg-info/` and `build/` are gitignored so `--dirty` stays clean. Version-equals-tag check holds.
- `binaries`: `shell: bash` on all three; `--name vcfcf-migrator-windows` gives `vcfcf-migrator-windows.exe`; `$RUNNER_TEMP` mixed paths work under Git Bash. Smoke runs from a directory holding only the binary, and the `grep -F "vcfcf-migrator ${GITHUB_REF_NAME#v}"` check catches a 0.0.0 binary.
- `publish`: wheel built with build isolation (setuptools-scm present, version from tag); `merge-multiple: true` lands three uniquely named files; `chmod +x` restores the bit upload-artifact drops; `gh release view` then `upload --clobber` else `create` is idempotent per tag.

## Findings

### WARNING

- **W1** `src/vcfcf_migrator/export_reader.py:56` (`_VERSION_KEYS`) and `:130` (`_version_from_manifest`). Authority: RULE-002 (no fabrication), spec "8.x floor". The floor keys on a bare `version` manifest key that no real export carries; the fixture invents it. When a `version` key does appear in a 9.x manifest it is far more likely a format version than a product version, and the reader refuses the export with a false message (proved: `{"version": 1}` on the real corpus zip = "refused: VCF Operations 1"). → Only treat a value as a product version when it is a dotted `major.minor[.patch]` string; never refuse on a bare integer; drop `version` from the key list unless the 8.x corpus proves it, and record the real key name when it lands.
- **W2** `src/vcfcf_migrator/ui.py:118` (`do_POST`). Authority: spec "no network", house rule "no credentials"; `ss` proves loopback-only, but any web page the admin visits can POST to `127.0.0.1:<port>` (no Origin/Host check): a foreign-origin POST rewrote `settings.json` and a POST can make the process read any local path. Bounded in M3 (one setting, listing shown only locally); at M4 `build` writes files, so this must be closed now. → Reject a POST whose `Origin` (or `Host` when no Origin) is not `http://127.0.0.1:<port>`; add a test that a foreign Origin gets 403.
- **W3** `.github/workflows/release.yml:88` (`macos-latest`) and `README.md:15`. Authority: spec "Mac, Windows, Linux"; github-ci skill (macos-latest is arm64). The macOS asset is Apple-Silicon-only and is named as if it were universal; an Intel-Mac admin gets "Bad CPU type in executable". → Name it `-macos-arm64` and either add `macos-13` (x86_64) to the matrix or state the architecture in README.
- **W4** `README.md` §Install. Authority: house rule 8 (seen working) and the M3 done criterion. CI proves the binaries run on the runner; an operator's download does not run as documented: Linux/macOS need `chmod +x` (release assets carry no mode), macOS Gatekeeper blocks an unsigned quarantined binary (`xattr -d com.apple.quarantine` or Privacy & Security allow), Windows SmartScreen prompts. → Add a three-line "first run" note per OS.
- **W5** `tests/fixtures/make_export_fixture.py` vs `corpus/devel-9x-2026-09-14.zip`. Authority: spec "Each fixture is authored from a corpus example by hand". The fixture's member names (`AlertContent.xml`, `CustomGroup.json`, `Notification Setting.json`, `Reports.zip`) do not mirror the 9.x corpus (`symptomdefs.xml`, `alertdefs.xml`, `customgroups.json`, `reports.zip`); the reader dispatches by content so it works, but the committed tier does not exercise the real layout, and the declared missing-optional-members handling has no test (I proved it by hand). → Add a corpus-shaped variant (split symptom/alert XML, lowercase names, no version key) and a test that drops `reports.zip` and `customgroups.json`.
- **W6** `src/vcfcf_migrator/export_reader.py:34`. Authority: spec "library it builds on". Imports three underscore-private functions from `vcfcf_core.extractor.extractor`; the exact pin means no silent drift, but the next core bump can break the migrator with no deprecation signal. → Factory-side follow-up issue: export public names (`content_xml_from_export_zip`, `dashboards_from_export_zip`, `supermetrics_from_export_zip`) in core; migrator switches on the next core bump.

### NIT

- **N1** `.github/workflows/release.yml:22` `permissions: contents: write` is workflow-wide; only `publish` needs it. → `contents: read` at top, `write` on the publish job.
- **N2** `.github/workflows/release.yml:40-46` two redundant tag checks (`case` then `grep -E`) on top of the `on.push.tags` glob. → keep the `grep -E` strict check only.
- **N3** `README.md:38` says `--corpus DIR`; it is a global option and must precede the subcommand (`vcfcf-migrator ui --corpus DIR` errors "unrecognized arguments"). → show `vcfcf-migrator --corpus DIR ui`.
- **N4** `README.md:33` "Every command line option has a control on it" overclaims: `--port`, `--no-browser`, `tree <zip>`, `build --select/--out` have none (the last two are stubs). → "Every setting has a control on it; launch options (`--port`, `--no-browser`) are command-line only."
- **N5** `src/vcfcf_migrator/export_reader.py:243` an empty zip or one with neither marker nor `configuration.json` exits 0 with zero items and only a note. → exit 1 ("not a content export") when both are absent.
- **N6** `tests/test_ui.py:99` uses `urllib.error.HTTPError` without `import urllib.error` (works only because `urllib.request` imports it). → add the import.
- **N7** PyInstaller bundles only statically imported core modules (8 of 36 today; `dep_walker` and the preview stack are absent). Not an M3 defect; M4 must keep core imports static or add `--hidden-import`, and the binary smoke should exercise every subcommand it claims. → add a comment in release.yml next to the PyInstaller step.
- **N8** Factory-side: spec §Repo says the clone gets "one line in a registry"; `.gitignore` has `content/migrator/` but `knowledge/context/managed_paks.md` has no migrator line. → follow-up on the factory, not this branch.

## Author claims vs observed

All claims held: core pulled by URL, 19 passed, fixture 12 / corpus 83 matching the manifest, binary works from an empty dir with cleared env after `--copy-metadata`, ui serves / saves / stops on SIGINT, actionlint clean. Declared limits confirmed: no product version in the 9.x export (`configuration.json` keys: customGroups, reports, symptomDefs, dashboardsByOwner, superMetrics, signature, alertDefs, type, dashboards, views), custom groups have no id key in the export, PR-time corpus compare absent (M4).

## If shipped as-is

`v0.0.1` would release three binaries that run `inspect` on the corpus zip (the M3 bar). An admin on an Intel Mac could not run the macOS one, any Mac admin would hit Gatekeeper with no README guidance, a future export carrying a format-version integer would be refused as "VCF Operations 1", and a visited web page could rewrite the ui's saved corpus directory.

## Round 2 (2026-09-14, same day): fix commits 24d0201, 0d62232, 892768b, eab7612

Branch now ten commits over `main` (6241b10 .. eab7612). Scratch venv
`$CLAUDE_JOB_DIR/tmp/mig-venv-r2b` (fresh `pip install <clone> pytest`;
migrator `0.0.1.dev11+geab7612cc`, core `0.1.0`).

### Verdict

APPROVE. 0 BLOCKING / 0 WARNING / 2 NIT. All six warnings and seven of
eight nits from round 1 are closed for real (evidence below); N8 stays
open on the factory side (no branch change can close it).

### Re-run

| Check | Result |
|---|---|
| `pytest -q`, PYTHONPATH unset | 39 passed (was 19) |
| `inspect --json corpus/scott-8.18.7-2026-09-14.zip --source-version 8.18.7` | rc 0, 48 items: dashboard 5, view 19, supermetric 17, customgroup 2, recommendation 2, notificationrule 1, notificationtemplate 1, outboundsetting 1. Equals the manifest's content counts (dashboards 5, views 19, superMetrics 17, customGroups 2, recommendations 2, notificationRules 1, payloadTemplates 1, outboundSettings 1) and the spec's "Corpus on hand" paragraph. The nine non-content manifest kinds (policies, users, userGroups, userRoles, costDrivers, globalSettings, configFiles, authSources, integrations) are the 17 carried members. No duplicate uuids, no notes. |
| `inspect --json corpus/devel-9x-2026-09-14.zip --source-version 9.0.2` | rc 0, 83 items: dashboard 12, view 28, supermetric 33, customgroup 3, symptom 4, alert 2, report 1; equals `configuration.json`. Nothing carried. |
| Floor, both ways, on the real 9.x zip | `--source-version 8.9.0` rc 1 "refused: declared source version 8.9.0 is below the floor 8.10"; `--source-version 1` rc 2 "not major.minor[.patch]"; none declared rc 0 with "source version: not declared" and the note; `VCFCF_MIGRATOR_SOURCE_VERSION=8.18.7` picked up. |
| Real 9.x zip with `configuration.json` gaining `"version": 1` (W1 reproduction) | rc 0, 83 items, `version=1` shown in the manifest line, not refused. Reader no longer sniffs any manifest key (`_VERSION_KEYS` and `_version_from_manifest` gone). |
| Served ui, out of pytest, probed with `Origin: http://evil.example`, `Origin: http://127.0.0.1:<port+1>`, `Origin: null`, `Host: evil.example` (no Origin) on both `/settings` and `/inspect` | 403 on all eight; settings file absent after all of them. Own origin then 200 and the file appears with only that value. Below-floor `8.9` via the page: not saved. |
| `tests/test_ui.py::test_foreign_origin_post_is_refused_with_403` | exercises the same four header sets, asserts 403 each and `not settings.json.exists()` after, then proves own-origin and bare same-host pass. Not tautological. |
| `tests/test_cli.py` floor | refused `8.9.0`, `8.9`, `7.5.0` (rc 1); accepted `8.10`, `8.10.0`, `8.18.7`, `9.0.2` (rc 0); malformed `1`, `eight`, `8.`, `v8.10`, `8.10.1.2` rc 2; env and settings-file sources; `{"version": 1}` manifest rc 0. |
| Fixture vs 9.x corpus member names | `<digits>L.v1`, `configuration.json`, `views.zip`, `usermappings.json`, `dashboards/<owner>`, `dashboardsharings/<owner>`, `supermetrics.json`, `symptomdefs.xml`, `alertdefs.xml`, `customgroups.json`, `reports.zip`: all eleven present under the real names; the 8.x-only members (`recommendationdefs.xml`, `notificationrules.json`, `payloadtemplates.json`, `outboundsettings.json`, `policies.xml`) use the 8.x corpus names. `AlertContent.xml` / `CustomGroup.json` / `Reports.zip` gone. |
| Missing-member and not-an-export tests | `test_inspect_tolerates_missing_optional_members` drops three real member groups via `build_export_zip(without=...)`, asserts rc 0, no traceback and that each dropped kind is absent; `test_inspect_refuses_a_zip_that_is_not_a_content_export` proves empty zip rc 1, junk zip (readme + `supermetrics.json`, no marker/manifest) rc 1, marker-only rc 0. Real. |
| `actionlint` 1.7.12 on both workflows | clean; `macos-15-intel` is in actionlint's built-in label list and in `actions/runner-images` README (macOS 15, x64: `macos-15-large` or `macos-15-intel`). `macos-latest` is arm64 (macOS 26). |
| `permissions` in release.yml | `contents: read` at the top; `contents: write` only under `jobs.publish.permissions`. Publish uploads `-linux`, `-macos-arm64`, `-macos-x86_64`, `-windows.exe` and the wheel. |
| Em-dash / en-dash grep over the tree | none |
| Spec conformance | "8.x floor" row: floor on the declared value only, `--source-version` on every command (global option) with a page control, remembered in settings, undeclared inspect continues and says so, build refuses (M3 stub exits 2 either way; the refusal lands with M4). "Corpus on hand" counts reproduced exactly. |

### Round 1 findings, status

W1 closed (24d0201). W2 closed (0d62232). W3 closed (892768b). W4 closed (eab7612: chmod, Gatekeeper, SmartScreen). W5 closed (24d0201). W6: filed as factory issue #165. N1, N2, N7 closed (892768b). N3, N4 closed (eab7612). N5, N6 closed (24d0201, 0d62232). **N8 still open**: no factory issue exists and `knowledge/context/managed_paks.md` still has no migrator line; factory side, not this branch.

### New findings

- **N9** `src/vcfcf_migrator/ui.py:186` (`_same_origin`). `Origin: http://localhost:<port>` gets 403 with "only this page may post here". The tool prints and opens the `127.0.0.1` URL so the default path is fine, but an admin who runs `--port 8080` and types `localhost:8080` can load the page and then cannot save a setting, and the message tells them they are on the wrong page. → accept `http://localhost:<port>` alongside `http://127.0.0.1:<port>` (both are the same loopback socket), or have the 403 body name the URL to use.
- **N10** `.github/workflows/ci.yml:55` `vcfcf-migrator --source-version 8.18.7 inspect fixture.zip | head -3`. The step has no `shell: bash`, so it runs under `bash -e` without `pipefail`; if the accept path ever regressed to a refusal, `head` would exit 0 and the step would pass. pytest covers the accept path, so this is a masked CI check, not a gap. → drop `| head -3` or add `set -o pipefail`.

### If shipped as-is

`v0.0.1` releases four binaries plus the wheel; `inspect` matches both corpus manifests exactly; a foreign page cannot touch settings or make the process read a path. An admin who reaches the page by `localhost` instead of `127.0.0.1` gets a confusing 403 on save (N9).
