# Framework review (ROUND 3): install.ps1 TLS gate + advisory parity (#106, #104)

- **Branch:** `fix-install-ps1-parity` (uncommitted working tree)
- **Date:** 2026-08-21
- **Prior rounds:** `...-2026-08-21.md` (R1, 2 BLOCKING),
  `...-2026-08-21-round2.md` (R2, 1 BLOCKING)
- **Verdict:** **APPROVE** (0 BLOCKING / 0 WARNING / 3 NIT)

Narrow confirmation pass. Round 2's BLOCKING is resolved and, more
importantly, is now covered by a test that I proved would have caught it.
Nothing previously cleared was re-opened.

## Checks re-run independently

| Check | Result |
|---|---|
| `vcfops_* validate` chain (all 7) | **pass**, exit 0 each |
| `python3 -m pytest -q` | **939 passed, 4 skipped**, 178 deselected |
| `pytest tests/test_install_ps1_tls_and_advisories.py` | 22 passed |
| `pwsh` AST parse, `install.ps1` + harness | **PARSE CLEAN**, both |
| Harness against shipped template | ALL ASSERTIONS PASSED, **46** (see N3) |
| **Mutation test: harness vs. the reintroduced regression** | **FAILS correctly**, exit 1 |
| Mid-stream WARN, PS vs PY, 9 envelopes | **8/9 byte-identical** (see N1) |
| SSL reachability probe (A/B/C/D), re-run on round-3 file | 0 / 1 / 1 / 0 - unchanged, correct |
| Path audit (all touched + new files) | clean |
| `CURRENT_TEMPLATE_VERSION` | `2026-08-21-2` - **not** re-bumped, correct |

## Round 2 BLOCKING - RESOLVED

`install.ps1:670` now reads:

```powershell
if (($osState -ne "FINISHED" -and $osState -ne "") -or $osFailed -gt 0 -or $osSkipped -gt 0) {
```
matching `install.py:454`:
```python
if os_state not in ("FINISHED", "") or os_failed > 0 or os_skipped > 0:
```

**Equivalence verified by differential execution, not by reading.** I drove
the real `Write-ImportSummaryWarnings` (AST-extracted from the shipped
template, under `StrictMode Latest` + `$ErrorActionPreference='Stop'`) and
`install.py:448-459`'s verbatim condition over nine envelopes:

```
                          PS                  PY
SM all-skipped 0/4        WARN ...            WARN ...        identical
REPORTS all-skipped 0/2   WARN ...            WARN ...        identical
re-sync 1/1               WARN ...            WARN ...        identical
clean 2/0                 SILENT              SILENT          identical
failed 0/0/1              WARN ...            WARN ...        identical
odd state PARTIAL         WARN ...            WARN ...        identical
empty state string        SILENT              SILENT          identical
fields absent entirely    SILENT              SILENT          identical
null counts / state:null  SILENT              WARN state=None   <- N1
```

The regression envelope from round 2 (`SUPER_METRICS imported=0 skipped=4`)
now warns on both installers, with byte-identical text.

**tooling's structural point is correct.** `_all_skipped_summaries` /
`Get-AllSkippedSummaries` is a second, narrower layer scoped to
`_install_dashboards` / `Install-Dashboard` and filtered to
`DASHBOARDS` / `VIEW_DEFINITIONS`. Round 1's error was exactly as described:
applying that layer's precision to the mid-stream line, which has no such
content-type scope. Confirmed by reading both call graphs.

## The new test coverage - verified it would actually have caught this

This is the claim that mattered most, so I did not take it on faith. I wrote
a **mutant** copy of the shipped template with the condition narrowed back to
the exact regression (`-or $osSkipped -gt 0` deleted, single occurrence,
asserted) and ran the unmodified harness against it:

```
  pass: status envelope without operationSummaries: no output, no throw
  pass: null status tolerated
  pass: summary missing state/failed/skipped/imported: no throw
Exception: install_ps1_advisory_harness.ps1:70
  FAIL: failures and skips warn; a clean type stays quiet
mutant harness exit=1
```

