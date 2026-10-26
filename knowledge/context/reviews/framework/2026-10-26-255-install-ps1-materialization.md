# Framework Review: install.ps1 post-import materialization check (#255)

- **Branch:** `fix/255-install-ps1-materialization`, commit `fdd62f5`, diffed against `main` (`bc783ea`)
- **Reviewer:** framework-reviewer (RULE-013 blanket gate)
- **Date:** 2026-10-26
- **Verdict:** CHANGES REQUESTED
- **Findings:** 1 BLOCKING / 2 WARNING / 6 NIT
- **Surfaces:** `src/vcfcf_packaging/templates/install.ps1` (+576),
  `tests/test_install_ps1_materialization.py` (new),
  `tests/fixtures/install_ps1_materialization_harness.ps1` (new),
  `knowledge/context/authoring/guide_powershell.md` (+13)

## Checks re-run (independent)

- **validate chain x7:** PASS (supermetrics, dashboards, customgroups, symptoms, alerts,
  reports, managementpacks; all rc=0).
- **full pytest** (`-n auto --dist=loadgroup -m ""`): 2774 passed, 12 failed, 9 skipped.
  Six failures are the known main failures (`test_release_naming_phase_v2_item1.py` x5,
  `test_validator_phase2.py` x1). The other six (`test_publish_phase3`,
  `test_third_party_component_routing_phase5` x2, `test_third_party_routing` x2,
  `test_discrete_builder_builtin_metric_enables`) are environmental: this worktree has no
  `content/sdk-adapters/` clones, so `vcfcf_packaging validate` fails on
  `bundles/releases/synology-diskstation-managementpack.yaml` ("artifact source not
  found"). None touches the installer templates; not attributable to this diff.
- **Installer test files** (`test_install_ps1_materialization.py`,
  `test_install_ps1_tls_and_advisories.py`, `test_install_materialization.py`) with pwsh
  7.5.1 present: 129 passed.
- **Same new file with pwsh removed from PATH:** 5 passed, 22 skipped (see W1).
- **Mutation checks** (template copy, test module pointed at the copy):
  changing one word of the STALLED sentence killed `test_classifier_matches_core`;
  reverting the enable-warning filter to the old substring test killed
  `test_install_stalled_run_exits_2`. The harness really extracts and runs the shipped
  template's functions (AST `ParseFile` on the path under test, constants replayed from
  the same AST), not a copy.
- **CI evidence:** `gh run view 40341318759` (main, `bc783ea`): the `test` job runs on
  `runs-on: lab`; `test_advisory_harness` and all three `TestSkipSslVerifyIsReachable`
  tests are **SKIPPED** there. The lab image has no pwsh.
- **Measured under pwsh 7.5.1:** the guide's new pitfall reproduces exactly
  (`@($l).Count` over `New-Object ...List[object]` throws "Argument types do not match",
  empty or not; `::new()` and `List[string]` do not). Shipped `install.ps1` has no
  `New-Object ...List[object]` left.
- **Reference corpus scan:** 211 dashboard documents under `reference/references/`,
  `content/`, `third_party/`: max JSON depth 14, max 356 KB, zero case-colliding keys,
  zero empty-string keys (relevant to N1).
- render-regression: n/a (no renderer touched). pak-compare: n/a.

## Windows PowerShell 5.1 walk (static; 5.1 was not run, see W2)

Checked every added line:

- No `?.`, `??`, ternary, `&&`/`||`, `-AsHashtable`, `ConvertFrom-Json -Depth`,
  `-Parallel`, `-SkipHttpErrorCheck`, `-StatusCodeVariable`, `$IsWindows`.
  `TestPowerShellCompat::test_no_ps7_only_operators` and `test_ascii_only` pass over the
  whole file.
- `::new()` is used only on `List[object]` and `List[string]` (5.0+). Other generics
  (`HashSet[string]`, `Dictionary[string,object]`, `OrderedDictionary`) are built with
  `New-Object` and an `IEqualityComparer` argument; all exist in .NET Framework 4.x
  (`HashSet` in System.Core, loaded by 5.1).
- `System.IO.Compression.ZipArchive` is loaded by the top-level
  `Add-Type -AssemblyName System.IO.Compression` (install.ps1:1614), which runs before
  the main dispatch. On pwsh 7 the harness would not notice a missing `Add-Type`, but none
  is missing.
- `[Nullable[int]]` param, `[long]::TryParse(..., NumberStyles, CultureInfo, [ref])`,
  `StartsWith(string, StringComparison)`, `Array.Sort(arr, StringComparer.Ordinal)`,
  `StreamReader(stream, UTF8, $true)`: all .NET Framework APIs.
- TLS 1.2: the existing unconditional `-bor Tls12` for Major -lt 6 (install.ps1:148)
  covers the new `Invoke-RestMethod`/`Invoke-WebRequest` calls; cert bypass on 5.1 goes
  through the global `CertificatePolicy`, which `Invoke-WebRequest` honours.
  `-UseBasicParsing` is set on the download (pinned by `test_download_is_basic_parsing`).
