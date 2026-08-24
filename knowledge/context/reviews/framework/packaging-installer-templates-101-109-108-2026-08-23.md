# Framework review — installer templates, issues #101 / #109 / #108

- **Branch:** `fix/installer-templates-101-109-108` (uncommitted working tree, 8 files)
- **Base:** `main` @ `05480de`
- **Reviewer:** `framework-reviewer` (RULE-013 blanket gate, pre-PR)
- **Date:** 2026-08-23
- **Verdict:** **CHANGES REQUESTED** — 1 BLOCKING, 4 WARNING, 3 NIT

## Surface under change

| File | What changed |
|---|---|
| `src/vcfops_packaging/templates/install.py` | 5 reads pinned to `encoding="utf-8"` |
| `src/vcfops_managementpacks/templates/post-install.py` | 3 `open()` calls pinned to `encoding="utf-8"` |
| `src/vcfops_packaging/templates/install.ps1` | 3 new StrictMode probe helpers; ~20 sites routed through them; SM ghost-state retry ported |
| `src/vcfops_packaging/template_version.py` | `2026-08-21-2` -> `2026-08-23-1` |
| `tests/fixtures/install_ps1_advisory_harness.ps1` | +~50 assertions (94 total) |
| `tests/test_install_ps1_tls_and_advisories.py` | AST encoding guard + 4 anti-generalisation pins |
| `knowledge/context/authoring/guide_powershell.md` | new "the `if ($r.pageInfo)` guard cannot save itself" section |
| `knowledge/context/wire-formats/wire_formats.md` | SM ghost state: three call sites, must stay in step |

## Checks re-run independently

