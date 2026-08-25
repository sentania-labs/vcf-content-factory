# Framework review: install.ps1 / install.py family batch (#116, #118, #119, #121)

- **Reviewer:** `framework-reviewer` (RULE-013 blanket gate)
- **Date:** 2026-08-24
- **Branch:** `worktree-agent-a4bbd21027a944fff` (worktree
  `/home/scott/claude/vcf-content-factory/.claude/worktrees/agent-a4bbd21027a944fff`), diffed against `main`
- **Area:** `src/vcfops_packaging/templates/` (install.ps1, install.py),
  `src/vcfops_packaging/template_version.py`, `tests/`
- **Verdict:** **APPROVE** (0 BLOCKING, 3 WARNING, 3 NIT)

Fourth pass over the two shipped installers. Nothing in this diff touches
renderers, loaders, or builders, so anchors `00d3382` (pak-local default leaking
to the global import path) and `6c59f6b` (transform-blind key derivation) are
structurally out of reach here; confirmed by inspection of the diffstat, not
assumed.

---

## 1. Independent re-runs

| Check | Result |
|---|---|
| Full test suite | **976 passed, 6 failed, 13 skipped** (138s) — matches the claim |
| The 6 failures | Environmental, confirmed: `artifact source not found: 'content/sdk-adapters/synology/adapter.yaml' ... this source is under content/sdk-adapters/ which is gitignored`. Not diff-induced. |
| `tests/test_install_ps1_tls_and_advisories.py` | **55 passed** — matches |
| Behaviour harness | exit 0, **177 `pass:` lines** — matches. Baseline on `main` re-run for comparison: **132**. +45 new assertions. |
| pwsh AST parse of install.ps1 | **0 parse errors, 17784 tokens** — matches exactly |
| `install.py` | `ast.parse` clean |
| Validate chain (7 pkgs: supermetrics, dashboards, customgroups, symptoms, alerts, reports, managementpacks) | **7/7 PASS** |
| Render regression | n/a — no renderer/loader touched |
| pak-compare | n/a — no builder/pak-structure change |

---

## 2. The five load-bearing measured facts — all independently reproduced

Run under `pwsh 7.5.1`, `Set-StrictMode -Version Latest`, `$ErrorActionPreference='Stop'`
(the same mode install.ps1 sets at :83-84, verified):

| Claim | My measurement | Verdict |
|---|---|---|
| `@($null).Count` is 1, not 0 | `@($null).Count = 1`, `@().Count = 0` | **CONFIRMED.** Null and empty-array genuinely cannot share one guard. |
| `Get-PropValue` unrolls a returned array | 1-element array member -> returns `PSCustomObject` (`-is [System.Array]` False); empty array member -> returns `$null` | **CONFIRMED.** Using it for `result` / `dashboards` would have refused a healthy empty instance. The two direct probes are correct, not a style regression. |
| Direct `PSObject.Properties[...].Value` preserves shape | empty array member -> `isNull=False isArray=True count=0` | **CONFIRMED** |
| `Uninstall-Views`' `if ($v.viewDefinitionKey)` guard throws before any delete | `if ($v.viewDefinitionKey) {...} else { $v.id }` on `{"id":"i1"}` -> **PropertyNotFoundException** | **CONFIRMED, and it is the worst site in the batch.** The guard existed *because* the member is optional, so under StrictMode it threw on exactly the population it was written to serve. Same shape as the `if ($r.pageInfo)` finding. Not listed in #116. |
| The two exceptions are distinct | `@()[0]` -> IndexOutOfRangeException; missing member -> PropertyNotFoundException; **`@{}.nope` -> PropertyNotFoundException too** | **CONFIRMED.** A partial fix swaps one raw .NET exception for another. |

#119 BOM caveat (the issue flagged it as "check rather than assume"):
BOM'd and bare UTF-8 files read with `-Encoding UTF8` decode **identically**
(both `Café Überblick`, rawLen 25, no leading U+FEFF). **CONFIRMED — no BOM side
effect on read.** The mojibake path also reproduced: the same bytes through a
cp1252 decoder give `CafÃ© Ãœberblick`, and `ConvertFrom-Json` parses it without
complaint — a *successful* install with corrupted names, not a crash.

#118: reproduced end to end. `PYTHONIOENCODING=cp1252` + piped stdout, printing
a CJK content name: **exit 1 / UnicodeEncodeError** before the fix, **exit 0**
with correct UTF-8 bytes after.

---

## 3. #116 — my own recount

