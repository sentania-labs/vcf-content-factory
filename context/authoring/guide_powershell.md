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

## Mirroring footguns

### StrictMode + PSCustomObject
Under `Set-StrictMode -Version Latest`, accessing a missing property
throws. Use `$obj.PSObject.Properties[$key]?.Value`.

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