| Check | Result |
|---|---|
| `python3 -m pytest -q` | **945 passed, 4 skipped, 178 deselected** (matches claim) |
| `python3 -m pytest -q -m slow` | **not completed in the review window** (two attempts, each killed by the wall clock while a concurrent reviewer's suite ran on the same box). Not material to this diff: the 156 slow tests are publish/release integration and touch none of the changed surface. |
| `python3 -m pytest -q -m "" tests/test_install_ps1_tls_and_advisories.py` | **28 passed** (the whole file, slow-marked included) |
| Seven-package `validate` chain | **pass**, whole corpus, incl. 6 Tier 2 SDK projects |
| PowerShell harness (94 assertions) | **ALL ASSERTIONS PASSED** |
| `pwsh` AST parse of `install.ps1` | clean, 16825 tokens, 0 parse errors |
| `scripts/path_reference_audit.sh` | clear x4 (1 idle, 3 under concurrent slow-suite load) |
| `check-staleness` on all 3 `dist/*.zip` | all three now report **STALE** against `2026-08-23-1` |
| Render regression / `pak-compare` | n/a — no renderer, loader, or builder change in the diff |

### Negative control 1 — #101 encoding guard (re-run by me)

Ran `test_shipped_templates_pin_text_encoding` with `REPO_ROOT` repointed at
`git show HEAD:` copies of both templates. **Control holds**, and names the
exact 8 sites claimed:

```
CONTROL OK install.py:      [(1534,'read_text'),(92,'read_text'),(1541,'read_text'),(126,'read_text'),(142,'read_text')]
CONTROL OK post-install.py: [(56,'open'),(60,'open'),(64,'open')]
```

An independent AST audit of my own over the post-fix tree returns **zero**
un-pinned text-mode sites in either template.

### Negative control 2 — #108 narrow scope (re-run by me)

Deleted only the `contentType` filter line from a copy of `install.ps1` and ran
the real harness against it. **Control holds**, failing on exactly the intended
assertion:

```
FAIL: an all-skipped DASHBOARDS/VIEW_DEFINITIONS import NEVER triggers the SM retry
```

### Verified claims about PowerShell semantics (measured under pwsh 7.5.1)

The `guide_powershell.md` guidance is **correct**, and I measured both halves:

- `if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }` throws
  `PropertyNotFoundException` on **both** envelope shapes (PSCustomObject and
  the error hashtable). The guard genuinely cannot save itself.
- `return @()` yields `$null`; `return @(1)` yields `Int32`; `return ,@()`
  yields `Object[]` Count 0 and `return ,@(1)` yields `Object[]` Count 1. The
  comma-wrap in `Get-PropList` is load-bearing as documented.

### The #101 "correct by construction" ceiling — raised to measured

The brief asks whether "correct by construction" is good enough for something
that ships to customers. It did not have to stay at construction. Both halves
of the failure mode reproduce on this Linux box:

```
LANG=C   read_text()                -> UnicodeDecodeError: 'ascii' codec ... 0xe2
LANG=C   read_text(encoding='utf-8') -> succeeds
         read_text(encoding='cp1252') -> 'xâ†’y'   (silent mojibake, no exception)
         read_text(encoding='utf-8')  -> 'x→y'
```

The important half is the second: on cp1252 the un-pinned read does **not**
crash, it returns mojibake, and `json.loads()` parses it happily. A customer on
native Windows would have gotten a successful install with mangled view and
dashboard names. That is the reports-green-while-broken class. The fix removes
the dependency on `locale.getpreferredencoding()` entirely, which is a property
of the Python API contract rather than of the platform, so a
`windows-latest` runner would add nothing to the *correctness* argument. It
would only add coverage for site *discovery*, and the new AST guard covers that
better than a runner would. **Ceiling accepted.**

### The `newline="\n"` half — verified, and stronger than claimed

`tooling`'s argument covers only the templates' own writes. Both halves check
out, and there is a third guarantee it missed in its own favour:

1. `install.py` has **no** filesystem text writes at all (AST-verified). Every
   write is `zipfile.writestr(name, str)`, which always encodes UTF-8 and
   preserves the string's own `\n` regardless of host locale.
2. `post-install.py`'s three writes target `$ADAPTER_BASE/work/install.log` and
   `$VCOPS_BASE/user/conf/lastbuildversion.txt` (`post-install.py:92-93`), both
   on the appliance, never zipped. `copy_to` uses `shutil.copyfile` (binary).
3. `builder.py:622-623,736-737` reads both templates with
   `read_text(encoding="utf-8")` (universal newlines: any CRLF in the source
   collapses to `\n`) and ships them via `writestr`. **No CRLF can reach a
   distributable through this path even if a template were committed with CRLF.**

Zero `newline=` sites is correct.

### Stale-zip discipline (dimension 9) — satisfied on both halves

`src/vcfops_packaging/templates/` changed, so all dist zips are stale.
`CURRENT_TEMPLATE_VERSION` **is** bumped, and I verified the signal reaches
already-distributed copies: all three `dist/*.zip` now report `STALE` against
`2026-08-23-1`. Both builders that stamp it (`builder.py:729`,
`discrete_builder.py:850`) read the constant, so previously built bundles will
prompt an operator to rebuild.

**Required post-approval action (orchestrator, not tooling):** full
`content-packager` rebuild of every manifest in `bundles/` (CLAUDE.md, "After
tooling changes"). Not optional.

---

## BLOCKING

### B1 — `Upsert-CustomGroup` now takes a mutating action on a lookup it knows failed

`src/vcfops_packaging/templates/install.ps1:1244-1275`

```powershell
$resp = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
$existingId = $null
foreach ($g in (Get-PropList $resp "groups")) { ... }
if ($existingId) { PUT } else { POST }   # <- create
```

Before this diff, an error envelope on the lookup GET threw
`PropertyNotFoundException` and the installer stopped. After it,
`Get-PropList` correctly returns `@()`, `$existingId` stays `$null`, and control
falls through to the **create** branch. The status code of the failed lookup is
never consulted, even though `Get-StatusCode` is right there and every other
converted site in this diff reports it.

The harness asserts this path "degrades to create, which reports the status" —
but only because the stubbed POST also returns the error envelope. On a real
instance with a transient 500 on the GET followed by a healthy POST, the
installer creates a **second custom group with the same name** on a customer's
instance, silently, and reports `OK Created`.

Whether VCF Ops actually permits a duplicate group name is unproven either way,
and that is the point: per the reviewer doctrine's skeptic default, taking a
mutating action on the basis of a read that returned an error envelope is the
finding, regardless of how the server happens to respond. It is also precisely
the failure class #109 exists to close (a crash replaced by a wrong action, not
by a sentence). Every other site converted in this diff degrades to a benign
no-op or a `Write-Fail` naming the status; this one does not.

**Smallest correct fix** — status-gate the lookup, matching the pattern already
used in `Get-DefaultPolicyId`:

```powershell
$resp = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
$sc = Get-StatusCode $resp
if ($sc -ne 200) { Write-Fail "Custom group lookup failed for '$name' (HTTP $sc); refusing to create a possible duplicate" }
```

Add a harness assertion that an error envelope on the lookup GET produces the
lookup sentence and issues **no** POST (`$script:ApiCalls -eq 1`). The existing
"degrades to create" assertion should be inverted, not extended.

---

## WARNING

### W1 — the uninstall lookups now state a falsehood about the instance

`install.ps1:2663-2676` (`Uninstall-Supermetrics`), `:2688-2700`
(`Uninstall-CustomGroups`)

Same root as B1, opposite direction. On an error envelope,
`Get-SupermetricsByName` / `Find-CustomGroupIds` return an empty map, and the
operator is told:

```
WARN  Super metric not found (already removed?): <name>
WARN  Custom group not found (already removed?): <name>
```

"Already removed?" is an assertion about instance state derived from a lookup
that failed. The operator concludes the uninstall is complete when nothing was
deleted. This is loud (it lands in `$Ctx.Warnings` and the advisory trailer), so
it is not a silent downgrade, but the sentence is wrong. Direction of travel is
still a clear improvement over the pre-diff crash.

**Fix:** have the two helpers signal lookup failure distinctly (a status-check
`Write-Fail`, or an out-param the callers can turn into "lookup failed (HTTP
N); cannot determine whether '<name>' exists"). One line each at the same place
as B1's fix.

### W2 — the `#114` comment is stronger than the document it cites

`install.ps1:1607-1614` (`Get-SmGhostStateSkipCount`) and the mirrored block in
`tests/fixtures/install_ps1_advisory_harness.ps1`

The comment reads:

> #114 bisected the identical `imported=0/skipped>0` signature on the
> DASHBOARDS and VIEW_DEFINITIONS paths and found an unrelated cause:
> create-only mode (`force=false`), where the skip is idempotent and a retry is
> a guaranteed no-op...

`knowledge/context/api-surface/content_import_skip_semantics.md:29-34` is more
careful, and the difference matters:

> A `force=true` import that reports this signature is therefore
> **unexplained**, not benign, and should be treated as a new finding rather
> than diagnosed from this document. Since every factory call site hard-codes
> `force=true`, any occurrence seen through the factory falls into exactly that
> unexplained category.

`install.ps1:734` hard-codes `?force=true`. So the one variant an operator can
actually hit through this installer is the *unexplained* one, and the comment
tells the next reader it is a settled no-op case. The **behaviour is correct**
(do not widen the retry) and the anti-generalisation pins are right; only the
justification overstates. This is the "the claim that would let the next person
stop looking" failure mode, on a comment placed specifically to stop people
looking.

**Fix:** add one sentence — "under `force=true` (what this installer always
sends) the signature is unexplained per that document, not benign; it is
surfaced as an advisory rather than retried."

