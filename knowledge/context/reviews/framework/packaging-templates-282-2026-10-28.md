# Framework review: installer alert subType default (issue #282)

- Date: 2026-10-28
- Branch: `install-subtype-default` (uncommitted)
- Reviewer: framework-reviewer
- Scope (only these): `src/vcfcf_packaging/templates/install.py`,
  `src/vcfcf_packaging/templates/install.ps1`,
  `src/vcfcf_core/packaging/template_version.py`,
  `tests/test_install_alert_subtype.py`,
  `tests/fixtures/install_ps1_alert_subtype_harness.ps1`, the paragraph added
  to `knowledge/context/wire-formats/alertdef_symptomset_import.md`.
- Verdict: **CHANGES REQUESTED** (1 BLOCKING / 1 WARNING / 2 NIT)

## Change

Both shipped installers stop falling back to alert `subType` 3 (outside the
18-22 enum). Absent or null now posts 19; anything outside 18-22 raises in the
conversion step and the alert is skipped with a WARN. `install.ps1`
`Install-Alerts` gains a try/catch around `ConvertTo-AlertWire` so that throw
becomes a per-alert skip. Template version bumped `2026-10-26-1` to
`2026-10-28-1` with a history line.

## Checks re-run

| Check | Result |
|---|---|
| `tests/test_install_alert_subtype.py`, `VCFCF_REQUIRE_PWSH=1`, pwsh 7.5.1 Linux | 25 passed, PS tests ran (not skipped) |
| Full suite (default addopts) | 3107 passed, 5 skipped, 131 deselected |
| Seven-package validate chain | all exit 0 |
| Mutation test of the guard (scratch copy) | 8 of 9 mutants killed; the survivor is equivalent (see below) |
| Windows PowerShell 5.1 | **not run anywhere**: no Windows host here, and CI does not run this file (B1) |
| Render regression / pak-compare | n/a (no renderer or builder change) |

Mutants: py default back to 3, py accept any int, py old `get("sub_type", 3)`
restored, ps default 3, ps accept double/decimal, ps try/catch removed, ps
`subType` not wired to the helper, ps range widened to 23: all KILLED. "ps accept
bool" SURVIVED, but it is equivalent: `[long]$true` is 1, which the range check
rejects anyway.

## Do they match the loader?

Yes, on every value the installers can actually receive.

- Default: `vcfcf_core.alerts.loader._sub_type` returns 19 for None; the
  dataclass default is 19. `install.py` `_alert_sub_type` and `install.ps1`
  `Get-AlertSubType` both return 19 for absent or null, and only then.
- Integer strings: `install.py` uses the loader's exact expression
  (`raw.strip().lstrip("-").isdigit()` then `int(...)`). `install.ps1` uses
  `^-?[0-9]+$` after `Trim()`. Same verdict for every ASCII case in the
  20-case table (N1 covers the non-ASCII edge).
- Enum: `install.py` `_ALERT_SUBTYPES` equals `VALID_SUBTYPES` (pinned by
  `test_install_py_enum_matches_loader`); `install.ps1` checks the contiguous
  range 18-22, and the test fails if the loader's enum ever stops being
  contiguous. Bool, float, 0, negatives, text, empty string all rejected on
  both sides, matching `AlertDef.validate`.
- Reachability: `assembly.py` `_render_alerts_payload` writes `sub_type` from a
  validated `AlertDef`, so factory-built zips always carry an int in 18-22.
  Both new branches (default and reject) are defense for hand-edited or
  older-assembled payloads, as #282 says. No change to the import-zip path or
  to any emitted wire key beyond the `subType` value.

Wire-format authority: `knowledge/context/wire-formats/alertdef_symptomset_import.md`
section "Alert subType enum". The added paragraph there is accurate.

## Is the new catch in Install-Alerts safe?

Mostly, and it is the right direction, with one masked parity gap (W1).

Safe because:
- `install.py` already wrapped `_alert_to_wire` in `except Exception` and
  skipped with a warning before this change (pre-existing, not in the diff).
  The ps1 catch brings the two installers to the same contract.
- `ConvertTo-AlertWire` makes no REST calls. Every `Invoke-Api` and
  `Assert-LookupOk` in `Install-Alerts` is outside the try, so network, auth,
  and lookup failures still abort as before. The catch cannot hide a server
  failure.
- The warning is added to `$Ctx.Warnings`, which drives exit 2. A skipped alert
  is a loud non-zero exit, not a silent success.
- Before the change, any throw here aborted the installer mid-run after
  earlier content types had already landed, which is the partial-install
  failure `Get-PropValue`'s own comment exists to prevent.

What it hides: see W1. Under `Set-StrictMode -Version Latest`,
`ConvertTo-AlertWire` reads `$s.threshold_type` and `$s.threshold_value`
directly. Probed with pwsh against the real function:
a `defined_on: CHILD` set with no `threshold_type` throws
`PropertyNotFoundException`. The loader accepts that shape (`_validate_set`
only checks `threshold_type` when present). So valid content that
`install.py` installs gets skipped by `install.ps1`, now as a WARN instead of a
crash. None of the 9 corpus alerts under `content/` and `third_party/` hit it.

