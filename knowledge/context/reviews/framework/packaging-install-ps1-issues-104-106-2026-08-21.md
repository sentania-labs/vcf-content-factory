# Framework review: install.ps1 TLS gate + advisory parity (#106, #104)

- **Branch:** `fix-install-ps1-parity` (uncommitted working tree)
- **Date:** 2026-08-21
- **Area:** `src/vcfops_packaging/templates/install.ps1`, `src/vcfops_packaging/template_version.py`
- **Verdict:** **CHANGES REQUESTED** (2 BLOCKING / 4 WARNING / 4 NIT)

## Scope reviewed

```
M knowledge/context/authoring/guide_powershell.md
M knowledge/context/wire-formats/wire_formats.md
M src/vcfops_packaging/template_version.py
M src/vcfops_packaging/templates/install.ps1      (+330 / -38)
? tests/test_install_ps1_tls_and_advisories.py
? tests/fixtures/install_ps1_advisory_harness.ps1
```

Weighting note: `install.ps1` is copied verbatim into every bundle zip
(`builder.py:623,737`; `discrete_builder.py:711,857`) and executes on
customers' Windows machines. Native-Windows correctness is in scope.

## Checks re-run independently

| Check | Result |
|---|---|
| `vcfops_* validate` chain (all 7) | **pass** (exit 0, all seven) |
| `python3 -m pytest -q` | **932 passed, 4 skipped**, 178 deselected (matches claim) |
| `pytest tests/test_install_ps1_tls_and_advisories.py` | 15 passed |
| `install.ps1` AST parse under pwsh 7.5.1 | **PARSE CLEAN**, zero errors |
| Non-ASCII bytes, file-wide | **zero** (byte scan, not line scan) |
| `??` / `?.` / `&&` / `||` / ternary | **zero** (independent scan incl. `) ? ... : ...` form) |
| Continuation literal starting with `&` | none |
| `?.Value` anywhere | none (Scott's `guide_powershell.md:19` correction confirmed necessary and correctly applied) |
| Cross-implementation extractor parity on real rendered artifacts | **byte-identical** (see below) |
| `check-staleness` against current dist zips | **STALE** correctly reported, exit 1 |
| `pak-compare` | n/a (no pak surface touched) |
| Render regression | n/a (renderer untouched) |

### Extractor parity, measured not asserted

Extracted the real `views_content.xml` + `dashboard.json` from
`dist/bundles/vks-core-consumption-bundle.zip` and ran both
implementations over them. The PowerShell helpers were loaded from the
shipped template by AST (not retyped), and the bounds were read from the
template's own assignment ASTs rather than restated:

```
PS  bounds: 120 / 20
PS  VIEWS: [VCF Content Factory] VKS Core Consumption by vCenter
PS  DASH:  VCF Content Factory/[VCF Content Factory] VKS Core Consumption
PY  VIEWS: ['[VCF Content Factory] VKS Core Consumption by vCenter']
PY  DASH:  ['VCF Content Factory/[VCF Content Factory] VKS Core Consumption']
PY  bounds: 120 20   clip -> 123 chars   cap -> 21 entries, last = "and 5 more"
```

Identical. Clip/cap/tail semantics match `install.py:_bounded_names`
exactly. The advisory sentence text, the `[bundle]` prefix, the trailer
header, the `ATTENTION` line shape, and both final-line strings are
character-for-character identical to `install.py:2520-2574`.

---

## BLOCKING

### B1. `install.ps1:105` clobbers the `-SkipSslVerify` parameter, so **both** cert-bypass call sites are unreachable

**Authority:** `knowledge/context/authoring/guide_powershell.md` ("Mirroring
footguns"); the change's own claim, tested by
`tests/test_install_ps1_tls_and_advisories.py:83`
(`test_cert_bypass_helper_guards_both_ps_version_and_type_redefinition`).

In a PowerShell **script**, `param()` variables live in the *script*
scope. `$script:SkipSslVerify` and `$SkipSslVerify` are therefore the
same variable. `install.ps1:105`:

```powershell
$script:SkipSslVerify = $false        # line 105, runs unconditionally
```

overwrites the switch the operator passed on the command line, before
line 154 ever reads it. Reproduced with a faithful mini-script using the
verbatim lines (param default incl. `$env:VCFOPS_VERIFY_SSL`, line 105,
line 154, the `Get-Credentials` guard at 411, and the line-2842 guard):

```
=== run with -SkipSslVerify ===
site-1 cert bypass ran: False
  -> would PROMPT 'Verify SSL certificate? [Y/n]'
site-2 guard ($script:SkipSslVerify -and -not $SkipSslVerify): False
=== run with VCFOPS_VERIFY_SSL=false ===
site-1 cert bypass ran: False
  -> would PROMPT 'Verify SSL certificate? [Y/n]'
site-2 guard: False
```

Consequences:

1. `install.ps1:154` `if ($SkipSslVerify) { Disable-CertificateValidationLegacy }`
   is **dead code**. The consolidation refactor therefore consolidates
   two call sites neither of which can execute.
2. `install.ps1:2842` `if ($script:SkipSslVerify -and -not $SkipSslVerify)`
   is `X -and -not X` — **always false**. Dead too. The interactive path
   still works only because `Get-Credentials` sets the shared variable
   at `:414`, which the `-and Major -ge 6` sites at `:485,525,581,619,...`
   read directly.
3. The comment at `:408-410` ("Prompt for SSL verification only when
   neither `-SkipSslVerify` nor `VCFOPS_VERIFY_SSL=false` was supplied")
   documents an intent that line 105 defeats. A **non-interactive** run
   with `-SkipSslVerify` hits `Read-Host "Verify SSL certificate? [Y/n]"`,
   and cert verification stays ON. That is the exact scenario the flag
   exists for.

**Provenance:** pre-existing (line 105 and the 2842 guard are unchanged
context). Raised as BLOCKING rather than a follow-up because this PR is
*the* remediation for "install.ps1 is broken on Windows", it restructures
this exact code, and it ships a test asserting the correctness of a
helper that cannot be reached. That is the reports-green-while-broken
class.

**Smallest correct fix:** stop aliasing. Give the interactive-prompt
result its own name (e.g. `$script:SslPromptDeclined`), delete the line
105 clobber, and make the line-2842 block
`if ($script:SslPromptDeclined) { ... }`. Then `-SkipSslVerify` reaches
`:154` and the prompt guard at `:411` behaves as its comment says.

**Note on what the change *did* fix here:** because both blocks were
dead, `SecurityProtocol = Tls12` was previously **never** executed on any
path. Hoisting it to top level (`:123-126`) is therefore a strictly
larger fix than #106 diagnosed, and is correct.

### B2. `install.ps1:678` (touched hunk) dot-accesses `operationSummaries` under `Set-StrictMode -Version Latest`; the new test's coverage of that input is an artifact of the stub

**Authority:** `guide_powershell.md` "StrictMode + PSCustomObject"; the
never-raise contract stated in `install.py:_bounded_names` /
`_extract_dashboard_names` docstrings ("every caller runs AFTER content
has been imported, so an escaping exception leaves a partial install").

```powershell
# install.ps1:84
$ErrorActionPreference = 'Stop'
...
# install.ps1:678, immediately above the line this diff rewrote
if ($s.operationSummaries) {
    foreach ($os in $s.operationSummaries) {
        $osState  = if ($os.state)   { $os.state }        else { "" }
        $osFailed = if ($os.failed)  { [int]$os.failed }  else { 0 }
        $osSkipped= if ($os.skipped) { [int]$os.skipped } else { 0 }
```

Verified under pwsh 7.5.1 with StrictMode Latest:

```
$s = '{"state":"FINISHED","endTime":5}' | ConvertFrom-Json
if ($s.operationSummaries) { }
-> THREW: PropertyNotFoundException: The property 'operationSummaries'
   cannot be found on this object.
```

With `$ErrorActionPreference='Stop'` and no enclosing `try`, this aborts
the installer **after the content has already been imported**: a partial
install with a raw PowerShell stack trace. Same class for `$os.state`,
`$os.failed`, `$os.skipped`, `$os.imported`, `$s.endTime`.

This is an **internal contradiction inside the diff**: the new
`Get-AllSkippedSummaries` (`:1400-1421`) probes the *same* fields on the
*same* objects with StrictMode-safe `PSObject.Properties[...]` and a
`try/catch`, explicitly because they may be absent — while the unguarded
dot-access three lines earlier runs **first** and would throw before the
hardened helper is ever reached.

The Python sibling cannot throw here:
`(result or {}).get("operationSummaries") or []` (`install.py:1400`).

**Why the tests do not catch it:** `install_ps1_advisory_harness.ps1:153`
feeds `'{"state":"FINISHED"}'` (no `operationSummaries`) into
`Install-Dashboard` and asserts the clean-install path — but line 52 of
the harness **stubs out `Import-ContentZip` entirely**, so `:678` never
runs. The assertion "response without operationSummaries takes the
clean-install path" is true of the stub and false of the shipped code.

**Smallest correct fix:**

```powershell
$sumProp = $s.PSObject.Properties["operationSummaries"]
if ($sumProp -and $sumProp.Value) {
    foreach ($os in @($sumProp.Value)) { ... }
}
```
and the same probe pattern for `state` / `failed` / `skipped` / `imported`
inside the loop (or wrap the whole summary block in `try { } catch { }`,
matching the never-raise contract the Python side documents).

---

## WARNING

### W1. `guide_powershell.md` and `install.ps1:122` both state the `-bor` rationale inaccurately

Both say: *"`-bor`, not `=`: a machine already permitting TLS 1.3 keeps
it."* On the dominant .NET Framework 4.7+ case the current value is
`SystemDefault` (`0`), and `0 -bor Tls12 == Tls12` — TLS 1.3 is **not**
kept; it is given up. The doc as written tells the next maintainer there
is no tradeoff, which is precisely the opposite of the tradeoff the
author consciously accepted.

**Fix:** state the real behavior in both places, e.g. *"`-bor`, not `=`,
so an explicitly-configured protocol list is preserved. Note that where
the current value is `SystemDefault` (0), the result is TLS 1.2 only:
OS-negotiated TLS 1.3 is deliberately traded away — see the judgment
below."*

**On the judgment itself: the author's tradeoff is right. Do not make it
conditional.** Reasoning:

- **Blast radius is asymmetric.** Pinning wrongly costs, at worst, TLS
  1.3 -> TLS 1.2 for one short-lived installer process against one
  appliance. Skipping wrongly costs a hard connection failure — the
  exact reported bug.
- **`SecurityProtocol -eq 0` is not a reliable proxy for "OS negotiation
  is healthy."** A hardened or registry-configured machine
  (`SystemDefaultTlsVersions`, `SchUseStrongCrypto`, SCHANNEL policy)
  can sit at `SystemDefault` and still not offer TLS 1.2 to .NET. The
  conditional would silently skip exactly the population it must not.
- **The population that loses anything is near-empty.** `Tls13` was only
  added to `SecurityProtocolType` in .NET Framework 4.8, and Schannel
  client TLS 1.3 needs Windows 11 / Server 2022+. It also requires the
  VCF Ops appliance to offer TLS 1.3, which is unestablished here.
- **We cannot test the target platform.** With no 5.1 runner, the branch
  with the fewest untestable behaviors is the correct one.

So: accept the cost, fix the sentence that denies it exists.

### W2. No `content-packager` rebuild flagged

`src/vcfops_packaging/templates/install.ps1` is on CLAUDE.md's
"After tooling changes" list, so **all dist zips are stale**. Nothing in
the change or its result block flags the rebuild. Confirmed live:

```
$ python3 -m vcfops_packaging check-staleness "dist/bundles/storage-path-monitoring.zip"
STALE -- bundle template is 2026-08-21-1, current is 2026-08-21-2. ...  (exit 1)
```

Two zips (`storage-path-monitoring`, `vks-core-consumption-bundle`) carry
`2026-08-21-1`; one discrete zip carries `2026-04-18-1`. All must be
rebuilt before the PR ships.

*(The **version stamp** half of dimension 9 is correct — see
"Dimension 9" below. This is the artifact half.)*

### W3. Second, misleading version stamp inside the shipped script

`install.ps1:97-100`:

```powershell
# Template version stamp -- injected at build time by vcfops_packaging builder.
# Used by `python3 -m vcfops_packaging check-staleness <zip>` ...
$TEMPLATE_VERSION = "2026-04-18-1"
```

Both sentences are false. `builder.py:29` states *"Template stamping is
removed entirely, install.py and install.ps1 are"* copied verbatim
(`builder.py:623,737`), and `cmd_check_staleness` (`cli.py:503-550`)
reads `vcfops_manifest.json`, never this variable. So a reader
diagnosing a staleness problem finds a stamp four months out of date
sitting in the shipped script, claiming to be the thing
`check-staleness` compares. This is exactly the "signal about the
artifact" surface dimension 9 exists to protect.

**Fix:** delete `$TEMPLATE_VERSION` and its comment, or correct the
comment to say it is inert and point at
`vcfops_manifest.json` / `template_version.py`.

### W4. Remaining install.py/install.ps1 parity gap: SUPER_METRICS all-skipped auto-reimport

`install.py:1508-1530` (`_install_supermetrics`) detects the all-skipped
SM signal and **retries the import once** to re-register the ghost-state
SM. This is a documented factory behavior
(`knowledge/context/wire-formats/wire_formats.md`, "ghost state ... Both
`src/vcfops_supermetrics/client.py:import_supermetrics_bundle` and
`install.py:_install_supermetrics` detect the all-skipped signal and
retry automatically").

`install.ps1:Install-Supermetrics` has no such retry, and this diff
discards the newly-available status object at `:1933`
(`$null = Import-ContentZip ...`). The change made the fix one line
cheaper and did not take it.

Out of #104's stated scope (DASHBOARDS/VIEW_DEFINITIONS), so not
blocking — but it is the same drift class #104 was filed about, in the
same file, discovered while the file was open. **File a follow-up issue**
rather than letting it be re-found later.

---

## NIT

### N1. Harness restates the bounds instead of extracting them

`install_ps1_advisory_harness.ps1:40-41` hardcodes
`$script:AdvisoryNameMaxChars = 120` / `$script:AdvisoryNamesMax = 20`
because the AST walk only extracts `FunctionDefinitionAst` nodes and the
bounds are script-scope assignments. If the template's bounds changed,
the harness would still inject 120/20 and the "clipped to 120 chars"
assertion would pass against divergent shipped code.

Largely mitigated by `test_bounding_constants_match_python`, which pins
both templates' literals — good defensive design, and the reason this is
a NIT and not a WARNING. Extracting the `AssignmentStatementAst` nodes
whose text starts `$script:AdvisoryName` closes the seam entirely
(demonstrated working during this review).

**On the harness overall: it is the right design.** It loads the
functions *verbatim from the shipped template* via
`Parser::ParseFile` + `Invoke-Expression $f.Extent.Text`, so it cannot
drift from the code the way a retyped copy would; it fails loudly if a
named function disappears (`:35-37`); and it asserts the PowerShell-
specific traps (single-element unwrap, `[object[]]` binding of
`List.ToArray()`, StrictMode-safe probes) that a Python-side test
structurally cannot reach. Keep it. Its one real limitation is B2's:
stubbing a collaborator hides defects inside that collaborator, so
assertions about inputs that only the *unstubbed* code touches must not
be read as coverage.

### N2. `RULE-018` / `knowledge/rules/posix-only.md` does not exist in this tree

Cited in the brief and in
`tests/test_install_ps1_tls_and_advisories.py:4-5` ("RULE-018 carves out
shipped artifacts"). `knowledge/rules/` contains 17 files; none is
`posix-only.md`, and `RULE-018` appears nowhere under `knowledge/rules/`.
Either the rule lands in a parallel change (then ordering matters, and
the PR should say so) or the docstring is a dead reference. The
substantive point — install.ps1 ships to customers, so Windows
correctness is in scope — stands on its own and is not in question.

### N3. Cosmetic divergence for a non-list `dashboards` value

`{"dashboards": "oops"}`:
- Python `_extract_dashboard_names` -> `[]` -> advisory reads
  `NOT updated: dashboard.`
- PowerShell `Get-DashboardAdvisoryNames` -> `@("?")` -> advisory reads
  `NOT updated: ?.`

Both are safe (no per-character iteration; `@("oops")` wraps, it does not
split) and both are unreachable with factory-rendered input. Harness line
94 asserts the PS behavior deliberately. Flagged only so the "mirrors it
line for line" claim in `wire_formats.md` is not read as exact.

### N4. `test_no_ps7_only_operators` strips at the first `#`

`tests/test_install_ps1_tls_and_advisories.py:166` does
`line.split("#", 1)[0]`, which truncates at a `#` inside a string
literal and would blind the check on that line. It also does not scan
for the ternary `? :` form. Both hold today (verified independently:
zero ternaries, zero PS7-only operators, whole-file) — this is about the
guard's future strength, not current state.

---

## Dimension walk

| # | Dimension | Result |
|---|---|---|
| 1 | Global-default / pak-specific leak (`00d3382`) | **n/a / clean.** No renderer, no pak-specific default, no coordinate convention touched. The one new global default (TLS 1.2 at `:123`) is deliberately global and correct. |
| 2 | Key / label derivation collision (`6c59f6b`) | **n/a / clean.** No key derivation. Name extraction is display-only and never feeds an identifier. |
| 3 | Wire-format conformance | **Clean.** `wire_formats.md` "three paths" -> "four paths" is accurate: the four bullets (`cli.py:cmd_sync`, `handler.py`, `install.py`, `install.ps1`) all exist and all filter per content type as described. The `install.ps1` bullet's claims (helper names, 120/20 bounds, non-fatal `$Ctx.Advisories`) were each verified against the code. Final-line wording change is a doc catch-up to code already shipped in `install.py`. |
| 4 | Loader / validator correctness | **n/a.** No loader, no UUIDs, no prefixes. Validate chain re-run green regardless. |
| 5 | Render regression vs known-good | **n/a** (renderer untouched); extractor output against real rendered artifacts is byte-identical across both installers. |
| 6 | Builder / pak structure | **n/a.** `builder.py` / `discrete_builder.py` unchanged; they copy the template verbatim. No `pak-compare` surface. |
| 7 | Corpus regression | **Clean.** All seven `validate` commands exit 0; 932 passed / 4 skipped. |
| 8 | Silent capability change / downgrade | **B1** is a silent capability loss on `-SkipSslVerify` (pre-existing, surfaced here). The mid-stream WARN narrowing at `:683` is a deliberate, documented reduction in *noise* with the signal relocated to a louder, named, per-type advisory — a net upgrade, correctly reasoned in-comment. |
| 9 | Stale-zip discipline **and the signal** | **Stamp: correct and sufficient.** `2026-08-21-1` was committed today in `a35db82` (#103), so `-2` is the right next increment on the documented `YYYY-MM-DD-N` scheme; `template_version.py`'s docstring already lists `templates/install.ps1` as a bump trigger; both builders write it into `vcfops_manifest.json`; `check-staleness` confirmed live to flip the two current bundle zips to STALE (exit 1). **Artifact: not flagged — W2.** **Signal hygiene: W3** (a second, false, four-month-stale stamp inside the shipped script). |
| 10 | Test coverage of the change | **Good, with one hole.** 15 new tests: static shape pins for the TLS gate (assigned once, `-bor` not `=`, indentation depth, ordering vs the bypass branch, `TrustAllCertsVcf2` gone, both helper guards present), advisory-shape pins, a Python/PowerShell bounds-parity assertion, and ASCII / PS7-syntax hygiene. Plus a behavior harness that runs the shipped functions verbatim. Hole: **B2** — the one assertion covering a missing `operationSummaries` passes only because the collaborator that would crash is stubbed. |

## Cert-bypass consolidation: the specific questions asked

- **Does `if (-not ('TrustAllCertsVcf' -as [type]))` genuinely handle
  the "`Add-Type` cannot redefine a type" constraint?** Yes. `-as [type]`
  returns `$null` for an unloaded type name, so the first call compiles
  and later calls skip compilation while still re-applying
  `[ServicePointManager]::CertificatePolicy`. This is a strictly better
  construction than the `TrustAllCertsVcf` / `TrustAllCertsVcf2` pair it
  replaces, and `guide_powershell.md` now records the rule.
- **Is the early `Major -ge 6` return correct?** Yes.
  `ICertificatePolicy` does not exist on .NET Core, so the `Add-Type`
  body must never compile there; PS 7+ call sites use
  `-SkipCertificateCheck` / the handler callback instead.
- **Are the two former call sites mutually exclusive?** *They are worse
  than mutually exclusive — both are unreachable.* See **B1**. The
  `-not $SkipSslVerify` term at `:2842` was written to make them
  exclusive, but because it tests the same variable that `:414` sets, it
  is `X -and -not X`.

## Internal contract changes: output-stream audit

- **`Import-ContentZip` now returns `$s`.** Three call sites, all
  correct: `:1933` `$null =`, `:1953` `$importResult =`, `:2189`
  `$null =`. No other call sites exist (grep confirmed). Nothing else in
  `Import-ContentZip` emits to the success stream: `Add-Type
  -AssemblyName` is silent, every `.Add(...)` / `.Dispose(...)` /
  `LoadXml` returns `void`, `Write-Host` goes to the information stream,
  `Invoke-Api` results are assigned. This matters because
  `Invoke-InstallBundle:2535` calls `& $entry.InstallFn $ctx`
  **uncaptured**, so any stray output would have been flattened into
  `return $warnings` and printed as a phantom warning (and, via
  `$allWarnings.Count`, changed the exit code to 2). Correctly avoided.
- **`Invoke-InstallBundle` drains into `$GlobalCtx.Advisories`.** Correct.
  `List[T].Add` returns `void`, so nothing leaks into the return value;
  the `$null -ne $GlobalCtx.Advisories` guard (rather than truthiness) is
  right, since an empty collection is falsy in PowerShell and would have
  dropped the first bundle's advisories. The uninstall context
  (`:2557-2563`) has no `Advisories` key, which is safe: no uninstall
  function touches it, and hashtable key misses do not throw under
  StrictMode.
- **Return-shape unwrap.** Every name helper uses the comma-wrap idiom
  (`return ,$array`) and every caller assigns directly, never
  `@(Get-...)`. Verified by the harness (`single element stays an array
  of 1`) and by my own run against real content. The calling convention
  is documented in-file at `:1305-1313`, which is the right place for it.
- **Advisories never reach the exit code.** `Write-Warn` is
  `Write-Host` only (`:171-173`); `Install-Dashboard` contains zero
  `$Ctx.Warnings.Add`; pinned by
  `test_advisories_never_reach_the_warnings_list`. Confirmed.

## Verification ceiling

**Windows PowerShell 5.1 cannot be executed on this machine or on any
POSIX runner** — it is .NET Framework and Windows-only. Everything above
was verified under **pwsh 7.5.1** or by static analysis of the file
bytes. Per `guide_powershell.md`, "QA passing on pwsh 7 does NOT
guarantee 5.1 compat."

Statically confirmed by me, independently of the author's claims: zero
non-ASCII bytes file-wide; zero `??` / `?.` / `&&` / `||` / ternary; no
continuation literal starting with `&`; StrictMode-safe `PSObject`
probes in all **new** helpers (but see **B2** for the un-probed
pre-existing line in the same execution path); `[object[]]`-typed params
accepting `List.ToArray()`; clean AST parse.

**Still requires a Windows runner to prove:**

1. That `Add-Type` compiling `ICertificatePolicy` against .NET Framework
   actually succeeds in-session (only reachable at all once **B1** is
   fixed).
2. That `[System.Net.ServicePointManager]::SecurityProtocol -bor Tls12`
   produces a working handshake against a real VCF Ops appliance from
   .NET Framework — including that `HttpClient` on 4.x honors
   `ServicePointManager` as `install.ps1:621-622` asserts.
3. That the 5.1 parser accepts the whole file (pwsh 7 accepts a superset
   of 5.1 grammar; the static scans cover the known divergences, not
   all of them).
4. That `Read-Host`, `Write-Host 6>&1`, and console encoding behave as
   assumed under Windows PowerShell.

Both #106's issue text and this review reach the same recommendation: a
`windows-latest` CI job exercising `install.ps1` under **both** Windows
PowerShell 5.1 and pwsh 7, plus PSScriptAnalyzer
`PSUseCompatibleSyntax` / `PSUseCompatibleCmdlets` targeting 5.1 (the
latter runs on the existing Linux runner). Until one of those exists,
every `install.ps1` change ships on static evidence alone.

## `guide_powershell.md:19` correction (Scott's)

**Correct, and it was necessary.** The guide previously recommended
`$obj.PSObject.Properties[$key]?.Value` six lines after declaring 5.1
compatibility non-negotiable. `?.` is PowerShell 7 only and is a **parse
error** on 5.1 — not a runtime failure but a whole-file refusal to load,
so an agent following the guide would have produced an installer that
does not start on the platform the guide exists to protect. The
replacement (explicit `$prop = ...; if ($prop) {...}`) is the correct
5.1-safe idiom and is exactly what the new helpers use. Independently
confirmed: `?.` appears nowhere in `install.ps1`, and `?.Value` appears
nowhere in the file at all.

## If shipped as-is

A Windows operator on PowerShell 5.1 gets the #106 fix and the #104
advisory parity — real, verified improvements. But: `-SkipSslVerify` and
`VCFOPS_VERIFY_SSL=false` remain silently ignored, so a scripted
non-interactive install against a self-signed appliance blocks on an
unanswerable `Verify SSL certificate? [Y/n]` prompt or fails the
handshake (B1); and any import whose status response omits
`operationSummaries` aborts the installer with a raw
`PropertyNotFoundException` **after** content has landed, leaving a
partial install that the new advisory machinery was written to prevent
and that the new test suite reports as covered (B2). Downstream, every
distributed bundle zip still carries the old `install.ps1` until
`content-packager` rebuilds (W2) — though `check-staleness` now
correctly says so, which is the version bump working as designed.