### W3 — #101's guard covers file I/O only; stdout on a customer's Windows box is untouched

`install.py:197, 218, 260, 1683, 1766, 1806, 1814, 1883, 1891` (and peers)

The installer prints content names it read out of the bundle
(`_ok(f"Created: {name}")` and friends). On a customer's native-Windows box with
output redirected to a file or a pipe, Python encodes stdout with the locale
encoding, and a view name carrying a character outside cp1252 raises
`UnicodeEncodeError` **after** the object has been created on the instance —
the same half-modified-instance shape #109 exists to close. The new AST guard
does not and cannot see this.

Not a regression from this diff, and out of #101's stated scope. Flagged because
closing #101 will read as "shipped-template encoding: done", and it is not.

**Fix:** file a follow-up. The one-line mitigation is
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` near the top of
`install.py` (3.7+; the template already targets 3.9+).

### W4 — three changed behaviours have no test coverage

Dimension 10. The harness is genuinely strong — it extracts the functions
verbatim from the template via the AST, so it tests shipped code, not a copy —
but three things in this diff sit outside it:

- `install.ps1:2818-2819` — the new `Write-Fail` when `/api/auth/currentuser`
  returns no `id`. Zero coverage; `Invoke-Install` is not in the harness's
  `$want` list.
- `install.ps1:626-658` (`Get-MarkerFilename`) — four converted reads, including
  a real behaviour change (the first poll loop now breaks immediately on an
  error envelope instead of swallowing the throw and timing out). Zero coverage.
- `Install-Supermetrics` is tested against a **stubbed** `Import-ContentZip`, so
  the load-bearing assumption "`$importResult` is exactly the status object, not
  a polluted output stream" is never exercised against the real function. I
  verified it by inspection (`Write-ImportSummaryWarnings` emits only via
  `Write-Host`; every other statement in `Import-ContentZip` is an assignment or
  a void method call, so `return $s` is the sole success-stream value) — but
  inspection is not a test, and a future edit that adds one uncaptured
  expression to `Import-ContentZip` would silently disable the #108 retry with
  every assertion still green.

**Fix:** add the currentuser-no-id assertion (cheap, `Invoke-Install` need not
be extracted — assert the guard exists via the existing static-pin pattern in
`TestSmGhostStateRetryStaysNarrow`); add a static pin that
`Import-ContentZip`'s body contains no uncaptured pipeline statement, or extract
it into the harness with `Invoke-Api` and `System.Net.Http` stubbed.

---

## NIT

### N1 — two different dictionary tests against the same envelope

`Get-StatusCode:578` uses `-is [hashtable]`; `Get-PropValue:209` uses
`-is [System.Collections.IDictionary]`. This diff now leans on both against the
same `Invoke-Api` error shape. Harmless today (`Invoke-Api` builds a literal
`@{}`), but they will disagree the day that shape becomes an ordered dictionary.

### N2 — `Authenticate:605` `$resp.token` — agree with leaving it

Confirmed: it sits inside a `try/catch` whose `Write-Fail "Authentication
failed: $_"` yields a sentence, and it runs at step 1 before anything has landed
on the instance, so there is no half-install to recover. The sentence would read
"Authentication failed: The property 'token' cannot be found on this object",
which names a symptom rather than a cause, but an operator reading
"Authentication failed" at step 1 is not misdirected. **Leaving it is right.**
Optional one-liner if it is ever touched: probe the member and fail with
"authentication succeeded but the response carried no token".

### N3 — the path-audit concurrency explanation is unconfirmed, not confirmed

`tooling` reported one dead-reference run and attributed it to a concurrent full
pytest. I could not reproduce it: 4 runs of `scripts/path_reference_audit.sh`,
one idle and three with the slow suite running concurrently, all clear. The
`tests/README.md:91` description of the `real_corpus` group also says those tests
**read** the corpus, which does not obviously support a "tests write the tree"
mechanism; the more plausible mechanism is index contention on the audit's
`git ls-files --error-unmatch` validity check (`path_reference_audit.sh:354`).