`pwsh` AST sweep (`MemberExpressionAst` / `IndexExpressionAst`) over the UI
function family. **My numbers do not match tooling's 35/9, because the scope
differs, not because a site was missed.** Over the 14-function set
(Get-ExtDirectResult, the two transports, the three list functions, the three
delete functions, the three Uninstall-* consumers, Start/Stop-UISession) I count
**93 member expressions and 18 index expressions raw**. The AST double-counts
nested composites (`$a.b.c` yields both `$a.b.c` and `$a.b`), and tooling's 35
plainly excludes the transports, `Start-UISession`, statics like
`[List[object]]::new()`, and the nested halves. **The count is a bookkeeping
disagreement, not a coverage one.** What matters is the classification, which I
redid from scratch:

- **Transport call sites: 6.** `install.ps1:2055, 2097, 2132, 2171, 2187, 2236`.
  **CONFIRMED.**
- **Downstream consumers not in the issue: 3.** `Uninstall-Dashboards`,
  `Uninstall-Views`, `Uninstall-Reports`. **CONFIRMED**, and these were the real
  hazard — the issue listed only the four `$result[0]` sites.
- **Index expressions: zero are `[0]` into an envelope array.** Confirmed:
  `grep '\$result\[0\]'` returns only three *comment* lines. The surviving
  indexes are `$envelopes[0]` (after a `.Count` check), `$first["result"]`
  (inside `.Contains()`), `PSObject.Properties[...]` (a member-collection
  indexer that returns `$null`, does not throw), and hashtable lookups on maps
  the function built itself.
- **Every remaining dot-access on wire-derived data is guarded**, verified by
  reading each in its data flow:
  - `Get-ExtDirectResult`: `$first` null-checked; `.Contains` behind
    `-is [IDictionary]`; `.PSObject` is an intrinsic present on any non-null
    object; `$resultProp.Value` behind a null check.
  - `Get-AllDashboards`: same shape.
  - `Get-AllViews` / `Get-AllReports`: `$grouped` / `$raw` non-null by
    `-RequireResult`; every further hop is `PSObject.Properties` + a type test.
  - `Remove-Dashboards` (`$_.id`/`$_.name`) and `Remove-Reports`
    (`$_.Uuid`/`$_.Name`) read `$toDelete`, hashtable literals built three lines
    earlier in the same function with exactly those keys. Safe by construction —
    and each has exactly one call site, verified by grep.
  - `$Ctx.Names` / `$Ctx.Warnings` are registry-loop-constructed.

**I concur with the claim: zero Ext.Direct- or dashboard.action-derived reads
remain unguarded on the uninstall path.**

### The deliberately-unfixed site (`:2009 $opsData.csrfToken`)

Leaving it does **not** make the sweep incoherent. It is cookie-derived, on the
login path, inside a `try` whose `catch` calls `Write-Fail` — it fails **closed**
with an operator sentence that quotes the exception (which names `csrfToken`).
See NIT-1 for the one cosmetic consequence.

---

## 4. #121 — the asymmetry is real

Read both poll loops:

- `install.py:481` — `if s.status_code != 200: _die(f"Import status check failed ({s.status_code}): {s.text}")`.
  The poll dies on the **first** non-200, so `state` at timeout always came from
  a 200 and can only be `""` in the weaker sense "the 200 omitted the member".
- `install.ps1:1007-1038` — deliberately keeps polling through a non-200. That
  tolerance is what makes `state=` ambiguous between "the server said nothing was
  happening" and "we never got a usable answer".

**The asymmetry is real and the pin is the right guard**: the new
`test_python_installer_has_no_matching_gap` asserts the exact `_die` string, so
if Python ever starts tolerating a non-200 the test breaks and forces the
last-seen tracking. Correct place to pin.

The new sentence also matches its in-file sibling exactly: `:877`
`"Marker-probe export timed out; state=$st (last status HTTP $sc)"` vs `:1038`
`"Import of $Label timed out; state=$state (last status HTTP $sc)"`. Parity
within install.ps1 is genuine.

See **WARNING-1** for the half of the parity question the pin does not cover.

---

## 5. Coverage — negative controls spot-checked

I built six mutants from the real template into scratch copies (no `src/` edit)
and ran the committed harness against each. **All six fail on the exactly
correct assertion**, none pass:

