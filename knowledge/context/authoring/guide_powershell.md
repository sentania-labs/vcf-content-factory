# PowerShell rules

Hard requirements for PowerShell install scripts. PS 5.1
compatibility is non-negotiable.

## PS 5.1 compatibility is a hard requirement

Install scripts must parse under PowerShell 5.1 (Windows PowerShell):
- ASCII-only in all strings, comments, and throw messages (non-ASCII
  causes mojibake under default Windows encoding)
- Never start a continuation string literal with `&` (parsed as the
  call operator)
- QA passing on pwsh 7 does NOT guarantee 5.1 compat

## TLS 1.2 must be forced, unconditionally (issue #106)

Windows PowerShell 5.1 runs on .NET Framework and inherits its default
protocol list, which on many machines still resolves to SSL3/TLS 1.0.
VCF Operations requires TLS 1.2+, so every request fails at connection
time. PowerShell 7 runs on .NET Core and negotiates the system default,
which is why this is invisible on pwsh:

```powershell
if ($PSVersionTable.PSVersion.Major -lt 6) {
    [System.Net.ServicePointManager]::SecurityProtocol =
        [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
}
```

- Runs unconditionally, before the first request. Never nest it inside a
  cert-bypass branch: protocol selection and certificate verification are
  unrelated concerns, and gating one on the other breaks only the operator
  doing the more secure thing.
- `-bor`, not `=`, so an explicitly-configured protocol list is preserved.
  Be honest about the tradeoff: where the current value is `SystemDefault`
  (`0`, the .NET Framework 4.7+ default), `0 -bor Tls12` is `Tls12`, so
  OS-negotiated TLS 1.3 is given up, not kept. Accept that cost rather
  than making the block conditional. Pinning wrongly costs one
  short-lived installer process TLS 1.3; skipping wrongly costs a hard
  connection failure, which is the reported bug. `SecurityProtocol -eq 0`
  is not a reliable proxy for "OS negotiation is healthy" on a machine
  with SCHANNEL policy or `SystemDefaultTlsVersions` configured, and with
  no 5.1 runner the branch with the fewest untestable behaviors wins.
- `ICertificatePolicy` (the 5.1 cert-bypass interface) does not exist on
  .NET Core, so any `Add-Type` using it must be guarded by
  `Major -lt 6`. `Add-Type` also cannot redefine a type in one session:
  guard with `if (-not ('MyType' -as [type]))` rather than declaring a
  second near-identical class.

## Mirroring footguns

### `param()` variables are already script-scope
In a script (not a function), `param()` variables live in the script
scope, so `$script:Foo` and `$Foo` are the SAME variable. Writing
`$script:SkipSslVerify = $false` near the top to "initialize" a tracking
flag silently overwrites the `-SkipSslVerify` switch the operator passed,
before any call site reads it. That made both cert-bypass blocks in
`install.ps1` dead code for months, and turned a later guard into
`X -and -not X`. Give internal state its own name.

### StrictMode + PSCustomObject
Under `Set-StrictMode -Version Latest`, accessing a missing property
throws `PropertyNotFoundException`, and with
`$ErrorActionPreference = 'Stop'` that terminates the script. On an
install path this aborts AFTER content has landed, leaving a partial
install.

Two facts that are easy to get wrong, both measured under pwsh 7.5.1
with StrictMode Latest:

- **Hashtables throw too.** `@{a=1}.b` raises
  `PropertyNotFoundException`, same as a PSCustomObject. A missing
  hashtable key is not a quiet `$null`.
- **`PSObject.Properties` does not see hashtable keys.**
  `@{a=1}.PSObject.Properties['a']` is `$null` even though the key
  exists. So a probe helper written only for PSCustomObject silently
  reports "absent" for every key of a hashtable.

Any read of an API response therefore needs both branches, because a
client may return either shape (`install.ps1:Get-PropValue` returns
`$null` for absent members and handles both):

```powershell
if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) { return $Object[$Name] }
    return $null
}
$prop = $Object.PSObject.Properties[$Name]
if ($null -eq $prop) { return $null }
return $prop.Value
```

For a one-off read of an object you know is a PSCustomObject, the same
probe inline:

```powershell
$prop = $obj.PSObject.Properties[$key]
$value = if ($prop) { $prop.Value } else { $null }
```

**Do not use `?.`** (null-conditional). It is PowerShell 7 only and is a
**parse error** on 5.1, so it breaks the compatibility this whole guide
exists to protect. This guide previously recommended
`$obj.PSObject.Properties[$key]?.Value`, which was wrong: it advised the
exact class of syntax forbidden six lines above. Corrected 2026-08-21 after
an agent following the guide would have broken 5.1.

### The `if ($r.pageInfo)` guard cannot save itself
Measured while sweeping `install.ps1` for issue #109. This looks defensive
and is not:

```powershell
$total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
```

The guard's *own* `$r.pageInfo` is a member access, so on an envelope
lacking `pageInfo` it throws before the `else` branch can ever run. Under
StrictMode, "check it exists first" has to be done with a probe helper, not
with the access you are trying to protect. `install.ps1` now has two
derived helpers, both built on `Get-PropValue`:

- `Get-PropList $obj $name` — collection-valued member, **always** returns
  an array (absent, null, and empty all collapse to `@()`), so callers can
  iterate it and read `.Count` without special cases. Its `return ,@(...)`
  comma-wrap is load-bearing; see "Function return unwrap" below.
- `Get-PageTotalCount $resp` — the two-hop `pageInfo.totalCount` read every
  paging loop in the file uses. Returns `0`, which ends the loop.

Nested reads need a probe at **every** hop, not just the last one:
`$g.resourceKey.name` throws on the first dot when `resourceKey` is absent.