What is proven: the audit is clear on this tree. What is not proven: why it once
was not. Recording it so the next occurrence is not waved off as known.

---

## Assessments requested in the brief

### 1. The ExtDirect / `Invoke-DashboardAction` reads left out of scope

**Leaving them does not make this PR incoherent.** #109's scope is literally
"unguarded property reads on **`Invoke-Api`** results", and that family is a
different envelope reached through `Invoke-WebRequest` + `ConvertFrom-Json`, on
the uninstall path only. Sweeping it here would have widened the diff into a
second envelope contract with no shared helper. Splitting is right.

**But the follow-up issue must name the full set, not four lines.** `tooling`
listed `1851, 1890, 1911, 1954`. The complete set I found is:

| Line | Read | Function |
|---|---|---|
| 1800 | `$result.dashboards` | `Get-AllDashboards` |
| 1806 | `$_.id`, `$_.name` | `Remove-Dashboards` |
| 1851, 1852, 1855 | `$result[0].type/.message/.result` | `Get-AllViews` |
| 1890, 1891 | `$result[0].type/.message` | `Remove-View` |
| 1911, 1912, 1914 | `$result[0].type/.message/.result` | `Get-AllReports` |
| 1954, 1955 | `$result[0].type/.message` | `Remove-Reports` |
| 2638, 2639 | `$r.name`, `$r.id` on `Get-AllReports` records | `Uninstall-Reports` |

Note `$result[0]` is itself an index into an array that may be empty, so those
sites have an index failure in front of the member failure — the fix is not a
straight `Get-PropValue` substitution. A four-line issue would produce a sweep
that reads complete and is not, which is the same shape as the #109 partial that
created #109 in the first place.

### 2. `Authenticate`'s `$resp.token` — agree, leave it. See N2.

### 3. The pwsh-7.5.1-on-Linux / no-`windows-latest` ceiling

Stated plainly, in two parts because they are not the same claim.

**For #101 the ceiling is fine, and I raised it above "by construction" anyway.**
The failure mode reproduces on this box in both forms (crash under `LANG=C`,
silent mojibake under explicit cp1252), and the fix demonstrably removes both.
Pinning an encoding removes a dependency on the platform's locale rather than
accommodating it, so a Windows runner cannot make the argument stronger. The
only thing a runner would add is confidence that all sites were *found*, and the
new AST guard does that job better and permanently.

**For #109 and #108 the ceiling is real and unchanged.** The harness banner is
honest about it (`install_ps1_advisory_harness.ps1:11-13`). `Set-StrictMode
-Version Latest` on Windows PowerShell 5.1 is not the same "Latest" as pwsh 7's,
`PSObject.Properties[...]`, `IDictionary.Contains`, and the `,@()` return-unwrap
behaviour all need to hold on the 5.1 engine, and none of that is exercised
anywhere. The mitigation in place is `guide_powershell.md`'s "PS 5.1
compatibility is a hard requirement" section plus the parse-level checks. That
is the standing state of this file, not something this diff worsens, and it is
not a reason to hold the PR.

---

## If shipped as-is

A Windows operator installing a bundle while the Ops API is having a bad minute
gets, instead of the pre-diff crash, a **second custom group created under a
name that already exists** and an `OK Created` line for it (B1) — and on
uninstall, "not found (already removed?)" for objects that are still there (W1).
Everything else in the diff is a clear improvement: the encoding fix closes a
silent-mojibake path on customers' machines, the StrictMode sweep converts about
twenty crash sites into operator sentences, and the SM ghost-state port closes a
real Python/PowerShell drift that left Windows operators with invisible super
metrics.

Resolve B1 and re-review. W1-W4 should land in the same PR if cheap (all four
fixes are one to five lines); N1-N3 are recordable as follow-ups.

---
---

# Round 2 — confirmation review (2026-08-23, same branch)

**Verdict: CHANGES REQUESTED — 1 BLOCKING (new), 0 carried over.**

Round 1's BLOCKING and all four WARNINGs are **resolved**. One leg of the W4
fix does not hold, and the failure it fails to catch is the silent disabling of
the #108 retry.

## Checks re-run (round 2, all independent)

| Check | Result |
|---|---|
| `python3 -m pytest -q` | **954 passed, 4 skipped** (matches claim; was 945) |
| `pytest -q -m "" tests/test_install_ps1_tls_and_advisories.py` | **37 passed** (was 28) |
| `pytest -m slow --collect-only` | **178 collected** (`tooling` said 165; the `-m slow` selector reports 178) |
| Full slow suite | again did not finish in the review window; not material to this surface |
| PowerShell harness | **ALL ASSERTIONS PASSED**, **123** `pass:` lines (matches claim) |
| `pwsh` AST parse | clean, 17039 tokens |
| Seven-package `validate` chain | **7/7 OK** |
| `path_reference_audit.sh` | clear |
| My own AST encoding audit | 0 un-pinned text-I/O sites |
| My own `Invoke-Api`-derived read sweep | only the known out-of-scope ExtDirect family remains |

