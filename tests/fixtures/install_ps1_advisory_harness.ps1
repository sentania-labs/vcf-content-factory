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
          "Write-ImportSummaryWarnings", "Install-Dashboard",
          # issue #109 -- StrictMode-safe reads of Invoke-Api results
          "Get-PropList", "Get-PageTotalCount", "Get-GroupName",
          "Get-StatusCode", "Get-DefaultPolicyId", "Get-SupermetricsByName",
          "Find-CustomGroupIds", "Upsert-CustomGroup", "Uninstall-Alerts",
          # the guard closing the create-on-failed-lookup class
          "Assert-LookupOk", "Install-Symptoms", "Uninstall-Supermetrics",
          "Uninstall-CustomGroups", "Remove-Supermetric", "Remove-CustomGroup",
          "Get-OwnerId", "Get-CurrentUser", "Get-MarkerFilename",
          # issue #108 -- SM ghost-state retry
          "Get-SmGhostStateSkipCount", "Install-Supermetrics",
          # issue #116 -- the Ext.Direct / dashboard.action envelope family
          "Get-ExtDirectResult", "Get-AllViews", "Get-AllReports",
          "Get-AllDashboards", "Remove-View", "Remove-Reports",
          "Uninstall-Views", "Uninstall-Reports", "Uninstall-Dashboards")
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

# ===========================================================================
# Issue #109 -- unguarded property reads on Invoke-Api results
# ===========================================================================
# Invoke-Api returns TWO shapes: a PSCustomObject from ConvertFrom-Json on
# success, and a plain hashtable (@{__statusCode; __body; __error}) on any HTTP
# error.  Under StrictMode a dot-access for a member absent from either shape
# is a terminating error, so an API hiccup produced a raw .NET exception rather
# than a sentence -- and several of these sites run AFTER content has already
# been imported, so it aborted a half-modified instance.
#
# $errShape below is that error hashtable.  Every read tested here is driven
# with it as well as with a well-formed envelope.
$errShape = @{ __statusCode = 500; __body = "boom"; __error = "exc" }

# --- Get-PropList ----------------------------------------------------------
Assert ((Get-PropList $errShape "policySummaries").Count -eq 0) "error envelope: absent collection member is an empty array, not a throw"
Assert ((Get-PropList $null "groups").Count -eq 0) "null object tolerated"
Assert ((Get-PropList ('{"groups":[]}' | ConvertFrom-Json) "groups").Count -eq 0) "empty collection stays empty (not null)"
$one = Get-PropList ('{"groups":[{"id":"g1"}]}' | ConvertFrom-Json) "groups"
Assert ($one.Count -eq 1 -and (Get-PropValue $one[0] "id") -eq "g1") "single-element collection survives the return unroll as an array of 1"
Assert ((Get-PropList ('{"groups":[{"id":"a"},{"id":"b"}]}' | ConvertFrom-Json) "groups").Count -eq 2) "multi-element collection passed through"

# --- Get-PageTotalCount ----------------------------------------------------
# The old `if ($r.pageInfo) { $r.pageInfo.totalCount }` guard could not save
# itself: its own dot-access threw before the guard was evaluated.
Assert ((Get-PageTotalCount $errShape) -eq 0) "error envelope: paging bound is 0, not a throw"
Assert ((Get-PageTotalCount $null) -eq 0) "null tolerated"
Assert ((Get-PageTotalCount ('{"pageInfo":{"totalCount":42}}' | ConvertFrom-Json)) -eq 42) "totalCount read"
Assert ((Get-PageTotalCount ('{"pageInfo":{}}' | ConvertFrom-Json)) -eq 0) "pageInfo without totalCount ends the loop"
Assert ((Get-PageTotalCount ('{"state":"FINISHED"}' | ConvertFrom-Json)) -eq 0) "envelope without pageInfo ends the loop"

# --- Get-GroupName (two-hop read) ------------------------------------------
Assert ((Get-GroupName ('{"resourceKey":{"name":"n"}}' | ConvertFrom-Json)) -eq "n") "nested name read"
Assert ($null -eq (Get-GroupName ('{"id":"g"}' | ConvertFrom-Json))) "group without resourceKey: first hop guarded"
Assert ($null -eq (Get-GroupName ('{"resourceKey":{}}' | ConvertFrom-Json))) "resourceKey without name: second hop guarded"
Assert ($null -eq (Get-GroupName $null)) "null group tolerated"

# --- functions that call Invoke-Api ----------------------------------------
# Queue-driven stub: response N is returned for the Nth call, the last entry
# repeats.  $script:ApiCalls doubles as the assertion that a paging loop
# terminates instead of spinning on a degenerate bound.
$script:ApiResponses = @()
$script:ApiCalls = 0
$script:ApiLog = [System.Collections.Generic.List[string]]::new()
function Invoke-Api {
    param($Method, $Path, $Headers, $Body, $Query)
    $i = $script:ApiCalls
    $script:ApiCalls++
    # Logged so a test can assert that a MUTATION did not happen, rather than
    # only that an error was raised.  Asserting the error alone is what let a
    # create-on-failed-lookup defect pass review once already.
    $script:ApiLog.Add("$Method $Path")
    if ($i -ge $script:ApiResponses.Count) { return $script:ApiResponses[-1] }
    return $script:ApiResponses[$i]
}
function Write-Fail($msg) { throw "WRITE-FAIL: $msg" }
# Stubbed so a poll that is SUPPOSED to retry costs no wall clock.  The
# ApiCalls counter, not the clock, is what proves a loop terminates.
function Start-Sleep { param([int]$Seconds) }
function Reset-Api($responses) {
    $script:ApiResponses = @($responses)
    $script:ApiCalls = 0
    $script:ApiLog = [System.Collections.Generic.List[string]]::new()
}
function Get-MutationCount {
    return @($script:ApiLog | Where-Object { $_ -match "^(POST|PUT|DELETE) " }).Count
}
function Get-Thrown($block) {
    try { & $block; return $null } catch { return "$_" }
}