It fails on the rebalanced mixed case, before it even reaches the
SUPER_METRICS guard. **The regression cannot be reintroduced silently.**

The new cases are real-function cases, not stub cases: `Write-ImportSummaryWarnings`
is loaded verbatim by AST (`harness:24-35`) and invoked directly with
`6>&1` capture (`:117-125`). Specifically confirmed present:
`SUPER_METRICS imported=0 skipped=4` asserting one line naming type and both
counts; `REPORTS imported=0 skipped=2`; and the mixed case asserting
`VIEW_DEFINITIONS imported=2 skipped=0` produces no line **and** appears
nowhere in the output (`:104`, the `-notlike "*VIEW_DEFINITIONS*"` form,
which is stronger than a count assertion).

`test_mid_stream_summary_warn_matches_install_py`
(`tests/test_install_ps1_tls_and_advisories.py:138-156`) pins the literal in
**both** templates, so narrowing either one alone fails the suite. That is
the right shape: the defect was drift, so the guard is a parity pin, not a
single-file pin.

## Follow-ups - verified

- **`Get-AllSkippedSummaries` converted to `Get-PropValue`** (`:1502-1512`).
  Behaviour-equivalent to the prior probe form: `imported: 0` still yields
  `0`, `imported: null` still yields `0`, a non-numeric count still lands in
  the `catch` and `continue`s, and the `contentType` fallback to `"?"` still
  matches Python's `entry.get("contentType") or "?"`. Confirmed by reading
  both; the harness's `imported=1/skipped=1 is NOT flagged` case still passes.
- **Guide.** `guide_powershell.md`'s StrictMode section now carries both
  measured facts (hashtables throw too; `PSObject.Properties[...]` returns
  `$null` on a hashtable). Round 2 N2 resolved.

### Spot-check of the nine remaining `PSObject.Properties` sites

**None of the eight can receive an `Invoke-Api` result.** But the
classification is off for two of them, so record it accurately:

- Genuinely local bundle/manifest JSON, as described: `:410`, `:424`
  (`$Bundle.Manifest.content`), `:1424`, `:1434`, `:1437` (rendered
  `dashboard.json`), `:2015`, `:2181`, `:2227` (`$Ctx.Manifest.content`).
- `:213` inside `Get-PropValue` itself, as described.
- **`:1809` (`$raw`) and `:1749`/`:1752` (`$grouped`) are not local JSON** -
  they are `$result[0].result` from the **live UI-API RPC** path. They still
  cannot receive an `Invoke-Api` hashtable: that path goes through
  `Invoke-DashboardAction` / siblings, which use `Invoke-WebRequest` +
  `ConvertFrom-Json` (`:1678-1679`) and never touch `Invoke-Api`'s catch
  block. Both sites also use the safe forms anyway (indexed probe returns
  `$null` for a missing key on a PSCustomObject; the enumerating form is
  guarded by `-is [PSCustomObject]`).

So the safety conclusion holds; only the provenance label was wrong. No
finding.

---

## NIT

### N1. Pre-existing, unchanged PS/PY divergence on `"state": null`

The one envelope of nine that differs: `{"state": null, ...}` with all-zero
counts. Python's `os_entry.get("state", "")` returns `None` (the default only
fires when the key is **absent**), so `None not in ("FINISHED","")` is true
and it prints `state=None`. PowerShell coerces `$null` to `""` and stays
silent.

Not introduced here - `main`'s PowerShell did the same - and PowerShell's
behaviour is the more sensible of the two (`state=None` is a Python artifact,
not a signal). If `state` is null **and** anything is skipped or failed, both
warn. Left as a note so the "character-equivalent" claim is not read as
"identical on every input"; the fix, if wanted, belongs on the Python side.

### N2. `Get-AllSkippedSummaries` no longer double-guards non-numeric counts

