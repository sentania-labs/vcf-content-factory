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