# Get-DefaultPolicyId: the site the review MEASURED throwing.  Verified against
# the pre-fix template as PropertyNotFoundException: "The property
# 'policySummaries' cannot be found on this object."  It runs at InstallOrder 3
# via Install-SmEnable, i.e. after content has landed.
Reset-Api @($errShape)
$msg = Get-Thrown { Get-DefaultPolicyId }
Assert ($msg -like "*WRITE-FAIL: No default policy found*HTTP 500*") "error envelope yields an operator sentence naming the status, not PropertyNotFoundException"
Assert ($msg -notlike "*cannot be found on this object*") "the StrictMode PropertyNotFoundException is gone"
# First summary deliberately omits defaultPolicy: JSON drops false booleans,
# and the old $p.defaultPolicy threw on exactly that.
Reset-Api @('{"policySummaries":[{"id":"p1"},{"id":"p2","defaultPolicy":true}]}' | ConvertFrom-Json)
Assert ((Get-DefaultPolicyId) -eq "p2") "a summary lacking defaultPolicy is skipped, not fatal"
Reset-Api @('{"policySummaries":[]}' | ConvertFrom-Json)
Assert ((Get-Thrown { Get-DefaultPolicyId }) -like "*No default policy found*") "empty list still reaches the operator sentence"

# Get-SupermetricsByName: paging loop bounded by pageInfo.totalCount.
Reset-Api @($errShape)
$msg = Get-Thrown { Get-SupermetricsByName -Names @("sm-a") }
Assert ($msg -like "*Super metric lookup failed (HTTP 500)*") "a failed lookup refuses rather than returning an empty map"
Assert ((Get-MutationCount) -eq 0) "and nothing is mutated"
Reset-Api @('{"superMetrics":[{"name":"sm-a","id":"1"},{"id":"no-name"}],"pageInfo":{"totalCount":2}}' | ConvertFrom-Json)
$f = Get-SupermetricsByName -Names @("sm-a")
Assert ($f["sm-a"] -eq "1") "matching super metric mapped to its id"
Assert ($f.Count -eq 1) "an item with no name is skipped rather than throwing"

# Find-CustomGroupIds: same shape, different collection member.
Reset-Api @($errShape)
$msg = Get-Thrown { Find-CustomGroupIds -Names @("g") }
Assert ($msg -like "*Custom group lookup failed (HTTP 500)*") "a failed lookup refuses rather than returning an empty map"
Reset-Api @('{"groups":[{"id":"gid","resourceKey":{"name":"g"}},{"id":"other"}],"pageInfo":{"totalCount":2}}' | ConvertFrom-Json)
$f = Find-CustomGroupIds -Names @("g")
Assert ($f["g"] -eq "gid") "matching group mapped to its id"
Assert ($f.Count -eq 1) "a group with no resourceKey is skipped rather than throwing"

# Upsert-CustomGroup -- THE REGRESSION THE #109 SWEEP INTRODUCED.
#
# The lookup GET chooses between PUT (update) and POST (create).  Converting it
# to Get-PropList made an error envelope yield @(), which is indistinguishable
# from "no such group", so a transient 500 fell through to POST and created a
# SECOND custom group with the same name, printing "OK  Created".  Pre-sweep
# this site threw, which was uglier and safer.
#
# The assertion here previously checked only that SOMETHING threw.  It passed
# because the stubbed POST also returned an error -- it was testing the stub.
# It now asserts that ZERO mutating requests were sent, which is the property
# that actually matters and which the buggy code could not satisfy.
$payload = '{"resourceKey":{"name":"[VCF Content Factory] G"}}' | ConvertFrom-Json
Reset-Api @($errShape, ('{"ok":true}' | ConvertFrom-Json))
$msg = Get-Thrown { Upsert-CustomGroup -Payload $payload }
# NOTE: no [ ] in this pattern.  -like treats them as a character class, and a
# backtick escape inside a double-quoted string is consumed before -like sees
# it, so a bracketed pattern silently never matches.
Assert ($msg -like "*Custom group lookup for*G' failed (HTTP 500)*") "a failed lookup names itself and the status"
Assert ($msg -like "*this step stopped before acting*") "and says it stopped before acting (a claim that stays true wherever the guard sits, unlike 'nothing was modified')"
Assert ((Get-MutationCount) -eq 0) "NO POST/PUT/DELETE is sent after a failed lookup -- no duplicate group is created"
Assert ($script:ApiLog.Count -eq 1) "and the run stops at the lookup itself"

# Same shape via the 500-PUT verification path: "the group exists so the 500
# was spurious" is a state claim that a failed verification lookup cannot make.
Reset-Api @(('{"groups":[{"id":"gid","resourceKey":{"name":"[VCF Content Factory] G"}}]}' | ConvertFrom-Json), $errShape, $errShape)
$msg = Get-Thrown { Upsert-CustomGroup -Payload $payload }
Assert ($msg -like "*PUT verification lookup*failed (HTTP 500)*") "a failed verification lookup is not downgraded to 'PUT failed'"

# Healthy paths still work, and still mutate exactly once.
Reset-Api @(('{"groups":[{"id":"gid","resourceKey":{"name":"[VCF Content Factory] G"}}]}' | ConvertFrom-Json), ('{"ok":true}' | ConvertFrom-Json))
Assert ($null -eq (Get-Thrown { Upsert-CustomGroup -Payload $payload })) "existing group takes the update branch cleanly"
Assert ((Get-MutationCount) -eq 1 -and $script:ApiLog[1] -like "PUT *") "and updates rather than creating"
Reset-Api @(('{"groups":[]}' | ConvertFrom-Json), ('{"ok":true}' | ConvertFrom-Json))
Assert ($null -eq (Get-Thrown { Upsert-CustomGroup -Payload $payload })) "a genuine empty 200 result still creates"
Assert ((Get-MutationCount) -eq 1 -and $script:ApiLog[1] -like "POST *") "and it is a POST"

# Uninstall-Alerts: representative of the four symptom/alert paging loops.
# W1: "not found (already removed?)" is a claim about instance state.  Derived
# from a lookup that returned HTTP 500, it is a confident false statement that
# lands in the advisory trailer.  All four uninstall paths must refuse instead.
Reset-Api @($errShape)
$ctx = @{ Names = @("[VCF Content Factory] A"); Warnings = [System.Collections.Generic.List[string]]::new() }
$msg = Get-Thrown { $null = @(Uninstall-Alerts $ctx 6>&1 3>&1) }
Assert ($msg -like "*Alert lookup (uninstall) failed (HTTP 500)*") "a failed uninstall lookup refuses"
Assert ($ctx.Warnings.Count -eq 0) "and does NOT claim the alert was already removed"
Assert ((Get-MutationCount) -eq 0) "and attempts no DELETE"

