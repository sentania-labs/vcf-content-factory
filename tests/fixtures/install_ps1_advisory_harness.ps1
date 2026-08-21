# Behaviour harness for the install.ps1 advisory helpers (issue #104).
#
# Extracts the functions under test verbatim from the real template with the
# PowerShell AST, stubs their collaborators, and drives the imported=0 /
# skipped>0 paths without a live VCF Operations instance.
#
# Invoked by tests/test_install_ps1_tls_and_advisories.py, which passes the
# template path as the single positional argument.  Exits non-zero on the
# first failed assertion.
#
# NOTE: this runs under whatever PowerShell is on the box (pwsh 7 on the
# factory's POSIX runners).  Passing here does NOT prove Windows PowerShell
# 5.1 compatibility; only a windows-latest runner can prove that.
param([Parameter(Mandatory = $true)][string]$TemplatePath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($TemplatePath, [ref]$tokens, [ref]$errors)
if ($errors) { throw "install.ps1 has parse errors" }

$want = @("Write-Ok", "Write-Warn", "Get-PropValue", "Get-BoundedNames",
          "Get-DashboardAdvisoryNames", "Get-ViewAdvisoryNames",
          "Get-AllSkippedSummaries", "Write-AdvisoryTrailer",
          "Write-ImportSummaryWarnings", "Install-Dashboard")
$found = New-Object System.Collections.Generic.List[string]
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($f in $fns) {
    if ($want -contains $f.Name) {
        Invoke-Expression $f.Extent.Text
        $found.Add($f.Name)
    }
}
foreach ($w in $want) {
    if ($found -notcontains $w) { throw "function $w not found in install.ps1" }
}

# The bounds the helpers read are script-scope assignments, not functions, so
# they are replayed from the template's own AST rather than restated here.
# Restating them would let the template's bounds drift while the "clipped to
# 120 chars" assertion below kept passing against divergent shipped code.
$boundsFound = 0
$assignments = $ast.FindAll({
    param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst]
}, $true)
foreach ($a in $assignments) {
    if ($a.Left.Extent.Text -like '$script:Advisory*') {
        Invoke-Expression $a.Extent.Text
        $boundsFound++
    }
}
if ($boundsFound -ne 2) { throw "expected 2 advisory bound assignments, found $boundsFound" }

# --- stubs for Install-Dashboard collaborators -----------------------------
$script:StubImportResult = $null
$script:StubFiles = @{}
function Load-RawTextFile($Path) { return $script:StubFiles[$Path] }
function Get-DashboardIds { param($DashJson, $OwnerId) return @("id1") }
function New-DashboardZip {
    param($ViewsXml, $DashJson, $Marker, $OwnerId, $NViews, $NDashboards, $DashboardIds)
    return [byte[]]@(1, 2)
}
function Import-ContentZip { param($ZipBytes, $Label) return $script:StubImportResult }
function Test-Path { param($LiteralPath) return $true }
function Join-Path { param($Path, $ChildPath) return $ChildPath }

function Assert($cond, $msg) {
    if (-not $cond) { throw "FAIL: $msg" }
    Write-Host "  pass: $msg"
}

# --- Get-PropValue ---------------------------------------------------------
# The whole point of this helper is that StrictMode is on: a dot-access to a
# missing member here is a terminating error, and on the import path that
# aborts the installer after content has already landed.
$resp = '{"state":"FINISHED"}' | ConvertFrom-Json
Assert ($null -eq (Get-PropValue $resp "operationSummaries")) "missing member returns null instead of throwing"
Assert ((Get-PropValue $resp "state") -eq "FINISHED") "present member returned"
Assert ($null -eq (Get-PropValue $null "state")) "null object tolerated"
$errShape = @{ __statusCode = 500; __body = "boom" }
Assert ((Get-PropValue $errShape "__statusCode") -eq 500) "hashtable (Invoke-Api error shape) supported"
Assert ($null -eq (Get-PropValue $errShape "operationSummaries")) "hashtable missing key returns null"