| Mutant | Harness result |
|---|---|
| **The partial-fix trap you named**: `Get-AllViews` reverted to `Get-PropValue $result[0] "result"` (member read guarded, index still raw) | exit 1 — `FAIL: Get-AllViews on an empty envelope array: operator sentence, not IndexOutOfRangeException` |
| `-RequireResult` dropped from `Get-AllReports` | exit 1 — `FAIL: Get-AllReports refuses result:null instead of dereferencing it` |
| Unary comma dropped from `Get-ExtDirectResult`'s return | exit 1 — `FAIL: a 1-element array result is NOT unrolled on return` |
| `-Encoding UTF8` dropped from `Load-JsonFile` | exit 1 — `FAIL: no Get-Content call decodes with the host default: 420:` |
| `Uninstall-Views` reverted to the `if ($v.viewDefinitionKey)` dot-access | exit 1 — `FAIL: a view thumbnail carrying viewDefinitionKey but NO id does not throw` |
| #121 sentence reverted to bare `state=$state` | exit 1 — `FAIL: the bare state= timeout sentence is gone` |

The partial-fix trap is genuinely trapped, and it fails on the *index* assertion
specifically — which is the whole point.

### The self-reported harness hole

`Get-AllDashboards` reads `$script:CsrfToken` in its form fields; under
StrictMode an unset script variable is a terminating error, so an assertion
could have "passed" against a cannot-be-retrieved error rather than the guard.
The fix (`$script:CsrfToken = "test-csrf"`, `$script:OpsHost = "ops.test"`) is
real — the harness now exercises `Get-AllDashboards` for real, proven by mutant
5 above failing on a `Get-AllDashboards`-adjacent path and by the three healthy
`Get-AllDashboards` assertions passing.

**No sibling assertion has the same defect.** I enumerated every script-scope
variable read by the 39 imported functions: exactly five —
`CsrfToken` (now set), `BaseUrl` and `Token` (only read by `Invoke-Api`, which
the harness stubs at :296), and `AdvisoryNameMaxChars` / `AdvisoryNamesMax`
(imported from the template by the harness's own `$script:Advisory*` assignment
sweep at :63). Nothing else can silently throw.

Separately, every `-notlike` (negative) assertion in the new block is paired with
a positive `-like` on the same `$msg`, so none of them can pass on a spurious
unrelated error. Checked all four pairs.

---

## 6. Dimension walk

1. **Global-default / pak-specific leak (`00d3382`)** — n/a; no renderer, no
   builder, no coordinate/default surface touched.
2. **Key/label derivation (`6c59f6b`)** — n/a.
3. **Wire-format conformance** — `knowledge/context/api-surface/dashboard_delete_api.md` is
   *extended*, not contradicted: the added section documents the client-side
   read contract for the same envelope shape already recorded there. Every
   factual claim in the new section I reproduced myself (section 2 above). The
   request shapes (`deleteView` array-wrapped data, `deleteReportDefinitions`
   bare-dict data) are untouched by this diff — verified by reading
   `Remove-View` / `Remove-Reports`.
4. **Loader / validator correctness** — n/a; RULE-006/007 surfaces untouched.
5. **Render regression** — n/a.
6. **Builder / pak structure** — n/a.
7. **Corpus regression** — validate chain 7/7, suite at parity with main's
   environmental baseline.