The conversion replaced `if ($impProp -and $null -ne $impProp.Value)` with
`if ($null -ne $impRaw)`. Equivalent in every case I could construct, and the
`try`/`catch` still absorbs a non-numeric cast. Purely an observation that the
change is behaviour-preserving, recorded because it was not in the brief.

### N3. Harness assertion count is 46, not 47

`grep -c '^Assert '` gives 46 call sites; the run emits 46 `pass:` lines.
Cosmetic, but the result block should say 46 so the number stays a
verification handle rather than a decoration.

---

## Dimension walk (delta only)

| # | Dimension | Result |
|---|---|---|
| 3 | Wire-format conformance | **Clean.** `wire_formats.md`'s "mirrors it line for line" claim is now true of the mid-stream line as well; the only carved-out non-parity (SUPER_METRICS retry, #108) remains accurately documented. |
| 7 | Corpus regression | **Clean.** 7/7 validate exit 0; 939 passed / 4 skipped. |
| 8 | Silent capability change / downgrade | **Clean.** The signal removed in round 2 is restored and identical across both installers. No content type is left without a no-op signal. |
| 9 | Stale-zip discipline and the signal | **Stamp correct**, `2026-08-21-2`, not re-bumped (correct: the same PR, already-bumped). Artifact rebuild + RULE-018/#107 tracked by the coordinator; not gating. |
| 10 | Test coverage of the change | **Now the strongest part.** The gap named in round 2 ("nothing pins the mid-stream condition against install.py's") is closed by a both-template parity pin, and the behaviour cases are mutation-proven to catch the exact regression. |

---

## Judgment asked: is shipping noisier-but-identical right?

**Yes. Agree with tooling. It should not block, and it does not make this PR
worse for the common case.**

1. **It is not a regression for the common case - it is the status quo.**
   `install.py` has always warned on `imported=1 skipped=1`, and so did
   `install.ps1` on `main`. This PR does not add noise; it declines to remove
   noise from one template only. The common case is exactly as loud today as
   it was before the branch.

2. **The objection in #104 point 1 targets a different layer.** The complaint
   was "a no-op import reports as success." That is the advisory layer, and it
   is correctly narrow (`imported == 0 and skipped > 0`) in both installers
   now. The mid-stream line is a factual per-type accounting line, not a false
   alarm - `skipped=1` on a re-sync is true.

3. **The asymmetry runs the right way.** A spurious WARN costs an operator a
   second of reading. A missing WARN cost them, as we measured two rounds ago,
   a silent no-op supermetric install with `OK  Imported 4 super metric(s)` as
   the last line. Noise is recoverable; silence is not.

4. **Parity is the harder invariant to hold, so hold it.** Two installers
   sharing a condition can be narrowed together in one commit later. Two
   installers with different conditions drift permanently - which is the
   defect class #104 exists to close and the class that produced the round-2
   finding.

**One condition on the follow-up, which I would put in the issue text:**
narrowing the mid-stream line to `imported == 0 and skipped > 0` in both
templates is only safe **after** the named advisory covers `SUPER_METRICS`
and `REPORTS`. Doing the narrowing first - even in both templates - re-opens
the exact hole round 2 caught, just symmetrically. Sequence it: extend the
advisory, then quiet the line.

## Verification ceiling (unchanged)

Windows PowerShell 5.1 still cannot be executed here. Everything above is
pwsh 7.5.1 plus static analysis. The `windows-latest` CI job (5.1 + pwsh 7,
plus PSScriptAnalyzer `PSUseCompatibleSyntax`/`PSUseCompatibleCmdlets`
targeting 5.1 on the existing Linux runner) remains the right structural fix
and remains absent.

## If shipped as-is

A Windows operator gets working TLS 1.2, an honored `-SkipSslVerify`, a
no-op dashboard or view import named rather than reported as clean, and the
same per-content-type accounting lines their Linux colleague sees for the
same bundle. The two installers no longer disagree about what an import did.