## Windows PowerShell 5.1

Read-through finds nothing 7-only in the new code: `-is [string]`, `-is [int]`,
`-is [long]`, `-match`, `[long]` and `[int]` casts, `throw "..."`, try/catch
with `continue` in a `foreach` are all 3.0-era. On 5.1, `ConvertFrom-Json`
yields Int32 for small integers (accepted), Decimal for `19.0` (rejected),
Boolean for `true` (rejected), which matches the 7 results. The harness also
looks 5.1-safe (`6>$null`, `[ordered]`, BOM from `Set-Content -Encoding UTF8`
read back as `utf-8-sig`).

That is a reading, not proof, and the harness's own header says so. B1 is the
gap.

## Is the test a real regression guard?

On the Python side, yes: it compares each installer against the loader's own
`_sub_type` plus `AlertDef.validate`, not against hard-coded expectations, so
a loader change moves the test. It exercises `_install_alerts` end to end with
a fake client (skip one, post the rest, one warning, WARN printed). The
mutants confirm it.

On the PowerShell side the harness pulls the real functions out of the
template by AST, so it tests shipped code, not a copy. It is a real guard
**where it runs**. It runs nowhere in CI (B1).

## Findings

### BLOCKING

**B1. The install.ps1 half of the guard runs in no CI job, so the new PS code
is unproven on Windows PowerShell 5.1.**
Authority: `knowledge/rules/posix-only.md` (RULE-018 carve-out: shipped
installers must work on native Windows); the harness header ("only a
windows-latest runner can prove that").
`.github/workflows/ci.yml` job `installer-ps` (line 222) runs an explicit
file list: `tests/test_install_ps1_materialization.py
tests/test_install_ps1_tls_and_advisories.py`. The new
`tests/test_install_alert_subtype.py` is not on it, and the lab-pool `test`
job has no PowerShell, so it skips `test_install_ps1_agrees_with_loader`.
Net: nothing ever runs the new `Get-AlertSubType` or the new catch on 5.1, or
on any PowerShell in CI.
Fix: add `tests/test_install_alert_subtype.py` to the `installer-ps` run line.
`.github/` is outside `tooling`'s write scope, so the orchestrator makes the
one-line edit in the same PR, and the PR waits for the three `installer-ps`
legs to go green.

### WARNING

**W1. The new catch turns a StrictMode crash on loader-valid alerts into a
Windows-only skip, a parity divergence with install.py.**
`install.ps1` `ConvertTo-AlertWire`, the `$s.threshold_type` and
`$s.threshold_value` reads (the `if ($definedOn -ne "SELF" -and $s.threshold_type)`
block). Authority: `vcfcf_core.alerts.loader._validate_set` (threshold fields
optional) and `_set_to_wire` (uses `.get`); the `Get-PropValue`
contract in the same template.
A non-SELF set without `threshold_type`, or with `threshold_type` but no
`threshold_value`, validates and installs via `install.py`, but `install.ps1`
throws `PropertyNotFoundException` and now skips the alert. Pre-existing bug,
but it sits in the function this change edits and the new catch is what makes
it quiet.
Fix: read those two through `Get-PropValue` and add one harness case (CHILD set
without `threshold_type`) asserting the alert posts with no `aggregation`.

### NIT

**N1. Non-ASCII digit strings diverge.** `install.py` and the loader accept
`"١٩"` (Python `isdigit` plus `int` give 19); `install.ps1`'s `[0-9]` rejects it.
Unreachable from factory-built zips (assembly writes the int). Either match it
or add one line in the `Get-AlertSubType` comment saying ASCII only on purpose.

**N2. The docs undersell the ps1 behaviour change.** The version-history line
and the wire-format paragraph describe the out-of-enum skip, but not that
`install.ps1` now skips on any `ConvertTo-AlertWire` error instead of aborting
(matching `install.py`). Add half a sentence to the history line. Cosmetic in
the same area: an over-Int64 numeric string fails the `[long]` cast with
"Cannot convert value ... Int64" rather than the enum message. It is still
skipped and warned.

## Stale-zip discipline (dimension 9)

Templates touched, so every distribution zip is stale.
`CURRENT_TEMPLATE_VERSION` is bumped to `2026-10-28-1` with a history line, so
`check-staleness` will flag previously built bundles. Signal: correct. The
orchestrator still owes a full `content-packager` rebuild of every manifest in
`bundles/` after merge (CLAUDE.md, "After tooling changes"). I could not
confirm whether `tooling`'s result block flagged it.

## If shipped as-is

Factory-built zips behave identically (they already carry valid subtypes). A
hand-edited or malformed payload now gets 19 or a per-alert WARN and exit 2,
not a 3 or a crash. The risk is the Windows 5.1 path, which no automated run
has executed.