Reset-Api @($errShape)
$ctx = @{ Names = @("[VCF Content Factory] S"); Warnings = [System.Collections.Generic.List[string]]::new() }
$msg = Get-Thrown { $null = @(Uninstall-Supermetrics $ctx 6>&1 3>&1) }
Assert ($msg -like "*Super metric lookup failed (HTTP 500)*") "same for super metrics"
Assert ($ctx.Warnings.Count -eq 0 -and (Get-MutationCount) -eq 0) "no false 'already removed', no DELETE"

Reset-Api @($errShape)
$ctx = @{ Names = @("[VCF Content Factory] G"); Warnings = [System.Collections.Generic.List[string]]::new() }
$msg = Get-Thrown { $null = @(Uninstall-CustomGroups $ctx 6>&1 3>&1) }
Assert ($msg -like "*Custom group lookup failed (HTTP 500)*") "same for custom groups"
Assert ($ctx.Warnings.Count -eq 0 -and (Get-MutationCount) -eq 0) "no false 'already removed', no DELETE"

# A genuine 200-with-no-match must STILL report not-found: the guard must not
# have flattened the real not-found path into an error.
Reset-Api @(('{"alertDefinitions":[],"pageInfo":{"totalCount":0}}' | ConvertFrom-Json))
$ctx = @{ Names = @("[VCF Content Factory] A"); Warnings = [System.Collections.Generic.List[string]]::new() }
$null = @(Uninstall-Alerts $ctx 6>&1 3>&1)
Assert ($ctx.Warnings.Count -eq 1 -and $ctx.Warnings[0] -like "Alert not found*") "a real empty 200 still reports not-found"
Assert ((Get-MutationCount) -eq 0) "and still attempts no DELETE"

# Install-Symptoms: the create-on-failed-lookup shape on the symptom path.
Reset-Api @($errShape, ('{"ok":true}' | ConvertFrom-Json))
$script:StubSymptoms = @('{"name":"[VCF Content Factory] Sym"}' | ConvertFrom-Json)
function Load-JsonFile($Path) { return $script:StubSymptoms }
$msg = Get-Thrown { $null = @(Install-Symptoms @{ BundleDir = "/b"; Manifest = ([pscustomobject]@{ content = [pscustomobject]@{ symptoms = [pscustomobject]@{ file = "/b/s.json" } } }) } 6>&1) }
Assert ($msg -like "*Symptom lookup for*failed (HTTP 500)*") "a failed symptom lookup refuses"
Assert ((Get-MutationCount) -eq 0) "and creates no duplicate symptom"

# BOUNDARY, pinned so it is not later mistaken for a gap in the guard: a 200
# carrying an explicit null collection still CREATES, exactly as on main.  null
# and [] both legitimately mean "empty instance", so refusing on either would
# break first install on a clean box.  Only a non-200 means "we do not know".
Reset-Api @(('{"groups":null}' | ConvertFrom-Json), ('{"ok":true}' | ConvertFrom-Json))
Assert ($null -eq (Get-Thrown { Upsert-CustomGroup -Payload $payload })) "a 200 with a null collection still creates (clean-box first install)"
Assert ((Get-MutationCount) -eq 1 -and $script:ApiLog[1] -like "POST *") "and it is a POST, not a refusal"

# Get-OwnerId: extracted so this guard is reachable at all.
Reset-Api @(('{"id":"u-123"}' | ConvertFrom-Json))
Assert ((Get-OwnerId) -eq "u-123") "owner id read from a healthy currentuser response"
Reset-Api @(('{"username":"admin"}' | ConvertFrom-Json))
Assert ((Get-Thrown { Get-OwnerId }) -like "*returned no user id*") "a currentuser response with no id stops the install"
Reset-Api @($errShape)
Assert ((Get-Thrown { Get-OwnerId }) -like "*currentuser failed*") "an error envelope stops the install"

# Get-MarkerFilename: the four export-status conversions.  -TimeoutSeconds 0
# makes each deadline immediate, so this costs no wall clock.
#
# THE CODEX P2 GUARD (PR #120).  The prior-export wait loop is a POLL whose
# exit condition is "no export is running".  Get-PropValue returns "" for a
# member that is not there, and an error envelope has no "state" at all, so
# before the status gate ONE transient 5xx concluded idle, the probe POST
# below overlapped a live export, and the install died task-busy.  The
# assertion this replaces pinned exactly that: it asserted the error envelope
# "reaches the export POST status check", i.e. it pinned the defect.
Reset-Api @($errShape)
$msg = Get-Thrown { Get-MarkerFilename -TimeoutSeconds 0 }
Assert ($msg -like "*Timed out waiting for prior export to finish*HTTP 500*") "an error envelope on the prior-export poll does NOT conclude idle; it polls to the deadline and fails naming the status"
Assert ((Get-MutationCount) -eq 0) "and no marker-probe export is POSTed while the instance state is unknown"

# The same envelope, transient rather than sticky: the poll is supposed to
# outlast it.  This is why Assert-LookupOk is not the right instrument here --
# it would refuse on the first non-200 and abort a recoverable install.
# Start-Sleep is stubbed away above, so the retry costs no wall clock.
# The 503 is the POST response, so reaching it is the proof the poll recovered;
# the run stops there rather than walking on into the zip download.
$busyShape = @{ __statusCode = 503; __body = "busy" }
$finished = '{"state":"FINISHED","startTime":1}' | ConvertFrom-Json
Reset-Api @($errShape, $finished, $finished, $busyShape)
$msg = Get-Thrown { Get-MarkerFilename -TimeoutSeconds 30 }
Assert ($msg -like "*Marker-probe export failed (503)*") "a TRANSIENT error on the poll is outlasted, not fatal: the poll recovers and reaches the probe POST"
Assert (@($script:ApiLog | Where-Object { $_ -like "POST *" }).Count -eq 1) "and the probe export is POSTed exactly once"

# BOUNDARY, pinned deliberately: a 200 carrying no "state" IS idle.  That is
# the never-exported instance, and it is what install.py:362-365 does.
# Refusing there would burn the full timeout and abort first install on a
# clean box.  Only a non-200 means "we do not know".
Reset-Api @(('{"ok":true}' | ConvertFrom-Json))
$msg = Get-Thrown { Get-MarkerFilename -TimeoutSeconds 0 }
Assert ($msg -notlike "*Timed out waiting for prior export*") "a 200 with no state is treated as idle (never-exported instance), not as a stall"
Assert ($msg -like "*Marker-probe export timed out*") "and the run proceeds to the probe export"