# --- Write-ImportSummaryWarnings -------------------------------------------
# This is the REAL function Import-ContentZip calls, not a stub.  Before the
# split it was inline, and 'if ($s.operationSummaries)' threw on exactly the
# first input below.
$out = @(Write-ImportSummaryWarnings -Status ('{"state":"FINISHED"}' | ConvertFrom-Json) 6>&1)
Assert ($out.Count -eq 0) "status envelope without operationSummaries: no output, no throw"
$out = @(Write-ImportSummaryWarnings -Status $null 6>&1)
Assert ($out.Count -eq 0) "null status tolerated"
$out = @(Write-ImportSummaryWarnings -Status ('{"operationSummaries":[{"contentType":"DASHBOARDS"}]}' | ConvertFrom-Json) 6>&1)
Assert ($out.Count -eq 0) "summary missing state/failed/skipped/imported: no throw"
$mixed = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"DASHBOARDS","imported":1,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":2,"skipped":0,"failed":0,"state":"FINISHED"},
 {"contentType":"REPORTS","imported":0,"skipped":0,"failed":1,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$out = @(Write-ImportSummaryWarnings -Status $mixed 6>&1)
Assert ($out.Count -eq 2) "failures and skips warn; a clean type stays quiet"
Assert (($out -join "`n") -notlike "*VIEW_DEFINITIONS*") "imported>0 with no skips produces no line"
Assert (@($out | Where-Object { $_ -like "WARN: content type REPORTS:*failed=1*" }).Count -eq 1) "failure line names the type and counts"

# REGRESSION GUARD: SUPER_METRICS and REPORTS get NO named advisory (that
# layer covers DASHBOARDS / VIEW_DEFINITIONS only), so this mid-stream line is
# their only signal.  Narrowing the condition to imported=0 deleted it and
# left an all-skipped super metric import reporting "OK  Imported N super
# metric(s)" over an unchanged instance.  install.py:454 warns on skipped>0
# for every content type; this must match it.
$smAllSkipped = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"SUPER_METRICS","imported":0,"skipped":4,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$out = @(Write-ImportSummaryWarnings -Status $smAllSkipped 6>&1)
Assert ($out.Count -eq 1) "all-skipped SUPER_METRICS import warns"
Assert ($out[0] -like "WARN: content type SUPER_METRICS:*imported=0*skipped=4*") "the SUPER_METRICS warning names the type and both counts"
$reportsSkipped = '{"operationSummaries":[{"contentType":"REPORTS","imported":0,"skipped":2,"failed":0,"state":"FINISHED"}]}' | ConvertFrom-Json
$out = @(Write-ImportSummaryWarnings -Status $reportsSkipped 6>&1)
Assert ($out[0] -like "WARN: content type REPORTS:*skipped=2*") "all-skipped REPORTS import warns"

$single = '{"operationSummaries":[{"contentType":"REPORTS","imported":0,"skipped":0,"failed":2,"state":"FINISHED"}]}' | ConvertFrom-Json
$out = @(Write-ImportSummaryWarnings -Status $single 6>&1)
Assert ($out.Count -eq 1) "single-element operationSummaries survives pipeline unwrap"

# --- Get-BoundedNames ------------------------------------------------------
$r = Get-BoundedNames -Names @("a")
Assert ($r.Count -eq 1 -and $r[0] -eq "a") "single element stays an array of 1 (no pipeline unwrap)"
Assert ((Get-BoundedNames -Names @()).Count -eq 0) "empty in, empty out"
$r = Get-BoundedNames -Names @("x" * 200)
Assert ($r[0].Length -eq 123 -and $r[0].EndsWith("...")) "long name clipped to 120 chars"
$r = Get-BoundedNames -Names (1..25)
Assert ($r.Count -eq 21 -and $r[20] -eq "and 5 more") "capped at 20 with 'and N more' tail"
Assert ($r[0] -eq "1") "non-string name coerced instead of throwing"

# --- Get-AllSkippedSummaries ----------------------------------------------
$resp = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"DASHBOARDS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":1,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"SUPERMETRICS","imported":0,"skipped":3,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$f = Get-AllSkippedSummaries -Result $resp -ContentTypes @("DASHBOARDS", "VIEW_DEFINITIONS")
Assert ($f.ContainsKey("DASHBOARDS")) "imported=0/skipped=1 is flagged"
Assert (-not $f.ContainsKey("VIEW_DEFINITIONS")) "imported=1/skipped=1 is NOT flagged"
Assert (-not $f.ContainsKey("SUPERMETRICS")) "content type outside the filter ignored"
Assert ($f["DASHBOARDS"].Imported -eq 0 -and $f["DASHBOARDS"].Skipped -eq 1) "counts carried through"
Assert ((Get-AllSkippedSummaries -Result $null -ContentTypes @("DASHBOARDS")).Count -eq 0) "null response tolerated"
$noSum = '{"state":"FINISHED"}' | ConvertFrom-Json
Assert ((Get-AllSkippedSummaries -Result $noSum -ContentTypes @("DASHBOARDS")).Count -eq 0) "missing operationSummaries is StrictMode safe"
$junk = '{"operationSummaries":[{"contentType":"DASHBOARDS","imported":"x","skipped":2}]}' | ConvertFrom-Json
Assert ((Get-AllSkippedSummaries -Result $junk -ContentTypes @("DASHBOARDS")).Count -eq 0) "non-numeric counts skipped without throwing"

# --- name extraction -------------------------------------------------------
$dashJson = '{"dashboards":[{"id":"abc","name":"[VCF Content Factory] My Dash","owner":"PLACEHOLDER_USER_ID"}]}'
$n = Get-DashboardAdvisoryNames -DashJson $dashJson -OwnerId "u1"
Assert ($n.Count -eq 1 -and $n[0] -eq "[VCF Content Factory] My Dash") "dashboard name extracted"
Assert ((Get-DashboardAdvisoryNames -DashJson "not json" -OwnerId "u1").Count -eq 0) "malformed json degrades to no names"
Assert ((Get-DashboardAdvisoryNames -DashJson '{"dashboards":"oops"}' -OwnerId "u1").Count -eq 0) "non-array dashboards value yields no names, matching install.py"
Assert ((Get-DashboardAdvisoryNames -DashJson '{"dashboards":[{"id":"only-id"}]}' -OwnerId "u1")[0] -eq "only-id") "falls back to id"

$viewsXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Content><Views>' +
    '<ViewDef id="1"><Title>[VCF Content Factory] CPU &amp; Memory</Title></ViewDef>' +
    '<ViewDef id="2" name="attr-fallback"><Description>no title</Description></ViewDef>' +
    '</Views></Content>'
$v = Get-ViewAdvisoryNames -ViewsXml $viewsXml
Assert ($v.Count -eq 2) "one name per ViewDef"
Assert ($v[0] -eq "[VCF Content Factory] CPU & Memory") "entities decoded"
Assert ($v[1] -eq "attr-fallback") "name attribute fallback"
Assert ((Get-ViewAdvisoryNames -ViewsXml "<Content><unclosed>").Count -eq 0) "malformed xml degrades to no names"
Assert ((Get-ViewAdvisoryNames -ViewsXml "").Count -eq 0) "empty xml degrades to no names"

# --- Install-Dashboard -----------------------------------------------------
$script:StubFiles = @{ "/b/dash.json" = $dashJson; "/b/views.xml" = $viewsXml }
function New-Ctx {
    return @{
        BundleDir  = "/b"
        Manifest   = ([pscustomobject]@{ content = [pscustomobject]@{
            dashboards = [pscustomobject]@{ file = "/b/dash.json" }
            views      = [pscustomobject]@{ file = "/b/views.xml" } } })
        Marker     = "m"
        OwnerId    = "u1"
        Warnings   = [System.Collections.Generic.List[string]]::new()
        Advisories = [System.Collections.Generic.List[string]]::new()
    }
}

$script:StubImportResult = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"DASHBOARDS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$ctx = New-Ctx
Install-Dashboard $ctx
Assert ($ctx.Advisories.Count -eq 2) "no-op import produces one advisory per content type"
Assert ($ctx.Warnings.Count -eq 0) "advisories stay out of the exit-code warnings list"
Assert ($ctx.Advisories[0].Contains("NOT updated: [VCF Content Factory] My Dash.")) "dashboard named in its advisory"
Assert ($ctx.Advisories[1].Contains("CPU & Memory")) "views named in their advisory"

$script:StubImportResult = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"DASHBOARDS","imported":1,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":1,"skipped":1,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$ctx = New-Ctx
Install-Dashboard $ctx
Assert ($ctx.Advisories.Count -eq 0) "a re-sync that imports 1 and skips 1 stays quiet"

$script:StubImportResult = @'
{"state":"FINISHED","operationSummaries":[
 {"contentType":"DASHBOARDS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":1,"skipped":0,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
$ctx = New-Ctx
Install-Dashboard $ctx
Assert ($ctx.Advisories.Count -eq 1 -and $ctx.Advisories[0].Contains("no dashboards")) "attribution is per content type"

# Import-ContentZip is stubbed here, so this covers Install-Dashboard's own
# handling of a bare envelope and NOT the polling code inside
# Import-ContentZip.  That path is covered for real by the
# Write-ImportSummaryWarnings block above; do not read this assertion as
# coverage of it.
$script:StubImportResult = '{"state":"FINISHED"}' | ConvertFrom-Json
$ctx = New-Ctx
Install-Dashboard $ctx
Assert ($ctx.Advisories.Count -eq 0) "Install-Dashboard on a bare envelope takes the clean-install path"

# --- trailer ---------------------------------------------------------------
$out = @(Write-AdvisoryTrailer -Advisories @() 6>&1)
Assert ($out.Count -eq 0) "no advisories means no trailer"
$out = @(Write-AdvisoryTrailer -Advisories @("[bundle] something") 6>&1)
Assert ($out.Count -eq 3 -and $out[1] -like "1 item(s) need attention*" -and $out[2] -like "  ATTENTION  *") "trailer shape"
$empty = [System.Collections.Generic.List[string]]::new()
Assert ((@(Write-AdvisoryTrailer -Advisories $empty.ToArray() 6>&1)).Count -eq 0) "empty List.ToArray() accepted by the typed parameter"

Write-Host "ALL ASSERTIONS PASSED"