8. **Silent capability change** — this diff adds *loud* refusals
   (`Get-AllDashboards` and `-RequireResult` now `Write-Fail`) where the previous
   behaviour was either a raw exception or a quiet degrade to
   `not found (already removed?)`. That is the correct direction per
   `knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md` ("unknown is
   never the reassuring branch"). Blast radius is bounded: all three list
   functions have exactly one call site each, all on the **uninstall** path, and
   all refuse **before** any delete. No install path is reachable.
9. **Stale-zip discipline and the signal about it** — this touches
   `src/vcfops_packaging/templates/`, so **all dist zips are stale**.
   `CURRENT_TEMPLATE_VERSION` bumped `2026-08-23-1` -> `2026-08-24-1`: one bump,
   monotonic, matches `test_template_version_staleness`'s
   `\d{4}-\d{2}-\d{2}-\d+` format, and both `builder.py:729` and
   `discrete_builder.py:850` stamp it into `vcfops_manifest.json` where
   `cli.py:538` `check-staleness` compares it. **The signal is correct** — this
   is the PR #105 miss, and it is not repeated here. See REQUIRED ACTION below.
10. **Test coverage** — +45 harness assertions, +14 pytest cases, all six of my
    mutants caught. Strong.

---

## Findings

### BLOCKING
None.

### WARNING

**W-1. `install.py`'s prior-export wait loop has the exact #121 defect, in the
opposite direction, and the new test's docstring asserts it does not.**
`tests/test_install_ps1_tls_and_advisories.py` (`test_python_installer_has_no_matching_gap`)
states *"Both installers name a status on the path where one exists; only the
shapes differ."* That is false. `install.py:401-410`:

```python
while True:
    g = self._req("GET", "/api/content/operations/export")
    if g.status_code == 200:
        st = (g.json() or {}).get("state", "")
        if st not in ("RUNNING", "INITIALIZED"):
            break
    if time.monotonic() > deadline:
        _die("Timed out waiting for prior export to finish")
    time.sleep(2)
```

This loop **tolerates a non-200** (it only breaks inside the 200 branch), which
is precisely the tolerance #121 says creates the ambiguity — and its timeout
names neither a status nor a state. Its PowerShell sibling `install.ps1:847`
*was* given `(last seen: $lastSeen)` in PR #120. So Python is one loop behind
PowerShell on exactly this class. The narrow sentence in the docstring ("this is
NOT a case of Python naming the status and PowerShell not") is true; the general
one is not, and it is the general one a future reader will act on.

*Why WARNING, not BLOCKING:* diagnostic-only, pre-existing, and outside the line
#121 names (`install.ps1:887`). Widening a gated diff is the thing #116 itself
was split out to avoid.
**Fix:** correct the docstring sentence to scope its claim to the *import* poll,
and file a follow-up issue for `install.py:408`.

**W-2. The `-RequireResult` guarantee stops one level short: a present-but-
wrong-shaped `result` still degrades to an empty list.**
`install.ps1:2148` (`Get-AllViews`) — `if ($grouped -is [PSCustomObject]) {...}`
with no `else`, so a `result` that is a string, a bool, or `[]` falls through and
returns an **empty** `$allViews`, and `Uninstall-Views` then prints
`View not found (already removed?)` for every requested view.
`install.ps1:2216-2225` (`Get-AllReports`) — the final flatten fallback likewise
returns an empty `$items` for any unrecognised object shape.

This is the residual-`else`-with-a-confident-sentence shape named verbatim in
`knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md`, whose own
example list includes *"an uninstall reporting `not found (already removed?)`
from a lookup that had failed"*. The diff's comments and the new wire-format
section read as though the class is closed for this family; it is closed for
absent/null/empty-envelope, not for wrong-shape.

*Why WARNING, not BLOCKING:* pre-existing and **unchanged** by this diff, and it
needs a well-formed Ext.Direct envelope carrying a wrongly-typed `result`, which
is a much narrower trigger than the error/empty envelope the diff does close.
**Fix (follow-up issue, not this diff):** give both `else` paths a `Write-Fail`
in the same voice as the existing refusal, rather than returning an empty list.

**W-3. `-Encoding UTF8` changes 5.1 behaviour for a genuinely non-UTF-8 bundle
file, and nothing records that trade.**
On 5.1 a hand-edited ANSI `bundle.json` previously decoded correctly and now
decodes to U+FFFD. This is the right trade (factory-generated bundles are always
UTF-8; `install.py` writes them with `encoding="utf-8"`, and there are **zero**
PowerShell write sites in the template — verified by grep for
`Out-File|Set-Content|WriteAllText`), but the "leave `ReadAllText` alone" note in
`guide_powershell.md` records the *other* direction and not this one.
**Fix:** one sentence in the `guide_powershell.md` #119 section.

### NIT

**N-1. `install.ps1:2009-2013` — the `csrfToken not found` branch is unreachable,
so the operator gets the wrong sentence.** Under StrictMode `$opsData.csrfToken`
throws when the member is absent, so control goes to
`Write-Fail "Failed to decode OPS_SESSION cookie: $_"` — which claims decoding
failed when decoding succeeded — and the accurate
`"csrfToken not found in OPS_SESSION payload"` two lines down can never fire.
Fails closed and the exception text does name `csrfToken`, so the operator is not
misled far. Deliberately out of scope is fine; the dead branch is the incoherence,
not the unguarded read.

**N-2. The harness stubs `Remove-Dashboards`, so its `$_.id` / `$_.name` reads are
covered by inspection only.** They are safe today (`$toDelete` is a local
hashtable literal with exactly those keys). But if a future change ever passed
`$allDash` (wire objects) straight through, no test fires. The stub is justified
in-comment; worth one static assertion that `Remove-Dashboards` is only ever
called with a locally-built list.

**N-3. `install.ps1:1006` `$sc = 0` is dead** — the loop always assigns `$sc`
before the timeout check can be reached. Harmless; keeps the variable in scope.

---

## REQUIRED ACTION before the PR merges (not a finding, a process gate)

Per CLAUDE.md "After tooling changes": this diff touches
`src/vcfops_packaging/templates/`, so **every zip in `dist/` is stale.**
Delegate a full `content-packager` rebuild of every manifest in `bundles/`.
The version stamp is correctly bumped (so previously distributed copies *will*
now report stale to `check-staleness`), but that only tells operators to rebuild
— it does not rebuild our own artifacts.

---

## If shipped as-is

An operator running an uninstall against an instance that answers with an error
page, an expired session, or an empty Ext.Direct envelope gets a plain sentence
naming the step and the server's own message, and **nothing is deleted**, instead
of a raw `IndexOutOfRangeException` / `PropertyNotFoundException` partway through
removal. Views whose thumbnails carry `viewDefinitionKey` but no `id` — the
common case, and the one that previously killed the run at the guard itself —
now uninstall normally. A Windows PowerShell 5.1 customer stops silently
installing mojibake content names from a UTF-8 bundle. A native-Windows Python
install with redirected stdout stops crashing *after* the import already
succeeded. An import timeout names the last-seen HTTP status instead of a bare
`state=`.

The three WARNINGs are diagnostic-quality follow-ups on pre-existing behaviour,
not regressions introduced here.

---

# Confirmation round (2026-08-24, same worktree branch)

All three WARNINGs folded in rather than filed. Narrow pass on the delta only;
nothing cleared in the first round was re-opened.

**Verdict: APPROVE.** 0 BLOCKING, 0 WARNING, 4 NIT (3 carried, 1 new).

## Re-run claims

| Claim | My result |
|---|---|
| 979 passed / 6 failed / 13 skipped | **matches** (71s). Same 6 environmental sdk-adapter-clone failures, identical set to round 1, so unchanged. |
| installer module 58 | **58 passed** |
| harness 188 assertions | **188 `pass:` lines, exit 0, ALL ASSERTIONS PASSED** |
| pwsh AST parse 17888 tokens | **errors=0, tokens=17888** — exact |
| validate chain 7/7 | **7/7 PASS** |
| `CURRENT_TEMPLATE_VERSION` `2026-08-24-1`, one bump | **confirmed**: one line, `2026-08-23-1` -> `2026-08-24-1`, monotonic, format-valid |
| path audit clear | passes as part of the suite |
| 29 negative controls, 0 uncaught | **not certifiable by me** — they are ad hoc, not committed. See below for what I can attest. |

*Process note against myself:* one command block in this round backgrounded its
own `cd` (`cd worktree && (...) &`), so the following commands ran against the
**main** repo and reported main's numbers (132 assertions, 17180 tokens,
`2026-08-23-1`, 38 tests). I caught it, re-ran everything in the worktree with
explicit cwd, and the numbers above are the corrected ones. Recording it because
this review's whole premise is that unverified numbers are claims.

## W-1 — residual else, wrong-shape `result`

Verified with **my own driver and my own stubs**, extracting the four functions
from the template by AST rather than going through tooling's harness, so this is
not self-confirming.

**Legitimate-empty cases — all four return zero and none refuses:**

| Input | Result |
|---|---|
| views `result:{}` | OK, count=0 |
| reports `result:[]` (bare empty array) | OK, count=0 |
| reports `result:{"records":[],"total":0}` | OK, count=0 |
| dashboards `{"dashboards":[]}` | OK, count=0 |

**The claimed asymmetry is real in both directions**, which was the specific
thing to confirm rather than assume:

- `Get-AllReports` returns at `-is [System.Array]` **before** the fallback, so a
  bare `[]` is accepted as the documented shape. Only a scalar reaches the else.
- `Get-AllViews` has no array branch, so `[]` is wrong-shape and refuses.

**Wrong shapes refuse, naming the shape received:**
views `[]` -> `unrecognised shape (Object[])`; `"a string"` -> `(String)`;
`true` -> `(Boolean)`; **`42` -> `(Int64)`** (my own addition, not in the
harness, also correct). reports `"a string"` -> `(String)`; `true` -> `(Boolean)`.
dashboards `{"other":1}` -> the no-`dashboards`-field refusal. Healthy paths
(2 views, 1 report via `records`, 2 reports via bare array, 1 dashboard) all
unchanged.

**Negative controls — all three fire**, including the one that matters:

| Mutant | Harness |
|---|---|
| **`Write-Fail` -> `Write-Warn` in `Get-AllViews`** (a warning followed by an empty list: the same false claim in a quieter voice) | exit 1 — `FAIL: Get-AllViews refuses a result of shape "a string" rather than reporting zero views` |
| **`Write-Fail` -> `Write-Warn` in `Get-AllReports`** | exit 1 — `FAIL: Get-AllReports refuses a result of shape "a string"...` |
| views `else` branch deleted entirely (back to a silent empty list) | exit 1 — same assertion |

The `Write-Warn` mutants do not throw, so they return the empty list and the
`Get-Thrown` assertion catches the absence of a refusal. That is the correct
catch mechanism, not an accident of the message text.

## W-2 — the false docstring, and the real gap

Both halves done. `install.py:404-421` now mirrors `install.ps1:833-847`: same
`last_seen = "no status response yet"` initial, same 200-branch
`last_seen = f"state={st}"`, same `else: last_seen = f"HTTP {g.status_code}"`,
same `(last seen: ...)` sentence. Read both side by side.

**The rename is accurate to what the test now proves.**
`test_python_import_poll_cannot_reach_the_ambiguous_state` asserts exactly one
thing — that `install.py`'s **import** poll still `_die`s on the first non-200 —
and its name says exactly that and nothing more. The old name asserted a
whole-file property the body never tested. The docstring is rewritten rather than
deleted: it states the previous claim, that it was false, and where the real case
is now covered. That is the right shape for a corrected record.

**Negative control fires.** I ran the test's own assertions verbatim against a
mutant with **only** the `else: last_seen = f"HTTP {g.status_code}"` branch
removed and `(last seen: {last_seen})` left in place — the version that looks
fixed. Baseline passes; mutant fails on `non-200 branch missing`. The third
assertion, not the sentence check, is what catches it. Correct.

## W-3 — the guide sentence

**Measured, and it matches:** on-disk `43 61 66 E9` read with `-Encoding UTF8`
returns `U+0043 U+0061 U+0066 U+FFFD`; the same bytes through a cp1252 decoder
return `U+0043 U+0061 U+0066 U+00E9` (`Café`). Reproduced myself.

The guide states it **as a chosen trade**, not an oversight: it names what is
lost, why the trade is correct here (the factory writes bundles as UTF-8 and
there are zero PowerShell write sites in the shipped installer, which I verified
independently by grep for `Out-File|Set-Content|WriteAllText`), and gives a
boundary for the next reader ("weigh it again before pinning a read whose input a
human is expected to author by hand in a Windows editor"). That is better than
what I asked for.

## Count dispute

Agreed and closed. Both counts describe the same corpus; tooling's 35/9 were
distinct source-level reads after collapsing nested composites and excluding
transports and statics, which is a legitimate denominator that simply was not
stated. No action.

## Findings

### BLOCKING / WARNING
None.

### NIT

**N-4 (new). The per-endpoint legitimate-shape asymmetry lives only in code
comments and harness assertions, not in the wire-format doc.** That views accept
`{}` but refuse `[]`, while reports accept both `[]` and `{"records":[]}`, is
the single most "fix this into symmetry" -prone thing in the diff, and
`knowledge/context/api-surface/dashboard_delete_api.md`'s new shape table does not
record it. Both `else` branches explain themselves in place, so a reader editing
*that* line is safe; a reader starting from the wire doc is not.
**Fix:** two rows in the existing shape table.

**N-1, N-2, N-3 carried unchanged** from the first round (unreachable
`csrfToken not found` branch; `Remove-Dashboards` stubbed so its reads are
covered by inspection only; dead `$sc = 0`). None blocks.

*Observation, deliberately not raised as a finding:* `Get-AllViews`' inner loops
still skip a non-conforming subject bucket or view list silently, which can
under-populate the name->id map inside an otherwise well-formed envelope. That is
a strictly narrower version of what W-1 just closed, one level deeper, and
raising it now would be scope creep on a confirmation pass. Worth a future issue,
not this PR.

## If shipped as-is

Unchanged from the first round, plus: an uninstall against an instance whose UI
API answers with a well-formed envelope carrying a wrongly-typed `result` now
refuses by name and shape instead of quietly reporting "already removed?" about
content that is still there; and a Python installer whose prior-export wait times
out now says whether it was looking at HTTP 503s or a genuinely stuck export,
matching its PowerShell sibling word for word.