Reset-Api @(('{"state":"RUNNING"}' | ConvertFrom-Json))
$msg = Get-Thrown { Get-MarkerFilename -TimeoutSeconds 0 }
Assert ($msg -like "*Timed out waiting for prior export*state=RUNNING*") "a genuinely RUNNING prior export still times out, and the sentence names the state"
Assert ((Get-MutationCount) -eq 0) "and still POSTs nothing"

# The post-POST wait loop, same class: a non-200 there must not satisfy the
# exit condition either.  It keeps polling (the export is already running;
# outlasting a blip is the recoverable answer) and names the status at the
# deadline.
Reset-Api @(('{"state":"FINISHED","startTime":1}' | ConvertFrom-Json), ('{"state":"FINISHED","startTime":1}' | ConvertFrom-Json), ('{"ok":true}' | ConvertFrom-Json), $errShape)
$msg = Get-Thrown { Get-MarkerFilename -TimeoutSeconds 0 }
Assert ($msg -like "*Marker-probe export timed out*HTTP 500*") "an error envelope on the post-POST wait loop does not read as FINISHED, and the timeout sentence names the status"
$fin = '{"state":"FINISHED","startTime":1}' | ConvertFrom-Json
Reset-Api @($fin, $fin, ('{"ok":true}' | ConvertFrom-Json), ('{"state":"FINISHED"}' | ConvertFrom-Json))
Assert ((Get-Thrown { Get-MarkerFilename -TimeoutSeconds 0 }) -like "*Marker-probe export timed out; state=FINISHED*") "the third loop reads a status envelope with no startTime without throwing"

# ===========================================================================
# Issue #108 -- SM ghost-state retry
# ===========================================================================
# Ghost state: an SM exists in the DB but never registered in the SM catalog,
# so the importer skips it and a later enable 404s.  Re-importing the same zip
# re-registers it.  install.py has done this since it was written; install.ps1
# threw the import status away, so Windows operators got a clean-looking
# install with invisible SMs.
Assert ((Get-SmGhostStateSkipCount -Result $null) -eq 0) "null result: no retry"
Assert ((Get-SmGhostStateSkipCount -Result $errShape) -eq 0) "error envelope: no retry, no throw"
Assert ((Get-SmGhostStateSkipCount -Result ('{"state":"FINISHED"}' | ConvertFrom-Json)) -eq 0) "envelope with no operationSummaries: no retry"
$ghost = '{"operationSummaries":[{"contentType":"SUPER_METRICS","imported":0,"skipped":4,"failed":0,"state":"FINISHED"}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $ghost) -eq 4) "imported=0/skipped=4 is the ghost signature; skip count returned"
$partial = '{"operationSummaries":[{"contentType":"SUPER_METRICS","imported":1,"skipped":3}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $partial) -eq 0) "imported>0 is a partial import, not ghost state"
$clean = '{"operationSummaries":[{"contentType":"SUPER_METRICS","imported":4,"skipped":0}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $clean) -eq 0) "a clean import does not retry"
$noCounts = '{"operationSummaries":[{"contentType":"SUPER_METRICS"}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $noCounts) -eq 0) "summary with no counts: no retry, no throw"
# install.py sums across SUPER_METRICS summaries; so must this.
$multi = '{"operationSummaries":[{"contentType":"SUPER_METRICS","imported":0,"skipped":2},{"contentType":"SUPER_METRICS","imported":0,"skipped":3}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $multi) -eq 5) "skips summed across multiple SUPER_METRICS summaries"
$multiMixed = '{"operationSummaries":[{"contentType":"SUPER_METRICS","imported":0,"skipped":2},{"contentType":"SUPER_METRICS","imported":1,"skipped":0}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $multiMixed) -eq 0) "any import across the summed summaries suppresses the retry"

# THE #114 GUARD.  Do not delete this assertion to make a generalisation pass.
# #114 bisected the identical imported=0/skipped=N signature on DASHBOARDS and
# VIEW_DEFINITIONS and found a different cause: create-only mode (force=false),
# where the skip is idempotent and a retry is a guaranteed no-op costing a
# round trip plus a 30s import-busy backoff.  See
# knowledge/context/api-surface/content_import_skip_semantics.md.
$dashSkip = @'
{"operationSummaries":[
 {"contentType":"DASHBOARDS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"},
 {"contentType":"VIEW_DEFINITIONS","imported":0,"skipped":1,"failed":0,"state":"FINISHED"}]}
'@ | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $dashSkip) -eq 0) "an all-skipped DASHBOARDS/VIEW_DEFINITIONS import NEVER triggers the SM retry"
$reportsSkip = '{"operationSummaries":[{"contentType":"REPORTS","imported":0,"skipped":2}]}' | ConvertFrom-Json
Assert ((Get-SmGhostStateSkipCount -Result $reportsSkip) -eq 0) "nor does an all-skipped REPORTS import"

# --- Install-Supermetrics actually retries ---------------------------------
# Redefines the Import-ContentZip stub used by the Install-Dashboard block
# above; that block has already run.
$script:SmImportLabels = [System.Collections.Generic.List[string]]::new()
$script:SmImportResults = @()
function Import-ContentZip {
    param($ZipBytes, $Label, $TimeoutSeconds, $Retries)
    $i = $script:SmImportLabels.Count
    $script:SmImportLabels.Add($Label)
    if ($i -ge $script:SmImportResults.Count) { return $script:SmImportResults[-1] }
    return $script:SmImportResults[$i]
}
function Load-JsonFile($Path) { return $script:StubSmDict }
function New-SmZip { param($SmDict, $Marker, $OwnerId) return [byte[]]@(1, 2) }
$script:StubSmDict = [pscustomobject]@{ "sm-a" = 1; "sm-b" = 2 }
function New-SmCtx {
    return @{
        BundleDir = "/b"
        Manifest  = ([pscustomobject]@{ content = [pscustomobject]@{
            supermetrics = [pscustomobject]@{ file = "/b/sm.json" } } })
        Marker    = "m"
        OwnerId   = "u1"
    }
}
function Invoke-SmInstall($results) {
    $script:SmImportLabels = [System.Collections.Generic.List[string]]::new()
    $script:SmImportResults = @($results)
    $out = @(Install-Supermetrics (New-SmCtx) 6>&1)
    return $out
}