- ASCII only, no BOM (file starts `3c 23 0a`).
- Array unrolling: every JSON-array read goes through `Get-MatJsonArray` /
  in-place `PSObject.Properties` reads, never a function return of the bare array, and
  every collection return is comma-wrapped. 5.1's `ConvertFrom-Json`
  (JavaScriptSerializer) preserves nested arrays as `object[]`; the one 5.1 unroll quirk
  (top-level array) does not apply, `dashboard.json` is an object. Depth 14 is far below
  any 5.1 recursion limit.
- Remaining 5.1 runtime-semantics risk is unprovable without a 5.1 run: see W2.

## Parity with install.py (line by line)

Read `_mat_*`, `_check_materialization`, `_report_materialization`,
`export_dashboards_zip`, `list_adapter_kind_keys`, `_extract_dashboard_id_names`, the
dashboard recording site and the summary block against the PowerShell side.

- OK / WAIT / STALLED / INCOMPLETE / ABSENT / UNCHECKED sentences: identical; pinned
  byte-for-byte by `test_report_lines_match_install_py` and per state by
  `test_classifier_matches_core`.
- Exit codes: STALLED joins the warnings, `exit 2`; INCOMPLETE/ABSENT/UNCHECKED are
  notes, exit 0. Matches `sys.exit(2)` path. Pinned by `test_install_stalled_run_exits_2`
  and `test_install_incomplete_run_does_not_end_on_all_successful`.
- Trailer: blank line, "N dashboard(s) need a later look (installed, but not confirmed
  finished building):", `  ATTENTION  ` lines, printed before the advisory trailer in
  both branches; "Done. No failures, but see the attention list..." when only notes.
  Matches `_print_advisories`.
- Wait: 180 default, 900 cap, `VCFCF_MATERIALIZATION_WAIT_S`, explicit 0 reports at
  once, re-check failure keeps the first read with `after=0`. Matches.
- Divergences found: N1 (degraded export shapes), N2 (env parse), N3 (download error
  text), N4 (warning order), N5 (pwsh 7 date coercion).

## Behavioural regressions in touched paths

- **Install-Dashboard "record only if the import changed it":** the record sits in the
  `else` of `$flagged.ContainsKey("DASHBOARDS")`, the same predicate as install.py's
  `"DASHBOARDS" not in flagged`. `List[object].Add` returns void, so nothing leaks into
  `Invoke-InstallBundle`'s return stream (which is the warnings list).
  `Get-DashboardIdNames` is wrapped in try/catch and returns `@()`, so a malformed
  dashboard.json cannot abort an install after the import landed. The success/advisory
  lines are unchanged. Pinned by `test_install_dashboard_records_only_changed` (both
  branches). No regression.
- **Super-metric enable-warning filter:** for every non-`MATERIALIZATION ` warning the
  predicate is unchanged (`-like *enable*`/`*resolve*`, case-insensitive as before);
  only lines starting with the exact ordinal prefix are excluded. A STALLED line naming
  "Enable and Resolve Board" no longer triggers the super-metric sentence (pinned, and
  the mutation above confirms the pin bites). No regression.
- **Bundle ctx sharing:** `ImportedDashboards` is the same `List` object in every bundle
  ctx, set from `$GlobalCtx`, mirroring install.py's shallow copy.

## Findings

### BLOCKING