### A safe reader can create an unsafe decision
The trap the #109 sweep walked into, caught in review. Making a reader
StrictMode-safe is not the whole job:

```powershell
$resp = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name }
foreach ($g in (Get-PropList $resp "groups")) { ... }   # safe read
if ($existingId) { PUT } else { POST }                   # UNSAFE decision
```

`Get-PropList` correctly returns `@()` for an error envelope. But `@()` from
a *failed request* is indistinguishable from `@()` meaning *no such object*,
so a transient 500 on the lookup falls through to POST and **creates a
duplicate**, printing `OK  Created`. Before the guard this site threw, which
was uglier and strictly safer.

The rule: whenever a lookup result drives a **mutation** (create vs update,
delete vs skip) or a **claim about instance state** ("already removed?"),
check the status *before* acting on emptiness. `install.ps1:Assert-LookupOk`
does this and `Write-Fail`s; refusing is the only safe answer, because a
failed read means you do not know what is there.

Test it by asserting **zero mutating requests were sent**, not that something
threw. An assertion that only checks for an exception passes when the stubbed
mutation also errors, i.e. it tests the stub. Make the stubbed POST return
200 and count the POST/PUT/DELETEs.

### Void-by-receiver, never void-by-method-name
PowerShell appends every uncaptured expression to the enclosing function's
output stream, so one stray statement changes a function's return value. The
classic instance is `.Add()`:

```powershell
$list = New-Object System.Collections.ArrayList
$list.Add("x")        # returns the insertion INDEX -> lands on the output stream
```

`[List[T]].Add` returns void. `[ArrayList].Add` returns an int. `.Clear`,
`.Write` and `.RemoveAll` are receiver-dependent the same way. **The method
name cannot tell you whether a call is void; only the receiver can.**

Measured consequence in this repo: injecting those two lines into
`install.ps1:Import-ContentZip` flipped its return from `PSCustomObject` to
`Object[]`, which made `Get-SmGhostStateSkipCount` read `0` instead of `4` and
silently disabled the #108 super-metric ghost-state retry.

If you write a static check for this, key the allowlist on
`$receiver.Method`, not on `Method`. A name-keyed allowlist containing "Add"
excuses the exact bug the check exists to catch — that is not a weaker check,
it is a broken one, and it is easy to write while quoting the ArrayList
example in the comment directly above it.

### `Get-Content` with no `-Encoding` is not UTF-8 (issue #119)

The default differs by runtime, so the *same* script decodes the *same*
bundle differently depending on which PowerShell the customer runs:

- **5.1** (.NET Framework): the system **ANSI** code page, cp1252 on a
  US box.
- **7** (.NET Core): UTF-8, no BOM.

The failure is not a crash. Read UTF-8 bytes through a cp1252 decoder
and `ConvertFrom-Json` parses the mojibake without complaint, so the
install *succeeds* with corrupted content names on the instance.
Measured on Linux by forcing the cp1252 decoder explicitly:
`Café Überblick` came back as `CafÃ© Ãœberblick` and parsed fine.

Pin every read: `Get-Content -LiteralPath $p -Raw -Encoding UTF8`.

Two things worth knowing before "fixing" a neighbouring site:

- The BOM difference 5.1 has for `-Encoding UTF8` is a **write-side**
  behaviour (5.1 emits a BOM, 7 does not). On a **read** it only
  selects the decoder, and the `StreamReader` strips a leading BOM
  either way — verified: a BOM'd and a bare UTF-8 file decode
  identically. A future *write* site must still pin deliberately.
- `[System.IO.File]::ReadAllText($path)` already defaults to UTF-8 with
  BOM detection on **both** runtimes. It has never had this split.
  Leave it alone; do not convert it to `Get-Content` for consistency.
- **The pin trades one failure for another, and that is the choice.**
  On 5.1, `-Encoding UTF8` applied to a file that genuinely *is* ANSI
  turns every high byte into U+FFFD, so a hand-edited `bundle.json`
  saved as cp1252 loses characters instead of being read correctly.
  That trade is correct here because the factory writes bundles as
  UTF-8 and there are **zero** PowerShell write sites in the shipped
  installer, so no ANSI bundle can originate from us. Weigh it again
  before pinning a read whose input a human is expected to author by
  hand in a Windows editor.

The Python sibling is `encoding="utf-8"` on every `open` / `read_text` /
`write_text`, plus `sys.stdout.reconfigure(encoding="utf-8",
errors="replace")` so that **printing** a content name can never fail an
install that already succeeded (issue #118).

### Two failures in front of one read (issue #116)

`$result[0].type` is not one risky access, it is two, and they raise
**different** exceptions:

```powershell
@()[0]                  # IndexOutOfRangeException
(json '{}').missing     # PropertyNotFoundException
```

So routing the member read through `Get-PropValue` and stopping there
converts one raw .NET exception into another and looks fixed. Guard the
index first. Two traps while doing it:

- `@($null).Count` is **1**, not 0. A null response and an empty array
  are separate cases; folding them into one `Count` check leaves the
  null one live.
- A returned empty array becomes `$null` at the caller, so at *caller*
  level "empty array" and "null" collapse. Both branches still have to
  exist because parameter binding preserves `@()`.

### Pipeline unwrap of single-element arrays
PowerShell unwraps single-element collections on function return. Fix:
wrap in `@(...)` or use `Write-Output -NoEnumerate`.

### Typed collection parameters
Typed params reject unwrapped scalars. Accept `[object[]]` or wrap at
call site.

## Function return unwrap

`return $hashset` enumerates through the pipeline:
- Empty → `$null`
- Single-item → bare element
- Multi-item → `Object[]` (loses type)

Fix: `return ,$collection` (comma-wrap) or have callers use `@()`.
`Hashtable` and `PSCustomObject` survive intact.