$out = Invoke-SmInstall @($ghost, $clean)
Assert ($script:SmImportLabels.Count -eq 2) "ghost signature triggers exactly one retry"
Assert ($script:SmImportLabels[0] -eq "super metrics" -and $script:SmImportLabels[1] -eq "super metrics (retry)") "the retry is the same zip under a distinguishable label, matching install.py"
Assert ((($out | ForEach-Object { "$_" }) -join "`n") -like "*ghost-state recovery*4 SM(s) skipped*") "the operator is told a recovery happened, and how many"

$null = Invoke-SmInstall @($clean)
Assert ($script:SmImportLabels.Count -eq 1) "a clean import imports once"

$null = Invoke-SmInstall @($errShape)
Assert ($script:SmImportLabels.Count -eq 1) "an error envelope does not trigger a retry"

$null = Invoke-SmInstall @($dashSkip)
Assert ($script:SmImportLabels.Count -eq 1) "a dashboard-shaped skip envelope does not trigger the SM retry"

$null = Invoke-SmInstall @(($multi), $clean)
Assert ($script:SmImportLabels.Count -eq 2) "summed multi-summary ghost signature retries once"

# The retry fires at most once even if it also comes back all-skipped: the
# second envelope is never re-examined.
$null = Invoke-SmInstall @($ghost, $ghost)
Assert ($script:SmImportLabels.Count -eq 2) "retry is once, not a loop, even when the retry also reports all-skipped"

# --- W4: Import-ContentZip must emit EXACTLY the status object -------------
# Install-Supermetrics's retry reads operationSummaries off the value
# Import-ContentZip returns.  PowerShell appends every uncaptured expression to
# a function's output stream, so one future `$list.Add($x)` on an ArrayList, or
# one un-piped cmdlet call, would make $importResult an ARRAY.  Get-PropList
# would then find no operationSummaries on element 0, Get-SmGhostStateSkipCount
# would return 0, and the ghost-state retry would silently stop happening --
# with every behavioural assertion in this file still green, because they all
# stub Import-ContentZip.
#
# This is therefore checked structurally against the REAL function.
function Test-Captured($Node, $StopAt) {
    # True when $Node's value is consumed (assigned, returned, used as a
    # condition or argument) rather than falling onto the output stream.
    $n = $Node.Parent
    while ($null -ne $n -and $n -ne $StopAt) {
        if ($n -is [System.Management.Automation.Language.AssignmentStatementAst] -or
            $n -is [System.Management.Automation.Language.ParenExpressionAst] -or
            $n -is [System.Management.Automation.Language.SubExpressionAst] -or
            $n -is [System.Management.Automation.Language.ReturnStatementAst] -or
            $n -is [System.Management.Automation.Language.IfStatementAst] -or
            $n -is [System.Management.Automation.Language.CommandAst]) {
            return $true
        }
        $n = $n.Parent
    }
    return $false
}

$icz = $null
foreach ($f in $fns) { if ($f.Name -eq "Import-ContentZip") { $icz = $f } }
Assert ($null -ne $icz) "Import-ContentZip located in the template"

$returns = $icz.Body.FindAll({
    param($n) $n -is [System.Management.Automation.Language.ReturnStatementAst]
}, $true)
Assert ($returns.Count -eq 1) "Import-ContentZip has exactly one return statement"
Assert ($returns[0].Pipeline.Extent.Text -eq '$s') "and it returns the polled status object"

# Commands are void-by-contract or captured; anything else lands on the
# output stream and corrupts the return value.
$voidCommands = @("Write-Host", "Write-Ok", "Write-Warn", "Write-Fail",
                  "Write-Error", "Write-Output", "Start-Sleep", "Add-Type",
                  "Out-Null", "Remove-Item", "Write-ImportSummaryWarnings",
                  "Write-Step", "ForEach-Object", "Where-Object")
$leaked = @()
foreach ($c in $icz.Body.FindAll({
    param($n) $n -is [System.Management.Automation.Language.CommandAst]
}, $true)) {
    $nm = $c.GetCommandName()
    if ($nm -and ($voidCommands -contains $nm)) { continue }
    if (-not (Test-Captured $c $icz)) { $leaked += "$($c.Extent.StartLineNumber): $($c.Extent.Text)" }
}
Assert ($leaked.Count -eq 0) "no uncaptured command output in Import-ContentZip (would corrupt the status return and silently disable the SM retry): $($leaked -join ' | ')"

# Statement-level method calls must be void, and the allowlist is keyed by
# RECEIVER.METHOD -- never by method name alone.
#
# Keying on the method name is not a weaker version of this check, it is a
# broken one, and it broke on exactly the example its own comment cited.
# [List[T]].Add returns void; [ArrayList].Add returns the insertion INDEX.
# .Clear, .Write and .RemoveAll are receiver-dependent the same way.  So an
# allowlist containing "Add" excuses the precise trap this pin exists to
# catch: injecting
#     $scratch = New-Object System.Collections.ArrayList
#     $scratch.Add("x")
# into Import-ContentZip turns its return value from PSCustomObject into
# Object[], Get-SmGhostStateSkipCount then reads 0 instead of 4, and the #108
# ghost-state retry silently stops happening with this entire file green.
# That injection is the negative control for this assertion.
#
# The two Add sites below are void because of what they are called ON
# (HttpRequestHeaders and MultipartFormDataContent), not because they are
# called "Add" -- which is the whole point.  Deleting "Add" from a name-keyed
# list would red the assert instead of fixing it; the receiver is the fact
# that carries the meaning.
#
# Adding an entry here is a claim that THAT receiver's method returns void.
# Verify it before adding one.
$voidCalls = @(
    '$httpClient.Dispose',                      # IDisposable.Dispose -> void
    '$httpClient.DefaultRequestHeaders.Add',    # HttpRequestHeaders.Add -> void
    '$content.Add'                              # MultipartFormDataContent.Add -> void
)
$badMethods = @()
foreach ($st in $icz.Body.FindAll({
    param($n) $n -is [System.Management.Automation.Language.CommandExpressionAst]
}, $true)) {
    $expr = $st.Expression
    if ($expr -is [System.Management.Automation.Language.InvokeMemberExpressionAst]) {
        if (Test-Captured $st $icz) { continue }
        $call = "$($expr.Expression.Extent.Text).$($expr.Member.Extent.Text)"
        if ($voidCalls -notcontains $call) {
            $badMethods += "$($st.Extent.StartLineNumber): $call"
        }
    }
}
Assert ($badMethods.Count -eq 0) "statement-level method calls in Import-ContentZip are void-by-receiver: $($badMethods -join ' | ')"