**B1. [src/vcfcf_core/packaging/template_version.py:31] No `CURRENT_TEMPLATE_VERSION` bump
for an `install.ps1` change.** Authority: that module's own docstring ("Bump this value
whenever any of the following change: ... vcfcf_packaging/templates/install.ps1"),
CLAUDE.md "After tooling changes", reviewer dimension 9. The constant is still
`2026-10-24-1`, the value the install.py half of this same feature (#244) shipped
under. Every bundle built since 10-24 carries that stamp in `vcfops_manifest.json`, so
after this merges `check-staleness` reports every distributed copy, including the ones
whose `install.ps1` has no materialization check, as current. A Windows admin holding a
10-24 zip is never told to rebuild, which is exactly the gap #255 exists to close.
Fix: bump to `2026-10-26-1` and add a history line
("install.ps1: post-import dashboard materialization check, -SkipMaterializationCheck,
-MaterializationWait; issue #255"). Orchestrator: tooling's result and commit message do
not flag the stale zips; a full `content-packager` rebuild of every manifest in
`bundles/` is required after merge.

### WARNING

**W1. [tests/test_install_ps1_materialization.py:46, .github/workflows/ci.yml:21] The
behaviour layer, which carries every parity claim, will be skipped in CI.** Authority:
reviewer doctrine (a test that cannot fail is not proof), dimension 10. 22 of the 27 new
tests are `@needs_pwsh`; the CI `test` job runs on the `lab` pool, whose image has no
pwsh (main run 40341318759 shows the existing `test_advisory_harness` and
`TestSkipSslVerifyIsReachable` SKIPPED). In CI only the five static string checks run;
a future edit that breaks a sentence, the exit code or the classifier goes green.
Reproduced locally with pwsh off PATH: 5 passed, 22 skipped. Fix (tooling, this
branch): make the skip conditional on an opt-in, e.g. `VCFCF_REQUIRE_PWSH=1` turns
"PowerShell not installed" into a failure, mirroring `VCFCF_SDK_COMPAT_REQUIRED`; apply
it to `test_install_ps1_tls_and_advisories.py` too. Fix (orchestrator, github-ci skill,
not tooling): get pwsh into the job, either installed on the lab job or a hosted
`ubuntu-latest` job (pwsh is preinstalled there) running the two `install_ps1` test
files with the require switch set.

**W2. RULE-018: Windows PowerShell 5.1 compatibility is asserted by inspection only, and
no CI job can prove it.** Authority: `knowledge/rules/posix-only.md` carve-out
("installers must keep working on native Windows"); doctrine (unproven is a finding).
My static walk (above) found no 7-only construct. What a 5.1 run would still have to
prove: `ConvertFrom-Json` (JavaScriptSerializer under 5.1) on a real export
`dashboard.json`, the `New-Object` generic constructors with an `IEqualityComparer`
argument under 5.1 overload resolution, and the `Invoke-WebRequest -OutFile` download
under the legacy cert policy. No workflow has a `windows-latest` job (`ci.yml`,
`publish-core.yml`, `publish-buildkit.yml` are all `lab` or `ubuntu-latest`).
Recommendation: yes, add one. A GitHub-hosted `windows-latest` runner ships Windows
PowerShell 5.1 as `powershell.exe`, and the repo is public so hosted minutes are free.
Have `_run` / `_run_installer` take the interpreter from an env var (`pwsh` default,
`powershell.exe` on that job) and run the two `install_ps1` test files there with the
require switch. That is a workflow change through the github-ci skill; the test-side
interpreter parameter is tooling's and belongs on this branch with W1's switch.

### NIT

**N1. [install.ps1:2049-2097 `ConvertFrom-DashboardExportZip`] Degraded-shape
divergence from install.py and the core reader.** install.py
(`_mat_dashboards_from_export_zip`) and `vcfcf_core.extractor.dashboards_from_export_zip`
raise (so the run prints UNCHECKED) when a `dashboard.json` is not an object, when a
`dashboards[]` element is not an object (`dict(dash)`), or when reading an outer member
fails (`zf.read` is outside the inner try). The port `continue`s in all three, so those
dashboards print ABSENT ("was in the import but is not on the instance afterwards"),
which is false. Separately, `ConvertFrom-Json` on pwsh 7 throws on case-colliding keys
and empty-string keys (measured), which Python parses; one such key anywhere in an
owner's export would mark every dashboard that owner holds ABSENT. Zero such keys in 211
reference dashboard documents, and the exit code is unaffected (notes only), hence NIT.
Fix: match install.py's structure (outer member read outside the inner try; non-object
`dj` or `dash` throws "failed to parse dashboard export zip: ..."), and add a test for a
non-object element.

**N2. [install.ps1:1987 `Get-MaterializationWait`] Env-value parse narrower than
Python.** `int()` accepts `1_000` (and non-ASCII digits); the port falls back to 180 for
them. Fix: strip single underscores between digits before `TryParse`, and add `"1_000"`
to `test_wait_matches_factory`.

**N3. [install.ps1:2345-2350 `Export-DashboardsZip`] Download-failure text differs.**
install.py prints `export zip download failed (404)`; the port prints the .NET exception
message in the parentheses, so the UNCHECKED line differs between the two installers.
Fix: use `$_.Exception.Response.StatusCode.value__` when present (StrictMode-safe via
`PSObject.Properties`), else the message.

**N4. [install.ps1:3825 `Invoke-Install` summary] Warning order differs.** install.py
prints `enable_warnings + other_warnings`; the port prints `$allWarnings` in insertion
order. Pre-existing, but in the summary block this diff edits, and the task is "a
Windows admin sees the same thing". Fix: emit the enable-filtered list first, then the
rest, as install.py does.

**N5. [install.ps1:2083] pwsh 7 coerces ISO-8601 date strings to `DateTime`.** A resource
name like `2024-01-01T00:00:00Z` in `entryKeys.resource` prints as
`01/01/2024 00:00:00` (measured) on pwsh 7, verbatim on 5.1 and install.py. Unlikely in
practice. Fix if wanted: `-DateKind String` on 7.5+ behind the existing
`PSVersion.Major` gate, or accept and note it in the port header.

**N6. [install.ps1:2341-2350] 5.1 download progress bar.** `Invoke-WebRequest -OutFile`
on 5.1 renders a progress bar that slows large downloads markedly, and a CUSTOM
DASHBOARDS export covers every user's dashboards. Same pre-existing pattern as
`Get-MarkerFilename`. Fix: set `$ProgressPreference = 'SilentlyContinue'` locally around
the download.

## If shipped as-is

Windows admins on a rebuilt zip get the same materialization lines and exit code as
Linux admins. Everyone holding a 10-24 zip is told it is current and never gets the
check. CI would keep passing even if the port broke, because it never runs the tests
that exercise it.
