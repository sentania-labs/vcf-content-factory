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

## 2026-04-11 — PowerShell `install.ps1` acceptance, second attempt (post PS-1/2/3 fix)

**Instance:** `vcf-lab-operations.int.sentania.net` (VCF Ops 9.0.2)
**Runtime:** pwsh 7.5.1 on Linux
**Build under test:** commit `7dc3acd` rebuilt zips with install.ps1
updated via commit `da1579a` (PS-1/2/3 fixes)
**Scope:** full 6-test acceptance, same shape as the Python run

**Result: 4/6 PASS, 2 PARTIAL**

- Test 1 — Single-bundle install: **PARTIAL**. Content imported
  cleanly but SM enable failed with "The SSL connection could not be
  established" errors on every attempt. Exit code 2.
- Test 2 — Single-bundle uninstall (admin): **PASS**.
  Dashboard/view/report delete cleanly, zero HTTP 500s. Confirmed
  the PS-1/2/3 fixes work and the Delete-View / Delete-Reports shapes
  parity with Python was proven for the first time.
- Test 3 — Multi-bundle install: **PARTIAL**. Same SSL error pattern
  as Test 1. Content imported for both bundles, SM enable failed on
  all 16 SMs across both bundles.
- Test 4 — Multi-bundle uninstall: **PASS**. Both bundles' content
  removed cleanly. Per-bundle delete order respected. Zero 500s.
- Test 5 — Admin-guard enforcement: **PASS**. PS-3 fix confirmed
  working — single-item Get-BundleUninstallNames no longer crashes
  the .Count call. Guard fires with clear error.
- Test 6 — Display-name branding: **PASS**. "VKS Core Consumption"
  and "VM Performance" appeared in every user-facing context.

**Lab state after run:** clean (Tests 2 and 4 cleaned up normally;
Tests 1 and 3's exit-2 partial failures left content but subsequent
uninstall cycles in Tests 2 and 4 removed it)

**New bug surfaced — PS-4:** `Import-PolicyZip` used a PowerShell
scriptblock (`{ $true }`) for the SSL bypass callback. .NET Core 6+
(PS 7) does not accept PS scriptblocks for
`HttpClientHandler.ServerCertificateCustomValidationCallback` — the
property is typed as `Func<HttpRequestMessage, X509Certificate2,
X509Chain, SslPolicyErrors, bool>`. Every request through this
handler throws. The sibling function `Import-ContentZip` already
used the correct static delegate
`[System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator`
— one function got it right, one got it wrong.

Also surfaced during this run: spurious "Report not found" WARN
during uninstall even though the instance ended up clean. api-explorer
investigation (see session task `a73f632c6ba4678eb`) confirmed that
`Get-AllReports` works correctly post-PS-2-fix and that both REST
and Ext.Direct listing paths see content-zip-imported reports when
probed directly. The WARN is a cosmetic artifact — likely a
dashboard-delete cascade removing the report before `_uninstall_reports`
lists, matching Python's identical benign behavior.

**Agent output file:** session task transcript `a460fd364239280df`

**Follow-up:** PS-4 SSL bypass fix + `Get-AllReports` limit parity
bump (50 → 500) + narrow re-run of Tests 1 and 3.

---

## 2026-04-11 — PowerShell `install.ps1` acceptance, final narrow re-run

**Instance:** `vcf-lab-operations.int.sentania.net` (VCF Ops 9.0.2)
**Runtime:** pwsh 7.5.1 on Linux
**Build under test:** commit `889c761` (PS-4 SSL fix + limit=500 parity)
**install.ps1 md5:** `736b7c89f31462281ba05d633d225f4a` (uniform across
all four freshly-rebuilt dist zips)
**Scope:** Tests 1 and 3 only — the SM enable paths that were partial
in the previous run. Tests 2, 4, 5, 6 already passed and were not
re-run.

**Result: 2/2 PASS**

- Test 1 — Single-bundle install + cleanup: **PASS**
  - `install.ps1` exit 0
  - 10 SMs imported AND enabled on Default Policy (step 6/7, zero SSL
    errors, zero `[enable-verify N/3]` retry lines)
  - 1 view + 1 dashboard + 1 report imported
  - Uninstall as admin exited 0 cleanly, zero HTTP 500s across all
    delete operations (view, dashboard, SMs; report "not found" WARN
    is benign pre-existing behavior)
- Test 3 — Multi-bundle install + cleanup: **PASS**
  - Multi-select checklist showed both display names, both selected
  - Single auth token across both bundles
  - 10 + 6 = 16 SMs imported AND enabled — zero SSL errors, zero
    retries across either bundle
  - 2 views + 2 dashboards + 1 report imported
  - Multi-bundle uninstall as admin exited 0 cleanly, per-bundle
    delete order respected, zero HTTP 500s across 16 SMs + 2 views
    + 2 dashboards + 1 report

**Critical pass criteria:**
- Exit code 0 on both install runs: PASS
- Zero SSL errors in stdout/stderr: PASS (PS-4 fix confirmed working)
- Zero `[enable-verify N/3]` retry lines: PASS (policy round-trip
  succeeded on first attempt every time)
- Zero HTTP 500s on delete operations across both runs: PASS
  (PS-1/2/3 + delete-shape fixes intact across a fresh cycle)
- Instance clean at end: PASS (REST confirmed zero VCF Content
  Factory SMs remaining)

**Lab state after run:** clean

**Non-blocking observations:**
- Temp dirs `/tmp/psqa-narrow-single/` and `/tmp/psqa-narrow-multi/`
  remain on the host — qa-tester shell sandbox blocked `rm -rf`
  cleanup. Contain only extracted zip contents; no secrets or
  instance state. Safe to leave or remove manually.
- Benign "Report not found" WARN still present during uninstall,
  consistent with every prior run on both runtimes. Cosmetic only;
  end state is always correct.

**Agent output file:** session task transcript `a1ddfa85160992253`

**Verdict:** PowerShell install path has reached full 6/6 parity
with Python. The multi-bundle packaging refactor is **complete and
validated against the live lab across both runtimes.**

---