# And the callers actually capture it.
foreach ($fname in @("Install-Supermetrics", "Install-Dashboard")) {
    $fn = $null
    foreach ($f in $fns) { if ($f.Name -eq $fname) { $fn = $f } }
    $calls = $fn.Body.FindAll({
        param($n) $n -is [System.Management.Automation.Language.CommandAst]
    }, $true) | Where-Object { $_.GetCommandName() -eq "Import-ContentZip" }
    $first = @($calls)[0]
    Assert ($first.Parent -is [System.Management.Automation.Language.PipelineAst] -and
            $first.Parent.Parent -is [System.Management.Automation.Language.AssignmentStatementAst]) "$fname captures the first Import-ContentZip return rather than discarding it"
}

# ===========================================================================
# Issue #116 -- Ext.Direct / dashboard.action envelopes
#
# A THIRD envelope shape, distinct from the two Get-PropValue was written for.
# Invoke-ExtDirect returns ConvertFrom-Json of an ARRAY:
#     [ { "type":"rpc", "tid":1, "result": {...} } ]
# and the callers read $result[0].type.  Verified against pwsh 7 under
# Set-StrictMode -Version Latest, the mode this file and install.ps1 both run:
#     @()[0]              -> IndexOutOfRangeException
#     (json '{}').missing -> PropertyNotFoundException
#     @{}.missingKey      -> PropertyNotFoundException
# so there are TWO failures in front of each read, and a fix that only routes
# the member read through Get-PropValue swaps the second for the first.
# ===========================================================================

$script:ExtResponses = @()
$script:ExtCalls = 0
function Invoke-ExtDirect {
    param([object[]]$Calls)
    $i = $script:ExtCalls
    $script:ExtCalls++
    if ($i -ge $script:ExtResponses.Count) { return $script:ExtResponses[-1] }
    return $script:ExtResponses[$i]
}
function Invoke-DashboardAction {
    param([hashtable]$FormFields)
    $i = $script:ExtCalls
    $script:ExtCalls++
    if ($i -ge $script:ExtResponses.Count) { return $script:ExtResponses[-1] }
    return $script:ExtResponses[$i]
}
function Reset-Ext($responses) {
    $script:ExtResponses = @($responses)
    $script:ExtCalls = 0
}
function Get-NextTid { return 1 }
# StrictMode makes an unset variable a terminating error, and these UI
# functions read script-scope session state that Start-UISession normally
# populates.  Without them the assertions below would "pass" against a
# cannot-be-retrieved error instead of the guard under test.
$script:CsrfToken = "test-csrf"
$script:OpsHost = "ops.test"
# Stubbed rather than imported: it only formats a request body, and letting it
# fail would make the Uninstall-Dashboards assertion below pass through the
# catch block instead of through the member reads it is actually testing.
function Remove-Dashboards { param([object[]]$Dashboards) }
function New-UiCtx($names) {
    return @{
        Names      = @($names)
        Warnings   = [System.Collections.Generic.List[string]]::new()
        Advisories = [System.Collections.Generic.List[string]]::new()
    }
}

# --- Get-ExtDirectResult: the index failure, IN FRONT of the member failure --
$msg = Get-Thrown { Get-ExtDirectResult -Response $null -What "View list" }
Assert ($msg -like "*no response body*") "null response yields a sentence, not a null-reference exception"
Assert ($msg -notlike "*IndexOutOfRange*" -and $msg -notlike "*cannot be found on this object*") "and neither raw .NET exception survives"

# @($null) has Count 1, NOT 0, so the null case above cannot be folded into
# this one.  If it were, $first stays $null and the type read below throws.
$msg = Get-Thrown { Get-ExtDirectResult -Response @() -What "View list" }
Assert ($msg -like "*empty response envelope*") "empty array yields a sentence, not IndexOutOfRangeException"
$msg = Get-Thrown { Get-ExtDirectResult -Response @($null) -What "View list" }
Assert ($msg -like "*empty response envelope*") "a one-element array holding null is also empty"

$exc = '[{"type":"exception","message":"Internal server error."}]' | ConvertFrom-Json
$msg = Get-Thrown { Get-ExtDirectResult -Response $exc -What "deleteView v1" }
Assert ($msg -like "*deleteView v1 failed: Internal server error.*") "an exception envelope keeps the server's own message"
$excNoMsg = '[{"type":"exception"}]' | ConvertFrom-Json
$msg = Get-Thrown { Get-ExtDirectResult -Response $excNoMsg -What "deleteView v1" }
Assert ($msg -like "*no message supplied*") "an exception envelope with no message member does not throw reading it"

# -Fatal picks the reporting channel, nothing else.  Write-Fail is stubbed at
# the top of this file to throw WRITE-FAIL: rather than exit.
$msg = Get-Thrown { Get-ExtDirectResult -Response @() -What "View list" -Fatal }
Assert ($msg -like "WRITE-FAIL: *empty response envelope*") "-Fatal routes through Write-Fail"
$msg = Get-Thrown { Get-ExtDirectResult -Response @() -What "View list" }
Assert ($msg -notlike "WRITE-FAIL:*") "without -Fatal it throws, so the caller's try/catch can downgrade it to a warning"

$ok = '[{"type":"rpc","tid":1,"result":{"a":1}}]' | ConvertFrom-Json
Assert ((Get-ExtDirectResult -Response $ok -What "x").a -eq 1) "a healthy envelope returns its result payload"

# The Invoke-Api hashtable shape reaches this helper only if someone wires it
# up wrong, but Get-PropValue supports it and so must this.
Assert ((Get-ExtDirectResult -Response @(@{ type = "rpc"; result = "payload" }) -What "x") -eq "payload") "IDictionary envelope supported, matching Get-PropValue's two branches"

