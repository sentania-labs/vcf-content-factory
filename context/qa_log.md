# QA log

Chronological record of acceptance runs against live VCF Ops instances
and their outcomes. Not a replacement for CI — this is an audit trail
for "what was actually tested when" so future agents can tell whether
a given feature has been validated against a real server or only
exercised in isolation.

Entries are append-only in reverse-chronological order. Each entry
includes the date, instance, runtime under test, scope, and
pass/fail verdict with the commit hash the test was run against.

---

## 2026-04-11 — Python `install.py` acceptance (multi-bundle refactor)

**Instance:** `vcf-lab-operations.int.sentania.net` (VCF Ops 9.0.2)
**Runtime:** Python 3 + stdlib + `requests` (bootstrapped)
**Build under test:** commit `131f3ce` — "Fix view/report delete: correct
Ext.Direct data shape + add report uninstall"
**Scope:** 6 tests exercising the Python install path end-to-end:
install, uninstall, multi-bundle install, multi-bundle uninstall,
admin-guard enforcement, SM enable verification

**Result: 6/6 PASS**

- Test 1 — Single-bundle install (vks-core-consumption): PASS
  - 10 SMs + 1 view + 1 dashboard + 1 report imported
  - No enable-verify retries (all SMs enabled on first attempt)
  - DeprecationWarning noted on install.py:554 (ElementTree `or`
    pattern) — fixed in commit `674af29`
- Test 2 — Single-bundle uninstall (admin): PASS
  - Zero HTTP 500s on dashboard, report, or view delete operations
  - This was the first production exercise of the corrected
    `deleteView` and `deleteReportDefinitions` data shapes (see
    `dashboard_delete_api.md` §"2026-04-11 correction")
  - `_uninstall_reports` handler working correctly (new in this
    refactor)
- Test 3 — Multi-bundle install (vks-core-consumption + vm-performance):
  PASS
  - Both bundles extracted to same directory with no content file
    collisions (the whole point of the multi-bundle refactor)
  - Multi-select checklist pre-checked both bundles
  - Single auth prompt, per-bundle loop, sequential install under
    one token
  - 16 total VCF Content Factory SMs on instance post-install
- Test 4 — Multi-bundle uninstall (admin): PASS
  - Cross-bundle dependency order respected: dashboards → reports
    → views → SMs within each bundle
  - Zero HTTP 500s
  - Instance returned to clean baseline after run
- Test 5 — Admin-guard enforcement (non-admin uninstall attempt): PASS
  - Exit code 1 with clear admin-required error message
  - Guard fired too late (after credential prompt / TLS warning) —
    UX observation, reordered in commit `674af29`
- Test 6 — SM enable verification: PASS
  - All 10 SMs confirmed enabled in Default Policy XML via REST
  - Content-zip path preserved UUID stability (server-resolved IDs
    matched the UUIDs from YAML)
  - 16 total enabled SMs in the policy (10 new + 6 pre-existing)

**Lab state after run:** clean (zero `[VCF Content Factory]` content)

**Agent output file:** captured in session task transcript
`a3b7aef306bddde47` (task runner temp path)

**Non-blocking findings:** 3 (all rolled into commit `674af29`):
1. ElementTree `or` truth-test pattern — DeprecationWarning
2. Admin-guard UX ordering (fires after preamble output)
3. Dashboard `locked=False` observed on import, contradicting
   long-standing `locked=true` documentation — noted in
   `dashboard_delete_api.md`

---

## 2026-04-11 — PowerShell `install.ps1` acceptance (multi-bundle refactor)

**Instance:** `vcf-lab-operations.int.sentania.net` (VCF Ops 9.0.2)
**Runtime:** pwsh 7.5.1 on Linux (PS 5.1 compatibility guards present
but not exercised on this host)
**Build under test:** commit `7dc3acd` — "Auto-derive display name for
branded distribution zip filenames"
**Scope:** 6 tests mirroring the Python acceptance run against the
freshly-rebuilt branded zip (`[VCF Content Factory] VKS Core
Consumption.zip`), including branding verification of display-name
usage in user-facing output.

**Result: 0/6 PASS — 3 fails (root-caused), 3 dependent skips**

Overall FAIL: three PowerShell-specific language idioms blocked the
run before any API call was made. Python QA passing was not a
guarantee of PS parity because the bugs are in PS semantics that
don't exist in Python.

**Bugs identified** (all in `install.ps1`, none in `install.py`):

1. **PS-1 (single-bundle parameter binding crash):** `Get-Bundles`
   returns `[List[hashtable]]`; PS pipeline unwraps single-element
   results to bare `Hashtable`; `Select-Bundles` typed param can't
   coerce. Fires on every single-bundle install.
2. **PS-2 (StrictMode PSCustomObject missing-property access):**
   `$content.$ManifestKey` under `Set-StrictMode -Version Latest`
   throws when the key is absent, instead of returning `$null`.
   Fires on any bundle that doesn't include every content type
   (all four current bundles).
3. **PS-3 (single-item array function return unwrap):** functions
   returning `@("one-item")` are unwrapped to bare strings by the
   pipeline; callers' `.Count` calls then throw under StrictMode.
   Fires on any bundle with exactly 1 item of a given content type.

**What was NOT tested due to the early crashes:**
- The corrected `Delete-View` signature (uuid + name) against the
  live instance
- The new `Delete-Reports` bare-dict `reportDefIds` shape against
  the live instance
- Multi-bundle install/uninstall on PS
- Display-name fallback behavior in `Get-BundleDisplayName` beyond
  the happy path

**Branding verification** (partial, from the paths that got far
enough to render): PASS — "VKS Core Consumption" and "VM Performance"
appeared in multi-select checklist and selection summary. Display-
name fallback from manifest works correctly on the happy path.

**Lab state after run:** clean (all three failures crashed pre-auth,
no content touched)

**Agent output file:** session task transcript `a50a426cbba8da2fd`

**Follow-up:** tooling fix pass for the three bugs (see
`memory/feedback_powershell_idioms.md` for the patterns) followed by
a PS-focused re-run.

---