## Round-1 findings: resolved

- **B1 (`Upsert-CustomGroup`)** — closed, and correctly widened. `Assert-LookupOk`
  `Write-Fail`s on any non-200 and is present at all seven decision sites
  (`install.ps1:866, 1280, 1306, 1345, 2467, 2498, 2526, 2600, 2629`), pinned
  statically by `TestFailedLookupsDoNotMutate::test_lookup_is_status_checked`.
  I confirmed `Invoke-Api` returns the `@{__statusCode; __body; __error}`
  hashtable for **every** non-2xx (`Invoke-RestMethod` throws, the catch builds
  it), so `Get-StatusCode` cannot be fooled into reporting 200 on an API error
  and the guard is genuinely reachable.
- **W1 (uninstall's false "already removed?")** — closed at the source, inside
  `Get-SupermetricsByName` / `Find-CustomGroupIds` / both uninstall loops.
- **W2 (the #114 comment)** — closed. The rewrite now names that this installer
  hard-codes `force=true`, quotes "unexplained, not benign", lists the three
  untested contexts, and restates the reason as *no evidence a retry helps*
  rather than *we know it is harmless*, ending "investigate it -- do not reach
  for this function." I verified the three contexts against
  `content_import_skip_semantics.md:27-29, 202-204`: UI-locked dashboards, a
  non-admin importer against another user's content, pak-supplied solution
  content. Cited accurately. **It no longer tells the next person to stop looking.**
- **W3 (stdout encoding)** — accepted as out of scope, filed as #118. Agreed.
- **N1 (`Get-StatusCode` classification)** — closed with a pytest pin.

## Negative controls: spot-checked, and they hold

- **Upsert-CustomGroup guard removed, *and* both message assertions deleted
  from the harness** → still fails, on the assertion that matters:
  `FAIL: NO POST/PUT/DELETE is sent after a failed lookup`. The stub's POST now
  returns 200, so "something threw" genuinely cannot satisfy it. **Claim confirmed.**
- **`Install-Symptoms` guard removed** → fires on the behavioural harness
  (`FAIL: a failed symptom lookup refuses`) *and*, with that message assertion
  also deleted, on `FAIL: and creates no duplicate symptom`, *and* independently
  on the static pytest pin. Three-way. **Claim confirmed.**
- **`Get-StatusCode` reverted to `[hashtable]`/`.ContainsKey`** → the pytest pin
  fires. Confirmed.
- **#108 `contentType` filter deleted** (re-run from round 1) → fires on the
  #114 guard assertion. Confirmed.
- Round 1's #101 control re-confirmed: 8 sites, exact line numbers.

The genuine not-found path is **not** flattened: a real empty-200 still creates
(`Assert (Get-MutationCount) -eq 1 ... POST`) and uninstall still reports
"Alert not found" on `{"alertDefinitions":[],"pageInfo":{"totalCount":0}}`.
Both assertions exist and pass.

## The "pre-existing" history claim — verified, and it needs one correction

`tooling` says `Install-Symptoms` and `Install-Alerts` "threw at
`$r.symptomDefinitions` before the sweep". I replayed `main`'s exact loop shape
against all four envelopes under `Set-StrictMode -Version Latest`:

```
error-hashtable            -> THREW PropertyNotFoundException
200, member ABSENT         -> THREW PropertyNotFoundException
200, member explicit null  -> NO THROW, iterated 0  => falls through to CREATE
200, member empty array    -> NO THROW, iterated 0  => falls through to CREATE   (correct)
```

So the claim is **true for the shape that matters**, but "the sweep surfaced two
latent duplicate-by-name bugs" would be **inaccurate in the PR description**.
On `main` these sites crashed on an error envelope; they did not duplicate. The
accurate sentence is:

> `main` crashed at these sites on an API error envelope. The #109 sweep
> converted that crash into a silent duplicate-create at three sites
> (`Upsert-CustomGroup`, `Install-Symptoms`, `Install-Alerts`). This round
> converts it to a refusal. Net versus `main`: crash -> sentence, never
> crash -> duplicate.

One genuinely pre-existing duplicate path does survive: a **200 carrying
`"symptomDefinitions": null`** falls through to create on `main` and still does
now, because `Assert-LookupOk` checks only the status. That is the right
boundary — `null` and `[]` both legitimately mean "empty instance", and
refusing on either would break first install on a clean instance. Not a finding,
recorded so it is not mistaken for a gap later.

## The uninstall-refusal judgment — I agree with refusing

You asked whether refusal or a distinct warning is right for an operator
mid-teardown. **Refusal.** Three reasons:

1. The failed read is a **lookup that resolves names to IDs**. Without it the
   uninstall has nothing to delete, so "warn and continue" and "refuse" remove
   exactly the same number of objects: zero. The only difference is whether the
   operator is told the teardown succeeded.
2. A warning that scrolls past in a teardown is read as "that one was already
   gone", which is what W1 was about. The operator's next action after a clean
   -looking uninstall is typically to delete the bundle directory or reinstall
   over it. Both are worse decisions made on a false premise.
3. It is recoverable and cheap: re-run the uninstall when the API is healthy.
   Uninstall is idempotent by construction here (name lookup, delete if found),
   so refusing costs one re-run and risks nothing.

The one case where refusal is worse is a **partial** page failure mid-paging on
a large instance, where some objects were already deleted before the refusal.
The message says "nothing was created, deleted, or modified by this step",
which is then not strictly true for a multi-page uninstall. That is a wording
NIT (N5 below), not a reason to prefer warning.

---

## BLOCKING (round 2)

### B2 — the `Import-ContentZip` output-purity pin whitelists the exact trap its own comment names

`tests/fixtures/install_ps1_advisory_harness.ps1:594-611`

```powershell
# Statement-level method calls must be void.  $x.Add() on an ArrayList returns
# an int; on a generic List it returns void.  This is the classic version of
# the same bug.
$voidMethods = @("Dispose", "Close", "Add", "Clear", "SetAttribute",
                 "AppendChild", "Write", "RemoveAll")
```

`"Add"` is on the allowlist. The comment directly above it identifies
`ArrayList.Add()` as "the classic version of the same bug", and then the check
skips every method named `Add` regardless of receiver. The `$leaked` check
above it does not compensate: `$x.Add(...)` parses as a
`CommandExpressionAst` / `InvokeMemberExpressionAst`, not a `CommandAst`, so it
is invisible to that pass too.

**Measured, not argued.** I injected `$scratch = New-Object
System.Collections.ArrayList; $scratch.Add("x")` into `Import-ContentZip` and
ran the real harness: **`ALL ASSERTIONS PASSED`, 123/123**, including
"statement-level method calls in Import-ContentZip are void". The runtime
consequence of the same injection:

```
clean        : type=PSCustomObject  ghostSkipped=4
with .Add()  : type=Object[]  count=2  ghostSkipped=0
```

The status object becomes a two-element array, `Get-SmGhostStateSkipCount`
reads `operationSummaries` off an `Object[]`, gets `$null`, returns 0, and the
**#108 ghost-state retry is silently disabled** — no error, no warning, full
green suite. That is exactly the scenario W4 asked to be closed, and it is the
reports-green-while-broken class aimed at a future maintainer who will cite
this assertion as proof the property holds.

`"Clear"`, `"Write"` and `"RemoveAll"` are on the same allowlist by name and
have the same receiver-dependence (`ArrayList.RemoveAll` is void,
`List<T>.RemoveAll` returns `int`).

**Smallest correct fix.** The two statement-level `.Add(` calls in
`Import-ContentZip` today are genuinely void
(`HttpRequestHeaders.Add`, `MultipartFormDataContent.Add`), so simply deleting
`"Add"` from the list would red the assertion. Allowlist by **receiver
expression**, not method name:

```powershell
# Void by receiver, not by method name: ArrayList.Add returns an int and
# List<T>.RemoveAll returns an int, so a name-only allowlist cannot be safe.
$voidCalls = @('$httpClient.DefaultRequestHeaders.Add',
               '$content.Add',
               '$httpClient.Dispose')
```

and match `$expr.Expression.Extent.Text`. Then any new `.Add()` on any other
receiver fails the assertion. Re-run my injection as the negative control: it
must produce `FAIL: statement-level method calls in Import-ContentZip are void:
<line>: $scratch.Add("x")`.

The other two legs of W4 are solid and I am not asking for changes to them:
`Get-OwnerId` is extracted and both branches asserted
(`install.ps1:639-649`, harness), and all four `Get-MarkerFilename`
conversions are driven with `-TimeoutSeconds 0`, including an assertion that
pre-fix this died as a misleading "Timed out waiting for prior export".

---

## NIT (round 2)

### N4 — `Invoke-Api`'s own catch has the #109 defect, one frame below the sweep

`install.ps1:625` — `$statusCode = $_.Exception.Response.StatusCode.value__`.
On a connection-level failure (DNS, refused, TLS handshake, timeout) there is
no `Response`, and under StrictMode this throws
`PropertyNotFoundException: The property 'StatusCode' cannot be found on this
object` (measured). The exception escapes `Invoke-Api` entirely, so
`Assert-LookupOk` and every other guard added by this PR never run.

Pre-existing, outside #109's stated scope (it is a read inside `Invoke-Api`,
not on an `Invoke-Api` result), and it fails loudly rather than silently, so it
is not a blocker. Flagged because "the #109 sweep is complete" would otherwise
be read to cover it. Belongs in the same follow-up issue as the ExtDirect family.

### N5 — `Assert-LookupOk`'s message overclaims on a multi-page uninstall

"nothing was created, deleted, or modified by this step" is true for every
install site and for a first-page uninstall failure, but the uninstall guards
sit inside paging loops that delete after the loop, so it holds there too —
except for `Uninstall-Symptoms` / `Uninstall-Alerts` where the *collection*
loop precedes deletion, so it does hold. The one shape where it could be false
is a future guard placed after a mutation. Consider "nothing was created,
deleted, or modified by this step" -> "this step stopped before acting".
Cosmetic.

---

## If shipped as-is (round 2)

The shipped installer is **correct**: the duplicate-create paths are closed,
uninstall no longer lies about instance state, and the encoding and ghost-state
fixes stand. Nothing an operator does today goes wrong. What ships broken is a
**test that says it is guarding something it is not**: the next person to add a
statement to `Import-ContentZip` can disable the #108 retry with 123 green
assertions and an explicit "statement-level method calls are void" pass line
telling them it is fine.

Fix B2 and re-review. It is a contained change to one allowlist in the harness
plus its negative control.

---
---

# Round 3 — final confirmation (2026-08-23, same branch)

**Verdict: APPROVE.** Zero BLOCKING. One WARNING with a one-line fix, handed
over rather than held.

## Tree integrity after the disclosed `git stash push` / `pop`

Asked for specifically. The disclosure is accurate and **the tree is whole.**
I did not take that on the stash bookkeeping; I verified it three ways.

1. **Stash list is clean.** `git stash list` holds two entries, both predating
   this work and both on other branches (`feat/vm-snapshot-inventory`,
   `ci/test-speed`). No orphan from this round. All 8 files still show `M`
   against `main`; line counts grew monotonically across rounds
   (`install.ps1` 306 -> 327, harness 388 -> 421, pytest 201 -> 234,
   `guide_powershell.md` 51 -> 76).
2. **Marker sweep across all four rounds.** Every distinguishing artifact from
   R1 through R3 is present: the 5+1 `read_text(encoding="utf-8")` sites and
   post-install's 3, `CURRENT_TEMPLATE_VERSION = 2026-08-23-1`, `Get-PropList`
   / `Get-PageTotalCount` / `Get-GroupName` / `Get-SmGhostStateSkipCount` /
   the `super metrics (retry)` label, `Assert-LookupOk` (definition + **9**
   call sites), `Get-OwnerId`, `Get-StatusCode`'s `IDictionary` +
   `.Contains()`, the "unexplained, not benign" caveat, `Get-MutationCount`,
   `TestFailedLookupsDoNotMutate`, `$voidCalls` (and `$voidMethods` gone),
   `test_void_call_allowlist_is_receiver_keyed`, `Void-by-receiver`, and
   "this step stopped before acting". No conflict markers; every file's tail
   is intact (no truncation).
3. **Byte-level regression diff against reconstructed round-2 state.** I still
   held round-2 copies of `install.ps1` and the harness from my own negative
   controls, so I reconstructed round 2 and diffed forward:
   - `install.ps1` round-2 -> round-3 delta is **exactly three hunks, all
     comment or message text** (the `Assert-LookupOk` wording, the
     `Install-Symptoms` sequence + boundary comment, the `Install-Alerts`
     back-reference). **Zero code lines changed.**
   - Harness round-2 -> round-3 delta removes **only** the old `$voidMethods`
     block and its loop, and adds 43 lines. Nothing else was removed. The two
     assertion lines I had deleted to build NC-A are present again, i.e. the
     current file is a superset of round 2.

   A partial restore cannot produce that shape. Combined with 955 green, both
   `.ps1` files parsing clean, and validate 7/7, I am satisfied nothing was
   lost.

## Checks re-run (round 3)

| Check | Result | Claim |
|---|---|---|
| `pytest -q` | **955 passed, 4 skipped** | matches |
| `pytest -q -m "" tests/test_install_ps1_tls_and_advisories.py` | **38 passed** | — |
| PowerShell harness | ALL ASSERTIONS PASSED, **125** `pass:` lines | matches |
| `pwsh` AST parse, `install.ps1` | clean, 17081 tokens | matches |
| `pwsh` AST parse, harness | clean, 4258 tokens | matches |
| `pytest -m slow --collect-only` | **178** collected | `tooling` said 166; the `-m slow` selector reports 178 both rounds. Immaterial, but the number in the PR body should be the one the command prints. |
| validate chain | **7/7 OK** | matches |
| `path_reference_audit.sh` | clear | matches |
| `check-staleness` on 3 dist zips | all STALE vs `2026-08-23-1` | rebuild still owed |

## B2 (round 2) — closed, and verified from both directions

- **My injection against the new pin:** `FAIL: statement-level method calls in
  Import-ContentZip are void-by-receiver`. **Fires.**
- **Clean current template against the new pin:** `ALL ASSERTIONS PASSED`.
  No false positive.
- Round 2's measurement stands as the other direction: the same injection
  passed the name-keyed pin with 123/123 green while
  `Get-SmGhostStateSkipCount` went 4 -> 0.

**The three allowlisted receivers really are void.** I did not take this from
memory; I reflected them:

```
HttpClient.Dispose()                                  -> Void
HttpRequestHeaders.Add(String,String)                 -> Void
MultipartFormDataContent.Add(HttpContent,String,String) -> Void
--- contrast ---
ArrayList.Add(Object)                                 -> Int32
List`1.Add(String)                                    -> Void
```

The fix is precise about the right thing: the receiver carries the meaning,
and all three entries are correct. The `guide_powershell.md` lesson states the
same facts accurately.

## The null-vs-`[]` boundary pin — it genuinely prevents the tightening

Not just present, tested. I applied the plausible future tightening (treat a
200 carrying a null collection as "we could not read it either") to
`Assert-LookupOk` and ran the harness:

```
FAIL: a 200 with a null collection still creates (clean-box first install)
```

**Fires.** A later maintainer cannot close that boundary without the suite
telling them they are about to break first install on a clean box.

## The corrected source comments — accurate against what I replayed

`install.ps1:2473-2487` now reads: on `main` this loop threw under StrictMode
(both on an error envelope and on a 200 missing the member); the #109 sweep
turned that crash into a silent duplicate-create; this guard turns it into a
refusal; "there was never a window where main created duplicates here"; and the
`"symptomDefinitions": null` case still creates, exactly as on `main`.

Every clause matches my replay of `main`'s loop shape under
`Set-StrictMode -Version Latest`:

```
error-hashtable            -> THREW PropertyNotFoundException
200, member ABSENT         -> THREW PropertyNotFoundException
200, member explicit null  -> NO THROW, iterated 0 => CREATE
200, member empty array    -> NO THROW, iterated 0 => CREATE  (correct)
```

The universal negative ("never a window") holds for every shape I could
construct: the only non-throwing shapes on `main` are `null` and `[]`, and both
genuinely mean "no such object", so creating is correct rather than duplicative.
**Accurate. Use this wording in the PR body.**

---

## WARNING (round 3, not blocking)

### W5 — the meta-pin can be satisfied by a decoy declaration

`tests/test_install_ps1_tls_and_advisories.py::test_void_call_allowlist_is_receiver_keyed`

You asked whether the meta-pin holds or whether a cosmetic rename satisfies it.
**A rename satisfies it.** Proven, not argued. I built a harness that keeps the
current `$voidCalls` block untouched as a decoy and reverts the actual
comparison to a name-keyed list under a different variable:

```powershell
$voidCalls = @( '$httpClient.Dispose', ... )          # decoy, unchanged
$allowedNames = @('Dispose','Add','Clear','Write','RemoveAll')
...
if ($allowedNames -notcontains "$($expr.Member.Extent.Text)") {
```

Result:

```
META-PIN: PASSES on the bypass  <-- not caught
bypassed harness vs my ArrayList injection: ALL ASSERTIONS PASSED
```

The hole is that the pin validates the **declaration** and never checks that
the declaration is the list the comparison consults. Its three assertions
(block exists, entries receiver-qualified, `$voidMethods` absent) are all
satisfiable while the live check is name-keyed again.

This is **not** the round-2 failure repeated, and that is why it is a WARNING
rather than a BLOCKING. In round 2 the assertion stated a false property of the
code under test, and an *ordinary* edit (adding one line) defeated it silently.
Here every assertion is true of what it inspects, and defeating it requires
someone to deliberately build a decoy. Nothing ships broken.

**Fix, one line**, appended to the same test:

```python
assert "$voidCalls -notcontains" in text, (
    "the receiver-keyed allowlist is declared but not consulted; the check "
    "is reading some other list"
)
```

Verified: absent from my bypass harness, present in the real one. It ties the
declaration to the use, which is the only part currently unpinned.

---

## Negative controls run by me across all three rounds

Seven, each firing on its own assertion and on nothing else:

1. #101 encoding stripped (both templates) -> names all 8 original line numbers.
2. #108 `contentType` filter deleted -> the #114 DASHBOARDS/VIEW guard.
3. `Upsert-CustomGroup` guard removed, **both message asserts deleted** ->
   `NO POST/PUT/DELETE is sent after a failed lookup`.
4. `Install-Symptoms` guard removed -> behavioural harness, the mutation
   assert alone, **and** the static pytest pin. Three-way.
5. `Get-StatusCode` reverted to `[hashtable]` -> the classification pin.
6. ArrayList `.Add()` injected into `Import-ContentZip` -> passed the round-2
   name-keyed pin (the hole), fails the round-3 receiver-keyed pin.
7. `Assert-LookupOk` tightened onto null collections -> the clean-box
   boundary pin.

## Carried forward, not blocking

- **N4** — `Invoke-Api:625` `$_.Exception.Response.StatusCode.value__` throws
  under StrictMode on a connection-level failure, so on DNS/refused/TLS errors
  none of this PR's guards run. Per your instruction, it goes in the ExtDirect
  follow-up. The follow-up should also carry the full ExtDirect set from round
  2 (`1865, 1871, 1916-1920, 1955-1956, 1976-1979, 2019-2020, 2703-2704` in
  current numbering), not the original four lines.
- **#118** — stdout encoding on a customer's Windows box (my W3). Filed,
  deliberately not fixed here. Agreed.
- **Required post-approval:** full `content-packager` rebuild of every manifest
  in `bundles/`, then the PR. All three `dist/*.zip` correctly report STALE.

## If shipped as-is

An operator gets an installer that refuses rather than guesses when a lookup
fails, self-heals SM ghost state on Windows exactly as the Python path does,
and cannot silently mangle non-ASCII content names on a customer's machine.
The one residual is a regression tripwire that a determined rewrite could
route around; the behaviour it protects is correct today and independently
covered by the receiver-keyed check itself.