# -RequireResult is the Assert-LookupOk of this family: it is about DECISIONS,
# not about reading.
$noResult = '[{"type":"rpc","tid":1}]' | ConvertFrom-Json
Assert ($null -eq (Get-ExtDirectResult -Response $noResult -What "deleteView v1")) "without -RequireResult an absent result is simply null: the delete callers discard it"
$msg = Get-Thrown { Get-ExtDirectResult -Response $noResult -What "View list" -RequireResult }
Assert ($msg -like "*refusing to treat that as an empty list*") "with -RequireResult an absent result refuses rather than degrading to 'nothing exists'"
$nullResult = '[{"type":"rpc","tid":1,"result":null}]' | ConvertFrom-Json
$msg = Get-Thrown { Get-ExtDirectResult -Response $nullResult -What "Report list" -RequireResult }
Assert ($msg -like "*refusing to treat that as an empty list*") "a present-but-null result is also refused: Get-AllReports would dereference it"

# The unary comma in the return.  Without it PowerShell unrolls the array and
# a 1-element result list arrives at Get-AllReports as a bare object, missing
# its `-is [System.Array]` branch.
$oneItem = '[{"type":"rpc","result":[{"id":"r1"}]}]' | ConvertFrom-Json
$got = Get-ExtDirectResult -Response $oneItem -What "Report list" -RequireResult
Assert ($got -is [System.Array] -and $got.Count -eq 1) "a 1-element array result is NOT unrolled on return"
$emptyItems = '[{"type":"rpc","result":[]}]' | ConvertFrom-Json
$got = Get-ExtDirectResult -Response $emptyItems -What "Report list" -RequireResult
Assert ($got -is [System.Array] -and $got.Count -eq 0) "an empty array result survives as an empty array, not as null"

# --- Get-AllViews ----------------------------------------------------------
# Note on the empty-array case at CALLER level: PowerShell unrolls a returned
# array, so a transport that answers with @() delivers $null to its caller,
# not an empty array.  Both collapse to the same operator sentence here, which
# is why Get-ExtDirectResult guards $null and Count separately -- the unit
# tests above bind @() as a PARAMETER, where it survives, and reach the other
# branch.
Reset-Ext @(, @())
$msg = Get-Thrown { Get-AllViews }
Assert ($msg -like "WRITE-FAIL: View list failed*") "Get-AllViews on an empty envelope array: operator sentence, not IndexOutOfRangeException"
Reset-Ext @($exc)
$msg = Get-Thrown { Get-AllViews }
Assert ($msg -like "*View list failed: Internal server error.*") "Get-AllViews surfaces the server's exception message"
Reset-Ext @($noResult)
$msg = Get-Thrown { Get-AllViews }
Assert ($msg -like "*refusing to treat that as an empty list*") "Get-AllViews refuses an envelope with no result rather than reporting zero views"

$grouped = '[{"type":"rpc","result":{"LIST":{"HostSystem":[{"name":"V1","id":"i1"},{"name":"V2","viewDefinitionKey":"k2"}]}}}]' | ConvertFrom-Json
Reset-Ext @($grouped)
$views = Get-AllViews
Assert ($views.Count -eq 2) "a healthy grouped payload still flattens to the view list"

# WRONG SHAPE is the case -RequireResult does NOT close, and the one the
# residual `else` used to swallow.  A present result that is a string, a bool,
# or an array is not an exception, is not null, and is not absent -- it simply
# is not the shape this endpoint documents.  Returning an empty list for it
# makes the uninstall print "not found (already removed?)" about content that
# is still on the instance, which is the sentence
# knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md lists as an
# instance of this defect.
foreach ($bad in @('"a string"', 'true', '[]')) {
    Reset-Ext @(("[{""type"":""rpc"",""result"":$bad}]" | ConvertFrom-Json))
    $msg = Get-Thrown { Get-AllViews }
    Assert ($msg -like "WRITE-FAIL: View list failed*unrecognised shape*") "Get-AllViews refuses a result of shape $bad rather than reporting zero views"
    Assert ($msg -notlike "*already removed*") "and never reaches the sentence that claims the instance is clean"
}
# The shape that IS legitimate must still pass: an empty object is a real
# instance with no views, not a broken envelope.
Reset-Ext @(('[{"type":"rpc","result":{}}]' | ConvertFrom-Json))
Assert ((@(Get-AllViews)).Count -eq 0) "an empty grouped object is a genuinely empty instance, and is NOT refused"

# --- Remove-View -----------------------------------------------------------
Reset-Ext @(, @())
$msg = Get-Thrown { Remove-View -ViewId "v1" -ViewName "V1" }
Assert ($msg -like "*deleteView v1 failed*") "Remove-View on an empty envelope array throws a sentence"
Assert ($msg -notlike "*IndexOutOfRange*" -and $msg -notlike "*cannot be found on this object*") "and not a raw .NET exception partway through the uninstall"
Assert ($msg -notlike "WRITE-FAIL:*") "and it throws rather than exiting, so one bad view does not abandon the uninstall"
Reset-Ext @($exc)
$msg = Get-Thrown { Remove-View -ViewId "v1" -ViewName "V1" }
Assert ($msg -like "*deleteView v1 failed: Internal server error.*") "Remove-View keeps the server message"
Reset-Ext @($noResult)
Assert ($null -eq (Get-Thrown { Remove-View -ViewId "v1" -ViewName "V1" })) "a delete whose envelope carries no result payload still counts as success"

# --- Get-AllReports --------------------------------------------------------
Reset-Ext @(, @())
$msg = Get-Thrown { Get-AllReports }
Assert ($msg -like "WRITE-FAIL: Report list failed*") "Get-AllReports on an empty envelope array: operator sentence"
Reset-Ext @($nullResult)
$msg = Get-Thrown { Get-AllReports }
Assert ($msg -like "*refusing to treat that as an empty list*") "Get-AllReports refuses result:null instead of dereferencing it"
Assert ($msg -notlike "*null-valued expression*") "and the null-reference exception it used to raise is gone"
$records = '[{"type":"rpc","result":{"records":[{"name":"R1","id":"ri1"}],"total":1}}]' | ConvertFrom-Json
Reset-Ext @($records)
$reports = @(Get-AllReports)
Assert ($reports.Count -eq 1) "a healthy records payload still returns the reports"

