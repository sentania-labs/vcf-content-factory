# Framework review (ROUND 2): install.ps1 TLS gate + advisory parity (#106, #104)

- **Branch:** `fix-install-ps1-parity` (uncommitted working tree)
- **Date:** 2026-08-21
- **Area:** `src/vcfops_packaging/templates/install.ps1`,
  `src/vcfops_packaging/templates/install.py`,
  `src/vcfops_packaging/template_version.py`
- **Round 1 report:** `packaging-install-ps1-issues-104-106-2026-08-21.md`
  (CHANGES REQUESTED, 2 BLOCKING)
- **Verdict:** **CHANGES REQUESTED** (1 BLOCKING / 2 WARNING / 5 NIT)

Round 1's two BLOCKING findings are **both genuinely resolved**, verified by
my own measurement against the file on disk, not by the claim table. One
**new** BLOCKING finding surfaced from the round-2 extraction itself, and it
is exactly the question the brief asked me to answer ("no OTHER silent
divergences between the two installers' advisory paths").

## Checks re-run independently

| Check | Result |
|---|---|
| `vcfops_* validate` chain (all 7, correct module list) | **pass**, exit 0 each |
| `python3 -m pytest -q` | **939 passed, 4 skipped**, 178 deselected (matches claim) |
| `pytest tests/test_install_ps1_tls_and_advisories.py` | 22 passed (was 15 in round 1) |
| `pwsh` AST parse, `install.ps1` | **PARSE CLEAN** |
| `pwsh` AST parse, `install_ps1_advisory_harness.ps1` | **PARSE CLEAN** |
| Harness run against shipped template | **ALL ASSERTIONS PASSED**, exit 0 |
| Non-ASCII bytes, file-wide | zero |
| `??` / `?.` / `&&` / `\|\|` / ternary | zero |
| Machine-specific absolute paths (all 4 touched/new files) | zero |
| `check-staleness` over `dist/` | **STALE** on every zip, exit 1 (see W1) |
| `CURRENT_TEMPLATE_VERSION` bump | `2026-08-21-1` -> `2026-08-21-2`, **once**, correct |
| Render regression / `pak-compare` | n/a (no renderer or pak surface touched) |

---

## Round 1 BLOCKING 1 - RESOLVED (measured)

`$script:SkipSslVerify = $false` is gone; the prompt result is now
`$script:SslPromptDeclined` (`install.ps1:109`), the self-cancelling
`-and -not $SkipSslVerify` term is gone (`:2909`), and the
`Set-Variable -Name SkipSslVerify -Scope Script` promotion now runs.

I re-ran the measurement myself against the file on disk (shipped script,
empty directory, exits at "No bundles found" after the SSL preamble):

```
=== A: no flag, no env       ===  (no warning)          <- correct
=== B: -SkipSslVerify        ===  WARNING: TLS certificate verification disabled.
=== C: VCFOPS_VERIFY_SSL=false ==  WARNING: TLS certificate verification disabled.
=== D: VCFOPS_VERIFY_SSL=true  ==  (no warning)          <- correct
```

**Inverse confirmed: no path disables verification unless asked.**
`Set-Variable -Name SkipSslVerify` appears exactly once in the file, inside
`if ($script:SslPromptDeclined)`, and `$script:SslPromptDeclined = $true`
appears exactly once, inside `if (-not $SkipSslVerify)` after an explicit
`n`/`no` answer. Cases A and D above produce no bypass.

Three further things I checked that the claim did not assert:

1. **Promotion semantics.** `Set-Variable -Scope Script` from script top level
   genuinely reaches the `param()` variable and preserves its type. Measured
   with a faithful mini-script: callsite reads `false` before, `TRUE` after,
   `SwitchParameter` / `IsPresent: True`, and the
   `if ($SkipSslVerify -and Major -ge 6)` splat idiom used at 14 call sites
   picks it up.
2. **Ordering.** The promotion at `:2909` sits after `Get-Credentials`
   (`:2902`) and before `$script:BaseUrl` is set (`:2915`).
   `Get-Credentials` makes no API call (it only prompts), and `Invoke-Api`
   builds its URI from `$script:BaseUrl`. So **no request can precede the
   promotion** - the interactive path is not weakened by moving the bypass
   out of `Get-Credentials`.
3. **The guard expression is silent.** `'TrustAllCertsVcf' -as [type]` on an
   unloaded type returns `$null` and emits **zero** error records under
   `StrictMode Latest` + `$ErrorActionPreference='Stop'`. Measured.

## Round 1 BLOCKING 2 - RESOLVED (measured)

`Get-PropValue` (`install.ps1:190-216`) and the extraction of the summary
block into `Write-ImportSummaryWarnings` (`:638-670`) both do what is
claimed.

**`Get-PropValue` genuinely handles both shapes.** I first confirmed the
premise, and in doing so corrected an error in my own round-1 report: under
`Set-StrictMode -Version Latest`, a **hashtable** missing-key read throws
`PropertyNotFoundException` too, not just a `PSCustomObject`. (Round 1 said
"hashtable key misses do not throw under StrictMode." That was wrong. See
N5.) So the `IDictionary` branch is not defensive padding - it is load-bearing
for the `@{ __statusCode; __body; __error }` shape `Invoke-Api` returns on an
HTTP error. Measured against the real function extracted from the template:

```
hashtable PSObject.Properties[missing]      -> null, no throw
Get-AllSkippedSummaries(errShape)           -> count 0, no throw
Get-AllSkippedSummaries($null)              -> count 0, no throw
Write-ImportSummaryWarnings(errShape)       -> 0 lines, no throw
UNGUARDED $resp.policySummaries (errShape)  -> THREW: PropertyNotFoundException
```

**The extraction is faithful**, with one exception that is now B1 below.
Comparing against `git show main:install.ps1`:

- `$osState = if ($os.state) {...} else {""}` -> `[string](Get-PropValue ...)`:
  equivalent (`[string]$null` is `""`).
- `$os.imported` interpolated directly -> `$osImported = Get-PropValue ...`:
  strictly safer (the old form threw when `imported` was absent).
- Operator precedence preserved: PowerShell binds `-and` tighter than `-or`,
  so main's `A -and B -or C -or D` was already `(A -and B) -or C -or D`, and
  the new explicit parenthesisation matches - **except** for the removal of
  the `-or $osSkipped -gt 0` term, which is B1.

**The new harness cases exercise real code, not a stub.**
`install_ps1_advisory_harness.ps1:86-107` drives `Write-ImportSummaryWarnings`
loaded verbatim from the shipped template by AST, under
`Set-StrictMode -Version Latest` + `$ErrorActionPreference='Stop'`
(`:16-17`), with the exact input that used to throw
(`'{"state":"FINISHED"}'`, no `operationSummaries`). It also asserts the
error-hashtable shape through `Get-PropValue`. The remaining
`Import-ContentZip` stub is still there for the `Install-Dashboard` cases, but
`:201-205` now carries an explicit comment telling the reader **not** to read
those assertions as coverage of `Import-ContentZip`. That is the honest
construction; the coverage hole round 1 named is closed.

Round 1's N1 is also fixed: the harness now replays the bounds from the
template's own `AssignmentStatementAst` and throws if it does not find
exactly two (`:44-54`).

## Round 3 addition - TEMPLATE_VERSION deletion is CORRECT, independently confirmed

I verified the "nothing reads it" claim rather than accepting it:

- Bare-token grep across `src/`, `tests/`, `.claude/`, `knowledge/`: the only
  surviving `\bTEMPLATE_VERSION\b` hits are the new regression test and my own
  round-1 report. Zero code reads either script's literal.
- Both builders copy the templates **verbatim** with no substitution:
  `builder.py:622-623` and `discrete_builder.py:710-711` do
  `read_text(...)`, and `builder.py:736-737` / `discrete_builder.py:856-857`
  do `writestr(...)` of that same string. No `.replace`, no `format`, no
  stamping. `builder.py:29` states this as the design.
- `release_builder.py` does not reference either template at all.
- `cmd_check_staleness` (`cli.py:503-550`) reads `template_version` from the
  zip's `vcfops_manifest.json`, which both builders stamp from
  `CURRENT_TEMPLATE_VERSION`.

So the deletion is a cleanup, not a regression, and it is now pinned by
`test_no_false_template_version_stamp` for both templates - which also asserts
the false phrase `"injected at build time"` is gone. Round 1's W3 is resolved
and regression-proofed.

---

## BLOCKING

### B1. The mid-stream WARN narrowing silently removes the **only** no-op signal for `SUPER_METRICS` and `REPORTS` on the PowerShell path, and diverges from `install.py`

**Authority:** dimension 8 (silent capability change / downgrade - "a silent
downgrade is BLOCKING"); `knowledge/context/wire-formats/wire_formats.md:287-310`
(this change's own text: *"mirrors it line for line"*, *"Parity is exact for
DASHBOARDS / VIEW_DEFINITIONS"*, and a carve-out that names **only** the
SUPER_METRICS retry); `install.py:454`.

`Write-ImportSummaryWarnings` (`install.ps1:665`) drops the
`-or $osSkipped -gt 0` term that `install.py:454` still has:

```powershell
# install.ps1:665  (new)
if (($osState -ne "FINISHED" -and $osState -ne "") -or $osFailed -gt 0) {
```
```python
# install.py:454   (unchanged)
if os_state not in ("FINISHED", "") or os_failed > 0 or os_skipped > 0:
```

Measured, driving the real PowerShell function and `install.py`'s verbatim
condition over the same three envelopes:

```
PS  [SUPER_METRICS all-skipped (ghost state)] -> 0 line(s)
PY  [SUPER_METRICS all-skipped (ghost state)] -> WARN: content type SUPER_METRICS: imported=0 skipped=4 failed=0 state=FINISHED

PS  [REPORTS all-skipped]                     -> 0 line(s)
PY  [REPORTS all-skipped]                     -> WARN: content type REPORTS: imported=0 skipped=2 failed=0 state=FINISHED

PS  [normal re-sync (imported=1 skipped=1)]   -> 0 line(s)
PY  [normal re-sync (imported=1 skipped=1)]   -> WARN: content type DASHBOARDS: imported=1 skipped=1 failed=0 state=FINISHED
```

And it is a **regression against `main`**, not a pre-existing gap. Running
main's inline condition verbatim over the SM envelope:

```
OLD-PS WARN: content type SUPER_METRICS: imported=0 skipped=4 failed=0 state=FINISHED
```

**Why this is BLOCKING rather than the noise reduction it is documented as.**
The in-comment justification (`:643-648`) is that the signal is *relocated* to
a named per-content-type advisory. That relocation is real - but it covers
**only** `DASHBOARDS` and `VIEW_DEFINITIONS`, which the change's own
wire-format text states. `Install-Supermetrics` (`:1997`) and
`Install-Reports` (`:2253`) both do `$null = Import-ContentZip ...` and have
no advisory at all. So for those two content types the noise was deleted and
nothing replaced it.

The resulting end-to-end experience for a Windows operator hitting the
documented SUPER_METRICS ghost state is:

1. no auto-retry (known, deliberate, issue #108 - out of scope), **and now**
2. no `WARN` line (new, this diff), **and**
3. `OK  Imported 4 super metric(s)` - an affirmatively false success line
   with nothing anywhere in the run contradicting it.

That is the reports-green-while-broken class this PR exists to kill, newly
introduced in the same file, on the type where the factory already knows the
failure mode is real. #108 made the retry a documented non-parity; it did not
license removing the warning too.

I accepted this narrowing in round 1 (dimension 8, "net upgrade"). **I was
wrong**: I evaluated it only against DASHBOARDS/VIEW_DEFINITIONS, where the
relocated advisory does cover it. It is in scope for this round because the
round-2 extraction re-authored the condition, and because the brief asked
directly for OTHER silent divergences between the two installers.

**Smallest correct fix:** restore the term in
`Write-ImportSummaryWarnings`, matching `install.py:454` exactly:

```powershell
if (($osState -ne "FINISHED" -and $osState -ne "") -or $osFailed -gt 0 -or $osSkipped -gt 0) {
```

The cry-wolf reduction may well be right - but it has to be made in **both**
installers, and only *after* the named advisory covers SUPER_METRICS and
REPORTS. That is a larger change than #104's scope; do it as a follow-up, not
as a side effect of an extraction.

---

## WARNING

### W1. Still no `content-packager` rebuild flagged (round 1 W2, unresolved)

`src/vcfops_packaging/templates/install.ps1` and `install.py` are both on
CLAUDE.md's "After tooling changes" list, so **all dist zips are stale**.
Confirmed live across `dist/`:

```
dist/bundles/vks-core-consumption-bundle.zip        STALE -- 2026-08-21-1, current 2026-08-21-2
dist/bundles/storage-path-monitoring.zip            STALE
dist/reports/vks-core-consumption-report.zip        STALE
dist/dashboards/vks-core-consumption-dashboard.zip  STALE
dist/dashboards/cpu-support-status-dashboard.zip    STALE
dist/dashboards/demand-driven-capacity-v2.zip       STALE
(...every zip under dist/)
```

The **signal** half of dimension 9 is correct and complete (see below); this
is the artifact half. A full `content-packager` rebuild of every manifest in
`bundles/` must happen before the PR ships.

### W2. Pre-existing unguarded API-derived member access remains throughout the file, including post-import

The brief asked me to look beyond the sites `tooling` named. There are ~25
of them. A mechanical AST/regex audit of every variable assigned from
`Invoke-Api` and then dot-accessed:

```
761   $resp.policySummaries       Get-DefaultPolicyId      <- called by Install-SmEnable (InstallOrder 3)
774   $resp.superMetrics          Get-SupermetricsByName
778   $resp.pageInfo              Get-SupermetricsByName
1179  $resp.groups                custom groups            <- InstallOrder 4
1191  $chk.groups
1222  $resp.groups / 1228 pageInfo
2270  $r.symptomDefinitions       <- InstallOrder 6
2319  $r.alertDefinitions         <- InstallOrder 7
590/600/611/612  $g.state / $g.startTime  (marker probe)
570   $resp.token
```

Measured: `$err.policySummaries` on the `Invoke-Api` error-hashtable shape
throws `PropertyNotFoundException` under StrictMode. Several of these run
**after** content has already landed (`Install-SmEnable` is InstallOrder 3,
behind the supermetric and dashboard imports), so the failure mode is
identical to round 1's B2: a partial install with a raw stack trace.

**Not blocking, deliberately.** Every one of these is pre-existing, untouched
by this diff, and outside #104/#106's scope; escalating the whole file's
latent surface in round 2 would be moving the goalposts. But it is now a
bounded, mechanical follow-up: `Get-PropValue` exists, so the fix is a
sed-and-review pass. **File a follow-up issue** rather than letting it be
re-found on the next incident.

---

## NIT

### N1. `Get-AllSkippedSummaries` does not use the new `Get-PropValue` helper

`install.ps1:1508-1521` probes with `$Result.PSObject.Properties[...]`
directly while the sibling code introduced in the same diff routes through
`Get-PropValue`. Measured safe (`PSObject.Properties[missing]` on a hashtable
returns `$null` without throwing, so the error shape is tolerated), so this is
cosmetic - but it leaves two idioms for the same job in one file, and only one
of them is the one the guide now teaches.

### N2. `guide_powershell.md` StrictMode section is still incomplete in the way that produced `Get-PropValue`

The corrected section (`guide_powershell.md`, "StrictMode + PSCustomObject")
teaches the `PSObject.Properties[$key]` probe and correctly forbids `?.`. It
does **not** say the two things this change actually had to discover:

1. Under `StrictMode -Version Latest`, a **hashtable** missing-key read throws
   `PropertyNotFoundException` too. The heading implies the trap is
   PSCustomObject-only.
2. `$hashtable.PSObject.Properties[$key]` returns `$null` for a key that is
   present, so the guide's own recommended snippet silently reads nothing on
   the `Invoke-Api` error shape. That is precisely why `Get-PropValue` needs
   its `IDictionary` branch.

An agent following the guide as written would write the probe and still be
wrong for half the shapes `Invoke-Api` returns. Fold the `Get-PropValue`
two-shape rule into the guide.

### N3. `Add-Type` is not wrapped, so a 5.1 compile failure surfaces as a raw C# compiler error

`Disable-CertificateValidationLegacy` (`:151-160`) runs `Add-Type` under
`$ErrorActionPreference='Stop'` with no `try`/`catch`. If it ever fails on a
Windows PowerShell 5.1 box, the operator gets a compiler diagnostic rather
than a sentence naming `-SkipSslVerify`. See the 5.1 judgment below for why
this is a NIT and not more.

### N4. `RULE-018` / `knowledge/rules/posix-only.md` still does not exist (round 1 N2, unresolved)

`tests/test_install_ps1_tls_and_advisories.py:5` still cites
"(RULE-018 carves out shipped artifacts)". `knowledge/rules/` contains 18
files; none is `posix-only.md`, and `RULE-018` appears nowhere under
`knowledge/rules/`. Either the rule lands in a parallel change (say so in the
PR, ordering matters) or the docstring is a dead reference. The substantive
point stands on its own.

### N5. Correction to my own round-1 report

`packaging-install-ps1-issues-104-106-2026-08-21.md`, "Internal contract
changes" section, states: *"hashtable key misses do not throw under
StrictMode."* **That is false** - measured above, they throw
`PropertyNotFoundException`. The conclusion it supported (the uninstall
context lacking an `Advisories` key is safe) still holds, but by a different
route: `Invoke-InstallBundle` is only ever called with the `$globalCtx` built
at `:2679`, which always defines `Advisories`; the uninstall `$globalCtx`
(`:2821`) goes only to `Invoke-UninstallBundle`. Verified by call-site grep.
Recorded here so the round-1 report is not cited for a false premise.

---

## Dimension walk

| # | Dimension | Result |
|---|---|---|
| 1 | Global-default / pak-specific leak (`00d3382`) | **clean.** No renderer, no pak-specific default, no coordinate convention. The one new global default (TLS 1.2, `:133`) is deliberately global and correct. |
| 2 | Key / label derivation collision (`6c59f6b`) | **clean.** No key derivation; name extraction is display-only. |
| 3 | Wire-format conformance | **Drift in the doc's own claim - B1.** `wire_formats.md` now asserts "mirrors it line for line" and carves out only the SM retry; the mid-stream WARN divergence is real and uncarved. Everything else in the doc delta was verified accurate against the code. |
| 4 | Loader / validator correctness | **n/a.** No loader, no UUIDs, no prefixes. Chain green regardless. |
| 5 | Render regression vs known-good | **n/a** (renderer untouched). Extractor parity on real rendered artifacts was byte-identical in round 1 and those helpers are unchanged. |
| 6 | Builder / pak structure | **n/a.** Builders unchanged; confirmed they copy both templates verbatim. |
| 7 | Corpus regression | **clean.** Seven validate commands exit 0; 939 passed / 4 skipped. |
| 8 | Silent capability change / downgrade | **B1.** A signal present on `main` and present in `install.py` is now absent on the PowerShell path for SUPER_METRICS and REPORTS, with a false success line left standing. |
| 9 | Stale-zip discipline **and the signal** | **Stamp: correct.** `2026-08-21-1` -> `2026-08-21-2`, exactly one bump relative to `main`, correct `YYYY-MM-DD-N` increment, both builders stamp it into `vcfops_manifest.json`, `check-staleness` flips every dist zip to STALE (measured). **Signal hygiene: resolved** - the false in-script stamps are deleted from *both* templates and pinned by a test. **Artifact: W1**, still not flagged. |
| 10 | Test coverage of the change | **Good.** 22 tests (up from 15), including the real-script SSL preamble runs (`_run_installer`) and the both-template stamp pin; the harness now drives the real `Write-ImportSummaryWarnings` and AST-extracts the bounds. **Gap:** nothing pins the mid-stream WARN condition against `install.py`'s, which is how B1 got through. A parity test on that condition would have caught it. |

---

## Judgment 1 (asked): how much risk does the never-executed `Add-Type` leave a PowerShell 5.1 operator?

**Low, and the asymmetry runs the right way. Nothing in the change makes a
5.1 failure worse or harder to diagnose than the status quo.**

The claim itself checks out: on `main`, both cert-bypass sites were
unreachable (round 1 B1), so the `ICertificatePolicy` `Add-Type` has never
compiled on a customer machine, and neither has `SecurityProtocol = Tls12`.

What the change newly exposes to 5.1:

1. **`Add-Type` compiling `TrustAllCertsVcf : ICertificatePolicy`.** The C#
   text is unchanged from `main` (it was already in the file twice); only its
   reachability changed. This is the canonical `TrustAllCertsPolicy` snippet
   used across a very large body of 5.1 scripts, so the compile risk is about
   as well-trodden as PowerShell gets. `ICertificatePolicy` is `[Obsolete]` in
   .NET Framework, which is a compiler *warning*, and `Add-Type` does not
   treat warnings as errors by default.
2. **`[SecurityProtocolType]::Tls12` evaluating on every 5.1 run.** This is
   the one genuinely new unconditional side effect on the 5.1 path, and the
   only one that could break a previously-working install. `Tls12` exists from
   .NET Framework 4.5, and Windows PowerShell 5.1 requires 4.5+, so the enum
   member is guaranteed present. Untestable here; low.

**Why a 5.1 failure would not be worse than today.** Both newly-reachable
blocks run **pre-flight**: `:164-167` is at script top level before anything
else, and the interactive promotion at `:2909-2913` still precedes
`$script:BaseUrl = ...` (`:2915`) and therefore every API call. So a failure
in either aborts with **nothing installed** - a clean early exit. The status
quo it replaces is worse in every case: that same operator today gets a TLS or
certificate failure at the first request, mid-run, having already been
prompted for credentials, or (with `-SkipSslVerify`) hangs on an
unanswerable `Verify SSL certificate? [Y/n]` prompt in a scripted run.

**The one diagnosability cost** is N3: `Add-Type` is not wrapped, so a
hypothetical compile failure prints a C# compiler diagnostic instead of a
sentence naming the flag the operator passed. Worth fixing, not worth
blocking.

**The verification ceiling from round 1 is unchanged and unclosed.** Windows
PowerShell 5.1 cannot run on this machine or any POSIX runner; everything
above is pwsh 7.5.1 plus static analysis of the file bytes. The
`windows-latest` CI job (both 5.1 and pwsh 7, plus PSScriptAnalyzer
`PSUseCompatibleSyntax`/`PSUseCompatibleCmdlets` targeting 5.1, which runs on
the existing Linux runner) remains the right structural fix and remains
absent. Until it exists, every `install.ps1` change ships on static evidence.

## Judgment 2 (asked): does the advisory behavior match `install.py`'s contract, or merely resemble it?

**It matches for DASHBOARDS / VIEW_DEFINITIONS. It does not match on the
mid-stream WARN line, and that divergence is undocumented and silent - B1.**

Verified as matching (independent string-fragment comparison across both
templates plus a structural read of `install.py:1387-1406`, `:1550-1605`,
`:2515-2569` against their PowerShell counterparts):

- `_all_skipped_summaries` vs `Get-AllSkippedSummaries`: same
  `imported == 0 and skipped > 0` test, same `"?"` contentType fallback, same
  content-type filter, same non-numeric-count `continue`. PowerShell is
  strictly more defensive (it skips a `null` array entry where Python's
  `entry.get` would raise).
- Advisory sentence, both types: character-for-character identical, including
  the shared `unchanged_tail`.
- `"dashboard"` / `"view(s)"` fallbacks when no names extract: identical.
- Per-bundle prefix `[<name>] <advisory>`: identical.
- Trailer: identical wording, identical count line, identical `  ATTENTION  `
  indent, printed in **both** summary branches, **after** the 5-minute NOTE
  block in both.
- Final line: `"Done. No failures, but see the attention list at the end of
  this output."` vs `"Done. All content installed successfully."`, identical
  in both, chosen on the same condition.
- Advisories never reach the exit code in either: `_warn` is `print` only,
  `Write-Warn` is `Write-Host` only, and neither appends to the
  warnings/exit-2 list. Pinned by
  `test_advisories_never_reach_the_warnings_list`.
- View-title extraction: `root.iter("ViewDef")` + `find("Title")` vs
  `SelectNodes("//ViewDef")` + `SelectSingleNode("Title")` - equivalent
  semantics (descendant-or-self; direct child). Round 1 measured the outputs
  byte-identical on real rendered artifacts.

The known deliberate non-parity (SUPER_METRICS ghost-state retry, #108) is
correctly documented in `wire_formats.md`. **B1 is the other divergence, and
it is not documented anywhere.**

---

## If shipped as-is

The #106 TLS fix and the #104 dashboard/view advisory parity are real,
verified, and now actually reachable - a Windows operator finally gets TLS 1.2
forced and `-SkipSslVerify` honored, and a no-op dashboard import is named
rather than reported as a clean install. But a Windows operator whose
**super metrics** all skip (the documented ghost-state case, where
`install.py` retries and PowerShell does not) now sees *less* than they did
before this PR: no retry, no `WARN` line, and `OK  Imported N super metric(s)`
as the last word - a green report over an instance that did not change. Same
for an all-skipped reports import. And until `content-packager` rebuilds,
every distributed zip still carries the old `install.ps1`, though
`check-staleness` now correctly says so on all of them.