# Same residual-else in Get-AllReports.  Note the asymmetry with Get-AllViews:
# a bare ARRAY is a documented shape here (returned as the list directly), so
# only a scalar reaches the fallback.
foreach ($bad in @('"a string"', 'true')) {
    Reset-Ext @(("[{""type"":""rpc"",""result"":$bad}]" | ConvertFrom-Json))
    $msg = Get-Thrown { Get-AllReports }
    Assert ($msg -like "WRITE-FAIL: Report list failed*unrecognised shape*") "Get-AllReports refuses a result of shape $bad rather than reporting zero reports"
}
Reset-Ext @(('[{"type":"rpc","result":[]}]' | ConvertFrom-Json))
Assert ($null -eq (Get-Thrown { Get-AllReports })) "a bare empty array IS a documented report-list shape and is not refused"
Reset-Ext @(('[{"type":"rpc","result":{"records":[],"total":0}}]' | ConvertFrom-Json))
Assert ((@(Get-AllReports)).Count -eq 0) "records:[] is a genuinely empty instance, and is NOT refused"

# --- Get-AllDashboards (dashboard.action, NOT Ext.Direct) ------------------
Reset-Ext @('{"other":1}' | ConvertFrom-Json)
$msg = Get-Thrown { Get-AllDashboards }
Assert ($msg -like "WRITE-FAIL: Dashboard list failed*refusing to treat that as an empty dashboard list*") "a response with no 'dashboards' field refuses rather than reporting zero dashboards"
Assert ($msg -notlike "*cannot be found on this object*") "and the PropertyNotFoundException is gone"
# The distinction the refusal above depends on: [] is PRESENT and empty.
Reset-Ext @('{"dashboards":[]}' | ConvertFrom-Json)
Assert ((@(Get-AllDashboards)).Count -eq 0) "a genuinely empty instance still reports zero, and does NOT refuse"
Reset-Ext @('{"dashboards":[{"name":"D1","id":"di1"}]}' | ConvertFrom-Json)
Assert ((@(Get-AllDashboards)).Count -eq 1) "a healthy dashboard list still comes through"

# --- the per-item reads on the uninstall path ------------------------------
# These objects come off the wire too, and #109's sweep never reached them.
Reset-Ext @($grouped)
$ctx = New-UiCtx @("V2")
$msg = Get-Thrown { Uninstall-Views $ctx }
Assert ($null -eq $msg) "a view thumbnail carrying viewDefinitionKey but NO id does not throw: the if/else condition itself was the exposure"
Reset-Ext @(('[{"type":"rpc","result":{"LIST":{"HostSystem":[{"id":"i1"},{"name":"V2","viewDefinitionKey":"k2"}]}}}]' | ConvertFrom-Json))
$ctx = New-UiCtx @("V2")
$msg = Get-Thrown { Uninstall-Views $ctx }
Assert ($null -eq $msg) "a view thumbnail with no name at all is skipped, not fatal"

Reset-Ext @('{"dashboards":[{"id":"di1"},{"name":"D1","id":"di2"}]}' | ConvertFrom-Json)
$ctx = New-UiCtx @("D1")
$msg = Get-Thrown { Uninstall-Dashboards $ctx }
Assert ($null -eq $msg) "a dashboard thumbnail missing 'name' does not abort the uninstall"

Reset-Ext @(('[{"type":"rpc","result":{"records":[{"id":"ri1"},{"name":"R1","id":"ri2"}]}}]' | ConvertFrom-Json))
$ctx = New-UiCtx @("R1")
$msg = Get-Thrown { Uninstall-Reports $ctx }
Assert ($null -eq $msg) "a report thumbnail missing 'name' does not abort the uninstall"

# --- structural: no raw $result[0] survives in the four Ext.Direct callers --
# The behavioural assertions above all drive the helper.  This one pins that
# nobody reintroduces a direct index next to it.
# Keyed on a NUMERIC index specifically: Get-AllDashboards legitimately does
# $result["dashboards"], which is a key lookup on a different envelope shape,
# not an index into an array of Ext.Direct envelopes.
foreach ($fname in @("Get-AllViews", "Get-AllReports", "Remove-View", "Remove-Reports", "Get-AllDashboards")) {
    $fn = $null
    foreach ($f in $fns) { if ($f.Name -eq $fname) { $fn = $f } }
    $bad = @()
    foreach ($ix in $fn.Body.FindAll({
        param($n) $n -is [System.Management.Automation.Language.IndexExpressionAst]
    }, $true)) {
        $isNumeric = ($ix.Index -is [System.Management.Automation.Language.ConstantExpressionAst] -and
                      $ix.Index.Value -is [int])
        if ($ix.Target.Extent.Text -eq '$result' -and $isNumeric) {
            $bad += "$($ix.Extent.StartLineNumber): $($ix.Extent.Text)"
        }
    }
    Assert ($bad.Count -eq 0) "$fname never indexes the response array directly; the guard is Get-ExtDirectResult's job: $($bad -join ' | ')"
}

# ===========================================================================
# Issue #121 -- the import-wait timeout names the last-seen HTTP status
# ===========================================================================
$icz2 = $null
foreach ($f in $fns) { if ($f.Name -eq "Import-ContentZip") { $icz2 = $f } }
$iczText = $icz2.Extent.Text
Assert ($iczText -notmatch 'timed out; state=\$state"') "the bare state= timeout sentence is gone"
Assert ($iczText -match 'timed out; state=\$state \(last status HTTP \$sc\)') "the import-wait timeout names the last-seen HTTP status, matching the marker-probe loop"
Assert ($iczText -match '\$sc = Get-StatusCode \$s') "and the status is actually tracked each poll rather than interpolated from nothing"

# ===========================================================================
# Issue #119 -- Get-Content reads are encoding-pinned
# ===========================================================================
# Every Get-Content in the template must name -Encoding.  Unpinned, PowerShell
# 5.1 decodes a UTF-8 bundle as the system ANSI code page and ConvertFrom-Json
# parses the mojibake happily: a successful install with corrupted names.
$unpinned = @()
foreach ($c in $ast.FindAll({
    param($n) $n -is [System.Management.Automation.Language.CommandAst]
}, $true)) {
    if ($c.GetCommandName() -ne "Get-Content") { continue }
    $hasEncoding = $false
    foreach ($el in $c.CommandElements) {
        if ($el -is [System.Management.Automation.Language.CommandParameterAst] -and
            $el.ParameterName -like "Encoding*") { $hasEncoding = $true }
    }
    if (-not $hasEncoding) { $unpinned += "$($c.Extent.StartLineNumber): $($c.Extent.Text)" }
}
Assert ($unpinned.Count -eq 0) "no Get-Content call decodes with the host default: $($unpinned -join ' | ')"

Write-Host "ALL ASSERTIONS PASSED"
